"""
Data Dragon fetcher with disk-cached icons + per-champion spell costs.

Public endpoints used:
  https://ddragon.leagueoflegends.com/api/versions.json
  https://ddragon.leagueoflegends.com/cdn/{ver}/data/{locale}/champion/{Name}.json
  https://ddragon.leagueoflegends.com/cdn/{ver}/img/champion/{Name}.png
  https://ddragon.leagueoflegends.com/cdn/{ver}/img/spell/{spellId}.png
  https://ddragon.leagueoflegends.com/cdn/{ver}/img/passive/{passive.png}
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

import requests
from PIL import Image

log = logging.getLogger(__name__)

BASE = "https://ddragon.leagueoflegends.com"


class DataDragon:
    def __init__(self, version: str = "latest", locale: str = "en_US", cache_dir: str = "assets/cache"):
        self.locale = locale
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.version = self._resolve_version(version)
        self._champ_data_cache: Dict[str, dict] = {}
        log.info("Data Dragon version: %s (locale=%s)", self.version, locale)

    # ------------------------------------------------------------------ setup
    def _resolve_version(self, v: str) -> str:
        if v and v != "latest":
            return v
        try:
            r = requests.get(f"{BASE}/api/versions.json", timeout=5)
            r.raise_for_status()
            return r.json()[0]
        except Exception as e:  # noqa: BLE001
            log.warning("Could not resolve latest DDragon version: %s — falling back", e)
            return "14.10.1"

    # ------------------------------------------------------------- champ data
    def champion_data(self, champion_name: str) -> Optional[dict]:
        """
        Returns the full champion record from Data Dragon.
        `champion_name` is the canonical key (e.g. "Annie", "MissFortune", "Wukong").
        """
        if champion_name in self._champ_data_cache:
            return self._champ_data_cache[champion_name]

        cache_file = os.path.join(self.cache_dir, f"champ_{champion_name}.json")
        if os.path.isfile(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._champ_data_cache[champion_name] = data
                return data
            except Exception:  # noqa: BLE001
                pass

        url = f"{BASE}/cdn/{self.version}/data/{self.locale}/champion/{champion_name}.json"
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            payload = r.json()
            data = (payload.get("data") or {}).get(champion_name)
            if data is None:
                return None
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
            self._champ_data_cache[champion_name] = data
            return data
        except Exception as e:  # noqa: BLE001
            log.warning("Failed to fetch champion data for %s: %s", champion_name, e)
            return None

    def spell_costs(self, champion_name: str) -> Dict[str, List[float]]:
        """
        Returns {"Q": [c1,c2,c3,c4,c5], "W": [...], "E": [...], "R": [...]}.
        Empty list per slot if the spell is resourceless.
        """
        data = self.champion_data(champion_name)
        if not data:
            return {}
        out: Dict[str, List[float]] = {}
        for slot, spell in zip(("Q", "W", "E", "R"), data.get("spells", [])):
            out[slot] = list(spell.get("cost", []) or [])
        return out

    # ---------------------------------------------------------------- icons
    def _cache_path(self, kind: str, key: str) -> str:
        return os.path.join(self.cache_dir, f"{kind}_{key}.png")

    def _download(self, url: str, dest: str) -> bool:
        try:
            r = requests.get(url, timeout=8, stream=True)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("Icon download failed %s: %s", url, e)
            return False

    def champion_icon(self, champion_name: str) -> Optional[Image.Image]:
        dest = self._cache_path("champ", champion_name)
        if not os.path.isfile(dest):
            url = f"{BASE}/cdn/{self.version}/img/champion/{champion_name}.png"
            if not self._download(url, dest):
                return None
        try:
            return Image.open(dest).convert("RGBA")
        except Exception:  # noqa: BLE001
            return None

    def spell_icon(self, champion_name: str, slot: str) -> Optional[Image.Image]:
        """slot ∈ {Q,W,E,R}. Looks up the spell id from champion data."""
        data = self.champion_data(champion_name)
        if not data:
            return None
        spells = data.get("spells", [])
        idx = {"Q": 0, "W": 1, "E": 2, "R": 3}.get(slot)
        if idx is None or idx >= len(spells):
            return None
        spell_id = spells[idx].get("id")
        if not spell_id:
            return None
        dest = self._cache_path("spell", spell_id)
        if not os.path.isfile(dest):
            url = f"{BASE}/cdn/{self.version}/img/spell/{spell_id}.png"
            if not self._download(url, dest):
                return None
        try:
            return Image.open(dest).convert("RGBA")
        except Exception:  # noqa: BLE001
            return None

    def passive_icon(self, champion_name: str) -> Optional[Image.Image]:
        data = self.champion_data(champion_name)
        if not data:
            return None
        passive = data.get("passive") or {}
        image = (passive.get("image") or {}).get("full")
        if not image:
            return None
        dest = self._cache_path("passive", image)
        if not os.path.isfile(dest):
            url = f"{BASE}/cdn/{self.version}/img/passive/{image}"
            if not self._download(url, dest):
                return None
        try:
            return Image.open(dest).convert("RGBA")
        except Exception:  # noqa: BLE001
            return None
