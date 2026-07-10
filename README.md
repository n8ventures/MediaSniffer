# Media Scanner GUI (GIF & Video)

Two files:
- `media_core.py` — all non-GUI logic: binary resolution, ffprobe/ffmpeg
  wrappers, metadata + loudness extraction, report builders.
- `mainGUI.py` — the CustomTkinter application.

## Setup

```
pip install customtkinter tkinterdnd2 static-ffmpeg python-docx
python mainGUI.py
```

- **static-ffmpeg** is optional but recommended for packaging: it downloads
  and caches a self-contained `ffmpeg`/`ffprobe` pair per platform on first
  run, so a packaged app doesn't depend on the end user having ffmpeg on
  PATH. If it's not installed, `media_core.resolve_binaries()` falls back
  to `ffmpeg`/`ffprobe` on PATH automatically.
- **tkinterdnd2** is optional — without it, drag-and-drop is disabled and
  the drop zone shows a note, but the folder/file buttons work fine. Swap
  in your own patched hybrid class in `mainGUI.py` — the `_CTkDnD` block
  near the top is clearly marked and everything else only depends on
  `AppBaseClass` / `DND_FILES`.
- **python-docx** is only needed for the DOCX "Save As" option.

## What it does

- Drop or select a file/folder → walks it for `.gif` + video files only
  (no plain audio files, per your ask).
- Required fields (always shown, not checkboxes): **Codec, Dimensions,
  FPS, Bitrate, Duration, Size**. Duration is frame-accurate
  (`H:MM:SS:FF`), using ffprobe's exact frame count when available.
- Optional checkboxes:
  - **Integrated Loudness (LUFS)** and **True Peak (dBTP)** — via
    ffmpeg's `ebur128` filter (full audio decode, so it's opt-in). Files
    with no audio track (most GIFs, silent clips) show `N/A` instead of
    running the analysis.
  - **Audio Track Info** — codec/channels/sample rate, when present.
  - **Color / HDR Info** — bit depth, color primaries, and HDR10(PQ)/HLG/SDR
    detection from `color_transfer`.
  - **Container Format** — e.g. "QuickTime / MOV".
  - **Creation Date** — from container metadata tags, if present.
  - **Aspect Ratio** — from stream data, or computed from dimensions.
- Scanning runs in a background thread with a modal progress popup
  (file-by-file), so the UI never freezes — this matters especially with
  LUFS analysis on, since that's a full decode per file.
- Results open in a separate scrollable, grouped-by-folder window. Bottom
  bar: **Save As** (HTML / Markdown / DOCX / TXT) and **Exit**.

## Design notes / things you may want to tweak

- `info_rows()` in `media_core.py` is the single source of truth for which
  fields get shown/exported — the GUI results view and all four export
  formats all call it, so they can't drift out of sync.
- The checkbox → field mapping lives in `CHECKBOX_DEFS` at the top of
  `gui_app.py` — add a tuple there plus a branch in `extract_info()` /
  `info_rows()` in `media_core.py` to add more optional fields later.
- LUFS/peak default timeout is 600s per file (`analyze_loudness(...,
  timeout=600)`) — long 4K files could take a while to decode; adjust if
  needed.