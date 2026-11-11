"""Stüdyonun kendini GitHub'dan güncellemesi.

Yeni sürüm = depodaki `.surum` dosyasının numarası yüklü olandan büyük. Güncellemede program dosyaları
değişir; projeler, sesler (tts/), indirilen modeller ve ayarlar olduğu gibi kalır.
"""
import io, json, os, shutil, ssl, subprocess, sys, threading, time, urllib.request, zipfile

KOK = os.path.dirname(os.path.abspath(__file__))
DEPO = os.environ.get("ANIMASYON_DEPO", "ordinaryboy81/Animation-Studio")
DAL = os.environ.get("ANIMASYON_DAL", "main")
# test ve çatallar için: ANIMASYON_GUNCELLEME_URL=http://.../ (içinde .surum, degisiklikler.json, kaynak.zip)
TEST = os.environ.get("ANIMASYON_GUNCELLEME_URL")
HAM = TEST or f"https://raw.githubusercontent.com/{DEPO}/{DAL}/"
ZIP = (TEST + "kaynak.zip") if TEST else f"https://codeload.github.com/{DEPO}/zip/refs/heads/{DAL}"
DOKUNMA = {"projeler", "docs", "paket", ".github", ".gitignore", "tts", ".ortam", ".python", ".uv_cache", ".bin", "bin"}

IS = {"calisiyor": False, "asama": "", "hata": None, "bitti": False}
_ONBELLEK = {"zaman": 0, "veri": None}


def _baglam():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def indir(url, zaman_asimi=30):
    """URL'nin içeriğini döndürür. Python'un sertifikaları yoksa (bazı Mac kurulumları) curl'e düşer."""
    istek = urllib.request.Request(url, headers={"User-Agent": "animation-studio", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(istek, timeout=zaman_asimi, context=_baglam()) as r:
            return r.read()
    except (ssl.SSLError, urllib.error.URLError) as e:
        if isinstance(e, urllib.error.HTTPError) or not shutil.which("curl"):
            raise
        return subprocess.run(["curl", "-fsSL", "--max-time", str(zaman_asimi), url], check=True, capture_output=True).stdout


def kiyas(s):
    try:
        return tuple(int(x) for x in str(s).strip().split("."))
    except ValueError:
        return (0,)


def yerel_surum():
    try:
        return open(os.path.join(KOK, ".surum"), encoding="utf-8").read().strip()
    except OSError:
        return None


def mod():
    """acik: kendini günceller · git: git ile yönetilen klasör (git pull) · yok: sürüm dosyası yok"""
    if os.path.isdir(os.path.join(KOK, ".git")):
        return "git"
    return "acik" if yerel_surum() else "yok"


def kontrol(zorla=False):
    yerel = yerel_surum()
    d = {"surum": yerel, "mod": mod(), "son": None, "yeni": False, "notlar": [], "depo": DEPO}
    if d["mod"] == "yok":
        return d
    if not zorla and _ONBELLEK["veri"] and time.time() - _ONBELLEK["zaman"] < 3600:
        return dict(d, **{k: _ONBELLEK["veri"][k] for k in ("son", "yeni", "notlar")}, hata=_ONBELLEK["veri"].get("hata"))
    try:
        son = indir(HAM + ".surum?t=%d" % time.time(), 10).decode("utf-8").strip()
        d["son"] = son
        d["yeni"] = kiyas(son) > kiyas(yerel)
        if d["yeni"]:
            try:
                tum = json.loads(indir(HAM + "degisiklikler.json?t=%d" % time.time(), 10).decode("utf-8"))
                d["notlar"] = [n for n in tum if kiyas(n.get("surum")) > kiyas(yerel)]
            except Exception:  # noqa: BLE001
                d["notlar"] = []
    except Exception as e:  # noqa: BLE001
        d["hata"] = f"Güncelleme denetlenemedi ({type(e).__name__})."
    _ONBELLEK.update(zaman=time.time(), veri=d)
    return d


def baslat(mesgul=None):
    if IS["calisiyor"]:
        raise ValueError("Güncelleme zaten sürüyor.")
    if mod() != "acik":
        raise ValueError("Bu klasör git ile yönetiliyor; güncellemek için 'git pull' kullan." if mod() == "git"
                         else "Bu kurulumda sürüm bilgisi yok, kendini güncelleyemez.")
    if mesgul:
        raise ValueError(mesgul)
    IS.update(calisiyor=True, asama="İndiriliyor…", hata=None, bitti=False)
    threading.Thread(target=_is, daemon=True).start()


def _kopyala(kaynak, hedef):
    """kaynak klasördeki dosyaları hedefe yazar; hedefte fazladan olan dosyalara dokunmaz."""
    for kok, dizinler, dosyalar in os.walk(kaynak):
        goreli = os.path.relpath(kok, kaynak)
        dizinler[:] = [x for x in dizinler if x != "__pycache__"]
        os.makedirs(os.path.join(hedef, goreli), exist_ok=True)
        for f in dosyalar:
            k, h = os.path.join(kok, f), os.path.join(hedef, goreli, f)
            gecici = h + ".yeni"
            shutil.copyfile(k, gecici)
            try:
                shutil.copymode(k, gecici)
            except OSError:
                pass
            os.replace(gecici, h)


def _paket_kurucu():
    for uv in (os.path.join(KOK, "bin", "uv.exe"), os.path.join(KOK, ".bin", "uv")):
        if os.path.isfile(uv):
            return [uv, "pip", "install", "-q", "--python", sys.executable, "-r"]
    return [sys.executable, "-m", "pip", "install", "-q", "-r"]


def _is():
    gecici = os.path.join(KOK, ".guncelleme")
    try:
        veri = indir(ZIP, 120)
        IS["asama"] = "Dosyalar açılıyor…"
        shutil.rmtree(gecici, ignore_errors=True)
        with zipfile.ZipFile(io.BytesIO(veri)) as z:
            z.extractall(gecici)
        kokler = [os.path.join(gecici, x) for x in os.listdir(gecici)]
        yeni = kokler[0] if len(kokler) == 1 and os.path.isdir(kokler[0]) else gecici
        if not os.path.isfile(os.path.join(yeni, "arayuz.py")) or not os.path.isfile(os.path.join(yeni, ".surum")):
            raise RuntimeError("İndirilen dosya stüdyoya benzemiyor.")
        surum = open(os.path.join(yeni, ".surum"), encoding="utf-8").read().strip()
        eski_gerek = _oku(os.path.join(KOK, "gereksinimler.txt"))

        IS["asama"] = "Yeni dosyalar yerleştiriliyor…"
        hedefler = [KOK] + _mac_paketleri()
        for hedef in hedefler:
            for ad in os.listdir(yeni):
                if ad in DOKUNMA or ad == ".surum":
                    continue
                k = os.path.join(yeni, ad)
                if os.path.isdir(k):
                    _kopyala(k, os.path.join(hedef, ad))
                else:
                    _kopyala_dosya(k, os.path.join(hedef, ad))
        _mac_baslatici(yeni)

        if _oku(os.path.join(yeni, "gereksinimler.txt")) != eski_gerek:
            IS["asama"] = "Gerekli paketler güncelleniyor…"
            r = subprocess.run(_paket_kurucu() + [os.path.join(KOK, "gereksinimler.txt")], capture_output=True, text=True, cwd=KOK)
            if r.returncode != 0:
                raise RuntimeError("Paketler kurulamadı: " + (r.stderr or r.stdout)[-300:])

        for hedef in hedefler:          # sürüm numarası en son: yarıda kalırsa bir dahaki sefere yeniden dener
            _kopyala_dosya(os.path.join(yeni, ".surum"), os.path.join(hedef, ".surum"))
        _ONBELLEK.update(zaman=0, veri=None)
        IS.update(asama=f"Sürüm {surum} kuruldu. Stüdyo yeniden başlatılıyor…", bitti=True, surum=surum)
    except Exception as e:  # noqa: BLE001
        IS.update(hata=f"Güncelleme yapılamadı: {e}", asama="Hata")
    finally:
        shutil.rmtree(gecici, ignore_errors=True)
        IS["calisiyor"] = False


def _oku(yol):
    try:
        return open(yol, encoding="utf-8").read()
    except OSError:
        return None


def _kopyala_dosya(k, h):
    gecici = h + ".yeni"
    shutil.copyfile(k, gecici)
    os.replace(gecici, h)


def _mac_paketleri():
    """Mac'te uygulama paketinin içindeki kopya da güncellenir (yoksa uygulama açılışta eski sürümü geri yazar)."""
    if sys.platform != "darwin":
        return []
    sonuc = []
    for app in ("/Applications/Animation Studio.app", os.path.expanduser("~/Applications/Animation Studio.app")):
        r = os.path.join(app, "Contents", "Resources", "uygulama")
        if os.path.isdir(r) and os.access(r, os.W_OK):
            sonuc.append(r)
    return sonuc


def _mac_baslatici(yeni):
    kaynak = os.path.join(yeni, "paket", "mac", "AnimationStudio")
    if sys.platform != "darwin" or not os.path.isfile(kaynak):
        return
    for r in _mac_paketleri():
        h = os.path.join(os.path.dirname(os.path.dirname(r)), "MacOS", "AnimationStudio")
        try:
            _kopyala_dosya(kaynak, h)
            os.chmod(h, 0o755)
        except OSError:
            pass


def yeniden_baslat(kapat):
    """Yeni bir stüdyo süreci başlatır (eskisi kapanınca portu alır) ve bu süreci kapatır."""
    komut = [sys.executable, os.path.join(KOK, "arayuz.py"), "--tarayici-acma", "--gizli"]
    ortam = dict(os.environ, ANIMASYON_BEKLE="1")
    if os.name == "nt":
        subprocess.Popen(komut, cwd=KOK, env=ortam, creationflags=0x00000008 | 0x00000200, close_fds=True)   # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        subprocess.Popen(komut, cwd=KOK, env=ortam, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    kapat()
    threading.Timer(3.0, lambda: os._exit(0)).start()
