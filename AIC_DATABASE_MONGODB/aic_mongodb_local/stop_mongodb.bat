@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_mongodb.ps1"
pause
