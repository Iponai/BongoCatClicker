@echo off
rem Creates desktop-style .lnk shortcuts with the cat icon (optional, just for looks)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\make_shortcuts.ps1"
echo.
pause
