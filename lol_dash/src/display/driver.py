"""
Thin wrapper around the vendored `turing-smart-screen-python` library
for the Revision A 3.5" panel (USB35INCHIPS / USB35INCHIPSV2).

We intentionally avoid using the library's `Reset()` call by default —
many resellers' units crash on reset. Set `skip_reset: false` in config
if you want to re-enable it.

The wrapper exposes a single high-level method:
    driver.push_frame(pil_image)

…which dispatches a full-screen JPEG to the panel. Frame rate is roughly
8-12 fps depending on USB host + JPEG quality.
"""

from __future__ import annotations

import glob
import logging
import sys
from typing import Optional

from PIL import Image

log = logging.getLogger(__name__)


def _autodetect_port() -> Optional[str]:
    """Best-effort serial port autodetection across OSes."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return None

    # Turing USB35INCHIPS shows up with various VID:PID combos; we just take
    # the first ttyUSB / cu.usbserial / COM device.
    candidates = []
    for p in list_ports.comports():
        desc = (p.description or "").lower()
        if "usb" in desc or "ch340" in desc or "ch9102" in desc or "serial" in desc:
            candidates.append(p.device)
    if candidates:
        return candidates[0]

    # Filesystem fallback (macOS / Linux)
    for pattern in ("/dev/cu.usbserial-*", "/dev/ttyUSB*", "/dev/ttyACM*"):
        hits = glob.glob(pattern)
        if hits:
            return hits[0]
    return None


class TuringDriver:
    """
    Wraps the upstream `library.lcd.lcd_comm_rev_a.LcdCommRevA` (vendored under
    ./vendor/turing-smart-screen-python). The install script clones it.
    """

    def __init__(
        self,
        com_port: str = "auto",
        width: int = 320,
        height: int = 480,
        rotation: int = 0,
        brightness: int = 200,
        skip_reset: bool = True,
    ):
        self.width = width
        self.height = height
        self.rotation = rotation
        self.brightness = brightness
        self.skip_reset = skip_reset

        port = com_port if com_port != "auto" else _autodetect_port()
        if not port:
            raise RuntimeError(
                "Could not auto-detect Turing screen serial port. "
                "Set `display.com_port` explicitly in config.yaml."
            )
        log.info("Turing screen on %s (%dx%d, rot=%d)", port, width, height, rotation)

        # The Turing library lives at the repo root (we are bundled with it).
        # Walk up from this file to find the repo root and add it to sys.path.
        try:
            import os as _os
            here = _os.path.dirname(_os.path.abspath(__file__))
            repo_root = _os.path.abspath(_os.path.join(here, "..", "..", "..", ".."))
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            from library.lcd.lcd_comm_rev_a import LcdCommRevA
            from library.lcd.lcd_comm import Orientation
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "Could not import the bundled turing-smart-screen-python library. "
                "Make sure you're running this from the repo root with `python -m lol_dash.src.main`."
            ) from e

        self._orient = Orientation
        self.lcd = LcdCommRevA(
            com_port=port, display_width=width, display_height=height
        )

        if not skip_reset:
            try:
                self.lcd.Reset()
            except Exception as e:  # noqa: BLE001
                log.warning("Reset() raised — skipping (%s)", e)

        self.lcd.InitializeComm()
        self.lcd.SetOrientation(self._rotation_to_orientation(rotation))
        self.lcd.SetBrightness(brightness)
        self.lcd.Clear()

    def _rotation_to_orientation(self, r: int):
        return {
            0: self._orient.PORTRAIT,
            1: self._orient.LANDSCAPE,
            2: self._orient.REVERSE_PORTRAIT,
            3: self._orient.REVERSE_LANDSCAPE,
        }.get(r, self._orient.PORTRAIT)

    # ---------------------------------------------------------------- output
    def push_frame(self, img: Image.Image) -> None:
        """Display a full-screen image. Image is resized/converted as needed."""
        # The library is rotation-aware: when in PORTRAIT we draw at (w, h),
        # in LANDSCAPE we draw at (h, w). Match library expectation.
        if self.rotation in (0, 2):
            target = (self.width, self.height)
        else:
            target = (self.height, self.width)
        if img.size != target:
            img = img.resize(target, Image.LANCZOS)
        if img.mode != "RGB":
            img = img.convert("RGB")
        self.lcd.DisplayPILImage(img, 0, 0)

    def clear(self) -> None:
        try:
            self.lcd.Clear()
        except Exception:  # noqa: BLE001
            pass

    def close(self) -> None:
        try:
            self.lcd.ScreenOff()
        except Exception:  # noqa: BLE001
            pass
