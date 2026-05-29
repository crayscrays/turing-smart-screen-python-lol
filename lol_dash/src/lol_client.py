"""
League of Legends Live Client Data API wrapper.

The local game client binds an HTTPS server to 127.0.0.1:2999 whenever a
match is loaded. The cert is self-signed by Riot — `install.sh` downloads
the public chain so we can do proper TLS verification.

Endpoints we care about:
  /liveclientdata/allgamedata       — everything (heavier)
  /liveclientdata/activeplayer      — your champion only (light, what we poll)
  /liveclientdata/playerlist        — used once per game for champion lookup
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import requests
import urllib3

log = logging.getLogger(__name__)


@dataclass
class LiveClientConfig:
    endpoint: str
    cert_path: str
    timeout: float = 1.0


class LiveClient:
    """Minimal HTTPS client for the local Riot Live Client Data API."""

    def __init__(self, cfg: LiveClientConfig):
        self.cfg = cfg
        self.session = requests.Session()

        # Resolve cert path; if missing, fall back to insecure (warn once).
        if cfg.cert_path and os.path.isfile(cfg.cert_path):
            self.session.verify = cfg.cert_path
            log.info("TLS verify using %s", cfg.cert_path)
        else:
            log.warning(
                "Riot cert not found at %s — falling back to insecure TLS. "
                "Run scripts/fetch_cert.sh (or .ps1) to fix.",
                cfg.cert_path,
            )
            self.session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Riot's cert CN is "LocalHost" — disable hostname matching just in case
        # by routing the call through the same session settings.
        self._base = cfg.endpoint.rsplit("/", 1)[0]  # strip "/allgamedata"

    # ----------------------------------------------------------------- helpers
    def _get(self, path: str) -> Optional[dict]:
        url = f"{self._base}/{path.lstrip('/')}"
        try:
            r = self.session.get(url, timeout=self.cfg.timeout)
        except (requests.ConnectionError, requests.Timeout):
            return None
        except requests.exceptions.RequestException as e:
            log.debug("LoL API error: %s", e)
            return None
        if r.status_code != 200:
            return None
        try:
            return r.json()
        except ValueError:
            return None

    # ------------------------------------------------------------ public calls
    def all_game_data(self) -> Optional[dict]:
        """Full snapshot — heavy. Use once per game start or for debugging."""
        return self._get("allgamedata")

    def active_player(self) -> Optional[dict]:
        """
        Light endpoint we poll while in-game. Returns:
            {
              "abilities": {
                  "E": {"abilityLevel": 0, "displayName": "...", "id": "...", ...},
                  "Passive": {...},
                  "Q": {...}, "R": {...}, "W": {...}
              },
              "championStats": {... "resourceValue": N, "resourceMax": N, ...},
              "currentGold": float,
              "fullRunes": {...},
              "level": int,
              "summonerName": str
            }
        """
        return self._get("activeplayer")

    def player_list(self) -> Optional[list]:
        """One-shot lookup to map summonerName → championName."""
        return self._get("playerlist")

    def player_scores(self, summoner_name: str) -> Optional[dict]:
        """{kills, deaths, assists, creepScore, wardScore}"""
        return self._get(f"playerscores?summonerName={summoner_name}")

    def is_alive(self) -> bool:
        """Quick liveness check used by the state machine."""
        return self._get("gamestats") is not None
