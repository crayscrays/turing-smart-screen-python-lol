"""
Idle-video discovery and on-the-fly MP4 → GIF conversion.

Behavior:
  - Scans `videos_dir` for the first video file (alphabetical order).
  - Accepts .gif directly (used as-is, no conversion).
  - Accepts .mp4 / .mov / .webm → converted to GIF via ffmpeg.
  - Re-converts only if the source file is newer than the cached GIF.
  - Returns the resolved GIF path, or None if no file is present.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
from typing import Optional

log = logging.getLogger(__name__)

# Search order matters: .gif first (no ffmpeg needed), then video formats.
SUPPORTED_EXTS = (".gif", ".mp4", ".mov", ".webm", ".mkv", ".avi")


def find_first_video(videos_dir: str) -> Optional[str]:
    """Return the first supported file in the folder, alphabetically.

    GIFs are preferred over video files since they need no conversion.
    """
    if not os.path.isdir(videos_dir):
        return None
    for ext in SUPPORTED_EXTS:
        matches = sorted(
            glob.glob(os.path.join(videos_dir, f"*{ext}"))
            + glob.glob(os.path.join(videos_dir, f"*{ext.upper()}"))
        )
        if matches:
            return matches[0]
    return None


# Back-compat alias
def find_first_mp4(videos_dir: str) -> Optional[str]:
    return find_first_video(videos_dir)


def _is_stale(src: str, gif: str) -> bool:
    """GIF is stale if missing or older than the source video."""
    if not os.path.isfile(gif):
        return True
    try:
        return os.path.getmtime(gif) < os.path.getmtime(src)
    except OSError:
        return True


def ensure_idle_gif(
    videos_dir: str,
    gif_path: str,
    width: int = 320,
    height: int = 480,
    fps: int = 8,
) -> Optional[str]:
    """
    Resolve the idle GIF path. If the source in `videos_dir` is already a
    .gif, use it directly. Otherwise convert via ffmpeg to `gif_path`.
    """
    src = find_first_video(videos_dir)
    if not src:
        log.warning(
            "No video file (.gif/.mp4/.mov/.webm) found in %s — idle screen "
            "will be blank. Drop a file into that folder and restart.",
            videos_dir,
        )
        return None

    # If user dropped a .gif, use it directly. No ffmpeg needed.
    if src.lower().endswith(".gif"):
        log.info("Using GIF directly: %s", src)
        return src

    # Otherwise we need ffmpeg to convert to a fixed-size GIF.
    if not _is_stale(src, gif_path):
        log.info("Idle GIF is up to date (%s)", gif_path)
        return gif_path

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.warning(
            "ffmpeg not found on PATH — cannot convert %s. "
            "Install ffmpeg, or drop a .gif directly into %s.",
            src, videos_dir,
        )
        return gif_path if os.path.isfile(gif_path) else None

    os.makedirs(os.path.dirname(gif_path) or ".", exist_ok=True)
    vf = (
        f"fps={fps},"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    log.info("Converting %s → %s (%dx%d @ %dfps)", src, gif_path, width, height, fps)
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", src, "-vf", vf, "-loop", "0", gif_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return gif_path
    except subprocess.CalledProcessError as e:
        log.error("ffmpeg conversion failed: %s", e)
        return None
