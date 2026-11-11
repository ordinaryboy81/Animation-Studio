"""
Animasyon Stüdyosu — tarayıcıda açılan arayüz (sadece bu bilgisayardan erişilir).
Çalıştırmak için BASLAT.bat dosyasına çift tıkla (ya da: python arayuz.py).
"""
import json, mimetypes, os, re, shutil, signal, socket, subprocess, sys, threading, time, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote, unquote

import yaml

import tts_yonetici as tts
import ceviri
import guncelleme

KOK = os.path.dirname(os.path.abspath(__file__))


def _ffmpeg_hazirla():
    """Sistemde ffmpeg yoksa 'ffmpeg-binaries' paketiyle gelen hazır ffmpeg'i kullan."""
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    try:
        import importlib.util
        spec = importlib.util.find_spec("ffmpeg")
        if spec and spec.origin:
            kok = os.path.join(os.path.dirname(spec.origin), "binaries")
            for k in (os.path.join(kok, "bin"), kok):
                if os.path.isfile(os.path.join(k, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")):
                    if os.name != "nt":
                        for ad in ("ffmpeg", "ffprobe"):
                            yol = os.path.join(k, ad)
                            if os.path.isfile(yol):
                                os.chmod(yol, 0o755)
                    os.environ["PATH"] = k + os.pathsep + os.environ.get("PATH", "")
                    return
    except Exception:  # noqa: BLE001
        pass


_ffmpeg_hazirla()
if os.path.isdir(os.path.join(KOK, ".ortam")):      # kurulum paketi: Python ve indirilenler stüdyo klasöründe kalsın
    os.environ.setdefault("UV_PYTHON_INSTALL_DIR", os.path.join(KOK, ".python"))
    os.environ.setdefault("UV_CACHE_DIR", os.path.join(KOK, ".uv_cache"))
    os.environ.setdefault("PYTHONUTF8", "1")
PROJELER = os.path.join(KOK, "projeler")
SESLER = os.path.join(KOK, "motor", "sesler")
PORT = 8765
ORTAM = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
GIZLI = 0x08000000 if os.name == "nt" else 0
SES_UZANTI = (".mp3", ".wav", ".m4a", ".ogg")

IS = {"calisiyor": False, "log": [], "ciktilar": [], "hata": False, "yuzde": 0, "asama": "", "proje": None}
SURUC = {"p": None}


# ------------------------------------------------------------------ yardımcılar
def proje_klasoru(ad):
    if not re.fullmatch(r"[\w\-]+", ad or ""):
        raise ValueError("Geçersiz proje adı")
    return os.path.join(PROJELER, ad)


def projeler():
    if not os.path.isdir(PROJELER):
        return []
    return sorted(d for d in os.listdir(PROJELER) if os.path.exists(os.path.join(PROJELER, d, "video.yaml")))


def ozet(metin, ad=None):
    try:
        p = yaml.safe_load(metin)
    except yaml.YAMLError as e:
        m = getattr(e, "problem_mark", None)
        yer = f" (satır {m.line + 1}, sütun {m.column + 1})" if m else ""
        return {"hata": f"Senaryo dosyasında yazım hatası{yer}. Genelde girinti (boşluk) ya da eksik tırnak/parantez sebep olur."}
    if not isinstance(p, dict) or not isinstance(p.get("sahneler"), list):
        return {"hata": "Dosyada 'sahneler:' listesi bulunamadı."}
    sahneler, bas, olaylar = [], 0.0, []
    for i, s in enumerate(p["sahneler"]):
        if not isinstance(s, dict):
            continue
        sure = float(s.get("sure", 5))
        tur = s.get("tur", "kart")
        url = None
        if tur in ("vektor", "uc", "piksel") and ad and s.get("dosya"):
            url = "/k/projeler/" + quote(ad) + "/" + quote(s["dosya"].replace("\\", "/"))
        arka0 = None
        if url:
            from motor.vektor_kayit import arka_rengi
            arka0 = arka_rengi(os.path.join(PROJELER, ad, s["dosya"]))
        sahneler.append({"no": i + 1, "tur": tur, "baslik": s.get("baslik") or s.get("ad") or "", "sure": sure, "sure0": sure, "bas": bas, "url": url,
                         "pay": float(s.get("ses_payi", 0.6)), "anlatim": s.get("anlatim") or {}, "storyboard": s.get("storyboard") or {}, "arka0": arka0})
        for e in s.get("efektler", []) or []:
            olaylar.append({"t": bas + float(e.get("t", 0)), "no": i + 1, "yerel": float(e.get("t", 0)), "ses": e.get("ses"), "seviye": e.get("seviye", 0.5)})
        for o in (s.get("ogeler", []) or []) + (s.get("yazilar", []) or []):
            if isinstance(o, dict) and o.get("ses"):
                olaylar.append({"t": bas + float(o.get("bas", 0)), "no": i + 1, "yerel": float(o.get("bas", 0)), "ses": o["ses"], "seviye": o.get("ses_seviye", 0.5)})
        bas += sure
    for i, s in enumerate(sahneler):   # devir geçişi: bir sonraki sahnenin ilk rengi
        if i + 1 < len(sahneler):
            s["sonraki"] = sahneler[i + 1]["arka0"] or "000000"
    muzik = p.get("muzik")
    if isinstance(muzik, str):
        muzik = {"dosya": muzik, "ses": 0.15}
    for o in olaylar:
        o["url"] = ses_url(o["ses"], ad)
    diller = list(p.get("diller", ["tr"]))
    if ad:
        diller = ceviri.birlestir(sahneler, diller, os.path.join(PROJELER, ad))
    return {"diller": diller, "sure": bas, "format": p.get("format", "dikey"), "sahneler": sahneler,
            "olaylar": [o for o in olaylar if o["url"]], "muzik": muzik}


def ses_url(ad, proje=None):
    if not ad:
        return None
    adaylar = []
    if proje:
        adaylar.append(("projeler/" + proje + "/" + ad, os.path.join(PROJELER, proje, ad)))
    for uz in ("", ".wav", ".mp3"):
        adaylar.append(("motor/sesler/" + ad + uz, os.path.join(SESLER, ad + uz)))
    for url, yol in adaylar:
        if os.path.isfile(yol):
            return "/k/" + quote(url)
    return None


def sesler(ad=None):
    liste = []
    if os.path.isdir(SESLER):
        liste += [{"ad": f, "kaynak": "hazır"} for f in sorted(os.listdir(SESLER)) if f.endswith(SES_UZANTI) and "muzik" in f.lower()]
    if ad:
        for alt in ("", "muzik"):
            k = os.path.join(PROJELER, ad, alt)
            if os.path.isdir(k):
                liste += [{"ad": (alt + "/" if alt else "") + f, "kaynak": "proje"} for f in sorted(os.listdir(k)) if f.endswith(SES_UZANTI)]
    return liste


def ciktilar(ad):
    k = os.path.join(proje_klasoru(ad), "cikti")
    if not os.path.isdir(k):
        return []
    liste = []
    for f in os.listdir(k):
        if f.endswith(".mp4") and "_sahne" not in f:
            yol = os.path.join(k, f)
            liste.append({"ad": f, "boyut": os.path.getsize(yol), "zaman": os.path.getmtime(yol),
                          "url": "/dosya?yol=" + quote(yol)})
    return sorted(liste, key=lambda x: -x["zaman"])


ANLATIM_UZ = (".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac")
_SURE_ONBELLEK = {}


def ses_suresi(yol):
    anahtar = (yol, os.path.getmtime(yol))
    if anahtar not in _SURE_ONBELLEK:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", yol],
                             capture_output=True, text=True, creationflags=GIZLI)
        try:
            _SURE_ONBELLEK[anahtar] = round(float(out.stdout.strip()), 2)
        except ValueError:
            _SURE_ONBELLEK[anahtar] = 0.0
    return _SURE_ONBELLEK[anahtar]


def anlatim_durumu(ad):
    """ses/<dil>/tam.* ve ses/<dil>/NN.* dosyalarını listeler."""
    sonuc = {}
    kok = os.path.join(proje_klasoru(ad), "ses")
    if not os.path.isdir(kok):
        return sonuc
    for dil in os.listdir(kok):
        k = os.path.join(kok, dil)
        if not os.path.isdir(k):
            continue
        from motor import sigdir
        d = {"tam": None, "sahneler": {}, "sigdir": sigdir.oku(proje_klasoru(ad), dil)}
        uretim = tts.uretim_oku(proje_klasoru(ad), dil)
        for f in sorted(os.listdir(k)):
            ad_, uz = os.path.splitext(f)
            if uz.lower() not in ANLATIM_UZ:
                continue
            yol = os.path.join(k, f)
            bilgi = {"url": "/dosya?yol=" + quote(yol) + f"&v={os.path.getmtime(yol)}", "sure": ses_suresi(yol), "dosya": f}
            u = uretim.get(ad_)
            if isinstance(u, dict) and abs(u.get("zaman", 0) - os.path.getmtime(yol)) < 1.5:
                bilgi["metin"] = u.get("metin")      # Chatterbox bu metinden üretti; senaryo değiştiyse ses eskimiştir
            kt = tts.kontrol_oku(yol)
            if kt:
                bilgi["kontrol"] = {"benzerlik": kt.get("benzerlik"), "eksik": kt.get("eksik", [])[:12], "fazla": kt.get("fazla", [])[:12],
                                    "duyulan": kt.get("duyulan", "")}
            if ad_ == "tam":
                d["tam"] = bilgi
            elif ad_.isdigit():
                d["sahneler"][str(int(ad_))] = bilgi
        sonuc[dil] = d
    return sonuc


def anlatim_sil(ad, dil, hedef):
    k = os.path.join(proje_klasoru(ad), "ses", dil)
    if not re.fullmatch(r"\w+", dil) or not re.fullmatch(r"tam|\d{2}", hedef) or not os.path.isdir(k):
        return
    yan = os.path.join(k, hedef + ".kelimeler.json")
    if os.path.isfile(yan):
        os.remove(yan)
    for uz in ANLATIM_UZ:
        yol = os.path.join(k, hedef + uz)
        if os.path.isfile(yol):
            os.remove(yol)


def metin_duzelt(ad, dil, no, yeni):
    """Sahnenin seslendirme metnini değiştirir. Metin senaryoda (video.yaml) yazılıysa orada, yalnızca o satır
    değiştirilir (dosyanın geri kalanı ve yorumlar aynen kalır); çeviriden geliyorsa ceviri.json'da."""
    klasor = proje_klasoru(ad)
    yol = os.path.join(klasor, "video.yaml")
    ham = open(yol, encoding="utf-8").read()
    proje = yaml.safe_load(ham)
    sahneler = proje["sahneler"]
    if not 1 <= no <= len(sahneler):
        raise ValueError("Sahne bulunamadı")

    def oku(p):
        a = p["sahneler"][no - 1].get("anlatim")
        return (a.get(dil) if isinstance(a, dict) else a) if a else None
    eski = oku(proje)
    if not isinstance(eski, str) or not eski.strip():
        if not yeni:
            raise ValueError("Metin boş olamaz")
        ceviri.yaz(klasor, None, dil, "anlatim", str(no), yeni)      # senaryoda bu dil yok: çeviri dosyasında tutulur
        return "ceviri"
    if not yeni:
        raise ValueError("Metin boş olamaz (sahneyi sessiz bırakmak için Senaryo'dan satırı sil).")
    if yeni == eski:
        return "ayni"
    for aday in dict.fromkeys([eski, json.dumps(eski, ensure_ascii=False)[1:-1]]):
        i = -1
        while (i := ham.find(aday, i + 1)) >= 0:
            once, sonra = ham[i - 1:i], ham[i + len(aday):i + len(aday) + 1]
            if once == '"' and sonra == '"':
                konan = json.dumps(yeni, ensure_ascii=False)[1:-1]
            elif once == "'" and sonra == "'":
                konan = yeni.replace("'", "''")
            else:       # tırnaksız değer: güvenli olsun diye tırnak içine al
                konan = json.dumps(yeni, ensure_ascii=False)
            deneme = ham[:i] + konan + ham[i + len(aday):]
            try:
                p2 = yaml.safe_load(deneme)
                beklenen = json.loads(json.dumps(proje, default=str))
                a = beklenen["sahneler"][no - 1]["anlatim"]
                if isinstance(a, dict):
                    a[dil] = yeni
                else:
                    beklenen["sahneler"][no - 1]["anlatim"] = yeni
                if json.loads(json.dumps(p2, default=str)) == json.loads(json.dumps(beklenen, default=str)):   # yalnızca bu metin değişti
                    with open(yol, "w", encoding="utf-8", newline="\n") as f:
                        f.write(deneme)
                    return "senaryo"
            except Exception:  # noqa: BLE001
                pass
    raise ValueError("Bu metin senaryoda tek satır olarak bulunamadı; Senaryo penceresinden düzenle.")


BOS_PROJE = """# Yeni proje. Tüm seçenekler: stüdyo klasöründeki bos_sablon.yaml
ad: {ad}
stil: {stil}            # sahnelerin tarzı: vektor | uc (3D) | piksel. Claude yeni sahneleri bu tarzda yazar.
diller: [{diller}]
format: dikey
fps: {fps}

sahneler:
  - tur: {stil}
    baslik: {baslik}
    dosya: sahneler/01_baslangic.html
    sure: 4
    anlatim:
      {d1}: "{a1}"
"""
BOS_SAHNE = {
    "vektor": """<!doctype html><html><head><meta charset="utf-8"><title>01_baslangic</title>
<link rel="stylesheet" href="../../../motor/vektor/vektor.css"></head><body>
<script src="../../../motor/vektor/vektor.js"></script>
<script>
let baslik, alt;
V.sahne({
  sure: 4, arka: ["#141a33", "#27306b"], giris: "siyah", cikis: "siyah",
  kur(s) {
    baslik = V.yazi(s.ust, { metin: { tr: "Yeni proje", en: "New project" }, x: 540, y: 860, boyut: 96, genislik: 900 });
    alt = V.yazi(s.ust, { metin: { tr: "Sahneleri Claude'a yazdır", en: "Ask Claude to write the scenes" }, x: 540, y: 1010, boyut: 48, renk: "#ffd166", genislik: 900 });
  },
  ciz(t, s) {
    V.itme(t, { yakin: 1.05 });
    baslik.anim(t, 0.3, "bulanik", 3.6);
    alt.anim(t, 1.0, "bulanik", 3.6);
  },
});
</script></body></html>
""",
    "uc": """<!doctype html><html><head><meta charset="utf-8"><title>01_baslangic</title>
<link rel="stylesheet" href="../../../motor/vektor/vektor.css">
<script type="importmap">{"imports":{"three":"../../../motor/uc/three.module.min.js","three/addons/":"../../../motor/uc/addons/"}}</script></head><body>
<script type="module">
import { U, THREE } from "../../../motor/uc/uc.js";
let ada, baslik, alt;
U.sahne({
  sure: 4, arka: ["#8ec5ff", "#fde2c8"], isik: "gun", sis: 0.012, gorus: 30, giris: "siyah", cikis: "siyah",
  kur(s) {
    s.sahne.add(U.zemin("#4aa3df", { boyut: 80 }));
    ada = new THREE.Group(); s.sahne.add(ada);
    const kara = U.silindir(2.6, 0.5, "#f1d9a0", { ust: 2.4 }); kara.position.y = 0.1; ada.add(kara);
    const cim = U.silindir(2.3, 0.2, "#6cc06a", { ust: 2.2 }); cim.position.y = 0.42; ada.add(cim);
    const ev = U.ev({ cati: "#e8695d" }); ev.position.set(-0.4, 0.52, 0.2); ada.add(ev);
    [[1.1, -0.6], [0.9, 0.9], [-1.4, -0.7]].forEach(([x, z], i) => { const a = U.agac({ boy: 0.8, tohum: i }); a.position.set(x, 0.52, z); ada.add(a); });
    baslik = U.yazi(s.ust, { metin: { tr: "Yeni proje", en: "New project" }, y: 260, boyut: 96 });
    alt = U.yazi(s.ust, { metin: { tr: "Sahneleri Claude'a yazdır", en: "Ask Claude to write the scenes" }, y: 390, boyut: 50, renk: "#fff4d6" });
  },
  ciz(t, s) {
    U.itme(t, { bas: [0, 6, 15], son: [2, 4, 11], hedef: [0, 0.8, 0] });
    ada.rotation.y = t * 0.1;
    baslik.anim(t, 0.3, "bulanik", 3.4); alt.anim(t, 0.8, "bulanik", 3.4);
  },
});
</script></body></html>
""",
    "piksel": """<!doctype html><html><head><meta charset="utf-8"><title>01_baslangic</title>
<link rel="stylesheet" href="../../../motor/piksel/piksel.css"></head><body>
<script src="../../../motor/piksel/piksel.js"></script>
<script>
PX.sahne({
  sure: 4, arka: ["#1a1b3a", "#3e2a5e"], giris: "siyah", cikis: "siyah",
  ciz(t, c) {
    c.gok(["#1a1b3a", "#283066", "#3e2a5e", "#7a4fb3"], { y1: 240 });
    c.yildizlar(t, { n: 45, y1: 170 });
    c.ay(146, 118, { r: 10 });
    c.daglar({ y: 225, h: 60, renk: "#2b2452", golge: "#1f1a3c", kar: "#b8b4d8", tohum: 3, kayma: t * 2 });
    c.agac(30, 262, { tur: "cam" }); c.agac(150, 262, {});
    c.ev(90, 262, { cati: "kirmizi" });
    c.zemin({ y: 262, renk: "#3a2a1e", ust: "#2f7a40", ust2: "#1f4c36" });
    c.sprite("insan", 20 + t * 12, 262, { anim: "yuru" });
    c.yazi({ tr: "Yeni proje", en: "New project" }, 90, 40, { boyut: 3, renk: "sari", t0: 0.3, hiz: 12 });
    c.yazi({ tr: "Sahneleri Claude'a yazdır", en: "Ask Claude to write the scenes" }, 90, 74, { boyut: 1, t0: 1.2 });
  },
});
</script></body></html>
""",
}


def bos_proje_yaz(hedef, ad, stil, dil):
    stil = stil if stil in BOS_SAHNE else "vektor"
    en = dil == "en"
    os.makedirs(os.path.join(hedef, "sahneler"))
    yaml_metin = BOS_PROJE.format(ad=ad, stil=stil, diller="en, tr" if en else "tr, en", fps=24 if stil == "piksel" else 30,
                                  baslik="Start" if en else "Başlangıç", d1="en" if en else "tr",
                                  a1="This is a new project." if en else "Bu yeni bir proje.")
    open(os.path.join(hedef, "video.yaml"), "w", encoding="utf-8", newline="\n").write(yaml_metin)
    open(os.path.join(hedef, "sahneler", "01_baslangic.html"), "w", encoding="utf-8", newline="\n").write(BOS_SAHNE[stil])


def storyboard_oku(ad):
    """Son çıkarılan storyboard + senaryodaki storyboard notları."""
    yol = os.path.join(proje_klasoru(ad), "cikti", "storyboard", "storyboard.json")
    o = ozet(open(os.path.join(proje_klasoru(ad), "video.yaml"), encoding="utf-8").read(), ad)
    sb = {}
    if os.path.isfile(yol):
        with open(yol, encoding="utf-8") as f:
            sb = json.load(f)
    kareler = {k["no"]: k for k in sb.get("sahneler", [])}
    sahneler = []
    for s in o.get("sahneler", []):
        k = kareler.get(s["no"], {})
        sahneler.append(dict(s, kareler=["/dosya?yol=" + quote(y) + f"&v={os.path.getmtime(y)}" for y in k.get("kareler", []) if os.path.isfile(y)],
                             anlar=k.get("anlar", []), uyarilar=k.get("uyarilar", [])))
    sayfa = sb.get("sayfa")
    return {"dil": sb.get("dil"), "zaman": os.path.getmtime(yol) if os.path.isfile(yol) else None, "sahneler": sahneler,
            "sayfa": "/dosya?yol=" + quote(sayfa) + f"&v={os.path.getmtime(sayfa)}" if sayfa and os.path.isfile(sayfa) else None,
            "hata": o.get("hata")}


def calistir(arglar):
    return subprocess.Popen([sys.executable, os.path.join(KOK, "olustur.py")] + arglar, cwd=KOK, env=ORTAM,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", creationflags=GIZLI)


def video_isi(v):
    diller = v["diller"]
    IS.update(calisiyor=True, log=[], ciktilar=[], hata=False, yuzde=0, asama="Başlıyor…", proje=v["ad"])
    arg = [os.path.join(proje_klasoru(v["ad"]), "video.yaml"), "--dil", ",".join(diller), "--format", v["format"]]
    if v.get("kalite") == "taslak":
        arg.append("--taslak")
    if v.get("yeniden"):
        arg.append("--yeniden")
    if v.get("muzik") is not None:
        arg += ["--muzik", v["muzik"] or "yok"]
    if v.get("muzik_ses") is not None:
        arg += ["--muzik-ses", str(v["muzik_ses"])]
    if v.get("altyazi"):
        arg.append("--altyazi")
    t0 = time.time()
    p = calistir(arg)
    SURUC["p"] = p
    bitti_dil, plan, yapilan = 0, {}, {}
    def guncelle():
        top = sum(plan.values())
        oran = (sum(yapilan.values()) / top) if top else 0.0
        IS["yuzde"] = round(100 * (bitti_dil + 0.92 * oran) / len(diller), 1)
    for satir in p.stdout:
        satir = satir.rstrip()
        if not satir:
            continue
        m = re.match(r"^\[(\w+) / (\w+)\]", satir)
        if m:
            plan, yapilan = {}, {}
            IS["asama"] = f"{m.group(1).upper()} dili: sahneler çiziliyor"
        if satir.startswith("PLAN "):
            plan = {k: v_ for k, v_ in json.loads(satir[5:]).items()}
            yapilan = {k: 0 for k in plan}
            guncelle(); continue
        if satir.startswith("ILERLEME "):
            _, no, i, n = satir.split()
            yapilan[no] = int(i); plan.setdefault(no, int(n))
            guncelle(); continue
        if "çizim süresi" in satir:
            IS["asama"] = "Ses ve müzik ekleniyor…"
        IS["log"].append(satir)
        if "HAZIR:" in satir:
            IS["ciktilar"].append(satir.split("HAZIR:", 1)[1].strip())
            bitti_dil += 1; plan, yapilan = {}, {}
            guncelle()
    kod = p.wait()
    SURUC["p"] = None
    if kod != 0:
        IS["hata"] = True
        IS["asama"] = "Durduruldu" if IS.get("durduruldu") else "Hata oluştu — ayrıntı için kayıtlara bak"
    else:
        IS["yuzde"] = 100
        IS["asama"] = f"Bitti ({time.time() - t0:.0f} sn)"
    IS["durduruldu"] = False
    IS["calisiyor"] = False


def durdur():
    p = SURUC.get("p")
    if not p:
        return
    IS["durduruldu"] = True
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], creationflags=GIZLI, capture_output=True)
    else:
        p.terminate()


def klasor_ac(yol):
    if os.name == "nt":
        os.startfile(yol)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", yol])
    else:
        subprocess.Popen(["xdg-open", yol])


def tts_post(komut, v):
    """Chatterbox ile ilgili POST istekleri."""
    if komut == "kur":                 # ilk kurulum ve güncelleme aynı yoldan geçer
        tts.kur_baslat(); return {"tamam": True}
    if komut == "geri":
        return {"surum": tts.geri_al()}
    if komut == "durdur":
        tts.durdur(); return {"tamam": True}
    if komut == "ayar":
        return {"ayar": tts.ayar_kaydet(v)}
    if komut == "ses_ayar":
        tts.ses_ayari_kaydet(v["id"], v["hiz"], v["duraklama"]); return {"tamam": True}
    if komut == "ses_olc":   # kaydın temposunu ölçüp önerilen hız/duraklamayı uygula
        yol = tts.HAZIR_ORNEK if v["id"] == "hazir" else tts.ses_ornegi(v["id"])
        o = tts.tempo_onerisi(tts.konusma_temposu(yol) if yol else None)
        tts.ses_ayari_kaydet(v["id"], o["hiz"], o["duraklama"]); return o
    if komut == "ses_sil":
        tts.ses_sil(v["id"]); return {"tamam": True}
    if komut == "ses_ad":
        tts.ses_yeniden_adlandir(v["id"], v["ad"]); return {"tamam": True}
    if komut == "ses_turet":
        return {"id": tts.ses_turet(v["id"], v["oran"])}
    if komut == "ses_sec":
        tts.ses_sec(proje_klasoru(v["ad"]), v["dil"], v["id"], bool(v.get("varsayilan"))); return {"tamam": True}
    if komut == "sablon":
        tts.sablon_baslat(); return {"tamam": True}
    if komut == "cevir":     # seslendirme metinlerini ve ekrandaki yazıları başka dillere çevir
        ad, kaynak = v["ad"], v["kaynak"]
        hedefler = [h for h in v.get("hedefler") or [] if h in ceviri.DILLER and h != kaynak]
        if kaynak not in ceviri.DILLER or not hedefler:
            raise ValueError("Kaynak ve en az bir hedef dil seç.")
        klasor = proje_klasoru(ad)
        proje = yaml.safe_load(open(os.path.join(klasor, "video.yaml"), encoding="utf-8").read())
        isler = ceviri.isler(klasor, proje, kaynak, hedefler, bool(v.get("hepsi")))
        tts.ceviri_baslat(isler, kaynak, lambda h, t, a, m: ceviri.yaz(klasor, kaynak, h, t, a, m), ceviri.DIL_AD)
        return {"tamam": True, "sayi": len(isler)}
    if komut in ("metin_duzelt", "ceviri_duzelt"):   # seslendirme metni pencereden düzeltildi
        if v["dil"] not in ceviri.DILLER or not re.fullmatch(r"\d+", str(v["no"])):
            raise ValueError("Geçersiz istek")
        return {"tamam": True, "yer": metin_duzelt(v["ad"], v["dil"], int(v["no"]), " ".join(str(v["metin"]).split()))}
    if komut == "kontrol":   # mevcut seslendirmeleri Whisper ile dinle, senaryoyla karşılaştır
        ad, dil = v["ad"], v["dil"]
        o = ozet(open(os.path.join(proje_klasoru(ad), "video.yaml"), encoding="utf-8").read(), ad)
        var = anlatim_durumu(ad).get(dil, {})
        k = os.path.join(proje_klasoru(ad), "ses", dil)
        metin = lambda s: str((s.get("anlatim") or {}).get(dil) or "").strip()
        isler = []
        for s in o.get("sahneler", []):
            b = var.get("sahneler", {}).get(str(s["no"]))
            if b and (v.get("hepsi") or not b.get("kontrol")):
                isler.append((os.path.join(k, b["dosya"]), metin(s), f"Sahne {s['no']}"))
        if var.get("tam") and (v.get("hepsi") or not var["tam"].get("kontrol")):
            isler.append((os.path.join(k, var["tam"]["dosya"]), "\n\n".join(metin(s) for s in o["sahneler"] if metin(s)), "Tüm video"))
        if not isler and not v.get("hepsi"):
            raise ValueError("Bütün sesler zaten kontrol edilmiş. Yeniden kontrol için 'Hepsini yeniden kontrol et'.")
        tts.kontrol_baslat(proje_klasoru(ad), dil, isler)
        return {"tamam": True, "sayi": len(isler)}
    if komut == "uret":
        ad, dil, hedef = v["ad"], v["dil"], v["hedef"]
        o = ozet(open(os.path.join(proje_klasoru(ad), "video.yaml"), encoding="utf-8").read(), ad)
        if o.get("hata"):
            raise ValueError(o["hata"])
        var = anlatim_durumu(ad).get(dil, {}).get("sahneler", {})
        metin = lambda s: str((s.get("anlatim") or {}).get(dil) or "").strip()
        if hedef == "tam":
            tum = "\n\n".join(metin(s) for s in o["sahneler"] if metin(s))
            isler = [("tam", tum, "Tüm video")] if tum else []
        else:
            isler = [(f"{s['no']:02d}", metin(s), f"Sahne {s['no']}") for s in o["sahneler"] if metin(s) and (
                hedef == "hepsi" or hedef == f"{s['no']:02d}" or (hedef == "eksik" and (
                    str(s["no"]) not in var or var[str(s["no"])].get("metin") not in (None, metin(s)))))]
        tts.uret_baslat(proje_klasoru(ad), dil, isler)
        return {"tamam": True, "sayi": len(isler)}
    raise ValueError("Bilinmeyen komut")


# ------------------------------------------------------------------ sunucu
class Isleyici(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def gonder(self, kod, veri, tur="application/json; charset=utf-8"):
        if not isinstance(veri, (bytes, bytearray)):
            veri = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(veri)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(veri)

    def dosya_gonder(self, yol):
        tur = mimetypes.guess_type(yol)[0] or "application/octet-stream"
        if yol.endswith(".js"): tur = "text/javascript"
        boyut = os.path.getsize(yol)
        aralik = self.headers.get("Range")
        with open(yol, "rb") as f:
            if aralik and (m := re.match(r"bytes=(\d*)-(\d*)", aralik)):
                a = int(m.group(1) or 0); b = int(m.group(2)) if m.group(2) else boyut - 1
                b = min(b, boyut - 1); f.seek(a); veri = f.read(b - a + 1)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {a}-{b}/{boyut}")
            else:
                veri = f.read(); self.send_response(200)
        self.send_header("Content-Type", tur)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(veri)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(veri)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def govde(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/favicon.ico":
                return self.gonder(204, b"")
            if u.path == "/":
                return self.gonder(200, SAYFA.encode("utf-8"), "text/html; charset=utf-8")
            if u.path.startswith("/k/"):      # motor ve proje dosyaları (önizleme için)
                yol = os.path.realpath(os.path.join(KOK, unquote(u.path[3:])))
                if not yol.startswith(os.path.realpath(KOK)) or not os.path.isfile(yol):
                    return self.gonder(404, {"hata": "yok"})
                return self.dosya_gonder(yol)
            if u.path == "/dosya":
                yol = os.path.realpath(q["yol"])
                if not yol.startswith(os.path.realpath(PROJELER)) or not os.path.isfile(yol):
                    return self.gonder(404, {"hata": "dosya yok"})
                return self.dosya_gonder(yol)
            if u.path == "/api/storyboard":
                return self.gonder(200, storyboard_oku(q["ad"]))
            if u.path == "/api/projeler":
                return self.gonder(200, {"projeler": projeler()})
            if u.path == "/api/proje":
                metin = open(os.path.join(proje_klasoru(q["ad"]), "video.yaml"), encoding="utf-8").read()
                return self.gonder(200, dict(ozet(metin, q["ad"]), metin=metin, sesler=sesler(q["ad"]), ciktilar=ciktilar(q["ad"]),
                                             anlatim_dosyalar=anlatim_durumu(q["ad"])))
            if u.path == "/api/anlatim":
                return self.gonder(200, {"anlatim": anlatim_durumu(q["ad"])})
            if u.path == "/api/ciktilar":
                return self.gonder(200, {"ciktilar": ciktilar(q["ad"])})
            if u.path == "/api/durum":
                return self.gonder(200, IS)
            if u.path == "/api/guncelleme":      # GitHub'da yeni sürüm var mı?
                return self.gonder(200, guncelleme.kontrol(q.get("zorla") == "1"))
            if u.path == "/api/guncelleme/durum":
                return self.gonder(200, dict(guncelleme.IS, surum=guncelleme.yerel_surum()))
            if u.path == "/api/tts/durum":     # Chatterbox durumu (kontrol=1: güncellemeye bak, 2: hemen bak)
                return self.gonder(200, tts.durum(int(q.get("kontrol", 0)), ses_suresi,
                                                 proje_klasoru(q["ad"]) if q.get("ad") else None, q.get("dil")))
            if u.path == "/api/tts/yenilikler":
                return self.gonder(200, {"liste": tts.yenilikler()})
            if u.path.startswith("/tts-ses/"):     # ses kütüphanesindeki örnekler (dinlemek için)
                sid = unquote(u.path[9:])
                yol = tts.HAZIR_ORNEK if sid == "_hazir" else tts.ses_ornegi(sid)
                return self.dosya_gonder(yol) if yol and os.path.isfile(yol) else self.gonder(404, {"hata": "yok"})
            self.gonder(404, {"hata": "yok"})
        except Exception as e:
            self.gonder(400, {"hata": str(e)})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/yukle":     # seslendirme dosyası yükleme (ham veri)
                q = {k: v_[0] for k, v_ in parse_qs(u.query).items()}
                dil, hedef, uz = q["dil"], q["hedef"], q.get("uzanti", ".mp3").lower()
                if not re.fullmatch(r"\w+", dil) or not re.fullmatch(r"tam|\d{2}", hedef) or uz not in ANLATIM_UZ:
                    return self.gonder(400, {"hata": "Geçersiz dosya"})
                n = int(self.headers.get("Content-Length", 0))
                if n > 200 * 1024 * 1024:
                    return self.gonder(400, {"hata": "Dosya çok büyük"})
                veri = self.rfile.read(n)
                anlatim_sil(q["ad"], dil, hedef)
                k = os.path.join(proje_klasoru(q["ad"]), "ses", dil)
                os.makedirs(k, exist_ok=True)
                yol = os.path.join(k, hedef + uz)
                with open(yol, "wb") as f:
                    f.write(veri)
                return self.gonder(200, {"tamam": True, "sure": ses_suresi(yol)})
            if u.path == "/api/tts/ses_yukle":   # ses kütüphanesine yeni ses (ham veri)
                q = {k: v_[0] for k, v_ in parse_qs(u.query).items()}
                uz = q.get("uzanti", ".wav").lower()
                if uz not in tts.REF_UZ:
                    return self.gonder(400, {"hata": "Desteklenmeyen dosya türü"})
                n = int(self.headers.get("Content-Length", 0))
                if n > 100 * 1024 * 1024:
                    return self.gonder(400, {"hata": "Dosya çok büyük"})
                return self.gonder(200, {"id": tts.ses_ekle(q.get("ad", ""), uz, self.rfile.read(n))})
            v = self.govde()
            if u.path.startswith("/api/tts/"):
                return self.gonder(200, tts_post(u.path[9:], v))
            if u.path == "/api/sigdir":     # sahne başına: sesi sahneye nasıl sığdıralım
                from motor import sigdir
                if not re.fullmatch(r"\w+", v["dil"]) or not re.fullmatch(r"\d{2}", v["hedef"]) or v["mod"] not in sigdir.MODLAR:
                    return self.gonder(400, {"hata": "Geçersiz istek"})
                sigdir.kaydet(proje_klasoru(v["ad"]), v["dil"], v["hedef"], v["mod"]); return self.gonder(200, {"tamam": True})
            if u.path == "/api/anlatim_sil":
                anlatim_sil(v["ad"], v["dil"], v["hedef"]); return self.gonder(200, {"tamam": True})
            if u.path == "/api/kaydet":
                o = ozet(v["metin"], v["ad"])
                with open(os.path.join(proje_klasoru(v["ad"]), "video.yaml"), "w", encoding="utf-8", newline="\n") as f:
                    f.write(v["metin"])
                return self.gonder(200, o)
            if u.path == "/api/storyboard":
                if IS["calisiyor"]:
                    return self.gonder(200, {"hata": "Şu an video oluşturuluyor; bitince tekrar dene."})
                p = calistir([os.path.join(proje_klasoru(v["ad"]), "video.yaml"), "--storyboard", "--dil", v["dil"]])
                cikti, _ = p.communicate(timeout=900)
                if not re.search(r"^STORYBOARD \S", cikti, re.M):
                    return self.gonder(200, {"hata": (cikti.strip().splitlines() or ["Bilinmeyen hata"])[-1]})
                return self.gonder(200, storyboard_oku(v["ad"]))
            if u.path == "/api/kare":
                p = calistir([os.path.join(proje_klasoru(v["ad"]), "video.yaml"), "--kare", str(float(v["t"])),
                              "--dil", v["dil"], "--format", v.get("format", "dikey")])
                cikti, _ = p.communicate(timeout=180)
                m = re.search(r"Kare kaydedildi:\s*(.+)", cikti)
                if not m:
                    return self.gonder(200, {"hata": (cikti.strip().splitlines() or ["Bilinmeyen hata"])[-1]})
                return self.gonder(200, {"url": "/dosya?yol=" + quote(m.group(1).strip()) + f"&v={time.time()}", "ad": os.path.basename(m.group(1).strip())})
            if u.path == "/api/olustur":
                if IS["calisiyor"]:
                    return self.gonder(200, {"hata": "Zaten bir video oluşturuluyor."})
                threading.Thread(target=video_isi, args=(v,), daemon=True).start()
                return self.gonder(200, {"tamam": True})
            if u.path == "/api/durdur":
                durdur(); return self.gonder(200, {"tamam": True})
            if u.path == "/api/yeni":
                ad = v["ad"].strip().lower().replace(" ", "-")
                hedef = proje_klasoru(ad)
                if os.path.exists(hedef):
                    return self.gonder(200, {"hata": "Bu isimde bir proje zaten var."})
                if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,60}", ad):
                    return self.gonder(200, {"hata": "Proje adında yalnızca küçük harf, rakam ve tire olsun (örn: piri-reis)."})
                kaynak = v.get("kaynak") if v.get("kopya") and v.get("kaynak") in projeler() else None
                if not kaynak:      # tek sahnelik boş bir başlangıç, seçilen tarzda
                    bos_proje_yaz(hedef, ad, v.get("stil", "vektor"), v.get("dil"))
                    return self.gonder(200, {"ad": ad})
                shutil.copytree(proje_klasoru(kaynak), hedef, ignore=shutil.ignore_patterns("cikti", "ses"))
                yol = os.path.join(hedef, "video.yaml")
                metin = re.sub(r"(?m)^ad:.*$", f"ad: {ad}", open(yol, encoding="utf-8").read(), count=1)
                open(yol, "w", encoding="utf-8", newline="\n").write(metin)
                return self.gonder(200, {"ad": ad})
            if u.path == "/api/guncelleme":     # yeni sürümü indir, kur, stüdyoyu yeniden başlat
                mesgul = "Önce süren video işinin bitmesini bekle." if IS["calisiyor"] else \
                    "Önce süren seslendirme işinin bitmesini bekle." if tts.IS.get("calisiyor") else None
                try:
                    guncelleme.baslat(mesgul)
                except ValueError as e:
                    return self.gonder(200, {"hata": str(e)})

                def bekle():
                    while guncelleme.IS["calisiyor"]:
                        time.sleep(0.3)
                    if guncelleme.IS["bitti"]:
                        time.sleep(2.0)          # arayüz "kuruldu" mesajını görsün
                        guncelleme.yeniden_baslat(kapat)
                threading.Thread(target=bekle, daemon=True).start()
                return self.gonder(200, {"tamam": True})
            if u.path == "/api/kapat":     # stüdyoyu kapat (Mac'te pencere olmadan çalışırken)
                durdur(); tts.durdur()
                threading.Thread(target=kapat, daemon=True).start()
                return self.gonder(200, {"tamam": True})
            if u.path == "/api/ac":
                yol = KOK if v.get("alt") == ".." else os.path.join(proje_klasoru(v["ad"]), v.get("alt", ""))
                os.makedirs(yol, exist_ok=True)
                klasor_ac(yol)
                return self.gonder(200, {"tamam": True})
            self.gonder(404, {"hata": "yok"})
        except Exception as e:
            self.gonder(400, {"hata": str(e)})


SAYFA = r"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8"><title>Animasyon Stüdyosu</title>
<style>
@font-face{font-family:"Plex";src:url(/k/fontlar/arayuz/plex-latin-400.woff2) format("woff2");font-weight:400;unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:"Plex";src:url(/k/fontlar/arayuz/plex-latin-500.woff2) format("woff2");font-weight:500;unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:"Plex";src:url(/k/fontlar/arayuz/plex-latin-600.woff2) format("woff2");font-weight:600;unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:"Plex";src:url(/k/fontlar/arayuz/plex-latin-ext-400.woff2) format("woff2");font-weight:400;unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:"Plex";src:url(/k/fontlar/arayuz/plex-latin-ext-500.woff2) format("woff2");font-weight:500;unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:"Plex";src:url(/k/fontlar/arayuz/plex-latin-ext-600.woff2) format("woff2");font-weight:600;unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
:root{--bg:#141516;--p1:#1c1d1f;--p2:#242628;--p3:#2f3235;--line:#35383c;--text:#e9e7e2;--muted:#9b9993;
--gold:#edb14c;--coral:#e8695d;--teal:#62b6a8;--violet:#edb14c;--green:#78c48d;--r:6px}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--text);font:13.5px/1.45 "Plex","Segoe UI",system-ui,sans-serif;display:flex;flex-direction:column;overflow:hidden;-webkit-font-smoothing:antialiased}
b,strong{font-weight:600}
button,select,input,textarea{font:inherit;color:var(--text)}
:focus-visible{outline:2px solid var(--gold);outline-offset:1px}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:#3a3d41;border-radius:5px;border:2px solid transparent;background-clip:content-box}::-webkit-scrollbar-track{background:transparent}
.btn{background:var(--p2);border:1px solid var(--line);border-radius:var(--r);padding:6px 12px;cursor:pointer;font-weight:500;display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.btn:hover{background:var(--p3);border-color:#484c51}.btn:active{background:#393c40}.btn:disabled{opacity:.45;cursor:default;background:var(--p2)}
.btn.ana{background:var(--gold);color:#1d1503;border-color:var(--gold);font-weight:600}.btn.ana:hover{background:#f5c165;border-color:#f5c165}.btn.ana:disabled{background:var(--gold)}
.btn.kirmizi{background:transparent;border-color:#6d3a36;color:#f0a39b}.btn.kirmizi:hover{background:#3a2422}
.btn.kucuk{padding:4px 9px;font-size:12.5px}
.btn.duz{background:transparent;border-color:transparent;color:var(--muted)}.btn.duz:hover{color:var(--text);background:var(--p2)}
select{background:var(--p2);border:1px solid var(--line);border-radius:var(--r);padding:6px 8px}
input[type=text],input:not([type]){background:var(--p2);border:1px solid var(--line);border-radius:var(--r);padding:6px 8px}
input[type=checkbox]{accent-color:var(--gold);width:15px;height:15px;margin:0;flex:none}
header{display:flex;align-items:center;gap:8px;padding:0 14px;height:50px;flex:none;border-bottom:1px solid var(--line);background:var(--p1)}
.logo{font-weight:600;font-size:15px;margin-right:14px;display:flex;align-items:center;gap:9px;white-space:nowrap}
.logo i{width:20px;height:20px;border-radius:5px;background:var(--gold);display:grid;place-items:center}.logo i::after{content:"";border-left:7px solid #1d1503;border-top:4.5px solid transparent;border-bottom:4.5px solid transparent;margin-left:2px}
.ayrac{width:1px;height:22px;background:var(--line);margin:0 6px}
.dilSec{display:inline-flex;border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.dilSec button{background:transparent;border:0;padding:5px 9px;cursor:pointer;font-size:12.5px;font-weight:500;color:var(--muted)}.dilSec button.secili{background:var(--p3);color:var(--text)}
.bosluk{flex:1}
main{flex:1;display:grid;grid-template-columns:264px 1fr 348px;min-height:0}
.panel{background:var(--p1);padding:14px;display:flex;flex-direction:column;min-height:0}
main>.panel:first-child{border-right:1px solid var(--line)}main>.panel:last-child{border-left:1px solid var(--line)}
.panel h3{margin:0 0 12px;font-size:13.5px;color:var(--text);font-weight:600}
#sahneler{overflow:auto;display:flex;flex-direction:column;margin:0 -14px}
.sahne{border-left:3px solid transparent;padding:9px 14px 9px 11px;cursor:pointer;display:grid;grid-template-columns:22px 1fr auto;gap:10px;align-items:center}
.sahne:hover{background:var(--p2)}.sahne.aktif{background:var(--p2);border-left-color:var(--gold)}
.no{font-weight:500;color:var(--muted);font-variant-numeric:tabular-nums;text-align:right}
.sahne.aktif .no{color:var(--gold)}
.sb{font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.st{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.rozet{font-size:11.5px;color:var(--muted)}
.orta{display:flex;flex-direction:column;align-items:center;min-height:0;gap:14px;padding:18px 18px 14px;background:var(--bg)}
#ekran{position:relative;height:calc(100% - 104px);aspect-ratio:9/16;background:#000;border-radius:4px;overflow:hidden;outline:1px solid var(--line)}
#ekran iframe{position:absolute;inset:0;width:100%;height:100%;border:0;visibility:hidden}
#ekran iframe.gor{visibility:visible}
#ekran img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;display:none}
#ekranNot{position:absolute;left:10px;right:10px;bottom:10px;background:#000c;border-radius:4px;padding:7px 9px;font-size:12px;color:#d8d6d0;display:none}
.oynatici{width:min(720px,100%);display:flex;flex-direction:column;gap:9px}
.kontrol{display:flex;align-items:center;gap:8px}
#oynat{width:38px;height:32px;justify-content:center;padding:0;font-size:13px}
#zaman{font-variant-numeric:tabular-nums;color:var(--muted);min-width:110px;margin-left:4px}
#serit{position:relative;height:26px;border-radius:3px;overflow:hidden;cursor:pointer;display:flex;background:var(--p2)}
#serit .parca{height:100%;border-right:1px solid var(--bg);display:flex;align-items:center;justify-content:center;font-size:11.5px;font-weight:500;color:#ffffff99;overflow:hidden;white-space:nowrap}
#imlec{position:absolute;top:0;bottom:0;width:2px;background:var(--gold);pointer-events:none}
.sec{display:inline-flex;flex-wrap:wrap;border:1px solid var(--line);border-radius:var(--r);overflow:hidden;background:var(--p2)}
.sec label{padding:5px 12px;cursor:pointer;user-select:none;font-weight:500;font-size:13px;color:var(--muted);border-right:1px solid var(--line)}
.sec label:last-child{border-right:0}
.sec input{display:none}.sec label:has(input:checked){color:var(--text);background:var(--p3);box-shadow:inset 0 -2px 0 var(--gold)}
.alan{margin-bottom:14px}.alan>div:first-child{font-size:12.5px;color:var(--muted);margin-bottom:6px}
.onay{display:flex;gap:9px;align-items:flex-start;margin:0 0 12px;cursor:pointer;font-size:12.5px;color:var(--muted);line-height:1.4}.onay input{margin-top:2px}.onay b{color:var(--text);font-weight:500;display:block}
input[type=range]{width:100%;accent-color:var(--gold)}
#ilerleme{height:4px;border-radius:2px;background:var(--p2);overflow:hidden;margin:12px 0 7px}
#ilerleme div{height:100%;width:0;background:var(--gold);transition:width .4s}
#asama{font-size:12.5px;color:var(--muted);min-height:20px}
#ciktilar{overflow:auto;display:flex;flex-direction:column;margin:0 -14px}
.cikti{padding:9px 14px;display:flex;align-items:center;gap:10px;border-top:1px solid var(--line)}
.cikti .ad{font-weight:500;font-size:13px;word-break:break-all}.cikti .bil{font-size:12px;color:var(--muted)}
.ipucu{font-size:12.5px;color:var(--muted)}
#perde{position:fixed;inset:0;background:#000000b3;display:none;align-items:center;justify-content:center;z-index:10;padding:28px}
#perde .kutu{background:var(--p1);border:1px solid var(--line);border-radius:8px;padding:16px;display:flex;flex-direction:column;gap:10px;max-height:100%;box-shadow:0 24px 80px #000a}
#perde textarea{width:min(900px,90vw);height:70vh;background:#111213;color:#dddbd5;border:1px solid var(--line);border-radius:var(--r);padding:12px;font:13px/1.5 Consolas,"Cascadia Mono",monospace;resize:none;white-space:pre}
#perde video{max-height:80vh;max-width:90vw;border-radius:4px;background:#000}
#bildirim{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(120px);background:#2c2e31;border:1px solid #45494e;padding:9px 14px;border-radius:var(--r);font-weight:500;transition:transform .2s;z-index:20;box-shadow:0 8px 30px #0008}
#bildirim.gor{transform:translateX(-50%)}#bildirim.hata{border-color:var(--coral);color:#f5b3ab}
.anl{width:min(1040px,92vw);max-height:78vh;overflow:auto;display:flex;flex-direction:column;padding-right:6px}
.anlS{padding:14px 0;display:grid;grid-template-columns:1fr 264px;gap:18px;align-items:start;border-top:1px solid var(--line)}
#perde textarea.anlYaz{width:100%;height:auto;min-height:58px;border:1px solid var(--line);color:inherit;font-size:14.5px;line-height:1.5;font-family:inherit;resize:vertical;box-sizing:border-box;white-space:pre-wrap;padding:9px 11px;field-sizing:content;background:#151617}
#perde textarea.anlYaz:hover{border-color:#4a4e53}#perde textarea.anlYaz:focus{border-color:var(--gold);outline:none}
.anlMetin{background:#151617;border-radius:var(--r);padding:9px 11px;font-size:14.5px;line-height:1.5;white-space:pre-wrap;min-height:44px}
.anlDurum{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.anlDurum>div,.anlDurum>label{flex-basis:100%}.anlDurum select{flex:1;min-width:0;padding:4px 6px;font-size:12.5px}
.tamam{color:var(--green);font-weight:500}.uyari{color:#e9bd6f;font-size:12.5px}
.sbIzgara{width:min(1180px,94vw);max-height:76vh;overflow:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;padding-right:6px}
.sbKart{background:var(--p2);border-radius:var(--r);padding:10px;display:flex;flex-direction:column;gap:7px}
.sbKart .ust{display:flex;align-items:center;gap:8px}.sbKart .no{min-width:18px;text-align:left;color:var(--gold);font-weight:600}
.sbKareler{display:grid;grid-template-columns:1fr 1fr;gap:6px}.sbKareler div{position:relative}.sbKareler img{width:100%;border-radius:3px;display:block;cursor:pointer;background:#000;aspect-ratio:9/16;object-fit:cover}
.sbKareler span{position:absolute;left:5px;top:5px;font-size:11.5px;background:#000b;border-radius:3px;padding:1px 6px}
.sbBos{aspect-ratio:9/16;border-radius:3px;background:#151617;display:grid;place-items:center;color:var(--muted);font-size:12px;text-align:center;padding:8px}
.sbNot{font-size:12.5px;color:#cfcdc7;line-height:1.45}.sbNot b{color:var(--muted);font-weight:500}
.ttsBar{background:var(--p2);border-radius:var(--r);padding:10px 12px;display:flex;flex-direction:column;gap:8px}
.ttsSatir{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.ttsIler{height:4px;border-radius:2px;background:#151617;overflow:hidden}.ttsIler div{height:100%;background:var(--gold);transition:width .4s}
.ttsAyar{display:grid;grid-template-columns:1fr 1fr;gap:18px;border-top:1px solid var(--line);padding:12px 0 2px}
.refSatir{display:flex;align-items:center;gap:8px;margin-top:6px}.refSatir b{min-width:70px}
.kay{display:grid;grid-template-columns:190px 1fr;gap:2px 10px;align-items:center;margin-bottom:6px;font-size:13px}.kay .ipucu{grid-column:2}
.kayitK{background:#111213;border-radius:var(--r);padding:8px;font:11.5px/1.45 Consolas,"Cascadia Mono",monospace;color:#b3b1ab;max-height:160px;overflow:auto;white-space:pre-wrap}
.yeniList{background:#151617;border-radius:var(--r);padding:8px 12px;font-size:13px;max-height:160px;overflow:auto}
#ttsRozet{display:none;background:var(--gold);color:#1d1503;border-radius:3px;font-size:11px;font-weight:600;padding:0 5px;margin-left:2px}
#mikPerde{position:fixed;inset:0;background:#000000b3;display:none;align-items:center;justify-content:center;z-index:15}
#mikPerde .kutu{background:var(--p1);border:1px solid var(--line);border-radius:8px;padding:18px;width:min(760px,94vw);display:flex;flex-direction:column;gap:12px}
.okuMetin{background:#151617;border-radius:var(--r);padding:16px 18px;font-size:18px;line-height:1.6}
.seviye{height:8px;border-radius:4px;background:var(--p2);overflow:hidden}.seviye div{height:100%;width:0;background:var(--green);transition:width .08s}
#mikSure{font-weight:600;font-size:24px;line-height:1;font-variant-numeric:tabular-nums;min-width:90px}
.kirmiziNokta{display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--coral);animation:yanip 1s infinite}@keyframes yanip{50%{opacity:.25}}
#kayit{display:none;background:#111213;border-radius:var(--r);padding:8px;font:11.5px/1.45 Consolas,"Cascadia Mono",monospace;color:#b3b1ab;max-height:140px;overflow:auto;white-space:pre-wrap;margin-top:6px}
.stiller{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.stil{display:flex;flex-direction:column;gap:6px;padding:8px;border:1px solid var(--line);border-radius:var(--r);cursor:pointer;background:var(--p2)}
.stil:hover{border-color:#4a4e53}.stil:has(input:checked){border-color:var(--gold);box-shadow:inset 0 0 0 1px var(--gold)}
.stil input{display:none}.stil img{width:100%;aspect-ratio:9/12;object-fit:cover;object-position:center 30%;border-radius:3px;background:#000;image-rendering:auto}
.stil b{font-size:13.5px}.stil .ipucu{font-size:12px;line-height:1.4}
.kilavuz{width:min(760px,92vw);max-height:80vh;overflow:auto;padding-right:10px;font-size:14px;line-height:1.6}
.kilavuz h2{font-size:20px;font-weight:600;margin:0 0 4px}.kilavuz h4{font-size:15px;font-weight:600;margin:22px 0 6px;display:flex;gap:10px;align-items:baseline}
.kilavuz h4 span{color:var(--gold);font-variant-numeric:tabular-nums;min-width:16px}
.kilavuz p{margin:0 0 8px;color:#d2d0ca;max-width:68ch}.kilavuz ul{margin:0 0 8px;padding-left:26px;color:#d2d0ca;max-width:66ch}.kilavuz li{margin-bottom:3px}
.kilavuz .ornek{background:#151617;border-left:2px solid var(--gold);padding:9px 12px;margin:8px 0 10px 26px;font-size:13.5px;color:var(--text);max-width:62ch;display:flex;gap:10px;align-items:flex-start}
.kilavuz .ornek span{flex:1}.kilavuz kbd{background:var(--p3);border-radius:3px;padding:0 5px;font:inherit;font-size:12.5px}
</style></head><body>
<header>
 <div class="logo"><i></i>Animasyon Stüdyosu</div>
 <select id="proje" title="Proje"></select>
 <button class="btn duz" onclick="yeniProje()">Yeni proje</button>
 <span class="bosluk"></span>
 <button class="btn" onclick="storyboardAc()" title="Video çizmeden her sahnenin ana karelerini numaralı olarak gör">Storyboard</button>
 <button class="btn" onclick="seslendirme()">Seslendirme<span id="ttsRozet" title="Chatterbox için güncelleme var">güncelleme</span></button>
 <button class="btn" onclick="duzenleyici()" title="video.yaml dosyasını elle düzenle (gelişmiş)">Senaryo</button>
 <button class="btn" onclick="ac('')">Proje klasörü</button>
 <span class="ayrac"></span>
 <button class="btn duz" onclick="kilavuz()">Kılavuz</button>
 <span class="dilSec" title="Arayüz dili / Interface language"><button id="dilTR" onclick="dilSec('tr')">TR</button><button id="dilEN" onclick="dilSec('en')">EN</button></span>
 <button class="btn duz" onclick="studyoKapat()" title="Stüdyoyu kapat">Çıkış</button>
</header>
<main>
 <section class="panel"><h3>Sahneler</h3><div id="sahneler"></div></section>
 <section class="orta">
  <div id="ekran"><img id="kare"><div id="ekranNot"></div></div>
  <div class="oynatici">
   <div class="kontrol">
    <button class="btn" id="oynat" onclick="oynatDurdur()" title="Oynat / durdur (Boşluk)">▶</button>
    <span id="zaman">0.0 / 0.0 sn</span><span class="bosluk"></span>
    <button class="btn kucuk" onclick="kareKaydet()" title="Şu anki kareyi resim olarak kaydet (kapak resmi için)">Kareyi kaydet</button>
    <select id="onizDil" title="Önizleme dili" style="padding:4px 6px;font-size:12.5px"></select>
    <button class="btn kucuk" id="sesBtn" onclick="sesAcKapa()">Ses açık</button>
   </div>
   <div id="serit"><div id="imlec"></div></div>
  </div>
 </section>
 <section class="panel" style="overflow:auto">
  <h3>Video oluştur</h3>
  <div class="alan"><div>Diller</div><div class="sec" id="diller"></div></div>
  <div class="alan"><div>Format</div><div class="sec" id="formatlar"></div></div>
  <div class="alan"><div>Kalite</div><div class="sec">
   <label><input type="radio" name="kalite" value="normal" checked>Yüksek</label>
   <label><input type="radio" name="kalite" value="taslak">Hızlı taslak</label></div></div>
  <div class="alan"><div>Arka müzik</div><select id="muzik" style="width:100%"></select>
   <div style="display:flex;align-items:center;gap:10px;margin-top:8px"><span class="ipucu">Düzey</span><input type="range" id="muzikSes" min="0" max="100" value="35"><span id="muzikSesY" class="ipucu" style="width:36px;text-align:right">35%</span></div></div>
  <label class="onay"><input type="checkbox" id="altyazi" onchange="localStorage.setItem('altyazi',this.checked?1:0)">
   <span><b>Altyazıyı videoya göm</b>Konuşulan kelime sarı yanar. Whisper kontrolünden geçmiş seslerden çıkar; .srt dosyası her zaman yazılır.</span></label>
  <label class="onay" id="onceSesL"><input type="checkbox" id="onceSes" onchange="localStorage.setItem('onceSes',this.checked?1:0)">
   <span><b>Önce eksik sesleri üret</b>Sesi olmayan ya da metni değişmiş sahneler Chatterbox ile seslendirilir, sonra video çizilir.</span></label>
  <button class="btn ana" id="olusturBtn" style="justify-content:center;padding:10px;font-size:14.5px" onclick="olustur()">Video oluştur</button>
  <div id="ilerleme"><div></div></div>
  <div style="display:flex;align-items:center;gap:8px"><div id="asama">Hazır.</div><span class="bosluk"></span>
   <button class="btn kucuk kirmizi" id="durBtn" style="display:none" onclick="durdur()">Durdur</button>
   <button class="btn kucuk duz" onclick="kayit.style.display=kayit.style.display=='block'?'none':'block'">Kayıtlar</button></div>
  <div id="kayit"></div>
  <h3 style="margin-top:22px">Oluşturulan videolar</h3>
  <div id="ciktilar"></div>
 </section>
</main>
<div id="perde" onclick="if(event.target===this)perdeKapat()"><div class="kutu" id="perdeIc"></div></div>
<div id="mikPerde"><div class="kutu" id="mikIc"></div></div>
<div id="bildirim"></div>
<script>
const $=s=>document.querySelector(s);
// ---------------- arayüz dili (TR / EN) ----------------
// Arayüz Türkçe yazılır; İngilizce seçiliyken ekrandaki yazılar aşağıdaki sözlükle çevrilir.
let DIL=localStorage.getItem('dil')||((navigator.language||'tr').toLowerCase().startsWith('tr')?'tr':'en');
const EN={
"Animasyon Stüdyosu":"Animation Studio","İndiriliyor…":"Downloading…","Dosyalar açılıyor…":"Unpacking…","Yeni dosyalar yerleştiriliyor…":"Installing the new files…","Gerekli paketler güncelleniyor…":"Updating the required packages…",
"Bu klasör git ile yönetiliyor; güncellemek için git pull kullan.":"This folder is managed with git; use git pull to update.","Önce süren video işinin bitmesini bekle.":"Wait for the running video job to finish first.","Önce süren seslendirme işinin bitmesini bekle.":"Wait for the running voice-over job to finish first.","Güncelleme zaten sürüyor.":"An update is already running.","Piksel":"Pixel","Piksel art":"Pixel art","Tarz: Claude bu projenin sahnelerini seçtiğin tarzda yazar.":"Style: Claude writes this project's scenes in the style you choose.",
"Proje adı (küçük harf, rakam ve tire; örn: piri-reis)":"Project name (lowercase letters, numbers and dashes, for example: piri-reis)","Oluştur":"Create",
"Düz renkli, yumuşak hareketli 2D çizimler. Açıklayıcı videolar için en esnek tarz.":"Flat-colour 2D drawings with smooth motion. The most flexible style for explainers.",
"Yumuşak ışıklı, gölgeli 3D sahneler: gezegenler, nesneler, maketler. Çizimi biraz daha uzun sürer.":"Softly lit 3D scenes with shadows: planets, objects, miniatures. Takes a little longer to render.",
"Eski oyunlar gibi piksel piksel çizilmiş sahneler ve karakterler. Hikâye ve tarih anlatımına uygun.":"Scenes and characters drawn pixel by pixel like classic games. Suits stories and history.",
"Tarz seçimi yerine şu anki projenin sahneleri ve metinleri kopyalanır (sesler ve videolar hariç).":"Copies the current project's scenes and text instead of using a style (audio and videos are not copied).",
"Proje adında yalnızca küçük harf, rakam ve tire olsun (örn: piri-reis).":"Use only lowercase letters, numbers and dashes in the project name (for example: piri-reis).","Önce bir proje aç ya da Yeni proje ile oluştur.":"Open a project first, or create one with New project.","Henüz proje yok. Kılavuz, Claude ile ilk videonun nasıl hazırlanacağını anlatır. Boş bir projeyle başlamak için Yeni proje.":"No projects yet. The Guide explains how to prepare your first video with Claude. To start from an empty project, use New project.","Yeni proje":"New project","güncelleme":"update","Proje klasörü":"Project folder","Kılavuz":"Guide","Kapat":"Close","Çıkış":"Quit","Seslendirme":"Voice-over","Senaryo":"Script","Sahneler":"Scenes",
"Kareyi kaydet":"Save frame","Ses açık":"Sound on","Ses kapalı":"Sound off","Video oluştur":"Make video","Diller":"Languages","Kalite":"Quality","Yüksek":"High","Hızlı taslak":"Quick draft",
"Dikey 9:16":"Vertical 9:16","Yatay 16:9":"Wide 16:9","Kare 1:1":"Square 1:1","Arka müzik":"Background music","Düzey":"Level","Müzik yok":"No music",
"Altyazıyı videoya göm":"Burn subtitles into the video","Konuşulan kelime sarı yanar. Whisper kontrolünden geçmiş seslerden çıkar; .srt dosyası her zaman yazılır.":"The spoken word lights up yellow. Built from audio that passed the Whisper check; an .srt file is always written.",
"Önce eksik sesleri üret":"Generate missing audio first","Sesi olmayan ya da metni değişmiş sahneler Chatterbox ile seslendirilir, sonra video çizilir.":"Scenes with no audio or changed text are voiced with Chatterbox, then the video is rendered.",
"Hazır.":"Ready.","Durdur":"Stop","■ Durdur":"■ Stop","Kayıtlar":"Logs","Oluşturulan videolar":"Finished videos","Henüz video yok.":"No videos yet.","Klasörde göster":"Show in folder",
"Vektör":"Vector","Çizgi film":"Cartoon","Harita":"Map","Resim":"Image","Kart":"Card",
"Çeviri":"Translation","Kaynak:":"From:","+ dil ekle":"+ add language","Önceki çevirileri yenile":"Redo existing translations","Çevirmeye başla":"Start translating","Çevir":"Translate",
"Seslendirme metinleri ve ekrandaki yazılar bilgisayarında çevrilir (ilk seferde ~8 GB model iner). Senaryoda zaten yazılı olan diller değişmez. Çeviriden sonra o dilde Eksikleri üret.":"Voice-over lines and on-screen text are translated on your computer (the first run downloads a ~8 GB model). Languages already written in the script stay as they are. After translating, switch to that language and press Generate missing.",
"Sahne sahne (önerilen)":"Per scene (recommended)","Tek dosya":"Single file","Tek dosyayı üret":"Generate the file","Eksikleri üret":"Generate missing","Hepsini yeniden":"Regenerate all","Whisper kontrolü":"Whisper check",
"Üret, metni Chatterbox ile bilgisayarında seslendirir. Başka bir araçta ürettiğin sesi Yükle ile ekleyebilirsin (mp3, wav, m4a). Sesler önizlemede ve videoda kendiliğinden çalar.":"Generate voices the text on your computer with Chatterbox. Audio made in another tool can be added with Upload (mp3, wav, m4a). Audio plays automatically in the preview and the video.",
"Başka bir araçta ürettiğin sesi Yükle ile ekleyebilirsin (mp3, wav, m4a). Sesler önizlemede ve videoda kendiliğinden çalar.":"Audio made in another tool can be added with Upload (mp3, wav, m4a). It plays automatically in the preview and the video.",
"Yükle":"Upload","Kopyala":"Copy","Sil":"Delete","▶ Dinle":"▶ Play","Ses yok":"No audio","Yeniden üret":"Regenerate","Chatterbox ile üret":"Generate with Chatterbox",
"Sığdır:":"Fit:","Otomatik (≤%20 hızlan)":"Automatic (speed up ≤20%)","Hızlandır (≤%40)":"Speed up (≤40%)","Sahneyi uzat":"Lengthen the scene",
"✎ Metin değişti, ses eski":"✎ Text changed, audio is outdated","Tüm videonun metni":"Text of the whole video","Metin yok.":"No text.",
"Tek dosyada konuşma sahnelerle tam eşleşmeyebilir. Sahne sahne yüklemek daha iyi senkron sağlar.":"With a single file the speech may drift from the scenes. Per-scene audio keeps better sync.",
"Not: sahne sesleri de var; ikisi birlikte çalar. Birini silmen önerilir.":"Note: there is per-scene audio too, and both will play. Delete one of them.",
"Chatterbox durumu alınıyor…":"Checking Chatterbox…",
"Bilgisayarında ücretsiz çalışan yapay zeka seslendirme (TR, EN, PL, PT, ES ve 18 dil daha). Tek tıkla kurulur: ~10 GB yer, ilk kurulum 15-30 dk.":"Free AI voice-over that runs on your computer (TR, EN, PL, PT, ES and 18 more languages). One-click install: ~10 GB of disk, 15–30 minutes the first time.",
"Chatterbox'u kur":"Install Chatterbox","Güncelle":"Update","Neler değişti?":"What changed?","Güncelleme kontrol edilemedi":"Could not check for updates","✓ Güncel":"✓ Up to date","Önceki sürüm":"Previous version","Güncellemeye bak":"Check for updates","Ses ayarları":"Voice settings",
"bu projeye özel":"for this project","varsayılan":"default","Varsayılan yap":"Make default","Daha fazla ses için Ses ayarları → şablon oluştur ya da kendi kaydını yükle":"For more voices open Voice settings: create the presets or add your own recording",
"Son kurduğundan beri değişenler:":"Changes since your installed version:","Liste boş.":"Nothing listed.","Kayıt yok.":"No log entries.",
"Ses kütüphanesi":"Voice library","Mikrofonla kaydet":"Record with microphone","Dosyadan ekle":"Add from file","Hazır şablonları oluştur":"Create the preset voices","Kopya":"Variant","Ad":"Rename",
"Kendi kaydın için 10-20 sn net, müziksiz, tek kişilik konuşma yeter. Chatterbox o sesle (cinsiyet, kalınlık, tarz) konuşur; en iyi sonuç için kayıt seslendirilecek dilde olsun. Kopya, bir sesin daha kalın ya da ince hâlini çıkarır. Yalnızca kendi sesini ya da izni olan sesleri kullan.":"For your own voice, 10–20 seconds of clear speech by one person with no music is enough. Chatterbox then speaks in that voice (gender, pitch, style); record in the language you will narrate in for best results. Variant makes a deeper or higher copy of a voice. Only use your own voice or voices you have permission for.",
"(bu sese özel)":"(for this voice only)","Konuşma hızı":"Speaking speed","Cümle arası duraklama (sn)":"Pause between sentences (s)","1 = Chatterbox'ın kendi hızı · 0.8 = %20 daha yavaş (ton bozulmaz)":"1 = Chatterbox's own pace, 0.8 = 20% slower (pitch is kept)","Her cümleden sonra bırakılan sessizlik":"Silence left after each sentence",
"Bu ses için kaydet":"Save for this voice","Kayda göre ayarla":"Match my recording","Üretince Whisper ile kontrol et (altyazı zamanları da çıkar)":"Check with Whisper after generating (also gives subtitle timing)","Kelime atlanmışsa bir kez otomatik yeniden üret":"If a word was skipped, regenerate once automatically",
"En yenisi önerilir":"The newest is recommended","Ayarları kaydet":"Save settings",
"Ses örneği kaydet":"Record a voice sample","Sessiz bir odada, mikrofona bir karış uzaklıkta, video anlatır gibi doğal bir tonla aşağıdaki metni oku. 15-25 saniye idealdir (en fazla 30 sn). Seslendirilecek dilde kayıt en iyi sonucu verir.":"In a quiet room, about a hand's width from the microphone, read the text below in the natural tone you would narrate a video in. 15–25 seconds is ideal (30 at most). Recording in the narration language gives the best result.",
"Mikrofon":"Microphone","Konuşunca çubuk yeşil-sarı arasında oynamalı.":"While you speak the bar should move through its middle range.","Yeniden kaydet":"Record again","Kaydı başlat":"Start recording","✓ Kütüphaneye ekle":"✓ Add to library","Vazgeç":"Cancel","İptal":"Cancel",
"Çok yüksek, ses bozulabilir: mikrofondan biraz uzaklaş.":"Too loud, the sound may distort: move back from the microphone a little.","Çok sessiz: biraz daha yüksek sesle konuş ya da mikrofona yaklaş.":"Too quiet: speak up a little or move closer to the microphone.","Ses seviyesi iyi ✓":"Level is good ✓",
"geçiş":"transition","orta":"middle","çiziliyor…":"rendering…","Kare yok":"No frame","Sahne dosyası yok":"Scene file missing","Ekranda:":"On screen:","Hareket:":"Motion:","Sonrakine geçiş:":"Transition to next:",
"Ana kareler çiziliyor, video çizilmiyor (birkaç saniye – 1 dk)…":"Rendering key frames only, not the video (a few seconds to a minute)…","Her sahnenin ortasından ve geçiş anından birer kare. Notlar için \"4'ten 5'e geçiş olmadı\" gibi numarayla söyle.":"One frame from the middle of each scene and one at its transition. Refer to scenes by number in your notes, for example \"the cut from 4 to 5 doesn't work\".",
"Kareleri yeniden çıkar":"Render frames again","Tek sayfa":"One page","Senaryo (video.yaml)":"Script (video.yaml)","Ctrl+S ile kaydet. Tüm seçenekler: bos_sablon.yaml":"Save with Ctrl+S. All options: bos_sablon.yaml","Kaydet":"Save",
"Stüdyo kapatıldı.":"The studio is closed.","Bu sekmeyi kapatabilirsin. Tekrar açmak için Animasyon Stüdyosu simgesine tıkla.":"You can close this tab. To open it again, click the Animation Studio icon.",
"Proje":"Project","Video çizmeden her sahnenin ana karelerini numaralı olarak gör":"See numbered key frames of every scene without rendering the video","Chatterbox için güncelleme var":"An update is available for Chatterbox","video.yaml dosyasını elle düzenle (gelişmiş)":"Edit video.yaml by hand (advanced)","Stüdyoyu kapat":"Quit the studio","Oynat / durdur (Boşluk)":"Play / pause (Space)","Şu anki kareyi resim olarak kaydet (kapak resmi için)":"Save the current frame as an image (for a thumbnail)","Önizleme dili":"Preview language",
"İşaretli değilse sadece eksik çeviriler yapılır; senin düzelttiklerin korunur":"When unchecked only missing translations are made and your corrections are kept","Sesi olmayan ve metni değişmiş sahneleri seslendirir":"Voices scenes that have no audio or whose text changed","Sesleri Whisper ile dinler, senaryoyla karşılaştırır ve altyazı zamanlarını çıkarır. Shift+tık: hepsini yeniden kontrol et":"Listens to the audio with Whisper, compares it with the script and extracts subtitle timing. Shift+click: check everything again","Seslendirme metinlerini ve ekrandaki yazıları bilgisayarında başka dillere çevirir":"Translates voice-over lines and on-screen text into other languages on your computer",
"Ses sahneden uzunsa ne yapılsın? Ses dosyası değişmez; hız videoda ve önizlemede uygulanır.":"What to do when the audio is longer than the scene. The audio file is not changed; speed is applied in the video and the preview.","Ses, metnin önceki hâlinden üretilmiş. Eksikleri üret bu sahneyi de yeniler.":"This audio was made from an earlier version of the text. Generate missing will redo this scene too.","Videodaki hızıyla çalar":"Plays at the speed used in the video",
"Bu sahne için metin yok. Buraya yazabilirsin ya da Çevir ile başka bir dilden çevrilir.":"No text for this scene. Type it here, or use Translate to bring it over from another language.","Metni burada düzeltebilirsin; kutudan çıkınca kaydedilir":"Edit the text here; it saves when you leave the box",
"Dinle / durdur":"Play / stop","Bu sesin kalın ya da ince bir kopyasını oluştur":"Make a deeper or higher copy of this voice","Yeniden adlandır":"Rename","Ses örneğindeki konuşma hızını ölçer ve ona göre ayarlar":"Measures the speaking pace of the sample and sets the values to match","Önizlemede bu sahneye git":"Go to this scene in the preview",
"Metin kaydedildi ✓":"Text saved ✓","En az bir dil seç.":"Pick at least one language.","Not: vektör sahneler dikey için tasarlandı; diğer formatlarda kenarlar boş kalır.":"Note: vector scenes are designed for vertical video; other formats leave empty edges.","Video oluşturulamadı. \"Kayıtlar\"a bak.":"The video could not be made. See Logs.","Video hazır.":"The video is ready.","Kare çıkarılıyor…":"Rendering the frame…","Metin kopyalandı":"Text copied","Kopyalanamadı, metni elle seç":"Could not copy; select the text by hand","Yükleniyor…":"Uploading…",
"Bu ses dosyası silinsin mi?":"Delete this audio file?","Bu dildeki tüm sahne sesleri (elle yüklediklerin dahil) Chatterbox ile yeniden üretilecek. Devam?":"All scene audio in this language (including files you uploaded) will be regenerated with Chatterbox. Continue?","Bu sahnenin mevcut sesi yenisiyle değiştirilecek. Devam?":"This scene's current audio will be replaced. Continue?","Durduruluyor…":"Stopping…","Güncelleme kontrol ediliyor…":"Checking for updates…",
"Bir önceki Chatterbox sürümüne dönülsün mü? (Tekrar basarsan yeni sürüme geri gelir.)":"Go back to the previous Chatterbox version? (Press again to return to the new one.)","Ses ayarları kaydedildi":"Voice settings saved","Bu sese bir isim ver (örn: Benim sesim, Kadın anlatıcı, Kalın erkek):":"Name this voice (for example: My voice, Female narrator, Deep male):","Ses yükleniyor…":"Uploading the voice…",
"Ses ayarı kaydedildi. Yeni üretimlerde kullanılacak; mevcut sesleri \"Yeniden üret\" ile güncelleyebilirsin.":"Saved. New audio will use it; update existing audio with Regenerate.","Yeni isim:":"New name:","Ne kadar kalın ya da ince olsun?\n\n0.80 = çok daha kalın · 0.90 = biraz kalın · 1.10 = biraz ince · 1.20 = çok daha ince":"How deep or high should it be?\n\n0.80 = much deeper, 0.90 = a little deeper, 1.10 = a little higher, 1.20 = much higher",
"Yeni ses oluşturuldu ✓ Listeden dinleyebilirsin":"New voice created ✓ You can play it from the list","Chatterbox'un hazır sesinden bir örnek kaydedilip ondan kalın, çok kalın ve ince şablon sesler türetilecek. Birkaç dakika sürer. Devam?":"A sample of Chatterbox's built-in voice will be recorded and deep, very deep and high presets made from it. This takes a few minutes. Continue?",
"Mikrofon bağlı değil":"No microphone connected","Kaydediliyor…":"Saving…","Ses seçildi ✓":"Voice selected ✓","Storyboard hazır ✓":"Storyboard is ready ✓","Yeni projenin adı (Türkçe karakter ve boşluk olmadan, örn: piri-reis):":"Name of the new project (no spaces or special letters, for example: piri-reis):","Stüdyo kapatılsın mı? (Süren video ya da seslendirme işi durdurulur.)":"Quit the studio? (A running render or voice-over job will be stopped.)","Kaydedildi":"Saved",
"Bu sahne türü canlı oynatılmaz — sahnenin ilk karesi gösteriliyor.":"This scene type has no live preview; its first frame is shown.","Varsayılan ses ayarlandı ✓":"Default voice set ✓","Ses seçildi. Yeni üretimlerde bu ses kullanılacak.":"Voice selected. New audio will use it.",
// sunucudan gelenler
"Geçersiz proje adı":"Invalid project name","Dosyada 'sahneler:' listesi bulunamadı.":"The file has no 'sahneler:' list.","Sahne bulunamadı":"Scene not found","Metin boş olamaz":"The text cannot be empty","Metin boş olamaz (sahneyi sessiz bırakmak için Senaryo'dan satırı sil).":"The text cannot be empty (to leave the scene silent, remove the line in Script).","Bu metin senaryoda tek satır olarak bulunamadı; Senaryo penceresinden düzenle.":"This text was not found as a single line in the script; edit it in the Script window.",
"Başlıyor…":"Starting…","Ses ve müzik ekleniyor…":"Adding audio and music…","Durduruldu":"Stopped","Durdu.":"Stopped.","Kaynak ve en az bir hedef dil seç.":"Pick a source and at least one target language.","Geçersiz istek":"Invalid request","Bütün sesler zaten kontrol edilmiş. Yeniden kontrol için 'Hepsini yeniden kontrol et'.":"All audio has already been checked. Shift+click Whisper check to check everything again.",
"Geçersiz dosya":"Invalid file","Dosya çok büyük":"The file is too large","Desteklenmeyen dosya türü":"Unsupported file type","Şu an video oluşturuluyor; bitince tekrar dene.":"A video is being made; try again when it finishes.","Zaten bir video oluşturuluyor.":"A video is already being made.","Bu isimde bir proje zaten var.":"A project with this name already exists.","Kopyalanacak proje yok.":"There is no project to copy.",
"Geçersiz ses":"Invalid voice","Ses bulunamadı":"Voice not found","Oran 0.6 ile 1.5 arasında olmalı (0.85 = daha kalın, 1.1 = daha ince).":"The ratio must be between 0.6 and 1.5 (0.85 = deeper, 1.1 = higher).","Hazır sesin örneği henüz yok. Önce 'Hazır şablonları oluştur'a bas.":"There is no sample of the built-in voice yet. Press Create the preset voices first.",
"Seslendirme motoru beklenmedik şekilde kapandı. Ayrıntı için Kayıtlar'a bak.":"The voice engine closed unexpectedly. See Logs for details.","Chatterbox şu an başka bir iş yapıyor, bitmesini bekle.":"Chatterbox is busy with another job; wait for it to finish.","Kurulum aracı (uv) hazırlanıyor…":"Preparing the installer (uv)…","Kurulum aracı (uv) kurulamadı. İnternet bağlantını kontrol et.":"The installer (uv) could not be set up. Check your internet connection.",
"Chatterbox'un en son sürümü bulunuyor…":"Finding the latest Chatterbox version…","Ayrı Python 3.11 ortamı hazırlanıyor…":"Preparing a separate Python 3.11 environment…","Python 3.11 ortamı oluşturulamadı.":"The Python 3.11 environment could not be created.","Kurulum kontrol ediliyor (ekran kartı testi)…":"Verifying the install (graphics card test)…",
"Kurulum tamamlanamadı. Ayrıntı için Kayıtlar'a bak. Eski sürümün olduğu gibi duruyor.":"The install did not finish. See Logs for details. Your previous version is untouched.","Yeni sürüm devreye alınıyor…":"Switching to the new version…","Kurulum durduruldu. Mevcut sürüm (varsa) olduğu gibi duruyor.":"Install stopped. The current version, if any, is untouched.","Hata":"Error","Önce süren işin bitmesini bekle.":"Wait for the running job to finish first.","Geri dönülecek önceki sürüm yok.":"There is no previous version to go back to.",
"Whisper yükleniyor… (ilk seferde ~1,6 GB iner)":"Loading Whisper… (the first run downloads ~1.6 GB)","Whisper, Chatterbox'ın ortamını kullanır: önce Chatterbox'u kur.":"Whisper uses Chatterbox's environment: install Chatterbox first.","Kontrol edilecek ses yok.":"There is no audio to check.","Motor başlatılıyor…":"Starting the engine…","Kontrol durduruldu.":"Check stopped.",
"Çeviri, Chatterbox'ın ortamını kullanır: önce Chatterbox'u kur.":"Translation uses Chatterbox's environment: install Chatterbox first.","Çevrilecek yeni metin yok (hepsi zaten çevrilmiş ya da senaryoda yazılı).":"Nothing new to translate (everything is already translated or written in the script).","Çeviri modeli yükleniyor… (ilk seferde ~8 GB iner)":"Loading the translation model… (the first run downloads ~8 GB)","Çeviri durduruldu.":"Translation stopped.",
"Chatterbox kurulu değil.":"Chatterbox is not installed.","Üretilecek metin yok (sesi olmayan ve metni olan sahne bulunamadı).":"Nothing to generate (no scene has text but no audio).","Seslendirme motoru başlatılıyor…":"Starting the voice engine…","Hazır sesin örneği kaydediliyor…":"Recording a sample of the built-in voice…","Şablon sesler hazır ✓ Dinleyip beğendiklerine istediğin adı verebilirsin.":"Preset voices are ready ✓ Listen and rename the ones you like.","Model yükleniyor… (ilk seferde ~3 GB iner, birkaç dakika sürebilir)":"Loading the model… (the first run downloads ~3 GB and can take a few minutes)",
"Örneğe bağlılık / tempo":"Closeness to the sample / pace","Örnek hızlı konuşuyorsa ya da başka dildeyse 0.3 dene":"Try 0.3 if the sample speaks fast or is in another language","Duygu / canlılık":"Emotion / liveliness","0.5 doğal · 0.7+ daha coşkulu":"0.5 is natural, 0.7 and up is more animated","Çeşitlilik":"Variation","Düşük = daha düz ve tutarlı":"Lower is flatter and more consistent",
"Hazır ses (Chatterbox)":"Built-in voice (Chatterbox)","Hazır ses · ince":"Built-in voice, higher","Hazır ses · kalın":"Built-in voice, deeper","Hazır ses · çok kalın":"Built-in voice, much deeper","şablon":"preset","hazır":"built-in","Arayüz dili / Interface language":"Interface language",
"Türkçe":"Turkish","İngilizce":"English","Lehçe":"Polish","Portekizce":"Portuguese","İspanyolca":"Spanish","Almanca":"German","Fransızca":"French","İtalyanca":"Italian","Felemenkçe":"Dutch","Rusça":"Russian","Arapça":"Arabic","Japonca":"Japanese","Korece":"Korean","Çince":"Chinese","Hintçe":"Hindi","İsveççe":"Swedish","Danca":"Danish","Fince":"Finnish","Norveççe":"Norwegian","Yunanca":"Greek","İbranice":"Hebrew","Malayca":"Malay","Svahili":"Swahili"
};
const EN_K=[
[/^(\d+(?:\.\d+)?) \/ (\d+(?:\.\d+)?) sn$/,"$1 / $2 s"],[/^(\d+(?:\.\d+)?)–(\d+(?:\.\d+)?) sn(?: · ses ×([\d.]+))?$/,(m,a,b,o)=>`${a}–${b} s`+(o?` · audio ×${o}`:'')],[/^(\d+(?:\.\d+)?) sn$/,"$1 s"],
[/^(\d+) kelime$/,(m,n)=>n+(n==='1'?' word':' words')],[/^\/ en fazla ~(\d+)$/,"/ about $1 at most"],[/^sahne (\d+(?:\.\d+)?) sn ·$/,"scene $1 s ·"],[/^· makine çevirisi$/,"· machine translation"],
[/^video (\d+(?:\.\d+)?) sn · en fazla ~(\d+) kelime$/,"video $1 s · about $2 words at most"],[/^Sahne (\d+)$/,"Scene $1"],[/^(.*) \(proje\)$/,"$1 (project)"],[/^(.*) projesini kopyala$/,"Copy the project $1"],
[/^✓ Ses var · ([\d.]+) sn$/,"✓ Audio · $1 s"],[/^Ses sahneden uzun: ×([\d.]+) hızlandırıldı, videoda bu sahne ([\d.]+) sn olur\.$/,"Audio is longer than the scene: sped up ×$1, and the scene becomes $2 s in the video."],[/^Ses sahneden uzun: videoda bu sahne ([\d.]+) sn olur\.$/,"Audio is longer than the scene: the scene becomes $1 s in the video."],[/^Sahneye sığdırıldı \(ses ×([\d.]+)\)$/,"Fitted to the scene (audio ×$1)"],
[/^(✓|⚠) Whisper %(\d+)(?: · eksik: (.*))?$/,(m,i,y,e)=>`${i} Whisper ${y}%`+(e?` · missing: ${e}`:'')],[/^Eksikleri üret \((\d+)\)$/,"Generate missing ($1)"],
[/^Kaydedildi: (.*)$/,"Saved: $1"],[/^(\d+) metin çevriliyor…$/,"Translating $1 texts…"],[/^Proje oluşturuldu: ?(.*)$/,"Project created: $1"],[/^Ses yüklendi ✓ \((.*)$/,"Audio uploaded ✓ ($1"],[/^Önceki sürüme dönüldü \((.*)$/,"Back on the previous version ($1"],
[/^Kayda göre ayarlandı: hız ([\d.]+), duraklama ([\d.]+) sn$/,"Matched to the recording: speed $1, pause $2 s"],[/^Kayıt kısa \((\d+) sn\)\. En az 10-15 sn önerilir; istersen yeniden kaydet\.$/,"The recording is short ($1 s). At least 10–15 s is recommended; record again if you like."],
[/^"(.*)" kütüphaneye eklendi ✓\n\nBu projenin (\w+) seslendirmesinde (?:şimdi )?bu ses kullanılsın mı\?$/,'"$1" was added to the library ✓\n\nUse this voice for this project\'s $2 voice-over?'],[/^"(.*)" sesi kütüphaneden silinsin mi\? \(Daha önce üretilmiş seslendirmeler silinmez\.\)$/,'Delete the voice "$1" from the library? (Audio already generated is kept.)'],
[/^(\w+) sesi:$/,"$1 voice:"],[/^Seçili ses: (.*)$/,(m,a)=>"Selected voice: "+cev(a)],[/^● (.*)$/,(m,a)=>"● "+cev(a)],[/^([^()]+) \((\w\w)\)$/,(m,a,b)=>EN[a]?`${EN[a]} (${b})`:m],[/^Yeni sürüm var \((.*)\)$/,"New version available ($1)"],[/^sürüm (.*)$/,"version $1"],[/^Son işlem: (.*)$/,(m,a)=>"Last job: "+cev(a)],
[/^Chatterbox ["'](\w+)["'] dilini desteklemiyor(?:; bu dil için sesi elle yükle)?\.$/,'Chatterbox does not support "$1"; upload audio for this language by hand.'],[/^Yeni projelerde de (\w+) için bu ses kullanılsın$/,"Use this voice for $1 in new projects too"],[/^Bir önceki kurulu sürüme dön(.*)$/,"Return to the previously installed version$1"],
[/^Sesin adı \(örn: Benim sesim (\w+)\)$/,"Voice name (for example: My voice $1)"],[/^Mikrofon (\d+)$/,"Microphone $1"],[/^(geçiş|orta) ([\d.]+s)?$/,(m,a,b)=>(a==='orta'?'middle ':'transition ')+(b||'')],
[/^(\w+): (\d+) sahne seslendiriliyor…$/,"$1: voicing $2 scenes…"],[/^(\w+) seslendirme: (.*)$/,(m,d,a)=>`${d} voice-over: ${cev(a)}`],
[/^(\w+) dili: sahneler çiziliyor(.*)$/,"$1: rendering scenes$2"],[/^Bitti \((\d+) sn\)$/,"Done ($1 s)"],[/^Bitti ✓ (\d+) ses üretildi$/,"Done ✓ $1 audio files generated"],[/^Durduruldu \((\d+)\/(\d+) hazır\)\.$/,"Stopped ($1/$2 ready)."],
[/^(.*) seslendiriliyor \((\d+)\/(\d+)\)…$/,"Voicing $1 ($2/$3)…"],[/^(.*) Whisper ile kontrol ediliyor…$/,"Checking $1 with Whisper…"],[/^(.*) yeniden üretiliyor \(kelime atlanmış\)…$/,"Regenerating $1 (a word was skipped)…"],[/^(.*) dinleniyor \((\d+)\/(\d+)\)…$/,"Listening to $1 ($2/$3)…"],
[/^Kontrol bitti ✓ ?(.*)$/,"Check finished ✓ $1"],[/^Çevriliyor \((\d+)\/(\d+)\)…$/,"Translating ($1/$2)…"],[/^Çeviri bitti ✓ (\d+) metin\. Gözden geçirip istersen düzelt\.$/,"Translation finished ✓ $1 texts. Read them through and correct where needed."],
[/^Chatterbox (güncellendi|kuruldu) ✓ \(sürüm (.*)\)$/,(m,a,b)=>`Chatterbox ${a==='kuruldu'?'installed':'updated'} ✓ (version ${b})`],[/^Şablon hazırlanıyor: (.*)$/,"Preparing preset: $1"],[/^GitHub'a ulaşılamadı \((.*)\)$/,"Could not reach GitHub ($1)"],
[/^Senaryo dosyasında yazım hatası(.*)\. Genelde girinti \(boşluk\) ya da eksik tırnak\/parantez sebep olur\.$/,"Syntax error in the script file$1. The usual cause is indentation or a missing quote or bracket."],
[/^Mikrofona erişilemedi\..*$/,"Could not access the microphone. Allow it from the microphone icon in the browser's address bar (on a Mac also under System Settings → Privacy & Security → Microphone), then open this again."],
[/^Stüdyo güncel ✓ \(sürüm (.*)\)$/,"The studio is up to date ✓ (version $1)"],[/^Sürüm (.*) kuruldu\. Stüdyo yeniden başlatılıyor…$/,"Version $1 installed. Restarting the studio…"],[/^Güncelleme yapılamadı: (.*)$/,"The update failed: $1"],[/^Güncelleme denetlenemedi \((.*)\)\.$/,"Could not check for updates ($1)."],[/^%(\d+) · (.*)$/,(m,y,a)=>`${y}% · ${cev(a)}`],[/^sahne (\d+)$/,"scene $1"],[/^Sahne (\d+): (.*)$/,"Scene $1: $2"],
];
function cev(m){ if(DIL==='tr'||m==null)return m; const ham=String(m), k=ham.trim(); if(!k)return m;
 let y=EN[k]; if(y===undefined){const d=k.replace(/[ \t\r]*\n[ \t]*/g,' ').replace(/ {2,}/g,' '); y=EN[d]}
 if(y===undefined)for(const [r,p] of EN_K){ if(r.test(k)){ y=k.replace(r,p); break } }
 return y===undefined?m:ham.replace(k,()=>y) }
function cevDugum(n){
 if(n.nodeType===3){ const y=cev(n.nodeValue); if(y!==n.nodeValue)n.nodeValue=y; return }
 if(n.nodeType!==1||n.tagName==='SCRIPT'||n.tagName==='STYLE'||n.tagName==='IFRAME'||n.classList.contains('ham'))return;
 for(const a of ['title','placeholder']){ const v=n.getAttribute(a); if(v){const y=cev(v); if(y!==v)n.setAttribute(a,y)} }
 if(n.tagName==='TEXTAREA')return;
 n.childNodes.forEach(cevDugum) }
function dilSec(d){ localStorage.setItem('dil',d); location.reload() }
function dilKur(){ document.documentElement.lang=DIL; if(DIL!=='tr')document.title='Animation Studio'; $('#dil'+DIL.toUpperCase()).classList.add('secili'); if(DIL==='tr')return;
 cevDugum(document.body);
 new MutationObserver(ms=>{ for(const m of ms){ if(m.type==='childList')m.addedNodes.forEach(cevDugum); else cevDugum(m.target) } })
  .observe(document.body,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['title','placeholder']});
 const o={confirm:window.confirm.bind(window),prompt:window.prompt.bind(window),alert:window.alert.bind(window)};
 window.confirm=m=>o.confirm(cev(m)); window.prompt=(m,v)=>o.prompt(cev(m),v); window.alert=m=>o.alert(cev(m)) }

// ---------------- kılavuz ----------------
const KILAVUZ={
tr:{baslik:"Kılavuz",giris:"Animasyon Stüdyosu, kısa animasyonlu videoları bilgisayarında üretir. Sahneleri Claude yazar; seslendirme, çeviri, altyazı ve video bu stüdyoda yapılır.",kopya:"Kopyala",kopyalandi:"Kopyalandı",klasor:"Stüdyo klasörünü aç",kapat:"Kapat",
adimlar:[
["Claude'u stüdyo klasörüne bağla",`<p>Animasyonları Claude yazar, bu yüzden Claude'un stüdyo klasörünü görmesi gerekir.</p><ul><li>Bilgisayarına Claude masaüstü uygulamasını kur ve hesabınla gir.</li><li>Yeni bir sohbet aç ve stüdyo klasörünü sohbete bağla. Klasörün yerini görmek için aşağıdaki düğmeyi kullan.</li><li>Claude klasördeki <kbd>CLAUDE.md</kbd> dosyasını okur; sahnelerin nasıl yazılacağı orada anlatılır.</li></ul>`],
["Konuyu söyle, storyboard'u onayla",`<p>Claude'a ne hakkında video istediğini yaz. Önce numaralı bir storyboard (sahne planı) önerir; beğenince sahneleri yazar ve projeyi <kbd>projeler</kbd> klasörüne koyar.</p><p>Yeni projeyi stüdyoda <b>Yeni proje</b> ile açarsan tarzını seçersin: <b>Vektör</b> (2D çizim), <b>3D</b> ya da <b>Piksel art</b>. Claude sahneleri o tarzda yazar.</p><div class="ornek"><span>Bu klasördeki animasyon stüdyosu için "Ahtapotların neden üç kalbi var?" konulu 40 saniyelik dikey bir video hazırla. Önce storyboard öner.</span></div><p>Düzeltme isterken sahne numarasıyla söyle: "3. sahnede yazı çok küçük", "4'ten 5'e geçiş sert".</p>`],
["Projeyi aç ve izle",`<ul><li>Sol üstteki listeden projeyi seç. Ortada canlı önizleme oynar.</li><li>Soldaki sahneye tıklayınca önizleme oraya atlar.</li><li><b>Storyboard</b>, video çizmeden her sahneden iki kare çıkarır. Claude'a geri bildirim vermenin en hızlı yolu budur.</li><li>Kısayollar: <kbd>Boşluk</kbd> oynat/durdur, <kbd>←</kbd> <kbd>→</kbd> 1 saniye, <kbd>↑</kbd> <kbd>↓</kbd> sahne.</li></ul>`],
["Seslendir",`<p><b>Seslendirme</b> penceresinde her sahnenin metni ve sesi durur.</p><ul><li>İlk seferde <b>Chatterbox'u kur</b> (yaklaşık 10 GB, bir kez).</li><li><b>Ses ayarları</b>'ndan bir ses seç ya da <b>Mikrofonla kaydet</b> ile kendi sesini ekle (15-25 saniye yeter).</li><li><b>Eksikleri üret</b> bütün sahneleri seslendirir. Whisper her sesi dinler; atlanan kelime varsa uyarır.</li><li>Metni kutuda düzeltebilirsin. Değişen sahne işaretlenir, <b>Eksikleri üret</b> onu yeniler.</li><li>Ses sahneden uzunsa <b>Sığdır</b> seçimi sesi biraz hızlandırır ya da sahneyi uzatır.</li><li>Konuşma hızlı ya da yavaş geliyorsa Ses ayarları'ndaki <b>Konuşma hızı</b> ve <b>duraklama</b> ile ayarla.</li></ul>`],
["Başka dillere çevir",`<p>Seslendirme penceresindeki <b>Çevir</b>, metinleri ve ekrandaki yazıları bilgisayarında çevirir (ilk seferde yaklaşık 8 GB model iner). Çeviriyi okuyup düzelt, sonra o dilde <b>Eksikleri üret</b>. Aynı ses bütün dillerde konuşur.</p>`],
["Videoyu oluştur",`<ul><li>Sağdaki panelde dilleri, formatı ve müziği seç.</li><li><b>Altyazıyı videoya göm</b> konuşulan kelimeyi vurgulayan altyazı ekler.</li><li><b>Video oluştur</b>'a bas. Eksik sesler varsa önce onlar üretilir.</li><li>Biten videolar aşağıda listelenir; dosyalar projenin <kbd>cikti</kbd> klasöründedir. Yanında YouTube için bir <kbd>.srt</kbd> altyazı dosyası da olur.</li><li>Denemeler için <b>Hızlı taslak</b>, yayın için <b>Yüksek</b> kaliteyi kullan.</li></ul>`],
["Kapatmak ve sorun çözmek",`<ul><li>Stüdyo arka planda çalışır. Tamamen kapatmak için sağ üstteki <b>Çıkış</b>'a bas.</li><li>Bir iş takılırsa ilgili paneldeki <b>Kayıtlar</b>'a bak.</li><li>Videoda eski görüntü kalırsa projeyi yeniden seç ve videoyu tekrar oluştur.</li><li>Arayüz dilini sağ üstteki <b>TR / EN</b> düğmesinden değiştirirsin.</li><li>Stüdyo açılırken yeni sürüm olup olmadığına bakar; varsa sorar, <b>Şimdi güncelle</b> dersen kendini günceller ve yeniden açılır. Projelerin ve seslerin korunur.</li></ul>`]]},
en:{baslik:"Guide",giris:"Animation Studio makes short animated videos on your computer. Claude writes the scenes; voice-over, translation, subtitles and the final video are made here in the studio.",kopya:"Copy",kopyalandi:"Copied",klasor:"Open the studio folder",kapat:"Close",
adimlar:[
["Connect Claude to the studio folder",`<p>Claude writes the animations, so it needs to see the studio folder.</p><ul><li>Install the Claude desktop app on your computer and sign in.</li><li>Start a new chat and connect the studio folder to it. Use the button below to find where the folder is.</li><li>Claude reads the <kbd>CLAUDE.md</kbd> file in the folder, which explains how scenes are written. (That file is in Turkish; Claude reads it fine.)</li></ul>`],
["Give the topic, approve the storyboard",`<p>Tell Claude what the video is about. It first proposes a numbered storyboard; once you are happy it writes the scenes and puts the project in the <kbd>projeler</kbd> folder.</p><p>If you create the project yourself with <b>New project</b>, you pick its style: <b>Vector</b> (2D drawing), <b>3D</b> or <b>Pixel art</b>. Claude writes the scenes in that style.</p><div class="ornek"><span>Using the animation studio in this folder, make a 40-second vertical video on "Why do octopuses have three hearts?". Write the narration in English. Propose a storyboard first.</span></div><p>When asking for changes, refer to scenes by number: "the text in scene 3 is too small", "the cut from 4 to 5 is abrupt".</p>`],
["Open the project and watch it",`<ul><li>Pick the project from the list at the top left. A live preview plays in the middle.</li><li>Click a scene on the left to jump to it.</li><li><b>Storyboard</b> renders two frames per scene without making the video. It is the quickest way to give Claude feedback.</li><li>Shortcuts: <kbd>Space</kbd> play/pause, <kbd>←</kbd> <kbd>→</kbd> one second, <kbd>↑</kbd> <kbd>↓</kbd> scene.</li></ul>`],
["Add the voice-over",`<p>The <b>Voice-over</b> window holds the text and audio of every scene.</p><ul><li>The first time, press <b>Install Chatterbox</b> (about 10 GB, once).</li><li>Pick a voice under <b>Voice settings</b>, or add your own with <b>Record with microphone</b> (15–25 seconds is enough).</li><li><b>Generate missing</b> voices every scene. Whisper listens to each one and warns you if a word was skipped.</li><li>You can edit the text in its box. A changed scene is flagged, and <b>Generate missing</b> redoes it.</li><li>If the audio is longer than its scene, <b>Fit</b> speeds it up slightly or lengthens the scene.</li><li>If the speech feels fast or slow, adjust <b>Speaking speed</b> and the <b>pause</b> in Voice settings.</li></ul>`],
["Translate into other languages",`<p><b>Translate</b> in the Voice-over window translates the lines and the on-screen text on your computer (the first run downloads a model of about 8 GB). Read the translation and correct it, then press <b>Generate missing</b> in that language. The same voice speaks every language.</p>`],
["Make the video",`<ul><li>Choose languages, format and music in the panel on the right.</li><li><b>Burn subtitles into the video</b> adds subtitles that highlight the spoken word.</li><li>Press <b>Make video</b>. Missing audio is generated first.</li><li>Finished videos are listed below; the files are in the project's <kbd>cikti</kbd> folder, with an <kbd>.srt</kbd> subtitle file for YouTube next to them.</li><li>Use <b>Quick draft</b> for tests and <b>High</b> quality for publishing.</li></ul>`],
["Quitting and fixing problems",`<ul><li>The studio runs in the background. To close it completely, press <b>Quit</b> at the top right.</li><li>If a job gets stuck, open <b>Logs</b> in that panel.</li><li>If the video shows an old picture, pick the project again and make the video again.</li><li>Change the interface language with the <b>TR / EN</b> switch at the top right.</li><li>When it opens, the studio checks for a new version. If there is one it asks; press <b>Update now</b> and it updates itself and restarts. Your projects and voices are kept.</li></ul>`]]}};
// ---------------- güncelleme ----------------
let GUN=null;
async function guncellemeDenetle(zorla){ const d=await api('/api/guncelleme'+(zorla?'?zorla=1':'')); GUN=d;
 if(zorla){ if(d.hata)return bildir(d.hata,1); if(d.mod==='git')return bildir(DIL==='tr'?'Bu klasör git ile yönetiliyor; güncellemek için git pull kullan.':'This folder is a git checkout; use git pull to update.'); if(!d.yeni)return bildir((DIL==='tr'?'Stüdyo güncel ✓ (sürüm ':'The studio is up to date ✓ (version ')+(d.surum||'?')+')') }
 if(d.yeni&&(zorla||sessionStorage.getItem('gunAtla')!==d.son))guncellemePenceresi(d) }
function guncellemePenceresi(d){ ANL_ACIK=false;
 const notlar=(d.notlar||[]).map(n=>`<div style="margin-top:10px"><b>${kac(n.surum)}</b>${n.tarih?` <span class="ipucu">${kac(n.tarih)}</span>`:''}<ul style="margin:4px 0 0;padding-left:20px">${(n[DIL]||n.tr||n.en||[]).map(x=>`<li>${kac(x)}</li>`).join('')}</ul></div>`).join('');
 $('#perdeIc').innerHTML=`<div class="ham" style="width:min(560px,90vw);display:flex;flex-direction:column;gap:10px">
  <h3 style="margin:0;font-size:16px">${DIL==='tr'?'Yeni sürüm hazır: '+kac(d.son):'A new version is ready: '+kac(d.son)}</h3>
  <div class="ipucu">${DIL==='tr'?'Şu an kullandığın: '+kac(d.surum)+'. Projelerin, seslerin ve ayarların korunur; yalnızca programın kendisi güncellenir.':'You are on '+kac(d.surum)+'. Your projects, voices and settings are kept; only the program itself is updated.'}</div>
  <div style="max-height:46vh;overflow:auto;font-size:13.5px;line-height:1.5">${notlar}</div>
  <div id="gunDurum" class="ipucu"></div>
  <div style="display:flex;gap:8px"><span class="bosluk"></span><button class="btn" id="gunSonra" onclick="sessionStorage.setItem('gunAtla','${kac(d.son)}');perdeKapat()">${DIL==='tr'?'Sonra':'Later'}</button>
  <button class="btn ana" id="gunBtn" onclick="guncelle()">${DIL==='tr'?'Şimdi güncelle':'Update now'}</button></div></div>`;
 $('#perde').style.display='flex' }
async function guncelle(){ const o=await api('/api/guncelleme',{}); if(o.hata)return bildir(o.hata,1);
 $('#gunBtn').disabled=true; $('#gunSonra').disabled=true; const yaz=m=>{const e=$('#gunDurum'); if(e)e.textContent=m};
 let bitti=false, eski=GUN&&GUN.surum;
 while(true){ await new Promise(r=>setTimeout(r,800));
  let d; try{ d=await (await fetch(bitti?'/api/guncelleme/durum?yeni=1':'/api/guncelleme/durum')).json() }catch(e){ yaz(DIL==='tr'?'Stüdyo yeniden başlatılıyor…':'Restarting the studio…'); continue }
  if(d.hata){ yaz(cev(d.hata)); $('#gunBtn').disabled=false; $('#gunSonra').disabled=false; return }
  if(d.bitti)bitti=true;
  if(bitti&&d.surum&&d.surum!==eski&&!d.calisiyor&&!d.bitti){ location.reload(); return }   // yeni süreç cevap veriyor
  yaz(cev(d.asama)) } }
function kilavuz(){ const k=KILAVUZ[DIL]; ANL_ACIK=false;
 $('#perdeIc').innerHTML=`<div class="kilavuz ham"><h2>${k.baslik}</h2><p>${k.giris}</p>`+
  k.adimlar.map(([b,g],i)=>`<h4><span>${i+1}</span>${b}</h4><div style="padding-left:26px">${g}</div>`).join('')+`</div>
  <div class="ham" style="display:flex;gap:8px;align-items:center"><button class="btn" onclick="api('/api/ac',{ad:'',alt:'..'})">${k.klasor}</button>
  ${GUN&&GUN.surum?`<span class="ipucu">${DIL==='tr'?'Sürüm':'Version'} ${kac(GUN.surum)}</span>${GUN.mod==='acik'?`<button class="btn duz kucuk" onclick="guncellemeDenetle(true)">${DIL==='tr'?'Güncellemeleri denetle':'Check for updates'}</button>`:''}`:''}<span class="bosluk"></span><button class="btn ana" onclick="perdeKapat()">${k.kapat}</button></div>`;
 document.querySelectorAll('.kilavuz .ornek').forEach(e=>{const b=document.createElement('button'); b.className='btn kucuk'; b.textContent=k.kopya;
  b.onclick=()=>navigator.clipboard.writeText(e.querySelector('span').textContent).then(()=>{b.textContent=k.kopyalandi}); e.appendChild(b)});
 $('#perde').style.display='flex'; localStorage.setItem('kilavuzGoruldu','1') }

let CEV_ACIK=false, CEV_YENI=[];
const CEV_DILLER={tr:'Türkçe',en:'İngilizce',pl:'Lehçe',pt:'Portekizce',es:'İspanyolca',de:'Almanca',fr:'Fransızca',it:'İtalyanca',nl:'Felemenkçe',ru:'Rusça',ar:'Arapça',ja:'Japonca',ko:'Korece',zh:'Çince',hi:'Hintçe',sv:'İsveççe',da:'Danca',fi:'Fince',no:'Norveççe',el:'Yunanca',he:'İbranice',ms:'Malayca',sw:'Svahili'};
function cevPanel(){ const kay=localStorage.getItem('cevKaynak'); const kaynak=P.diller.includes(kay)?kay:P.diller[0];
 const hedef=[...new Set([...P.diller,...CEV_YENI])].filter(x=>x!==kaynak);
 const diger=Object.keys(CEV_DILLER).filter(x=>!P.diller.includes(x)&&!CEV_YENI.includes(x));
 return `<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;background:var(--p2);border:1px solid var(--line);border-radius:6px;padding:10px 14px;margin:10px 0"><b>Çeviri</b>
  <label class="ipucu">Kaynak: <select id="cevKaynak" onchange="localStorage.setItem('cevKaynak',this.value);anlCiz()">${P.diller.map(x=>`<option value="${x}" ${x==kaynak?'selected':''}>${x.toUpperCase()}</option>`).join('')}</select></label>
  <span class="ipucu">→</span>${hedef.map(x=>`<label class="ipucu"><input type="checkbox" class="cevHedef" value="${x}" checked>${x.toUpperCase()}</label>`).join('')}
  ${diger.length?`<select onchange="if(this.value){CEV_YENI.push(this.value);anlCiz()}"><option value="">+ dil ekle</option>${diger.map(x=>`<option value="${x}">${CEV_DILLER[x]} (${x})</option>`).join('')}</select>`:''}
  <label class="ipucu" title="İşaretli değilse sadece eksik çeviriler yapılır; senin düzelttiklerin korunur"><input type="checkbox" id="cevHepsi">Önceki çevirileri yenile</label>
  <span class="bosluk"></span><button class="btn kucuk ana" id="cevGit" onclick="cevBaslat()">Çevirmeye başla</button>
  <div class="ipucu" style="flex-basis:100%">Seslendirme metinleri ve ekrandaki yazılar bilgisayarında çevrilir (ilk seferde ~8 GB model iner). Senaryoda zaten yazılı olan diller değişmez. Çeviriden sonra o dilde Eksikleri üret.</div></div>` }
async function cevBaslat(){ const hedefler=[...document.querySelectorAll('.cevHedef:checked')].map(e=>e.value);
 const o=await api('/api/tts/cevir',{ad:AD,kaynak:$('#cevKaynak').value,hedefler,hepsi:$('#cevHepsi').checked}); if(o.hata)return bildir(o.hata,1);
 bildir(o.sayi+' metin çevriliyor…'); CEV_ACIK=false; ttsIzle() }
// Seslendirme metnini pencereden düzeltme (senaryodaysa video.yaml'da, çeviriyse ceviri.json'da değişir)
let METIN_KAYIT=Promise.resolve();
const kelimeSay=m=>(String(m||'').trim().match(/\S+/g)||[]).length;
function kelimeYazi(m,sure){ const n=kelimeSay(m), en=Math.round(sure*2.0); return `<span style="${n>en*1.25?'color:var(--coral)':n>en?'color:var(--gold)':''}">${n} kelime</span> / en fazla ~${en}` }
function sesEski(b,m){ return !!(b&&b.metin!=null&&b.metin!==String(m||'').trim()) }
function eksikSes(dil){ const d=ANL[dil]||{sahneler:{}}; if(d.tam)return []; return P.sahneler.filter(s=>{const m=String(s.anlatim[dil]||'').trim(); const b=d.sahneler[String(s.no)]; return m&&(!b||sesEski(b,m))}) }
function metinDuzelt(no,el){ const dil=ANL_DIL, metin=el.value.replace(/\s+/g,' ').trim(); const s=P.sahneler.find(x=>x.no===no);
 if(!s||metin===String(s.anlatim[dil]||'').trim())return;
 METIN_KAYIT=METIN_KAYIT.then(async()=>{ const o=await api('/api/tts/metin_duzelt',{ad:AD,dil,no,metin});
  if(o.hata){bildir(o.hata,1); el.value=s.anlatim[dil]||''; return}
  s.anlatim=Object.assign({},s.anlatim,{[dil]:metin}); if(o.yer==='senaryo'){const p=await api('/api/proje?ad='+encodeURIComponent(AD)); if(!p.hata)P.metin=p.metin}
  bildir('Metin kaydedildi ✓'); if(ANL_ACIK&&document.activeElement.tagName!=='TEXTAREA')anlCiz() }); return METIN_KAYIT }
let ANL={}, ANL_SES=null, ANL_NO=null, ANL_DIL=null, ANL_MOD='sahne', ANL_ACIK=false;
let TTS_D=null, TTS_IZ=false, TTS_AYAR=false, TTS_LOG=false, TTS_YENI=null;
let P=null, AD=null, T=0, OYNUYOR=false, SON=0, SES=true, FORMAT='dikey', FRAMES={}, KARELER={}, MUZIK=null, SFX={};
async function api(y,v){const r=await fetch(y,v?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(v)}:{});return r.json()}
function bildir(m,h){const b=$('#bildirim');b.textContent=m;b.className='gor'+(h?' hata':'');clearTimeout(b._t);b._t=setTimeout(()=>b.className='',3500)}
const fmt=t=>t.toFixed(1);
function projeYok(){ if(P)return false; bildir('Önce bir proje aç ya da Yeni proje ile oluştur.',1); return true }
async function projeleriYukle(sec){const {projeler}=await api('/api/projeler');
 if(!projeler.length){ $('#sahneler').innerHTML='<div class="ipucu" style="padding:4px 14px;line-height:1.5">Henüz proje yok. Kılavuz, Claude ile ilk videonun nasıl hazırlanacağını anlatır. Boş bir projeyle başlamak için Yeni proje.</div>' }
 $('#proje').innerHTML=projeler.map(p=>`<option>${p}</option>`).join('');
 const son=sec||localStorage.getItem('sonProje'); if(son&&projeler.includes(son))$('#proje').value=son;
 await projeAc($('#proje').value)}
async function projeAc(ad){ if(!ad)return; durdurOyna(); AD=ad; localStorage.setItem('sonProje',ad);
 P=await api('/api/proje?ad='+encodeURIComponent(ad)); if(P.hata){bildir(P.hata,1);return}
 FORMAT=P.format||'dikey'; ANL=P.anlatim_dosyalar||{}; arayuzKur(); T=0; ciz(true)}
function arayuzKur(){
 const renk={vektor:'#a79be0',uc:'#e2a76f',piksel:'#78c48d',cizgi:'#62b6a8',harita:'#6f9fdc',resim:'#d99a5b',kart:'#d9778a'};
 const ad={vektor:'Vektör',uc:'3D',piksel:'Piksel',cizgi:'Çizgi film',harita:'Harita',resim:'Resim',kart:'Kart'};
 const onc=$('#onizDil').value; $('#onizDil').innerHTML=P.diller.map(d=>`<option>${d}</option>`).join(''); if(P.diller.includes(onc))$('#onizDil').value=onc;
 planHesapla();
 $('#diller').innerHTML=P.diller.map((d,i)=>`<label><input type="checkbox" value="${d}" ${i==0?'checked':''}>${d.toUpperCase()}</label>`).join('');
 $('#formatlar').innerHTML=[['dikey','Dikey 9:16'],['yatay','Yatay 16:9'],['kare','Kare 1:1']].map(([f,y])=>`<label><input type="radio" name="fmt" value="${f}" ${f==FORMAT?'checked':''}>${y}</label>`).join('');
 const m=P.muzik&&P.muzik.dosya; $('#muzik').innerHTML='<option value="">Müzik yok</option>'+P.sesler.map(s=>`<option value="${s.ad}" ${s.ad==m?'selected':''}>${s.ad}${s.kaynak=='proje'?' (proje)':''}</option>`).join('');
 const sv=Math.round(100*((P.muzik&&P.muzik.ses)??0.35)); $('#muzikSes').value=sv; $('#muzikSesY').textContent=sv+'%';
 // önizleme çerçeveleri
 document.querySelectorAll('#ekran iframe').forEach(f=>f.remove()); FRAMES={}; KARELER={};
 P.sahneler.forEach(s=>{ if(s.url){const f=document.createElement('iframe'); $('#ekran').prepend(f); FRAMES[s.no]=f;} });
 zamanKur(); muzikKur(); ciktilariGoster(P.ciktilar);
}
// --- seslendirmeyi sahneye sığdırma (motor/sigdir.py ile aynı hesap) ---
const SIG_MAKS={otomatik:1.2,hizlandir:1.4,uzat:1};
function sigHesap(ses,sure,mod,pay){ pay=pay??0.6; const m=SIG_MAKS[mod]||1.2, yer=Math.max(0.5,sure-pay); let o=1;
 if(ses>yer&&m>1)o=Math.round(Math.min(ses/yer,m)*1000)/1000; return [o,Math.max(sure,ses/o+pay)] }
function planHesapla(){ // önizleme dilinin seslerine göre sahne süreleri (videodaki gibi); değiştiyse true
 const d=ANL[$('#onizDil').value]; let bas=0, degisti=false;
 P.sahneler.forEach(s=>{ let sure=s.sure0, oran=1; const b=d&&!d.tam&&d.sahneler[String(s.no)];
  if(b){[oran,sure]=sigHesap(b.sure,s.sure0,(d.sigdir||{})[String(s.no).padStart(2,'0')]||'otomatik',s.pay)}
  if(Math.abs(sure-s.sure)>0.001||Math.abs(bas-s.bas)>0.001)degisti=true; s.sure=sure; s.bas=bas; s.oran=oran; bas+=sure });
 if(d&&d.tam&&P.sahneler.length){const f=d.tam.sure+0.8-bas; if(f>0){const s=P.sahneler[P.sahneler.length-1]; s.sure+=f; bas+=f; degisti=true}}
 P.sure=bas; const bul=no=>P.sahneler.find(s=>s.no===no); P.olaylar.forEach(o=>{const s=bul(o.no); if(s)o.t=s.bas+o.yerel});
 return degisti }
function zamanKur(){
 const renk={vektor:'#a79be0',uc:'#e2a76f',piksel:'#78c48d',cizgi:'#62b6a8',harita:'#6f9fdc',resim:'#d99a5b',kart:'#d9778a'};
 const ad={vektor:'Vektör',uc:'3D',piksel:'Piksel',cizgi:'Çizgi film',harita:'Harita',resim:'Resim',kart:'Kart'};
 $('#sahneler').innerHTML=P.sahneler.map(s=>`<div class="sahne" data-no="${s.no}" onclick="git(${s.bas+0.01})"><div class="no">${s.no}</div>
  <div><div class="sb">${s.baslik||ad[s.tur]||s.tur}</div><div class="st">${fmt(s.bas)}–${fmt(s.bas+s.sure)} sn${s.oran>1?` · ses ×${s.oran.toFixed(2)}`:''}</div></div><span class="rozet">${ad[s.tur]||s.tur}</span></div>`).join('');
 $('#serit').innerHTML=P.sahneler.map(s=>`<div class="parca" style="flex:${s.sure};background:${renk[s.tur]||'#555'}33">${s.no}</div>`).join('')+'<div id="imlec"></div>';
 const dil=$('#onizDil').value;
 P.sahneler.forEach(s=>{const f=FRAMES[s.no]; if(!f)return; const src=s.url+`?mod=gomulu&dil=${dil}&sure=${+s.sure.toFixed(3)}`+(s.sonraki?`&sonraki=${s.sonraki}`:''); if(f.dataset.src!==src){f.dataset.src=src; f.src=src}});
 if(T>=P.sure)T=0 }
function muzikKur(){ if(MUZIK){MUZIK.pause();MUZIK=null}
 const ad=$('#muzik').value; if(!ad)return; const yol=P.sesler.find(s=>s.ad==ad);
 MUZIK=new Audio(yol.kaynak=='proje'?`/k/projeler/${AD}/${ad}`:`/k/motor/sesler/${ad}`); MUZIK.loop=true; MUZIK.volume=$('#muzikSes').value/100}
function aktifSahne(t){return P.sahneler.find(s=>t>=s.bas&&t<s.bas+s.sure)||P.sahneler[P.sahneler.length-1]}
async function ciz(sicra){ if(!P||!P.sahneler.length)return;
 const s=aktifSahne(T); const yerel=Math.min(T-s.bas,s.sure-0.001);
 Object.entries(FRAMES).forEach(([no,f])=>f.classList.toggle('gor',+no===s.no));
 document.querySelectorAll('.sahne').forEach(e=>e.classList.toggle('aktif',+e.dataset.no===s.no));
 $('#imlec').style.left=(100*T/P.sure)+'%'; $('#zaman').textContent=`${fmt(T)} / ${fmt(P.sure)} sn`;
 const img=$('#kare'), not=$('#ekranNot');
 if(s.url){FRAMES[s.no].contentWindow.postMessage({komut:'git',t:yerel},'*'); img.style.display='none'; not.style.display='none'}
 else{ img.style.display='block'; not.style.display='block'; not.textContent='Bu sahne türü canlı oynatılmaz — sahnenin ilk karesi gösteriliyor.';
  const k=s.no+'_'+$('#onizDil').value; if(KARELER[k]){img.src=KARELER[k]} else if(sicra!==false){KARELER[k]='';
   const o=await api('/api/kare',{ad:AD,t:s.bas+0.6,dil:$('#onizDil').value,format:'dikey'}); if(o.url){KARELER[k]=o.url; if(aktifSahne(T)===s)img.src=o.url}}}
}
function anlatimVar(){const d=ANL[$('#onizDil').value]; return !!(d&&(d.tam||Object.keys(d.sahneler).length))}
function muzikSeviye(){ if(MUZIK) MUZIK.volume=($('#muzikSes').value/100)*(anlatimVar()?0.45:1) }
function anlatimDur(){ if(ANL_SES)ANL_SES.pause(); ANL_SES=null; ANL_NO=null }
function anlatimGuncelle(zorla){
 if(!SES||!OYNUYOR){anlatimDur();return}
 const d=ANL[$('#onizDil').value]; if(!d){anlatimDur();return}
 if(d.tam){ if(ANL_NO!=='tam'||zorla){anlatimDur(); ANL_NO='tam'; const off=T-0.3;
   if(off<d.tam.sure){ANL_SES=new Audio(d.tam.url); ANL_SES.currentTime=Math.max(0,off); ANL_SES.play().catch(()=>{})}} return }
 const s=aktifSahne(T);
 if(ANL_NO!==s.no||zorla){ anlatimDur(); ANL_NO=s.no; const b=d.sahneler[String(s.no)];
  if(b){const o=s.oran||1, off=(T-s.bas-0.3)*o; if(off<b.sure){ANL_SES=new Audio(b.url); ANL_SES.preservesPitch=true; ANL_SES.playbackRate=o; ANL_SES.currentTime=Math.max(0,off); ANL_SES.play().catch(()=>{})}}}
}
function dongu(simdi){ if(!OYNUYOR)return; const dt=(simdi-SON)/1000; SON=simdi; const once=T; T+=dt;
 if(T>=P.sure){T=0; if(MUZIK)MUZIK.currentTime=0; ANL_NO=null}
 anlatimGuncelle(false);
 if(SES) P.olaylar.forEach(o=>{ if(o.t>once&&o.t<=T){ const a=new Audio(o.url); a.volume=Math.min(1,o.seviye); a.play().catch(()=>{}) } });
 ciz(false); requestAnimationFrame(dongu)}
function oynatDurdur(){ if(OYNUYOR)return durdurOyna(); OYNUYOR=true; $('#oynat').textContent='❚❚'; SON=performance.now(); muzikSeviye();
 if(MUZIK&&SES){MUZIK.currentTime=T%(MUZIK.duration||1e9);MUZIK.play().catch(()=>{})} anlatimGuncelle(true); requestAnimationFrame(dongu)}
function durdurOyna(){OYNUYOR=false; $('#oynat').textContent='▶'; if(MUZIK)MUZIK.pause(); anlatimDur()}
function git(t){T=Math.max(0,Math.min(P.sure-0.01,t)); if(MUZIK)MUZIK.currentTime=T%(MUZIK.duration||1e9); anlatimGuncelle(true); ciz()}
function sesAcKapa(){SES=!SES; $('#sesBtn').textContent=SES?'Ses açık':'Ses kapalı'; if(!SES&&MUZIK)MUZIK.pause(); if(SES&&OYNUYOR&&MUZIK)MUZIK.play(); anlatimGuncelle(true)}
const serit=$('#serit'); let surukle=false;
serit.onmousedown=e=>{surukle=true;seritGit(e)}; window.onmousemove=e=>{if(surukle)seritGit(e)}; window.onmouseup=()=>surukle=false;
function seritGit(e){const r=serit.getBoundingClientRect(); git(P.sure*Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)))}
window.addEventListener('message',e=>{ if(e.data&&e.data.hazir) ciz(false) });
$('#onizDil').onchange=()=>{ planHesapla(); zamanKur(); anlatimGuncelle(true); ciz()};
$('#muzik').onchange=()=>{const was=OYNUYOR; durdurOyna(); muzikKur(); if(was)oynatDurdur()};
$('#muzikSes').oninput=e=>{$('#muzikSesY').textContent=e.target.value+'%'; muzikSeviye()};
$('#proje').onchange=e=>projeAc(e.target.value);
document.addEventListener('keydown',e=>{ if(e.target.tagName==='TEXTAREA'||e.target.tagName==='INPUT')return;
 if(e.key==='Escape'&&$('#perde').style.display==='flex')return perdeKapat(); if(!P||$('#perde').style.display==='flex')return;
 if(e.code==='Space'){e.preventDefault();oynatDurdur()} if(e.key==='ArrowRight')git(T+(e.shiftKey?0.1:1)); if(e.key==='ArrowLeft')git(T-(e.shiftKey?0.1:1));
 const i=P.sahneler.indexOf(aktifSahne(T)); if(e.key==='ArrowDown'&&P.sahneler[i+1]){e.preventDefault();git(P.sahneler[i+1].bas+0.01)} if(e.key==='ArrowUp'){e.preventDefault();git(P.sahneler[Math.max(0,T-P.sahneler[i].bas>0.5?i:i-1)].bas+0.01)}
 if(e.key==='Home')git(0)});
// --- üretim
let IPTAL=false;
async function sesleriHazirla(diller){ // seçili dillerde sesi olmayan / metni değişmiş sahneleri önce seslendir
 if(!$('#onceSes').checked||!TTS_D||!TTS_D.kurulu)return true;
 for(const dil of diller){ if(!ttsDilVar(dil)||!eksikSes(dil).length)continue;
  $('#asama').textContent=`${dil.toUpperCase()}: ${eksikSes(dil).length} sahne seslendiriliyor…`;
  const o=await api('/api/tts/uret',{ad:AD,dil,hedef:'eksik'}); if(o.hata){bildir(o.hata,1);return false}
  while(true){ await new Promise(r=>setTimeout(r,1000)); const d=await api(ttsQ()); TTS_D=d;
   $('#asama').textContent=`${dil.toUpperCase()} seslendirme: ${d.is.asama||''}`; $('#ilerleme div').style.width=(d.is.yuzde||0)+'%';
   if(!d.is.calisiyor){ if(d.is.hata){bildir(d.is.hata,1);return false} break } }
  await anlYenile(); if(IPTAL)return false }
 return true }
async function olustur(){ if(projeYok())return; const diller=[...document.querySelectorAll('#diller input:checked')].map(x=>x.value);
 if(!diller.length)return bildir('En az bir dil seç.',1);
 const fmtSec=document.querySelector('input[name=fmt]:checked').value;
 IPTAL=false; $('#olusturBtn').disabled=true; $('#durBtn').style.display='';
 const tamam=await sesleriHazirla(diller); $('#ilerleme div').style.width='0%';
 if(!tamam){ $('#olusturBtn').disabled=false; $('#durBtn').style.display='none'; $('#asama').textContent='Durdu.'; return }
 if(fmtSec!=='dikey'&&P.sahneler.some(s=>s.tur==='vektor')) bildir('Not: vektör sahneler dikey için tasarlandı; diğer formatlarda kenarlar boş kalır.');
 const o=await api('/api/olustur',{ad:AD,diller,format:fmtSec,kalite:document.querySelector('input[name=kalite]:checked').value,
  muzik:$('#muzik').value,muzik_ses:$('#muzikSes').value/100,altyazi:$('#altyazi').checked});
 if(o.hata){$('#olusturBtn').disabled=false; $('#durBtn').style.display='none'; return bildir(o.hata,1)} izle()}
async function izle(){ const s=await api('/api/durum');
 $('#ilerleme div').style.width=s.yuzde+'%'; $('#asama').textContent=(s.calisiyor?`%${Math.round(s.yuzde)} · `:'')+s.asama;
 $('#kayit').textContent=s.log.join('\n'); $('#kayit').scrollTop=1e9;
 if(s.calisiyor)return setTimeout(izle,700);
 $('#olusturBtn').disabled=false; $('#durBtn').style.display='none';
 if(s.hata){bildir('Video oluşturulamadı. "Kayıtlar"a bak.',1); kayit.style.display='block'}
 else if(s.ciktilar.length){bildir('Video hazır.'); const c=await api('/api/ciktilar?ad='+AD); ciktilariGoster(c.ciktilar)}}
function ciktilariGoster(l){ $('#ciktilar').innerHTML=l.length?l.map(c=>`<div class="cikti"><div style="flex:1"><div class="ad">${c.ad}</div>
 <div class="bil">${new Date(c.zaman*1000).toLocaleString(DIL==='tr'?'tr-TR':'en-GB')} · ${(c.boyut/1048576).toFixed(1)} MB</div></div>
 <button class="btn kucuk" onclick="izleVideo('${c.url}')">▶</button></div>`).join(''):'<div class="ipucu" style="padding:0 14px">Henüz video yok.</div>'}
async function durdur(){IPTAL=true; await api('/api/durdur',{}); api('/api/tts/durdur',{})}
async function kareKaydet(){ if(projeYok())return; durdurOyna(); bildir('Kare çıkarılıyor…'); const f=document.querySelector('input[name=fmt]:checked').value;
 const o=await api('/api/kare',{ad:AD,t:T,dil:$('#onizDil').value,format:f}); if(o.hata)return bildir(o.hata,1);
 ANL_ACIK=false; $('#perdeIc').innerHTML=`<img src="${o.url}" style="max-height:74vh;max-width:90vw;border-radius:6px;align-self:center"><div style="display:flex;gap:8px;align-items:center"><span class="ipucu">Kaydedildi: cikti/${kac(o.ad)}</span><span class="bosluk"></span><button class="btn" onclick="ac('cikti')">Klasörde göster</button><button class="btn" onclick="perdeKapat()">Kapat</button></div>`; $('#perde').style.display='flex' }
function izleVideo(u){ durdurOyna(); ANL_ACIK=false; $('#perdeIc').innerHTML=`<video src="${u}" controls autoplay></video><div style="display:flex;gap:8px"><button class="btn" onclick="ac('cikti')">Klasörde göster</button><span class="bosluk"></span><button class="btn" onclick="perdeKapat()">Kapat</button></div>`; $('#perde').style.display='flex'}
function perdeKapat(){ sesDur(); ANL_ACIK=false; $('#perde').style.display='none'; $('#perdeIc').innerHTML=''}
// --- seslendirme
const kac=x=>String(x).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function seslendirme(){ if(projeYok())return; durdurOyna(); ANL_ACIK=true; ttsDurum(); ANL_DIL=ANL_DIL&&P.diller.includes(ANL_DIL)?ANL_DIL:$('#onizDil').value; anlCiz(); $('#perde').style.display='flex'}
function anlCiz(){ const dil=ANL_DIL, d=ANL[dil]||{tam:null,sahneler:{}}; const tOk=ttsDilVar(dil), tMesgul=!!(TTS_D&&TTS_D.is.calisiyor);
 const ust=`<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><b style="font-size:17px">Seslendirme</b>
  <div class="sec">${P.diller.map(x=>`<label><input type="radio" name="anlDil" value="${x}" ${x==dil?'checked':''} onchange="ANL_DIL=this.value;anlCiz();ttsDurum()">${x.toUpperCase()}</label>`).join('')}</div>
  <div class="sec"><label><input type="radio" name="anlMod" ${ANL_MOD=='sahne'?'checked':''} onchange="ANL_MOD='sahne';anlCiz()">Sahne sahne (önerilen)</label>
  <label><input type="radio" name="anlMod" ${ANL_MOD=='tam'?'checked':''} onchange="ANL_MOD='tam';anlCiz()">Tek dosya</label></div>
  <span class="bosluk"></span>${tOk?`<button class="btn kucuk ana" onclick="ttsUret('${ANL_MOD=='tam'?'tam':'eksik'}')" ${tMesgul?'disabled':''} title="Sesi olmayan ve metni değişmiş sahneleri seslendirir">${ANL_MOD=='tam'?'Tek dosyayı üret':'Eksikleri üret'+(eksikSes(dil).length?` (${eksikSes(dil).length})`:'')}</button>${ANL_MOD=='sahne'?`<button class="btn kucuk" onclick="ttsUret('hepsi')" ${tMesgul?'disabled':''}>Hepsini yeniden</button>`:''}`:''}
  ${TTS_D&&TTS_D.kurulu&&(d.tam||Object.keys(d.sahneler).length)?`<button class="btn kucuk" onclick="whisperKontrol(event.shiftKey)" ${tMesgul?'disabled':''} title="Sesleri Whisper ile dinler, senaryoyla karşılaştırır ve altyazı zamanlarını çıkarır. Shift+tık: hepsini yeniden kontrol et">Whisper kontrolü</button>`:''}
  ${TTS_D&&TTS_D.kurulu?`<button class="btn kucuk" onclick="CEV_ACIK=!CEV_ACIK;anlCiz()" ${tMesgul?'disabled':''} title="Seslendirme metinlerini ve ekrandaki yazıları bilgisayarında başka dillere çevirir">Çevir</button>`:''}
  <button class="btn" onclick="perdeKapat()">Kapat</button></div>
  ${CEV_ACIK?cevPanel():''}
  <div class="ttsBar" id="ttsBar"></div>
  <div class="ipucu">${tOk?'Üret, metni Chatterbox ile bilgisayarında seslendirir. ':''}Başka bir araçta ürettiğin sesi Yükle ile ekleyebilirsin (mp3, wav, m4a). Sesler önizlemede ve videoda kendiliğinden çalar.</div>`;
 let govde='';
 if(ANL_MOD==='sahne'){
  govde=P.sahneler.map(s=>{const m=s.anlatim[dil]||''; const b=d.sahneler[String(s.no)]; const nn=String(s.no).padStart(2,'0');
   const mod=(d.sigdir||{})[nn]||'otomatik'; const [oran,ysure]=b?sigHesap(b.sure,s.sure0,mod,s.pay):[1,s.sure0];
   const sig=!b?'':ysure>s.sure0+0.01?`<div class="uyari">Ses sahneden uzun${oran>1?`: ×${oran.toFixed(2)} hızlandırıldı,`:':'} videoda bu sahne ${ysure.toFixed(1)} sn olur.</div>`
     :oran>1?`<div class="ipucu" style="color:var(--green)">Sahneye sığdırıldı (ses ×${oran.toFixed(2)})</div>`:'';
   const secim=b?`<label class="ipucu" style="display:flex;gap:6px;align-items:center" title="Ses sahneden uzunsa ne yapılsın? Ses dosyası değişmez; hız videoda ve önizlemede uygulanır.">Sığdır:
     <select onchange="sigdirSec(${s.no},this.value)"><option value="otomatik" ${mod=='otomatik'?'selected':''}>Otomatik (≤%20 hızlan)</option><option value="hizlandir" ${mod=='hizlandir'?'selected':''}>Hızlandır (≤%40)</option><option value="uzat" ${mod=='uzat'?'selected':''}>Sahneyi uzat</option></select></label>`:'';
   const eski=sesEski(b,m);
   const durum=b?`<div class="tamam">✓ Ses var · ${b.sure.toFixed(1)} sn</div>${eski?'<div class="uyari" title="Ses, metnin önceki hâlinden üretilmiş. Eksikleri üret bu sahneyi de yeniler.">✎ Metin değişti, ses eski</div>':kontrolRozet(b.kontrol)}${sig}${secim}
    <div style="display:flex;gap:6px"><button class="btn kucuk" onclick="sesCal('${b.url}',this,${oran})" title="Videodaki hızıyla çalar">▶ Dinle</button><button class="btn kucuk kirmizi" onclick="anlSil('${String(s.no).padStart(2,'0')}')">Sil</button></div>`:'<div class="ipucu">Ses yok</div>';
   return `<div class="anlS"><div><div style="display:flex;gap:8px;align-items:center;margin-bottom:6px"><span class="no" style="width:26px;height:26px;font-size:13px">${s.no}</span><b>${kac(s.baslik||('Sahne '+s.no))}</b><span class="ipucu">sahne ${s.sure0} sn · <span id="ks${s.no}">${kelimeYazi(m,s.sure0)}</span>${(s.ceviri||[]).includes(dil)?' · makine çevirisi':''}</span></div>
    <textarea class="anlMetin anlYaz" rows="2" spellcheck="false" placeholder="Bu sahne için metin yok. Buraya yazabilirsin ya da Çevir ile başka bir dilden çevrilir." title="Metni burada düzeltebilirsin; kutudan çıkınca kaydedilir"
     oninput="$('#ks${s.no}').innerHTML=kelimeYazi(this.value,${s.sure0})" onchange="metinDuzelt(${s.no},this)">${kac(m)}</textarea></div>
    <div class="anlDurum">${m&&tOk?`<button class="btn kucuk ${b?'':'ana'}" onclick="ttsUret('${String(s.no).padStart(2,'0')}')" ${tMesgul?'disabled':''}>${b?'Yeniden üret':'Chatterbox ile üret'}</button>`:''}${m?`<button class="btn kucuk" onclick="kopyala(${s.no})">Kopyala</button>`:''}<button class="btn kucuk" onclick="anlSec('${String(s.no).padStart(2,'0')}')">Yükle</button>${durum}</div></div>`}).join('');
 } else {
  const m=P.sahneler.map(s=>s.anlatim[dil]||'').filter(Boolean).join('\n\n'); const b=d.tam;
  govde=`<div class="anlS"><div><b>Tüm videonun metni</b> <span class="ipucu">video ${P.sure.toFixed(1)} sn · en fazla ~${Math.round(P.sure*2.0)} kelime</span>
   <div class="anlMetin" style="margin-top:6px">${m?kac(m):'<span class="ipucu">Metin yok.</span>'}</div>
   <div class="uyari" style="margin-top:8px">Tek dosyada konuşma sahnelerle tam eşleşmeyebilir. Sahne sahne yüklemek daha iyi senkron sağlar.</div></div>
   <div class="anlDurum">${m?`<button class="btn kucuk" onclick="kopyala(0)">Kopyala</button>`:''}<button class="btn kucuk ana" onclick="anlSec('tam')">Yükle</button>
   ${b?`<div class="tamam">✓ Ses var · ${b.sure.toFixed(1)} sn</div>${kontrolRozet(b.kontrol)}<div style="display:flex;gap:6px"><button class="btn kucuk" onclick="sesCal('${b.url}',this)">▶ Dinle</button><button class="btn kucuk kirmizi" onclick="anlSil('tam')">Sil</button></div>`:'<div class="ipucu">Ses yok</div>'}
   ${b&&Object.keys(d.sahneler).length?'<div class="uyari">Not: sahne sesleri de var; ikisi birlikte çalar. Birini silmen önerilir.</div>':''}</div></div>`;
 }
 $('#perdeIc').innerHTML=ust+`<div class="anl">${govde}</div><input type="file" id="anlDosya" accept="audio/*,.mp3,.wav,.m4a,.ogg" style="display:none">`;
 ttsCiz();
}
function kopyala(no){ const dil=ANL_DIL; const m=no?P.sahneler.find(s=>s.no===no).anlatim[dil]:P.sahneler.map(s=>s.anlatim[dil]||'').filter(Boolean).join('\n\n');
 navigator.clipboard.writeText(m).then(()=>bildir('Metin kopyalandı'),()=>bildir('Kopyalanamadı, metni elle seç',1))}
function anlSec(hedef){ const inp=$('#anlDosya'); inp.value=''; inp.onchange=async()=>{ const f=inp.files[0]; if(!f)return;
  const uz=(f.name.match(/\.[a-z0-9]+$/i)||['.mp3'])[0].toLowerCase(); bildir('Yükleniyor…');
  const r=await fetch(`/api/yukle?ad=${encodeURIComponent(AD)}&dil=${ANL_DIL}&hedef=${hedef}&uzanti=${uz}`,{method:'POST',body:f}); const o=await r.json();
  if(o.hata)return bildir(o.hata,1); bildir('Ses yüklendi ✓ ('+o.sure.toFixed(1)+' sn)'); await anlYenile() }; inp.click()}
async function anlSil(hedef){ if(!confirm('Bu ses dosyası silinsin mi?'))return; await api('/api/anlatim_sil',{ad:AD,dil:ANL_DIL,hedef}); await anlYenile()}
async function anlYenile(){ const o=await api('/api/anlatim?ad='+encodeURIComponent(AD)); ANL=o.anlatim||{}; if(planHesapla()){zamanKur(); ciz(false)} if(ANL_ACIK)anlCiz(); muzikSeviye()}
async function sigdirSec(no,mod){ const o=await api('/api/sigdir',{ad:AD,dil:ANL_DIL,hedef:String(no).padStart(2,'0'),mod}); if(o.hata)return bildir(o.hata,1); await anlYenile() }
// --- Chatterbox (bilgisayarda yapay zeka seslendirme)
const tarih=t=>t?new Date(t).toLocaleDateString(DIL==='tr'?'tr-TR':'en-GB',{day:'numeric',month:'short',year:'numeric'}):'';
function ttsDilVar(dil){ return !!(TTS_D&&TTS_D.kurulu&&(!TTS_D.diller.length||TTS_D.diller.includes(dil))) }
const ttsQ=k=>`/api/tts/durum?ad=${encodeURIComponent(AD||'')}&dil=${ANL_DIL||($('#onizDil')&&$('#onizDil').value)||'tr'}`+(k?'&kontrol='+k:'');
async function ttsDurum(kontrol){ TTS_D=await api(ttsQ(kontrol)); ttsRozet();
 if(ANL_ACIK)anlCiz(); if(TTS_D.is.calisiyor)ttsIzle() }
function ttsRozet(){ $('#ttsRozet').style.display=TTS_D&&TTS_D.guncelleme_var&&!TTS_D.is.calisiyor?'inline':'none' }
async function ttsIzle(){ if(TTS_IZ)return; TTS_IZ=true; let son=-1, ilk=true;
 while(true){ TTS_D=await api(ttsQ()); const is=TTS_D.is;
  if(ilk&&ANL_ACIK){anlCiz(); ilk=false} else ttsCiz();
  if((is.tur==='uretim'||is.tur==='kontrol')&&is.biten!==son){ if(son>=0)await anlYenile(); son=is.biten }
  if(!is.calisiyor)break; await new Promise(r=>setTimeout(r,1000)) }
 TTS_IZ=false; await ttsDurum(); if(TTS_D.is.tur==='ceviri'){const t=T; await projeAc(AD); git(Math.min(t,P.sure-0.01)); CEV_YENI=[]} await anlYenile(); ttsRozet();
 if(TTS_D.is.hata)bildir(TTS_D.is.hata,1); else bildir(TTS_D.is.asama) }
function ttsCiz(){ const el=$('#ttsBar'), d=TTS_D; if(!el)return; if(!d){el.innerHTML='<span class="ipucu">Chatterbox durumu alınıyor…</span>';return}
 const is=d.is; let h='';
 if(is.calisiyor){
  h=`<div class="ttsSatir"><b>Chatterbox</b><span>${kac(is.asama)}</span><span class="bosluk"></span>
   <button class="btn kucuk kirmizi" onclick="ttsDurdur()">■ Durdur</button><button class="btn kucuk" onclick="TTS_LOG=!TTS_LOG;ttsCiz()">Kayıtlar</button></div>
   <div class="ttsIler"><div style="width:${Math.max(3,is.yuzde)}%"></div></div>`;
 } else if(!d.kurulu){
  h=`<div class="ttsSatir"><b>Chatterbox</b><span class="ipucu">Bilgisayarında ücretsiz çalışan yapay zeka seslendirme (TR, EN, PL, PT, ES ve 18 dil daha). Tek tıkla kurulur: ~10 GB yer, ilk kurulum 15-30 dk.</span>
   <span class="bosluk"></span><button class="btn kucuk ana" onclick="ttsKur()">Chatterbox'u kur</button>${is.log.length?`<button class="btn kucuk" onclick="TTS_LOG=!TTS_LOG;ttsCiz()">Kayıtlar</button>`:''}</div>`;
 } else {
  const s=d.surum; let g;
  if(d.guncelleme_var) g=`<span class="uyari" style="font-size:13px">Yeni sürüm var (${tarih(d.son.tarih)})</span><button class="btn kucuk ana" onclick="ttsKur(1)">Güncelle</button><button class="btn kucuk" onclick="ttsYenilikler()">Neler değişti?</button>`;
  else if(d.son&&d.son.hata) g=`<span class="ipucu" title="${kac(d.son.hata)}">Güncelleme kontrol edilemedi</span>`;
  else if(d.son) g=`<span class="tamam">✓ Güncel</span>`; else g='';
  h=`<div class="ttsSatir"><b>Chatterbox</b><span class="ipucu">sürüm ${tarih(s.tarih)} · ${s.sha.slice(0,7)}${d.gpu?' · '+kac(d.gpu):''}</span>${g}<span class="bosluk"></span>
   ${d.eski_var?`<button class="btn kucuk" onclick="ttsGeri()" title="Bir önceki kurulu sürüme dön${d.eski_surum?' ('+tarih(d.eski_surum.tarih)+')':''}">Önceki sürüm</button>`:''}
   <button class="btn kucuk" onclick="ttsKontrol()">Güncellemeye bak</button><button class="btn kucuk" onclick="TTS_AYAR=!TTS_AYAR;ttsCiz()">Ses ayarları</button>
   <button class="btn kucuk" onclick="TTS_LOG=!TTS_LOG;ttsCiz()">Kayıtlar</button></div>`;
  if(!ttsDilVar(ANL_DIL)) h+=`<div class="uyari">Chatterbox "${ANL_DIL}" dilini desteklemiyor; bu dil için sesi elle yükle.</div>`;
  if(ttsDilVar(ANL_DIL)&&d.sesler){ const sec=d.secili||'hazir', bu=d.sesler.find(x=>x.id===sec);
   h+=`<div class="ttsSatir"><b>${ANL_DIL.toUpperCase()} sesi:</b><select id="sesSec" onchange="sesSec(this.value)" style="min-width:240px">${d.sesler.map(x=>`<option value="${x.id}" ${x.id===sec?'selected':''}>${kac(x.ad)}</option>`).join('')}</select>
    ${bu&&bu.url?`<button class="btn kucuk" onclick="sesCal('${bu.url}',this)">▶ Dinle</button>`:''}
    <span class="ipucu">${d.secim_kaynak==='proje'?'bu projeye özel':'varsayılan'}</span>
    <button class="btn kucuk" onclick="sesSec($('#sesSec').value,1)" title="Yeni projelerde de ${ANL_DIL.toUpperCase()} için bu ses kullanılsın">Varsayılan yap</button>
    ${d.sesler.length<2?`<span class="ipucu">Daha fazla ses için Ses ayarları → şablon oluştur ya da kendi kaydını yükle</span>`:''}</div>` }
  if(TTS_YENI) h+=`<div class="yeniList"><b>Son kurduğundan beri değişenler:</b><br>${TTS_YENI.length?TTS_YENI.map(x=>`• ${kac(x.mesaj)} <span class="ipucu">${tarih(x.tarih)}</span>`).join('<br>'):'Liste boş.'}</div>`;
  if(TTS_AYAR) h+=ttsAyarHtml();
 }
 if(is.hata&&!is.calisiyor) h+=`<div class="uyari">Son işlem: ${kac(is.hata)}</div>`;
 if(TTS_LOG) h+=`<div class="kayitK" id="ttsKayit">${kac(is.log.join('\n'))||'Kayıt yok.'}</div>`;
 el.innerHTML=h; const k=$('#ttsKayit'); if(k)k.scrollTop=1e9 }
function ttsAyarHtml(){ const a=TTS_D.ayar, L=TTS_D.sesler||[];
 const rozet={hazir:'Chatterbox',sablon:'şablon',kopya:'kopya',yuklenen:'yüklenen'};
 const satir=x=>`<div class="refSatir"><span class="sb" style="flex:1" title="${kac(x.ad)}">${kac(x.ad)}</span><span class="rozet">${rozet[x.tur]||x.tur}</span>
  ${x.url?`<button class="btn kucuk" onclick="sesCal('${x.url}',this)" title="Dinle / durdur">▶</button>`:''}
  ${x.id!=='hazir'||TTS_D.hazir_ornek?`<button class="btn kucuk" onclick="sesTuret('${x.id}')" title="Bu sesin kalın ya da ince bir kopyasını oluştur">Kopya</button>`:''}
  ${x.id!=='hazir'?`<button class="btn kucuk" onclick="sesAd('${x.id}')" title="Yeniden adlandır">Ad</button><button class="btn kucuk kirmizi" onclick="sesSil('${x.id}')" title="Sil">Sil</button>`:''}</div>`;
 const kay=(id,ad,min,max,deg,ip)=>`<label class="kay"><span>${ad} <b id="${id}Y">${deg}</b></span><input type="range" id="${id}" min="${min}" max="${max}" step="0.05" value="${deg}" oninput="$('#${id}Y').textContent=this.value"><span class="ipucu">${ip}</span></label>`;
 return `<div class="ttsAyar"><div><b>Ses kütüphanesi</b>
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0">
   <button class="btn kucuk" onclick="mikAc()">Mikrofonla kaydet</button>
   <button class="btn kucuk" onclick="sesYukle()">Dosyadan ekle</button>
   ${TTS_D.sablon_var?'':`<button class="btn kucuk" onclick="sablonOlustur()">Hazır şablonları oluştur</button>`}</div>
  <div style="max-height:220px;overflow:auto">${L.map(satir).join('')}</div>
  <div class="ipucu" style="margin-top:8px">Kendi kaydın için 10-20 sn net, müziksiz, tek kişilik konuşma yeter. Chatterbox o sesle (cinsiyet, kalınlık, tarz) konuşur; en iyi sonuç için kayıt seslendirilecek dilde olsun. Kopya, bir sesin daha kalın ya da ince hâlini çıkarır. Yalnızca kendi sesini ya da izni olan sesleri kullan.</div>
  <input type="file" id="refDosya" accept="audio/*" style="display:none"></div>
  <div>${(()=>{ const x=(TTS_D.sesler||[]).find(v=>v.id===(TTS_D.secili||'hazir')); if(!x)return '';
    return `<div style="background:#151617;border-radius:6px;padding:10px;margin-bottom:12px"><div style="margin-bottom:6px"><b>Seçili ses: ${kac(x.ad)}</b> <span class="ipucu">(bu sese özel)</span></div>
    ${kay('sHiz','Konuşma hızı',0.6,1.3,x.hiz,'1 = Chatterbox\'ın kendi hızı · 0.8 = %20 daha yavaş (ton bozulmaz)')}
    ${kay('sDur','Cümle arası duraklama (sn)',0,1.2,x.duraklama,'Her cümleden sonra bırakılan sessizlik')}
    <div style="display:flex;gap:6px"><button class="btn kucuk" onclick="sesAyarKaydet('${x.id}')">Bu ses için kaydet</button>
    ${x.url&&x.id!=='hazir'?`<button class="btn kucuk" onclick="sesOlc('${x.id}')" title="Ses örneğindeki konuşma hızını ölçer ve ona göre ayarlar">Kayda göre ayarla</button>`:''}</div></div>` })()}
  ${kay('aDuygu','Duygu / canlılık',0.25,1.5,a.duygu,'0.5 doğal · 0.7+ daha coşkulu')}${kay('aCfg','Örneğe bağlılık / tempo',0,1,a.cfg,'Örnek hızlı konuşuyorsa ya da başka dildeyse 0.3 dene')}${kay('aSic','Çeşitlilik',0.4,1.2,a.sicaklik,'Düşük = daha düz ve tutarlı')}
  <label style="display:flex;gap:8px;align-items:center;margin:4px 0 2px;font-size:13px"><input type="checkbox" id="aKontrol" ${a.otomatik_kontrol!==false?'checked':''}> Üretince Whisper ile kontrol et (altyazı zamanları da çıkar)</label>
  <label style="display:flex;gap:8px;align-items:center;margin:2px 0 10px;font-size:13px"><input type="checkbox" id="aTekrar" ${a.otomatik_tekrar!==false?'checked':''}> Kelime atlanmışsa bir kez otomatik yeniden üret</label>
  ${TTS_D.modeller.length?`<label class="kay"><span>Model</span><select id="aModel">${TTS_D.modeller.map(m=>`<option ${m==a.model?'selected':''}>${m}</option>`).join('')}</select><span class="ipucu">En yenisi önerilir</span></label>`:''}
  <button class="btn kucuk" onclick="ttsAyarKaydet()">Ayarları kaydet</button></div></div>` }
async function ttsKur(guncelle){
 if(!confirm(guncelle?'Chatterbox güncellensin mi?\n\nYeni sürüm ayrı bir klasöre kurulup test edilir, sonra eskisiyle yer değiştirir. Bir sorun olursa "Önceki sürüm" ile geri dönebilirsin. Birkaç dakika sürer.'
  :'Chatterbox kurulsun mu?\n\n• ~10 GB disk alanı (program + model)\n• İlk kurulum internet hızına göre 15-30 dk sürer\n• Stüdyonun kendi Python\'una dokunmaz, ayrı bir ortama kurulur\n\nKurulum sürerken stüdyoyu kapatma.'))return;
 const o=await api('/api/tts/kur',{}); if(o.hata)return bildir(o.hata,1); TTS_YENI=null; ttsIzle()}
async function ttsUret(h){ await METIN_KAYIT; if(h==='hepsi'&&!confirm('Bu dildeki tüm sahne sesleri (elle yüklediklerin dahil) Chatterbox ile yeniden üretilecek. Devam?'))return;
 if(/^\d\d$/.test(h)&&ANL[ANL_DIL]&&ANL[ANL_DIL].sahneler[String(+h)]&&!confirm('Bu sahnenin mevcut sesi yenisiyle değiştirilecek. Devam?'))return;
 anlatimDur(); const o=await api('/api/tts/uret',{ad:AD,dil:ANL_DIL,hedef:h}); if(o.hata)return bildir(o.hata,1); ttsIzle()}
async function ttsDurdur(){ await api('/api/tts/durdur',{}); bildir('Durduruluyor…')}
async function ttsKontrol(){ bildir('Güncelleme kontrol ediliyor…'); await ttsDurum(2); bildir(TTS_D.guncelleme_var?'Yeni sürüm var!':(TTS_D.son&&TTS_D.son.hata?'Kontrol edilemedi: '+TTS_D.son.hata:'Chatterbox güncel ✓'),TTS_D.son&&TTS_D.son.hata)}
async function ttsYenilikler(){ const o=await api('/api/tts/yenilikler'); TTS_YENI=o.liste||[]; ttsCiz()}
async function ttsGeri(){ if(!confirm('Bir önceki Chatterbox sürümüne dönülsün mü? (Tekrar basarsan yeni sürüme geri gelir.)'))return;
 const o=await api('/api/tts/geri',{}); if(o.hata)return bildir(o.hata,1); bildir('Önceki sürüme dönüldü ('+tarih(o.surum.tarih)+')'); ttsDurum()}
async function ttsAyarKaydet(){ const v={duygu:+$('#aDuygu').value,cfg:+$('#aCfg').value,sicaklik:+$('#aSic').value,otomatik_kontrol:$('#aKontrol').checked,otomatik_tekrar:$('#aTekrar').checked}; if($('#aModel'))v.model=$('#aModel').value;
 const o=await api('/api/tts/ayar',v); if(o.hata)return bildir(o.hata,1); bildir('Ses ayarları kaydedildi'); ttsDurum()}
function sesYukle(){ const inp=$('#refDosya'); inp.value=''; inp.onchange=async()=>{ const f=inp.files[0]; if(!f)return;
  const ad=prompt('Bu sese bir isim ver (örn: Benim sesim, Kadın anlatıcı, Kalın erkek):', f.name.replace(/\.[^.]+$/,'')); if(ad===null)return;
  const uz=(f.name.match(/\.[a-z0-9]+$/i)||['.wav'])[0].toLowerCase(); bildir('Ses yükleniyor…');
  const r=await fetch(`/api/tts/ses_yukle?ad=${encodeURIComponent(ad)}&uzanti=${uz}`,{method:'POST',body:f}); const o=await r.json();
  if(o.hata)return bildir(o.hata,1);
  if(confirm(`"${ad}" kütüphaneye eklendi ✓\n\nBu projenin ${ANL_DIL.toUpperCase()} seslendirmesinde şimdi bu ses kullanılsın mı?`)) await sesSec(o.id); else ttsDurum()}; inp.click()}
async function sesSec(id,vars){ const o=await api('/api/tts/ses_sec',{ad:AD,dil:ANL_DIL,id,varsayilan:!!vars}); if(o.hata)return bildir(o.hata,1);
 bildir(vars?'Varsayılan ses ayarlandı ✓':'Ses seçildi. Yeni üretimlerde bu ses kullanılacak.'); ttsDurum()}
async function sesAyarKaydet(id){ const o=await api('/api/tts/ses_ayar',{id,hiz:+$('#sHiz').value,duraklama:+$('#sDur').value});
 if(o.hata)return bildir(o.hata,1); bildir('Ses ayarı kaydedildi. Yeni üretimlerde kullanılacak; mevcut sesleri "Yeniden üret" ile güncelleyebilirsin.'); ttsDurum()}
async function sesOlc(id){ const o=await api('/api/tts/ses_olc',{id}); if(o.hata)return bildir(o.hata,1);
 bildir(`Kayda göre ayarlandı: hız ${o.hiz}, duraklama ${o.duraklama} sn`); ttsDurum()}
async function sesAd(id){ const x=TTS_D.sesler.find(s=>s.id===id); const ad=prompt('Yeni isim:',x?x.ad:''); if(!ad)return; await api('/api/tts/ses_ad',{id,ad}); ttsDurum()}
async function sesSil(id){ const x=TTS_D.sesler.find(s=>s.id===id); if(!confirm(`"${x?x.ad:id}" sesi kütüphaneden silinsin mi? (Daha önce üretilmiş seslendirmeler silinmez.)`))return;
 await api('/api/tts/ses_sil',{id}); ttsDurum()}
async function sesTuret(id){ const o=prompt('Ne kadar kalın ya da ince olsun?\n\n0.80 = çok daha kalın · 0.90 = biraz kalın · 1.10 = biraz ince · 1.20 = çok daha ince','0.90'); if(!o)return;
 const r=await api('/api/tts/ses_turet',{id,oran:parseFloat(o.replace(',','.'))}); if(r.hata)return bildir(r.hata,1); bildir('Yeni ses oluşturuldu ✓ Listeden dinleyebilirsin'); ttsDurum()}
async function sablonOlustur(){ if(!confirm('Chatterbox\'un hazır sesinden bir örnek kaydedilip ondan kalın, çok kalın ve ince şablon sesler türetilecek. Birkaç dakika sürer. Devam?'))return;
 const o=await api('/api/tts/sablon',{}); if(o.hata)return bildir(o.hata,1); ttsIzle()}
// --- mikrofonla ses örneği kaydı
const OKU={
 tr:'Merhaba, ben anlatıcınız. Bugün sizi kısa ama ilginç bir yolculuğa çıkarıyorum. Bazen en sıradan görünen şeylerin arkasında şaşırtıcı hikâyeler saklıdır. Bir fincan kahve, eski bir harita ya da tek bir karar, tarihin akışını değiştirebilir. Hazırsanız başlayalım. Sonuna kadar izleyin, çünkü en ilginç kısım en sonda.',
 en:'Hello, I\'m your narrator. Today I\'m taking you on a short but fascinating journey. Sometimes the most ordinary things hide the most surprising stories. A cup of coffee, an old map, or a single decision can change the course of history. If you\'re ready, let\'s begin. Stay until the end, because the best part comes last.',
 pl:'Cześć, jestem waszym narratorem. Dzisiaj zabieram was w krótką, ale fascynującą podróż. Czasami za najzwyklejszymi rzeczami kryją się najbardziej zaskakujące historie. Filiżanka kawy, stara mapa albo jedna decyzja mogą zmienić bieg historii. Jeśli jesteście gotowi, zaczynajmy. Zostańcie do końca, bo najlepsze jest na samym końcu.',
 pt:'Olá, eu sou o seu narrador. Hoje vou levar você numa viagem curta, mas fascinante. Às vezes, as coisas mais comuns escondem as histórias mais surpreendentes. Uma xícara de café, um mapa antigo ou uma única decisão podem mudar o rumo da história. Se estiver pronto, vamos começar. Fique até o fim, porque a melhor parte vem por último.',
 es:'Hola, soy tu narrador. Hoy te llevo a un viaje corto, pero fascinante. A veces, las cosas más comunes esconden las historias más sorprendentes. Una taza de café, un mapa antiguo o una sola decisión pueden cambiar el rumbo de la historia. Si estás listo, empecemos. Quédate hasta el final, porque lo mejor llega al final.'};
let MIK={akis:null,kayitci:null,parca:[],blob:null,url:null,bas:0,zam:null,ctx:null,an:null,dil:null,tip:null};
function mikTip(){ for(const [t,u] of [['audio/webm;codecs=opus','.webm'],['audio/webm','.webm'],['audio/mp4','.m4a'],['audio/ogg;codecs=opus','.ogg']])
  if(window.MediaRecorder&&MediaRecorder.isTypeSupported(t))return [t,u]; return ['','.webm'] }
async function mikAc(){ durdurOyna(); MIK.dil=OKU[ANL_DIL]?ANL_DIL:'tr'; $('#mikPerde').style.display='flex'; mikCiz('hazir'); await mikBaglan() }
function mikCiz(durum){ const d=MIK.dil;
 $('#mikIc').innerHTML=`<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><b style="font-size:17px">Ses örneği kaydet</b>
  <div class="sec">${Object.keys(OKU).map(x=>`<label><input type="radio" name="mikDil" value="${x}" ${x==d?'checked':''} onchange="MIK.dil=this.value;$('#okuMetin').textContent=OKU[this.value]">${x.toUpperCase()}</label>`).join('')}</div>
  <span class="bosluk"></span><button class="btn" onclick="mikKapat()">Kapat</button></div>
  <div class="ipucu">Sessiz bir odada, mikrofona bir karış uzaklıkta, video anlatır gibi doğal bir tonla aşağıdaki metni oku. 15-25 saniye idealdir (en fazla 30 sn). Seslendirilecek dilde kayıt en iyi sonucu verir.</div>
  <div class="okuMetin" id="okuMetin">${kac(OKU[d])}</div>
  <div style="display:flex;align-items:center;gap:12px"><span style="font-size:12px;color:var(--muted);">Mikrofon</span><select id="mikSec" style="flex:1" onchange="mikBaglan(this.value)"></select></div>
  <div class="seviye"><div id="mikSeviye"></div></div><div class="ipucu" id="mikSevNot">Konuşunca çubuk yeşil-sarı arasında oynamalı.</div>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
   <span id="mikSure">0.0 sn</span>
   ${durum==='kayit'?`<span class="kirmiziNokta"></span><button class="btn kirmizi" onclick="mikDur()">■ Durdur</button>`
    :`<button class="btn ana" onclick="mikBasla()">● ${durum==='bitti'?'Yeniden kaydet':'Kaydı başlat'}</button>`}
   ${durum==='bitti'?`<audio id="mikDinle" src="${MIK.url}" controls style="height:36px;flex:1"></audio>`:''}
  </div>
  ${durum==='bitti'?`<div style="display:flex;align-items:center;gap:10px"><input id="mikAd" placeholder="Sesin adı (örn: Benim sesim ${d.toUpperCase()})" value="Benim sesim (${d.toUpperCase()})" style="flex:1;background:var(--p3);border:1px solid var(--line);border-radius:6px;padding:9px 12px">
   <button class="btn ana" onclick="mikKaydet()">✓ Kütüphaneye ekle</button></div>`:''}`;
 mikListe() }
async function mikListe(){ try{ const c=(await navigator.mediaDevices.enumerateDevices()).filter(x=>x.kind==='audioinput'); const s=$('#mikSec'); if(!s)return;
  const akt=MIK.akis&&MIK.akis.getAudioTracks()[0]&&MIK.akis.getAudioTracks()[0].getSettings().deviceId;
  s.innerHTML=c.map((x,i)=>`<option value="${x.deviceId}" ${x.deviceId===akt?'selected':''}>${kac(x.label||('Mikrofon '+(i+1)))}</option>`).join('') }catch(e){} }
async function mikBaglan(id){ mikAkisKapat();
 try{ MIK.akis=await navigator.mediaDevices.getUserMedia({audio:{deviceId:id?{exact:id}:undefined,channelCount:1,echoCancellation:false,noiseSuppression:false,autoGainControl:false}}) }
 catch(e){ $('#mikSevNot').innerHTML='<span class="uyari">Mikrofona erişilemedi. Tarayıcının adres çubuğundaki mikrofon simgesinden izin ver'+(navigator.platform.includes('Mac')?' (Mac: Sistem Ayarları → Gizlilik ve Güvenlik → Mikrofon\'da tarayıcıya izin ver)':'')+', sonra tekrar aç.</span>'; return }
 MIK.ctx=new (window.AudioContext||window.webkitAudioContext)(); MIK.an=MIK.ctx.createAnalyser(); MIK.an.fftSize=1024; MIK.ctx.createMediaStreamSource(MIK.akis).connect(MIK.an);
 const veri=new Float32Array(MIK.an.fftSize); let tepe=0;
 const dongu=()=>{ if(!MIK.an)return; MIK.an.getFloatTimeDomainData(veri); let m=0; for(const v of veri)m=Math.max(m,Math.abs(v)); tepe=Math.max(m,tepe*0.95);
  const el=$('#mikSeviye'), nt=$('#mikSevNot'); if(el)el.style.width=Math.min(100,tepe*130)+'%';
  if(nt&&MIK.kayitci&&MIK.kayitci.state==='recording'){ nt.innerHTML=tepe>0.98?'<span class="uyari">Çok yüksek, ses bozulabilir: mikrofondan biraz uzaklaş.</span>':tepe<0.05?'<span class="uyari">Çok sessiz: biraz daha yüksek sesle konuş ya da mikrofona yaklaş.</span>':'<span class="tamam">Ses seviyesi iyi ✓</span>' }
  requestAnimationFrame(dongu) }; dongu(); mikListe() }
function mikAkisKapat(){ if(MIK.akis)MIK.akis.getTracks().forEach(t=>t.stop()); MIK.akis=null; if(MIK.ctx)MIK.ctx.close().catch(()=>{}); MIK.ctx=null; MIK.an=null }
function mikBasla(){ if(!MIK.akis)return bildir('Mikrofon bağlı değil',1); const [tip,uz]=mikTip(); MIK.tip=uz; MIK.parca=[];
 MIK.kayitci=new MediaRecorder(MIK.akis,tip?{mimeType:tip}:{}); MIK.kayitci.ondataavailable=e=>{if(e.data.size)MIK.parca.push(e.data)};
 MIK.kayitci.onstop=()=>{ clearInterval(MIK.zam); MIK.blob=new Blob(MIK.parca,{type:MIK.kayitci.mimeType||tip}); if(MIK.url)URL.revokeObjectURL(MIK.url); MIK.url=URL.createObjectURL(MIK.blob);
  const sure=(performance.now()-MIK.bas)/1000; mikCiz('bitti'); $('#mikSure').textContent=sure.toFixed(1)+' sn';
  if(sure<8)$('#mikSevNot').innerHTML='<span class="uyari">Kayıt kısa ('+sure.toFixed(0)+' sn). En az 10-15 sn önerilir; istersen yeniden kaydet.</span>' };
 MIK.kayitci.start(250); MIK.bas=performance.now(); mikCiz('kayit');
 MIK.zam=setInterval(()=>{ const t=(performance.now()-MIK.bas)/1000; const el=$('#mikSure'); if(el)el.textContent=t.toFixed(1)+' sn'; if(t>=30)mikDur() },100) }
function mikDur(){ if(MIK.kayitci&&MIK.kayitci.state==='recording')MIK.kayitci.stop() }
async function mikKaydet(){ const ad=($('#mikAd').value||'').trim()||'Benim sesim'; bildir('Kaydediliyor…');
 const r=await fetch(`/api/tts/ses_yukle?ad=${encodeURIComponent(ad)}&uzanti=${MIK.tip}`,{method:'POST',body:MIK.blob}); const o=await r.json();
 if(o.hata)return bildir(o.hata,1); const dil=MIK.dil; mikKapat(); TTS_AYAR=true;
 if(confirm(`"${ad}" kütüphaneye eklendi ✓\n\nBu projenin ${dil.toUpperCase()} seslendirmesinde bu ses kullanılsın mı?`)){
  await api('/api/tts/ses_sec',{ad:AD,dil,id:o.id}); bildir('Ses seçildi ✓') } ttsDurum() }
function mikKapat(){ mikDur(); mikAkisKapat(); clearInterval(MIK.zam); $('#mikPerde').style.display='none'; $('#mikIc').innerHTML='' }
// --- storyboard
let SB=null;
async function storyboardAc(){ if(projeYok())return; durdurOyna(); ANL_ACIK=false; SB=await api('/api/storyboard?ad='+encodeURIComponent(AD)); sbCiz(false);
 $('#perde').style.display='flex'; if(!SB.zaman) storyboardCikar() }
function sbCiz(yukleniyor){ const dil=$('#onizDil').value;
 const kart=s=>{ const sb=s.storyboard||{}, a=(s.anlatim||{})[dil];
  const kareler=s.kareler.length?s.kareler.map((u,i)=>`<div><img src="${u}" onclick="izleResim('${u}')"><span>${i?'geçiş':'orta'} ${s.anlar[i]!=null?s.anlar[i].toFixed(1)+'s':''}</span></div>`).join('')
   :`<div class="sbBos">${yukleniyor?'çiziliyor…':'Kare yok'}</div><div class="sbBos">${s.tur==='vektor'&&!s.url?'Sahne dosyası yok':''}</div>`;
  return `<div class="sbKart"><div class="ust"><div class="no">${s.no}</div><div style="flex:1"><div class="sb">${kac(s.baslik||s.tur)}</div>
   <div class="st">${s.bas.toFixed(1)}–${(s.bas+s.sure).toFixed(1)} sn</div></div><button class="btn kucuk" onclick="perdeKapat();git(${s.bas+0.01})" title="Önizlemede bu sahneye git">▶</button></div>
   <div class="sbKareler">${kareler}</div>
   ${a?`<div class="sbNot"><b></b> ${kac(a)}</div>`:''}
   ${sb.ekranda?`<div class="sbNot"><b>Ekranda:</b> ${kac(sb.ekranda)}</div>`:''}${sb.hareket?`<div class="sbNot"><b>Hareket:</b> ${kac(sb.hareket)}</div>`:''}
   ${sb.gecis?`<div class="sbNot"><b>Sonrakine geçiş:</b> ${kac(sb.gecis)}</div>`:''}
   ${s.uyarilar.map(u=>`<div class="uyari" style="font-size:12.5px">⚠ ${kac(u)}</div>`).join('')}</div>` };
 $('#perdeIc').innerHTML=`<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><b style="font-size:16px">Storyboard</b>
  <span class="ipucu">${yukleniyor?'Ana kareler çiziliyor, video çizilmiyor (birkaç saniye – 1 dk)…':SB.zaman?'Her sahnenin ortasından ve geçiş anından birer kare. Notlar için "4\'ten 5\'e geçiş olmadı" gibi numarayla söyle.':''}</span>
  <span class="bosluk"></span><button class="btn kucuk" onclick="storyboardCikar()" ${yukleniyor?'disabled':''}>Kareleri yeniden çıkar</button>
  ${SB.sayfa?`<button class="btn kucuk" onclick="izleResim('${SB.sayfa}')">Tek sayfa</button>`:''}
  <button class="btn" onclick="perdeKapat()">Kapat</button></div>
  ${SB.hata?`<div class="uyari">${kac(SB.hata)}</div>`:''}<div class="sbIzgara">${(SB.sahneler||[]).map(kart).join('')}</div>` }
async function storyboardCikar(){ sbCiz(true);
 const o=await api('/api/storyboard',{ad:AD,dil:$('#onizDil').value}); if(o.hata&&!o.sahneler){bildir(o.hata,1); SB.hata=o.hata; return sbCiz(false)}
 SB=o; if($('#perde').style.display==='flex')sbCiz(false); bildir('Storyboard hazır ✓') }
function izleResim(u){ const w=window.open(u,'_blank'); if(!w)location.href=u }
// --- ses dinleme: tek oynatıcı; aynı düğmeye tekrar basınca durur, başka sese geçince öncekini keser
let CALAN=null, CALAN_BTN=null, CALAN_URL=null;
function sesCal(url, btn, oran){
 const ayni=CALAN&&CALAN_URL===url; sesDur(); if(ayni)return;
 CALAN=new Audio(url); CALAN_URL=url; CALAN_BTN=btn||null; if(oran&&oran!==1){CALAN.preservesPitch=true; CALAN.playbackRate=oran}
 if(CALAN_BTN){CALAN_BTN.dataset.yazi=CALAN_BTN.innerHTML; CALAN_BTN.innerHTML='■ Durdur'; CALAN_BTN.classList.add('kirmizi')}
 CALAN.onended=sesDur; CALAN.play().catch(()=>sesDur())}
function sesDur(){ if(CALAN){CALAN.pause(); CALAN.onended=null}
 if(CALAN_BTN&&CALAN_BTN.dataset.yazi!==undefined){CALAN_BTN.innerHTML=CALAN_BTN.dataset.yazi; CALAN_BTN.classList.remove('kirmizi')}
 CALAN=null; CALAN_BTN=null; CALAN_URL=null}
function kontrolRozet(k){ if(!k)return ''; const y=Math.round(100*k.benzerlik), iyi=k.benzerlik>=0.95;
 const ayr=[k.eksik.length?`Okunmayan: ${k.eksik.join(', ')}`:'', k.fazla.length?`Fazladan duyulan: ${k.fazla.join(', ')}`:'', `Whisper'ın duyduğu: "${k.duyulan}"`].filter(Boolean).join('\n');
 return `<div class="${iyi?'tamam':'uyari'}" style="font-size:12.5px;cursor:help" title="${kac(ayr)}">${iyi?'✓':'⚠'} Whisper %${y}${!iyi&&k.eksik.length?' · eksik: '+kac(k.eksik.slice(0,5).join(', ')):''}</div>` }
async function whisperKontrol(hepsi){ const o=await api('/api/tts/kontrol',{ad:AD,dil:ANL_DIL,hepsi:!!hepsi}); if(o.hata)return bildir(o.hata,1); ttsIzle()}
function duzenleyici(){ if(projeYok())return; durdurOyna(); ANL_ACIK=false; $('#perdeIc').innerHTML=`<div style="display:flex;align-items:center;gap:10px"><b>Senaryo (video.yaml)</b><span class="ipucu">Ctrl+S ile kaydet. Tüm seçenekler: bos_sablon.yaml</span><span class="bosluk"></span>
 <button class="btn ana" onclick="kaydet()">Kaydet</button><button class="btn" onclick="perdeKapat()">Kapat</button></div><textarea id="metin" spellcheck="false"></textarea>`;
 $('#metin').value=P.metin; $('#perde').style.display='flex';
 $('#metin').onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();kaydet()}
  if(e.key==='Tab'){e.preventDefault();const t=e.target,s=t.selectionStart;t.setRangeText('  ',s,t.selectionEnd,'end')}}}
async function kaydet(){ const o=await api('/api/kaydet',{ad:AD,metin:$('#metin').value}); if(o.hata)return bildir(o.hata,1);
 bildir('Kaydedildi'); perdeKapat(); await projeAc(AD)}
const STILLER=[['vektor','Vektör','Düz renkli, yumuşak hareketli 2D çizimler. Açıklayıcı videolar için en esnek tarz.'],
 ['uc','3D','Yumuşak ışıklı, gölgeli 3D sahneler: gezegenler, nesneler, maketler. Çizimi biraz daha uzun sürer.'],
 ['piksel','Piksel art','Eski oyunlar gibi piksel piksel çizilmiş sahneler ve karakterler. Hikâye ve tarih anlatımına uygun.']];
function yeniProje(){ durdurOyna(); ANL_ACIK=false;
 $('#perdeIc').innerHTML=`<div style="width:min(760px,90vw);display:flex;flex-direction:column;gap:14px">
  <h3 style="margin:0;font-size:16px">Yeni proje</h3>
  <label class="ipucu" style="display:flex;flex-direction:column;gap:6px">Proje adı (küçük harf, rakam ve tire; örn: piri-reis)
   <input id="ypAd" style="font-size:14px" autocomplete="off" spellcheck="false"></label>
  <div class="ipucu">Tarz: Claude bu projenin sahnelerini seçtiğin tarzda yazar.</div>
  <div class="stiller">${STILLER.map(([k,b,a],i)=>`<label class="stil"><input type="radio" name="ypStil" value="${k}" ${i==0?'checked':''}>
   <img src="/k/veri/stiller/${k}.jpg" alt=""><b>${b}</b><span class="ipucu">${a}</span></label>`).join('')}</div>
  ${AD?`<label class="onay" style="margin:0"><input type="checkbox" id="ypKopya"><span><b>${kac(AD)} projesini kopyala</b>Tarz seçimi yerine şu anki projenin sahneleri ve metinleri kopyalanır (sesler ve videolar hariç).</span></label>`:''}
  <div style="display:flex;gap:8px"><span class="bosluk"></span><button class="btn" onclick="perdeKapat()">Vazgeç</button><button class="btn ana" onclick="yeniOlustur()">Oluştur</button></div></div>`;
 $('#perde').style.display='flex'; setTimeout(()=>$('#ypAd').focus(),50);
 $('#ypAd').onkeydown=e=>{ if(e.key==='Enter')yeniOlustur() } }
async function yeniOlustur(){ const ad=$('#ypAd').value.trim().toLowerCase().replace(/\s+/g,'-'); if(!ad)return $('#ypAd').focus();
 const stil=document.querySelector('input[name=ypStil]:checked').value, kopya=!!($('#ypKopya')&&$('#ypKopya').checked);
 const o=await api('/api/yeni',{ad,kaynak:AD,kopya,stil,dil:DIL}); if(o.hata)return bildir(o.hata,1);
 perdeKapat(); await projeleriYukle(o.ad); bildir('Proje oluşturuldu: '+o.ad)}
function ac(alt){ if(projeYok())return; api('/api/ac',{ad:AD,alt})}
async function studyoKapat(){ if(!confirm('Stüdyo kapatılsın mı? (Süren video ya da seslendirme işi durdurulur.)'))return; await api('/api/kapat',{});
 document.body.innerHTML='<div style="margin:auto;text-align:center;font-size:20px;color:#d8d6d0">Stüdyo kapatıldı.<br><span style="font-size:14px;color:var(--muted)">Bu sekmeyi kapatabilirsin. Tekrar açmak için Animasyon Stüdyosu simgesine tıkla.</span></div>'}
dilKur(); projeleriYukle().then(()=>{ if(!localStorage.getItem('kilavuzGoruldu'))kilavuz(); else guncellemeDenetle(false) }); ttsDurum(1); $('#altyazi').checked=localStorage.getItem('altyazi')==='1'; $('#onceSes').checked=localStorage.getItem('onceSes')!=='0'; api('/api/durum').then(s=>{if(s.calisiyor){$('#olusturBtn').disabled=true;$('#durBtn').style.display='';izle()}});
</script></body></html>"""


SUNUCU = {"s": None}


def kapat():
    time.sleep(0.5)
    tts.ISCI.durdur()
    if SUNUCU["s"]:
        SUNUCU["s"].shutdown()


class StudyoSunucu(ThreadingHTTPServer):
    """Windows'ta aynı portu ikinci bir sürecin almasını engeller (açık stüdyo varsa onu gösteririz)."""
    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main():
    adres = f"http://127.0.0.1:{PORT}"
    if "--gizli" in sys.argv:      # "Animasyon Stüdyosu.exe" ile penceresiz açılış: yazılar kayıt dosyasına
        try:
            os.makedirs(os.path.join(KOK, "veri"), exist_ok=True)
            sys.stdout = sys.stderr = open(os.path.join(KOK, "veri", "studyo.log"), "w", encoding="utf-8", buffering=1)
        except OSError:
            pass
    sunucu = None
    bitis = time.time() + (20 if os.environ.pop("ANIMASYON_BEKLE", None) else 0)   # güncellemeden sonra: eski süreç kapanana kadar bekle
    while sunucu is None:
        try:
            sunucu = StudyoSunucu(("127.0.0.1", PORT), Isleyici)
        except OSError:
            if time.time() < bitis:
                time.sleep(0.4)
                continue
            break
    if sunucu is None:   # stüdyo zaten açık: sadece tarayıcıda göster
        print("Stüdyo zaten açık, tarayıcıda gösteriliyor:", adres)
        if "--tarayici-acma" not in sys.argv:
            webbrowser.open(adres)
        return
    SUNUCU["s"] = sunucu
    print(f"Animasyon Stüdyosu çalışıyor: {adres}")
    print("Bu pencereyi kapatırsan stüdyo da kapanır.")
    if "--tarayici-acma" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(adres)).start()
    tts.arkaplan_baslat()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        tts.ISCI.durdur()
        print("Stüdyo kapandı.")


if __name__ == "__main__":
    main()
