"""Ortak yardımcılar: tuval, fontlar, yumuşatma (easing), renk ve yazı çizimi."""
import math, os
from PIL import Image, ImageDraw, ImageFont, ImageColor

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DOSYALARI = {
    "kalin": "DejaVuSans-Bold.ttf",
    "normal": "DejaVuSans.ttf",
    "serif": "DejaVuSerif.ttf",
    "serif-kalin": "DejaVuSerif-Bold.ttf",
}


# ---------- yumuşatma fonksiyonları ----------
def sinirla(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def yumusak(x):          # hızlı başlar, yavaşça durur
    x = sinirla(x); return 1 - (1 - x) ** 3

def yumusak_iki(x):      # yavaş başlar, yavaş biter
    x = sinirla(x); return 3 * x * x - 2 * x * x * x

def renk(c, alfa=1.0):
    """'#ffcc00' veya [255,204,0] -> (r,g,b,a)"""
    if isinstance(c, (list, tuple)):
        rgb = tuple(int(v) for v in c[:3])
    else:
        rgb = ImageColor.getrgb(c)[:3]
    return rgb + (int(255 * sinirla(alfa)),)


class Tuval:
    """Bir sahnenin çizim bağlamı. Konumlar 0-1 arası oran, boyutlar 'birim' cinsinden.
    1 birim = kısa kenarın binde biri (dikey ve yatay formatta aynı görünüm için)."""

    def __init__(self, W, H, ss, dil, proje_klasoru, tema):
        self.W, self.H, self.ss = W, H, ss
        self.cw, self.ch = W * ss, H * ss
        self.birim = min(W, H) / 1000 * ss
        self.dil = dil
        self.proje = proje_klasoru
        self.tema = tema
        self._fontlar = {}

    def font(self, tur, boyut):
        anahtar = (tur, int(boyut * self.birim))
        if anahtar not in self._fontlar:
            yol = os.path.join(KOK, "fonts", FONT_DOSYALARI.get(tur, FONT_DOSYALARI["kalin"]))
            self._fontlar[anahtar] = ImageFont.truetype(yol, max(4, anahtar[1]))
        return self._fontlar[anahtar]

    def b(self, v):           # birim -> piksel
        return v * self.birim

    def nokta(self, x, y):    # oran -> piksel
        return (x * self.cw, y * self.ch)

    def metin(self, v):
        """Çok dilli metin: {'tr': '...', 'en': '...'} veya düz yazı."""
        if v is None:
            return ""
        if isinstance(v, dict):
            return str(v.get(self.dil) or v.get("en") or next(iter(v.values())))
        return str(v)

    def dosya(self, ad):
        return ad if os.path.isabs(ad) else os.path.join(self.proje, ad)

    def yeni(self, arka="#000000"):
        return Image.new("RGB", (self.cw, self.ch), renk(arka)[:3])


def satirlara_bol(cizim, yazi, font, max_gen):
    satirlar = []
    for paragraf in yazi.split("\n"):
        kelimeler, cur = paragraf.split(), ""
        for k in kelimeler:
            dene = (cur + " " + k).strip()
            if cizim.textlength(dene, font=font) > max_gen and cur:
                satirlar.append(cur); cur = k
            else:
                cur = dene
        satirlar.append(cur)
    return satirlar


def yazi_ciz(tv, img, oge, t, sahne_suresi):
    """Bir yazı öğesini çizer. Öğe alanları (hepsi isteğe bağlı, 'metin' hariç):
    metin, x, y, boyut, renk, font, hiza (orta/sol/sag), genislik, bas, bit,
    animasyon (solma/yukari/yazma/buyume), kutu (renk), golge (true/false), sayac [bas, bit]"""
    bas = oge.get("bas", 0.0)
    bit = oge.get("bit", sahne_suresi)
    if t < bas or t > bit:
        return
    anim = oge.get("animasyon", "yukari")
    gir = yumusak((t - bas) / 0.5)
    cik = yumusak((bit - t) / 0.4) if bit < sahne_suresi - 0.01 else 1.0
    alfa = min(gir, cik) if anim != "yok" else 1.0

    if "sayac" in oge:
        a, z = oge["sayac"]
        sure = oge.get("sayac_suresi", max(0.1, bit - bas))
        deger = a + (z - a) * yumusak_iki((t - bas) / sure)
        yazi = tv.metin(oge.get("metin", "{}")).replace("{}", str(int(round(deger)))) if "metin" in oge else str(int(round(deger)))
    else:
        yazi = tv.metin(oge.get("metin"))
    if not yazi:
        return

    boyut = oge.get("boyut", 60)
    if anim == "buyume":
        boyut *= 0.7 + 0.3 * gir
    elif anim == "zipla":
        x_ = sinirla((t - bas) / 0.5); c1 = 1.9
        boyut *= max(0.05, 1 + (c1 + 1) * (x_ - 1) ** 3 + c1 * (x_ - 1) ** 2)
        alfa = min(1.0, (t - bas) / 0.12) * cik
    font = tv.font(oge.get("font", "kalin"), boyut)
    c = ImageDraw.Draw(img, "RGBA")
    max_gen = oge.get("genislik", 0.86) * tv.cw
    satirlar = satirlara_bol(c, yazi, font, max_gen)

    if anim == "yazma":   # daktilo efekti
        toplam = sum(len(s) for s in satirlar)
        hiz = oge.get("yazma_hizi", 28)  # saniyede harf
        kalan = int((t - bas) * hiz)
        yeni = []
        for s in satirlar:
            yeni.append(s[:max(0, kalan)]); kalan -= len(s)
        satirlar = yeni
        alfa = cik

    satir_yuk = tv.b(boyut) * oge.get("satir_araligi", 1.25)
    x, y = tv.nokta(oge.get("x", 0.5), oge.get("y", 0.5))
    if anim == "yukari":
        y += (1 - gir) * tv.b(40)
    hiza = oge.get("hiza", "orta")
    anchor = {"orta": "mm", "sol": "lm", "sag": "rm"}[hiza]
    toplam_yuk = satir_yuk * len(satirlar)
    y0 = y - toplam_yuk / 2 + satir_yuk / 2

    if oge.get("kutu"):
        genis = max((c.textlength(s, font=font) for s in satirlar), default=0)
        pad = tv.b(boyut * 0.45)
        if hiza == "orta":
            x0, x1 = x - genis / 2 - pad, x + genis / 2 + pad
        elif hiza == "sol":
            x0, x1 = x - pad, x + genis + pad
        else:
            x0, x1 = x - genis - pad, x + pad
        kutu_alfa = oge.get("kutu_saydamlik", 0.65)
        c.rounded_rectangle([x0, y0 - satir_yuk / 2 - pad * 0.5, x1, y0 + toplam_yuk - satir_yuk / 2 + pad * 0.5],
                            radius=pad, fill=renk(oge["kutu"], kutu_alfa * alfa))

    yazi_renk = renk(oge.get("renk", "#ffffff"), alfa)
    golge = oge.get("golge", True)
    if anim == "kelime":   # kelimeler sırayla, hafif yukarı kayarak belirir
        gecikme = oge.get("kelime_araligi", 0.09)
        bosluk = c.textlength(" ", font=font)
        sira = 0
        for i, s in enumerate(satirlar):
            yy = y0 + i * satir_yuk
            kelimeler = s.split()
            genis = c.textlength(s, font=font)
            xx = x - genis / 2 if hiza == "orta" else (x if hiza == "sol" else x - genis)
            for k in kelimeler:
                a = yumusak((t - bas - sira * gecikme) / 0.3) * cik
                sira += 1
                if a > 0:
                    dy = (1 - a) * tv.b(30)
                    if golge:
                        o = max(1, tv.b(boyut * 0.05))
                        c.text((xx + o, yy + dy + o), k, font=font, fill=(0, 0, 0, int(140 * a)), anchor="lm")
                    c.text((xx, yy + dy), k, font=font, fill=renk(oge.get("renk", "#ffffff"), a), anchor="lm")
                xx += c.textlength(k, font=font) + bosluk
        return
    for i, s in enumerate(satirlar):
        yy = y0 + i * satir_yuk
        if golge:
            o = max(1, tv.b(boyut * 0.05))
            c.text((x + o, yy + o), s, font=font, fill=(0, 0, 0, int(140 * alfa)), anchor=anchor)
        c.text((x, yy), s, font=font, fill=yazi_renk, anchor=anchor)


def altyazi_ciz(tv, img, metin, t, sure, tema):
    if not metin:
        return
    yazi_ciz(tv, img, {
        "metin": metin, "x": 0.5, "y": tema.get("altyazi_y", 0.86), "boyut": tema.get("altyazi_boyut", 40),
        "font": "normal", "kutu": "#000000", "kutu_saydamlik": 0.6, "genislik": 0.8,
        "bas": 0.3, "animasyon": "solma", "golge": False,
    }, t, sure)


def catmull_rom(noktalar, n=16):
    if len(noktalar) < 3:
        return list(noktalar)
    P = [noktalar[0]] + list(noktalar) + [noktalar[-1]]
    sonuc = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n; t2, t3 = t * t, t * t * t
            sonuc.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                      + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    sonuc.append(tuple(noktalar[-1]))
    return sonuc


def cizgi_kismi(noktalar, oran):
    """Bir çizginin ilk 'oran' kadarını döndürür (rota çizme animasyonu için)."""
    if oran <= 0 or len(noktalar) < 2:
        return noktalar[:1]
    parcalar = [math.dist(noktalar[i], noktalar[i + 1]) for i in range(len(noktalar) - 1)]
    hedef = sum(parcalar) * sinirla(oran)
    sonuc = [noktalar[0]]
    for i, L in enumerate(parcalar):
        if hedef >= L:
            sonuc.append(noktalar[i + 1]); hedef -= L
        else:
            a, b = noktalar[i], noktalar[i + 1]; r = hedef / L if L else 0
            sonuc.append((a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r)); break
    return sonuc
