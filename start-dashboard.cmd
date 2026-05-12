@echo off
chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

echo ==========================================
echo  Mnemosyne Dashboard
echo ==========================================
echo.
echo  Dashboard: http://localhost:8501
echo.

python -m streamlit run "%~dp0scripts\dashboard\app.py" --server.port=8501 --server.headless=true --browser.gatherUsageStats=false
