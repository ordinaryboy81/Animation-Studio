"""Çizgi film sahnesi: karakterler (PNG) zıplayarak girer, nefes alır, sallanır, göz kırpar,
bir yol boyunca hareket eder; kamera yakınlaşır/kayar."""
import math
from PIL import Image, ImageOps
import numpy as np
from .core import renk, sinirla, yumusak, yumusak_iki
from .scenes import Sahne


def geri_firlama(x):
    """Hedefi biraz aşıp geri gelen yumuşatma (zıplama hissi)."""
    x = sinirla(x); c1 = 1.9; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ara_deger(kf, t, varsayilan):
    """Anahtar kareler: [[t, a, b...], ...] -> t anındaki değerler."""
    if not kf:
        return list(varsayilan)
    if t <= kf[0][0]:
        return list(kf[0][1:])
    if t >= kf[-1][0]:
        return list(kf[-1][1:])
    for a, b in zip(kf, kf[1:]):
        if a[0] <= t <= b[0]:
            r = yumusak_iki((t - a[0]) / (b[0] - a[0])) if b[0] > a[0] else 1
            return [a[i] + (b[i] - a[i]) * r for i in range(1, len(a))]
    return list(kf[-1][1:])


class CizgiSahne(Sahne):
    def hazirla(self):
        tv = self.tv
        self._resimler = {}
        arka = self.d.get("arka_plan", ["#0d1430", "#1d2452"])
        if isinstance(arka, str) and arka.lower().endswith((".png", ".jpg", ".jpeg")):
            self.zemin_resim = self.yukle(arka).convert("RGB")
            self.zemin = None
        else:
            self.zemin_resim = None
            if isinstance(arka, list):
                a, b = np.array(renk(arka[0])[:3], np.float32), np.array(renk(arka[1])[:3], np.float32)
                r = np.linspace(0, 1, tv.ch, dtype=np.float32)[:, None, None]
                self.zemin = Image.fromarray(np.broadcast_to(a + (b - a) * r, (tv.ch, tv.cw, 3)).astype(np.uint8))
            else:
                self.zemin = tv.yeni(arka)
        self.ogeler = []
        for i, o in enumerate(self.d.get("ogeler", [])):
            im = self.yukle(o["dosya"])
            kirp = self.yukle(o["kirp"]) if o.get("kirp") else None
            if o.get("ayna"):
                im = ImageOps.mirror(im)
                kirp = ImageOps.mirror(kirp) if kirp else None
            self.ogeler.append((o, im, kirp, o.get("faz", i * 1.37)))
        kam = self.d.get("kamera", [])
        self.kam = [[k["t"], k.get("zoom", 1.0), k.get("merkez", [0.5, 0.5])[0], k.get("merkez", [0.5, 0.5])[1]]
                    for k in kam] if kam else [[0, 1.0, 0.5, 0.5]]

    def yukle(self, ad):
        if ad not in self._resimler:
            self._resimler[ad] = Image.open(self.tv.dosya(ad)).convert("RGBA")
        return self._resimler[ad]

    def kamera(self, t):
        z, mx, my = ara_deger(self.kam, t, [1.0, 0.5, 0.5])
        return z, mx, my

    def arka(self, t):
        tv = self.tv
        z, mx, my = self.kamera(t)
        if self.zemin_resim is not None:   # arka resim kameraya daha az tepki verir (derinlik)
            zb = 1 + (z - 1) * 0.5
            sw, sh = self.zemin_resim.size
            s = max(tv.cw / sw, tv.ch / sh) * zb
            bw, bh = tv.cw / s, tv.ch / s
            cx = sinirla(sw * (0.5 + (mx - 0.5) * 0.5), bw / 2, sw - bw / 2)
            cy = sinirla(sh * (0.5 + (my - 0.5) * 0.5), bh / 2, sh - bh / 2)
            tuval = self.zemin_resim.resize((tv.cw, tv.ch), Image.BILINEAR,
                                            box=(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)).convert("RGBA")
        else:
            tuval = self.zemin.convert("RGBA")
        for o, im, kirp, faz in self.ogeler:
            self.oge_ciz(tuval, o, im, kirp, faz, t, z, mx, my)
        return tuval.convert("RGB")

    def oge_ciz(self, tuval, o, im, kirp, faz, t, z, mx, my):
        tv = self.tv
        bas = o.get("bas", 0.0)
        if t < bas:
            return
        x, y = ara_deger(o.get("yol"), t, [o.get("x", 0.5), o.get("y", 0.5)])
        olcek = ara_deger(o.get("olcek"), t, [1.0])[0] if isinstance(o.get("olcek"), list) else o.get("olcek", 1.0)
        aci = ara_deger(o.get("donme"), t, [o.get("aci", 0)])[0]
        alfa = o.get("saydamlik", 1.0)
        ox = oy = 0.0
        sx = sy = 1.0

        # giriş
        g = o.get("giris", "zipla")
        gs = o.get("giris_suresi", 0.55)
        gt = (t - bas) / gs
        if gt < 1:
            if g == "zipla":
                olcek *= max(0.0, geri_firlama(gt))
            elif g == "solma":
                alfa *= yumusak(gt)
            elif g.startswith("kay"):
                k = 1 - yumusak(gt)
                yon = g.split("_")[-1]
                ox += {"sol": -0.7, "sag": 0.7}.get(yon, 0) * k
                oy += {"ust": -0.6, "alt": 0.6}.get(yon, 0) * k
            elif g == "buyu":
                olcek *= yumusak(gt)

        # çıkış
        c = o.get("cikis")
        if c and t >= c["t"]:
            ct = (t - c["t"]) / c.get("sure", 0.4)
            if ct >= 1:
                return
            tur = c.get("tur", "kucul")
            if tur == "kucul":
                olcek *= 1 - yumusak_iki(ct)
            elif tur == "solma":
                alfa *= 1 - ct
            elif tur.startswith("kay"):
                yon = tur.split("_")[-1]
                k = ct * ct
                ox += {"sol": -0.8, "sag": 0.8}.get(yon, 0) * k
                oy += {"ust": -0.7, "alt": 0.7}.get(yon, 0) * k

        # bekleme (canlılık) hareketleri — birden fazla olabilir: "nefes salla"
        for b in str(o.get("bekleme", "nefes")).split():
            if b == "nefes":
                k = math.sin(t * 2.6 + faz)
                sy *= 1 + 0.035 * k; sx *= 1 - 0.018 * k
            elif b == "salla":
                aci += o.get("salla_aci", 5) * math.sin(t * 2.1 + faz)
            elif b == "zipla":
                oy -= 0.014 * abs(math.sin(t * 4.2 + faz))
            elif b == "titre":
                ox += 0.003 * math.sin(t * 57 + faz); oy += 0.003 * math.cos(t * 49 + faz)
            elif b == "nabiz":
                k = 1 + o.get("nabiz_gucu", 0.1) * math.sin(t * 6 + faz)
                sx *= k; sy *= k
            elif b == "don":
                aci += t * o.get("donme_hizi", 90)
            elif b == "suz":
                oy += 0.008 * math.sin(t * 1.4 + faz); ox += 0.005 * math.cos(t * 1.1 + faz)

        sprite = im
        if kirp is not None and ((t + faz) % 3.1) < 0.12:
            sprite = kirp

        H = o.get("boyut", 0.3) * tv.ch * olcek * z * sy
        W = H * im.width / im.height * sx / sy
        if W < 2 or H < 2:
            return
        spr = sprite.resize((int(W), int(H)), Image.BILINEAR)
        if abs(aci) > 0.05:
            spr = spr.rotate(aci, resample=Image.BICUBIC, expand=True)
        if alfa < 0.999:
            a = spr.getchannel("A").point(lambda v: int(v * sinirla(alfa)))
            spr.putalpha(a)
        px = ((x + ox - mx) * z + 0.5) * tv.cw
        py = ((y + oy - my) * z + 0.5) * tv.ch
        if o.get("capa") == "alt":
            py -= o.get("boyut", 0.3) * tv.ch * olcek * z / 2
        yapistir(tuval, spr, int(px - spr.width / 2), int(py - spr.height / 2))


def yapistir(tuval, spr, x, y):
    """Ekran dışına taşan kısımları kırparak saydam yapıştırır."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(tuval.width, x + spr.width), min(tuval.height, y + spr.height)
    if x1 <= x0 or y1 <= y0:
        return
    tuval.alpha_composite(spr.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))
