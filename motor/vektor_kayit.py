"""Vektör (SVG/HTML) sahneleri tarayıcıyla kare kare kaydeder.
Windows'ta yüklü Edge'i, yoksa Chrome'u, yoksa Playwright'ın kendi Chromium'unu kullanır."""
import functools, json, os, re, subprocess, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Sessiz(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def sunucu_baslat():
    """Proje klasörünü yerel olarak sunar; adresini döndürür."""
    s = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Sessiz, directory=KOK))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{s.server_address[1]}", s


def tarayici_ac(p):
    hatalar = []
    for kanal in ("msedge", "chrome", None):
        try:
            # 3D sahneler WebGL ister: ekran kartı yoksa ya da engelliyse yazılımla çizilir
            ek = ["--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]
            return p.chromium.launch(channel=kanal, args=ek) if kanal else p.chromium.launch(args=ek)
        except Exception as e:
            hatalar.append(f"{kanal or 'chromium'}: {str(e).splitlines()[0]}")
    raise RuntimeError("Tarayıcı açılamadı. Edge veya Chrome yüklü olmalı. Ayrıntı: " + " | ".join(hatalar))


def sayfa_url(taban, sahne_dosyasi, dil, mod="kayit", sonraki=None):
    yol = os.path.relpath(sahne_dosyasi, KOK).replace("\\", "/")
    return f"{taban}/{yol}?mod={mod}&dil={dil}" + (f"&sonraki={sonraki}" if sonraki else "")


def arka_rengi(sahne_dosyasi):
    """Vektör sahnenin ilk arka plan rengini (arka: ["#..." ...]) dosyadan okur; '#' olmadan döndürür."""
    try:
        with open(sahne_dosyasi, encoding="utf-8") as f:
            m = re.search(r"arka\s*:\s*\[?\s*[\"'](#[0-9a-fA-F]{3,8})", f.read())
        return m.group(1)[1:] if m else None
    except OSError:
        return None


def _sayfa(p, tarayici, url, W, H, olcek=1):
    sayfa = tarayici.new_page(viewport={"width": W, "height": H}, device_scale_factor=olcek)
    sayfa.goto(url)
    sayfa.wait_for_function("window.HAZIR === true", timeout=30000)
    return sayfa


def kaydet(url, W, H, sure, fps, hedef, ilerleme=None, bas=0, son=None, olcek=1):
    """Sahnenin [bas, son) karelerini mp4 yazar. Sahneler zamanın saf fonksiyonu olduğu için bir sahne
    birkaç parçaya bölünüp ayrı süreçlerde çizilebilir. olcek < 1: hızlı taslak (düşük çözünürlükte yakalanır)."""
    import base64
    from playwright.sync_api import sync_playwright
    gecici = hedef[:-4] + ".gecici.mp4"
    buyut = ["-vf", f"scale={W}:{H}:flags=bicubic"] if olcek != 1 else []
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-r", str(fps), "-i", "-"] + buyut +
                          ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18" if olcek == 1 else "23", "-pix_fmt", "yuv420p",
                           "-r", str(fps), gecici], stdin=subprocess.PIPE)
    n = int(round(sure * fps))
    son = n if son is None else min(son, n)
    with sync_playwright() as p:
        tarayici = tarayici_ac(p)
        sayfa = _sayfa(p, tarayici, url, W, H, olcek)
        try:    # doğrudan tarayıcı protokolü: Playwright'ın ekran görüntüsünden daha hızlı
            cdp = sayfa.context.new_cdp_session(sayfa)
            cek = lambda: base64.b64decode(cdp.send("Page.captureScreenshot", {
                "format": "jpeg", "quality": 93 if olcek == 1 else 85, "optimizeForSpeed": True})["data"])
            sayfa.evaluate("t => V.git(t)", bas / fps); cek()
        except Exception:  # noqa: BLE001
            cek = lambda: sayfa.screenshot(type="jpeg", quality=93 if olcek == 1 else 85)
        for i in range(bas, son):
            sayfa.evaluate("t => V.git(t)", i / fps)
            ff.stdin.write(cek())
            k = i - bas
            if ilerleme and (k % 10 == 0 or i == son - 1):
                ilerleme(k + 1, son - bas)
        tarayici.close()
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg hata verdi (vektör sahne)")
    os.replace(gecici, hedef)


def tek_kare(url, W, H, t, hedef_png):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        tarayici = tarayici_ac(p)
        sayfa = _sayfa(p, tarayici, url, W, H)
        sayfa.evaluate("t => V.git(t)", t)
        sayfa.screenshot(path=hedef_png)
        tarayici.close()


def coklu_kare(isler, W, H):
    """Tek tarayıcı oturumunda birden çok kare çeker. isler: [(url, [(t, png_yolu), ...]), ...]
    Her sahne için motorun uyarılarını (window.UYARILAR) döndürür."""
    from playwright.sync_api import sync_playwright
    uyarilar = []
    with sync_playwright() as p:
        tarayici = tarayici_ac(p)
        for url, kareler in isler:
            sayfa = _sayfa(p, tarayici, url, W, H)
            for t, yol in kareler:
                sayfa.evaluate("t => V.git(t)", t)
                sayfa.screenshot(path=yol)
            uyarilar.append(sayfa.evaluate("window.UYARILAR || []"))
            sayfa.close()
        tarayici.close()
    return uyarilar
