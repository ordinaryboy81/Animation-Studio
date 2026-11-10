"""
Chatterbox seslendirme yöneticisi: kurulum, güncelleme, geri alma ve ses üretimi.
Stüdyo (arayuz.py) bunu kullanır; elle çalıştırmana gerek yok.

Yapı (hepsi stüdyo klasörünün içinde, 'tts/' altında):
  tts/env/          Chatterbox'un kendi Python 3.11 ortamı (stüdyonun Python'una dokunmaz)
  tts/env_old/      bir önceki sürüm (güncelleme kötü giderse tek tıkla geri dönülür)
  tts/model/        Hugging Face model dosyaları (~3 GB, ilk üretimde iner)
  tts/sesler/       ses kütüphanesi: <ses>/ornek.wav + bilgi.json (klonlama örnekleri, şablonlar)
  tts/surum.json    kurulu sürüm bilgisi
  tts/ayarlar.json  ses ayarları
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

KOK = os.path.dirname(os.path.abspath(__file__))
TTS = os.path.join(KOK, "tts")
ORTAM = os.path.join(TTS, "env")
YENI = os.path.join(TTS, "env_new")
ESKI = os.path.join(TTS, "env_old")
SURUM = os.path.join(TTS, "surum.json")
SURUM_ESKI = os.path.join(TTS, "surum_old.json")
AYAR = os.path.join(TTS, "ayarlar.json")
REFERANS = os.path.join(TTS, "referans")
HF = os.path.join(TTS, "model")
ISCI_BETIK = os.path.join(KOK, "motor", "chatterbox_isci.py")
GIZLI = 0x08000000 if os.name == "nt" else 0

REPO = "resemble-ai/chatterbox"
PERTH = "resemble-ai/Perth"
MAC = sys.platform == "darwin"
TORCH_SECENEK = ["auto"] if MAC else ["cu126", "cu128", "auto"]   # Windows: ekran kartı görünene kadar sırayla denenir
ANLATIM_UZ = (".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac")
REF_UZ = (".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".aac", ".flac", ".webm", ".opus")
BOSTA_KAPAT_SN = 600                              # 10 dk kullanılmazsa model GPU'dan çıkarılır
VARSAYILAN_AYAR = {"model": "", "duygu": 0.5, "cfg": 0.5, "sicaklik": 0.8, "otomatik_kontrol": True, "otomatik_tekrar": True}
KONTROL_ESIK = 0.95      # Whisper'ın duyduğu ile senaryonun benzerliği bunun altındaysa sahne "şüpheli"

IS = {"calisiyor": False, "tur": None, "asama": "", "yuzde": 0, "log": [], "hata": None, "biten": 0, "toplam": 0}
_DUR = {"istek": False, "p": None}


class Durduruldu(Exception):
    pass


# ------------------------------------------------------------------ yardımcılar
def ortam_py(k):
    return os.path.join(k, "Scripts", "python.exe") if os.name == "nt" else os.path.join(k, "bin", "python")


def _env():
    return dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", HF_HOME=HF,
                HF_HUB_DISABLE_SYMLINKS_WARNING="1", UV_NO_PROGRESS="1", PYTHONWARNINGS="ignore",
                PYTORCH_ENABLE_MPS_FALLBACK="1")


def _log(metin):
    for s in metin.replace("\r", "\n").split("\n"):
        s = s.rstrip()
        if s:
            IS["log"].append(s)
    if len(IS["log"]) > 400:
        del IS["log"][:-300]


def _json(yol, varsayilan=None):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def _json_yaz(yol, veri):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)


def kurulu():
    return os.path.isfile(ortam_py(ORTAM)) and os.path.isfile(SURUM)


def surum():
    return _json(SURUM) if kurulu() else None


def _sil(yol):
    if os.path.isdir(yol):
        shutil.rmtree(yol, ignore_errors=True)
    return not os.path.exists(yol)


def _calistir(arglar):
    """Komutu çalıştırır, çıktısını canlı olarak kayıtlara yazar, çıkış kodunu döndürür."""
    _log("$ " + " ".join(os.path.basename(a) if i == 0 else a for i, a in enumerate(arglar)))
    p = subprocess.Popen(arglar, cwd=KOK, env=_env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, creationflags=GIZLI)
    _DUR["p"] = p
    kalan = ""
    while True:
        parca = p.stdout.read1(4096)
        if not parca:
            break
        kalan += parca.decode("utf-8", "replace")
        if "\n" in kalan or "\r" in kalan:
            kes = max(kalan.rfind("\n"), kalan.rfind("\r"))
            _log(kalan[:kes]); kalan = kalan[kes + 1:]
    if kalan:
        _log(kalan)
    kod = p.wait()
    _DUR["p"] = None
    if _DUR["istek"]:
        raise Durduruldu()
    return kod


def _sil_dosya(yol):
    try:
        if yol and os.path.isfile(yol):
            os.remove(yol)
    except OSError:
        pass


def _sureci_oldur(p):
    if not p or p.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], creationflags=GIZLI, capture_output=True)
    else:
        p.kill()


# ------------------------------------------------------------------ GitHub (güncelleme kontrolü)
_GH = {"zaman": 0, "son": None, "yenilikler": {}}


def _gh(yol):
    istek = urllib.request.Request("https://api.github.com" + yol, headers={
        "User-Agent": "animasyon-studyosu", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(istek, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def son_surum(zorla=False):
    if not zorla and _GH["son"] and time.time() - _GH["zaman"] < 1800:
        return _GH["son"]
    try:
        c = _gh(f"/repos/{REPO}/commits/master")
        _GH["son"] = {"sha": c["sha"], "tarih": c["commit"]["committer"]["date"],
                      "mesaj": c["commit"]["message"].strip().splitlines()[0]}
        _GH["zaman"] = time.time()
    except Exception as e:  # noqa: BLE001
        if not _GH["son"]:
            return {"hata": f"GitHub'a ulaşılamadı ({e})"}
    return _GH["son"]


def yenilikler():
    s, son = surum(), son_surum()
    if not s or "sha" not in son or s["sha"] == son["sha"]:
        return []
    anahtar = (s["sha"], son["sha"])
    if anahtar not in _GH["yenilikler"]:
        try:
            c = _gh(f"/repos/{REPO}/compare/{s['sha']}...{son['sha']}")
            _GH["yenilikler"][anahtar] = [{"mesaj": x["commit"]["message"].strip().splitlines()[0],
                                           "tarih": x["commit"]["committer"]["date"]} for x in c.get("commits", [])][::-1][:20]
        except Exception as e:  # noqa: BLE001
            return [{"mesaj": f"Liste alınamadı: {e}", "tarih": ""}]
    return _GH["yenilikler"][anahtar]


# ------------------------------------------------------------------ ayarlar ve ses örnekleri
def ayarlar():
    a = dict(VARSAYILAN_AYAR, **(_json(AYAR, {}) or {}))
    modeller = (surum() or {}).get("modeller") or []
    if a["model"] not in modeller:
        a["model"] = modeller[-1] if modeller else ""      # en yeni model
    return a


def ayar_kaydet(v):
    a = ayarlar()
    for k in ("duygu", "cfg", "sicaklik"):
        if k in v:
            a[k] = max(0.0, min(2.0, float(v[k])))
    for k in ("otomatik_kontrol", "otomatik_tekrar"):
        if k in v:
            a[k] = bool(v[k])
    if "model" in v:
        a["model"] = str(v["model"])
    if "ceviri_model" in v:
        a["ceviri_model"] = str(v["ceviri_model"]).strip()
    _json_yaz(AYAR, a)
    return a


# ------------------------------------------------------------------ ses kütüphanesi
# tts/sesler/<id>/ornek.wav + bilgi.json {"ad", "tur": yuklenen|sablon|kopya, "oran"}
# "hazir" = Chatterbox'un kendi sesi (örnek dosyası yok, klonlama yapılmaz)
SESLER = os.path.join(TTS, "sesler")
HAZIR_ORNEK = os.path.join(SESLER, "_hazir_ornek.wav")
SABLONLAR = [("Hazır ses · kalın", 0.87), ("Hazır ses · çok kalın", 0.78), ("Hazır ses · ince", 1.12)]
SABLON_METNI = ("Hello, and welcome. Today we are going to explore a fascinating story, step by step. "
                "Some of it may surprise you, so stay with me until the very end.")


def _ses_klasoru(ses_id):
    if not ses_id or not all(c.isalnum() or c in "-_" for c in ses_id) or ses_id.startswith("_"):
        raise ValueError("Geçersiz ses")
    return os.path.join(SESLER, ses_id)


def ses_ornegi(ses_id):
    """Klonlama için kullanılacak örnek dosya; 'hazir' için None."""
    if ses_id == "hazir":
        return None
    yol = os.path.join(_ses_klasoru(ses_id), "ornek.wav")
    return yol if os.path.isfile(yol) else None


def _gocur():
    """Eski düzen (tts/referans/<dil>.wav) varsa kütüphaneye taşır."""
    if not os.path.isdir(REFERANS):
        return
    a = _json(AYAR, {}) or {}
    for f in os.listdir(REFERANS):
        ad, uz = os.path.splitext(f)
        if uz != ".wav" or ad.startswith("_"):
            continue
        sid = "eski-" + ad
        os.makedirs(os.path.join(SESLER, sid), exist_ok=True)
        os.replace(os.path.join(REFERANS, f), os.path.join(SESLER, sid, "ornek.wav"))
        _json_yaz(os.path.join(SESLER, sid, "bilgi.json"),
                  {"ad": "Ses örneği (genel)" if ad == "genel" else f"Ses örneği ({ad.upper()})", "tur": "yuklenen"})
        a.setdefault("sesler", {})["*" if ad == "genel" else ad] = sid
    _json_yaz(AYAR, a)
    shutil.rmtree(REFERANS, ignore_errors=True)


def ses_listesi(ses_suresi):
    _gocur()
    hz = ((_json(AYAR, {}) or {}).get("hazir_ses") or {})
    liste = [{"id": "hazir", "ad": "Hazır ses (Chatterbox)", "tur": "hazir", "hiz": float(hz.get("hiz", 1.0)),
              "duraklama": float(hz.get("duraklama", 0.3)),
              "url": f"/tts-ses/_hazir?v={os.path.getmtime(HAZIR_ORNEK)}" if os.path.isfile(HAZIR_ORNEK) else None,
              "sure": ses_suresi(HAZIR_ORNEK) if os.path.isfile(HAZIR_ORNEK) else 0}]
    if os.path.isdir(SESLER):
        digerleri = []
        for sid in os.listdir(SESLER):
            yol = os.path.join(SESLER, sid, "ornek.wav")
            if sid.startswith("_") or not os.path.isfile(yol):
                continue
            b = _json(os.path.join(SESLER, sid, "bilgi.json"), {}) or {}
            digerleri.append({"id": sid, "ad": b.get("ad") or sid, "tur": b.get("tur", "yuklenen"), "oran": b.get("oran"),
                              "hiz": float(b.get("hiz", 1.0)), "duraklama": float(b.get("duraklama", 0.3)),
                              "url": f"/tts-ses/{sid}?v={os.path.getmtime(yol)}", "sure": ses_suresi(yol),
                              "zaman": os.path.getmtime(yol)})
        sira = {"yuklenen": 0, "kopya": 1, "sablon": 2}
        liste += sorted(digerleri, key=lambda x: (sira.get(x["tur"], 3), x["ad"].lower()))
    return liste


VARSAYILAN_TEMPO = 4.5     # Chatterbox'ın konuşma temposu (hece/sn civarı, ölçülen)


def konusma_temposu(yol):
    """Kayıttaki konuşma temposunu ölçer: konuşulan saniye başına hece tepesi ve ortalama duraklama.
    Döndürür {tempo, duraklama} ya da None."""
    try:
        import numpy as np
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", yol, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                           capture_output=True, creationflags=GIZLI)
        x = np.frombuffer(p.stdout, np.int16).astype(np.float32) / 32768
        if len(x) < 16000 * 3:
            return None
        X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / 16000)
        X[(f < 300) | (f > 3000)] = 0                      # konuşma bandı
        y = np.fft.irfft(X, len(x))
        hop = 160
        e = np.sqrt(np.convolve(y * y, np.ones(400) / 400, "same"))[::hop]
        db = 20 * np.log10(e + 1e-6); esik = db.max() - 35
        aktif = (db > esik).mean() * len(x) / 16000
        duraklar, c = [], 0
        for v in db <= esik:
            if v: c += 1
            else:
                if c * hop / 16000 > 0.25: duraklar.append(c * hop / 16000)
                c = 0
        sm = np.convolve(e, np.ones(9) / 9, "same")
        enaz = 10 ** ((esik + 12) / 20); belirgin = sm.max() * 0.06; ara = int(0.11 * 16000 / hop)
        tepeler, son = 0, -ara
        for i in range(1, len(sm) - 1):
            if sm[i] >= sm[i - 1] and sm[i] > sm[i + 1] and sm[i] > enaz and i - son >= ara:
                sol = sm[max(0, i - ara * 2):i].min(); sag = sm[i + 1:i + ara * 2].min() if i + 1 < len(sm) else 0
                if sm[i] - max(sol, sag) > belirgin:
                    tepeler += 1; son = i
        if aktif < 2:
            return None
        return {"tempo": round(float(tepeler / aktif), 2), "duraklama": round(float(sum(duraklar) / len(duraklar)), 2) if duraklar else 0.3}
    except Exception:  # noqa: BLE001
        return None


def tempo_onerisi(olcum):
    """Ölçülen tempoya göre önerilen hız ve duraklama."""
    if not olcum:
        return {"hiz": 1.0, "duraklama": 0.3}
    hiz = max(0.7, min(1.1, olcum["tempo"] / VARSAYILAN_TEMPO))
    return {"hiz": round(hiz * 20) / 20, "duraklama": round(max(0.2, min(0.7, olcum["duraklama"])) * 20) / 20}


def ses_ayari(ses_id):
    """Bir sesin konuşma hızı ve cümle arası duraklaması."""
    if ses_id == "hazir":
        b = (_json(AYAR, {}) or {}).get("hazir_ses") or {}
    else:
        b = _json(os.path.join(_ses_klasoru(ses_id), "bilgi.json"), {}) or {}
    return {"hiz": float(b.get("hiz", 1.0)), "duraklama": float(b.get("duraklama", 0.3))}


def ses_ayari_kaydet(ses_id, hiz, duraklama):
    hiz = max(0.6, min(1.3, float(hiz))); duraklama = max(0.0, min(1.5, float(duraklama)))
    if ses_id == "hazir":
        a = _json(AYAR, {}) or {}
        a["hazir_ses"] = {"hiz": hiz, "duraklama": duraklama}
        _json_yaz(AYAR, a)
    else:
        if not ses_ornegi(ses_id):
            raise ValueError("Ses bulunamadı")
        yol = os.path.join(_ses_klasoru(ses_id), "bilgi.json")
        b = _json(yol, {}) or {}
        b.update(hiz=hiz, duraklama=duraklama)
        _json_yaz(yol, b)


def _yeni_id(ad):
    tablo = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU-")
    taban = "".join(c for c in ad.translate(tablo).lower() if c.isalnum() or c == "-")
    while "--" in taban:
        taban = taban.replace("--", "-")
    taban = taban[:24].strip("-") or "ses"
    sid, i = taban, 2
    while os.path.exists(os.path.join(SESLER, sid)):
        sid, i = f"{taban}-{i}", i + 1
    return sid


def _ffmpeg(arglar):
    p = subprocess.run(["ffmpeg", "-y", "-v", "error"] + arglar, capture_output=True, text=True, creationflags=GIZLI)
    if p.returncode != 0:
        raise ValueError("Ses dosyası işlenemedi: " + (p.stderr.strip().splitlines() or ["?"])[-1])


def ses_ekle(ad, uz, veri):
    """Yüklenen kaydı kütüphaneye ekler: mono 24 kHz wav, en fazla 30 sn, baş/son sessizlik kırpılır."""
    ad = (ad or "").strip()[:60] or "Yeni ses"
    os.makedirs(SESLER, exist_ok=True)
    ham = os.path.join(SESLER, "_yukleme" + uz)
    with open(ham, "wb") as f:
        f.write(veri)
    sid = _yeni_id(ad)
    k = os.path.join(SESLER, sid)
    os.makedirs(k)
    try:
        _ffmpeg(["-i", ham, "-t", "30", "-ac", "1", "-ar", "24000", "-af",
                 "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                 "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                 "highpass=f=70,loudnorm=I=-18:TP=-2:LRA=11", "-ar", "24000", os.path.join(k, "ornek.wav")])
    except ValueError:
        shutil.rmtree(k, ignore_errors=True)
        raise
    finally:
        os.remove(ham)
    olcum = konusma_temposu(os.path.join(k, "ornek.wav"))
    _json_yaz(os.path.join(k, "bilgi.json"), dict({"ad": ad, "tur": "yuklenen", "olcum": olcum}, **tempo_onerisi(olcum)))
    return sid


def ses_turet(kaynak, oran, ad=None, tur="kopya"):
    """Bir sesin daha kalın (<1) ya da daha ince (>1) kopyasını oluşturur. Klonlama bu örnekten yapılacağı için
    sonuç doğal bir ses olur; sadece ton ve ses rengi kayar."""
    oran = float(oran)
    if not 0.6 <= oran <= 1.5:
        raise ValueError("Oran 0.6 ile 1.5 arasında olmalı (0.85 = daha kalın, 1.1 = daha ince).")
    kaynak_yol = HAZIR_ORNEK if kaynak == "hazir" else ses_ornegi(kaynak)
    if not kaynak_yol or not os.path.isfile(kaynak_yol):
        raise ValueError("Hazır sesin örneği henüz yok. Önce 'Hazır şablonları oluştur'a bas."
                         if kaynak == "hazir" else "Kaynak ses bulunamadı.")
    if not ad:
        kaynak_ad = next((x["ad"] for x in ses_listesi(lambda y: 0) if x["id"] == kaynak), "Ses")
        ad = f"{kaynak_ad} · {'kalın' if oran < 1 else 'ince'} ({oran:g})"
    sid = _yeni_id(ad)
    k = os.path.join(SESLER, sid)
    os.makedirs(k)
    try:   # hızı koruyarak tonu ve ses rengini birlikte kaydır
        _ffmpeg(["-i", kaynak_yol, "-af", f"asetrate={round(24000 * oran)},aresample=24000,atempo={1 / oran:.5f}",
                 "-ac", "1", os.path.join(k, "ornek.wav")])
    except ValueError:
        shutil.rmtree(k, ignore_errors=True)
        raise
    _json_yaz(os.path.join(k, "bilgi.json"), {"ad": ad, "tur": tur, "oran": oran, "kaynak": kaynak})
    return sid


def ses_yeniden_adlandir(ses_id, ad):
    if not ses_ornegi(ses_id):
        raise ValueError("Ses bulunamadı")
    yol = os.path.join(_ses_klasoru(ses_id), "bilgi.json")
    b = _json(yol, {}) or {}
    b["ad"] = (ad or "").strip()[:60] or b.get("ad") or ses_id
    _json_yaz(yol, b)


def ses_sil(ses_id):
    k = _ses_klasoru(ses_id)
    if os.path.isdir(k):
        shutil.rmtree(k)
    a = _json(AYAR, {}) or {}
    a["sesler"] = {d: s for d, s in (a.get("sesler") or {}).items() if s != ses_id}
    _json_yaz(AYAR, a)


def _proje_secim_yolu(klasor):
    return os.path.join(klasor, "ses", "chatterbox.json")


def secili_ses(klasor, dil):
    """Öncelik: bu projede bu dil için seçilen → bu dil için varsayılan → genel varsayılan → hazır ses."""
    _gocur()
    var = lambda s: s == "hazir" or bool(s and ses_ornegi(s))
    proje = (_json(_proje_secim_yolu(klasor), {}) or {}) if klasor else {}
    if var(proje.get(dil)):
        return proje[dil], "proje"
    genel = (_json(AYAR, {}) or {}).get("sesler") or {}
    for anahtar in (dil, "*"):
        if var(genel.get(anahtar)):
            return genel[anahtar], "varsayilan"
    return "hazir", "varsayilan"


def ses_sec(klasor, dil, ses_id, varsayilan=False):
    if ses_id != "hazir" and not ses_ornegi(ses_id):
        raise ValueError("Ses bulunamadı")
    if varsayilan:
        a = _json(AYAR, {}) or {}
        a.setdefault("sesler", {})[dil] = ses_id
        _json_yaz(AYAR, a)
    yol = _proje_secim_yolu(klasor)
    d = _json(yol, {}) or {}
    d[dil] = ses_id
    _json_yaz(yol, d)


# ------------------------------------------------------------------ işçi (modeli GPU'da tutan arka plan süreci)
class Isci:
    def __init__(self):
        self.p = None
        self.kilit = threading.Lock()
        self.son = time.time()
        self.model = None
        self.whisper = False
        self.bilgi = {}

    def acik(self):
        return self.p is not None and self.p.poll() is None

    def baslat(self):
        if self.acik():
            return
        self.model = None
        self.whisper = False
        self.p = subprocess.Popen([ortam_py(ORTAM), "-u", ISCI_BETIK], cwd=TTS, env=_env(), stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=GIZLI)
        threading.Thread(target=self._stderr, args=(self.p,), daemon=True).start()
        c = self._oku()
        if c.get("hata"):
            self.durdur()
            raise RuntimeError(c["hata"])
        self.bilgi = c
        if c.get("cihaz") == "cpu":
            _log("UYARI: Ekran kartı kullanılamıyor, işlemciyle (yavaş) üretilecek.")

    def _stderr(self, p):
        kalan = ""
        while True:
            parca = p.stderr.read1(4096)
            if not parca:
                break
            kalan += parca.decode("utf-8", "replace")
            if "\n" in kalan or "\r" in kalan:
                kes = max(kalan.rfind("\n"), kalan.rfind("\r"))
                _log(kalan[:kes]); kalan = kalan[kes + 1:]

    def _oku(self):
        while True:
            satir = self.p.stdout.readline()
            if not satir:
                raise RuntimeError("Seslendirme motoru beklenmedik şekilde kapandı. Ayrıntı için Kayıtlar'a bak.")
            s = satir.decode("utf-8", "replace").strip()
            if s.startswith("@@"):
                return json.loads(s[2:])
            if s:
                _log(s)

    def istek(self, d):
        self.p.stdin.write((json.dumps(d, ensure_ascii=False) + "\n").encode("utf-8"))
        self.p.stdin.flush()
        c = self._oku()
        self.son = time.time()
        return c

    def durdur(self):
        p, self.p, self.model, self.whisper = self.p, None, None, False
        if p and p.poll() is None:
            try:
                p.stdin.write(b'{"is":"kapat"}\n'); p.stdin.flush()
                p.wait(timeout=5)
            except Exception:  # noqa: BLE001
                _sureci_oldur(p)


ISCI = Isci()


def _bosta_bekci():
    while True:
        time.sleep(60)
        if ISCI.acik() and not IS["calisiyor"] and time.time() - ISCI.son > BOSTA_KAPAT_SN:
            with ISCI.kilit:
                ISCI.durdur()


def arkaplan_baslat():
    threading.Thread(target=_bosta_bekci, daemon=True).start()


# ------------------------------------------------------------------ durum
def durum(kontrol=0, ses_suresi=None, klasor=None, dil=None):
    s = surum()
    son = son_surum(zorla=kontrol == 2) if (kontrol or _GH["son"]) else None
    d = {"kurulu": bool(s), "surum": s, "son": son, "eski_var": os.path.isfile(ortam_py(ESKI)),
         "eski_surum": _json(SURUM_ESKI) if os.path.isfile(ortam_py(ESKI)) else None,
         "guncelleme_var": bool(s and son and son.get("sha") and son["sha"] != s.get("sha")),
         "is": dict(IS, log=IS["log"][-200:]), "isci_acik": ISCI.acik(),
         "ayar": ayarlar(), "modeller": (s or {}).get("modeller") or [], "diller": (s or {}).get("diller") or [],
         "gpu": (s or {}).get("gpu")}
    if ses_suresi:
        d["sesler"] = ses_listesi(ses_suresi)
        d["hazir_ornek"] = os.path.isfile(HAZIR_ORNEK)
        d["sablon_var"] = any(x["tur"] == "sablon" for x in d["sesler"])
    if dil:
        d["secili"], d["secim_kaynak"] = secili_ses(klasor, dil)
    return d


def _is_baslat(tur):
    if IS["calisiyor"]:
        raise ValueError("Chatterbox şu an başka bir iş yapıyor, bitmesini bekle.")
    _DUR["istek"] = False
    IS.update(calisiyor=True, tur=tur, asama="Başlıyor…", yuzde=0, log=[], hata=None, biten=0, toplam=0)


def durdur():
    _DUR["istek"] = True
    _sureci_oldur(_DUR.get("p"))


# ------------------------------------------------------------------ kurulum / güncelleme
def _dogrula(k):
    kod = ("import json,torch,chatterbox.mtl_tts as m;"
           "ms=sorted([x for x in getattr(m,'MULTILINGUAL_T3_MODELS',{}) if x[:1]=='v' and x[1:].isdigit()],key=lambda x:int(x[1:]));"
           "print('@@'+json.dumps({'torch':torch.__version__,'cuda':torch.cuda.is_available(),"
           "'mps':bool(getattr(torch.backends,'mps',None) and torch.backends.mps.is_available()),"
           "'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,"
           "'modeller':ms,'diller':sorted(m.SUPPORTED_LANGUAGES)}))")
    p = subprocess.run([ortam_py(k), "-c", kod], cwd=TTS, env=_env(), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600, creationflags=GIZLI)
    for s in p.stdout.splitlines():
        if s.startswith("@@"):
            return json.loads(s[2:])
    _log(p.stdout + p.stderr)
    return None


def kur_baslat():
    _is_baslat("kurulum")
    threading.Thread(target=_kurulum_isi, daemon=True).start()


def _kurulum_isi():
    guncelleme = kurulu()
    try:
        os.makedirs(TTS, exist_ok=True)
        uv = [sys.executable, "-m", "uv"]
        IS.update(asama="Kurulum aracı (uv) hazırlanıyor…", yuzde=2)
        if _calistir(uv + ["--version"]) != 0:
            if _calistir([sys.executable, "-m", "pip", "install", "--upgrade", "uv"]) != 0:
                raise RuntimeError("Kurulum aracı (uv) kurulamadı. İnternet bağlantını kontrol et.")
        else:
            _calistir([sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "uv"])

        IS.update(asama="Chatterbox'un en son sürümü bulunuyor…", yuzde=5)
        son = son_surum(zorla=True)
        if "sha" not in son:
            raise RuntimeError(son.get("hata", "Son sürüm bulunamadı"))
        perth = _gh(f"/repos/{PERTH}/commits/master")["sha"]
        _log(f"Chatterbox: {son['sha'][:7]} ({son['tarih'][:10]}) – {son['mesaj']}")

        IS.update(asama="Ayrı Python 3.11 ortamı hazırlanıyor…", yuzde=8)
        if not _sil(YENI):
            raise RuntimeError("Eski yarım kalmış kurulum klasörü (tts/env_new) silinemedi. Stüdyoyu kapatıp aç, tekrar dene.")
        if _calistir(uv + ["venv", "--python", "3.11", YENI]) != 0:
            raise RuntimeError("Python 3.11 ortamı oluşturulamadı.")

        ov = os.path.join(TTS, "override.txt")
        with open(ov, "w", encoding="utf-8") as f:   # Perth'i git kurulumu gerektirmeden zip olarak al
            f.write(f"resemble-perth @ https://github.com/{PERTH}/archive/{perth}.zip\n")
        paketler = [f"chatterbox-tts @ https://github.com/{REPO}/archive/{son['sha']}.zip", "setuptools<81"]
        bilgi = None
        for i, secenek in enumerate(TORCH_SECENEK):
            IS.update(asama=("Paketler indirilip kuruluyor" + ((" (ilk kurulumda ~1 GB, 5-15 dk)" if MAC else " (ilk kurulumda ~3 GB, 10-25 dk)") if not guncelleme else "")
                             + f" · PyTorch {secenek}…"), yuzde=15 + i * 5)
            arg = uv + ["pip", "install", "--python", ortam_py(YENI), "--override", ov, "--torch-backend", secenek] + paketler
            if i:
                arg += ["--reinstall-package", "torch", "--reinstall-package", "torchaudio"]
            if _calistir(arg) != 0:
                _log(f"! '{secenek}' ile kurulamadı, başka seçenek deneniyor.")
                continue
            IS.update(asama="Kurulum kontrol ediliyor (ekran kartı testi)…", yuzde=85)
            bilgi = _dogrula(YENI)
            if bilgi and MAC:
                if bilgi.get("mps"):
                    bilgi["gpu"] = "Apple GPU (MPS)"
                else:
                    bilgi["gpu"] = "İşlemci (yavaş)"
                    _log("UYARI: Apple GPU (MPS) kullanılamıyor, sesler işlemciyle (yavaş) üretilecek.")
                break
            if bilgi and bilgi.get("cuda"):
                break
            _log("! Ekran kartı (CUDA) görünmüyor, başka PyTorch derlemesi deneniyor.")
            bilgi = None
        if not bilgi and MAC and platform.machine() == "x86_64":
            raise RuntimeError("Intel işlemcili Mac'lerde Chatterbox'un ihtiyaç duyduğu PyTorch sürümü yok. "
                               "Seslendirmeyi Windows bilgisayarda yap; stüdyonun geri kalanı bu Mac'te çalışır.")
        if not bilgi:
            raise RuntimeError("Kurulum tamamlanamadı. Ayrıntı için Kayıtlar'a bak. Eski sürümün olduğu gibi duruyor."
                               if guncelleme else "Kurulum tamamlanamadı. Ayrıntı için Kayıtlar'a bak.")

        IS.update(asama="Yeni sürüm devreye alınıyor…", yuzde=95)
        with ISCI.kilit:
            ISCI.durdur()
            time.sleep(1)
            if os.path.isdir(ORTAM):
                if not _sil(ESKI):
                    raise RuntimeError("tts/env_old silinemedi. Stüdyoyu kapatıp açınca tekrar dene.")
                os.rename(ORTAM, ESKI)
                if os.path.isfile(SURUM):
                    shutil.copyfile(SURUM, SURUM_ESKI)
            os.rename(YENI, ORTAM)
        _json_yaz(SURUM, {"sha": son["sha"], "tarih": son["tarih"], "mesaj": son["mesaj"], "perth": perth,
                          "torch": bilgi["torch"], "gpu": bilgi["gpu"], "modeller": bilgi["modeller"],
                          "diller": bilgi["diller"], "kurulum": time.strftime("%Y-%m-%dT%H:%M:%S")})
        IS.update(asama=f"Chatterbox {'güncellendi' if guncelleme else 'kuruldu'} ✓ (sürüm {son['tarih'][:10]})", yuzde=100)
    except Durduruldu:
        IS.update(hata="Kurulum durduruldu. Mevcut sürüm (varsa) olduğu gibi duruyor.", asama="Durduruldu")
        _sil(YENI)
    except Exception as e:  # noqa: BLE001
        IS.update(hata=str(e), asama="Hata")
        _log(f"HATA: {e}")
    finally:
        IS["calisiyor"] = False


def geri_al():
    """Son güncellemeyi geri alır (env <-> env_old yer değiştirir; tekrar basınca yeniye döner)."""
    if IS["calisiyor"]:
        raise ValueError("Önce süren işin bitmesini bekle.")
    if not os.path.isfile(ortam_py(ESKI)):
        raise ValueError("Geri dönülecek önceki sürüm yok.")
    with ISCI.kilit:
        ISCI.durdur()
        time.sleep(1)
        gecici = os.path.join(TTS, "env_tmp")
        _sil(gecici)
        os.rename(ORTAM, gecici)
        os.rename(ESKI, ORTAM)
        os.rename(gecici, ESKI)
        a, b = _json(SURUM), _json(SURUM_ESKI)
        if b:
            _json_yaz(SURUM, b)
        if a:
            _json_yaz(SURUM_ESKI, a)
    return surum()


# ------------------------------------------------------------------ Whisper: kontrol ve kelime zamanları
import difflib
import re as _re


def _norm(w, dil):
    if dil == "tr":
        w = w.replace("İ", "i").replace("I", "ı")
    return _re.sub(r"[^\w]", "", w.lower())


def hizala(metin, duyulan, dil):
    """Senaryodaki kelimeleri Whisper'ın duyduğu kelimelerle eşleştirir.
    Döndürür: benzerlik (0-1), eksik (okunmayan kelimeler), fazla (senaryoda olmayan), kelimeler (senaryo kelimeleri + zamanlar)."""
    sw = [w for w in _re.sub(r"\s+", " ", metin or "").strip().split(" ") if w]
    sn = [_norm(w, dil) for w in sw]
    wn = [_norm(k["w"], dil) for k in duyulan]
    if not sw:
        return {"benzerlik": 1.0, "eksik": [], "fazla": [], "kelimeler": duyulan}
    eslesme = {}
    sm = difflib.SequenceMatcher(None, sn, wn, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                eslesme[i1 + k] = j1 + k
        elif op == "replace":    # ek farkları ("kalbi" / "kalbin") benzer sayılır
            for k in range(min(i2 - i1, j2 - j1)):
                if difflib.SequenceMatcher(None, sn[i1 + k], wn[j1 + k]).ratio() >= 0.75:
                    eslesme[i1 + k] = j1 + k
    sayilan = [i for i, w in enumerate(sn) if w and not _re.search(r"\d", w)]   # rakamlar ("%6") okunuşla farklı yazılır
    tutan = [i for i in sayilan if i in eslesme]
    benzerlik = len(tutan) / len(sayilan) if sayilan else 1.0
    kullanilan = set(eslesme.values())
    eksik = [sw[i] for i in sayilan if i not in eslesme]
    fazla = [duyulan[j]["w"] for j in range(len(duyulan)) if j not in kullanilan and len(wn[j]) >= 3]
    # zamanlar: eşleşen kelime Whisper'ın zamanını alır, eşleşmeyenler komşular arasında paylaştırılır
    if not eslesme:
        return {"benzerlik": round(benzerlik, 3), "eksik": eksik, "fazla": fazla, "kelimeler": duyulan}
    zaman = [None] * len(sw)
    for i, j in eslesme.items():
        zaman[i] = [duyulan[j]["bas"], duyulan[j]["son"]]
    toplam = duyulan[-1]["son"] if duyulan else 0
    i = 0
    while i < len(sw):
        if zaman[i] is not None:
            i += 1; continue
        j = i
        while j < len(sw) and zaman[j] is None:
            j += 1
        bas = zaman[i - 1][1] if i > 0 else max(0.0, (zaman[j][0] if j < len(sw) else toplam) - 0.3 * (j - i))
        son = zaman[j][0] if j < len(sw) else max(bas + 0.3 * (j - i), toplam)
        uz = [max(1, len(w)) for w in sw[i:j]]; ad = (son - bas) / sum(uz) if sum(uz) else 0
        t = bas
        for k, u in zip(range(i, j), uz):
            zaman[k] = [round(t, 3), round(t + u * ad, 3)]; t += u * ad
        i = j
    return {"benzerlik": round(benzerlik, 3), "eksik": eksik, "fazla": fazla,
            "kelimeler": [{"w": w, "bas": z[0], "son": z[1]} for w, z in zip(sw, zaman)]}


def kontrol_yolu(ses_yolu):
    return os.path.splitext(ses_yolu)[0] + ".kelimeler.json"


def uretim_yolu(klasor, dil):
    return os.path.join(klasor, "ses", dil, "uretim.json")


def uretim_oku(klasor, dil):
    """Chatterbox'ın hangi sesi hangi metinden ürettiği: {hedef: {"metin", "zaman"}}. Metin sonradan değişirse ses 'eskimiş' sayılır."""
    return _json(uretim_yolu(klasor, dil)) or {}


def kontrol_oku(ses_yolu):
    """Sesin güncel Whisper kontrol sonucu (ses dosyası sonradan değiştiyse None)."""
    k = _json(kontrol_yolu(ses_yolu))
    if not k or abs(k.get("ses_zaman", 0) - os.path.getmtime(ses_yolu)) > 1:
        return None
    return k


def _whisper(ses_yolu, dil, metin):
    """İşçi açıkken çağrılır: sesi yazıya döker, senaryoyla karşılaştırır, sonucu sesin yanına yazar."""
    if not ISCI.whisper:
        IS["asama"] = "Whisper yükleniyor… (ilk seferde ~1,6 GB iner)"
    c = ISCI.istek({"is": "yazi", "ses": ses_yolu, "dil": dil})
    if c.get("hata"):
        raise RuntimeError("Whisper: " + c["hata"])
    ISCI.whisper = True
    h = hizala(metin, c["kelimeler"], dil)
    sonuc = {"ses_zaman": os.path.getmtime(ses_yolu), "dil": dil, "duyulan": c["metin"], "senaryo": metin, **h}
    _json_yaz(kontrol_yolu(ses_yolu), sonuc)
    return sonuc


def kontrol_baslat(klasor, dil, isler):
    """isler: [(ses_yolu, metin, etiket)] — mevcut sesleri Whisper ile kontrol eder."""
    if not kurulu():
        raise ValueError("Whisper, Chatterbox'ın ortamını kullanır: önce Chatterbox'u kur.")
    if not isler:
        raise ValueError("Kontrol edilecek ses yok.")
    _is_baslat("kontrol")
    IS["toplam"] = len(isler)
    threading.Thread(target=_kontrol_isi, args=(dil, isler), daemon=True).start()


def _kontrol_isi(dil, isler):
    try:
        sorunlu = 0
        with ISCI.kilit:
            if not ISCI.acik():
                IS["asama"] = "Motor başlatılıyor…"
                ISCI.baslat()
            for i, (yol, metin, etiket) in enumerate(isler):
                if _DUR["istek"]:
                    raise Durduruldu()
                if ISCI.whisper:
                    IS["asama"] = f"{etiket} dinleniyor ({i + 1}/{len(isler)})…"
                s = _whisper(yol, dil, metin)
                if s["benzerlik"] < KONTROL_ESIK:
                    sorunlu += 1
                _log(f"{'✓' if s['benzerlik'] >= KONTROL_ESIK else '⚠'} {etiket}: %{round(100 * s['benzerlik'])}"
                     + (f" · eksik: {', '.join(s['eksik'][:8])}" if s["eksik"] else ""))
                IS.update(biten=i + 1, yuzde=round(100 * (i + 1) / len(isler)))
        IS["asama"] = "Kontrol bitti ✓ " + (f"{sorunlu} sahnede sorun var" if sorunlu else "hepsi senaryoyla uyuşuyor")
    except Durduruldu:
        IS.update(hata="Kontrol durduruldu.", asama="Durduruldu")
    except Exception as e:  # noqa: BLE001
        IS.update(hata=str(e), asama="Hata")
        _log(f"HATA: {e}")
    finally:
        IS["calisiyor"] = False


# ------------------------------------------------------------------ çeviri
def ceviri_baslat(isler, kaynak, kaydet, dil_ad):
    """isler: [(hedef, tur, anahtar, metin)]; kaydet(hedef, tur, anahtar, ceviri) her sonuçta çağrılır."""
    if not kurulu():
        raise ValueError("Çeviri, Chatterbox'ın ortamını kullanır: önce Chatterbox'u kur.")
    if not isler:
        raise ValueError("Çevrilecek yeni metin yok (hepsi zaten çevrilmiş ya da senaryoda yazılı).")
    _is_baslat("ceviri")
    IS["toplam"] = len(isler)
    threading.Thread(target=_ceviri_isi, args=(isler, kaynak, kaydet, dil_ad), daemon=True).start()


def _ceviri_isi(isler, kaynak, kaydet, dil_ad):
    try:
        model = ayarlar().get("ceviri_model") or None
        with ISCI.kilit:
            if not ISCI.acik():
                IS["asama"] = "Motor başlatılıyor…"
                ISCI.baslat()
            IS["asama"] = "Çeviri modeli yükleniyor… (ilk seferde ~8 GB iner)"
            try:
                for i, (hedef, tur, anahtar, metin) in enumerate(isler):
                    if _DUR["istek"]:
                        raise Durduruldu()
                    c = ISCI.istek({"is": "cevir", "metin": metin, "tur": tur, "model": model,
                                    "kaynak_ad": dil_ad.get(kaynak, kaynak), "hedef_ad": dil_ad.get(hedef, hedef)})
                    ISCI.model, ISCI.whisper = None, False      # çeviri için boşaltıldılar
                    if c.get("hata"):
                        raise RuntimeError("Çeviri: " + c["hata"])
                    kaydet(hedef, tur, anahtar, c["metin"])
                    _log(f"{hedef.upper()} {'sahne ' + anahtar if tur == 'anlatim' else 'yazı'}: {c['metin']}")
                    IS.update(biten=i + 1, yuzde=round(100 * (i + 1) / len(isler)),
                              asama=f"Çevriliyor ({i + 1}/{len(isler)})…")
            finally:
                if ISCI.acik():
                    ISCI.istek({"is": "cevir_bitti"})
        IS["asama"] = f"Çeviri bitti ✓ {len(isler)} metin. Gözden geçirip istersen düzelt."
    except Durduruldu:
        IS.update(hata="Çeviri durduruldu.", asama="Durduruldu")
    except Exception as e:  # noqa: BLE001
        IS.update(hata=str(e), asama="Hata")
        _log(f"HATA: {e}")
    finally:
        IS["calisiyor"] = False


# ------------------------------------------------------------------ ses üretimi
def uret_baslat(klasor, dil, isler):
    ses_id, _ = secili_ses(klasor, dil)
    """isler: [(hedef, metin, etiket)] — hedef '01', '02'... ya da 'tam'."""
    if not kurulu():
        raise ValueError("Chatterbox kurulu değil.")
    diller = (surum() or {}).get("diller") or []
    if diller and dil not in diller:
        raise ValueError(f"Chatterbox '{dil}' dilini desteklemiyor.")
    if not isler:
        raise ValueError("Üretilecek metin yok (sesi olmayan ve metni olan sahne bulunamadı).")
    _is_baslat("uretim")
    IS["toplam"] = len(isler)
    threading.Thread(target=_uretim_isi, args=(klasor, dil, isler, ses_id), daemon=True).start()


def sablon_baslat():
    """Hazır sesin örneğini üretir ve ondan kalın/ince şablon sesler türetir."""
    if not kurulu():
        raise ValueError("Chatterbox kurulu değil.")
    _is_baslat("sablon")
    IS["toplam"] = 1 + len(SABLONLAR)
    threading.Thread(target=_sablon_isi, daemon=True).start()


def _sablon_isi():
    try:
        os.makedirs(SESLER, exist_ok=True)
        with ISCI.kilit:
            if not ISCI.acik():
                IS["asama"] = "Seslendirme motoru başlatılıyor…"
                ISCI.baslat()
            ayar = dict(ayarlar(), duygu=0.5, cfg=0.5, sicaklik=0.7)
            IS["asama"] = "Hazır sesin örneği kaydediliyor…" if ISCI.model == ayar["model"] else "Model yükleniyor…"
            gecici = os.path.join(SESLER, "_hazir_yeni.wav")
            c = ISCI.istek({"is": "uret", "metin": SABLON_METNI, "dil": "en", "cikti": gecici, "ayar": ayar,
                            "referans": None, "referans_zaman": None})
            if c.get("hata"):
                raise RuntimeError(c["hata"])
            ISCI.model = ayar["model"]
            os.replace(gecici, HAZIR_ORNEK)
        IS.update(biten=1, yuzde=40)
        mevcut = {x.get("oran") for x in ses_listesi(lambda y: 0) if x["tur"] == "sablon"}
        for i, (ad, oran) in enumerate(SABLONLAR):
            IS["asama"] = f"Şablon hazırlanıyor: {ad}"
            if oran not in mevcut:
                ses_turet("hazir", oran, ad, tur="sablon")
            IS.update(biten=2 + i, yuzde=40 + round(60 * (i + 1) / len(SABLONLAR)))
        IS["asama"] = "Şablon sesler hazır ✓ Dinleyip beğendiklerine istediğin adı verebilirsin."
    except Exception as e:  # noqa: BLE001
        IS.update(hata=str(e), asama="Hata")
        _log(f"HATA: {e}")
    finally:
        IS["calisiyor"] = False


def _uretim_isi(klasor, dil, isler, ses_id):
    try:
        ayar = ayarlar()
        ref = ses_ornegi(ses_id)
        sa = ses_ayari(ses_id)
        with ISCI.kilit:
            if not ISCI.acik():
                IS["asama"] = "Seslendirme motoru başlatılıyor…"
                ISCI.baslat()
            _log(f"Ses: {next((x['ad'] for x in ses_listesi(lambda y: 0) if x['id'] == ses_id), ses_id)}")
            k = os.path.join(klasor, "ses", dil)
            os.makedirs(k, exist_ok=True)
            for i, (hedef, metin, etiket) in enumerate(isler):
                if _DUR["istek"]:
                    raise Durduruldu()
                if ISCI.model != ayar["model"]:
                    IS["asama"] = "Model yükleniyor… (ilk seferde ~3 GB iner, birkaç dakika sürebilir)"
                else:
                    IS["asama"] = f"{etiket} seslendiriliyor ({i + 1}/{len(isler)})…"
                hedef_yol = os.path.join(k, hedef + ".wav")
                deneme, en_iyi = 0, None
                while True:
                    deneme += 1
                    gecici = os.path.join(k, f"_{hedef}_yeni{deneme}.wav")
                    c = ISCI.istek({"is": "uret", "metin": metin, "dil": dil, "cikti": gecici, "ayar": ayar, "duraklama": sa["duraklama"],
                                    "referans": ref, "referans_zaman": os.path.getmtime(ref) if ref else None})
                    if c.get("hata"):
                        raise RuntimeError(c["hata"])
                    ISCI.model = ayar["model"]
                    if abs(sa["hiz"] - 1) > 0.01:     # tonu bozmadan yavaşlat/hızlandır
                        yavas = gecici[:-4] + "_hiz.wav"
                        _ffmpeg(["-i", gecici, "-filter:a", f"atempo={sa['hiz']:.3f}", "-ar", "24000", yavas])
                        os.replace(yavas, gecici)
                        c["sure"] = round(c["sure"] / sa["hiz"], 2)
                    sonuc = None
                    if ayar.get("otomatik_kontrol", True):
                        try:
                            IS["asama"] = f"{etiket} Whisper ile kontrol ediliyor…" if ISCI.whisper else IS["asama"]
                            sonuc = _whisper(gecici, dil, metin)
                        except Exception as e:  # noqa: BLE001
                            _log(f"Whisper kontrolü yapılamadı: {e}")
                    puan = sonuc["benzerlik"] if sonuc else 1.0
                    if en_iyi is None or puan > en_iyi[0]:
                        if en_iyi:
                            _sil_dosya(en_iyi[1]); _sil_dosya(kontrol_yolu(en_iyi[1]))
                        en_iyi = (puan, gecici, c, sonuc)
                    else:
                        _sil_dosya(gecici); _sil_dosya(kontrol_yolu(gecici))
                    if puan >= KONTROL_ESIK or not ayar.get("otomatik_tekrar", True) or deneme >= 2:
                        break
                    _log(f"⚠ {etiket}: Whisper %{round(100 * puan)} duydu, eksik: {', '.join(sonuc['eksik'][:6])} → bir kez daha üretiliyor")
                    IS["asama"] = f"{etiket} yeniden üretiliyor (kelime atlanmış)…"
                puan, gecici, c, sonuc = en_iyi
                for uz in ANLATIM_UZ:
                    eski = os.path.join(k, hedef + uz)
                    if os.path.isfile(eski):
                        os.remove(eski)
                os.replace(gecici, hedef_yol)
                _sil_dosya(kontrol_yolu(gecici))
                if sonuc:   # kontrol sonucu son dosyanın zamanıyla
                    sonuc["ses_zaman"] = os.path.getmtime(hedef_yol)
                    _json_yaz(kontrol_yolu(hedef_yol), sonuc)
                else:
                    _sil_dosya(kontrol_yolu(hedef_yol))
                kayit = uretim_oku(klasor, dil)
                kayit[hedef] = {"metin": metin, "zaman": os.path.getmtime(hedef_yol)}
                _json_yaz(uretim_yolu(klasor, dil), kayit)
                _log(f"{'✓' if puan >= KONTROL_ESIK else '⚠'} {etiket}: {c['sure']:.1f} sn" + (f" · Whisper %{round(100 * puan)}" if sonuc else ""))
                IS["biten"] = i + 1
                IS["yuzde"] = round(100 * (i + 1) / len(isler))
        IS["asama"] = f"Bitti ✓ {len(isler)} ses üretildi" + (" (işlemciyle)" if ISCI.bilgi.get("cihaz") == "cpu" else "")
    except Durduruldu:
        IS.update(hata=f"Durduruldu ({IS['biten']}/{IS['toplam']} hazır).", asama="Durduruldu")
    except Exception as e:  # noqa: BLE001
        IS.update(hata=str(e), asama="Hata")
        _log(f"HATA: {e}")
    finally:
        IS["calisiyor"] = False
