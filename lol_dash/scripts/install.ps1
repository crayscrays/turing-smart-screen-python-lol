# lol-turing-dash installer (Windows).
# Run from the REPO ROOT:
#     powershell -ExecutionPolicy Bypass -File lol_dash\scripts\install.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Root = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $Root

Write-Host "==> lol-turing-dash installer (Windows)"
Write-Host "    Repo root: $Root"

# ---------- 1. Python venv ----------
if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating virtualenv .venv"
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1

Write-Host "==> Installing Python dependencies"
python -m pip install --upgrade pip wheel
python -m pip install -r requirements.txt
python -m pip install -r lol_dash\requirements.txt

# ---------- 2. Riot TLS cert ----------
Write-Host "==> Fetching Riot Live Client cert"
New-Item -ItemType Directory -Force -Path lol_dash\certs | Out-Null
try { python -m lol_dash.src.utils.cert } catch { Write-Host "   (cert fetch failed)" }

# ---------- 3. MP4 -> GIF ----------
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpeg) {
    if ((Test-Path "lol_dash\assets\idle.mp4") -and -not (Test-Path "lol_dash\assets\idle.gif")) {
        Write-Host "==> Converting lol_dash\assets\idle.mp4 -> lol_dash\assets\idle.gif"
        & ffmpeg -y -i "lol_dash\assets\idle.mp4" `
            -vf "fps=8,scale=320:480:force_original_aspect_ratio=increase,crop=320:480" `
            -loop 0 "lol_dash\assets\idle.gif"
    } else {
        Write-Host "==> Skipping GIF conversion (place file at lol_dash\assets\idle.mp4 and re-run)"
    }
} else {
    Write-Host "!! ffmpeg not found - install via 'winget install Gyan.FFmpeg' to enable idle video."
}

Write-Host ""
Write-Host "==> Done."
Write-Host "    Activate venv:   .\.venv\Scripts\Activate.ps1"
Write-Host "    Run dashboard:   python -m lol_dash.src.main --config lol_dash\config.yaml"
Write-Host "    Preview only:    python -m lol_dash.src.main --config lol_dash\config.yaml --no-screen"
