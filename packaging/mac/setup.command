#!/bin/bash
# Animation Studio - first-run setup on macOS (the app opens this by itself)
H="$HOME/AnimationStudio"
cd "$H" || exit 1
export PATH="$H/.bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export UV_PYTHON_INSTALL_DIR="$H/.python" UV_CACHE_DIR="$H/.uv_cache" PYTHONUTF8=1
hata() { echo; echo "Error: $1"; echo "Check your internet connection and open the app again."; read -r -p "Press Enter to close"; exit 1; }
clear
echo "Animation Studio is getting ready."
echo "Downloading what it needs. This takes 2-5 minutes and happens only once."
echo "Everything goes into ~/AnimationStudio; nothing else on your Mac is changed."
echo
if [ ! -x "$H/.bin/uv" ]; then
  echo "> Downloading the installer tool (uv)..."
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$H/.bin" UV_NO_MODIFY_PATH=1 INSTALLER_NO_MODIFY_PATH=1 sh >/dev/null || hata "uv could not be downloaded."
fi
if [ ! -x "$H/.ortam/bin/python" ]; then
  echo "> Preparing Python..."
  "$H/.bin/uv" venv -q --python 3.12 "$H/.ortam" || hata "Python could not be prepared."
fi
echo "> Installing packages..."
"$H/.bin/uv" pip install -q --python "$H/.ortam/bin/python" -r requirements.txt || hata "The packages could not be installed."
if [ ! -d "/Applications/Google Chrome.app" ] && [ ! -d "/Applications/Microsoft Edge.app" ] && [ ! -f "$H/.ortam/.chromium_tamam" ]; then
  echo "> Downloading Chromium for rendering (about 150 MB, once)..."
  "$H/.ortam/bin/python" -m playwright install chromium && touch "$H/.ortam/.chromium_tamam" || echo "Chromium could not be downloaded. The studio will open, but to render videos open the app again later (it retries) or install Google Chrome."
fi
# The bundled ffmpeg is an Intel build; Apple-silicon Macs need Rosetta for it (a Homebrew ffmpeg is used instead when present)
if [ "$(uname -m)" = "arm64" ] && ! command -v ffmpeg >/dev/null 2>&1 && ! /usr/bin/arch -x86_64 /usr/bin/true 2>/dev/null; then
  echo
  echo "> Video encoding needs Apple's Rosetta component (free, once)."
  /usr/sbin/softwareupdate --install-rosetta --agree-to-license || echo "Rosetta could not be installed; rendering may not work."
fi
echo
echo "Ready. The studio is opening in your browser."
echo "You can close this window. To quit the studio, use Quit at the top right of the studio."
mkdir -p "$H/data"
nohup "$H/.ortam/bin/python" studio.py > "$H/data/studio.log" 2>&1 &
sleep 2
