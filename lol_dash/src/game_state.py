"""
Game state tracker.

Consumes successive snapshots of /activeplayer + /playerscores and emits:
  - current KDA + level + gold + health
  - ability levels Q/W/E/R (0..5)
  - 'cast events' inferred from resource drops or level-ups

Cast detection is heuristic. The Live Client API doesn't expose cast events
directly, so we do two things:
  1) Resource-delta: if resourceValue drops by ~spell_cost (looked up from
     Data Dragon static data), flag the matching spell.
  2) Level-up flash: when abilityLevel increments, briefly flash that spell.
     This is the fallback for resource-less champs (Garen, Riven, Katarina).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

SLOTS = ("Q", "W", "E", "R")


@dataclass
class CastEvent:
    slot: str          # "Q" | "W" | "E" | "R"
    at: float          # time.monotonic() timestamp
    reason: str        # "resource" | "levelup"


@dataclass
class GameSnapshot:
    summoner_name: str = ""
    champion_name: str = ""
    level: int = 1
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    cs: int = 0
    current_gold: float = 0.0
    current_health: float = 0.0
    max_health: float = 0.0
    resource_value: float = 0.0
    resource_max: float = 0.0
    resource_type: str = "MANA"
    ability_levels: Dict[str, int] = field(
        default_factory=lambda: {"Q": 0, "W": 0, "E": 0, "R": 0}
    )
    recent_casts: List[CastEvent] = field(default_factory=list)


class GameStateTracker:
    def __init__(
        self,
        spell_costs_provider,           # callable(champ) -> {slot: [cost_per_level...]}
        min_delta: float = 5.0,
        match_tolerance: float = 0.15,
        highlight_duration: float = 0.8,
        level_up_flash: bool = True,
    ):
        self.spell_costs_provider = spell_costs_provider
        self.min_delta = min_delta
        self.match_tolerance = match_tolerance
        self.highlight_duration = highlight_duration
        self.level_up_flash = level_up_flash

        self._snap = GameSnapshot()
        self._prev_resource: Optional[float] = None
        self._prev_levels: Dict[str, int] = {s: 0 for s in SLOTS}

    # ------------------------------------------------------------- properties
    @property
    def snapshot(self) -> GameSnapshot:
        return self._snap

    # ---------------------------------------------------------------- updates
    def update_static(self, summoner_name: str, champion_name: str) -> None:
        self._snap.summoner_name = summoner_name
        self._snap.champion_name = champion_name

    def update_scores(self, scores: dict) -> None:
        if not scores:
            return
        self._snap.kills = int(scores.get("kills", 0))
        self._snap.deaths = int(scores.get("deaths", 0))
        self._snap.assists = int(scores.get("assists", 0))
        self._snap.cs = int(scores.get("creepScore", 0))

    def update_active(self, active: dict) -> None:
        if not active:
            return

        self._snap.level = int(active.get("level", 1))
        self._snap.current_gold = float(active.get("currentGold", 0.0))

        stats = active.get("championStats", {}) or {}
        self._snap.current_health = float(stats.get("currentHealth", 0.0))
        self._snap.max_health = float(stats.get("maxHealth", 0.0))
        self._snap.resource_value = float(stats.get("resourceValue", 0.0))
        self._snap.resource_max = float(stats.get("resourceMax", 0.0))
        self._snap.resource_type = str(stats.get("resourceType", "MANA"))

        abilities = active.get("abilities", {}) or {}
        new_levels = {
            s: int((abilities.get(s) or {}).get("abilityLevel", 0)) for s in SLOTS
        }

        now = time.monotonic()

        # --- Cast detection: resource delta ---
        if self._prev_resource is not None:
            delta = self._prev_resource - self._snap.resource_value
            if delta >= self.min_delta:
                slot = self._match_spell_by_cost(delta, new_levels)
                if slot:
                    self._emit(CastEvent(slot=slot, at=now, reason="resource"))

        # --- Level-up flash fallback ---
        if self.level_up_flash:
            for s in SLOTS:
                if new_levels[s] > self._prev_levels.get(s, 0):
                    self._emit(CastEvent(slot=s, at=now, reason="levelup"))

        self._snap.ability_levels = new_levels
        self._prev_resource = self._snap.resource_value
        self._prev_levels = new_levels

        # Prune highlights older than the configured duration
        cutoff = now - self.highlight_duration
        self._snap.recent_casts = [e for e in self._snap.recent_casts if e.at >= cutoff]

    def reset(self) -> None:
        """Called when leaving a game."""
        self._snap = GameSnapshot()
        self._prev_resource = None
        self._prev_levels = {s: 0 for s in SLOTS}

    # ------------------------------------------------------- helpers / queries
    def highlight_alpha(self, slot: str) -> float:
        """0.0 → 1.0 fade based on most recent cast in that slot."""
        now = time.monotonic()
        latest = max(
            (e.at for e in self._snap.recent_casts if e.slot == slot),
            default=None,
        )
        if latest is None:
            return 0.0
        age = now - latest
        if age >= self.highlight_duration:
            return 0.0
        return max(0.0, 1.0 - (age / self.highlight_duration))

    # ----------------------------------------------------------------- internal
    def _emit(self, ev: CastEvent) -> None:
        log.debug("CAST %s (%s)", ev.slot, ev.reason)
        self._snap.recent_casts.append(ev)

    def _match_spell_by_cost(
        self, delta: float, levels: Dict[str, int]
    ) -> Optional[str]:
        """Find the spell whose cost (at its current rank) most closely matches `delta`."""
        champ = self._snap.champion_name
        if not champ:
            return None
        try:
            cost_table = self.spell_costs_provider(champ)
        except Exception as e:  # noqa: BLE001
            log.debug("cost lookup failed for %s: %s", champ, e)
            return None
        if not cost_table:
            return None

        best_slot = None
        best_diff = float("inf")
        for slot in SLOTS:
            lvl = levels.get(slot, 0)
            if lvl < 1:
                continue
            costs = cost_table.get(slot) or []
            if not costs:
                continue
            # cost lists are 0-indexed by rank-1
            idx = min(lvl - 1, len(costs) - 1)
            expected = float(costs[idx] or 0)
            if expected <= 0:
                continue
            diff = abs(delta - expected) / max(expected, 1.0)
            if diff < self.match_tolerance and diff < best_diff:
                best_diff = diff
                best_slot = slot
        return best_slot
