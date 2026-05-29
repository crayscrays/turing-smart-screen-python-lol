"""
In-game dashboard renderer.

Composes a portrait 320x480 PIL frame with:
  - Champion portrait + summoner name + level
  - Large KDA
  - Health bar + resource bar
  - CS + gold
  - Q/W/E/R spell row with level pips and cast-highlight ring
"""

from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from ..game_state import GameSnapshot, SLOTS


# --- Theme ---
BG       = (12, 14, 22)
PANEL    = (22, 26, 38)
ACCENT   = (90, 200, 255)
GOLD     = (200, 170, 90)
RED      = (220, 70, 70)
GREEN    = (90, 200, 120)
TEXT     = (235, 240, 250)
DIM      = (130, 140, 160)
MANA     = (90, 140, 240)
ENERGY   = (240, 220, 100)
HEALTH   = (90, 200, 120)


def _font(size: int) -> ImageFont.ImageFont:
    # Try a few common fonts; fall back to default if nothing found.
    for candidate in (
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if os.path.isfile(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _resource_color(rtype: str):
    rtype = (rtype or "").upper()
    if rtype == "ENERGY":
        return ENERGY
    if rtype in ("NONE", "BLOODWELL", ""):
        return DIM
    return MANA


def _rounded_rect(draw: ImageDraw.ImageDraw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _bar(draw, x, y, w, h, frac, color, bg=PANEL):
    frac = max(0.0, min(1.0, frac))
    _rounded_rect(draw, (x, y, x + w, y + h), h // 2, bg)
    if frac > 0:
        _rounded_rect(draw, (x, y, x + int(w * frac), y + h), h // 2, color)


def render_dashboard(
    snap: GameSnapshot,
    ddragon,
    tracker,
    width: int = 320,
    height: int = 480,
) -> Image.Image:
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    # === Header strip: champ portrait + name + level ===
    portrait_size = 72
    portrait = ddragon.champion_icon(snap.champion_name) if snap.champion_name else None
    if portrait:
        portrait = portrait.resize((portrait_size, portrait_size), Image.LANCZOS)
        img.paste(portrait, (12, 12), portrait)
    else:
        _rounded_rect(draw, (12, 12, 12 + portrait_size, 12 + portrait_size), 10, PANEL)

    # Level chip
    chip_x, chip_y = 12 + portrait_size - 22, 12 + portrait_size - 22
    _rounded_rect(draw, (chip_x, chip_y, chip_x + 24, chip_y + 22), 6, (0, 0, 0, 220))
    draw.text((chip_x + 6, chip_y + 3), str(snap.level), font=_font(14), fill=ACCENT)

    # Summoner / champ text
    name_font = _font(18)
    sub_font = _font(13)
    draw.text((portrait_size + 24, 16), snap.summoner_name or "—", font=name_font, fill=TEXT)
    draw.text((portrait_size + 24, 40), snap.champion_name or "—", font=sub_font, fill=DIM)

    # === KDA panel ===
    panel_y = 100
    _rounded_rect(draw, (12, panel_y, width - 12, panel_y + 86), 14, PANEL)
    kda_font = _font(36)
    sep_font = _font(28)
    label_font = _font(11)

    k = str(snap.kills)
    d = str(snap.deaths)
    a = str(snap.assists)

    # Lay out K / D / A centered
    cx = width // 2
    spacing = 16
    k_w = draw.textlength(k, font=kda_font)
    d_w = draw.textlength(d, font=kda_font)
    a_w = draw.textlength(a, font=kda_font)
    sep_w = draw.textlength("/", font=sep_font)
    total_w = k_w + d_w + a_w + 2 * sep_w + 4 * spacing
    cur_x = cx - total_w / 2
    base_y = panel_y + 18

    draw.text((cur_x, base_y), k, font=kda_font, fill=GREEN)
    cur_x += k_w + spacing
    draw.text((cur_x, base_y + 4), "/", font=sep_font, fill=DIM)
    cur_x += sep_w + spacing
    draw.text((cur_x, base_y), d, font=kda_font, fill=RED)
    cur_x += d_w + spacing
    draw.text((cur_x, base_y + 4), "/", font=sep_font, fill=DIM)
    cur_x += sep_w + spacing
    draw.text((cur_x, base_y), a, font=kda_font, fill=ACCENT)

    draw.text((cx - 22, panel_y + 64), "KILLS / DEATHS / ASSISTS",
              font=label_font, fill=DIM, anchor="lm")

    # === Stats row: CS, gold ===
    stat_y = panel_y + 96
    draw.text((20, stat_y), f"CS  {snap.cs}", font=_font(14), fill=TEXT)
    gold_text = f"{int(snap.current_gold):,}g"
    gold_w = draw.textlength(gold_text, font=_font(14))
    draw.text((width - 20 - gold_w, stat_y), gold_text, font=_font(14), fill=GOLD)

    # === Health + resource bars ===
    bar_y = stat_y + 26
    bar_w = width - 24
    _bar(draw, 12, bar_y, bar_w, 12,
         (snap.current_health / snap.max_health) if snap.max_health else 0, HEALTH)
    draw.text((16, bar_y - 2), "HP", font=_font(10), fill=TEXT)

    res_color = _resource_color(snap.resource_type)
    _bar(draw, 12, bar_y + 22, bar_w, 10,
         (snap.resource_value / snap.resource_max) if snap.resource_max else 0, res_color)
    draw.text((16, bar_y + 20), snap.resource_type[:4], font=_font(9), fill=TEXT)

    # === Spell row (Q W E R) ===
    row_y = bar_y + 64
    icon = 56
    gap = (width - 4 * icon) // 5
    x = gap
    for slot in SLOTS:
        # Icon
        spell_img = ddragon.spell_icon(snap.champion_name, slot) if snap.champion_name else None
        lvl = snap.ability_levels.get(slot, 0)
        if spell_img:
            spell_img = spell_img.resize((icon, icon), Image.LANCZOS)
            if lvl < 1:
                # Greyscale + dim
                gs = spell_img.convert("L").convert("RGBA")
                # Apply translucency
                a = gs.split()[-1]
                gs.putalpha(a.point(lambda v: int(v * 0.45)))
                img.paste(gs, (x, row_y), gs)
            else:
                img.paste(spell_img, (x, row_y), spell_img)
        else:
            _rounded_rect(draw, (x, row_y, x + icon, row_y + icon), 8, PANEL)

        # Slot key label (top-left)
        _rounded_rect(draw, (x, row_y, x + 18, row_y + 18), 4, (0, 0, 0, 200))
        draw.text((x + 4, row_y + 1), slot, font=_font(13), fill=ACCENT)

        # Cast highlight ring
        alpha = tracker.highlight_alpha(slot) if tracker else 0.0
        if alpha > 0:
            ring_color = (255, 230, 120, int(255 * alpha))
            for off in range(3):
                draw.rounded_rectangle(
                    (x - off, row_y - off, x + icon + off, row_y + icon + off),
                    radius=8 + off, outline=ring_color, width=2,
                )

        # Level pips
        pip_y = row_y + icon + 6
        max_pips = 3 if slot != "R" else 3  # visual cap; ult shows 3 pips
        pip_count = 5 if slot != "R" else 3
        pip_gap = 3
        pip_w = (icon - (pip_count - 1) * pip_gap) // pip_count
        for i in range(pip_count):
            color = ACCENT if i < lvl else PANEL
            px = x + i * (pip_w + pip_gap)
            _rounded_rect(draw, (px, pip_y, px + pip_w, pip_y + 4), 2, color)

        x += icon + gap

    # === Footer hint ===
    draw.text((width / 2, height - 14), "lol-turing-dash",
              font=_font(9), fill=DIM, anchor="mm")

    return img
