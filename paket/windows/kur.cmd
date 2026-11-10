@echo off
rem Animation Studio - first-run setup. The launcher opens this window only when something must be downloaded.
chcp 65001 >nul
cd /d "%~dp0"
title Animation Studio - setup
set "UV_PYTHON_INSTALL_DIR=%~dp0.python"
set "UV_CACHE_DIR=%~dp0.uv_cache"
set "PYTHONUTF8=1"
echo.
echo   Animation Studio is getting ready.
echo   Downloading what it needs. This takes 2-5 minutes and happens only once.
echo   This window closes by itself when it is done.
echo.
if not exist ".ortam\Scripts\python.exe" (
  "bin\uv.exe" venv --python 3.12 .ortam || goto hata
)
"bin\uv.exe" pip install --python .ortam\Scripts\python.exe -r gereksinimler.txt || goto hata
exit /b 0
:hata
echo.
echo   Setup could not finish. Check your internet connection and open Animation Studio again.
pause
exit /b 1
