@echo off
REM Double-click runner for lol-turing-dash (Windows).
REM Activates the venv (creating it on first run) and launches the dashboard.

setlocal
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.."

if not exist ".venv\" (
    echo First run -- installing dependencies (one-time, ~1 minute)...
    powershell -ExecutionPolicy Bypass -File lol_dash\scripts\install.ps1
)

call .venv\Scripts\activate.bat
python -m lol_dash.src.main %*

popd
endlocal
pause
