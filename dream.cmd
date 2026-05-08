@echo off
chcp 65001 >nul 2>&1
set HF_ENDPOINT=https://hf-mirror.com
set PYTHONIOENCODING=utf-8

echo ==========================================
echo  Mnemosyne v6.1 - Dream Cycle (Fast/Slow)
echo ==========================================
echo.

python "%~dp0scripts\graph_dream.py" --stats
echo.
echo Running dream cycle...
echo   Fast Path (always): Snapshot -^> SimilarTo -^> Decay -^> Covenant -^> Sync
echo   Slow Path (optional): LogScan -^> Distill -^> Causal -^> Transfers -^> Contradicts -^> Strategy -^> LLMReview
echo   Use --no-slow to skip Slow Path (LLM phases)
echo.
python "%~dp0scripts\graph_dream.py" --full --no-slow
echo.
echo Done. Updated stats:
python "%~dp0scripts\graph_dream.py" --stats
echo.
pause
