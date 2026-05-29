"""
Idle-mode GIF loop player.

We pre-convert the user's MP4 to a GIF via ffmpeg in the install script,
then iterate frames at a fixed interval and push to the screen.
"""

from __future__ import annotations

import logging
import os
import time
from typing import List

from PIL import Image, ImageSequence

log = logging.getLogger(__name__)


class IdlePlayer:
    def __init__(self, gif_path: str, frame_interval: float = 0.125):
        self.gif_path = gif_path
        self.frame_interval = frame_interval
        self._frames: List[Image.Image] = []
        self._loaded = False

    def _load(self, target_size):
        if self._loaded:
            return
        if not os.path.isfile(self.gif_path):
            log.warning("Idle GIF missing at %s — idle screen will be blank.", self.gif_path)
            # Fall back to a single black frame so the loop still runs.
            self._frames = [Image.new("RGB", target_size, (0, 0, 0))]
            self._loaded = True
            return

        log.info("Loading idle GIF %s", self.gif_path)
        img = Image.open(self.gif_path)
        frames = []
        for frame in ImageSequence.Iterator(img):
            f = frame.convert("RGB")
            if f.size != target_size:
                f = f.resize(target_size, Image.LANCZOS)
            frames.append(f.copy())
        self._frames = frames or [Image.new("RGB", target_size, (0, 0, 0))]
        self._loaded = True
        log.info("Idle GIF loaded: %d frames", len(self._frames))

    def step(self, driver, stop_check) -> None:
        """
        Loop frames until `stop_check()` returns True. Non-blocking-ish:
        sleeps in slices so the main loop can break out within ~50ms.
        """
        # Choose target size from driver, accounting for rotation
        if driver.rotation in (0, 2):
            target = (driver.width, driver.height)
        else:
            target = (driver.height, driver.width)
        self._load(target)

        i = 0
        while not stop_check():
            frame = self._frames[i % len(self._frames)]
            driver.push_frame(frame)
            i += 1
            # Sleep in slices to remain responsive
            t_end = time.monotonic() + self.frame_interval
            while time.monotonic() < t_end:
                if stop_check():
                    return
                time.sleep(0.02)
