"""
lol-turing-dash entrypoint.

Run with:
    python -m src.main [--config config.yaml] [--mock] [--no-screen]

States:
    IDLE     → play idle GIF loop
    IN_GAME  → render dashboard from Live Client API
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from threading import Event

import yaml

from .data_dragon import DataDragon
from .display.dashboard import render_dashboard
from .display.idle_player import IdlePlayer
from .game_state import GameStateTracker
from .lol_client import LiveClient, LiveClientConfig
from .utils.cert import ensure_cert

log = logging.getLogger("lol-turing-dash")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_driver(cfg_display: dict, no_screen: bool):
    if no_screen:
        return _PreviewDriver(
            width=cfg_display["width"],
            height=cfg_display["height"],
            rotation=cfg_display.get("rotation", 0),
        )
    from .display.driver import TuringDriver
    return TuringDriver(
        com_port=cfg_display.get("com_port", "auto"),
        width=cfg_display["width"],
        height=cfg_display["height"],
        rotation=cfg_display.get("rotation", 0),
        brightness=cfg_display.get("brightness", 200),
        skip_reset=cfg_display.get("skip_reset", True),
    )


class _PreviewDriver:
    """Saves frames to assets/preview.jpg instead of pushing to the screen."""

    def __init__(self, width: int, height: int, rotation: int = 0):
        self.width = width
        self.height = height
        self.rotation = rotation
        os.makedirs("lol_dash/assets", exist_ok=True)

    def push_frame(self, img):
        img.save("lol_dash/assets/preview.jpg", quality=85)

    def clear(self):
        pass

    def close(self):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="lol_dash/config.yaml")
    ap.add_argument("--mock", action="store_true",
                    help="Point at the mock server on https://127.0.0.1:2999")
    ap.add_argument("--no-screen", action="store_true",
                    help="Save frames to assets/preview.jpg instead of using the panel")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    cfg = load_config(args.config)

    # --- TLS cert ---
    cert_path = cfg["lol"].get("cert_path", "lol_dash/certs/riotgames.pem")
    ensure_cert(cert_path)

    # --- Components ---
    ddragon = DataDragon(
        version=cfg["ddragon"].get("version", "latest"),
        locale=cfg["ddragon"].get("locale", "en_US"),
        cache_dir=cfg["ddragon"].get("cache_dir", "assets/cache"),
    )

    tracker = GameStateTracker(
        spell_costs_provider=ddragon.spell_costs,
        min_delta=cfg["cast_detection"].get("min_delta", 5),
        match_tolerance=cfg["cast_detection"].get("match_tolerance", 0.15),
        highlight_duration=cfg["cast_detection"].get("highlight_duration", 0.8),
        level_up_flash=cfg["cast_detection"].get("level_up_flash", True),
    )

    lol = LiveClient(LiveClientConfig(
        endpoint=cfg["lol"]["endpoint"],
        cert_path=cert_path,
    ))

    driver = build_driver(cfg["display"], args.no_screen)

    idle = IdlePlayer(
        gif_path=cfg["idle"].get("gif_path", "assets/idle.gif"),
        frame_interval=cfg["idle"].get("frame_interval", 0.125),
    )

    poll_idle = cfg["lol"].get("poll_idle", 0.25)
    poll_ingame = cfg["lol"].get("poll_ingame", 0.1)
    exit_debounce = cfg["lol"].get("exit_debounce", 5)

    # --- Shutdown handling ---
    stop = Event()

    def _shutdown(*_):
        log.info("Shutting down…")
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    # ============================ MAIN LOOP ============================
    log.info("Ready. Idle until a League game is detected.")
    in_game = False
    miss_streak = 0
    last_static_refresh = 0.0

    try:
        while not stop.is_set():
            if not in_game:
                # --- IDLE: try to enter game ---
                idle.step(driver, stop_check=lambda: stop.is_set() or _game_started(lol))
                if stop.is_set():
                    break
                # Coming out of idle means the next poll succeeded
                active = lol.active_player()
                if active is None:
                    continue
                in_game = True
                miss_streak = 0
                tracker.reset()
                # Look up champion name
                summoner = active.get("summonerName", "")
                champ = _lookup_champion(lol, summoner)
                tracker.update_static(summoner, champ)
                log.info("In-game: %s as %s", summoner, champ)

            # --- IN_GAME ---
            active = lol.active_player()
            if active is None:
                miss_streak += 1
                if miss_streak >= exit_debounce:
                    log.info("Game ended — back to idle.")
                    in_game = False
                    tracker.reset()
                    driver.clear()
                    continue
                time.sleep(poll_ingame)
                continue

            miss_streak = 0
            tracker.update_active(active)

            # Scores refresh — slightly less often (~every 4 frames)
            now = time.monotonic()
            if now - last_static_refresh > 0.4:
                scores = lol.player_scores(tracker.snapshot.summoner_name)
                tracker.update_scores(scores or {})
                last_static_refresh = now

            frame = render_dashboard(
                tracker.snapshot, ddragon, tracker,
                width=cfg["display"]["width"],
                height=cfg["display"]["height"],
            )
            driver.push_frame(frame)
            time.sleep(poll_ingame)

    finally:
        driver.close()


def _game_started(lol: LiveClient) -> bool:
    return lol.active_player() is not None


def _lookup_champion(lol: LiveClient, summoner_name: str) -> str:
    plist = lol.player_list() or []
    for p in plist:
        if p.get("summonerName") == summoner_name:
            # rawChampionName has a stable id; championName is the display name
            # — Data Dragon keys typically match championName for most champs.
            return p.get("championName", "") or ""
    return ""


if __name__ == "__main__":
    sys.exit(main())
