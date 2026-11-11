/* =====================================================================
   Piksel Animasyon Kütüphanesi (PX)
   Gerçek piksel art: sahne düşük çözünürlüklü bir tuvale (varsayılan 180 x 320) piksel piksel çizilir,
   ekrana tam kat büyütülür (1080 x 1920'de her piksel 6 x 6). Bulanıklık, yumuşatma, yarı saydamlık yok;
   solmalar ve geçişler "dither" (damalı nokta deseni) ile yapılır.

   Her sahne: PX.sahne({ sure, arka, kur(s), ciz(t, c) })
   - ciz(t, c): her karede tuval temizlenir ve sahne baştan çizilir (zamanın saf fonksiyonu).
   - c: çizim araçları (c.gok, c.daglar, c.sprite, c.agac, c.yazi, c.balon ... aşağıda).
   Koordinatlar piksel cinsinden; (0, 0) sol üst. Sprite'lar ve ağaçlar ALT ORTA noktalarından konumlanır.
   Mod: ?mod=kayit (video), ?mod=gomulu (stüdyo önizlemesi), yoksa kendi kendine oynar.
   ===================================================================== */
(function () {
  const q = new URLSearchParams(location.search);
  { let r = 20261111; Math.random = () => ((r = (Math.imul(r, 1664525) + 1013904223) >>> 0) / 4294967296); }

  const PX = (window.PX = {
    dil: q.get("dil") || "tr", mod: q.get("mod") || "oynat",
    W: 180, H: 320, sure: 5, t: 0, uyarilar: [], _sahne: null,
  });
  window.V = PX;                     // stüdyo ve kayıt aracı V.git(t) çağırır
  window.UYARILAR = PX.uyarilar;
  PX.uyar = (m) => { if (!PX.uyarilar.includes(m)) { PX.uyarilar.push(m); console.warn("[piksel] " + m); } };

  /* ---------------- palet ---------------- */
  // Adla ya da "#rrggbb" ile renk verilebilir.
  PX.palet = {
    kontur: "#1d1a2b", siyah: "#0e0c16", gece: "#1a1b3a", lacivert: "#283066", mavi: "#3b5fb5", gok: "#5e9be0",
    acikgok: "#9ccbf0", buz: "#d6eefa", beyaz: "#f6f2e6", krem: "#f2e2b8", gri: "#9c9aae", koyugri: "#5d5b72",
    kahve: "#6e4630", acikkahve: "#a56c40", kum: "#e2c27a", ten: "#f2c29b", koyuten: "#b77a4f", esmer: "#8c5638",
    kirmizi: "#d8433c", koyukirmizi: "#8e2b31", turuncu: "#ef8a37", sari: "#f6cf48", altin: "#d9a21f",
    yesil: "#5cb24a", acikyesil: "#9bd65a", koyuyesil: "#2f7a40", orman: "#1f4c36", camgobegi: "#3db5ae",
    deniz: "#2a7fa8", mor: "#7a4fb3", lila: "#b48ae0", pembe: "#ea7fae", koyumor: "#3e2a5e",
  };
  const renkCoz = (r) => (r == null ? null : r[0] === "#" ? r : PX.palet[r] || (PX.uyar(`Bilinmeyen renk: ${r}`), "#ff00ff"));
  const ON = {};
  const u32 = (r) => {          // "#rrggbb" -> ABGR (little endian ImageData)
    r = renkCoz(r); if (!r) return 0;
    if (ON[r] !== undefined) return ON[r];
    let h = r.slice(1); if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    const n = parseInt(h.slice(0, 6), 16);
    return (ON[r] = (0xff000000 | ((n & 0xff) << 16) | (n & 0xff00) | ((n >> 16) & 0xff)) >>> 0);
  };
  const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);
  const bayer = (x, y) => BAYER[(y & 3) * 4 + (x & 3)];
  PX.karistir = (a, b, p) => {
    const A = renkCoz(a), B = renkCoz(b), h = (s) => [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16));
    const x = h(A), y = h(B);
    return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * p).toString(16).padStart(2, "0")).join("");
  };

  /* ---------------- zaman yardımcıları ---------------- */
  PX.sinir = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  PX.e = { lin: (x) => x, giris: (x) => x * x * x, cikis: (x) => 1 - Math.pow(1 - x, 3), iki: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2) };
  /** 0→1 ilerleme: t0'da başlar, sure saniyede biter */
  PX.p = (t, t0, sure, yumusak = "iki") => PX.e[yumusak](PX.sinir((t - t0) / sure));
  PX.ara = (a, b, p) => a + (b - a) * p;
  /** anahtar kareler: PX.kf(t, [[0, 10], [2, 80], [3, 80]]) */
  PX.kf = (t, k, yumusak = "iki") => {
    if (t <= k[0][0]) return k[0][1];
    for (let i = 1; i < k.length; i++) if (t <= k[i][0]) return PX.ara(k[i - 1][1], k[i][1], PX.e[yumusak]((t - k[i - 1][0]) / (k[i][0] - k[i - 1][0])));
    return k[k.length - 1][1];
  };
  /** sahne başına sabit "rastgele" sayı üreteci */
  PX.tohum = (s) => { let r = (s * 2654435761) >>> 0 || 1; return () => ((r = (Math.imul(r, 1664525) + 1013904223) >>> 0) / 4294967296); };

  /* ---------------- çok dilli yazı ---------------- */
  PX._ceviri = undefined;
  const ceviriler = () => {
    if (PX._ceviri !== undefined) return PX._ceviri;
    PX._ceviri = null;
    try {
      const m = location.pathname.match(/^(.*\/projeler\/[^/]+\/)/);
      if (m) { const x = new XMLHttpRequest(); x.open("GET", m[1] + "ceviri.json?v=" + Date.now(), false); x.send(); if (x.status === 200) PX._ceviri = JSON.parse(x.responseText); }
    } catch (e) { /* çeviri yoksa sorun değil */ }
    return PX._ceviri;
  };
  PX.metin = (v) => {
    if (!v || typeof v !== "object") return v ?? "";
    if (v[PX.dil] != null) return v[PX.dil];
    const e = (((ceviriler() || {}).diller || {})[PX.dil] || {}).ekran || {};
    for (const k in v) if (e[v[k]]) return e[v[k]];
    return v.en ?? Object.values(v)[0];
  };

  /* ---------------- sprite'lar ----------------
     Harf haritası. "." boş, "k" kontur; diğer harfler aşağıdaki varsayılan renklerden gelir ve
     c.sprite(..., {renk: {g: "kirmizi"}}) ile değiştirilebilir. */
  const VARSAYILAN = { k: "kontur", s: "kahve", t: "ten", g: "camgobegi", G: "deniz", p: "lacivert", a: "kontur", w: "beyaz",
    y: "yesil", Y: "koyuyesil", b: "acikkahve", r: "kirmizi", R: "koyukirmizi", o: "sari", O: "altin", m: "pembe", l: "gri", L: "koyugri" };
  const UST = [       // insan: baş ve gövde (12 x 14)
    "...kkkkkk...",
    "..kssssssk..",
    ".kssssssssk.",
    ".ksssssssskk",
    ".kssttttsssk",
    ".ksttttttsk.",
    ".kttkttkttk.",
    ".kttttttttk.",
    "..kttmmttk..",
    "...kkkkkk...",
  ];
  const KOL = {      // 4 satır: kollar + gövde
    yan: ["..kggggggk..", ".kgkggggkgk.", ".kgkggggkgk.", ".ktkggggktk."],
    one: ["..kggggggk..", ".kgkggggkgk.", "..kkggggktk.", "..ktkgggkk.."],
    arka: ["..kggggggk..", ".kgkggggkgk.", ".ktkggggkk..", "..kkgggktk.."],
    yukari: ["kt.kggggk.tk", "kgkggggggkgk", ".kkggggggkk.", "..kggggggk.."],
    sallama: ["..kggggggktk", ".kgkggggkkgk", ".kgkggggkgk.", ".ktkggggk...", ],
  };
  const BACAK = {    // 6 satır
    dur: ["...kppppk...", "...kppppk...", "...kpkkpk...", "...kpkkpk...", "..kaakkaak..", "..kkkk.kkkk."].map((s) => s.slice(0, 12)),
    adim1: ["...kppppk...", "..kppkkppk..", "..kpk..kpk..", ".kpk....kpk.", ".kaak...kaak", ".kkk.....kkk"].map((s) => s.slice(0, 12)),
    adim2: ["...kppppk...", "...kppppk...", "...kpkkpk...", "...kpkkpk...", "..kaakkaak..", "..kkkk.kkkk."].map((s) => s.slice(0, 12)),
    zipla: ["...kppppk...", "..kppkkppk..", "..kpk..kpk..", "..kaak.kaak.", "..kkk...kkk.", "............"],
  };
  const insanKare = (kol, bacak, gozKapali) => {
    const ust = UST.slice(); if (gozKapali) ust[6] = ".kttttttttk.";
    return [...ust, ...KOL[kol], ...BACAK[bacak]];
  };
  const SPRITE = {
    insan: {
      dur: { fps: 2, kareler: [insanKare("yan", "dur"), insanKare("yan", "dur"), insanKare("yan", "dur"), insanKare("yan", "dur", true)] },
      yuru: { fps: 8, kareler: [insanKare("one", "adim1"), insanKare("yan", "adim2"), insanKare("arka", "adim1"), insanKare("yan", "adim2")] },
      sevin: { fps: 6, kareler: [insanKare("yukari", "dur"), insanKare("yukari", "zipla")] },
      salla: { fps: 6, kareler: [insanKare("sallama", "dur"), insanKare("yan", "dur")] },
    },
    kus: { uc: { fps: 8, kareler: [
      ["k.......k", "gk.....kg", ".gk...kg.", "..gkkkg..", "...kgk...", "....k...."],
      [".........", ".........", "kkk...kkk", ".gkkkkkg.", "...kgk...", "....k...."],
    ] } },
    kalp: { dur: { fps: 4, kareler: [
      [".kk...kk.", "krrk.krrk", "krwrkrrrk", "krrrrrrrk", ".krrrrrk.", "..krrrk..", "...krk...", "....k...."],
      ["..........", ".kk...kk..", "krrk.krrk.", "krwrrrrrk.", ".krrrrrk..", "..krrrk...", "...krk....", "....k....."].map((s) => s.slice(0, 9)),
    ] } },
    yildiz: { dur: { fps: 3, kareler: [
      ["....k....", "...kok...", "kkkkookkk", "kooooooOk", ".kooooOk.", ".kookoOk.", "kook.kOOk", "kkk...kkk"],
      ["....k....", "...kok...", "kkkkookkk", "kowooooOk", ".kooooOk.", ".kookoOk.", "kook.kOOk", "kkk...kkk"],
    ] } },
    para: { don: { fps: 8, kareler: [
      ["..kkkk..", ".koooOk.", "kowoOoOk", "kooOooOk", "kooOooOk", "koooooOk", ".kOOOOk.", "..kkkk.."],
      ["..kkk...", ".kooOk..", ".koOOk..", ".koOOk..", ".koOOk..", ".koOOk..", ".kOOOk..", "..kkk..."].map((s) => ".." + s.slice(0, 6)),
      ["...kk...", "...kOk..", "...kOk..", "...kOk..", "...kOk..", "...kOk..", "...kOk..", "...kk..."],
      ["..kkk...", ".kooOk..", ".koOOk..", ".koOOk..", ".koOOk..", ".koOOk..", ".kOOOk..", "..kkk..."].map((s) => ".." + s.slice(0, 6)),
    ] } },
    kedi: {
      dur: { fps: 2, kareler: [
        ["k...k.....", "kokkok....", "koooook...", "kokooko.kk", "koowook.ko", ".kooookko.", ".koooooook", ".koooooook", ".kokkkokok", ".kk...kk.."],
        ["k...k.....", "kokkok....", "koooook...", "kkkookk.kk", "koowook..k", ".kooookkok", ".koooooook", ".koooooook", ".kokkkokok", ".kk...kk.."],
      ] },
    },
    unlem: { dur: { fps: 4, kareler: [[".kk.", "kwwk", "kwwk", "kwwk", ".kk.", "....", ".kk.", "kwwk", ".kk."]] } },
    soru: { dur: { fps: 4, kareler: [[".kkkk.", "kwwwwk", "kwkkwk", ".k.kwk", "..kwk.", "..kwk.", "..kk..", "..kk..", ".kwwk.", "..kk.."]] } },
  };
  PX.sprite_ekle = (ad, animler) => { SPRITE[ad] = animler; };
  PX.spritelar = () => Object.keys(SPRITE);

  /* ---------------- çizim tuvali ---------------- */
  let BUF = null, IMG = null, CTX = null, CNV = null, YAZI = null;
  const kam = { x: 0, y: 0 };
  const C = {};
  const nokta = (x, y, renk, op = 1) => {
    x |= 0; y |= 0;
    if (x < 0 || y < 0 || x >= PX.W || y >= PX.H) return;
    if (op < 1 && bayer(x, y) >= op) return;
    BUF[y * PX.W + x] = renk;
  };
  /** kamera: bundan sonraki dünya çizimleri (x, y) kadar kayar; parallax için katsayıyla ver: c.kamera(kx * 0.5) */
  C.kamera = (x = 0, y = 0) => { kam.x = Math.round(x); kam.y = Math.round(y); };
  const X = (x) => Math.round(x - kam.x), Y = (y) => Math.round(y - kam.y);
  C.nokta = (x, y, renk, op = 1) => nokta(X(x), Y(y), u32(renk), op);
  C.temizle = (renk) => BUF.fill(u32(renk));
  C.dikdortgen = (x, y, w, h, renk, { op = 1 } = {}) => {
    const r = u32(renk); x = X(x); y = Y(y);
    for (let j = Math.max(0, y); j < Math.min(PX.H, y + h); j++) for (let i = Math.max(0, x); i < Math.min(PX.W, x + w); i++) nokta(i, j, r, op);
  };
  C.daire = (cx, cy, r, renk, { op = 1, kontur = null } = {}) => {
    const c = u32(renk), k = kontur && u32(kontur); cx = X(cx); cy = Y(cy);
    const r2 = (r + 0.5) * (r + 0.5), ri = (r - 0.5) * (r - 0.5);
    for (let j = -Math.ceil(r); j <= Math.ceil(r); j++) for (let i = -Math.ceil(r); i <= Math.ceil(r); i++) {
      const d = i * i + j * j; if (d > r2) continue;
      nokta(cx + i, cy + j, k && d > ri ? k : c, op);
    }
  };
  C.cizgi = (x0, y0, x1, y1, renk, { op = 1 } = {}) => {
    const c = u32(renk); x0 = X(x0); y0 = Y(y0); x1 = X(x1); y1 = Y(y1);
    const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1; let e = dx + dy;
    for (let n = 0; n < 2000; n++) { nokta(x0, y0, c, op); if (x0 === x1 && y0 === y1) break; const e2 = 2 * e; if (e2 >= dy) { e += dy; x0 += sx; } if (e2 <= dx) { e += dx; y0 += sy; } }
  };
  /** gökyüzü: renkler yukarıdan aşağıya, aralarda dither geçişli bantlar. y0..y1 ekran pikseli */
  C.gok = (renkler, { y0 = 0, y1 = PX.H } = {}) => {
    const r = renkler.map(u32), n = r.length - 1;
    for (let y = Math.max(0, y0); y < Math.min(PX.H, y1); y++) {
      const p = n ? ((y - y0) / Math.max(1, y1 - y0 - 1)) * n : 0, i = Math.min(n - 1, Math.floor(p)), f = p - i;
      // her renk çifti arasında 4 düz bant; bant sınırında 2 satır damalı geçiş (klasik piksel art gökyüzü)
      const bh = Math.max(1, (y1 - y0) / Math.max(1, n) / 4), k = Math.floor(f * 4), ici = (f * 4 - k) * bh;
      const a = n ? (k === 0 ? r[i] : PX._ara(i, k, renkler)) : r[0], b = n ? (k === 3 ? r[i + 1] : PX._ara(i, k + 1, renkler)) : r[0];
      for (let x = 0; x < PX.W; x++) BUF[y * PX.W + x] = ici > bh - 2 && ((x + y) & 1) ? b : a;
    }
  };
  PX._ara = (i, k, renkler) => u32(PX.karistir(renkCoz(renkler[i]), renkCoz(renkler[i + 1]), k / 4));
  /** yanıp sönen yıldızlar (ekran sabit) */
  C.yildizlar = (t, { n = 40, renk = "beyaz", y1 = PX.H * 0.6, tohum = 3 } = {}) => {
    const R = PX.tohum(tohum), c = u32(renk), c2 = u32("gri");
    for (let i = 0; i < n; i++) {
      const x = (R() * PX.W) | 0, y = (R() * y1) | 0, faz = R() * 6.28, hiz = 1 + R() * 2;
      const p = Math.sin(t * hiz + faz);
      if (p > 0.85 && R() < 2) { nokta(x, y, c); nokta(x - 1, y, c2); nokta(x + 1, y, c2); nokta(x, y - 1, c2); nokta(x, y + 1, c2); }
      else if (p > -0.3) nokta(x, y, p > 0.4 ? c : c2);
    }
  };
  /** dağ ya da tepe sırası (parallax için kayma kullan). sivri: true dağ, false yumuşak tepe */
  C.daglar = ({ y = 200, h = 60, renk = "koyumor", tohum = 1, kayma = 0, sivri = true, kar = null, golge = null } = {}) => {
    const R = PX.tohum(tohum), f = [R() * 0.02 + 0.015, R() * 0.05 + 0.03, R() * 0.11 + 0.07], fz = [R() * 9, R() * 9, R() * 9];
    const c = u32(renk), ck = kar && u32(kar), cg = golge && u32(golge);
    const tepeAl = (w) => {
      let v = Math.sin(w * f[0] + fz[0]) * 0.55 + Math.sin(w * f[1] + fz[1]) * 0.3 + Math.sin(w * f[2] + fz[2]) * 0.15;
      if (sivri) v = 1 - Math.abs(v) * 1.6 + 0.3 * v;
      return y - h * (0.5 + 0.5 * v);
    };
    // önce tepe çizgisi; gölge için her inişin başladığı zirveyi bul (ışık soldan)
    const T = [], Z = [];
    let zx = -1e9, zy = 0;
    for (let x = -60; x < PX.W; x++) {
      const w = x + kayma, ty = tepeAl(w), on = tepeAl(w - 1), son = tepeAl(w + 1);
      if (ty <= on && ty <= son) { zx = x; zy = ty; }
      if (x >= 0) { T[x] = Math.round(ty); Z[x] = son > ty ? [zx, zy] : null; }
    }
    for (let x = 0; x < PX.W; x++) {
      const tepe = T[x], z = Z[x];
      for (let j = Math.max(0, tepe); j < PX.H; j++) {
        let r = c;
        if (ck && tepe < y - h * 0.5 && j < tepe + 1 + (y - h * 0.5 - tepe) * 0.3 + (bayer(x, j) < 0.5 ? 1 : 0)) r = ck;
        else if (cg && z && x - z[0] > (j - z[1]) * 0.22) r = cg;
        BUF[j * PX.W + x] = r;
      }
    }
  };
  /** düz zemin: üstte ince çim/kenar şeridi */
  C.zemin = ({ y = 260, renk = "kahve", ust = "yesil", ust2 = "koyuyesil", kayma = 0 } = {}) => {
    const a = u32(renk), b = u32(ust), b2 = u32(ust2);
    for (let j = Math.max(0, y); j < PX.H; j++) for (let x = 0; x < PX.W; x++) {
      const w = x + kayma, d = j - y;
      let r = a;
      if (d < 3) r = b; else if (d < 5) r = ((w * 7 + d) % 5 === 0) ? b : b2;
      else if (((w * 13 + j * 7) % 23) === 0) r = b2;
      BUF[j * PX.W + x] = r;
    }
  };
  /** su yüzeyi: dalgalanan parıltılar */
  C.su = (t, { y = 260, renk = "deniz", parilti = "acikgok", koyu = "lacivert" } = {}) => {
    const a = u32(renk), p = u32(parilti), k = u32(koyu);
    for (let j = Math.max(0, y); j < PX.H; j++) for (let x = 0; x < PX.W; x++) {
      const d = j - y, dal = Math.sin(x * 0.35 + t * 3 + j * 0.9) + Math.sin(x * 0.11 - t * 2);
      BUF[j * PX.W + x] = dal > 1.55 ? p : d > 30 && bayer(x, j) < Math.min(0.75, (d - 30) / 60) ? k : a;
    }
  };

  const spriteCache = new Map();
  const spriteHazirla = (satirlar, renk) => {
    const anahtar = satirlar.join("|") + JSON.stringify(renk || {});
    if (spriteCache.has(anahtar)) return spriteCache.get(anahtar);
    const h = satirlar.length, w = Math.max(...satirlar.map((s) => s.length)), d = new Uint32Array(w * h);
    for (let j = 0; j < h; j++) for (let i = 0; i < satirlar[j].length; i++) {
      const ch = satirlar[j][i]; if (ch === "." || ch === " ") continue;
      d[j * w + i] = u32((renk && renk[ch]) || VARSAYILAN[ch] || "#ff00ff");
    }
    const s = { w, h, d }; spriteCache.set(anahtar, s); return s;
  };
  /** hazır sprite: c.sprite("insan", x, y, {anim: "yuru", t, ayna, renk: {g: "kirmizi", s: "sari"}, olcek: 2})
   *  (x, y) alt orta nokta. Adlar: PX.spritelar(). insan: dur | yuru | sevin | salla. renk harfleri: s saç, t ten, g gömlek, p pantolon, a ayakkabı */
  C.sprite = (ad, x, y, { anim, t = PX.t, kare = null, ayna = false, renk = null, olcek = 1, op = 1 } = {}) => {
    const sp = SPRITE[ad]; if (!sp) return PX.uyar(`Bilinmeyen sprite: ${ad} (olanlar: ${PX.spritelar().join(", ")})`);
    const a = sp[anim] || sp[Object.keys(sp)[0]];
    const ki = kare ?? Math.floor(t * a.fps + 1e-6) % a.kareler.length;
    const s = spriteHazirla(a.kareler[ki], renk);
    const ox = X(x) - Math.floor((s.w * olcek) / 2), oy = Y(y) - s.h * olcek;
    for (let j = 0; j < s.h * olcek; j++) for (let i = 0; i < s.w * olcek; i++) {
      const sx = ayna ? s.w - 1 - Math.floor(i / olcek) : Math.floor(i / olcek), v = s.d[Math.floor(j / olcek) * s.w + sx];
      if (v) nokta(ox + i, oy + j, v, op);
    }
    return { w: s.w * olcek, h: s.h * olcek };
  };
  /** ağaç (yuvarlak ya da çam), (x, y) gövde dibi; rüzgârda hafifçe sallanır */
  C.agac = (x, y, { tur = "yuvarlak", boy = 1, renk = "yesil", koyu = "koyuyesil", acik = "acikyesil", t = PX.t, tohum = 0 } = {}) => {
    const sal = Math.round(Math.sin(t * 1.6 + x * 0.3 + tohum) * 0.6 * boy);
    const g = u32("kahve"), gk = u32("kontur"), r = u32(renk), rk = u32(koyu), ra = u32(acik);
    const gx = X(x), gy = Y(y);
    if (tur === "cam") {
      const H = Math.round(26 * boy), gov = Math.round(5 * boy);
      for (let j = 0; j < gov; j++) { nokta(gx, gy - 1 - j, g); nokta(gx - 1, gy - 1 - j, gk); nokta(gx + 1, gy - 1 - j, gk); }
      for (let j = 0; j < H; j++) {
        const yy = gy - gov - j, kat = j % Math.max(4, Math.round(7 * boy)), gen = Math.round((H - j) * 0.42 * (0.6 + 0.4 * (1 - kat / (7 * boy)))) + 1;
        const kay = Math.round(sal * (j / H));
        for (let i = -gen; i <= gen; i++) nokta(gx + i + kay, yy, Math.abs(i) === gen ? gk : i > gen * 0.25 ? rk : i < -gen * 0.4 && bayer(gx + i, yy) < 0.5 ? ra : r);
      }
      nokta(gx + sal, gy - gov - H, gk);
      return;
    }
    const R = Math.round(10 * boy), gov = Math.round(7 * boy), cy = gy - gov - R + 2;
    for (let j = 0; j < gov; j++) { nokta(gx, gy - 1 - j, g); nokta(gx + 1, gy - 1 - j, g); nokta(gx - 1, gy - 1 - j, gk); nokta(gx + 2, gy - 1 - j, gk); }
    const top = [[0, 0, R], [-R * 0.6, R * 0.25, R * 0.7], [R * 0.6, R * 0.3, R * 0.65]];
    for (let j = -R - 2; j <= R + 2; j++) for (let i = -R * 2; i <= R * 2; i++) {
      let ic = false, kenar = false;
      for (const [ox, oy, rr] of top) { const d = Math.hypot(i - ox - sal, j - oy); if (d <= rr - 0.5) ic = true; else if (d <= rr + 0.6) kenar = true; }
      if (ic) { const isik = (i + j) < -R * 0.5, golge = (i - j * 0.3) > R * 0.35 || j > R * 0.45;
        nokta(gx + i, cy + j, isik && bayer(gx + i, cy + j) < 0.6 ? ra : golge ? rk : r); }
      else if (kenar) nokta(gx + i, cy + j, gk);
    }
  };
  /** ev: (x, y) alt orta. pencere: "isik" (sarı yanar) ya da "karanlik" */
  C.ev = (x, y, { gen = 26, boy = 18, duvar = "krem", cati = "kirmizi", kapi = "kahve", pencere = "isik", baca = true } = {}) => {
    const l = Math.round(x - gen / 2), u = y - boy;
    C.dikdortgen(l, u, gen, boy, duvar); C.dikdortgen(l, u, 1, boy, "kontur"); C.dikdortgen(l + gen - 1, u, 1, boy, "kontur"); C.dikdortgen(l, y - 1, gen, 1, "kontur");
    C.dikdortgen(l + 1, u + 1, gen - 2, 2, PX.karistir(renkCoz(duvar), "#000000", 0.18));
    const ch = Math.round(gen * 0.45) + 2;
    for (let j = 0; j < ch; j++) { const w = Math.round((gen / 2 + 3) * (j / ch)); C.dikdortgen(x - w, u - ch + j, w * 2 + 1, 1, j === ch - 1 ? "kontur" : cati); nokta(X(x - w - 1), Y(u - ch + j), u32("kontur")); nokta(X(x + w + 1), Y(u - ch + j), u32("kontur")); }
    if (baca) C.dikdortgen(l + gen - 8, u - ch + 2, 4, Math.round(ch * 0.6), "koyugri");
    C.dikdortgen(Math.round(x - 3), y - 10, 6, 9, kapi); C.dikdortgen(Math.round(x - 3), y - 11, 6, 1, "kontur"); nokta(X(x + 1), Y(y - 5), u32("sari"));
    const pr = pencere === "isik" ? "sari" : "lacivert";
    for (const px of [l + 3, l + gen - 8]) { C.dikdortgen(px, u + 5, 5, 5, "kontur"); C.dikdortgen(px + 1, u + 6, 3, 3, pr); }
  };
  /** şehir binası: pencereler zamanla yanıp söner */
  C.bina = (x, y, { gen = 24, boy = 60, renk = "koyumor", isik = 0.45, t = PX.t, tohum = 1 } = {}) => {
    const l = Math.round(x - gen / 2), u = y - boy, R = PX.tohum(tohum);
    C.dikdortgen(l, u, gen, boy, renk); C.dikdortgen(l, u, gen, 1, "kontur");
    C.dikdortgen(l + gen - 2, u + 1, 2, boy - 1, PX.karistir(renkCoz(renk), "#000000", 0.25));
    for (let j = u + 4; j < y - 4; j += 6) for (let i = l + 3; i < l + gen - 4; i += 5) {
      const yan = R() < isik && Math.sin(t * (0.2 + R() * 0.5) + R() * 20) > -0.7;
      C.dikdortgen(i, j, 2, 3, yan ? "sari" : PX.karistir(renkCoz(renk), "#000000", 0.4));
    }
  };
  /** bulut: (x, y) alt orta */
  C.bulut = (x, y, { gen = 30, renk = "beyaz", golge = "buz", tohum = 2 } = {}) => {
    const R = PX.tohum(tohum), parca = [[0, -gen * 0.18, gen * 0.22], [-gen * 0.28, -gen * 0.1, gen * 0.16], [gen * 0.28, -gen * 0.09, gen * 0.17], [gen * 0.1 * (R() - 0.5), -gen * 0.05, gen * 0.2]];
    const a = u32(renk), g = u32(golge), cx = X(x), cy = Y(y);
    for (let j = -gen * 0.45; j <= 0; j++) for (let i = -gen * 0.55; i <= gen * 0.55; i++) {
      let ic = false; for (const [ox, oy, r] of parca) if (Math.hypot(i - ox, j - oy) <= r) ic = true;
      if (ic) nokta(cx + Math.round(i), cy + Math.round(j), j > -gen * 0.08 ? g : a);
    }
  };
  C.gunes = (x, y, { r = 10, t = PX.t, renk = "sari", isin = "turuncu" } = {}) => {
    for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4 + t * 0.4, d0 = r + 3, d1 = r + 5 + (Math.sin(t * 3 + i) > 0 ? 1 : 0);
      C.cizgi(x + Math.cos(a) * d0, y + Math.sin(a) * d0, x + Math.cos(a) * d1, y + Math.sin(a) * d1, isin); }
    C.daire(x, y, r, renk, { kontur: isin });
  };
  C.ay = (x, y, { r = 9, renk = "krem", hilal = true } = {}) => {
    const c = u32(renk), cx = X(x), cy = Y(y);
    for (let j = -r; j <= r; j++) for (let i = -r; i <= r; i++) {
      if (i * i + j * j > (r + 0.5) ** 2) continue;
      if (hilal && (i - r * 0.45) ** 2 + (j + r * 0.3) ** 2 <= (r * 0.85) ** 2) continue;
      nokta(cx + i, cy + j, c);
    }
  };
  /** yağmur ve kar (ekran sabit) */
  C.yagmur = (t, { n = 60, renk = "acikgok", hiz = 220, egim = 0.25 } = {}) => {
    const R = PX.tohum(7);
    for (let i = 0; i < n; i++) { const x0 = R() * (PX.W + 60), y0 = R() * PX.H, y = (y0 + t * hiz * (0.8 + R() * 0.4)) % (PX.H + 10), x = (x0 - y * egim) % (PX.W + 60);
      C.cizgi(x + kam.x, y + kam.y, x + 1 + kam.x, y + 3 + kam.y, renk); }
  };
  C.kar = (t, { n = 50, renk = "beyaz" } = {}) => {
    const R = PX.tohum(9);
    for (let i = 0; i < n; i++) { const x0 = R() * PX.W, y = (R() * PX.H + t * (14 + R() * 12)) % PX.H, x = x0 + Math.sin(t * 1.5 + i) * 3;
      nokta(x | 0, y | 0, u32(renk)); if (i % 3 === 0) nokta((x | 0) + 1, y | 0, u32(renk)); }
  };

  /* ---------------- yazı ----------------
     boyut 1: küçük yazı (Tiny5, 10 px; Türkçe ve Lehçe harflerin işaretleri piksel piksel eklenir)
     boyut 2-4: başlık (Pixelify Sans, 16 / 24 / 32 px) */
  const BUYUK_PX = { 2: 16, 3: 24, 4: 32 };
  const ISARET = {
    "̆": [[-1, -2], [1, -2], [0, -1]], "̌": [[-1, -2], [1, -2], [0, -1]], "̇": [[0, -2]], "́": [[0, -2], [1, -3]],
    "̀": [[0, -2], [-1, -3]], "̂": [[-1, -2], [0, -3], [1, -2]], "̈": [[-1, -2], [1, -2]], "̃": [[-1, -2], [0, -3], [1, -2], [2, -3]],
    "̊": [[0, -3], [-1, -2], [1, -2]], "̋": [[-1, -2], [0, -3], [1, -2], [2, -3]], "̧": [[0, 1], [0, 2], [-1, 2]], "̨": [[0, 1], [1, 2]],
  };
  const kucukMu = (boyut) => !(boyut >= 2);
  const fontAyarla = (boyut, kalin) => { YAZI.font = kucukMu(boyut) ? "10px Tiny5" : `${kalin ? 700 : 400} ${BUYUK_PX[boyut] || Math.round(boyut * 8)}px Pixelify`; };
  const satirYuksek = (boyut) => (kucukMu(boyut) ? 10 : BUYUK_PX[boyut] || Math.round(boyut * 8));
  // küçük fontta olmayan harfler: temel harf + işaret
  const parcala = (ch) => {
    if (ch.charCodeAt(0) <= 0xff) return [ch, []];
    if (ch === "ı") return ["i", ["noktasiz"]];
    if (ch === "ł" || ch === "Ł") return [ch === "ł" ? "l" : "L", ["cizik"]];
    const d = ch.normalize("NFD");
    return d.length > 1 ? [d[0], [...d.slice(1)]] : [ch, []];
  };
  let X_UST = null;     // küçük fontta x harfinin üst sınırı (ı'nın noktasını silmek için)
  const olc = (s, boyut, kalin) => {
    fontAyarla(boyut, kalin);
    if (!kucukMu(boyut)) return YAZI.measureText(s).width;
    let w = 0; for (const ch of s) w += YAZI.measureText(parcala(ch)[0]).width; return w;
  };
  // satırı YAZI tuvaline beyaz olarak çizer (2, 2 kaydırmalı)
  const satirCiz = (s, boyut, kalin) => {
    const c = YAZI; c.clearRect(0, 0, c.canvas.width, c.canvas.height); c.fillStyle = "#fff"; c.textBaseline = "top"; fontAyarla(boyut, kalin);
    if (!kucukMu(boyut)) { c.fillText(s, 2, 2); return; }
    if (X_UST === null) {
      c.fillText("x", 2, 2); const d = c.getImageData(0, 0, 12, 14).data; X_UST = 2;
      for (let j = 0; j < 14; j++) { let v = false; for (let i = 0; i < 12; i++) if (d[(j * 12 + i) * 4 + 3] > 110) v = true; if (v) { X_UST = j; break; } }
      c.clearRect(0, 0, 40, 20);
    }
    let x = 2;
    for (const ch of s) {
      const [taban, isaretler] = parcala(ch), adv = c.measureText(taban).width;
      c.fillText(taban, x, 2);
      if (isaretler.length) {
        const gx = Math.floor(x), gw = Math.ceil(adv) + 1, d = c.getImageData(gx, 0, gw, 18).data;
        let ust = 99, alt = -1, sol = 99, sag = -1;
        for (let j = 0; j < 18; j++) for (let i = 0; i < gw; i++) if (d[(j * gw + i) * 4 + 3] > 110) { ust = Math.min(ust, j); alt = Math.max(alt, j); sol = Math.min(sol, i); sag = Math.max(sag, i); }
        const orta = gx + Math.round((sol + sag) / 2);
        for (const m of isaretler) {
          if (m === "noktasiz") { c.clearRect(gx, 0, gw, X_UST); continue; }
          if (m === "cizik") { const yy = Math.round((ust + alt) / 2); c.fillRect(orta - 1, yy, 1, 1); c.fillRect(orta + 1, yy - 1, 1, 1); continue; }
          const p = ISARET[m]; if (!p) continue;
          for (const [dx, dy] of p) {
            const bx = m === "̨" ? gx + sag : orta, by = dy < 0 ? ust + dy : alt + dy;
            if (by >= 0) c.fillRect(bx + dx, by, 1, 1);
          }
        }
      }
      x += adv;
    }
  };
  const satirlaraBol = (s, boyut, kalin, genislik) => {
    const cikti = [];
    for (const par of String(s).split("\n")) {
      let sat = "";
      for (const k of par.split(" ")) { const den = sat ? sat + " " + k : k; if (genislik && sat && olc(den, boyut, kalin) > genislik) { cikti.push(sat); sat = k; } else sat = den; }
      cikti.push(sat);
    }
    return cikti;
  };
  /** yazı: c.yazi({tr: "Merhaba"}, 90, 40, {boyut: 2, renk: "beyaz", golge: "kontur", hiza: "orta", genislik: 160, t0: 0.5, efekt: "daktilo"})
   *  boyut 1 küçük metin, 2 başlık, 3-4 büyük başlık. efekt: "daktilo" (harf harf), "yukari", "yanip"; bit: çıkış zamanı (dither ile solar) */
  C.yazi = (metin, x, y, { boyut = 2, renk = "beyaz", golge = "kontur", kontur = null, hiza = "orta", genislik = PX.W - 16, aralik = 1.3, kalin = false, t = PX.t, t0 = null, efekt = "daktilo", hiz = 30, bit = null } = {}) => {
    const tam = PX.metin(metin);
    let s = tam, op = 1, dy = 0;
    if (t0 != null) {
      if (t < t0) return;
      if (efekt === "daktilo") s = [...tam].slice(0, Math.floor((t - t0) * hiz)).join("");
      else if (efekt === "yukari") { const p = PX.p(t, t0, 0.5, "cikis"); dy = Math.round((1 - p) * 8); op = p; }
      else if (efekt === "yanip") op = Math.floor((t - t0) * 2) % 2 === 0 || t - t0 > 1.5 ? 1 : 0;
    }
    if (bit != null && t > bit) op = Math.min(op, 1 - PX.p(t, bit, 0.4, "lin"));
    if (op <= 0 || !s) return;
    const sh = satirYuksek(boyut), satirlar = satirlaraBol(tam, boyut, kalin, genislik);
    let kalan = [...s].length; const gor = satirlar.map((l) => { const p = [...l].slice(0, Math.max(0, kalan)).join(""); kalan -= [...l].length + 1; return p; });
    const c = u32(renk), cg = golge && u32(golge), ck = kontur && u32(kontur), lh = Math.round(sh * aralik), yy0 = Math.ceil(sh * 2);
    gor.forEach((l, i) => {
      if (!l) return;
      const w = Math.ceil(olc(satirlar[i], boyut, kalin)), x0 = Math.round(hiza === "orta" ? x - w / 2 : hiza === "sag" ? x - w : x), y0 = Math.round(y + i * lh + dy);
      satirCiz(l, boyut, kalin);
      const gw = Math.min(YAZI.canvas.width, w + 8), g = YAZI.getImageData(0, 0, gw, yy0).data;
      const dolu = (a, b) => a >= 0 && b >= 0 && a < gw && b < yy0 && g[(b * gw + a) * 4 + 3] > 110;
      for (let j = 0; j < yy0; j++) for (let ii = 0; ii < gw; ii++) {
        const xx = X(x0 + ii - 2), yy = Y(y0 + j - 2);
        if (dolu(ii, j)) nokta(xx, yy, c, op);
        else if (ck && (dolu(ii - 1, j) || dolu(ii + 1, j) || dolu(ii, j - 1) || dolu(ii, j + 1))) nokta(xx, yy, ck, op);
        else if (cg && dolu(ii - 1, j - 1)) nokta(xx, yy, cg, op);
      }
    });
    return { satir: satirlar.length, yukseklik: satirlar.length * lh };
  };
  /** çerçeveli kutu (piksel köşeli) */
  C.kutu = (x, y, w, h, { renk = "gece", kenar = "beyaz", golge = "kontur", op = 1 } = {}) => {
    if (golge) C.dikdortgen(x + 2, y + 2, w, h, golge, { op });
    C.dikdortgen(x + 1, y, w - 2, h, kenar, { op }); C.dikdortgen(x, y + 1, w, h - 2, kenar, { op });
    C.dikdortgen(x + 1, y + 1, w - 2, h - 2, renk, { op });
  };
  /** konuşma balonu: (x, y) kuyruğun ucu; metin üstte açılır. t0 verilirse harf harf yazılır */
  C.balon = (metin, x, y, { genislik = 120, boyut = 1, renk = "beyaz", yazi = "kontur", kuyruk = "orta", t = PX.t, t0 = null, bit = null } = {}) => {
    if (t0 != null && t < t0) return; if (bit != null && t > bit + 0.25) return;
    const s = PX.metin(metin), sat = satirlaraBol(s, boyut, false, genislik - 10), lh = Math.round(satirYuksek(boyut) * 1.3);
    const w = Math.min(genislik, Math.ceil(Math.max(...sat.map((l) => olc(l, boyut, false)))) + 11), h = sat.length * lh + 7;
    const bx = Math.round(PX.sinir(kuyruk === "sol" ? x - 8 : kuyruk === "sag" ? x - w + 8 : x - w / 2, 2 + kam.x, PX.W - w - 2 + kam.x)), by = Math.round(y - 5 - h);
    const acil = t0 == null ? 1 : PX.p(t, t0, 0.15, "cikis");
    if (acil < 1) { C.kutu(Math.round(x - (w * acil) / 2), Math.round(y - 5 - h * acil), Math.max(4, Math.round(w * acil)), Math.max(4, Math.round(h * acil)), { renk, kenar: "kontur" }); return; }
    C.kutu(bx, by, w, h, { renk, kenar: "kontur" });
    for (let j = 0; j < 5; j++) { C.dikdortgen(x - (4 - j) + (kuyruk === "sol" ? 2 : kuyruk === "sag" ? -2 : 0), by + h - 1 + j, Math.max(1, (4 - j) * 2 - 1), 1, j === 4 ? "kontur" : renk); nokta(X(x - (5 - j)), Y(by + h - 1 + j), u32("kontur")); }
    C.yazi(s, bx + 6, by + 4, { boyut, renk: yazi, golge: null, hiza: "sol", genislik: genislik - 10, aralik: 1.3, t, t0: t0 != null ? t0 + 0.15 : null, efekt: "daktilo", hiz: 40 });
  };
  /** büyük sayı ya da simge kartı (ortada kutu içinde) */
  C.etiket = (metin, x, y, { boyut = 1, renk = "kontur", arka = "sari", t = PX.t, t0 = null } = {}) => {
    if (t0 != null && t < t0) return;
    const s = PX.metin(metin), w = Math.ceil(olc(s, boyut, true)) + 10, h = satirYuksek(boyut) + 7;
    const zip = t0 != null ? Math.round(-3 * Math.max(0, Math.sin(PX.sinir((t - t0) / 0.3) * Math.PI))) : 0;
    C.kutu(Math.round(x - w / 2), y - h + zip, w, h, { renk: arka, kenar: "kontur" });
    C.yazi(s, x, y - h + 4 + zip, { boyut, renk, golge: null, kalin: true });
  };

  /* ---------------- sahne ---------------- */
  /**
   * PX.sahne({
   *   sure: 5, arka: ["#1a1b3a", "#283066"],        // ilk renk sahne geçişlerinde (devir) kullanılır
   *   genislik: 180,                               // tuval genişliği (180 → 6x, 270 → 4x büyütme); yükseklik 16:9'a göre
   *   giris: "siyah" | "beyaz" | "devir" | "iris" | "yok",  cikis: aynı + "devir": { x, y, renk, sure }
   *   kur(s) {...},  ciz(t, c) {...}
   * })
   */
  PX.sahne = (tanim) => {
    PX._sahne = tanim;
    PX.sure = Number(q.get("sure")) || tanim.sure || 5;
    const basla = async () => {
      PX.W = tanim.genislik || 180; PX.H = Math.round((PX.W * 16) / 9);
      const arka = tanim.arka ?? ["#1a1b3a", "#283066"];
      PX.arka0 = Array.isArray(arka) ? arka[0] : arka;
      document.body.style.cssText = `margin:0;height:100vh;overflow:hidden;display:grid;place-items:center;background:${renkCoz(Array.isArray(arka) ? arka[arka.length - 1] : arka)}`;
      CNV = document.createElement("canvas"); CNV.width = PX.W; CNV.height = PX.H;
      CNV.style.cssText = "image-rendering:pixelated;image-rendering:crisp-edges;height:100vh;width:auto;max-width:100vw;aspect-ratio:9/16;object-fit:contain";
      document.body.appendChild(CNV);
      CTX = CNV.getContext("2d"); IMG = CTX.createImageData(PX.W, PX.H); BUF = new Uint32Array(IMG.data.buffer);
      const yc = document.createElement("canvas"); yc.width = 1200; yc.height = 90; YAZI = yc.getContext("2d", { willReadFrequently: true });
      try { await Promise.all([document.fonts.load("400 16px Pixelify", "AĞŞİ"), document.fonts.load("700 16px Pixelify", "AĞŞİ"), document.fonts.load("10px Tiny5", "Aąç")]); await document.fonts.ready; } catch (e) {}
      const s = { c: C, W: PX.W, H: PX.H };
      tanim.kur && tanim.kur(s);
      PX._s = s;
      PX.git(0);
      window.HAZIR = true;
      if (PX.mod === "oynat") { const t0 = performance.now(); const d = () => { PX.git(((performance.now() - t0) / 1000) % PX.sure); requestAnimationFrame(d); }; requestAnimationFrame(d); }
      if (PX.mod === "gomulu") window.addEventListener("message", (e) => { if (e.data && e.data.komut === "git") PX.git(e.data.t); });
      if (window.parent !== window) window.parent.postMessage({ hazir: true, sure: PX.sure }, "*");
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", basla); else basla();
  };

  PX.git = (t) => {
    PX.t = t;
    const tn = PX._sahne;
    kam.x = kam.y = 0;
    BUF.fill(u32(Array.isArray(tn.arka) ? tn.arka[0] : tn.arka || "gece"));
    tn.ciz && tn.ciz(t, C, PX._s);
    kam.x = kam.y = 0;
    gecisler(t, tn);
    CTX.putImageData(IMG, 0, 0);
  };

  // tüm ekranı bir renkle dither deseninde örter (op 0..1)
  const ort = (renk, op) => { if (op <= 0) return; const c = u32(renk); for (let y = 0; y < PX.H; y++) for (let x = 0; x < PX.W; x++) if (op >= 1 || bayer(x, y) < op) BUF[y * PX.W + x] = c; };
  const daireOrt = (cx, cy, r, renk, disari) => {   // disari: dairenin dışını boya (iris), değilse içini
    const c = u32(renk), r2 = r * r;
    for (let y = 0; y < PX.H; y++) for (let x = 0; x < PX.W; x++) { const d = (x - cx) ** 2 + (y - cy) ** 2; if (disari ? d > r2 : d <= r2) BUF[y * PX.W + x] = c; }
  };
  function gecisler(t, tn) {
    const gr = tn.giris ?? "siyah", ck = tn.cikis ?? "siyah", R = Math.hypot(PX.W, PX.H) / 2 + 2;
    // giriş
    if (gr === "siyah" || gr === "beyaz") ort(gr === "beyaz" ? "beyaz" : "siyah", 1 - PX.sinir(t / 0.4));
    else if (gr === "devir") ort(PX.arka0, 1 - PX.e.cikis(PX.sinir(t / 0.45)));
    else if (gr === "iris" && t < 0.6) daireOrt(PX.W / 2, PX.H / 2, R * PX.e.cikis(t / 0.6), "siyah", true);
    // çıkış
    const kalan = PX.sure - t;
    if (ck === "siyah" || ck === "beyaz") ort(ck === "beyaz" ? "beyaz" : "siyah", 1 - PX.sinir(kalan / 0.4));
    else if (ck === "iris" && kalan < 0.6) daireOrt(PX.W / 2, PX.H / 2, R * PX.e.giris(PX.sinir(kalan / 0.6)), "siyah", true);
    else if (ck === "devir") {
      const d = tn.devir || {}, sure = d.sure ?? 0.9, p = PX.sinir((t - (PX.sure - sure)) / sure);
      if (p <= 0) return;
      const hedef = q.get("sonraki") ? "#" + q.get("sonraki") : d.hedef ?? PX.arka0;
      const kaynak = renkCoz(d.renk ?? "beyaz"), cx = d.x ?? PX.W / 2, cy = d.y ?? PX.H / 2;
      const Rmax = Math.hypot(Math.max(cx, PX.W - cx), Math.max(cy, PX.H - cy)) + 2, r0 = d.r ?? 6;
      const r = p < 0.2 ? r0 * (1 - 0.15 * PX.e.iki(p / 0.2)) : r0 * 0.85 * Math.pow(Rmax / (r0 * 0.85), PX.e.giris(PX.sinir((p - 0.2) / 0.75)) * 0.4 + PX.sinir((p - 0.2) / 0.75) * 0.6);
      const k = PX.e.iki(PX.sinir((p - 0.25) / 0.4));
      const c1 = u32(kaynak), c2 = u32(hedef), r2 = r * r;
      for (let y = 0; y < PX.H; y++) for (let x = 0; x < PX.W; x++) if ((x - cx) ** 2 + (y - cy) ** 2 <= r2) BUF[y * PX.W + x] = bayer(x, y) < k ? c2 : c1;
    }
  }
})();
