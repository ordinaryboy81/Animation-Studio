"""Sahne türleri: kart, resim (katmanlı/parallax), harita."""
import json, math, os, random
import numpy as np
from PIL import Image, ImageDraw
from .core import (KOK, renk, sinirla, yumusak, yumusak_iki, yazi_ciz, altyazi_ciz,
                    catmull_rom, cizgi_kismi)


class Sahne:
    def __init__(self, tanim, tv, sure):
        self.d = tanim
        self.tv = tv
        self.sure = sure
        self.giris = tanim.get("giris", "siyah")
        cikis = tanim.get("cikis", "siyah")
        self.cikis = cikis if isinstance(cikis, str) else cikis.get("tur", "siyah")
        self._vinyet = None
        self._parcaciklar = None
        self.hazirla()

    def hazirla(self):
        pass

    def arka(self, t):
        raise NotImplementedError

    # ---- ortak efektler ----
    def vinyet(self, img, guc):
        if self._vinyet is None:
            yy, xx = np.mgrid[0:img.height, 0:img.width].astype(np.float32)
            r = np.sqrt(((xx / img.width) - 0.5) ** 2 + ((yy / img.height) - 0.5) ** 2)
            m = np.clip((r - 0.3) / 0.45, 0, 1) ** 1.6 * 255 * guc
            self._vinyet = Image.fromarray(m.astype(np.uint8), "L")
            self._siyah = Image.new("RGB", img.size, (0, 0, 0))
        return Image.composite(self._siyah, img, self._vinyet)

    def parcacik(self, img, t, ayar):
        tur = ayar if isinstance(ayar, str) else ayar.get("tur", "toz")
        if self._parcaciklar is None:
            rnd = random.Random(7)
            n = 70 if tur == "toz" else 120
            self._parcaciklar = [(rnd.random(), rnd.random(), rnd.uniform(1.5, 4.5), rnd.uniform(0.2, 1.0), rnd.random() * 6.28)
                                 for _ in range(n)]
        c = ImageDraw.Draw(img, "RGBA")
        for x, y, s, v, faz in self._parcaciklar:
            if tur == "kar":
                px = (x + 0.02 * math.sin(t * v + faz)) % 1; py = (y + t * 0.05 * v) % 1; a = 200
            else:  # toz: yavaşça süzülen ışık zerreleri
                px = (x + t * 0.008 * v) % 1; py = (y - t * 0.012 * v + 0.01 * math.sin(t + faz)) % 1
                a = int(110 * (0.5 + 0.5 * math.sin(t * 1.5 * v + faz)))
            r = self.tv.b(s)
            X, Y = px * img.width, py * img.height
            c.ellipse([X - r, Y - r, X + r, Y + r], fill=(255, 240, 210, a))

    def kare(self, t):
        img = self.arka(t)
        if self.d.get("parcacik"):
            self.parcacik(img, t, self.d["parcacik"])
        if self.d.get("vinyet"):
            img = self.vinyet(img, float(self.d["vinyet"]) if not isinstance(self.d["vinyet"], bool) else 0.7)
        for oge in self.d.get("yazilar", []):
            yazi_ciz(self.tv, img, oge, t, self.sure)
        altyazi_ciz(self.tv, img, self.tv.metin(self.d.get("altyazi")), t, self.sure, self.tv.tema)
        img = self.gecis(img, t)
        if self.tv.ss != 1:
            img = img.resize((self.tv.W, self.tv.H), Image.LANCZOS)
        return img

    def gecis(self, img, t):
        def ort(renk_, a):
            return Image.blend(img, Image.new("RGB", img.size, renk_), sinirla(a))
        g = {"siyah": (0, 0, 0), "beyaz": (255, 255, 255)}
        if self.giris in g and t < 0.45:
            img = ort(g[self.giris], 1 - yumusak(t / 0.45))
        kalan = self.sure - t
        if self.cikis in g and kalan < 0.4:
            img = ort(g[self.cikis], 1 - kalan / 0.4)
        return img


# ---------------------------------------------------------------- KART
class KartSahne(Sahne):
    """Düz renk / renk geçişli arka plan üzerine yazılar. Başlık, alıntı, kapanış kartı için."""

    def hazirla(self):
        tv = self.tv
        arka = self.d.get("arka_plan", tv.tema.get("kart_arka", ["#141c2e", "#2a1f3d"]))
        if isinstance(arka, list):
            a, b = np.array(renk(arka[0])[:3], np.float32), np.array(renk(arka[1])[:3], np.float32)
            r = np.linspace(0, 1, tv.ch, dtype=np.float32)[:, None, None]
            g = a + (b - a) * r
            self.zemin = Image.fromarray(np.broadcast_to(g, (tv.ch, tv.cw, 3)).astype(np.uint8))
        else:
            self.zemin = tv.yeni(arka)

    def arka(self, t):
        return self.zemin.copy()


# ---------------------------------------------------------------- RESİM (katmanlı)
class ResimSahne(Sahne):
    """Bir veya birden çok resim katmanı. Kamera yavaşça yakınlaşır/kayar; katmanlar derinliğe göre
    farklı hızda hareket eder (2.5D parallax). Katmanlar şeffaf PNG olabilir."""

    def hazirla(self):
        self.katmanlar = []
        for k in self.d.get("katmanlar", []):
            if isinstance(k, str):
                k = {"dosya": k}
            im = Image.open(self.tv.dosya(k["dosya"])).convert("RGBA")
            self.katmanlar.append((k, im))
        kam = self.d.get("kamera", {})
        self.zoom = kam.get("zoom", [1.0, 1.1])
        self.kay = kam.get("kay", [[0, 0], [0, 0]])

    def arka(self, t):
        tv = self.tv
        r = yumusak_iki(t / self.sure)
        z = self.zoom[0] + (self.zoom[1] - self.zoom[0]) * r
        px = self.kay[0][0] + (self.kay[1][0] - self.kay[0][0]) * r
        py = self.kay[0][1] + (self.kay[1][1] - self.kay[0][1]) * r
        tuval = Image.new("RGBA", (tv.cw, tv.ch), renk(self.d.get("arka_plan", "#000000")))
        for k, im in self.katmanlar:
            der = k.get("derinlik", 0.5)
            zl = 1 + (z - 1) * (0.3 + 0.9 * der)
            ox, oy = px * tv.cw * (0.3 + der), py * tv.ch * (0.3 + der)
            if k.get("mod", "kapla") == "kapla":
                sw, sh = im.size
                s = max(tv.cw / sw, tv.ch / sh) * 1.12 * zl
                bw, bh = tv.cw / s, tv.ch / s
                cx = sinirla(sw / 2 - ox / s, bw / 2, sw - bw / 2)
                cy = sinirla(sh / 2 - oy / s, bh / 2, sh - bh / 2)
                parca = im.resize((tv.cw, tv.ch), Image.BILINEAR, box=(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2))
                tuval.alpha_composite(parca)
            else:  # nesne: belirli bir konumda, belirli yükseklikte
                h = k.get("yukseklik", 0.4) * tv.ch * zl
                w = h * im.width / im.height
                x = tv.cw / 2 + (k.get("x", 0.5) * tv.cw - tv.cw / 2) * zl + ox
                y = tv.ch / 2 + (k.get("y", 0.7) * tv.ch - tv.ch / 2) * zl + oy
                y += math.sin(t * 2) * tv.b(k.get("salinim", 0))
                gir = k.get("bas", None)
                if gir is not None:   # sahneye kayarak girer
                    a = yumusak((t - gir) / 0.8)
                    if a <= 0:
                        continue
                    x += (1 - a) * tv.cw * k.get("giris_yonu", -1)
                parca = im.resize((max(1, int(w)), max(1, int(h))), Image.BILINEAR)
                tuval.alpha_composite(parca, (int(x - w / 2), int(y - h / 2)))
        return tuval.convert("RGB")


# ---------------------------------------------------------------- HARİTA
_DUNYA = None
def dunya():
    global _DUNYA
    if _DUNYA is None:
        veri = json.load(open(os.path.join(KOK, "data", "world.json"), encoding="utf-8"))
        for u in veri:
            u["np"] = []
            mins, maxs = [], []
            for h in u["halkalar"]:
                a = np.array(h, np.float64)
                a[:, 1] = merc(a[:, 1])
                u["np"].append(a); mins.append(a.min(0)); maxs.append(a.max(0))
            u["kutu"] = (np.min(mins, 0), np.max(maxs, 0))
        _DUNYA = veri
    return _DUNYA

def merc(lat):
    lat = np.clip(lat, -85, 85)
    return np.degrees(np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)))


class HaritaSahne(Sahne):
    """Gerçek dünya haritası. Kamera hareketi, ülke vurgulama, noktalar, animasyonlu rotalar,
    etiketler ve sona 'yakınlaşarak geçiş' (imza hareketi)."""

    def hazirla(self):
        dunya()
        kam = self.d.get("kamera", [{"t": 0, "merkez": [30, 35], "genislik": 40}])
        self.kam = kam if isinstance(kam, list) else [dict(kam, t=0)]
        c = self.d.get("cikis", "siyah")
        self.zoom_gecis = c if isinstance(c, dict) and c.get("tur") == "zoom" else None
        if self.zoom_gecis:
            self.cikis = "yok"
        self.rotalar = []
        for r in self.d.get("rotalar", []):
            pts = [(p[0], float(merc(p[1]))) for p in r["noktalar"]]
            self.rotalar.append((r, catmull_rom(pts, 20) if r.get("yumusak", True) else pts))
        self._onbellek = (None, None)

    def kamera(self, t):
        k = self.kam
        if t <= k[0]["t"] or len(k) == 1:
            a = b = k[0]; r = 0
        elif t >= k[-1]["t"]:
            a = b = k[-1]; r = 0
        else:
            i = max(j for j in range(len(k)) if k[j]["t"] <= t)
            a, b = k[i], k[i + 1]
            r = yumusak_iki((t - a["t"]) / (b["t"] - a["t"]))
        lon = a["merkez"][0] + (b["merkez"][0] - a["merkez"][0]) * r
        my = float(merc(a["merkez"][1])) + (float(merc(b["merkez"][1])) - float(merc(a["merkez"][1]))) * r
        gen = a["genislik"] * (b["genislik"] / a["genislik"]) ** r
        if self.zoom_gecis:
            zs = self.zoom_gecis.get("sure", 0.9)
            if t > self.sure - zs:
                q = sinirla((t - (self.sure - zs)) / zs) ** 2
                h = self.zoom_gecis["hedef"]
                lon += (h[0] - lon) * min(1, q * 3)
                my += (float(merc(h[1])) - my) * min(1, q * 3)
                gen *= 0.02 ** q
        return lon, my, gen

    def yansit(self, a, kam):
        lon, my, gen = kam
        k = min(self.tv.cw, self.tv.ch) / gen
        x = self.tv.cw / 2 + (a[..., 0] - lon) * k
        y = self.tv.ch / 2 - (a[..., 1] - my) * k
        return x, y, k

    def xy(self, lon, lat, kam):
        x, y, _ = self.yansit(np.array([lon, float(merc(lat))]), kam)
        return float(x), float(y)

    def zemin(self, kam):
        anahtar = tuple(round(v, 4) for v in kam)
        if self._onbellek[0] == anahtar:
            return self._onbellek[1].copy()
        tv, tema = self.tv, self.tv.tema
        img = tv.yeni(tema.get("deniz", "#10203a"))
        c = ImageDraw.Draw(img, "RGBA")
        lon, my, gen = kam
        k = min(tv.cw, tv.ch) / gen
        yx, yy = tv.cw / 2 / k, tv.ch / 2 / k
        # enlem/boylam çizgileri
        if self.d.get("izgara", True):
            adim = 10 if gen > 25 else (5 if gen > 8 else 1)
            for L in range(int((lon - yx) // adim * adim), int(lon + yx) + adim, adim):
                x = tv.cw / 2 + (L - lon) * k
                c.line([(x, 0), (x, tv.ch)], fill=(255, 255, 255, 14), width=max(1, int(tv.b(1.5))))
            for B in range(-80, 85, adim):
                m = float(merc(B)); y = tv.ch / 2 - (m - my) * k
                if 0 <= y <= tv.ch:
                    c.line([(0, y), (tv.cw, y)], fill=(255, 255, 255, 14), width=max(1, int(tv.b(1.5))))
        kara, sinir = tema.get("kara", "#2c4060"), tema.get("sinir", "#50709a")
        kalinlik = max(1, int(tv.b(2.2)))
        for u in dunya():
            mn, mx = u["kutu"]
            if mx[0] < lon - yx * 1.1 or mn[0] > lon + yx * 1.1 or mx[1] < my - yy * 1.1 or mn[1] > my + yy * 1.1:
                continue
            for a in u["np"]:
                x, y, _ = self.yansit(a, kam)
                pts = list(zip(x.tolist(), y.tolist()))
                if len(pts) > 2:
                    c.polygon(pts, fill=renk(kara), outline=renk(sinir), width=kalinlik)
        self._onbellek = (anahtar, img)
        return img.copy()

    def arka(self, t):
        tv, tema = self.tv, self.tv.tema
        kam = self.kamera(t)
        img = self.zemin(kam)
        c = ImageDraw.Draw(img, "RGBA")
        vurgu_renk = tema.get("vurgu", "#f2b64a")

        # ülke vurgulama
        for v in self.d.get("vurgula", []):
            v = {"ad": v} if isinstance(v, str) else v
            a = yumusak((t - v.get("bas", 0)) / 0.6)
            if a <= 0:
                continue
            for u in dunya():
                if u["ad"] == v["ad"] or v["ad"] in u["adlar"].values():
                    for halka in u["np"]:
                        x, y, _ = self.yansit(halka, kam)
                        c.polygon(list(zip(x.tolist(), y.tolist())), fill=renk(v.get("renk", vurgu_renk), 0.55 * a))

        # ülke adları (haritanın kendi verisinden, seçilen dilde)
        for ad in self.d.get("ulke_adlari", []):
            for u in dunya():
                if u["ad"] == ad:
                    x, y = self.xy(u["etiket"][0], u["etiket"][1], kam)
                    yazi = u["adlar"].get(tv.dil) or u["adlar"].get("en") or ad
                    c.text((x, y), yazi.upper(), font=tv.font("normal", 26), fill=(200, 215, 235, 150), anchor="mm")

        # serbest etiketler (denizler, bölgeler)
        for e in self.d.get("etiketler", []):
            a = yumusak((t - e.get("bas", 0)) / 0.6)
            if a <= 0:
                continue
            x, y = self.xy(e["konum"][0], e["konum"][1], kam)
            c.text((x, y), tv.metin(e["metin"]), font=tv.font(e.get("font", "serif"), e.get("boyut", 30)),
                   fill=renk(e.get("renk", "#88a6cc"), a), anchor="mm")

        # rotalar
        for r, pts in self.rotalar:
            oran = yumusak_iki((t - r.get("bas", 0.5)) / r.get("sure", 3))
            if oran <= 0:
                continue
            a = np.array(pts)
            x, y, _ = self.yansit(a, kam)
            ekran = list(zip(x.tolist(), y.tolist()))
            parca = cizgi_kismi(ekran, oran)
            g = max(2, int(tv.b(r.get("kalinlik", 8))))
            rr = renk(r.get("renk", vurgu_renk))
            if len(parca) > 1:
                c.line(parca, fill=rr, width=g, joint="curve")
            if oran < 1 and r.get("bas_isareti", True):
                hx, hy = parca[-1]
                for R, al in ((tv.b(24), 70), (tv.b(11), 255)):
                    c.ellipse([hx - R, hy - R, hx + R, hy + R], fill=rr[:3] + (al,) if al < 255 else (255, 240, 205, 255))

        # noktalar
        for n in self.d.get("noktalar", []):
            a = yumusak((t - n.get("bas", 0)) / 0.5)
            if a <= 0:
                continue
            x, y = self.xy(n["konum"][0], n["konum"][1], kam)
            rr = renk(n.get("renk", tema.get("nokta", "#e85c48")))
            R = tv.b(n.get("boyut", 16)) * a
            if n.get("nabiz"):
                for i in range(3):
                    f = ((t - n.get("bas", 0)) * 0.8 + i / 3) % 1
                    RR = R + tv.b(60) * f
                    c.ellipse([x - RR, y - RR, x + RR, y + RR], outline=rr[:3] + (int(200 * (1 - f) * a),), width=max(1, int(tv.b(3.5))))
            c.ellipse([x - R, y - R, x + R, y + R], fill=rr, outline=(255, 255, 255, int(220 * a)), width=max(1, int(tv.b(3))))
            if n.get("etiket"):
                yon = n.get("etiket_yonu", "sag")
                off = tv.b(n.get("boyut", 16) + 18)
                dx, dy, anc = {"sag": (off, 0, "lm"), "sol": (-off, 0, "rm"), "ust": (0, -off, "mb"), "alt": (0, off, "mt")}[yon]
                f = tv.font("kalin", n.get("etiket_boyutu", 44))
                o = tv.b(2.5)
                c.text((x + dx + o, y + dy + o), tv.metin(n["etiket"]), font=f, fill=(0, 0, 0, int(150 * a)), anchor=anc)
                c.text((x + dx, y + dy), tv.metin(n["etiket"]), font=f, fill=(255, 255, 255, int(255 * a)), anchor=anc)

        return img

    def gecis(self, img, t):
        img = super().gecis(img, t)
        # yakınlaşma geçişinin beyaz parlaması (yazıların da üstünde)
        if self.zoom_gecis:
            zs = self.zoom_gecis.get("sure", 0.9)
            q = sinirla((t - (self.sure - zs * 0.6)) / (zs * 0.6))
            if q > 0:
                img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), q ** 1.5)
        return img


TURLER = {"kart": KartSahne, "resim": ResimSahne, "harita": HaritaSahne}
