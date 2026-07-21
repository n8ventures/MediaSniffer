import tkinter as tk
import customtkinter as ctk
import sys
import emoji
from PIL import Image, ImageDraw, ImageFont, ImageTk

from modules.platformModules import win, mac, icon
from __version__ import __author__, __version__, __appname__, __internal_app_name__

widget_color = [
    # 0 = Default
    "#323232",
    # 1 = Colored
    "#7d7dff",
    # 2 = Default Greyed Out
    "#c8c8c8",
    # 3 = Colored Greyed Out
    "#8383a6",
    # 4 = Red
    "#FF1F1F",
    # 5 = Greyed Out Red
    "#E96666",
]


def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y-35}")
    window.update_idletasks()


def make_non_resizable(window):
    window.resizable(False, False)


def create_popup(root, title, width, height, lift=0, warning=False, info=False, error=False):
    popup = ctk.CTkToplevel(root)
    popup.title(title)
    popup.iconbitmap(icon)
    center_window(popup, width, height)

    if lift:
        popup.lift()

    popup.grab_set()

    # if win:
    #     if warning:
    #         winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    #     elif info:
    #         winsound.MessageBeep(winsound.MB_ICONINFORMATION)
    #     elif error:
    #         winsound.MessageBeep(winsound.MB_ICONHAND)

    return popup


# Clickable links
def open_link(url):
    import webbrowser

    webbrowser.open(url)


def clickable_link_labels(parent, text, link):
    lbl = ctk.CTkLabel(
        parent,
        text=text,
        cursor="hand2",
        text_color=widget_color[1],
    )
    lbl.pack()
    lbl.bind("<Button-1>", lambda e: open_link(link))


# Watermark
def watermark_label(parent, version, debug=""):
    frame = ctk.CTkFrame(parent, bg_color="transparent", border_width=0)
    frame.pack(side=tk.BOTTOM, fill=tk.X)

    ctk.CTkLabel(
        frame,
        text=f" by {__author__}",
        text_color="gray",
    ).pack(side=tk.LEFT, padx=5)

    ctk.CTkLabel(
        frame,
        text=f"version: {version} {debug}",
        text_color="gray",
    ).pack(side=tk.RIGHT, padx=5)


# EMOJI IMAGES
def emoji_img(text, size=13):
    VALID_EMOJI_SIZES = [20, 32, 40, 48, 64, 96, 160]

    def closest_size(size):
        return min(VALID_EMOJI_SIZES, key=lambda x: abs(x - size))

    px = int(round(size * 72 / 96))
    if win:
        font = ImageFont.truetype("seguiemj.ttf", px)
    elif mac:
        px = closest_size(px)
        font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", px)

    canvas = px * 4
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.text(
        (canvas // 2, canvas // 2),
        text,
        font=font,
        embedded_color=True,
        anchor="mm",
    )

    bbox = img.getbbox()
    img = img.crop(bbox if bbox else (0, 0, px, px))

    return ctk.CTkImage(
        light_image=img,
        dark_image=img,
        size=img.size,
    )


def apply_emoji(widget, emoji_char, text="", px=13, compound="left"):
    """
    Makes an emoji render correctly on both platforms:
    - macOS: Tk's font fallback already renders color emoji fine, so the
      emoji just goes straight into the widget's text.
    - Windows: Tk won't render color emoji from a font at all, so we
      render it to an image via emoji_img() and set it as `image=`,
      with `text=` holding just the label text.
    The image ref is stashed on the widget itself (widget.image = ...) —
    same pattern you're already using for the title icon at line 373 —
    so Tk doesn't garbage-collect it once this function returns.
    """
    if mac:
        widget.configure(text=f"{emoji_char} {text}".strip())
        return

    img = emoji_img(emoji_char, size=px)
    widget.configure(text=text, image=img, compound=compound)
    widget.image = img


_fade_after_id = None  # tracks the in-flight animation so re-toggling mid-fade doesn't stack callbacks

import tkinter as tk


def animate_alpha(root, target, duration_ms, on_complete=None, steps=15):
    """
    Smoothly steps `root`'s alpha toward `target` over `duration_ms`.
    Cancels any fade already in progress before starting a new one, so
    rapid re-toggling can't stack conflicting animations.
    """
    global _fade_after_id
    if _fade_after_id is not None:
        try:
            root.after_cancel(_fade_after_id)
        except tk.TclError:
            pass
        _fade_after_id = None

    try:
        start = root.attributes("-alpha")
    except tk.TclError:
        start = 1.0

    step_delay = max(1, duration_ms // steps)

    def _step(i=0):
        global _fade_after_id
        try:
            progress = i / steps
            alpha = start + (target - start) * progress
            root.attributes("-alpha", alpha)
        except tk.TclError:
            return  # window destroyed mid-animation — bail quietly

        if i < steps:
            _fade_after_id = root.after(step_delay, lambda: _step(i + 1))
        else:
            _fade_after_id = None
            if on_complete:
                on_complete()

    _step()
