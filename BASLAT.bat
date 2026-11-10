@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -c "import yaml, PIL, numpy, playwright" 2>nul || (
  echo Gerekli paketler kuruluyor, bir-iki dakika...
  python -m pip install -r gereksinimler.txt
)
python arayuz.py
if errorlevel 1 pause
