@echo off
chcp 65001 >nul 2>&1
set HF_ENDPOINT=https://hf-mirror.com
set PYTHONIOENCODING=utf-8

echo ==========================================
echo  Memory Evolution v4.0 - Dream Cycle
echo ==========================================
echo.

python "%~dp0scripts\graph_dream.py" --stats
echo.
echo Running dream cycle...
python "%~dp0scripts\graph_dream.py"
echo.
echo Done. Updated stats:
python "%~dp0scripts\graph_dream.py" --stats
echo.
pause
