"""
Chatterbox seslendirme işçisi.
Stüdyo bu betiği Chatterbox'un kendi Python ortamında (tts/env) arka planda çalıştırır.
Elle çalıştırmana gerek yok.

Protokol: stdin'den her satırda bir JSON istek gelir, stdout'a '@@' ile başlayan tek satır JSON cevap yazılır.
Kütüphanelerin kendi çıktıları (indirme çubukları vs.) stderr'e gider ve stüdyonun kayıtlarında görünür.
"""
import json
import re
import sys
import traceback
import wave

CIKIS = sys.stdout
sys.stdout = sys.stderr          # kütüphane print'leri protokolü bozmasın


def gonder(d):
    CIKIS.write("@@" + json.dumps(d, ensure_ascii=False) + "\n")
    CIKIS.flush()


try:
    import numpy as np
    import torch
except Exception as e:  # noqa: BLE001
    gonder({"hata": f"PyTorch yüklenemedi: {e}"})
    sys.exit(1)

if torch.cuda.is_available():
    CIHAZ = "cuda"
elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
    CIHAZ = "mps"          # Apple Silicon Mac
else:
    CIHAZ = "cpu"
gonder({"hazir": True, "cihaz": CIHAZ, "gpu": torch.cuda.get_device_name(0) if CIHAZ == "cuda" else
        ("Apple GPU (MPS)" if CIHAZ == "mps" else None)})

MODEL = None
MODEL_AD = None
VARSAYILAN_KOSUL = None
SON_REF = ("-",)


def yukle(ad):
    global MODEL, MODEL_AD, VARSAYILAN_KOSUL, SON_REF
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    MODEL = None
    if CIHAZ == "cuda":
        torch.cuda.empty_cache()
    elif CIHAZ == "mps":
        torch.mps.empty_cache()
    try:
        m = ChatterboxMultilingualTTS.from_pretrained(device=CIHAZ, t3_model=ad or None)
    except TypeError:            # model seçimi olmayan eski sürümler
        m = ChatterboxMultilingualTTS.from_pretrained(device=CIHAZ)
    MODEL, MODEL_AD, VARSAYILAN_KOSUL, SON_REF = m, ad, m.conds, ("-",)


def parcala(metin, sinir=260):
    """Metni cümlelere böler (her cümle ayrı üretilir, araya ayarlanabilir duraklama girer).
    Çok kısa cümleler bir öncekine eklenir, çok uzunlar virgülden bölünür."""
    metin = re.sub(r"\s+", " ", metin).strip()
    if not metin:
        return []
    cumleler = [c.strip() for c in re.split(r"(?<=[.!?…;:])\s+", metin) if c.strip()]
    parcalar = []
    for c in cumleler:
        while len(c) > sinir:                      # tek cümle bile çok uzunsa virgülden böl
            kes = c.rfind(",", 0, sinir)
            kes = kes if kes > 40 else c.rfind(" ", 0, sinir)
            kes = kes if kes > 0 else sinir
            parcalar.append(c[:kes + 1].strip()); c = c[kes + 1:].strip()
        if parcalar and (len(c) < 18 or len(parcalar[-1]) < 18) and len(parcalar[-1]) + len(c) < sinir:
            parcalar[-1] = parcalar[-1] + " " + c   # "Tam üç!" gibi çok kısa cümleler tek başına kötü okunur
        else:
            parcalar.append(c)
    return [p for p in parcalar if p]


def kirp(a, sr, esik=0.012, pay=0.04):
    """Parçanın başındaki ve sonundaki sessizliği kırpar (duraklamalar eşit olsun)."""
    pencere = max(1, int(sr * 0.01))
    if len(a) < pencere * 4:
        return a
    enerji = np.sqrt(np.convolve(a * a, np.ones(pencere) / pencere, mode="same"))
    ses = np.where(enerji > esik)[0]
    if not len(ses):
        return a
    bas = max(0, ses[0] - int(sr * pay)); son = min(len(a), ses[-1] + int(sr * pay * 2))
    return a[bas:son]


def uret(d):
    global SON_REF
    ayar = d.get("ayar") or {}
    model_ad = ayar.get("model") or None
    if MODEL is None or MODEL_AD != model_ad:
        yukle(model_ad)
    duygu = float(ayar.get("duygu", 0.5))
    ref = d.get("referans") or None
    anahtar = (ref, d.get("referans_zaman"))
    if anahtar != SON_REF:
        if ref:
            MODEL.prepare_conditionals(ref, exaggeration=duygu)
        else:
            MODEL.conds = VARSAYILAN_KOSUL
        SON_REF = anahtar
    if ayar.get("tohum") not in (None, "", 0):
        torch.manual_seed(int(ayar["tohum"]))

    sr = MODEL.sr
    sessizlik = np.zeros(int(sr * max(0.0, float(d.get("duraklama", 0.3)))), dtype=np.float32)
    parcalar = []
    for i, p in enumerate(parcala(d["metin"])):
        wav = MODEL.generate(p, language_id=d["dil"], exaggeration=duygu,
                             cfg_weight=float(ayar.get("cfg", 0.5)), temperature=float(ayar.get("sicaklik", 0.8)))
        a = kirp(wav.squeeze().detach().float().cpu().numpy(), sr)
        if i:
            parcalar.append(sessizlik)
        parcalar.append(a)
    if not parcalar:
        return {"hata": "Metin boş"}
    ses = np.clip(np.concatenate(parcalar), -1.0, 1.0)
    with wave.open(d["cikti"], "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((ses * 32767).astype("<i2").tobytes())
    return {"tamam": True, "sure": round(len(ses) / sr, 2)}


# ---------------- Whisper (konuşma tanıma): seslendirme kontrolü ve altyazı zamanlaması ----------------
ASR = None
WHISPER = "openai/whisper-large-v3-turbo"
DIL_AD = {"tr": "turkish", "en": "english", "pl": "polish", "pt": "portuguese", "es": "spanish", "de": "german", "fr": "french",
          "it": "italian", "nl": "dutch", "ru": "russian", "ar": "arabic", "ja": "japanese", "ko": "korean", "zh": "chinese",
          "hi": "hindi", "sv": "swedish", "da": "danish", "fi": "finnish", "no": "norwegian", "el": "greek", "he": "hebrew",
          "ms": "malay", "sw": "swahili"}


def yazi(d):
    """Ses dosyasını yazıya döker: kelime kelime zamanlarıyla."""
    global ASR
    if ASR is None:
        from transformers import pipeline
        ASR = pipeline("automatic-speech-recognition", model=d.get("model") or WHISPER,
                       torch_dtype=torch.float16 if CIHAZ == "cuda" else torch.float32, device=CIHAZ,
                       model_kwargs={"attn_implementation": "eager"})
    import librosa
    y, _ = librosa.load(d["ses"], sr=16000, mono=True)
    kw = {"task": "transcribe"}
    if DIL_AD.get(d.get("dil")):
        kw["language"] = DIL_AD[d["dil"]]
    ek = {"chunk_length_s": 30, "batch_size": 4} if len(y) > 16000 * 29 else {}
    out = ASR({"raw": y, "sampling_rate": 16000}, return_timestamps="word", generate_kwargs=kw, **ek)
    kelimeler, son = [], 0.0
    for c in out.get("chunks", []):
        bas, bit = c.get("timestamp", (None, None))
        bas = son if bas is None else float(bas)
        bit = bas + 0.3 if bit is None else float(bit)
        kelimeler.append({"w": c["text"].strip(), "bas": round(bas, 3), "son": round(bit, 3)})
        son = bit
    return {"tamam": True, "metin": out.get("text", "").strip(), "kelimeler": kelimeler, "sure": round(len(y) / 16000, 2)}


# ---------------- Çeviri (yerel dil modeli) ----------------
CEV = None
CEVIRMEN = "Qwen/Qwen3-4B-Instruct-2507"     # Apache 2.0, giriş/onay istemez


def bellek_bosalt():
    import gc
    gc.collect()
    if CIHAZ == "cuda":
        torch.cuda.empty_cache()
    elif CIHAZ == "mps":
        torch.mps.empty_cache()


def cevir(d):
    """Tek bir metni çevirir. Bellek yetsin diye çeviri sırasında seslendirme ve Whisper modelleri boşaltılır."""
    global CEV, MODEL, MODEL_AD, ASR, SON_REF
    if CEV is None:
        MODEL, MODEL_AD, ASR, SON_REF = None, None, None, ("-",)
        bellek_bosalt()
        from transformers import AutoModelForCausalLM, AutoTokenizer
        ad = d.get("model") or CEVIRMEN
        tip = torch.bfloat16 if CIHAZ == "cuda" else (torch.float16 if CIHAZ == "mps" else torch.float32)
        tok = AutoTokenizer.from_pretrained(ad)
        m = AutoModelForCausalLM.from_pretrained(ad, dtype=tip).to(CIHAZ).eval()
        CEV = (tok, m)
    tok, m = CEV
    kaynak, hedef = d["kaynak_ad"], d["hedef_ad"]
    if d.get("tur") == "ekran":
        gorev = (f"Translate this short on-screen caption from an animated educational video from {kaynak} to {hedef}. "
                 "Keep it as short as the original, keep symbols (→, %, numbers) and proper names as they are.")
    else:
        gorev = (f"Translate this voice-over line of a short animated educational video (YouTube Shorts) from {kaynak} to {hedef}. "
                 f"Make it sound natural when spoken aloud by a native {hedef} narrator, keep the meaning and tone, "
                 "and do not make it longer than the original. Write numbers as words. Keep proper names.")
    mesajlar = [{"role": "system", "content": gorev + " Reply with the translation only, no quotes, no notes."},
                {"role": "user", "content": d["metin"]}]
    girdi = tok.apply_chat_template(mesajlar, add_generation_prompt=True, return_tensors="pt", return_dict=True).to(CIHAZ)
    n = girdi["input_ids"].shape[-1]
    with torch.inference_mode():
        cikti = m.generate(**girdi, max_new_tokens=min(600, 40 + 4 * len(d["metin"])), do_sample=False)
    sonuc = tok.decode(cikti[0][n:], skip_special_tokens=True).strip()
    sonuc = re.sub(r"^(translation|tłumaczenie|çeviri)\s*:\s*", "", sonuc, flags=re.I).strip()
    if len(sonuc) > 1 and sonuc[0] == sonuc[-1] and sonuc[0] in "\"'“”«»„" and d["metin"][0] not in "\"'“«„":
        sonuc = sonuc[1:-1].strip()
    return {"tamam": True, "metin": sonuc}


def cevir_bitti():
    global CEV
    CEV = None
    bellek_bosalt()
    return {"tamam": True}


for satir in sys.stdin:
    satir = satir.strip()
    if not satir:
        continue
    try:
        istek = json.loads(satir)
        if istek.get("is") == "kapat":
            break
        if istek.get("is") == "uret":
            gonder(uret(istek))
        elif istek.get("is") == "yazi":
            gonder(yazi(istek))
        elif istek.get("is") == "cevir":
            gonder(cevir(istek))
        elif istek.get("is") == "cevir_bitti":
            gonder(cevir_bitti())
        else:
            gonder({"hata": "Bilinmeyen istek"})
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        mesaj = f"{type(e).__name__}: {e}"
        if "out of memory" in str(e).lower():
            mesaj = "Ekran kartı belleği yetmedi. Başka bir program (oyun, video üretimi) GPU kullanıyorsa kapatıp tekrar dene."
        gonder({"hata": mesaj})
