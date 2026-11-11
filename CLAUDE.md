> This file is written in Turkish and is meant for Claude. Reply to the user in their own language, and write narration and on-screen text in the language they ask for (put that language first in `diller`).

# Animasyon Stüdyosu: Claude için çalışma rehberi

Bu klasör, kullanıcının bilgisayarında çalışan bir animasyon video stüdyosudur. Kullanıcı bu klasörü sana bağladıysa senden genellikle şunu ister: **"Şu konuda bir video hazırla."** Senin işin videonun dosyalarını hazırlayıp bu klasöre yazmaktır. Videoyu kullanıcı kendi bilgisayarındaki stüdyoda üretir.

## Çalışma kuralları
- Videoyu kendin render etme. Dosyaları yaz, kullanıcı stüdyoda (tarayıcıda açılan "Animasyon Stüdyosu") önizleyip **Video Oluştur**'a basar.
- Yeni video = `projects/<kisa-ad>/` altında yeni bir klasör (küçük harf, Türkçe karakter ve boşluk yok, örn. `bal-neden-bozulmaz`).
- Sağlık, bilim ve istatistik bilgilerini güvenilir kaynaklardan doğrula, kaynakları son sahnede küçük yazıyla göster. Sağlık videolarının sonuna "bilgilendirme amaçlıdır, doktoruna danış" notu ekle.
- Karakterler ve çizimler özgün olmalı. Bilinen çizgi film karakterlerini, logoları ya da markaları taklit etme.
- **Tarz:** `video.yaml`'daki `stil:` alanı projenin tarzıdır: `vektor` (2D, varsayılan), `uc` (3D) ya da `piksel` (piksel art). Kullanıcı stüdyoda yeni proje açarken seçer. Yeni sahneleri bu tarzda yaz (`tur:` aynı değer); kullanıcı istemedikçe tarzları karıştırma. Proje yoksa ve kullanıcı tarz söylemediyse sor ya da konuya uygun olanı öner.
- Sahne iskeleti için aşağıdaki "Vektör sahne yazma", "3D sahne yazma" ve "Piksel sahne yazma" bölümlerine bak; stüdyodaki **Yeni proje** tek sahnelik bir başlangıç (`sahneler/01_baslangic.html`) oluşturur, mevcut projeler varsa önce onların `video.yaml` ve `sahneler/*.html` dosyalarını oku.

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
- **Kukla (`V.kukla`, PNG'yi pinlerle bükme) sadece çok küçük hareketler için:** nefes, saçın hafif dalgalanması, başın birkaç derece eğilmesi. Kol kaldırma, el sallama gibi hareketlerde lastik gibi esner ve kötü görünür; öyle hareketler için parçaları ayrı katman olarak çiz. Pin koordinatları için `python tools/grid.py resim.png izgara.png`; ayaklara, omuzlara, kalçaya sabit (boş hareketli) pinler koy.

## Proje yapısı
```
projects/<ad>/
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
muzik: {dosya: ambient_music.mp3, ses: 0.6}
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
    efektler:                 # hazır sesler: pop, whoosh, sparkle, boom, tick, laser
      - {t: 0.3, ses: whoosh, seviye: 0.4}
```
3D (`uc`) ve piksel (`piksel`) sahneler aynı alanlarla yazılır. Diğer sahne türleri (`kart`, `harita`, `resim`, `cizgi`) ve tüm seçenekler `template.yaml` dosyasında açıklamalı olarak var. En iyi sonuç `vektor` ile alınır.

## Vektör sahne yazma (engine/vector/vector.js)
Her sahne ayrı bir HTML dosyasıdır:
```html
<!doctype html><html><head><meta charset="utf-8"><title>01_kanca</title>
<link rel="stylesheet" href="../../../engine/vector/vector.css"></head><body>
<script src="../../../engine/vector/vector.js"></script>
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

## 3D sahne yazma (engine/3d/3d.js, Three.js)
`tur: uc`. Her sahne bir HTML dosyası, betik **modül** olarak yazılır:
```html
<!doctype html><html><head><meta charset="utf-8"><title>01_ada</title>
<link rel="stylesheet" href="../../../engine/vector/vector.css">
<script type="importmap">{"imports":{"three":"../../../engine/3d/three.module.min.js","three/addons/":"../../../engine/3d/addons/"}}</script></head><body>
<script type="module">
import { U, THREE } from "../../../engine/3d/3d.js";
let ada, baslik;
U.sahne({
  sure: 5, arka: ["#6fb4ff", "#cfe6ff"], isik: "gun", sis: 0.008, gorus: 30,   // isik: gun | gece | studyo
  giris: "siyah", cikis: "devir", devir: { renk: "#ffd166", x: 0.5, y: 0.5, sure: 1 },  // x, y: ekran oranı
  kur(s) {        // s.sahne (THREE.Scene), s.kamera, s.ust (yazılar için 2D katman, 1080x1920)
    s.sahne.add(U.zemin("#3d9bd6"));
    ada = new THREE.Group(); s.sahne.add(ada);
    ada.add(U.silindir(2.6, 0.5, "#f1d9a0", { ust: 2.4 }));
    const ev = U.ev({ cati: "#e8695d" }); ev.position.set(0, 0.25, 0); ada.add(ev);
    baslik = U.yazi(s.ust, { metin: { tr: "Küçük bir ada" }, y: 260, boyut: 92 });
  },
  ciz(t, s) {
    U.itme(t, { bas: [0, 6, 15], son: [2, 4, 11], hedef: [0, 0.8, 0] });   // tek, sürekli kamera hareketi
    ada.rotation.y = t * 0.1;
    baslik.anim(t, 0.3, "bulanik", 4.2);
  },
});
</script></body></html>
```
- Birim ≈ metre; zemin y = 0. Kamera `U.itme(t, {bas, son, hedef})` ya da `U.yorunge(t, {merkez, yaricap, yukseklik, hiz})`.
- Hazır şekiller (yumuşak "kil" görünümü, gölgeli): `U.kure(r, renk)`, `U.kutu(g, y, d, renk, {yuvarlak})`, `U.silindir(r, y, renk, {ust})`, `U.koni(r, y, renk, {detay})`, `U.halka(r, kalinlik, renk)`, `U.zemin(renk)`, `U.agac({tur: "yuvarlak|cam", boy})`, `U.ev({duvar, cati})`, `U.bulut({boy})`, `U.yildizlar(n)`. Malzeme: `U.malzeme(renk, {parlak, metal, duz, yayilim, saydam})`.
- `U.yer(nesne, t, {x, y, z, s, bas, giris: "buyu|yukari|dus", bit, cikis, bekle: "suz don nabiz salla"})` nesneyi yerleştirip canlandırır.
- Hazır model: `const m = U.model("modeller/kopek.glb", {boy: 1}); s.sahne.add(m.g); ... m.anim(t, "Walk")`. Dosyayı projenin `sahneler/modeller/` klasörüne kullanıcı koyar (ücretsiz CC0 kaynaklar: Kenney, Quaternius, Poly Pizza). İnternetten kendin indiremiyorsan kullanıcıdan iste; yoksa hazır şekillerle kur.
- Yazılar 2D katmanda: `U.yazi(s.ust, {metin, x, y, boyut, renk})` → `.anim(t, t0, "bulanik", bit)`.
- `ciz(t)` saf fonksiyon olmalı (nesnelerin konumunu, dönüşünü t'den hesapla).
- 3D çizim vektörden yavaştır (ekran kartıyla kare başına ~0,1-0,5 sn). Sahne başına 2-5 ana nesne ve tek ışık düzeni yeter; yüzlerce ayrıntılı nesne koyma.

## Piksel sahne yazma (engine/pixel/pixel.js)
`tur: piksel`, projede `fps: 24`. Sahne 180 x 320 piksellik bir tuvale çizilir ve 6 kat büyütülür (her piksel net kare). Bulanıklık ve yarı saydamlık yoktur; solmalar damalı (dither) desenle olur. Her karede tuval temizlenir ve `ciz(t, c)` her şeyi baştan çizer (anlık çizim; `kur` genelde gerekmez).
```html
<!doctype html><html><head><meta charset="utf-8"><title>01_koy</title>
<link rel="stylesheet" href="../../../engine/pixel/pixel.css"></head><body>
<script src="../../../engine/pixel/pixel.js"></script>
<script>
PX.sahne({
  sure: 6, arka: ["#1a1b3a", "#3e2a5e"], giris: "siyah", cikis: "devir", devir: { x: 90, y: 150, renk: "sari", sure: 1 },
  ciz(t, c) {
    const kx = t * 6;                                   // kamera kayması (parallax)
    c.gok(["#1a1b3a", "#283066", "#3e2a5e", "#7a4fb3"], { y1: 230 });
    c.yildizlar(t, { n: 50, y1: 170 }); c.ay(146, 78, { r: 10 });
    c.daglar({ y: 215, h: 70, renk: "#3b3270", golge: "#2c2350", kar: "#b8b4d8", tohum: 3, kayma: kx * 0.2 });
    c.daglar({ y: 232, h: 40, renk: "#1f4c36", tohum: 8, kayma: kx * 0.5, sivri: false });
    c.kamera(kx);                                       // bundan sonrası dünya koordinatında kayar
    c.agac(40, 262, { tur: "cam" }); c.ev(90, 262, { cati: "kirmizi" });
    c.zemin({ y: 262, renk: "#3a2a1e", ust: "#2f7a40", ust2: "#1f4c36", kayma: kx });
    c.sprite("insan", 20 + t * 22, 262, { anim: "yuru", renk: { g: "turuncu" } });
    c.kamera(0);                                        // yazılar ekrana sabit
    c.yazi({ tr: "Gece köyü" }, 90, 22, { boyut: 3, renk: "sari", t0: 0.3, hiz: 12 });
    c.balon({ tr: "Yıldızlar çok parlak!" }, 70, 234, { genislik: 110, t0: 3.4 });
  },
});
</script></body></html>
```
- Koordinatlar piksel; (0, 0) sol üst, ekran 180 x 320. Sprite, ağaç, ev, bina ve bulut **alt orta** noktalarından konumlanır. Ufuk çizgisi genelde y 240-270.
- Renk: palet adı (`kontur, siyah, gece, lacivert, mavi, gok, acikgok, buz, beyaz, krem, gri, koyugri, kahve, acikkahve, kum, ten, koyuten, esmer, kirmizi, koyukirmizi, turuncu, sari, altin, yesil, acikyesil, koyuyesil, orman, camgobegi, deniz, mor, lila, pembe, koyumor`) ya da `"#rrggbb"`. Az renk kullan (sahne başına 8-16); piksel art'ı güzel yapan kısıtlı palettir.
- Arka plan: `c.gok(renkler, {y0, y1})` bantlı gökyüzü, `c.yildizlar(t)`, `c.daglar({y, h, renk, golge, kar, tohum, kayma, sivri})`, `c.zemin({y, renk, ust, ust2, kayma})`, `c.su(t, {y})`, `c.yagmur(t)`, `c.kar(t)`, `c.gunes(x, y, {r})`, `c.ay(x, y, {r})`, `c.bulut(x, y, {gen})`.
- Nesneler: `c.agac(x, y, {tur: "yuvarlak|cam", boy, renk, koyu, acik})`, `c.ev(x, y, {gen, boy, duvar, cati, pencere: "isik|karanlik"})`, `c.bina(x, y, {gen, boy, renk, isik})`.
- Sprite'lar: `c.sprite(ad, x, y, {anim, t, ayna, renk: {harf: renk}, olcek})`. `insan` (anim: dur, yuru, sevin, salla; renk harfleri s saç, t ten, g gömlek, p pantolon, a ayakkabı; `ayna: true` sola bakar), `kedi`, `kus` (uc), `kalp`, `yildiz`, `para` (don), `unlem`, `soru`. Yakın çekimde `olcek: 2` ya da 3. Yeni sprite: `PX.sprite_ekle("ad", {anim: {fps, kareler: [["..kk..", ".kook.", ...], ...]}})`, harf haritası: `.` boş, `k` kontur, diğer harfler `renk` ile verilir.
- Yazı: `c.yazi(metin, x, y, {boyut: 1|2|3|4, renk, golge, kontur, hiza: "orta|sol|sag", genislik, t0, efekt: "daktilo|yukari|yanip", hiz, bit})`. boyut 1 küçük metin (10 px), 2 başlık (16 px), 3-4 büyük başlık. Türkçe ve Lehçe harflerin hepsi çalışır. `c.balon(metin, x, y, {genislik, kuyruk: "sol|orta|sag", t0, bit})` konuşma balonu (x, y kuyruğun ucu), `c.etiket(metin, x, y, {arka})` kutulu sayı ya da kısa etiket, `c.kutu(x, y, w, h, {renk, kenar})`.
- Çizim: `c.nokta`, `c.dikdortgen(x, y, w, h, renk, {op})`, `c.daire(x, y, r, renk, {kontur})`, `c.cizgi(x0, y0, x1, y1, renk)`. `op` (0-1) damalı yarı saydamlık verir.
- Kamera: `c.kamera(x, y)` sonraki dünya çizimlerini kaydırır; parallax için uzak katmanlara daha küçük `kayma` ver. Yazıdan önce `c.kamera(0)`.
- Hareket: konumlar t'den hesaplanır (`PX.p(t, t0, sure)`, `PX.kf(t, [[0, 10], [2, 80]])`, `PX.ara`). Piksel art'ta hareket basamaklıdır, pürüzsüz kayma değil; yürüyen karakter + yavaş kamera kayması + yanıp sönen yıldız yeterince canlıdır.
- Geçiş: `giris/cikis: "siyah" | "beyaz" | "iris" | "devir" | "yok"`. `cikis: "devir"` + `devir: {x, y, renk, sure}` noktadan büyüyen dairenin sonraki sahnenin rengine dönüşmesi; `iris` eski oyunlardaki daralan daire.

## Kontrol
Dosyaları yazdıktan sonra kullanıcıya stüdyoda projeyi seçip ▶ ile önizlemesini söyle. Hata olursa stüdyodaki "Kayıtlar" bölümündeki metni iste.
