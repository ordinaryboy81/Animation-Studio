#!/bin/bash
# Builds the Windows installer and the macOS app into packaging/dist/.
# Needs: bash, makensis (NSIS 3), zip, curl, unzip. Run from anywhere: bash packaging/build.sh
set -e
P="$(cd "$(dirname "$0")" && pwd)"; K="$(dirname "$P")"; C="$P/dist"
SURUM="$(tr -d '[:space:]' < "$K/.surum")"; UV_SURUM="${UV_SURUM:-0.13.7}"
rm -rf "$C"; mkdir -p "$C/win" "$C/mac"

copy_app() {   # program files only: no projects, voices, models or caches
  for f in studio.py render.py voice.py translation.py updater.py changelog.json template.yaml requirements.txt CLAUDE.md README.md README.tr.md LICENSE THIRD_PARTY.md .surum engine tools fonts data; do
    cp -R "$K/$f" "$1/"
  done
  rm -f "$1/data/studio.log" "$1/data/.kisayol"; find "$1" -name "__pycache__" -prune -exec rm -rf {} +
}

# ---- Windows (x64) ----
copy_app "$C/win"
mkdir -p "$C/win/bin"
if [ -f "$P/uv.exe" ]; then cp "$P/uv.exe" "$C/win/bin/uv.exe"; else
  curl -LsSf -o "$C/uv.zip" "https://github.com/astral-sh/uv/releases/download/$UV_SURUM/uv-x86_64-pc-windows-msvc.zip"
  unzip -q -j "$C/uv.zip" uv.exe -d "$C/win/bin"; rm "$C/uv.zip"
fi
cp "$P/windows/setup.cmd" "$C/win/"
(cd "$P/windows" && makensis -V2 -INPUTCHARSET UTF8 launcher.nsi && mv launcher.exe "$C/win/Animation Studio.exe")
(cd "$P/windows" && makensis -V2 -INPUTCHARSET UTF8 "-DSURUM=$SURUM" installer.nsi)

# ---- macOS (Apple silicon and Intel) ----
A="$C/mac/Animation Studio.app/Contents"
mkdir -p "$A/MacOS" "$A/Resources/app"
cp "$P/mac/Info.plist" "$A/"; cp "$P/icon/studio.icns" "$A/Resources/"
cp "$P/mac/AnimationStudio" "$A/MacOS/"; chmod +x "$A/MacOS/AnimationStudio"
copy_app "$A/Resources/app"
cp "$P/mac/setup.command" "$A/Resources/app/"; chmod +x "$A/Resources/app/setup.command"
(cd "$C/mac" && zip -q -r -y "../Animation-Studio-$SURUM-macOS.zip" "Animation Studio.app")
rm -rf "$C/win" "$C/mac"
ls -la "$C"
