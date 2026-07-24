# modules/config.py
import json
from pathlib import Path

from modules.platformModules import config_dir

# config_dir should already point at wherever you resolved it —
# same Path object you're using elsewhere for the config directory.
CONFIG_FILE = Path(config_dir) / "config.json"

_DEFAULTS = {
    "appearance_mode": "System",
    # Custom QC target profiles, keyed by display name — same shape as
    # media_core.PLATFORM_TARGETS entries:
    #   {"lufs_target": -22.0, "lufs_min": -26.0, "lufs_max": -18.0,
    #    "peak_dbtp_max": -6.0, "gated": "full-programme",
    #    "kind": "delivery", "notes": "free text, e.g. client/QC ref"}
    # Hand-editable directly in config.json if you'd rather not use the
    # "Manage Targets…" dialog — lufs_min/lufs_max/peak_dbtp_max are the
    # only fields evaluate_target() actually reads for pass/fail; the rest
    # are just for display.
    "custom_targets": {},
    # Named presets bundling checkbox selections + a target, keyed by
    # display name: {"checks": {"lufs": true, ...}, "platform_target": "…"}
    # "checks" can also be the literal string "all" instead of a dict —
    # shorthand for "every checkbox that currently exists," which stays
    # true even after a future version adds new checkboxes (a literal
    # dict snapshot wouldn't include those).
    #
    # These two ("All", "TVCs") also double as *seed content* — see
    # _SEEDABLE / _seed_new_defaults() below. Add a new one here whenever
    # you want it to show up for every existing user on their next launch,
    # without stomping one they've already customized or deleted.
    "presets": {
        "All": {
            "checks": "all",
            "platform_target": "None",
        },
        "TVCs (US)": {
            "checks": {
                "lufs": True,
                "true_peak": True,
                "audio_info": True,
                "color_info": False,
                "container_info": True,
                "creation_date": False,
                "aspect_ratio": False,
                "tvc_slate": True,
            },
            "platform_target": "ATSC A/85 (US Broadcast)",
        },
    },
}

# Collections where new named entries get seeded in over app versions,
# without ever overwriting or reviving whatever the user's done with a
# name they've already seen — see _seed_new_defaults().
_SEEDABLE = ("custom_targets", "presets")


def _seed_new_defaults(data: dict) -> tuple:
    """Adds any default preset/custom-target the user has never seen
    before (per _DEFAULTS above), without reviving one they deleted.

    The tricky bit: "user deleted this preset" and "user has never had
    this preset" both look identical in the data alone — an absent key.
    So presence/absence of the *name* isn't enough; we track which names
    have ever been seeded to this user in data["_seeded"], and only copy
    a default in the first time its name shows up there. After that,
    what happens to it is entirely the user's call, forever.

    Returns (data, changed) — changed is True if this call added
    anything, so the caller knows whether a save is worth doing.
    """
    changed = False
    seeded = data.setdefault("_seeded", {})
    for key in _SEEDABLE:
        seeded_names = set(seeded.get(key, []))
        bucket = data.setdefault(key, {})
        for name, spec in _DEFAULTS.get(key, {}).items():
            if name not in seeded_names:
                bucket[name] = spec
                seeded_names.add(name)
                changed = True
        if seeded.get(key) != sorted(seeded_names):
            seeded[key] = sorted(seeded_names)
            changed = True
    return data, changed


def load_config() -> dict:
    is_first_run = not CONFIG_FILE.exists()
    data = {}
    if not is_first_run:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}  # corrupt/unreadable file — fall through to defaults

    # Merge over defaults rather than trusting the file wholesale — this
    # way, if a future app version adds a new flat setting key, an
    # existing user's older config.json (which won't have that key yet)
    # still gets a sane default instead of a KeyError. This is a shallow
    # overlay, so data["presets"]/["custom_targets"] (if present) win
    # wholesale here — the fine-grained "add only what's new" merge for
    # those happens next, in _seed_new_defaults().
    merged = {**_DEFAULTS, **data}
    merged, seeded_something = _seed_new_defaults(merged)

    if is_first_run or seeded_something:
        save_config(merged)
    return merged


def save_config(data: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        print(f"  ✗ Failed to save config: {e}")


def get_setting(key, default=None):
    return load_config().get(key, default)


def set_setting(key, value):
    data = load_config()
    data[key] = value
    save_config(data)


# --------------------------------------------------------------------------
# Custom QC target profiles
# --------------------------------------------------------------------------
def load_custom_targets() -> dict:
    return load_config().get("custom_targets", {})


def save_custom_target(name: str, spec: dict):
    data = load_config()
    targets = data.get("custom_targets", {})
    targets[name] = spec
    data["custom_targets"] = targets
    save_config(data)


def delete_custom_target(name: str):
    data = load_config()
    targets = data.get("custom_targets", {})
    targets.pop(name, None)
    data["custom_targets"] = targets
    save_config(data)


# --------------------------------------------------------------------------
# Presets — bundled checkbox selections + a target, so a QC pass doesn't
# mean re-toggling the same 8 checkboxes every time.
# --------------------------------------------------------------------------
def load_presets() -> dict:
    return load_config().get("presets", {})


def save_preset(name: str, preset: dict):
    data = load_config()
    presets = data.get("presets", {})
    presets[name] = preset
    data["presets"] = presets
    save_config(data)


def delete_preset(name: str):
    data = load_config()
    presets = data.get("presets", {})
    presets.pop(name, None)
    data["presets"] = presets
    save_config(data)
