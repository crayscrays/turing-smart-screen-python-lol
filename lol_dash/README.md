# lol-turing-dash

A League of Legends dashboard for the **Turing Smart Screen 3.5" (Revision A)**.

- **Idle mode** — loops a GIF (converted from your MP4) when you're not in a match.
- **In-game mode** — pulls live data from the League **Live Client Data API** and renders champion portrait, KDA, HP/mana, gold/CS, and Q/W/E/R spell icons. Each spell icon flashes when cast.

This sub-folder is the application code. The bundled `turing-smart-screen-python` library lives at the repo root.

The app is purely **passive** — it reads only Riot's official local HTTPS API at `127.0.0.1:2999`. No keyboard/mouse hooks, no game memory access, no input injection. Zero anti-cheat surface.

---

## Quick start

```bash
# from the REPO ROOT (the folder with `library/`, `lol_dash/`, etc.)
git clone https://github.com/crayscrays/turing-smart-screen-python-lol.git
cd turing-smart-screen-python-lol

# Drop your idle video here:
cp /path/to/your/video.mp4 lol_dash/assets/idle.mp4

# Linux / macOS:
bash lol_dash/scripts/install.sh
source .venv/bin/activate
python -m lol_dash.src.main

# Windows:
powershell -ExecutionPolicy Bypass -File lol_dash\scripts\install.ps1
.\.venv\Scripts\Activate.ps1
python -m lol_dash.src.main
```

The installer:
1. Creates `.venv`
2. Installs upstream library deps (`requirements.txt`) + our deps (`lol_dash/requirements.txt`)
3. Downloads Riot's public cert to `lol_dash/certs/riotgames.pem`
4. Converts `lol_dash/assets/idle.mp4` → `lol_dash/assets/idle.gif` (8fps, 320×480 portrait) via `ffmpeg`

---

## Layout

```
turing-smart-screen-python-lol/
├── library/                              ← upstream turing-smart-screen-python
│   └── lcd/lcd_comm_rev_a.py             ← Revision A driver (what we wrap)
├── lol_dash/                             ← OUR APP
│   ├── config.yaml                       ← all tunables
│   ├── requirements.txt                  ← extra deps on top of upstream
│   ├── README.md                         ← this file
│   ├── certs/                            ← Riot TLS cert (auto-downloaded)
│   ├── assets/
│   │   ├── idle.mp4                      ← drop your video here
│   │   ├── idle.gif                      ← auto-generated
│   │   └── cache/                        ← Data Dragon icons
│   ├── scripts/
│   │   ├── install.sh / install.ps1
│   │   └── mock_lol_server.py            ← offline-dev fake API
│   └── src/
│       ├── main.py                       ← state machine entrypoint
│       ├── lol_client.py                 ← Live Client API w/ TLS
│       ├── game_state.py                 ← KDA + cast inference
│       ├── data_dragon.py                ← icon + spell-cost fetcher
│       ├── display/
│       │   ├── driver.py                 ← wraps library/lcd_comm_rev_a
│       │   ├── idle_player.py            ← GIF frame pusher
│       │   └── dashboard.py              ← PIL composer (Pillow)
│       └── utils/cert.py                 ← Riot cert download
└── (upstream files: main.py, configure.py, theme-editor.py, etc.)
```

The upstream `main.py` / `configure.py` / `theme-editor.py` are unrelated to this app — they're for the original system-monitor product. You can ignore them.

---

## How it works

### State machine
```
                ┌──────────┐   /activeplayer returns 200    ┌──────────┐
   START ─────► │   IDLE   │ ─────────────────────────────► │ IN_GAME  │
                │ (GIF)    │ ◄── 5 consecutive 404/refused ─│ (Dash)   │
                └──────────┘                                 └──────────┘
```
- Idle polls every 250 ms
- In-game polls `/activeplayer` every 100 ms, `/playerscores` every ~400 ms
- 5-frame debounce avoids flicker during loading screens

### Cast detection
The Live Client API does **not** expose cast events. Two complementary signals:

1. **Resource delta** — diff `resourceValue` every 100 ms; match drops against Data Dragon spell costs at current rank (±15% tolerance). Works for mana/energy champs.
2. **Level-up flash** — flash an icon when its `abilityLevel` increments. Fallback for resourceless champs (Garen, Riven, Katarina) — they still get KDA / HP / portrait / CS / gold, plus the rank-up flash.

### TLS / Riot cert
The League client serves `https://127.0.0.1:2999` with a self-signed cert (`CN=LocalHost`). The installer downloads Riot's published cert and we pass `verify=` to `requests`. Missing cert → falls back to `verify=False` with a warning.

### Reset() workaround
Revision A units (`USB35INCHIPS` / `USB35INCHIPSV2`) can hang on `lcd.Reset()`. Our `TuringDriver` skips it by default (`display.skip_reset: true` in `config.yaml`). If your unit handles resets, flip it to `false`.

---

## Configuration (`lol_dash/config.yaml`)

| Section | Key | What it does |
|---|---|---|
| `display` | `com_port` | `auto`, or `COM5` / `/dev/cu.usbserial-…` / `/dev/ttyUSB0` |
| `display` | `rotation` | `0` portrait (default), `1`/`2`/`3` for rotated |
| `display` | `brightness` | 0–255 |
| `display` | `skip_reset` | `true` for USB35INCHIPS |
| `lol` | `poll_ingame` | Frame poll interval while in-game (seconds) |
| `lol` | `exit_debounce` | Consecutive misses before returning to idle |
| `idle` | `frame_interval` | Seconds between GIF frames (0.125 = 8fps) |
| `cast_detection` | `min_delta` | Min mana/energy drop to flag a cast |
| `cast_detection` | `match_tolerance` | Match window (0.15 = ±15%) |
| `cast_detection` | `highlight_duration` | Icon highlight fade (seconds) |
| `cast_detection` | `level_up_flash` | Flash on rank-up (resourceless fallback) |

---

## Offline dev

Iterate the dashboard without a real game **or** the screen:

```bash
pip install cryptography

# Terminal 1
python lol_dash/scripts/mock_lol_server.py

# Terminal 2 — frames write to lol_dash/assets/preview.jpg
python -m lol_dash.src.main --no-screen --mock
```

---

## Troubleshooting

**Can't find COM port** — run `python -c "from serial.tools import list_ports; [print(p) for p in list_ports.comports()]"` and paste the device into `display.com_port`.

**Screen upside-down** — set `display.rotation` to `2`.

**Spell icons never flash** — you're on a resourceless champ; verify `cast_detection.level_up_flash: true`. You'll see flashes on rank-up.

**"TLS verify failed"** — re-run `python -m lol_dash.src.utils.cert`. If you're behind a TLS-inspecting proxy, delete the cert file and the app falls back to insecure TLS.

**Low fps** — Revision A panels are UART-serial; ~8–12 fps full-screen is the realistic ceiling.

---

## Anti-cheat / ToS

This app only reads `https://127.0.0.1:2999/liveclientdata/*`. It is functionally equivalent to opening that URL in a browser. No hooks, no injection, no memory reads. Riot can change API access at any time — this is unofficial.

---

## License

GPL-3.0 — required by the bundled upstream library. See `LICENSE` at the repo root.
