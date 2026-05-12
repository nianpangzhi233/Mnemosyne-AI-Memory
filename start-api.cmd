@echo off
chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set HF_ENDPOINT=https://hf-mirror.com

echo ==========================================
echo  Mnemosyne REST API
echo ==========================================
echo.
echo  API:     http://localhost:8979/api/health
echo  Swagger: http://localhost:8979/docs
echo.

python "%~dp0scripts\api\start_api.py" --port 8979
