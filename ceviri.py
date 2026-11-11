"""Çeviri: seslendirme metinlerini ve ekrandaki yazıları başka dillere çevirir.

Çeviriler senaryoya (video.yaml / sahne dosyaları) dokunmadan projenin ceviri.json dosyasına yazılır:
  {"kaynak": "tr", "diller": {"pl": {"anlatim": {"1": "..."}, "ekran": {"<kaynak yazı>": "<çeviri>"}}}}
Senaryoda o dil zaten yazılıysa senaryodaki kullanılır; çeviri sadece eksikleri doldurur.
Çeviriyi yapan model Chatterbox'ın ortamında, bilgisayarda çalışır (bkz. tts_yonetici.ceviri_baslat).
"""
import json, os, re

DOSYA = "ceviri.json"
DILLER = {"tr", "en", "pl", "pt", "es", "de", "fr", "it", "nl", "ru", "ar", "ja", "ko", "zh", "hi", "sv", "da", "fi",
          "no", "el", "he", "ms", "sw", "uk", "cs", "ro", "hu"}
DIL_AD = {"tr": "Turkish", "en": "English", "pl": "Polish", "pt": "Portuguese", "es": "Spanish", "de": "German",
          "fr": "French", "it": "Italian", "nl": "Dutch", "ru": "Russian", "ar": "Arabic", "ja": "Japanese",
          "ko": "Korean", "zh": "Chinese", "hi": "Hindi", "sv": "Swedish", "da": "Danish", "fi": "Finnish",
          "no": "Norwegian", "el": "Greek", "he": "Hebrew", "ms": "Malay", "sw": "Swahili", "uk": "Ukrainian",
          "cs": "Czech", "ro": "Romanian", "hu": "Hungarian"}
_NESNE = re.compile(r"\{([^{}]*)\}")
_CIFT = re.compile(r"""([A-Za-z]{2}(?:[-_][A-Za-z]{2})?)\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")


def yol(klasor):
    return os.path.join(klasor, DOSYA)


def oku(klasor):
    try:
        with open(yol(klasor), encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("diller"), dict):
            return d
    except (OSError, ValueError):
        pass
    return {"kaynak": None, "diller": {}}


def kaydet(klasor, d):
    gecici = yol(klasor) + ".yeni"
    with open(gecici, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol(klasor))


def _dize(s):
    """JS dize sabitini Python dizesine çevirir ("..." ya da '...')."""
    if s[0] == "'":
        s = '"' + s[1:-1].replace('\\"', '"').replace('"', '\\"') + '"'
    try:
        return json.loads(s)
    except ValueError:
        return s[1:-1]


def ekran_metinleri(klasor, proje):
    """Vektör sahnelerdeki çok dilli yazılar: { tr: "...", en: "..." } biçimindeki nesneler."""
    dosyalar = []
    for s in proje.get("sahneler") or []:
        if isinstance(s, dict) and s.get("tur") in ("vektor", "uc", "piksel") and s.get("dosya"):
            d = os.path.join(klasor, s["dosya"])
            if os.path.isfile(d) and d not in dosyalar:
                dosyalar.append(d)
                k = os.path.dirname(d)          # sahnelerin ortak js dosyaları (_karakter.js gibi)
                for f in sorted(os.listdir(k)):
                    j = os.path.join(k, f)
                    if f.endswith(".js") and j not in dosyalar:
                        dosyalar.append(j)
    sonuc, gorulen = [], set()
    for d in dosyalar:
        with open(d, encoding="utf-8") as f:
            metin = f.read()
        for m in _NESNE.finditer(metin):
            ic = m.group(1)
            ciftler = _CIFT.findall(ic)
            if len(ciftler) < 1:
                continue
            kalan = _CIFT.sub("", ic).replace(",", "").strip()
            if kalan:               # başka anahtarlar da var: dil nesnesi değil
                continue
            v = {k.lower(): _dize(s) for k, s in ciftler}
            if not set(v) <= DILLER:   # { ad: "..." } gibi dil olmayan anahtarlar
                continue
            anahtar = json.dumps(v, sort_keys=True, ensure_ascii=False)
            if anahtar not in gorulen:
                gorulen.add(anahtar); sonuc.append(v)
    return sonuc


def _anlatim(s):
    a = s.get("anlatim") if isinstance(s, dict) else None
    return a if isinstance(a, dict) else ({} if not a else {"_": str(a)})


def isler(klasor, proje, kaynak, hedefler, hepsi=False):
    """Çevrilecekler: [(hedef_dil, tur, anahtar, kaynak_metin)]. tur: 'anlatim' (anahtar sahne no) ya da 'ekran'."""
    c = oku(klasor)
    liste = []
    ekran = ekran_metinleri(klasor, proje)
    for h in hedefler:
        var = c["diller"].get(h, {})
        for i, s in enumerate(proje.get("sahneler") or []):
            a = _anlatim(s)
            m = str(a.get(kaynak) or "").strip()
            if not m or str(a.get(h) or "").strip():
                continue                                    # senaryoda zaten yazılı
            if not hepsi and (var.get("anlatim") or {}).get(str(i + 1)):
                continue
            liste.append((h, "anlatim", str(i + 1), m))
        for v in ekran:
            m = str(v.get(kaynak) or "").strip()
            if not m or v.get(h):
                continue
            if not hepsi and m in (var.get("ekran") or {}):
                continue
            liste.append((h, "ekran", m, m))
    return liste


def yaz(klasor, kaynak, hedef, tur, anahtar, metin):
    c = oku(klasor)
    c["kaynak"] = kaynak or c.get("kaynak")
    c["diller"].setdefault(hedef, {}).setdefault(tur, {})[anahtar] = metin
    kaydet(klasor, c)


def birlestir(ozet_sahneler, diller, klasor):
    """ozet(): senaryoda olmayan dillerin metinlerini çeviriden doldurur, çevrilen dilleri dil listesine ekler."""
    c = oku(klasor)
    for h, d in c["diller"].items():
        if h not in diller:
            diller.append(h)
        for no, metin in (d.get("anlatim") or {}).items():
            for s in ozet_sahneler:
                if str(s["no"]) == no and isinstance(s["anlatim"], dict) and not str(s["anlatim"].get(h) or "").strip():
                    s["anlatim"] = dict(s["anlatim"], **{h: metin})
                    s.setdefault("ceviri", []).append(h)
    return diller
