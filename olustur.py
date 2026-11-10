"""
Animasyon Şablonu - video oluşturucu

Kullanım örnekleri:
  python olustur.py projeler/kahve/video.yaml                 # ilk dilde, dikey (Shorts/Reels)
  python olustur.py projeler/kahve/video.yaml --dil pl        # Lehçe
  python olustur.py projeler/kahve/video.yaml --dil hepsi     # tüm dillerde ayrı videolar
  python olustur.py projeler/kahve/video.yaml --format yatay  # YouTube uzun video formatı (16:9)
  python olustur.py projeler/kahve/video.yaml --kare 5.5      # 5.5. saniyenin resmini çıkar (hızlı kontrol)
  python olustur.py projeler/kahve/video.yaml --taslak        # daha hızlı, düşük kalite deneme
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from multiprocessing import Pool

import yaml

from motor.temel import Tuval
from motor.sahneler import TURLER
from motor.cizgi import CizgiSahne

TURLER["cizgi"] = CizgiSahne
KOK_DIZIN = os.path.dirname(os.path.abspath(__file__))
SESLER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "motor", "sesler")

FORMATLAR = {"dikey": (1080, 1920), "yatay": (1920, 1080), "kare": (1080, 1080)}
VARSAYILAN_TEMA = {
    "deniz": "#10203a", "kara": "#2c4060", "sinir": "#50709a", "vurgu": "#f2b64a", "nokta": "#e85c48",
    "kart_arka": ["#141c2e", "#2a1f3d"], "altyazi_y": 0.86, "altyazi_boyut": 40,
}


def ffmpeg_kontrol():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("HATA: ffmpeg bulunamadı. README'deki kurulum adımına bakın (Windows: winget install Gyan.FFmpeg).")


def ses_suresi(yol):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", yol],
                         capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


def dil_degeri(v, dil):
    if isinstance(v, dict):
        return v.get(dil)
    return v


SES_UZANTI = (".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac")


def anlatim_dosyasi(klasor, dil, ad):
    """ses/<dil>/<ad>.mp3|wav|... varsa yolunu döndürür (ad: '01', '02'... ya da 'tam')."""
    k = os.path.join(klasor, "ses", dil)
    for uz in SES_UZANTI:
        yol = os.path.join(k, ad + uz)
        if os.path.isfile(yol):
            return yol
    return None


def sahne_plani(proje, klasor, dil):
    """Her sahnenin süresini belirler (seslendirme varsa ona göre uzatır)."""
    from motor import sigdir
    import math
    fps = int(proje.get("fps", 30))
    tam_kare = lambda x: math.ceil(x * fps - 1e-6) / fps    # süreler tam kareye yuvarlanır: ses ve altyazı kaymaz
    modlar = sigdir.oku(klasor, dil)
    plan, bas = [], 0.0
    for i, s in enumerate(proje["sahneler"]):
        oran = 1.0
        sure = float(s.get("sure", 5))
        ses = dil_degeri(s.get("ses"), dil)
        if not ses:   # stüdyodan yüklenen seslendirme: ses/<dil>/NN.*
            ses = anlatim_dosyasi(klasor, dil, f"{i + 1:02d}")
            ses = os.path.relpath(ses, klasor) if ses else None
        ses_yolu = None
        if ses:
            ses_yolu = os.path.join(klasor, ses)
            if os.path.exists(ses_yolu):
                oran, sure = sigdir.hesapla(ses_suresi(ses_yolu), sure, modlar.get(f"{i + 1:02d}", "otomatik"),
                                            float(s.get("ses_payi", sigdir.VARSAYILAN_PAY)))
                if oran > 1:
                    print(f"  sahne {i + 1}: seslendirme ×{oran:.2f} hızlandırıldı (sahne {sure:.1f} sn)")
            else:
                print(f"  uyarı: ses dosyası yok, atlanıyor: {ses_yolu}")
                ses_yolu = None
        sure = tam_kare(sure)
        plan.append({"no": i + 1, "tanim": s, "sure": sure, "bas": bas, "ses": ses_yolu, "oran": oran})
        bas += sure
    tam = anlatim_dosyasi(klasor, dil, "tam")
    if tam and plan:
        fazla = ses_suresi(tam) + 0.8 - bas
        if fazla > 0:
            plan[-1]["sure"] = tam_kare(plan[-1]["sure"] + fazla)
    return plan


def sahne_olustur(is_):
    """Tek bir sahneyi mp4 olarak yazar (ayrı süreçte çalışır)."""
    tanim, sure, W, H, ss, dil, klasor, tema, fps, hedef = (is_[k] for k in
        ("tanim", "sure", "W", "H", "ss", "dil", "klasor", "tema", "fps", "hedef"))
    no = is_.get("kimlik", is_["no"])
    def ilerleme(i, n):
        print(f"ILERLEME {no} {i} {n}", flush=True)
    if tanim.get("tur") == "vektor":
        from motor import vektor_kayit
        url = vektor_kayit.sayfa_url(is_["taban"], os.path.join(klasor, tanim["dosya"]), dil, sonraki=is_.get("sonraki")) + f"&sure={sure}"
        vektor_kayit.kaydet(url, W, H, sure, fps, hedef, ilerleme, is_.get("bas", 0), is_.get("son"), is_.get("olcek", 1))
        return hedef
    tv = Tuval(W, H, ss, dil, klasor, tema)
    sahne = TURLER[tanim.get("tur", "kart")](tanim, tv, sure)
    gecici = hedef[:-4] + ".gecici.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "18", "-pix_fmt", "yuv420p", gecici], stdin=subprocess.PIPE)
    n = int(round(sure * fps))
    for i in range(n):
        p.stdin.write(sahne.kare(i / fps).tobytes())
        if i % 10 == 0 or i == n - 1:
            ilerleme(i + 1, n)
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg hata verdi: {hedef}")
    os.replace(gecici, hedef)
    return hedef


def parmak_izi(tanim, sure, W, H, ss, dil, klasor, tema, fps):
    dosyalar = []
    def topla(v):
        if isinstance(v, dict):
            for a in v.values(): topla(a)
        elif isinstance(v, list):
            for a in v: topla(a)
        elif isinstance(v, str) and v.lower().endswith((".png", ".jpg", ".jpeg", ".html", ".js", ".svg")):
            yol = os.path.join(klasor, v)
            dosyalar.append(os.path.getmtime(yol) if os.path.exists(yol) else 0)
    topla(tanim)
    if tanim.get("tur") == "vektor":
        for f in ("vektor.js", "vektor.css"):
            dosyalar.append(os.path.getmtime(os.path.join(KOK_DIZIN, "motor", "vektor", f)))
        sk = os.path.dirname(os.path.join(klasor, str(tanim.get("dosya", ""))))     # sahnelerin ortak dosyaları (_karakter.js, resimler)
        if os.path.isdir(sk):
            dosyalar += [(f, os.path.getmtime(os.path.join(sk, f))) for f in sorted(os.listdir(sk))
                         if f.lower().endswith((".js", ".png", ".jpg", ".jpeg", ".svg", ".css"))]
        import ceviri                                   # ekran yazılarının çevirisi değiştiyse sahne yeniden çizilir
        dosyalar.append(ceviri.oku(klasor)["diller"].get(dil, {}).get("ekran"))
    veri = json.dumps([tanim, sure, W, H, ss, dil, tema, fps, dosyalar], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(veri.encode()).hexdigest()


def sahne_efektleri(tanim):
    """Sahnedeki ses efektlerini topla: 'efektler' listesi + öğe/yazı 'ses' alanları."""
    olaylar = [dict(e) for e in tanim.get("efektler", [])]
    for o in tanim.get("ogeler", []) + tanim.get("yazilar", []):
        if o.get("ses"):
            olaylar.append({"t": o.get("bas", 0) + o.get("ses_gecikme", 0), "ses": o["ses"], "seviye": o.get("ses_seviye", 0.5)})
        c = o.get("cikis")
        if isinstance(c, dict) and c.get("ses"):
            olaylar.append({"t": c["t"], "ses": c["ses"], "seviye": c.get("ses_seviye", 0.5)})
    return olaylar


# ---------------- altyazı (Whisper kelime zamanlarından) ----------------
def altyazi_kelimeleri(plan, klasor, dil):
    """Sahne seslerinin yanındaki .kelimeler.json dosyalarından videonun zaman çizgisinde kelime listesi."""
    kelimeler = []
    def ekle(ses_yolu, ofset, oran=1.0):
        yan = os.path.splitext(ses_yolu)[0] + ".kelimeler.json"
        if not os.path.isfile(yan):
            return False
        with open(yan, encoding="utf-8") as f:
            k = json.load(f)
        if abs(k.get("ses_zaman", 0) - os.path.getmtime(ses_yolu)) > 1:
            print(f"  uyarı: {os.path.basename(ses_yolu)} değişmiş, altyazı için Whisper kontrolünü yeniden çalıştır.")
            return False
        for w in k.get("kelimeler", []):
            if w.get("w"):
                kelimeler.append({"w": w["w"], "bas": ofset + float(w["bas"]) / oran, "son": ofset + float(w["son"]) / oran})
        return True
    tam = anlatim_dosyasi(klasor, dil, "tam")
    eksik = 0
    if tam:
        eksik += 0 if ekle(tam, 0.3) else 1
    for p in plan:
        if p["ses"]:
            eksik += 0 if ekle(p["ses"], p["bas"] + 0.3, p.get("oran", 1.0)) else 1
    kelimeler.sort(key=lambda w: w["bas"])
    return kelimeler, eksik


def _parcala_altyazi(kelimeler, en_cok_kelime=3, en_cok_harf=20):
    """Kelimeleri ekranda birlikte görünecek kısa parçalara böler (noktalamada keser)."""
    parcalar, simdiki = [], []
    for w in kelimeler:
        if simdiki and (len(simdiki) >= en_cok_kelime or sum(len(x["w"]) + 1 for x in simdiki) + len(w["w"]) > en_cok_harf
                        or w["bas"] - simdiki[-1]["son"] > 0.6):
            parcalar.append(simdiki); simdiki = []
        simdiki.append(w)
        if w["w"][-1:] in ".,!?;:…":
            parcalar.append(simdiki); simdiki = []
    if simdiki:
        parcalar.append(simdiki)
    return parcalar


def _zaman_srt(t):
    t = max(0.0, t); s = int(t); ms = int(round((t - s) * 1000))
    if ms == 1000: s, ms = s + 1, 0
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d},{ms:03d}"


def _zaman_ass(t):
    t = max(0.0, t); cs = int(round(t * 100))
    return f"{cs // 360000}:{cs % 360000 // 6000:02d}:{cs % 6000 // 100:02d}.{cs % 100:02d}"


def srt_yaz(kelimeler, yol):
    parcalar = _parcala_altyazi(kelimeler, 7, 42)
    with open(yol, "w", encoding="utf-8") as f:
        for i, p in enumerate(parcalar, 1):
            son = p[-1]["son"] + 0.15
            if i < len(parcalar):
                son = min(son, parcalar[i][0]["bas"])
            f.write(f"{i}\n{_zaman_srt(p[0]['bas'])} --> {_zaman_srt(max(son, p[0]['bas'] + 0.5))}\n{' '.join(w['w'] for w in p)}\n\n")


def ass_yaz(kelimeler, yol, W, H, ayar):
    """Shorts tarzı altyazı: kısa parçalar, konuşulan kelime sarı yanar (ASS karaoke)."""
    boyut = int(ayar.get("boyut", 96 if W < H else (64 if W == H else 62)))
    konum = float(ayar.get("konum", 0.72 if W < H else 0.86))   # yazının alt kenarının ekran yüksekliğine oranı
    vurgu = str(ayar.get("vurgu", "#ffd166")).lstrip("#"); renk = str(ayar.get("renk", "#ffffff")).lstrip("#")
    bgr = lambda h: f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()
    satirlar = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Altyazi,Nunito Altyazi,{boyut},{bgr(vurgu)},{bgr(renk)},&H00141414,&H96000000,0,0,0,0,100,100,0,0,1,"
        f"{max(3, boyut // 13)},{max(1, boyut // 26)},2,90,90,{int(H * (1 - konum))},1", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    parcalar = _parcala_altyazi(kelimeler)
    for i, p in enumerate(parcalar):
        bas = p[0]["bas"]
        son = p[-1]["son"] + 0.2
        if i + 1 < len(parcalar):
            son = min(son, parcalar[i + 1][0]["bas"])
        son = max(son, bas + 0.35)
        metin = ""
        for j, w in enumerate(p):
            sonraki = p[j + 1]["bas"] if j + 1 < len(p) else son
            k = max(1, int(round((sonraki - w["bas"]) * 100)))
            metin += "{\\k" + str(k) + "}" + w["w"].replace("{", "(").replace("}", ")") + (" " if j + 1 < len(p) else "")
        satirlar.append(f"Dialogue: 0,{_zaman_ass(bas)},{_zaman_ass(son)},Altyazi,,0,0,0,,{{\\fad(60,40)}}{metin}")
    with open(yol, "w", encoding="utf-8") as f:
        f.write("\n".join(satirlar) + "\n")


def ses_kazanci(wav, hedef=-14.0):
    """Karışımın algılanan ses yüksekliğini (LUFS) ölçer; hedefe ulaşmak için gereken kazancı (dB) döndürür."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    try:
        olcum = json.loads(out[out.rindex("{"):out.rindex("}") + 1])
        i = float(olcum["input_i"])
    except (ValueError, KeyError):
        return 0.0
    if i < -60:        # neredeyse sessiz
        return 0.0
    kazanc = max(-15.0, min(15.0, hedef - i))
    print(f"  ses yüksekliği: {i:.1f} LUFS → {hedef:.0f} LUFS ({kazanc:+.1f} dB)", flush=True)
    return kazanc


def efekt_yolu(ad, klasor):
    """Proje klasöründe ya da hazır ses kütüphanesinde (motor/sesler) arar. 'pop' gibi kısa ad da olur."""
    for aday in (os.path.join(klasor, ad), os.path.join(SESLER, ad), os.path.join(SESLER, ad + ".wav"),
                 os.path.join(SESLER, ad + ".mp3")):
        if os.path.isfile(aday):
            return aday
    return None


def sonraki_renkler(plan, klasor):
    """Her sahne için bir sonraki sahnenin ilk arka plan rengi (sahne geçişi 'devir' bu renge dönüşür)."""
    from motor import vektor_kayit
    renkler = []
    for i, p in enumerate(plan):
        r = None
        if i + 1 < len(plan):
            s = plan[i + 1]["tanim"]
            r = vektor_kayit.arka_rengi(os.path.join(klasor, s["dosya"])) if s.get("tur") == "vektor" and s.get("dosya") else "000000"
        renkler.append(r)
    return renkler


def storyboard(plan, klasor, dil, fmt, W, H, kalite, tema, fps, taban):
    """Her sahneden iki ana kare (orta ve geçiş anı) + numaralı tek sayfalık storyboard.jpg"""
    from PIL import Image, ImageDraw, ImageFont
    from motor import vektor_kayit
    hedef = os.path.join(klasor, "cikti", "storyboard")
    os.makedirs(hedef, exist_ok=True)
    renkler = sonraki_renkler(plan, klasor)
    kartlar, vek = [], []
    for i, p in enumerate(plan):
        sure = p["sure"]
        anlar = [round(min(max(0.6, sure * 0.5), sure - 0.05), 2), round(max(0.0, sure - 0.55), 2)]
        kareler = [(t, os.path.join(hedef, f"{p['no']:02d}_{k}.png")) for k, t in zip("ab", anlar)]
        kart = {"no": p["no"], "baslik": p["tanim"].get("baslik") or p["tanim"].get("tur", ""), "bas": round(p["bas"], 2),
                "son": round(p["bas"] + sure, 2), "anlar": anlar, "kareler": [k[1] for k in kareler], "uyarilar": []}
        tur = p["tanim"].get("tur", "kart")
        if tur == "vektor":
            dosya = os.path.join(klasor, p["tanim"].get("dosya", ""))
            if os.path.isfile(dosya):
                url = vektor_kayit.sayfa_url(taban, dosya, dil, sonraki=renkler[i]) + f"&sure={sure}"
                vek.append((url, kareler, kart))
            else:
                kart["kareler"] = []; kart["uyarilar"].append("Sahne dosyası henüz yok: " + p["tanim"].get("dosya", ""))
        else:
            ss = 1 if tur == "resim" else kalite
            tv = Tuval(W, H, ss, dil, klasor, tema)
            sahne = TURLER[tur](p["tanim"], tv, sure)
            for t, yol in kareler:
                sahne.kare(min(t, sure - 1 / fps)).save(yol)
        kartlar.append(kart)
        print(f"STORYBOARD_ILERLEME {i + 1} {len(plan)}", flush=True)
    if vek:
        uy = vektor_kayit.coklu_kare([(u, k) for u, k, _ in vek], W, H)
        for (_, _, kart), u in zip(vek, uy):
            kart["uyarilar"] += u
    # tek sayfa: 4 sütun, her kartta iki kare yan yana
    tw, th = 240, int(240 * H / W)
    kw, kh = tw * 2 + 30, th + 110
    sut = min(4, max(1, len(kartlar)))
    satir = (len(kartlar) + sut - 1) // sut
    sayfa = Image.new("RGB", (sut * kw + 40, satir * kh + 40), "#0b1022")
    d = ImageDraw.Draw(sayfa)
    fy = os.path.join(KOK_DIZIN, "fontlar", "DejaVuSans-Bold.ttf")
    f1 = ImageFont.truetype(fy, 26) if os.path.isfile(fy) else ImageFont.load_default()
    f2 = ImageFont.truetype(fy, 17) if os.path.isfile(fy) else ImageFont.load_default()
    for n, k in enumerate(kartlar):
        x, y = 20 + (n % sut) * kw, 20 + (n // sut) * kh
        d.rounded_rectangle([x, y, x + kw - 14, y + kh - 14], 16, fill="#161d38")
        d.ellipse([x + 12, y + 10, x + 50, y + 48], fill="#8b7bff"); d.text((x + 31, y + 29), str(k["no"]), fill="white", font=f1, anchor="mm")
        d.text((x + 62, y + 14), str(k["baslik"])[:24], fill="white", font=f1)
        d.text((x + 62, y + 46), f"{k['bas']:.1f}–{k['son']:.1f} sn" + ("   ⚠" if k["uyarilar"] else ""), fill="#9aa6cc", font=f2)
        for j, yol in enumerate(k["kareler"]):
            if os.path.isfile(yol):
                im = Image.open(yol).convert("RGB").resize((tw, th))
                sayfa.paste(im, (x + 8 + j * (tw + 8), y + 78))
                d.text((x + 14 + j * (tw + 8), y + 82), ("orta" if j == 0 else "geçiş") + f" {k['anlar'][j]:.1f}s", fill="white", font=f2)
    sayfa_yol = os.path.join(hedef, "storyboard.jpg")
    sayfa.save(sayfa_yol, quality=88)
    with open(os.path.join(hedef, "storyboard.json"), "w", encoding="utf-8") as f:
        json.dump({"dil": dil, "sayfa": sayfa_yol, "sahneler": kartlar}, f, ensure_ascii=False, indent=1)
    print("STORYBOARD", os.path.join(hedef, "storyboard.json"), flush=True)
    return sayfa_yol


def video_olustur(proje, klasor, dil, fmt, args):
    W, H = FORMATLAR[fmt]
    fps = int(proje.get("fps", 30))
    kalite = 1 if args.taslak else int(proje.get("kalite", 2))
    tema = dict(VARSAYILAN_TEMA, **proje.get("tema", {}))
    ad = proje.get("ad", os.path.basename(klasor))
    plan = sahne_plani(proje, klasor, dil)
    toplam = sum(p["sure"] for p in plan)

    taban = None
    if any(p["tanim"].get("tur") == "vektor" for p in plan) or args.storyboard:
        from motor import vektor_kayit
        taban, _sunucu = vektor_kayit.sunucu_baslat()

    if args.storyboard:
        return storyboard(plan, klasor, dil, fmt, W, H, kalite, tema, fps, taban)
    renkler = sonraki_renkler(plan, klasor)

    # --- tek kare önizleme ---
    if args.kare is not None:
        for i, p in enumerate(plan):
            if p["bas"] <= args.kare < p["bas"] + p["sure"] or p is plan[-1]:
                if p["tanim"].get("tur") == "vektor":
                    yol = os.path.join(klasor, "cikti", f"kare_{dil}_{fmt}_{args.kare:.2f}.png")
                    os.makedirs(os.path.dirname(yol), exist_ok=True)
                    url = vektor_kayit.sayfa_url(taban, os.path.join(klasor, p["tanim"]["dosya"]), dil, sonraki=renkler[i]) + f"&sure={p['sure']}"
                    vektor_kayit.tek_kare(url, W, H, min(args.kare - p["bas"], p["sure"] - 1 / fps), yol)
                    print("Kare kaydedildi:", yol)
                    return yol
                ss = 1 if p["tanim"].get("tur") == "resim" else kalite
                tv = Tuval(W, H, ss, dil, klasor, tema)
                sahne = TURLER[p["tanim"].get("tur", "kart")](p["tanim"], tv, p["sure"])
                yol = os.path.join(klasor, "cikti", f"kare_{dil}_{fmt}_{args.kare:.2f}.png")
                os.makedirs(os.path.dirname(yol), exist_ok=True)
                sahne.kare(min(args.kare - p["bas"], p["sure"] - 1 / fps)).save(yol)
                print("Kare kaydedildi:", yol)
                return yol

    calisma = os.path.join(klasor, "cikti", f".parcalar_{dil}_{fmt}")
    os.makedirs(calisma, exist_ok=True)
    isler, dosyalar = [], []
    for i, p in enumerate(plan):
        if args.sahne and p["no"] != args.sahne:
            continue
        ss = 1 if p["tanim"].get("tur") == "resim" else kalite
        hedef = os.path.join(calisma, f"sahne_{p['no']:02d}.mp4")
        iz = parmak_izi(dict(p["tanim"], _sonraki=renkler[i], _taslak=bool(args.taslak)), p["sure"], W, H, ss, dil, klasor, tema, fps)
        iz_dosya = hedef + ".iz"
        dosyalar.append(hedef)
        if not args.yeniden and os.path.exists(hedef) and os.path.exists(iz_dosya) and open(iz_dosya).read() == iz:
            continue   # değişmemiş sahne, tekrar çizilmez
        if os.path.exists(iz_dosya):
            os.remove(iz_dosya)
        isler.append(({"tanim": p["tanim"], "sure": p["sure"], "W": W, "H": H, "ss": ss, "dil": dil, "klasor": klasor,
                       "tema": tema, "fps": fps, "hedef": hedef, "no": p["no"], "taban": taban, "sonraki": renkler[i]}, iz_dosya, iz))

    # Vektör sahneler parçalara bölünür: az sahneli videoda da bütün işlemci çekirdekleri çalışır.
    import math
    isci = max(1, min((os.cpu_count() or 2) - 1, int(proje.get("isci", 12))))
    olcek = 0.5 if args.taslak else 1
    kare = lambda i: int(round(i["sure"] * fps))
    toplam_kare = sum(kare(i[0]) for i in isler)
    dilim = max(90, math.ceil(toplam_kare / isci)) if proje.get("parcali", True) else 10 ** 9
    gorevler, birlesecek = [], []
    for i, _, _ in isler:
        n = kare(i)
        adet = math.ceil(n / dilim) if i["tanim"].get("tur") == "vektor" else 1
        if adet <= 1:
            gorevler.append(dict(i, kimlik=str(i["no"]), olcek=olcek, _kare=n)); continue
        parcalar = []
        for k in range(adet):
            a, b = n * k // adet, n * (k + 1) // adet
            ph = i["hedef"][:-4] + f".p{k + 1}.mp4"
            parcalar.append(ph)
            gorevler.append(dict(i, hedef=ph, bas=a, son=b, kimlik=f"{i['no']}.{k + 1}", olcek=olcek, _kare=b - a))
        birlesecek.append((i["hedef"], parcalar))
    gorevler.sort(key=lambda g: -g["_kare"])      # uzun parçalar önce: çekirdekler boş beklemez

    print(f"[{dil} / {fmt}] {len(plan)} sahne, toplam {toplam:.1f} sn — çizilecek: {len(isler)}"
          + (f" ({len(gorevler)} parça, {min(isci, len(gorevler))} çekirdek)" if isler else ""), flush=True)
    print("PLAN " + json.dumps({g["kimlik"]: g["_kare"] for g in gorevler}), flush=True)
    t0 = time.time()
    if gorevler:
        with Pool(min(len(gorevler), isci)) as havuz:
            list(havuz.imap_unordered(sahne_olustur, gorevler))
        for hedef, parcalar in birlesecek:
            pl = hedef[:-4] + ".parcalar.txt"
            with open(pl, "w", encoding="utf-8") as f:
                f.writelines("file '" + os.path.abspath(x).replace("\\", "/") + "'\n" for x in parcalar)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", pl, "-c", "copy", hedef], check=True)
            for x in parcalar + [pl]:
                os.remove(x)
        for _, iz_dosya, iz in isler:
            open(iz_dosya, "w").write(iz)
    print(f"  çizim süresi: {time.time() - t0:.0f} sn")

    liste = os.path.join(calisma, "liste.txt")
    with open(liste, "w", encoding="utf-8") as f:
        for d in dosyalar:
            f.write("file '" + os.path.abspath(d).replace("\\", "/") + "'\n")
    sessiz = os.path.join(calisma, "sessiz.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", liste, "-c", "copy", sessiz], check=True)

    ek = f"_sahne{args.sahne}" if args.sahne else ""
    cikti = os.path.join(klasor, "cikti", f"{ad}_{dil}_{fmt}{ek}.mp4")
    ses_ciktisi = os.path.join(klasor, "cikti", f"{ad}_{dil}_sadece_ses.m4a")

    # --- ses: anlatım + ses efektleri + arka müzik ---
    girdiler, filtreler, anl, efk = [], [], [], []
    def ses_ekle(liste, yol, an, seviye=1.0, oran=1.0):
        girdiler.extend(["-i", yol])
        n = girdiler.count("-i") - 1
        ms = max(0, int(an * 1000))
        tempo = f"atempo={oran},asetpts=N/SR/TB," if oran != 1 else ""
        filtreler.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,{tempo}volume={seviye},adelay={ms}|{ms}[a{n}]")
        liste.append(f"[a{n}]")
    if not args.sahne:
        tam = anlatim_dosyasi(klasor, dil, "tam")
        if tam:
            ses_ekle(anl, tam, 0.3)
        for p in plan:
            if p["ses"]:
                ses_ekle(anl, p["ses"], p["bas"] + 0.3, 1.0, p.get("oran", 1.0))
            for e in sahne_efektleri(p["tanim"]):
                yol = efekt_yolu(e["ses"], klasor)
                if yol and e["t"] < p["sure"]:
                    ses_ekle(efk, yol, p["bas"] + e["t"], e.get("seviye", 0.5))
    anlatim_var = bool(anl)
    son_karisim = list(efk)
    if anl:
        filtreler.append("".join(anl) + (f"amix=inputs={len(anl)}:normalize=0:duration=longest" if len(anl) > 1 else "anull") + f",apad=whole_dur={toplam}[anl]")
    muzik = proje.get("muzik")
    if args.muzik:
        muzik = None if args.muzik == "yok" else {"dosya": args.muzik, "ses": (muzik or {}).get("ses", 0.3) if isinstance(muzik, dict) else 0.3}
    if muzik is not None and args.muzik_ses is not None:
        muzik = {"dosya": muzik["dosya"] if isinstance(muzik, dict) else muzik, "ses": args.muzik_ses}
    muzik_var = False
    if muzik and not args.sahne:
        mad = muzik["dosya"] if isinstance(muzik, dict) else muzik
        myol = efekt_yolu(mad, klasor)
        if myol:
            sv = muzik.get("ses", 0.15) if isinstance(muzik, dict) else 0.15
            girdiler += ["-stream_loop", "-1", "-i", myol]
            n = girdiler.count("-i") - 1
            filtreler.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={sv * (0.8 if anlatim_var else 1)},"
                             f"atrim=0:{toplam},afade=t=out:st={max(0, toplam - 1.5)}:d=1.5[m]")
            muzik_var = True
        else:
            print(f"  uyarı: müzik dosyası bulunamadı: {mad}")
    if anl and muzik_var:
        # Otomatik kısma: konuşma sürerken müzik kendiliğinden alçalır, cümle aralarında ve sonda geri yükselir.
        filtreler.append("[anl]asplit=2[anl1][anlk]")
        filtreler.append(f"[anlk]volume=12dB,alimiter=limit=0.5:level=disabled[anahtar]")
        filtreler.append("[m][anahtar]sidechaincompress=threshold=0.05:ratio=1.6:attack=40:release=600:knee=4[md]")
        son_karisim += ["[anl1]", "[md]"]
    else:
        son_karisim += (["[anl]"] if anl else []) + (["[m]"] if muzik_var else [])

    # --- altyazı: Whisper kelime zamanları varsa .srt her zaman, istenirse videoya gömülü
    video_ayar = ["-map", "0:v", "-c:v", "copy"]
    cwd = None
    if not args.sahne:
        kel, eksik = altyazi_kelimeleri(plan, klasor, dil)
        if kel:
            srt = os.path.join(klasor, "cikti", f"{ad}_{dil}.srt")
            srt_yaz(kel, srt)
            print(f"  altyazı dosyası: {os.path.basename(srt)}" + (f" ({eksik} ses Whisper kontrolünden geçmemiş, onlarda altyazı yok)" if eksik else ""), flush=True)
            if args.altyazi:
                ass_yaz(kel, os.path.join(calisma, "altyazi.ass"), W, H, proje.get("altyazi") or {})
                font = os.path.join(KOK_DIZIN, "motor", "vektor", "fontlar", "NunitoAltyazi.ttf")
                if os.path.isfile(font):
                    shutil.copyfile(font, os.path.join(calisma, "NunitoAltyazi.ttf"))
                video_ayar = ["-vf", "subtitles=altyazi.ass:fontsdir=.", "-c:v", "libx264", "-preset", "veryfast",
                              "-crf", "18" if not args.taslak else "23", "-pix_fmt", "yuv420p"]
                cwd = calisma       # süzgeç yolu Windows'ta sorun çıkarmasın diye çalışma klasöründen
        elif args.altyazi:
            print("  uyarı: altyazı için önce Seslendirme → 🔍 Whisper kontrolü çalıştır (kelime zamanları yok).", flush=True)

    sessiz, cikti_tam = os.path.abspath(sessiz), os.path.abspath(cikti)
    if son_karisim:
        # 1) karışım tek bir wav'a, 2) ses yüksekliği ölçülür, 3) YouTube/Instagram düzeyine (-14 LUFS) getirilip videoya eklenir
        karisim = os.path.join(os.path.abspath(calisma), "karisim.wav")
        filtreler.append("".join(son_karisim) + f"amix=inputs={len(son_karisim)}:normalize=0:duration=longest,apad=whole_dur={toplam},asetpts=N/SR/TB,atrim=0:{toplam}[ses]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + girdiler + ["-filter_complex", ";".join(filtreler), "-map", "[ses]",
                        "-c:a", "pcm_s16le", "-ar", "48000", karisim], check=True)
        kazanc = ses_kazanci(karisim, float((proje.get("ses") or {}).get("hedef_lufs", -14)) if isinstance(proje.get("ses"), dict) else -14)
        ses_f = f"volume={kazanc:.2f}dB,alimiter=limit=0.89:level=disabled"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", sessiz, "-i", karisim] +
                       (["-map", "0:v", "-c:v", "copy"] if cwd is None else ["-map", "0:v"] + video_ayar) +
                       ["-map", "1:a", "-af", ses_f, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", cikti_tam], check=True, cwd=cwd)
        if anlatim_var:   # YouTube çok dilli ses için sadece ses dosyası
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", cikti, "-vn", "-c:a", "copy", ses_ciktisi], check=True)
    else:   # sessiz video: platform uyumluluğu için boş ses kanalı ekle
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", sessiz, "-f", "lavfi", "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=48000"] +
                       (["-map", "0:v", "-c:v", "copy"] if cwd is None else ["-map", "0:v"] + video_ayar) +
                       ["-map", "1:a", "-c:a", "aac", "-shortest", "-movflags", "+faststart", cikti_tam], check=True, cwd=cwd)
    print("  HAZIR:", cikti, flush=True)
    return cikti


def main():
    ap = argparse.ArgumentParser(description="Animasyon şablonu: YAML dosyasından video üretir.")
    ap.add_argument("proje", help="video.yaml dosyasının yolu")
    ap.add_argument("--dil", help="tr, en, pl... virgülle birden fazla, ya da 'hepsi'")
    ap.add_argument("--format", choices=list(FORMATLAR), help="dikey (Shorts/Reels/TikTok), yatay (YouTube), kare")
    ap.add_argument("--kare", type=float, help="sadece bu saniyenin resmini çıkar")
    ap.add_argument("--sahne", type=int, help="sadece bu numaralı sahneyi çiz")
    ap.add_argument("--altyazi", action="store_true", help="Whisper kelime zamanlarından altyazıyı videoya göm")
    ap.add_argument("--storyboard", action="store_true", help="her sahneden ana kareler + numaralı storyboard.jpg (video çizmeden)")
    ap.add_argument("--taslak", action="store_true", help="hızlı, düşük kalite")
    ap.add_argument("--yeniden", action="store_true", help="önbelleği yok say, her şeyi baştan çiz")
    ap.add_argument("--muzik", help="müzik dosyası (proje klasöründe ya da motor/sesler) ya da 'yok'")
    ap.add_argument("--muzik-ses", type=float, dest="muzik_ses", help="müzik seviyesi (0-1)")
    args = ap.parse_args()
    ffmpeg_kontrol()

    klasor = os.path.dirname(os.path.abspath(args.proje))
    with open(args.proje, encoding="utf-8") as f:
        proje = yaml.safe_load(f)
    import ceviri
    diller = ceviri.birlestir([], list(proje.get("diller", ["tr"])), klasor)   # 🌐 Çevir ile eklenen diller de
    if args.dil == "hepsi":
        secilen = diller
    elif args.dil:
        secilen = [d.strip() for d in args.dil.split(",")]
    else:
        secilen = diller[:1]
    fmt = args.format or proje.get("format", "dikey")
    for dil in secilen:
        video_olustur(proje, klasor, dil, fmt, args)


if __name__ == "__main__":
    main()
