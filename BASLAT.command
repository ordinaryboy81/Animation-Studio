#!/bin/bash
# Animasyon Stüdyosu — Mac başlatıcı. Çift tıkla (ilk seferde: sağ tık → Aç).
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
ORTAM=".mac_ortam"

echo "🎬 Animasyon Stüdyosu (Mac)"
echo

# 1) uv: Python'u ve paketleri yöneten küçük araç (yönetici şifresi gerekmez)
if ! command -v uv >/dev/null 2>&1; then
  echo "▶ Kurulum aracı (uv) indiriliyor…"
  curl -LsSf https://astral.sh/uv/install.sh | sh || { echo "uv kurulamadı. İnternet bağlantını kontrol et."; read -r -p "Kapatmak için Enter'a bas"; exit 1; }
  export PATH="$HOME/.local/bin:$PATH"
fi

# 2) Stüdyonun kendi Python ortamı (Mac'in sistem Python'una dokunmaz)
if [ ! -x "$ORTAM/bin/python" ]; then
  echo "▶ Python 3.12 ortamı hazırlanıyor (ilk seferde 1-2 dk)…"
  uv venv --python 3.12 "$ORTAM" || { read -r -p "Hata oluştu. Kapatmak için Enter'a bas"; exit 1; }
fi
if ! "$ORTAM/bin/python" -c "import yaml, PIL, numpy, playwright, uv" 2>/dev/null; then
  echo "▶ Gerekli paketler kuruluyor…"
  uv pip install --python "$ORTAM/bin/python" -r gereksinimler.txt uv || { read -r -p "Hata oluştu. Kapatmak için Enter'a bas"; exit 1; }
fi

# 3) Video kaydı için tarayıcı: Chrome/Edge yoksa Playwright'ın Chromium'u
if [ ! -d "/Applications/Google Chrome.app" ] && [ ! -d "/Applications/Microsoft Edge.app" ] && [ ! -f "$ORTAM/.chromium_tamam" ]; then
  echo "▶ Chrome bulunamadı, video kaydı için Chromium indiriliyor (~150 MB, tek seferlik)…"
  "$ORTAM/bin/python" -m playwright install chromium && touch "$ORTAM/.chromium_tamam"
fi

# 4) ffmpeg (video ve ses birleştirme)
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo
  echo "⚠️  ffmpeg bulunamadı. Video ve ses işlemek için gerekli."
  if command -v brew >/dev/null 2>&1; then
    echo "▶ Homebrew ile kuruluyor…"
    brew install ffmpeg
  else
    echo "ffmpeg'i kurmak için Homebrew gerekiyor (Mac'in yaygın, ücretsiz paket yöneticisi)."
    read -r -p "Homebrew ve ffmpeg şimdi kurulsun mu? Mac şifreni isteyecek. (e/h) " cevap
    if [ "$cevap" = "e" ] || [ "$cevap" = "E" ]; then
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      [ -x /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
      [ -x /usr/local/bin/brew ] && eval "$(/usr/local/bin/brew shellenv)"
      brew install ffmpeg
    else
      echo "ffmpeg olmadan stüdyo açılır ama video oluşturulamaz."
    fi
  fi
fi

echo
echo "✅ Stüdyo açılıyor. Bu pencereyi kapatırsan stüdyo da kapanır."
exec "$ORTAM/bin/python" arayuz.py
