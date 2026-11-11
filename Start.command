#!/bin/bash
# Animation Studio - start from source on a Mac. Double-click (the first time: right-click → Open).
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
ORTAM=".mac_ortam"

echo "Animation Studio (Mac)"
echo

# 1) uv: a small tool that manages Python and packages (no administrator password needed)
if ! command -v uv >/dev/null 2>&1; then
  echo "Downloading the setup tool (uv)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh || { echo "uv could not be installed. Check your internet connection."; read -r -p "Press Enter to close"; exit 1; }
  export PATH="$HOME/.local/bin:$PATH"
fi

# 2) The studio's own Python environment (the Mac's system Python is left alone)
if [ ! -x "$ORTAM/bin/python" ]; then
  echo "Preparing Python 3.12 (1-2 minutes the first time)…"
  uv venv --python 3.12 "$ORTAM" || { read -r -p "Something went wrong. Press Enter to close"; exit 1; }
fi
if ! "$ORTAM/bin/python" -c "import yaml, PIL, numpy, playwright, uv, ffmpeg" 2>/dev/null; then
  echo "Installing the required packages…"
  uv pip install --python "$ORTAM/bin/python" -r requirements.txt uv || { read -r -p "Something went wrong. Press Enter to close"; exit 1; }
fi

# 3) A browser for recording video: Playwright's Chromium if neither Chrome nor Edge is installed
if [ ! -d "/Applications/Google Chrome.app" ] && [ ! -d "/Applications/Microsoft Edge.app" ] && [ ! -f "$ORTAM/.chromium_tamam" ]; then
  echo "Chrome not found; downloading Chromium for video recording (~150 MB, once)…"
  "$ORTAM/bin/python" -m playwright install chromium && touch "$ORTAM/.chromium_tamam"
fi

echo
echo "The studio is opening. Closing this window also closes the studio."
exec "$ORTAM/bin/python" studio.py
