# PyInstaller spec — builds a single-file executable for lol-turing-dash.
#
# Usage (run from REPO ROOT):
#     pyinstaller lol_dash/lol_dash.spec --clean --noconfirm
#
# Produces:
#     dist/lol-turing-dash             (macOS / Linux)
#     dist/lol-turing-dash.exe         (Windows)
#
# Place the executable in any folder. It will look for:
#   ./lol_dash/config.yaml             (override the bundled default)
#   ./lol_dash/videos/*.mp4            (your idle video)
#   ./lol_dash/certs/riotgames.pem     (Riot cert — auto-downloaded on first run)
# next to the binary.

# ruff: noqa
import os
import sys

block_cipher = None

# Resolve repo root. SPECPATH is the directory containing this .spec file,
# i.e. <repo>/lol_dash — so the repo root is one level up.
REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

# Data files we MUST ship inside the exe so the app can run from anywhere.
# These are extracted to sys._MEIPASS at runtime by PyInstaller.
datas = [
    (os.path.join(REPO_ROOT, "lol_dash", "config.yaml"), "lol_dash"),
    # Bundled default cert location is empty; cert.py will download on first run.
]

# The whole upstream `library/` package is a hidden dependency tree because
# we import it dynamically via sys.path manipulation.
hidden_imports = [
    "library",
    "library.lcd",
    "library.lcd.lcd_comm",
    "library.lcd.lcd_comm_rev_a",
    "serial",
    "serial.tools.list_ports",
    "PIL._tkinter_finder",
    "yaml",
]

a = Analysis(
    [os.path.join(REPO_ROOT, "lol_dash", "entrypoint.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Big upstream-only deps we don't use
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "matplotlib", "scipy", "babel",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Also bundle the entire `library/` source tree as data so dynamic
# sys.path additions still resolve.
import glob
for p in glob.glob(os.path.join(REPO_ROOT, "library", "**", "*.py"), recursive=True):
    rel = os.path.relpath(os.path.dirname(p), REPO_ROOT)
    a.datas.append((os.path.join(rel, os.path.basename(p)), p, "DATA"))

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="lol-turing-dash",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
