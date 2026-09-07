@echo off
rem Launch BongoCatClicker AS ADMINISTRATOR (needed if Bongo Cat itself runs elevated)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" -Elevated
