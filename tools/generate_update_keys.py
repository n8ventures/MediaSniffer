"""
tools/generate_update_keys.py — one-time ed25519 keypair generator for the
silent auto-updater.

Run once, from your build machine:
    python tools/generate_update_keys.py

Output:
    update_signing_key.pem   — PRIVATE key. Keep this on your build machine
                                only. Do NOT commit it, do NOT ship it in the
                                .app bundle. If it ever leaks, rotate it and
                                re-embed the new public key immediately.
    update_public_key.hex    — paste this hex string into
                                modules/updater.py's UPDATE_PUBLIC_KEY_HEX.
                                Safe to be public — it can only verify
                                signatures, never create them.
"""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PRIVATE_KEY_PATH = Path("update_signing_key.pem")
PUBLIC_KEY_PATH = Path("update_public_key.hex")

if PRIVATE_KEY_PATH.exists():
    raise SystemExit(
        f"✗ {PRIVATE_KEY_PATH} already exists — refusing to overwrite an existing signing key.\n"
        f"  If you're intentionally rotating keys, move/delete it first."
    )

private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

priv_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
pub_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)

PRIVATE_KEY_PATH.write_bytes(priv_bytes)
PUBLIC_KEY_PATH.write_text(pub_bytes.hex())

print(f"✓ Generated {PRIVATE_KEY_PATH} (PRIVATE — keep off the repo, back it up somewhere safe)")
print(f"✓ Generated {PUBLIC_KEY_PATH} (paste into modules/updater.py)")
print(f"\nPublic key hex:\n  {pub_bytes.hex()}")
