"""
modules/updater.py — silent in-app auto-updater.

Flow:
    1. Fetch latest.json from R2 (primary), fall back to the GitHub
       releases mirror if R2 is unreachable. Both serve the same schema.
    2. Compare the manifest version against the running build's __version__
       using proper semantic-version comparison (not string compare).
    3. If newer: download the .zip artifact, verify its SHA-256 AND its
       ed25519 signature against the embedded public key. Any failure here
       aborts the silent path — we never swap in an unverified artifact,
       we fall back to a "here's the download page" notification instead.
    4. Extract, atomically swap the running .app bundle for the new one,
       relaunch, exit the old process.

This module does no UI of its own. Call check_and_update_async() once from
mainGUI.py on startup, passing callbacks that are already safe to run on
the Tk main thread (wrap them in `self.after(0, ...)` — see the notes on
check_and_update_async below, callbacks fire from a background thread).
"""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from packaging.version import InvalidVersion, Version

from __version__ import __appname__
from __version__ import __version__ as CURRENT_VERSION

# ── Config ──────────────────────────────────────────────────────────────
R2_MANIFEST_URL = "https://cdn.n8ventures.dev/eagleeye/latest.json"
GITHUB_MANIFEST_URL = "https://github.com/n8ventures/eagleeye-releases/releases/latest/download/latest.json"

FETCH_TIMEOUT = 8  # seconds — fail fast, this chain shouldn't hang app startup
DOWNLOAD_TIMEOUT = 60

# Public half of the ed25519 keypair from tools/generate_update_keys.py.
# The private key never leaves the build machine — it's only used to sign
# releases in devtools.py. Rotate this (and re-embed) if it's ever
# suspected to have leaked.
UPDATE_PUBLIC_KEY_HEX = "REPLACE_WITH_HEX_FROM_generate_update_keys.py"


class UpdateError(Exception):
    pass


# ── Manifest fetch (R2 primary, GitHub fallback) ─────────────────────────


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": f"{__appname__}-updater"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_manifest() -> dict:
    """Try R2 first, GitHub Releases second. Raises UpdateError if both fail."""
    last_err = None
    for url in (R2_MANIFEST_URL, GITHUB_MANIFEST_URL):
        try:
            return _fetch_json(url)
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
            last_err = exc
            continue
    raise UpdateError(f"Both manifest sources unreachable: {last_err}")


def is_newer(remote_version: str) -> bool:
    try:
        return Version(remote_version) > Version(CURRENT_VERSION)
    except InvalidVersion:
        return False  # never let a malformed version string trigger an update


# ── Download + verification ───────────────────────────────────────────────


def _verify_signature(sha256_hex: str, signature_b64: str) -> bool:
    try:
        pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(UPDATE_PUBLIC_KEY_HEX))
        pub_key.verify(base64.b64decode(signature_b64), bytes.fromhex(sha256_hex))
        return True
    except (InvalidSignature, ValueError):
        return False


def _download(url: str, dest: Path):
    req = urllib.request.Request(url, headers={"User-Agent": f"{__appname__}-updater"})
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_and_verify(manifest: dict, workdir: Path) -> Path:
    """Downloads + verifies the update zip. Returns the path to the
    extracted .app bundle, or raises UpdateError if anything fails
    verification — caller should treat that as "do not install"."""
    zip_path = workdir / "update.zip"
    _download(manifest["url"], zip_path)

    actual_hash = _sha256_of(zip_path)
    if actual_hash != manifest.get("sha256"):
        raise UpdateError("SHA-256 mismatch — downloaded artifact does not match manifest")

    if not _verify_signature(manifest["sha256"], manifest.get("signature", "")):
        raise UpdateError("Signature verification failed — refusing to install")

    extract_dir = workdir / "extracted"
    shutil.unpack_archive(str(zip_path), str(extract_dir))

    app_candidates = list(extract_dir.glob("*.app"))
    if not app_candidates:
        raise UpdateError("No .app bundle found inside update archive")
    return app_candidates[0]


# ── Swap + relaunch ────────────────────────────────────────────────────────


def apply_update(new_app_path: Path):
    """Swaps the running .app bundle for the new one and relaunches. Must
    be called from within the currently-running app's own bundle."""
    current_app_path = Path(sys.executable).resolve()
    # sys.executable inside a PyInstaller macOS bundle is .app/Contents/MacOS/<bin>
    # — walk up to the .app bundle root.
    while current_app_path.suffix != ".app" and current_app_path != current_app_path.parent:
        current_app_path = current_app_path.parent
    if current_app_path.suffix != ".app":
        raise UpdateError("Could not resolve running .app bundle path")

    backup_path = current_app_path.with_suffix(".app.bak")
    if backup_path.exists():
        shutil.rmtree(backup_path)

    # Same-volume rename is atomic. This process is still running out of
    # the old bundle's files at this point — macOS keeps existing open
    # file handles valid even after the directory entry that pointed to
    # them moves, so this is safe while the app is live.
    shutil.move(str(current_app_path), str(backup_path))
    shutil.move(str(new_app_path), str(current_app_path))

    subprocess.Popen(["open", "-n", str(current_app_path)])
    shutil.rmtree(backup_path, ignore_errors=True)
    os._exit(0)  # hard exit — no Tk teardown needed, the new process is already launching


# ── Entry point ─────────────────────────────────────────────────────────


def check_and_update_async(on_notify_only=None, on_error=None):
    """Fire-and-forget — call this once from mainGUI.py on startup.

    Runs entirely on a background thread. On success, apply_update() never
    returns (the process exits and a new one launches), so there's nothing
    to report back for the "everything worked" case.

    on_notify_only(version, download_page_url):
        Called if a newer version exists but silent verification failed —
        degrade to "here's a link" instead of failing silently. This fires
        from the background thread; wrap your UI call in
        `self.after(0, lambda: ...)` inside the callback you pass in.
    on_error(exc):
        Optional. Called if the check itself failed (e.g. both manifest
        sources unreachable). Safe to leave as a no-op — a failed update
        check should never interrupt someone just opening the app. Same
        threading caveat as on_notify_only applies if you touch Tk here.
    """

    def _worker():
        try:
            manifest = fetch_manifest()
        except UpdateError as exc:
            if on_error:
                on_error(exc)
            return

        if not is_newer(manifest.get("version", "")):
            return

        with tempfile.TemporaryDirectory() as tmp:
            try:
                new_app = download_and_verify(manifest, Path(tmp))
                apply_update(new_app)  # no return on success
            except UpdateError as exc:
                if on_notify_only:
                    on_notify_only(manifest.get("version"), manifest.get("download_page", manifest.get("url")))
                elif on_error:
                    on_error(exc)

    threading.Thread(target=_worker, daemon=True).start()
