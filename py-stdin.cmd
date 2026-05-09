@echo off
REM Run Python code from stdin with UTF-8 enabled.
REM Usage from PowerShell:
REM   @'
REM   print("hello")
REM   '@ | .\py-stdin.cmd
set PYTHONUTF8=1
python -X utf8 -
