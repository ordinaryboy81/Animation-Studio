"""Seslendirmeyi sahneye sığdırma: ses sahneden uzunsa önce hafifçe hızlandırır, yetmezse sahneyi uzatır.

Mod (sahne başına, ses/<dil>/sigdir.json):
  otomatik  : en fazla %20 hızlandır, kalan kısım için sahneyi uzat (varsayılan)
  hizlandir : en fazla %40 hızlandır (sahne süresi neredeyse hiç değişmez)
  uzat      : sese dokunma, sahneyi uzat
Ses dosyasının kendisi değişmez; hız videoda (ffmpeg atempo) ve önizlemede (playbackRate) uygulanır.
"""
import json, os

ON_BOSLUK = 0.3        # ses sahne başladıktan 0,3 sn sonra girer
VARSAYILAN_PAY = 0.6   # ön + arka boşluk toplamı
MAKS = {"otomatik": 1.2, "hizlandir": 1.4, "uzat": 1.0}
MODLAR = tuple(MAKS)


def hesapla(ses_sure, sahne_sure, mod="otomatik", pay=VARSAYILAN_PAY):
    """(oran, yeni_sahne_suresi). oran > 1 ise ses o kadar hızlı çalınır."""
    maks = MAKS.get(mod, MAKS["otomatik"])
    yer = max(0.5, sahne_sure - pay)
    oran = 1.0
    if ses_sure > yer and maks > 1:
        oran = round(min(ses_sure / yer, maks), 3)
    return oran, max(sahne_sure, ses_sure / oran + pay)


def yol(klasor, dil):
    return os.path.join(klasor, "ses", dil, "sigdir.json")


def oku(klasor, dil):
    try:
        with open(yol(klasor, dil), encoding="utf-8") as f:
            d = json.load(f)
        return {k: v for k, v in d.items() if v in MODLAR}
    except (OSError, ValueError):
        return {}


def kaydet(klasor, dil, hedef, mod):
    d = oku(klasor, dil)
    if mod == "otomatik":
        d.pop(hedef, None)
    else:
        d[hedef] = mod
    os.makedirs(os.path.dirname(yol(klasor, dil)), exist_ok=True)
    with open(yol(klasor, dil), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
