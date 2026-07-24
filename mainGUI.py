"""
mainGUI.py — CustomTkinter GUI for the GIF/video media scanner.

    pip install customtkinter tkinterdnd2 python-docx

Run:
    python mainGUI.py

Notes:
- ffmpeg/ffprobe are bundled at build time under bin/Silicon (macOS arm64)
  or bin/Win64 (Windows x64) — see media_core.resolve_binaries(). Running
  from source on an unsupported platform (Intel Mac, Linux) or without the
  bin/ folder falls back to ffmpeg/ffprobe on PATH.
- python-docx is only needed if you use the "Save As" DOCX export.
- tkinterdnd2 is optional; without it the drop zone is disabled but file/
  folder buttons still work fine.
"""

import os
import re
import sys
import queue
import threading
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox

import time

import customtkinter as ctk

import modules.media_core as core
from modules.platformModules import win, mac, icon, icon_png, bundle_path, is_dev_build, is_running_from_bundle
from modules.tkModules import watermark_label, apply_emoji, animate_alpha
from modules.configModule import (
    set_setting,
    load_custom_targets,
    save_custom_target,
    delete_custom_target,
    load_presets,
    save_preset,
    delete_preset,
)


from __version__ import __author__, __version__, __appname__, __internal_app_name__

if is_dev_build:
    __appname__ = f"{__appname__} (Beta)"

ctk.set_appearance_mode("System")
theme_path = (
    os.path.join(bundle_path, "assets", "themes", "Marcel.json") if bundle_path else "./assets/themes/Marcel.json"
)
ctk.set_default_color_theme(theme_path)


def set_icon(root):
    if win:
        root.iconbitmap(icon)
    elif mac:
        root.wm_iconphoto(True, ImageTk.PhotoImage(file=icon))


icon_img = Image.open(icon_png).convert("RGBA")
icon_img = icon_img.resize((256, 256), Image.LANCZOS)
icon_img = icon_img.resize((64, 64), Image.LANCZOS)

icon_ctkImage = ctk.CTkImage(
    light_image=icon_img,
    dark_image=icon_img,
    size=(64, 64),
)

# (light, dark) tuples — same colors you picked, just packaged so CTk can
# auto-update them on an appearance-mode toggle. A plain string (what the
# if/else snapshot produced) is fixed at widget-creation time and won't
# react to set_appearance_mode() being called later; a tuple does, with
# zero extra refresh code needed anywhere a toggle button flips the mode.
dir_color = ("#b8860b", "#f1c40f")
error_color = ("#a52a2a", "#e05555")
rows_color = ("#228b22", "#50fa7b")
filename_color = ("#c71585", "#ff79c6")
text_color = ("gray30", "gray70")
dnd_text_color = ("#ede5da", "#1e1e1e")
dnd_color = ("#1e1e1e", "#ede5da")

# --------------------------------------------------------------------------
# Optional drag-and-drop support. This is the "hybrid CTk + TkinterDnD"
# patch — swap this block for your own patched class if you've already
# got one; everything below only depends on `AppBaseClass` and `DND_FILES`.
# --------------------------------------------------------------------------
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    class _CTkDnD(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)

    AppBaseClass = _CTkDnD
    DND_AVAILABLE = True
except ImportError:
    AppBaseClass = ctk.CTk
    DND_FILES = None
    DND_AVAILABLE = False


def parse_dnd_paths(data):
    """Parse a tkinterdnd2 drop event's data string into a list of paths.
    Paths with spaces are wrapped in {curly braces}."""
    return [p.strip("{}") for p in re.findall(r"\{[^}]*\}|\S+", data)]


def enable_precise_scrolling(scrollable_frame):
    """Tk 9 <TouchpadScroll> (TIP 684) support for a CTkScrollableFrame.

    Why the previous version didn't work: it bound <TouchpadScroll> only
    on the canvas + the scrollable frame itself. But the pointer is almost
    always over some *child* widget inside it (a label, a card, ...), and
    Tk dispatches events to the widget directly under the pointer — not to
    its ancestors — unless you bind on the global "all" bindtag. That's
    exactly what CTkScrollableFrame does internally for <MouseWheel> (see
    its `bind_all("<MouseWheel>", self._mouse_wheel_all)`), which is why
    regular wheel scrolling worked everywhere while this didn't. Fixed by
    mirroring that pattern: bind on "all" + walk up event.widget's .master
    chain to confirm the event actually belongs to *this* scrollable
    frame's canvas before scrolling it (same ownership check CTk uses).
    """
    if tk.TkVersion < 9.0:
        return False

    canvas = getattr(scrollable_frame, "_parent_canvas", None)
    if canvas is None:
        return False

    def _belongs_to_this_canvas(widget):
        while widget is not None:
            if widget is canvas:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _on_touchpad_scroll(event):
        if not _belongs_to_this_canvas(event.widget):
            return
        try:
            dx, dy = map(int, canvas.tk.call("tk::PreciseScrollDeltas", event.delta))
        except tk.TclError:
            return
        if dy and canvas.yview() != (0.0, 0.0):
            canvas.yview_scroll(-1 if dy > 0 else 1, "units")

    try:
        scrollable_frame.bind_all("<TouchpadScroll>", _on_touchpad_scroll, add="+")
    except tk.TclError:
        return False  # Tk build doesn't support this event — safe no-op
    return True


CHECKBOX_DEFS = [
    ("lufs", "Integrated Loudness (LUFS)", False),
    ("true_peak", "True Peak (dBTP)", False),
    ("audio_info", "Audio Track Info", False),
    ("color_info", "Color / HDR Info", False),
    ("container_info", "Container Format", False),
    ("creation_date", "Creation Date (metadata)", False),
    ("aspect_ratio", "Aspect Ratio", False),
    ("tvc_slate", "Detect TVC Slate Beep (.mov 22s/37s)", False),
]


def _all_target_names():
    """Built-in platform targets plus any custom target profiles saved via
    the "Manage Targets…" dialog or hand-edited into config.json."""
    return ["None"] + list(core.PLATFORM_TARGETS.keys()) + list(load_custom_targets().keys())


VERDICT_COLOR = {
    "pass": ("#1a7a1a", "#4fd15a"),
    "fail": ("#a52a2a", "#e05555"),
    "warn": ("#b8860b", "#f1c40f"),
}
VERDICT_BADGE = {"pass": "PASS", "fail": "FAIL", "warn": "INCOMPLETE"}

SAVE_FORMATS = [
    ("HTML (.html)", "html", ".html"),
    ("Markdown (.md)", "md", ".md"),
    ("Word Document (.docx)", "docx", ".docx"),
    ("Plain Text (.txt)", "txt", ".txt"),
]


# --------------------------------------------------------------------------
# Progress popup — shown while scanning; updated from a worker thread via
# a thread-safe queue, polled on the Tk main loop.
# --------------------------------------------------------------------------
class ProgressPopup(ctk.CTkToplevel):
    def __init__(self, master, total):
        super().__init__(master)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = 420
        height = 150
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.title("Scanning…")
        self.geometry(f"{width}x{height}+{x}+{y-35}")
        self.update_idletasks()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.grab_set()

        self.label_status = ctk.CTkLabel(self, text=f"Scanning 0 / {total}", font=("", 14, "bold"))
        self.label_status.pack(pady=(20, 6))

        self.label_file = ctk.CTkLabel(self, text="", text_color=text_color)
        self.label_file.pack(pady=(0, 12))

        self.progress = ctk.CTkProgressBar(self, width=340)
        self.progress.set(0)
        self.progress.pack(pady=(0, 10))

        self.total = max(total, 1)

    def update_progress(self, index, filename):
        max_length = 45
        if len(filename) > max_length:
            part_len = (max_length - 3) // 2
            filename = filename[:part_len] + "..." + filename[-part_len:]

        self.label_status.configure(text=f"Scanning {index} / {self.total}")
        self.label_file.configure(text=filename)
        self.progress.set(index / self.total)


# --------------------------------------------------------------------------
# Results window — scrollable, grouped by directory, with Save As / Exit.
# --------------------------------------------------------------------------
class ResultsWindow(ctk.CTkToplevel):
    def __init__(self, master, scan_results, options, root_label):
        super().__init__(master)
        self.scan_results = scan_results
        self.options = options
        self.root_label = root_label

        self.title("Scan Results")
        width = 740
        height = 800
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y-35}")
        self.minsize(560, 400)

        total_files = sum(len(e["files"]) for e in scan_results)
        error_files = sum(1 for e in scan_results for _, i in e["files"] if "error" in i)
        total_size = sum(i.get("size_bytes") or 0 for e in scan_results for _, i in e["files"] if "error" not in i)

        header = ctk.CTkLabel(
            self,
            text="",
            font=("", 15, "bold"),
        )

        summary = f"{total_files} file(s) scanned  ·  {core.human_size(total_size)}"
        if error_files:
            summary += f"  ·  {error_files} error(s)"
        verdict_counts = core.scan_verdict_counts(scan_results, options)
        if verdict_counts:
            parts = []
            if verdict_counts["pass"]:
                parts.append(f"✅ {verdict_counts['pass']} passed")
            if verdict_counts["fail"]:
                parts.append(f"❌ {verdict_counts['fail']} failed")
            if verdict_counts["warn"]:
                parts.append(f"⚠️ {verdict_counts['warn']} incomplete")
            if parts:
                summary += "  ·  " + "  ·  ".join(parts)

        apply_emoji(header, "🔍", summary, 15)
        header.pack(pady=(12, 4), padx=16, anchor="w")

        # Scrollable results area
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        enable_precise_scrolling(self.scroll)
        self._build_results()

        # Bottom bar (Save As / Exit)
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(0, 12))

        self.format_var = tk.StringVar(value=SAVE_FORMATS[0][0])
        format_menu = ctk.CTkOptionMenu(
            bottom, values=[f[0] for f in SAVE_FORMATS], variable=self.format_var, width=180
        )
        format_menu.pack(side="left")

        save_btn = ctk.CTkButton(bottom, text="", command=self._on_save, width=120)
        apply_emoji(save_btn, "💾", "Save As…")
        save_btn.pack(side="left", padx=8)

        exit_btn = ctk.CTkButton(
            bottom, text="Close", fg_color="#8b2e2e", hover_color="#6e2424", command=self._on_exit, width=90
        )
        exit_btn.pack(side="right")

    def _build_results(self):
        target_key = self.options.get("platform_target")
        target = (
            core.resolve_target(target_key, self.options.get("custom_targets"))
            if target_key and target_key != "None"
            else None
        )

        for entry in self.scan_results:
            count = len(entry["files"])
            dir_label = ctk.CTkLabel(
                self.scroll,
                text="",
                font=("", 14, "bold"),
                text_color=dir_color,
            )
            apply_emoji(dir_label, "📁", f" {entry['dir']}  ({count} file{'s' if count != 1 else ''})", 14)
            dir_label.pack(fill="x", pady=(10, 2), anchor="w")

            for filename, info in entry["files"]:
                verdict = core.evaluate_target(info, target) if target and "error" not in info else None
                verdict_status = verdict["status"] if verdict else None

                card = ctk.CTkFrame(self.scroll, corner_radius=8)
                if verdict_status in ("pass", "fail", "warn"):
                    card.configure(border_width=2, border_color=VERDICT_COLOR[verdict_status])
                card.pack(fill="x", pady=4)

                icon = "🎬" if info.get("kind") == "video" else "🖼️"
                title = ctk.CTkLabel(card, text="", font=("", 13, "bold"), text_color=filename_color)
                apply_emoji(title, icon, f" {filename}", 13)
                title.pack(anchor="w", padx=12, pady=(8, 2))

                if "error" in info:
                    err = ctk.CTkLabel(card, text=f"", text_color=error_color)
                    apply_emoji(widget=err, emoji_char="⚠️", text=f" {info['error']}")
                    err.pack(anchor="w", padx=12, pady=(0, 8))
                    continue

                if verdict_status in ("pass", "fail", "warn"):
                    badge = ctk.CTkLabel(
                        card,
                        text=f"{VERDICT_BADGE[verdict_status]}",
                        font=("", 12, "bold"),
                        text_color=VERDICT_COLOR[verdict_status],
                        anchor="w",
                    )
                    badge.pack(anchor="w", padx=12, pady=(0, 2))

                rows_frame = ctk.CTkFrame(card, fg_color="transparent")
                rows_frame.pack(fill="x", padx=12, pady=(0, 8))
                for r, (label, value) in enumerate(core.info_rows(info, self.options)):
                    lbl = ctk.CTkLabel(
                        rows_frame,
                        text=f"{label}:",
                        text_color=rows_color,
                        font=("", 12, "bold"),
                        anchor="w",
                        width=150,
                    )
                    lbl.grid(row=r, column=0, sticky="w", pady=1)
                    val = ctk.CTkLabel(rows_frame, text=str(value), anchor="w", justify="left")
                    val.grid(row=r, column=1, sticky="w", pady=1, padx=(6, 0))

    def _on_save(self):
        label = self.format_var.get()
        fmt, ext = next((f[1], f[2]) for f in SAVE_FORMATS if f[0] == label)
        path = filedialog.asksaveasfilename(
            title="Save report as…",
            defaultextension=ext,
            filetypes=[(label, f"*{ext}")],
            initialfile=f"media_scan_report{ext}",
        )
        if not path:
            return
        try:
            core.save_report(fmt, path, self.scan_results, self.options, self.root_label)
        except ImportError:
            messagebox.showerror(
                "Missing dependency", "DOCX export requires python-docx.\n\nInstall with:\npip install python-docx"
            )
            return
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        messagebox.showinfo("Saved", f"Report saved to:\n{path}")

    def _on_exit(self):
        self.destroy()


# --------------------------------------------------------------------------
# Custom target manager — add/edit/delete a client-specific QC spec, e.g.
# "needs to be within -18 to -26 LKFS" from a QC rejection notice. Stored
# via configModule (config.json's "custom_targets" key), same shape as
# core.PLATFORM_TARGETS entries so evaluate_target() treats them identically.
# --------------------------------------------------------------------------
class ManageTargetsPopup(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("Manage Custom Targets")
        width, height = 440, 400
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y - 35}")
        self.resizable(False, False)
        self.grab_set()

        ctk.CTkLabel(
            self,
            text="Custom delivery specs — e.g. a client-specific loudness\n"
            "range from a QC rejection. Stored in config.json, hand-\n"
            "editable there too if you'd rather skip this dialog.",
            font=("", 11),
            text_color="gray55",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(14, 8))

        existing_row = ctk.CTkFrame(self, fg_color="transparent")
        existing_row.pack(fill="x", padx=16)
        ctk.CTkLabel(existing_row, text="Edit existing:", font=("", 11)).pack(side="left")
        self.existing_var = tk.StringVar(value="(new)")
        self.existing_menu = ctk.CTkOptionMenu(
            existing_row,
            values=self._existing_names(),
            variable=self.existing_var,
            width=220,
            command=self._on_pick_existing,
        )
        self.existing_menu.pack(side="left", padx=(8, 0))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=16, pady=(14, 0))

        self.name_var = tk.StringVar()
        self.min_var = tk.StringVar()
        self.max_var = tk.StringVar()
        self.peak_var = tk.StringVar()
        self.notes_var = tk.StringVar()

        fields = [
            ("Name", self.name_var, "e.g. Client X Broadcast Spot"),
            ("LUFS min", self.min_var, "e.g. -26.0"),
            ("LUFS max", self.max_var, "e.g. -18.0"),
            ("True Peak max (dBTP)", self.peak_var, "e.g. -6.0 (optional)"),
            ("Notes (optional)", self.notes_var, "e.g. QC rejection ref"),
        ]
        for row, (label, var, hint) in enumerate(fields):
            ctk.CTkLabel(form, text=label, font=("", 11), anchor="w", width=150).grid(
                row=row, column=0, sticky="w", pady=4
            )
            ctk.CTkEntry(form, textvariable=var, placeholder_text=hint, width=210).grid(
                row=row, column=1, sticky="w", pady=4, padx=(6, 0)
            )

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(18, 14), side="bottom")
        ctk.CTkButton(btn_row, text="Save", command=self._on_save, width=90).pack(side="left")
        ctk.CTkButton(
            btn_row, text="Delete", fg_color="#8b2e2e", hover_color="#6e2424", command=self._on_delete, width=90
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Close", command=self.destroy, width=90).pack(side="right")

    def _existing_names(self):
        return ["(new)"] + list(load_custom_targets().keys())

    def _on_pick_existing(self, name):
        if name == "(new)":
            self.name_var.set("")
            self.min_var.set("")
            self.max_var.set("")
            self.peak_var.set("")
            self.notes_var.set("")
            return
        spec = load_custom_targets().get(name, {})
        self.name_var.set(name)
        self.min_var.set("" if spec.get("lufs_min") is None else str(spec["lufs_min"]))
        self.max_var.set("" if spec.get("lufs_max") is None else str(spec["lufs_max"]))
        self.peak_var.set("" if spec.get("peak_dbtp_max") is None else str(spec["peak_dbtp_max"]))
        self.notes_var.set(spec.get("notes", ""))

    def _on_save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Missing name", "Give this target a name.")
            return
        try:
            lufs_min = float(self.min_var.get())
            lufs_max = float(self.max_var.get())
        except ValueError:
            messagebox.showerror("Invalid range", "LUFS min/max must both be numbers, e.g. -26.0 and -18.0.")
            return
        if lufs_min >= lufs_max:
            messagebox.showerror("Invalid range", "LUFS min must be less than LUFS max.")
            return
        peak_raw = self.peak_var.get().strip()
        try:
            peak_max = float(peak_raw) if peak_raw else None
        except ValueError:
            messagebox.showerror("Invalid peak", "True Peak max must be a number, e.g. -6.0 — or leave it blank.")
            return

        spec = {
            "lufs_target": round((lufs_min + lufs_max) / 2, 1),
            "lufs_min": lufs_min,
            "lufs_max": lufs_max,
            "peak_dbtp_max": peak_max,
            "gated": "full-programme",
            "kind": "delivery",
            "notes": self.notes_var.get().strip(),
        }
        save_custom_target(name, spec)
        self.existing_menu.configure(values=self._existing_names())
        self.existing_var.set(name)
        self.master_app._refresh_target_menu()
        messagebox.showinfo("Saved", f"Saved custom target '{name}'.")

    def _on_delete(self):
        name = self.existing_var.get()
        if name == "(new)":
            # Not picked from the dropdown — maybe they typed an existing
            # name directly into the Name field instead. Honor that too.
            typed = self.name_var.get().strip()
            if typed and typed in load_custom_targets():
                name = typed
            else:
                messagebox.showinfo("Nothing to delete", 'Pick a target from "Edit existing" first.')
                return
        if not messagebox.askyesno("Delete Target", f"Delete custom target '{name}'?"):
            return
        delete_custom_target(name)
        self.existing_var.set("(new)")
        self.existing_menu.configure(values=self._existing_names())
        self._on_pick_existing("(new)")
        self.master_app._refresh_target_menu()


# --------------------------------------------------------------------------
# Main application window
# --------------------------------------------------------------------------
class App(AppBaseClass):  # type: ignore

    def __init__(self):
        super().__init__()
        self.withdraw()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = 540
        height = 720
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.title(__appname__)
        self.geometry(f"{width}x{height}+{x}+{y-35}")
        self.minsize(460, 560)
        self.resizable(False, False)
        self.update_idletasks()

        self.selected_paths = []

        self._build_ui()
        self._check_binaries()
        self.after(100, self.deiconify)

    # ---- UI construction -------------------------------------------------
    def _build_ui(self):
        # --- Light/dark toggle — pinned to the top-right corner via place(),
        # independent of the packed layout below. A native menu bar felt
        # like the wrong call here: on macOS it'd live outside the window
        # entirely (top of screen, not in it), on Windows it'd bring back
        # a strip of native chrome that clashes with an otherwise fully
        # CTk-themed window. A small anchored icon button matches what the
        # rest of the app already looks like.
        self.theme_toggle_btn = ctk.CTkButton(
            self,
            text="",
            width=32,
            height=32,
            corner_radius=6,
            font=("", 15),
            command=self._toggle_appearance,
        )
        apply_emoji(self.theme_toggle_btn, emoji_char="☀️" if ctk.get_appearance_mode() == "Dark" else "🌑", px=15)
        self.theme_toggle_btn.place(relx=1.0, x=-14, y=14, anchor="ne")

        title = ctk.CTkLabel(
            self,
            text=f"{__appname__}" if mac else f" {__appname__}",
            image=icon_ctkImage,
            compound="left",
            font=("", 20, "bold"),
        )
        title.image = icon_ctkImage
        title.pack(pady=(18, 4))

        subtitle = ctk.CTkLabel(
            self, text="GIF & video metadata, loudness, and more", text_color="gray60", font=("", 12)
        )
        subtitle.pack(pady=(0, 14))

        # --- Drop zone ---
        self.drop_zone = ctk.CTkFrame(
            self, height=110, corner_radius=10, border_width=2, border_color="gray40", fg_color=dnd_color
        )
        self.drop_zone.pack(fill="x", padx=20, pady=(0, 10))
        self.drop_zone.pack_propagate(False)

        self.drop_label = ctk.CTkLabel(self.drop_zone, text="", text_color=dnd_text_color, bg_color="transparent")

        if DND_AVAILABLE:
            apply_emoji(widget=self.drop_label, emoji_char="⬇", text=" Drag & drop a file or folder here", px=13)
        else:
            apply_emoji(widget=self.drop_label, emoji_char="⚠️", text=" Drag & drop unavailable", px=13)

        self.drop_label.pack(expand=True)

        if DND_AVAILABLE:
            self.drop_zone.drop_target_register(DND_FILES)  # type: ignore
            self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore

        btn_row = ctk.CTkFrame(self, fg_color="transparent", border_width=0)
        btn_row.pack(fill="x", padx=20, pady=(0, 6))

        select_folder_btn = ctk.CTkButton(btn_row, text="", command=self._select_folder)
        apply_emoji(select_folder_btn, "📁", "Select Folder")
        select_folder_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        select_file_btn = ctk.CTkButton(btn_row, text="", command=self._select_files)
        apply_emoji(select_file_btn, "🎬", "Select File(s)")
        select_file_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.path_label = ctk.CTkLabel(self, text="No file or folder selected", text_color=text_color, wraplength=440)
        self.path_label.pack(pady=(4, 14), padx=20)

        # --- Optional data checkboxes ---
        ctk.CTkLabel(self, text="Optional Data", font=("", 13, "bold")).pack(anchor="w", padx=20)
        ctk.CTkLabel(
            self,
            text="Required fields (Codec, Dimensions, FPS, Bitrate, Duration, Size)" " are always included.",
            text_color="gray55",
            font=("", 10),
            wraplength=440,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 6))

        # --- Presets: bundle checkbox selections + a target so a QC pass
        # doesn't mean re-toggling the same boxes every time ---
        preset_row = ctk.CTkFrame(self, fg_color="transparent", border_width=0)
        preset_row.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(preset_row, text="Preset:", font=("", 11), text_color="gray55").pack(side="left")
        self.preset_var = tk.StringVar(value="Custom")
        self.preset_menu = ctk.CTkOptionMenu(
            preset_row,
            values=self._preset_names(),
            variable=self.preset_var,
            width=170,
            command=self._on_preset_selected,
        )
        self.preset_menu.pack(side="left", padx=(8, 0))
        ctk.CTkButton(preset_row, text="Save…", width=64, command=self._on_save_preset).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            preset_row,
            text="Delete",
            width=64,
            fg_color="#8b2e2e",
            hover_color="#6e2424",
            command=self._on_delete_preset,
        ).pack(side="left", padx=(8, 0))

        checks_frame = ctk.CTkFrame(self, fg_color="transparent")
        checks_frame.pack(fill="x", padx=20)
        self.check_vars = {}
        for i, (key, label, default) in enumerate(CHECKBOX_DEFS):
            var = tk.BooleanVar(value=default)
            self.check_vars[key] = var
            cb = ctk.CTkCheckBox(checks_frame, text=label, variable=var)
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=(10, 10), pady=4)

        target_row = ctk.CTkFrame(self, fg_color="transparent", border_width=0)
        target_row.pack(fill="x", padx=20, pady=(8, 0))
        self.target_label = ctk.CTkLabel(target_row, text="Compare loudness to:", font=("", 11), text_color="gray55")
        self.target_label.pack(side="left")
        self.platform_target_var = tk.StringVar(value="None")
        self.target_menu = ctk.CTkOptionMenu(
            target_row,
            values=_all_target_names(),
            variable=self.platform_target_var,
            width=220,
            state="disabled",
        )
        self.target_menu.pack(side="left", padx=(8, 0))
        self.manage_targets = ctk.CTkButton(
            target_row,
            text="Manage Targets…",
            width=130,
            command=self._open_manage_targets,
            state="disabled",
        )
        self.manage_targets.pack(side="left", padx=(8, 0))
        # Comparison is only meaningful once Integrated Loudness is measured
        # (platform_delta_rows needs lufs_integrated, which only gets
        # populated when that checkbox is on) — gate the control on it.
        self.check_vars["lufs"].trace_add("write", self._on_lufs_toggle)

        self.start_btn = ctk.CTkButton(
            self, text="", height=40, font=("", 14, "bold"), state="disabled", command=self._start_scan
        )
        apply_emoji(widget=self.start_btn, emoji_char="▶", text=f"Start Scan", px=14)
        self.start_btn.pack(fill="x", padx=20, pady=(16, 6))

        self.status_label = ctk.CTkLabel(self, text="", text_color="gray55", font=("", 11))
        self.status_label.pack(pady=(0, 10))

    def _on_lufs_toggle(self, *_):
        if self.check_vars["lufs"].get():
            self.target_menu.configure(state="normal")
            self.target_label.configure(text_color=("gray10", "gray90"))
            self.manage_targets.configure(state="normal")
        else:
            self.platform_target_var.set("None")
            self.target_menu.configure(state="disabled")
            self.target_label.configure(text_color="gray55")
            self.manage_targets.configure(state="disabled")

    # ---- Custom targets -----------------------------------------------------
    def _open_manage_targets(self):
        ManageTargetsPopup(self)

    def _refresh_target_menu(self):
        self.target_menu.configure(values=_all_target_names())

    # ---- Presets -------------------------------------------------------------
    def _preset_names(self):
        return ["Custom"] + list(load_presets().keys())

    def _on_preset_selected(self, name):
        if name == "Custom":
            # Clean slate, not "whatever was last loaded" — matches how
            # Custom reads everywhere else in the UI.
            for var in self.check_vars.values():
                var.set(False)
            self.platform_target_var.set("None")
            return
        preset = load_presets().get(name)
        if not preset:
            return
        checks = preset.get("checks", {})
        if checks == "all":
            # Magic string, not a real wildcard (JSON has no such thing) —
            # means "every checkbox that currently exists," so a preset
            # saved this way stays "all" even after a future version adds
            # new checkboxes, instead of freezing today's set forever.
            for var in self.check_vars.values():
                var.set(True)
        else:
            for key, val in checks.items():
                if key in self.check_vars:
                    self.check_vars[key].set(val)
        target = preset.get("platform_target", "None")
        self.platform_target_var.set(target if target in _all_target_names() else "None")

    def _on_save_preset(self):
        dialog = ctk.CTkInputDialog(text="Preset name:", title="Save Preset")
        name = dialog.get_input()
        if not name:
            return
        preset = {
            "checks": {key: var.get() for key, var in self.check_vars.items()},
            "platform_target": self.platform_target_var.get(),
        }
        save_preset(name, preset)
        self.preset_menu.configure(values=self._preset_names())
        self.preset_var.set(name)

    def _on_delete_preset(self):
        name = self.preset_var.get()
        if name == "Custom":
            return
        if not messagebox.askyesno("Delete Preset", f"Delete preset '{name}'?"):
            return
        delete_preset(name)
        self.preset_var.set("Custom")
        self.preset_menu.configure(values=self._preset_names())

    def _toggle_appearance(self):
        new_mode = "Light" if ctk.get_appearance_mode() == "Dark" else "Dark"

        # CTk's set_appearance_mode() doesn't recolor the window atomically —
        # it fires a callback that walks every live CTk widget one at a time,
        # and each one redraws its own canvas as it's visited. Tk paints each
        # of those redraws to screen as it happens, so on a window with this
        # many widgets you see the change roll across the UI top-to-bottom
        # ("domino") instead of the whole window flipping at once.
        #
        # Fix: drop the window's opacity to 0 before triggering the mode
        # change, so the whole cascade happens off-screen, then fade back in
        # once every widget has finished redrawing. Reads as a clean "blink"
        # instead of a wave. -alpha is supported on macOS/Windows; wrapped in
        # try/except since some Linux window managers don't support it.
        def _swap_and_reveal():
            ctk.set_appearance_mode(new_mode)
            set_setting("appearance_mode", new_mode)
            self.theme_toggle_btn.configure(text="")
            apply_emoji(
                self.theme_toggle_btn,
                emoji_char="☀️" if new_mode == "Dark" else "🌑",
                px=15,
            )
            self.update_idletasks()
            animate_alpha(self, 1.0, duration_ms=250)

        animate_alpha(self, 0.0, duration_ms=150, on_complete=_swap_and_reveal)

    def _check_binaries(self):
        if not core.binaries_available():
            self.status_label.configure(
                text="",
                text_color="#e0a020",
            )
            apply_emoji(widget=self.status_label, emoji_char="⚠️️", text="ffmpeg/ffprobe not found.")

    # ---- Path selection ----------------------------------------------------
    def _select_folder(self):
        path = filedialog.askdirectory(title="Select a folder")
        if path:
            self._set_paths([path])

    def _select_files(self):
        paths = filedialog.askopenfilenames(
            title="Select file(s)",
            filetypes=[("Media files", " ".join(f"*{e}" for e in core.MEDIA_EXTS)), ("All files", "*.*")],
        )
        if paths:
            self._set_paths(list(paths))

    def _on_drop(self, event):
        paths = parse_dnd_paths(event.data)
        valid = [p for p in paths if os.path.isdir(p) or os.path.isfile(p)]
        if valid:
            self._set_paths(valid)

    def _set_paths(self, paths):
        self.selected_paths = paths
        if len(paths) == 1:
            self.path_label.configure(text=paths[0], text_color=text_color)
        else:
            self.path_label.configure(text=f"{len(paths)} items selected", text_color=text_color)
        self.start_btn.configure(state="normal")

    # ---- Scan lifecycle -----------------------------------------------------
    def _gather_files(self):
        results = {}
        for path in self.selected_paths:
            if os.path.isfile(path):
                if core.is_media_file(path):
                    results.setdefault(".", []).append(path)
            elif os.path.isdir(path):
                for dirpath, dirnames, filenames in os.walk(path):
                    dirnames.sort()
                    media = sorted(f for f in filenames if core.is_media_file(f))
                    if not media:
                        continue
                    rel = os.path.relpath(dirpath, path)
                    display_dir = (
                        os.path.basename(path.rstrip(os.sep))
                        if rel == "."
                        else os.path.join(os.path.basename(path.rstrip(os.sep)), rel)
                    )
                    results.setdefault(display_dir, []).extend(os.path.join(dirpath, f) for f in media)
        return results

    def _start_scan(self):
        if not core.binaries_available():
            messagebox.showerror("ffmpeg/ffprobe not found", "This build is missing ffmpeg/ffprobe. Please reinstall.")
            return

        grouped = self._gather_files()
        total = sum(len(v) for v in grouped.values())
        if total == 0:
            messagebox.showinfo("No media files", "No GIF or video files were found in the selection.")
            return

        options = {key: var.get() for key, var in self.check_vars.items()}
        options["platform_target"] = self.platform_target_var.get() if options.get("lufs") else "None"
        options["custom_targets"] = load_custom_targets()

        self.start_btn.configure(state="disabled")
        popup = ProgressPopup(self, total)
        q = queue.Queue()

        thread = threading.Thread(target=self._scan_worker, args=(grouped, options, q), daemon=True)
        thread.start()
        self.after(100, self._poll_queue, q, popup, options)

    def _scan_worker(self, grouped, options, q):
        scan_results = []
        index = 0
        for display_dir, filepaths in grouped.items():
            entry = {"dir": display_dir, "files": []}
            for filepath in filepaths:
                index += 1
                q.put(("progress", index, os.path.basename(filepath)))
                info = core.extract_info(filepath, options)
                entry["files"].append((os.path.basename(filepath), info))
            scan_results.append(entry)
        q.put(("done", scan_results))

    def _poll_queue(self, q, popup, options):
        try:
            while True:
                msg = q.get_nowait()
                if msg[0] == "progress":
                    _, index, filename = msg
                    popup.update_progress(index, filename)
                elif msg[0] == "done":
                    scan_results = msg[1]
                    popup.destroy()
                    self.start_btn.configure(state="normal")
                    root_label = (
                        self.selected_paths[0]
                        if len(self.selected_paths) == 1
                        else f"{len(self.selected_paths)} selected items"
                    )
                    ResultsWindow(self, scan_results, options, root_label)
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_queue, q, popup, options)


def main():
    app = App()
    set_icon(app)
    watermark_label(app, __version__)

    from modules.githubReleaseChecker import autoChecker

    autoChecker(app)

    app.mainloop()


if __name__ == "__main__":
    main()
