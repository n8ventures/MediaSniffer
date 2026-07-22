import os
import sys
import platform
import tkinter as tk
from pathlib import Path
import json
import tempfile
import os

# Check the platform
current_platform = platform.system()
architecture = platform.machine().lower()

win = current_platform == "Windows"
mac = current_platform == "Darwin"
intel = architecture in ("x86_64", "amd64")


def is_running_from_bundle():
    # Check if the application is running from a bundled executable
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return sys._MEIPASS
        if win:
            return os.path.dirname(sys.executable)
        if mac:
            current_dir = os.path.dirname(sys.executable)
            parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
            return os.path.join(parent_dir, "Resources")

    return False


from __version__ import __version__

if mac:
    from __version__ import __versionMac__ as __version__

# TEMP AND LOG PATHS
from __version__ import __appname__, __internal_app_name__

if getattr(sys, "frozen", False):
    import certifi

    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def print_debug_info():

    if is_running_from_bundle():
        print("Running from a bundled application (.app/.exe)")
    else:
        print("Running from source (.py)")

    print("Current app version:", __version__)
    print(get_build_label())

    print("Current working directory:", os.getcwd())
    print("Executable path:", sys.executable)
    print("TclVersion: ", tk.TclVersion)
    print("TkVersion: ", tk.TkVersion)


# Handle bundle paths for binaries and icon
bundle_path = is_running_from_bundle()

icon = None

BUILD_FILE = Path(bundle_path) / "build_count.json" if bundle_path else Path("build_count.json")


def read_build_file() -> dict:
    print("==> BUILD FILE: ", BUILD_FILE)
    if BUILD_FILE.exists():
        try:
            return json.loads(BUILD_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            pass
    return {"build_count": 0}


def get_build_label():
    data = read_build_file()

    if data["build_count"] == 0:
        from datetime import datetime

        now = datetime.now()

        date_part = now.strftime("%Y%m%d")
        time_part = now.strftime("%H%M")

        return f"Build UNKNOWN.{date_part}{time_part}"

    else:
        date = data["date"].replace("-", "")
        time = data["time"].replace(":", "")
        build_count = data["build_count"]

        if getattr(sys, "frozen", False):
            return f"Build {build_count}.{date}{time}"
        else:
            return f"Source Version. (Builds: {build_count})"


is_dev_build = any(char.isalpha() for char in __version__) or __version__.startswith("0.")

if is_dev_build:
    if win:
        icon = (
            os.path.join(bundle_path, "assets", "icons", "win", "icon-dev.ico")
            if bundle_path
            else "./assets/icons/win/icon-dev.ico"
        )
        icon_png = (
            os.path.join(bundle_path, "assets", "icons", "win", "icon-dev.png")
            if bundle_path
            else "./assets/icons/win/icon-dev.png"
        )
    elif mac:
        icon = (
            os.path.join(bundle_path, "assets", "icons", "mac", "icon-dev.png")
            if bundle_path
            else "./assets/icons/mac/icon-dev.png"
        )
        icon_png = (
            os.path.join(bundle_path, "assets", "icons", "mac", "icon-dev.png")
            if bundle_path
            else "./assets/icons/mac/icon-dev.png"
        )
else:
    if win:
        icon = (
            os.path.join(bundle_path, "assets", "icons", "win", "icon.ico")
            if bundle_path
            else "assets/icons/win/icon.ico"
        )
        icon_png = (
            os.path.join(bundle_path, "assets", "icons", "win", "icon.png")
            if bundle_path
            else "./assets/icons/win/icon.png"
        )
    elif mac:
        icon = (
            os.path.join(bundle_path, "assets", "icons", "mac", "icon.png")
            if bundle_path
            else "./assets/icons/mac/icon.png"
        )
        icon_png = (
            os.path.join(bundle_path, "assets", "icons", "mac", "icon.png")
            if bundle_path
            else "./assets/icons/mac/icon.png"
        )


if bundle_path:
    if mac:
        # log_dir = os.path.expanduser(f"~/Library/Application Support/{__appname__}/Logs")
        config_dir = os.path.expanduser(f"~/Library/Application Support/{__appname__}/Config")
    elif win:
        # log_dir = os.path.join(os.environ["LOCALAPPDATA"], __appname__, "Logs")
        config_dir = os.path.join(os.environ["LOCALAPPDATA"], __appname__, "Config")

    # temp_dir = os.path.join(tempfile.gettempdir(), __appname__)

else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # temp_dir = os.path.join(base_dir, "temp")
    # log_dir = os.path.join(base_dir, "logs")
    config_dir = os.path.join(base_dir, "config")

# os.makedirs(temp_dir, exist_ok=True)
# os.makedirs(log_dir, exist_ok=True)
os.makedirs(config_dir, exist_ok=True)
