import os
import sys
import platform
import tkinter as tk
from pathlib import Path
import json

# Check the platform
current_platform = platform.system()

win = current_platform == "Windows"
mac = current_platform == "Darwin"


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
import tempfile
from __version__ import __appname__, __internal_app_name__

if getattr(sys, "frozen", False):
    import certifi

    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

    int_app_name = __internal_app_name__

    log_dir = os.path.expanduser(f"~/Library/Application Support/{__appname__}/Logs")
    config_dir = os.path.expanduser(f"~/Library/Application Support/{__appname__}/Config")
    temp_dir = os.path.join(tempfile.gettempdir(), __appname__)
    paddlex_dir = os.path.expanduser(f"~/Library/Application Support/{__appname__}/paddle/paddlex")

    os.makedirs(paddlex_dir, exist_ok=True)
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(base_dir, "temp")
    log_dir = os.path.join(base_dir, "logs")
    config_dir = os.path.join(base_dir, "config")

os.makedirs(config_dir, exist_ok=True)
os.makedirs(temp_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)


# Only print debug info in main process, not in spawned workers
def print_debug_info():
    _is_worker = os.environ.get("OCR_WORKER_PROCESS") == "1"

    if not _is_worker:
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


if any(char.isalpha() for char in __version__) or __version__.startswith("0."):
    if win:
        icon = (
            os.path.join(bundle_path, "assets", "icons", "win", "icoDev.ico")
            if bundle_path
            else "./assets/icons/win/icoDev.ico"
        )
    elif mac:
        icon = (
            os.path.join(bundle_path, "assets", "icons", "mac", "icoDev.png")
            if bundle_path
            else "./assets/icons/mac/icoDev.png"
        )
else:
    if win:
        icon = (
            os.path.join(bundle_path, "assets", "icons", "win", "ico.ico")
            if bundle_path
            else "assets/icons/win/ico.ico"
        )
    elif mac:
        icon = (
            os.path.join(bundle_path, "assets", "icons", "mac", "ico.png")
            if bundle_path
            else "./assets/icons/mac/icon.png"
        )
