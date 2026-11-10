# Animasyon Şablonu

Videoyu bir metin dosyasında (`video.yaml`) sahne sahne tarif edersin, program her dil için ayrı videoyu kendi bilgisayarında üretir. Ücretsiz, internet gerekmez, kullanım limiti yok.

Üç sahne türü var:
- **harita**: Gerçek dünya haritası. Kamera hareketi, ülke vurgulama, şehir noktaları, çizilen rotalar, yıl sayacı ve İstanbul'a "dalarak" geçiş gibi bir yakınlaşma efekti.
- **resim**: Katmanlı resimler (gökyüzü, silüet, ön plan...). Kamera yavaşça yaklaşırken katmanlar farklı hızda kayar ve derinlik hissi verir (2.5D / parallax). Toz zerreleri, kar, vinyet.
- **kart**: Renkli arka plan üzerine başlık, alıntı veya kapanış yazısı. Daktilo efekti de var.

Her sahnede çok dilli yazılar, altyazı, seslendirme ve geçişler (siyah/beyaz solma) kullanılabilir.

---

## 1. Kurulum (Windows, tek seferlik, ~10 dakika)

1. **Python**: https://www.python.org/downloads/ adresinden indir. Kurarken **"Add python.exe to PATH"** kutusunu işaretle.
2. **ffmpeg**: Başlat menüsünde "Terminal" (veya PowerShell) aç ve şunu yaz:
   ```
   winget install Gyan.FFmpeg
   ```
   Sonra terminali kapatıp yeniden aç.
3. Bu klasörü bir yere çıkar. Gerekli Python paketlerini `BASLAT.bat` ilk açılışta kendisi kurar.

## Yenilikler: Vektör animasyon ve yeni stüdyo

- **Vektör sahneler** (`tur: vektor`) en akıcı ve keskin animasyon türüdür. Tarayıcıda SVG ile çizilir.
- Stüdyoda vektör sahneler **video üretmeden canlı oynatılır**: ▶ düğmesi, boşluk tuşu, ← → ile 1 sn ileri/geri, alttaki şeride tıklayarak sahneye atlama.
- Sağ panelden dil, format, kalite, **arka müzik ve ses seviyesi** seçilir. "Video Oluştur" yüzdeli ilerleme gösterir, istersen "Durdur" ile kesebilirsin.
- Oluşan videolar aynı panelde listelenir, ▶ ile izlenir.
- Video kaydı için bilgisayardaki **Microsoft Edge** kullanılır (Windows'ta zaten yüklü). Edge yoksa Chrome kullanılır.

## Seslendirme

Üstteki **Seslendirme** düğmesi:
1. Dili seç. Her sahnenin seslendirme metni orada. **Kopyala** ile alıp kullandığın ses platformuna yapıştır, ses dosyasını üret.
2. **Yükle** ile dosyayı ekle (mp3, wav, m4a). **Sahne sahne** yüklemek en iyi senkronu verir. İstersen **Tek dosya** ile tüm videoyu tek seferde de yükleyebilirsin.
3. Önizlemede ses görüntüyle birlikte çalar. Video Oluştur'da sese eklenir, arka müzik otomatik kısılır. Ses sahneden uzunsa o sahne otomatik uzar.
Dosyalar `projeler/<proje>/ses/<dil>/` klasörüne kaydedilir (01.mp3, 02.mp3... ya da tam.mp3).

## 2. Stüdyoyu açmak

**`BASLAT.bat` dosyasına çift tıkla.** İlk açılışta eksik paketleri kendisi kurar, sonra tarayıcıda **Animasyon Stüdyosu** açılır. Siyah pencereyi kapatma, stüdyo onunla birlikte çalışıyor.

- **Sol taraf:** videonun senaryosu. Yazıları ve sahneleri burada değiştirip **Kaydet**'e basıyorsun (Ctrl+S).
- **Önizleme:** kaydırıcıyla bir saniye seç ve bırak, o anın görüntüsü çıkar. Dil ve format (dikey/yatay/kare) de buradan seçilir.
- **Video Oluştur:** dilleri seç ve bas. Bitince video sayfada oynar, dosyası da "Videolar klasörü"ndedir. "Hızlı taslak" daha çabuk ama biraz daha düşük kalite üretir.
- **+ Yeni proje:** açık olan projeyi kopyalayıp yeni bir proje başlatır.

Program değişmeyen sahneleri tekrar çizmez. Bir yazıyı düzeltirsen sadece o sahne yeniden üretilir.

<details><summary>İstersen komut satırından da kullanabilirsin</summary>

```
python olustur.py projeler/kahve/video.yaml --dil hepsi --format yatay
```
Diğer seçenekler: `--kare 5.5` (tek kare), `--sahne 2`, `--taslak`, `--yeniden`.
</details>

**Simgeyle açmak (Windows):** klasördeki **Animasyon Stüdyosu.exe**'ye çift tıkla. Siyah komut penceresi açılmaz, stüdyo doğrudan tarayıcıda görünür; ilk çalıştırmada masaüstüne ve Başlat menüsüne kısayol koyar. Bir şey indirmesi gerekirse (ilk kurulumdaki paketler) kısa süreliğine bir pencere açılır ve kendiliğinden kapanır. Stüdyo arka planda çalışır: kapatmak için sağ üstteki **Çıkış** düğmesini kullan. Sorun olursa kayıtlar `veri/studyo.log` dosyasındadır; `BASLAT.bat` eskisi gibi çalışır.

**Arayüz dili ve kılavuz:** sağ üstteki **TR / EN** düğmesi arayüzü Türkçe ya da İngilizce yapar. Yanındaki **Kılavuz**, Claude'u bağlamaktan videoyu oluşturmaya kadar adımları iki dilde anlatır; stüdyo ilk açıldığında kendiliğinden gösterilir.

## 3. Kendi videon

1. Stüdyoda **+ Yeni proje** butonuna bas ve bir isim ver (örneğin `piri-reis`).
2. **Resimler klasörü** butonuyla klasörü aç, resimlerini oraya koy ve senaryoyu stüdyoda düzenle. `bos_sablon.yaml` dosyasında tüm seçenekler açıklamalı olarak var.
3. Önizlemeyle birkaç kareye bak, beğenince videoyu üret.

**İpuçları**
- Harita konumları **[boylam, enlem]** sırasıyla yazılır. Google Maps'te sağ tıklayınca çıkan sayıların *tersi*: İstanbul `41.01, 28.98` → `[28.98, 41.01]`.
- Konumlar 0 ile 1 arası oranlardır: `x: 0.5, y: 0.1` = ortada, üstte.
- Resim katmanları: arka katman normal resim olabilir. Üstteki katmanlar **arka planı şeffaf PNG** olmalı ki alttaki görünsün. Canva, Photopea (ücretsiz, tarayıcıda) veya yapay zeka resim araçlarından gelebilir.
- `derinlik`: 0 = uzakta (az hareket eder), 1 = önde (çok hareket eder).
- yaml'da girintiler (boşluklar) önemli. Tab değil boşluk kullan. Bir hata çıkarsa önce girintilere bak.

## 4. Seslendirme ve diller

Her sahneye dil başına bir ses dosyası verebilirsin:
```yaml
ses: {tr: ses/tr/01.wav, en: ses/en/01.wav}
```
Ses sahneden uzunsa sahne kendiliğinden uzar. Arka müzik için:
```yaml
muzik: {dosya: muzik/arka.mp3, ses: 0.15}
```
(Telifsiz müzik için YouTube Studio → Ses Kitaplığı.)

**Hangi platformda nasıl kullanılır?**
- **Shorts / Reels / TikTok:** Her dil için ayrı video üret (`--dil hepsi`). Ekrandaki yazılar da o dilde olur.
- **YouTube uzun video:** Tek video yükleyip diğer dilleri **ek ses kanalı** olarak ekleyebilirsin. Program seslendirmeli her dil için `..._sadece_ses.m4a` dosyası da çıkarır. Bunu YouTube Studio'da videonun "Altyazılar → Ses" bölümüne yüklersin. Bu durumda ekran yazıları tek dilde kalır, o yüzden uzun videolarda ekran yazısını az tut (sayılar, yer adları).

## 5. Chatterbox: bilgisayarında yapay zeka seslendirme

**Seslendirme** penceresinin üstünde **Chatterbox** çubuğu var.

**İlk kurulum (tek seferlik):** **⬇ Chatterbox'u kur** düğmesine bas. Yaklaşık 10 GB yer kaplar, internet hızına göre 15-30 dakika sürer. Stüdyonun kendi Python'una dokunmaz; Chatterbox `tts/env` klasöründe kendi ayrı Python 3.11 ortamına kurulur. İlk ses üretiminde model dosyaları (~3 GB) bir kez iner (`tts/model`).

**Ses üretmek:**
- **Eksikleri üret**: sesi olmayan sahnelerin hepsini seslendirir.
- Her sahnedeki **Chatterbox ile üret / Yeniden üret**: sadece o sahne.
- **Hepsini yeniden**: o dildeki tüm sahne seslerini baştan üretir.
- Sesler `ses/<dil>/01.wav, 02.wav...` olarak kaydedilir, önizlemede ve videoda otomatik kullanılır. Beğenmezsen yeniden üret, her seferinde biraz farklı çıkar.
- Desteklenen diller: tr, en, pl, pt, es ve 18 dil daha.

**Sesler (ses seçimi ve Ses ayarları → Ses kütüphanesi):**
- Chatterbox'un tek bir hazır sesi var. Farklı sesler **ses örneğiyle (klonlama)** yapılır: 10-20 sn'lik bir kayıttan o sesin cinsiyetini, kalınlığını ve tarzını taklit eder.
- **Hazır şablonları oluştur**: hazır sesten **kalın**, **çok kalın** ve **ince** şablon sesler türetir. Dinle, beğendiklerine ✏ ile istediğin adı ver (örn. "Kadın anlatıcı", "Kalın erkek").
- **Mikrofonla kaydet**: stüdyonun içinde kendi sesini kaydedersin. Dil seç, ekrandaki kısa metni (TR, EN, PL, PT, ES) video anlatır gibi oku, durdur, dinle, isim verip kütüphaneye ekle. Ses seviyesi göstergesi çok sessiz ya da çok yüksek konuşursan uyarır. İlk seferde tarayıcı mikrofon izni ister.
- **⬆ Dosyadan ekle**: başka yerde kaydettiğin bir dosyayı (mp3, wav, m4a...) isimle kütüphaneye ekler. Kayıt seslendirilecek dilde olursa en iyi sonuç çıkar.
- ****: herhangi bir sesin daha kalın (0.8-0.9) ya da daha ince (1.1-1.2) kopyasını oluşturur.
- **TR/EN/PL sesi** listesi: bu projede o dil için hangi sesin kullanılacağını seçer. **★ Varsayılan yap** yeni projelerde de o sesi kullanır. Seçim sadece bundan sonra üretilen seslendirmeleri etkiler.
- Ayarlar: **Duygu / canlılık**, **Örneğe bağlılık / tempo** (kayıt başka dildeyse 0.3 dene), **Çeşitlilik** ve **Model** (en yenisi önerilir).

**Güncelleme (tek tık):**
- Stüdyo açılınca Chatterbox'un yeni sürümü olup olmadığına kendisi bakar. Varsa Seslendirme düğmesinde **güncelleme** etiketi çıkar.
- **Neler değişti?** son kurduğundan beri yapılan değişiklikleri listeler. **Güncelle** düğmesi yeni sürümü ayrı bir klasöre kurar, ekran kartıyla test eder, sorun yoksa eskisiyle yer değiştirir. Kurulum yarıda kalırsa ya da hata verirse eski sürümün çalışmaya devam eder.
- **↩ Önceki sürüm** son güncellemeyi geri alır. Tekrar basarsan yeni sürüme döner.
- **Güncellemeye bak** ile istediğin an kontrol edebilirsin.

Model 10 dakika kullanılmazsa ekran kartı belleğinden otomatik çıkarılır. Chatterbox her sese duyulmayan bir filigran (watermark) ekler.

## 6. Mac'te kullanım

Stüdyo Mac'te de çalışır. Mac ile Windows birbirinden bağımsızdır: her bilgisayarda kendi stüdyo klasörün ve projelerin olur.

1. `animasyon_mac.zip` dosyasını Mac'te istediğin yere çıkar (örneğin Belgeler).
2. **`BASLAT.command`** dosyasına **sağ tıkla → Aç** (ilk seferde macOS "tanımlanamayan geliştirici" uyarısı verir, "Aç" de). Sonraki seferlerde çift tıklaman yeterli.
3. İlk açılışta gerekenleri kendisi kurar: Python ortamı (`.mac_ortam`), paketler, Chrome yoksa Chromium. ffmpeg yoksa Homebrew ile kurmayı teklif eder (Mac şifreni ister).
4. Chatterbox'u Mac'te ayrıca kurman gerekir (Seslendirme → ⬇ Chatterbox'u kur, ~1 GB + model ~3 GB). Apple çipli (M1-M4) Mac'lerde Apple GPU ile çalışır, Windows'taki RTX 4080'den daha yavaştır. Intel Mac'lerde Chatterbox çalışmaz, stüdyonun geri kalanı çalışır.

Ses kütüphanesi (`tts/sesler`) zip'in içinde gelir. Mac'te kaydettiğin sesleri Windows'a taşımak istersen `tts/sesler` klasörünü kopyalaman yeterli.


## 7. Storyboard, sahne geçişleri ve el yapımı his

- **Storyboard** (üst menü): video çizmeden her sahnenin ortasından ve geçiş anından birer kare çıkarır, numaralı kartlarda seslendirme metni ve storyboard notlarıyla gösterir. "3'ten 4'e geçiş olmadı" gibi notları numarayla vermek kolaylaşır. Tek sayfalık hali: `cikti/storyboard/storyboard.jpg`.
- **Dönüşümlü geçişler:** sahneler siyaha kararmak yerine birbirine dönüşür: bir nesne (kalp, daire, kart) büyüyüp ekranı kaplar ve bir sonraki sahnenin rengine döner.
- **Yazılar** kelime kelime bulanıktan netleşerek gelir. **Kamera** tek yönde, başta hızlı sonra yavaş yaklaşır.
- **El yapımı his ve kukla:** saniyede 12 poz, çizgi titremesi, çıkartma gölgesi; saydam PNG bir karakteri pinlerle oynatma (el sallama, baş eğme, nefes). Pin koordinatları için: `python araclar/izgara.py resim.png izgara.png`.
- Claude bu kuralları `CLAUDE.md` dosyasından okur ve her yeni videoda önce storyboard hazırlayıp onayını bekler.

## 8. Whisper: seslendirme kontrolü ve altyazı

- Chatterbox her sahneyi ürettikten sonra **Whisper** (bilgisayarında çalışan konuşma tanıma) sesi dinler ve senaryoyla karşılaştırır. Sahne kartında **✓ Whisper %100** ya da **⚠ %78 · eksik: …** görünür (üstüne gelince Whisper'ın ne duyduğunu gösterir).
- Bir kelime atlanmışsa sahne **bir kez otomatik yeniden üretilir**, iyi olan tutulur. İkisi de Ses ayarları'ndan kapatılabilir.
- Kendi yüklediğin sesler için **Whisper kontrolü** düğmesi (Shift+tık: hepsini yeniden kontrol eder).
- Whisper ayrı kurulum istemez, Chatterbox'ın ortamını kullanır. İlk kullanımda model (~1,6 GB) bir kez iner.
- **Altyazı:** Video Oluştur'daki **"Altyazıyı videoya göm"** ile konuşulan kelimenin sarı yandığı Shorts tarzı altyazı eklenir. YouTube'a ayrıca yüklemek için `cikti/<proje>_<dil>.srt` her zaman yazılır. Konum/boyut: `video.yaml`'da `altyazi: {konum: 0.72, boyut: 96, vurgu: "#ffd166"}`.
- **Sahneye sığdırma:** Ses sahneden uzunsa her sahne kartındaki **Sığdır** seçimi devreye girer: *Otomatik* sesi en fazla %20 hızlandırır, yetmezse sahneyi biraz uzatır; *Hızlandır* %40'a kadar hızlandırır (sahne süresi değişmez); *Sahneyi uzat* sese dokunmaz. Ses dosyası değişmez, hız önizlemede ve videoda uygulanır, ton bozulmaz. Önizleme artık videodaki sürelerle oynar, sesin bir sonraki sahnede yarıda kesilmesi bitti.
- **▶ Dinle** düğmesi çalarken **■ Durdur** olur; başka bir sesi açınca ya da pencereyi kapatınca çalan durur.

## 9. Çeviri (bilgisayarında, internetsiz)

- Seslendirme penceresinde **Çevir** → kaynak dili seç (ör. TR), hedef dilleri işaretle; yeni bir dil için **+ dil ekle** (PT, ES, DE…). **Çevirmeye başla**.
- Seslendirme metinleri **ve** sahnelerdeki ekran yazıları çevrilir. Model ilk seferde bir kez iner (~8 GB, Qwen3-4B, Apache 2.0 lisanslı, üyelik/giriş istemez), sonra internetsiz çalışır. Chatterbox'ın ortamını kullanır; ayrı kurulum yok.
- Çevrilen sahnelerde metin kutusu düzenlenebilir: düzeltip kutudan çıkınca kaydedilir. Sonra o dilde **Eksikleri üret** → Whisper kontrol eder → **Sığdır** süreyi ayarlar.
- Çeviriler senaryoyu değiştirmez, projedeki `ceviri.json`'a yazılır. Senaryoda bir dil zaten yazılıysa o kullanılır. Kaynak metni sonradan değiştirirsen **Önceki çevirileri yenile** ile yeniden çevir (elle düzelttiklerin de yenilenir).
- Çeviri modeli Ses ayarları dosyasında (`tts/ayarlar.json` → `ceviri_model`) değiştirilebilir.

## 10. Hız ve kolaylıklar

- **Daha hızlı video:** sahneler parçalara bölünüp bütün işlemci çekirdeklerinde aynı anda çizilir. **Hızlı taslak** yarı çözünürlükte yakalar (deneme için), **Yüksek** tam kalitedir.
- **Önce eksik sesleri üret** (Video Oluştur'un üstünde): sesi olmayan ya da metni değişmiş sahneler Chatterbox ile seslendirilir, sonra video çizilir. Tek tıkla metinden videoya.
- **Metni yerinde düzelt:** Seslendirme penceresinde her sahnenin metni yazılabilir bir kutudur; kutudan çıkınca kaydedilir. Kelime sayacı sahneye sığıp sığmadığını gösterir. Metni değişen sahnede **✎ Metin değişti, ses eski** yazar; **Eksikleri üret** onu da yeniler.
- **Ses karışımı:** konuşma sırasında müzik kendiliğinden kısılır, cümle aralarında ve sonda yükselir; videonun ses düzeyi YouTube/Instagram ölçüsüne (-14 LUFS) ayarlanır. Müzik kaydırıcısı konuşma olmayan yerlerdeki düzeydir.
- **Kare:** önizlemedeki anı resim olarak `cikti` klasörüne kaydeder (kapak resmi için).
- **Kısayollar:** Boşluk oynat/durdur · ←/→ 1 sn (Shift ile 0,1 sn) · ↑/↓ önceki/sonraki sahne · Home başa · Esc pencereyi kapat.

---
Fontlar: DejaVu (serbest lisans, `fontlar/LICENSE-DejaVu.txt`). Harita verisi: Natural Earth (kamu malı).
