> This file is written in Turkish and is meant for Claude. Reply to the user in their own language, and write narration and on-screen text in the language they ask for (put that language first in `diller`).

# Animasyon Stüdyosu: Claude için çalışma rehberi

Bu klasör, kullanıcının bilgisayarında çalışan bir animasyon video stüdyosudur. Kullanıcı bu klasörü sana bağladıysa senden genellikle şunu ister: **"Şu konuda bir video hazırla."** Senin işin videonun dosyalarını hazırlayıp bu klasöre yazmaktır. Videoyu kullanıcı kendi bilgisayarındaki stüdyoda üretir.

## Çalışma kuralları
- Videoyu kendin render etme. Dosyaları yaz, kullanıcı stüdyoda (tarayıcıda açılan "Animasyon Stüdyosu") önizleyip **Video Oluştur**'a basar.
- Yeni video = `projeler/<kisa-ad>/` altında yeni bir klasör (küçük harf, Türkçe karakter ve boşluk yok, örn. `bal-neden-bozulmaz`).
- Sağlık, bilim ve istatistik bilgilerini güvenilir kaynaklardan doğrula, kaynakları son sahnede küçük yazıyla göster. Sağlık videolarının sonuna "bilgilendirme amaçlıdır, doktoruna danış" notu ekle.
- Karakterler ve çizimler özgün olmalı. Bilinen çizgi film karakterlerini, logoları ya da markaları taklit etme.
- Sahne iskeleti için aşağıdaki "Vektör sahne yazma" bölümüne bak; stüdyodaki **Yeni proje** tek sahnelik bir başlangıç (`sahneler/01_baslangic.html`) oluşturur, mevcut projeler varsa önce onların `video.yaml` ve `sahneler/*.html` dosyalarını oku.

## Akış: önce storyboard, sonra sahneler
1. **Konu ve sonuç.** Konu, dil(ler), süre ve videonun sonunda izleyicinin ne yapması gerektiği (takip et, yorum yaz, siteye git). Son sahne bundan geriye doğru tasarlanır.
2. **Numaralı storyboard, sonra BEKLE.** 4-8 numaralı sahne: her biri için süre, ekranda ne var, ne hareket ediyor, seslendirme cümlesi ve **bir sonraki sahneye nasıl dönüşüyor**. Bunu `video.yaml`'a (`storyboard:` alanlarıyla, sahne dosyaları henüz olmadan) yaz ve kullanıcıya numaralı liste olarak göster. Onay ya da not ("3'ten 4'e geçiş olmadı") gelmeden sahne kodu yazma: en ucuz değişiklik burada yapılır.
3. **Sahneleri yaz.** Onaydan sonra `sahneler/NN_ad.html` dosyalarını yaz. Her zamanlama değerini sahnenin başında tek yerde tut, yeniden zamanlama tek satır olsun.
4. **Kareleri kontrol et.** Kullanıcıdan stüdyoda **Storyboard → Kareleri yeniden çıkar** demesini iste. Bu, video çizmeden her sahnenin ortasından ve geçiş anından birer kare çıkarır ve `cikti/storyboard/storyboard.jpg` tek sayfasını yazar. Dosyaya erişimin varsa o sayfayı kendin aç ve bir hareket tasarımcısı gibi bak: yanlış şekil, sol/sağ hatası, üst üste binen parçalar, okunmayan yazı, ortadan kaymış ana öğe. Motorun uyarıları (⚠) da orada görünür. Sorunları düzeltmeden kullanıcıya "hazır" deme.
5. **Not turları.** Her turda notların hepsini uygula, neyi değiştirdiğini sade cümlelerle söyle.

## Görünümü iyi yapan kurallar
- **Her sahne bir sonrakine dönüşür.** Siyaha kararıp açılmak yerine `cikis: "devir"` kullan: bu sahnedeki bir nesne (kalp, daire, kart, logo) önce %8 sıkışır, sonra büyüyüp ekranı kaplar ve bir sonraki sahnenin arka plan rengine dönüşür. Sonraki sahne `giris: "devir"` ile aynı renkten %93→%100 açılır. Göz hep aynı yerde kalır. Storyboard'da her geçiş için "hangi şekil hangi şekle dönüşüyor" sorusunu yanıtla. Siyah kararma sadece videonun başı ve sonu için.
- **Önemli olan tam ortada.** Ana nesne görünmez bir artı işaretinin merkezinde dursun, göz aramak zorunda kalmasın. Son kart tamamen ortalı ve sabit olsun.
- **Her an bir şey hareket eder.** Büyük olması gerekmez: `V.itme` ile yavaş kamera yaklaşması, `bekle: "nefes suz"` gibi küçük canlılıklar. Donmuş kare bayat görünür.
- **Yön birden değişmez.** Yaklaşıp sonra uzaklaşma, büyüyüp sonra küçülme, dönüp geri dönme yok. Kamera için tek sürekli eğri: `V.itme(t, {yakin: 1.06})` (başta hızlı, sonra uzun süre yavaş). `V.kameraAyarla` kullanıyorsan yönü tersine çevirme; motor ters dönüşü storyboard'da uyarı olarak gösterir.
- **Hızlı başla, uzun süre yavaş devam et.** İlk taslaklar hep fazla hızlıdır; tutuşlara zaman ver.
- **Şekiller şeklini korur.** Dönüşümde eğriler ters dönmez, birlikte hareket eden parçalar aynı hızda ve eşit aralıkta gider.
- **Yazı:** kısa satırlar, cümle düzeni. Başlıklar `anim(t, t0, "bulanik", bit)` ile kelime kelime bulanıktan netleşerek ve hafifçe yükselerek gelir, aynı şekilde gider. Zıplama ve büyüme yok. Koyu arka planda başlıklara `degrade: true` (harflerin alt yarısı hafifçe koyulaşır). Yazıyı hareket edecek şeylerin üstüne ve kaybolacağı renklere koyma.
- **Kutlama anlarında küçük detaylar:** konfeti, parıltı (`url(#parilti)`), tik işareti. Her yere parıltı koyma, eski moda gölge ve lens parlaması kullanma.
- **Sonunda net bir çağrı:** "Takip et", "Yorumlara yaz", kaynak satırı.

## Diller ve çeviri
- Kullanıcı stüdyonun Claude'a bağlı olmadan çalışmasını istiyor. Yeni videoda seslendirme ve ekran yazılarını **sadece kaynak dilde** (kullanıcının istediği dil; `diller` listesinde ilk sırada) yaz; kullanıcı istemedikçe diğer dilleri yazma. Kullanıcı stüdyoda Çevir ile bilgisayarında çevirir (Qwen3-4B, Chatterbox ortamında).
- Ekran yazılarını yine dil nesnesi olarak yaz: `metin: { tr: "..." }`. Çeviri bu nesneleri bulur; düz dize (`metin: "..."`) çevrilmez.
- Çeviriler projenin `ceviri.json` dosyasındadır (`diller.<dil>.anlatim.<sahne no>`, `diller.<dil>.ekran.<kaynak yazı>`). Senaryoda yazılı olan dil her zaman önceliklidir. Bu dosyaya dokunma; kaynak metni değiştirirsen kullanıcıya "Çevir → Önceki çevirileri yenile" yapmasını söyle.

## Seslendirme ve Whisper
- Seslendirme metnini sahne süresine sığdır: yaklaşık **sure × 2,0 kelime** (ses sahneden uzunsa sahne uzar).
- Stüdyo Chatterbox ile ürettikten sonra Whisper ile dinler: `ses/<dil>/NN.kelimeler.json` içinde `benzerlik` (0-1), `eksik` (okunmayan kelimeler), `fazla`, `duyulan` ve kelime zamanları var. Sesleri dinlemek yerine bu dosyaları oku: `benzerlik < 0.95` ise metni sadeleştir (uzun yabancı adlar, kısaltmalar, rakamlar sorun çıkarır; rakamları yazıyla yaz: "yüzde altı").
- Ses sahneden uzunsa stüdyo önce sesi en fazla %20 hızlandırır, yetmezse sahneyi uzatır (sahne başına mod `ses/<dil>/sigdir.json`: otomatik | hizlandir (≤%40) | uzat). Yine de metni sahneye sığacak uzunlukta yaz; %20 hızlanma bir güvenlik payıdır.
- Videoda müzik konuşma sırasında kendiliğinden kısılır ve toplam ses -14 LUFS'a getirilir; `muzik.ses` konuşma olmayan yerlerdeki düzeydir (0.5-0.8 iyi).
- Kullanıcı seslendirme metnini stüdyoda düzeltebilir (video.yaml'daki satır yerinde değişir). Senaryoya dokunmadan önce dosyayı yeniden oku.
- Altyazı bu kelime zamanlarından otomatik çıkar (`cikti/<ad>_<dil>.srt`, istenirse videoya gömülü). Altyazı alt-orta bölgede durur (`altyazi: {konum: 0.72}`); önemli görselleri o bandın üstüne ya da altına yerleştir.

## El yapımı his ve kukla (isteğe bağlı)
- `V.sahne({..., poz: 12, titreme: 1.5, cikartma: true})`: saniyede 12 poz (8 daha "kaba"), her pozda hafif çizgi titremesi, düz ve sert "çıkartma" gölgesi. Böyle sahneleri olan projede `fps: 24` kullan (her poz tam 2 kare). Pürüzsüz Kurzgesagt tarzında bunları kullanma; daha el çizimi, çizgi film tarzı videolar için.
- **Karakterler eklemli parçalardan oluşsun.** `V.kisi` karakterinin kolları omuz ve dirsekten dönen sert parçalardır: her karede `kisi.kol("sag", omuzAcisi, dirsekAcisi)` (0 = aşağı sarkık, 90 = yana, 170 = yukarı) ve `kisi.basEg(aci)`. El sallama, işaret etme, omuz silkme bununla yapılır; hiçbir şey esnemez. Kendi çizdiğin karakterlerde de kolu, başı, kuyruğu ayrı `V.g` grupları yap ve eklem noktasının etrafında döndür.
- **Kukla (`V.kukla`, PNG'yi pinlerle bükme) sadece çok küçük hareketler için:** nefes, saçın hafif dalgalanması, başın birkaç derece eğilmesi. Kol kaldırma, el sallama gibi hareketlerde lastik gibi esner ve kötü görünür; öyle hareketler için parçaları ayrı katman olarak çiz. Pin koordinatları için `python araclar/izgara.py resim.png izgara.png`; ayaklara, omuzlara, kalçaya sabit (boş hareketli) pinler koy.

## Proje yapısı
```
projeler/<ad>/
  video.yaml          senaryo: diller, format, müzik, sahne listesi, seslendirme metinleri
  sahneler/NN_ad.html vektör sahneler (tarayıcıda SVG ile çizilir)
  sahneler/_ahtapot.js örnek: birden çok sahnede kullanılan ortak çizim fonksiyonları
  ses/<dil>/01.wav... seslendirme (stüdyo üretir ya da kullanıcı yükler)
  cikti/              üretilen videolar
```

## video.yaml
```yaml
ad: proje-adi
diller: [tr, en, pl]          # her dil için ayrı video üretilir
format: dikey                 # vektör sahneler dikey (1080x1920) tasarlanır
fps: 30
muzik: {dosya: ortam_muzik.mp3, ses: 0.6}
sahneler:
  - tur: vektor
    baslik: Kanca
    dosya: sahneler/01_kanca.html
    sure: 5                   # saniye
    anlatim: {tr: "...", en: "...", pl: "..."}   # seslendirme metni: en fazla ~ sure x 2.0 kelime
    storyboard:               # stüdyodaki Storyboard penceresinde görünür
      ekranda: "Ortada büyük sarı 3, altında ahtapot"
      hareket: "3 sayarak gelir, ahtapot süzülür, kamera yavaşça yaklaşır"
      gecis: "3 sıkışır, büyüyüp ekranı kaplar ve sahne 2'nin lacivertine dönüşür"
    efektler:                 # hazır sesler: pop, vin, parilti, bum, tik, lazer
      - {t: 0.3, ses: vin, seviye: 0.4}
```
Diğer sahne türleri (`kart`, `harita`, `resim`, `cizgi`) ve tüm seçenekler `bos_sablon.yaml` dosyasında açıklamalı olarak var. En iyi sonuç `vektor` ile alınır.

## Vektör sahne yazma (motor/vektor/vektor.js)
Her sahne ayrı bir HTML dosyasıdır:
```html
<!doctype html><html><head><meta charset="utf-8"><title>01_kanca</title>
<link rel="stylesheet" href="../../../motor/vektor/vektor.css"></head><body>
<script src="../../../motor/vektor/vektor.js"></script>
<script>
let baslik, kisi;
V.sahne({
  sure: 5, arka: ["#06213a", "#0b3d5c"], giris: "siyah",     // giris/cikis: devir | siyah | beyaz | yok
  cikis: "devir", devir: { oge: () => kisi.g, sure: 1.1 },  // sonraki sahnenin rengi otomatik bulunur
  kur(s) {        // öğeleri bir kez oluştur. s.kamera: kameralı katman, s.ust: yazılar (kamerasız)
    kisi = V.kisi(s.kamera, { gomlek: "#3ec7c0", ifade: "mutlu" });
    baslik = V.yazi(s.ust, { metin: { tr: "Merhaba", en: "Hello", pl: "Cześć" }, x: 540, y: 260, boyut: 80 });
  },
  ciz(t, s) {     // her karede t (saniye) ile çağrılır
    V.itme(t, { yakin: 1.06, hedefY: 0.52 });            // tek, sürekli kamera itmesi
    V.yer(kisi.g, t, { x: 540, y: 1600, bas: 0.3, giris: "yukari", bekle: "nefes" }); kisi.guncelle(t);
    baslik.anim(t, 0.2, "bulanik", 3.6);                  // 3.6 sn'de bulanıklaşarak gider
  },
});
</script></body></html>
```
- Tasarım alanı **1080 x 1920** (dikey). Yazıları üstte (y 200-800), karakterleri altta tut.
- `V.yer(el, t, {x, y, s, r, bas, giris: "zipla|solma|yukari|asagi|sol|sag|buyu", gs, bit, cikis: "kucul|solma|yukari|asagi|sol|sag", cs, bekle: "nefes salla zipla suz nabiz don titre", faz})`
- `V.yazi(ebeveyn, {metin:{tr,en,pl}, x, y, boyut, renk, genislik, agirlik, golge, degrade})` → `.anim(t, t0, "bulanik|kelime|yukari|solma|yazma|zipla", bit)` (başlıklar için `bulanik`)
- Geçiş: `cikis: "devir"` + `devir: {oge: () => el, renk, sekil: "oge|daire|kare", sure}`. `oge` verilirse nesnenin kendisi büyür (yazıda otomatik daire). Sonraki sahnede `giris: "devir"`. Sonraki sahnenin rengi `arka: ["#..."]` ilk renginden otomatik okunur, o yüzden `arka` her sahnede dizi olarak yazılsın.
- Kamera: `V.itme(t, {yakin, uzak, mx, my, hedefX, hedefY, hiz})`, ya da tek yönlü anahtar karelerle `V.kameraAyarla`.
- `V.etiket(ebeveyn, {metin, boyut, renk, arka, arkaOp})` hap şeklinde etiket, `V.buyukSayi(ebeveyn, {boyut, renk})` → `{g, yaz(metin)}`
- `V.kisi(ebeveyn, {gomlek, ten, sac, sacTip: "kisa|uzun|topuz|kel", ifade: "mutlu|uzgun|notr|saskin", telefon, kollar: "yan|yukari|kavus"})` → `{g, guncelle(t)}` (ayak tabanı orijin, ~670 px boy)
- `V.bina`, `V.saat`, `V.cubuk`, `V.yildizlar(ebeveyn, n)` / `V.zerreler(ebeveyn, n, renk)` → `.guncelle(t)`
- **Hazır ikonlar** (elle çizmeden önce bunlara bak): `V.ikon(ebeveyn, "kalp", {boyut: 160, renk, ikinci})` → `{g}` (origin merkezde, `V.yer` ile konumlanır). Adlar: kalp, yildiz, ev, insan, para, saat, telefon, dunya, ampul, simsek, damla, yaprak, ok, tik, carpi, soru, unlem, konusma, goz, kilit, takvim, grafik, ates, ay, gunes, bulut, kitap, muzik, hedef, kalkan, yatak, kahve (`V.ikonlar`).
- `V.halka(ebeveyn, {r, kalinlik, renk})` → `{g, ayarla(0..1)}` yüzde halkası; `V.cizgiGrafik(ebeveyn, {degerler: [..], genislik, yukseklik, renk})` → `{g, ayarla(0..1), nokta(i)}` soldan sağa çizilen çizgi grafik (origin sol alt).
- **`ciz(t)` zamanın saf fonksiyonu olmalı** (önceki kareye bağlı durum tutma): video, sahneler parçalara bölünerek paralel çizilir. `Math.random` sabit tohumludur, her açılışta aynı sonucu verir. Durum tutmak zorundaysan video.yaml'a `parcali: false` yaz.
- Çizim: `V.el(etiket, ozellikler, ebeveyn)`, `V.g(ebeveyn)`, `V.gradyan(renkler, {radyal})`, `V.cizgi(path, p)` kendini çizen çizgi, `V.op(el, opaklik)`
- Zaman: `V.p(t, t0, sure, "iki|giris|cikis")` (0→1 ilerleme), `V.ara(a, b, p)`, `V.kf(t, kareler)`. Filtreler: `url(#parilti)`, `url(#golge)`
- Tarz: koyu arka plan, parlak renkler, sevimli yuvarlak şekiller, sürekli hafif hareket (`bekle`), yavaş kamera yaklaşması.

## Kontrol
Dosyaları yazdıktan sonra kullanıcıya stüdyoda projeyi seçip ▶ ile önizlemesini söyle. Hata olursa stüdyodaki "Kayıtlar" bölümündeki metni iste.
