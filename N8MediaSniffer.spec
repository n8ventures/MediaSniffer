# -*- mode: python ; coding: utf-8 -*-
import os
import subprocess

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
    copy_metadata,
    collect_dynamic_libs,
)
from importlib.metadata import PackageNotFoundError

from __version__ import __versionMac__ as __version__
from __version__ import __author__, __appname__, __internal_app_name__

block_cipher = None


def safe_copy_metadata(package_name):
    try:
        return copy_metadata(package_name)
    except PackageNotFoundError:
        return []


docx_datas, docx_binaries, docx_hiddenimports = collect_all("docx")
datas = [
    ("build_count.json", "."),
    ("assets/themes/Marcel.json", "assets/themes"),
    ("assets/icons/mac/icon.png", "assets/icons/mac"),
]
binaries = []

datas += docx_datas

# Include python-docx package data (templates) used by paddlex save_to_word
binaries += docx_binaries
hiddenimports = docx_hiddenimports
datas += safe_copy_metadata("pillow")
datas += safe_copy_metadata("regex")
datas += safe_copy_metadata("packaging")
datas += safe_copy_metadata("scipy")
datas += safe_copy_metadata("python-docx")

datas += collect_data_files("certifi")

a = Analysis(  # type: ignore
    ["mainGUI.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["./hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # type: ignore

exe = EXE(  # type: ignore
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=f"{__appname__}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # signing handled post-build by devtools.py
    entitlements_file=None,  # avoids --timestamp failures with Apple Dev certs
    icon="assets/icons/mac/icon.icns",
)

coll = COLLECT(  # type: ignore
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=f"{__appname__}",
)

app = BUNDLE(  # type: ignore
    coll,
    name=f"{__appname__}.app",
    icon="assets/icons/mac/icon.icns",
    bundle_identifier=f"{__internal_app_name__}",
    version=os.environ.get("BUILD_VERSION", __version__),
    info_plist={
        "CFBundleDisplayName": f"{__appname__}",
        "CFBundleShortVersionString": os.environ.get("BUILD_VERSION", __version__),
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,  # respects dark/light mode
        "LSMinimumSystemVersion": "13.0",
        # for when you add AppleScript later:
        "NSAppleEventsUsageDescription": f"{__appname__} uses AppleScript to open Finder windows.",
        "NSScreenCaptureUsageDescription": f"{__appname__} requires Screen Recording to capture screenshots for bug reports.",
    },
)
