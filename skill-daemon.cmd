@echo off
chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set HF_ENDPOINT=https://hf-mirror.com

echo ==========================================
echo  Mnemosyne Skill Daemon
echo ==========================================
echo.
echo  Full dream cycle: 03:00, 12:00, 17:00
echo  Post-dream skill loop: auto scan, evolve, trial, gate
echo.

python "%~dp0scripts\skill_daemon.py" --loop
