"""
Idle-video discovery and on-the-fly MP4 → GIF conversion.

Behavior:
  - Scans `videos_dir` for the first `.mp4` (alphabetical order).
  - If `gif_path` is stale or missing, runs ffmpeg to regenerate it.
  - Returns the resolved GIF path, or None if no video is present.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
from typing import Optional

log = logging.getLogger(__name__)


def find_first_mp4(videos_dir: str) -> Optional[str]:
    if not os.path.isdir(videos_dir):
        return None
    matches = sorted(glob.glob(os.path.join(videos_dir, "*.mp4")))
    matches += sorted(glob.glob(os.path.join(videos_dir, "*.MP4")))
    return matches[0] if matches else None


def _is_stale(mp4: str, gif: str) -> bool:
    """GIF is stale if missing or older than the source MP4."""
    if not os.path.isfile(gif):
        return True
    try:
        return os.path.getmtime(gif) < os.path.getmtime(mp4)
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
    Make sure `gif_path` reflects the current MP4 in `videos_dir`.
    Returns the GIF path on success, or None if no MP4 / ffmpeg unavailable.
    """
    mp4 = find_first_mp4(videos_dir)
    if not mp4:
        log.warning(
            "No .mp4 found in %s — idle screen will be blank. "
            "Drop a video into that folder and restart.", videos_dir
        )
        return None

    if not _is_stale(mp4, gif_path):
        log.info("Idle GIF is up to date (%s)", gif_path)
        return gif_path

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.warning(
            "ffmpeg not found on PATH — cannot convert %s. "
            "Install ffmpeg or pre-generate %s manually.", mp4, gif_path
        )
        return gif_path if os.path.isfile(gif_path) else None

    os.makedirs(os.path.dirname(gif_path) or ".", exist_ok=True)
    vf = (
        f"fps={fps},"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    log.info("Converting %s → %s (%dx%d @ %dfps)", mp4, gif_path, width, height, fps)
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", mp4, "-vf", vf, "-loop", "0", gif_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return gif_path
    except subprocess.CalledProcessError as e:
        log.error("ffmpeg conversion failed: %s", e)
        return None
