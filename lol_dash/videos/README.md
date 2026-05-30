# Idle videos

Drop **one** file in this folder. The app picks the first one it finds.

## Supported formats

| Format | What happens | Need ffmpeg? |
|---|---|---|
| `.gif` | Used **directly** — no conversion. Fastest path. | No |
| `.mp4`, `.mov`, `.webm`, `.mkv`, `.avi` | Auto-converted to GIF on launch (320×480, 8fps). Cached at `lol_dash/assets/idle.gif`. | Yes |

`.gif` is **preferred** if multiple files are present.

## Tips for best results on the 3.5" panel

The Turing Smart Screen 3.5" Revision A is a UART-serial panel — realistic refresh is ~8–12 fps. Keep this in mind:

- **Resolution:** 320×480 portrait. Anything else gets center-cropped on load.
- **Frame rate:** 8 fps is what we target. Higher source fps just gets downsampled.
- **Length:** Short loops (5–15 seconds) work best — less RAM, snappier startup.
- **Pre-optimized GIF:** If you have one already at 320×480 / ~8fps, drop it in and skip ffmpeg entirely.

## Switching videos

1. Delete the old file
2. Drop in the new one
3. Restart the app — it auto-detects the change (re-converts only if needed)

Delete `lol_dash/assets/idle.gif` if you want to force a fresh conversion.

## Empty folder

If this folder is empty, the screen stays black during idle and the app logs a warning. The in-game dashboard still works normally.
