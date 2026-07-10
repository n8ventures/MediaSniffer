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


green = emoji_img("🟢")
yellow = emoji_img("🟡")
orange = emoji_img("🟠")
red = emoji_img("🔴")
warning = emoji_img("⚠️")
check = emoji_img("✅")
fail = emoji_img("❌")
white = emoji_img("⚪")
triangle = emoji_img("🔺")
bug = emoji_img("🐛")
save = emoji_img("💾")
