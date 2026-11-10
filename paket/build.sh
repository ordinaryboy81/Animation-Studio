#!/bin/bash
# Builds the Windows installer and the macOS app into paket/cikti/.
# Needs: bash, makensis (NSIS 3), zip, curl, unzip. Run from anywhere: bash paket/build.sh
set -e
P="$(cd "$(dirname "$0")" && pwd)"; K="$(dirname "$P")"; C="$P/cikti"
SURUM="$(cat "$K/.surum")"; UV_SURUM="${UV_SURUM:-0.13.7}"
rm -rf "$C"; mkdir -p "$C/win" "$C/mac"

kopyala() {   # program files only: no projects, voices, models or caches
  for f in arayuz.py olustur.py tts_yonetici.py ceviri.py bos_sablon.yaml gereksinimler.txt CLAUDE.md BENI_OKU.md README.md LICENSE THIRD_PARTY.md .surum motor araclar fontlar veri; do
    cp -R "$K/$f" "$1/"
  done
  rm -f "$1/veri/studyo.log" "$1/veri/.kisayol"; find "$1" -name "__pycache__" -prune -exec rm -rf {} +
}

# ---- Windows (x64) ----
kopyala "$C/win"
mkdir -p "$C/win/bin"
if [ -f "$P/uv.exe" ]; then cp "$P/uv.exe" "$C/win/bin/uv.exe"; else
  curl -LsSf -o "$C/uv.zip" "https://github.com/astral-sh/uv/releases/download/$UV_SURUM/uv-x86_64-pc-windows-msvc.zip"
  unzip -q -j "$C/uv.zip" uv.exe -d "$C/win/bin"; rm "$C/uv.zip"
fi
cp "$P/windows/kur.cmd" "$C/win/"
(cd "$P/windows" && makensis -V2 -INPUTCHARSET UTF8 baslatici.nsi && mv baslatici.exe "$C/win/Animation Studio.exe")
(cd "$P/windows" && makensis -V2 -INPUTCHARSET UTF8 kurulum.nsi)

# ---- macOS (Apple silicon and Intel) ----
A="$C/mac/Animation Studio.app/Contents"
mkdir -p "$A/MacOS" "$A/Resources/uygulama"
cp "$P/mac/Info.plist" "$A/"; cp "$P/ikon/studyo.icns" "$A/Resources/"
cp "$P/mac/AnimationStudio" "$A/MacOS/"; chmod +x "$A/MacOS/AnimationStudio"
kopyala "$A/Resources/uygulama"
cp "$P/mac/kurulum.command" "$A/Resources/uygulama/"; chmod +x "$A/Resources/uygulama/kurulum.command"
(cd "$C/mac" && zip -q -r -y "../Animation-Studio-$SURUM-macOS.zip" "Animation Studio.app")
rm -rf "$C/win" "$C/mac"
ls -la "$C"
