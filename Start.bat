@echo off
rem Animation Studio - start from source on Windows (needs Python on PATH)
chcp 65001 >nul
cd /d "%~dp0"
python -c "import yaml, PIL, numpy, playwright" 2>nul || (
  echo Installing the required packages, this takes a minute or two...
  python -m pip install -r requirements.txt
)
python studio.py
if errorlevel 1 pause
