/* =====================================================================
   Vektör Animasyon Kütüphanesi (V)
   Her sahne: V.sahne({ sure, arka, kur(s), ciz(t) })
   - kur(s): SVG öğelerini bir kez oluşturur
   - ciz(t): t saniyesindeki görünümü ayarlar (saf fonksiyon -> ileri/geri sarılabilir)
   Mod: ?mod=kayit (video kaydı), ?mod=gomulu (stüdyo önizlemesi), yoksa kendi kendine oynar.
   Tasarım alanı her zaman 1080 x 1920 (dikey).
   ===================================================================== */
(function () {
  const q = new URLSearchParams(location.search);
  // Rastgelelik sabit tohumlu: sahne her açılışta aynı görünür (önizleme = video; video parçalar hâlinde paralel çizilebilir).
  { let r = 20261109; Math.random = () => ((r = (Math.imul(r, 1664525) + 1013904223) >>> 0) / 4294967296); }
  const NS = "http://www.w3.org/2000/svg";
  const V = (window.V = {
    dil: q.get("dil") || "tr",
    mod: q.get("mod") || "oynat",
    W: 1080, H: 1920, sure: 5, t: 0,
    svg: null, defs: null, kamera: null, katman: null,
    _id: 0, _sahne: null, _guncel: [], _bekle: [], uyarilar: [],
  });
  window.UYARILAR = V.uyarilar;
  V.uyar = (m) => { if (!V.uyarilar.includes(m)) { V.uyarilar.push(m); console.warn("[vektor] " + m); } };

  /* ---------------- temel ---------------- */
  V.el = (tag, a = {}, ebeveyn) => {
    const e = document.createElementNS(NS, tag);
    for (const k in a) if (a[k] !== undefined && a[k] !== null) e.setAttribute(k, a[k]);
    if (ebeveyn) ebeveyn.appendChild(e);
    return e;
  };
  V.g = (ebeveyn, a = {}) => V.el("g", a, ebeveyn);
  V.id = (on = "v") => on + ++V._id;
  // Çok dilli yazı: { tr: "...", en: "..." }. Senaryoda olmayan dil projenin ceviri.json'ından (stüdyonun 🌐 Çevir'i) gelir.
  V._ceviri = undefined;
  V.ceviriler = () => {
    if (V._ceviri !== undefined) return V._ceviri;
    V._ceviri = null;
    try {
      const m = location.pathname.match(/^(.*\/projeler\/[^/]+\/)/);
      if (m) {
        const x = new XMLHttpRequest();
        x.open("GET", m[1] + "ceviri.json?v=" + Date.now(), false); x.send();
        if (x.status === 200) V._ceviri = JSON.parse(x.responseText);
      }
    } catch (e) { /* çeviri yoksa sorun değil */ }
    return V._ceviri;
  };
  V.metin = (v) => {
    if (!v || typeof v !== "object") return v ?? "";
    if (v[V.dil] != null) return v[V.dil];
    const e = (((V.ceviriler() || {}).diller || {})[V.dil] || {}).ekran || {};
    for (const k in v) if (e[v[k]]) return e[v[k]];
    return v.en ?? Object.values(v)[0];
  };
  V.sinir = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  V.ara = (a, b, p) => a + (b - a) * p;
  V.e = {
    lin: (x) => x,
    cikis: (x) => 1 - Math.pow(1 - x, 3),
    giris: (x) => x * x * x,
    iki: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    zipla: (x) => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
    elastik: (x) => (x === 0 || x === 1 ? x : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * (2 * Math.PI) / 3) + 1),
  };
  /** t0'dan başlayıp d saniye süren ilerleme (0..1), yumuşatılmış */
  V.p = (t, t0, d = 0.6, e = "cikis") => { const x = V.sinir((t - t0) / d); return V.e[e](x); };
  /** anahtar kareler: [[t, v], ...] veya [[t, [a,b]], ...] */
  V.kf = (t, kare, e = "iki") => {
    if (t <= kare[0][0]) return kare[0][1];
    for (let i = 0; i < kare.length - 1; i++) {
      const [t0, a] = kare[i], [t1, b] = kare[i + 1];
      if (t <= t1) {
        const p = V.e[e](V.sinir((t - t0) / (t1 - t0 || 1)));
        return Array.isArray(a) ? a.map((v, j) => V.ara(v, b[j], p)) : V.ara(a, b, p);
      }
    }
    return kare[kare.length - 1][1];
  };

  /* ---------------- dönüşüm ve görünürlük ---------------- */
  V.tf = (el, { x = 0, y = 0, s = 1, sx, sy, r = 0 } = {}) => {
    el.setAttribute("transform", `translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${r.toFixed(2)}) scale(${(sx ?? s).toFixed(4)} ${(sy ?? s).toFixed(4)})`);
  };
  V.op = (el, o) => el.setAttribute("opacity", V.sinir(o).toFixed(3));

  /**
   * Bir öğeyi t anına göre yerleştirir. Seçenekler:
   *  x,y,s,r  | bas (giriş zamanı), giris: zipla|solma|yukari|asagi|sol|sag|buyu|yok, gs (giriş süresi)
   *  bit (çıkış zamanı), cikis: kucul|solma|yukari|asagi|sol|sag, cs
   *  bekle: "nefes salla zipla suz nabiz don titre"  (canlılık), faz
   */
  V.yer = (el, t, o = {}) => {
    let { x = 0, y = 0, s = 1, r = 0 } = o;
    let sx = 1, sy = 1, op = o.op ?? 1;
    const bas = o.bas ?? 0, gs = o.gs ?? 0.55, faz = o.faz ?? 0;
    if (t < bas) { V.op(el, 0); return; }
    const gp = V.sinir((t - bas) / gs);
    switch (o.giris ?? "zipla") {
      case "zipla": s *= Math.max(0, V.e.zipla(gp)); op *= V.sinir(gp * 4); break;
      case "solma": op *= V.e.cikis(gp); break;
      case "buyu": s *= V.e.cikis(gp); break;
      case "yukari": y += (1 - V.e.cikis(gp)) * 80; op *= V.e.cikis(gp); break;
      case "asagi": y -= (1 - V.e.cikis(gp)) * 80; op *= V.e.cikis(gp); break;
      case "sol": x -= (1 - V.e.cikis(gp)) * 900; break;
      case "sag": x += (1 - V.e.cikis(gp)) * 900; break;
    }
    if (o.bit !== undefined && t >= o.bit) {
      const cp = V.sinir((t - o.bit) / (o.cs ?? 0.4));
      if (cp >= 1) { V.op(el, 0); return; }
      switch (o.cikis ?? "solma") {
        case "kucul": s *= 1 - V.e.iki(cp); break;
        case "solma": op *= 1 - cp; break;
        case "yukari": y -= V.e.giris(cp) * 300; op *= 1 - cp; break;
        case "asagi": y += V.e.giris(cp) * 300; op *= 1 - cp; break;
        case "sol": x -= V.e.giris(cp) * 1200; break;
        case "sag": x += V.e.giris(cp) * 1200; break;
      }
    }
    for (const b of (o.bekle || "").split(" ")) {
      if (b === "nefes") { const k = Math.sin(t * 2.6 + faz); sy *= 1 + 0.025 * k; sx *= 1 - 0.012 * k; }
      else if (b === "salla") r += (o.aci ?? 4) * Math.sin(t * 2 + faz);
      else if (b === "zipla") y -= 18 * Math.abs(Math.sin(t * 4 + faz));
      else if (b === "suz") { y += 10 * Math.sin(t * 1.3 + faz); x += 6 * Math.cos(t * 1.1 + faz); }
      else if (b === "nabiz") { const k = 1 + (o.nabiz ?? 0.08) * Math.sin(t * 6 + faz); sx *= k; sy *= k; }
      else if (b === "don") r += t * (o.hiz ?? 90);
      else if (b === "titre") { x += 3 * Math.sin(t * 57 + faz); y += 3 * Math.cos(t * 49 + faz); }
    }
    el.setAttribute("transform", `translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${r.toFixed(2)}) scale(${(s * sx).toFixed(4)} ${(s * sy).toFixed(4)})`);
    V.op(el, op);
  };

  /* ---------------- tanımlar: gradyan, filtre ---------------- */
  V.gradyan = (renkler, { yon = [0, 0, 0, 1], radyal = false } = {}) => {
    const id = V.id("g");
    const gr = V.el(radyal ? "radialGradient" : "linearGradient", radyal ? { id } : { id, x1: yon[0], y1: yon[1], x2: yon[2], y2: yon[3] }, V.defs);
    renkler.forEach((c, i) => {
      const [renk, ofs, op] = Array.isArray(c) ? c : [c, i / Math.max(1, renkler.length - 1), 1];
      V.el("stop", { offset: ofs, "stop-color": renk, "stop-opacity": op }, gr);
    });
    return `url(#${id})`;
  };
  V.filtre = {};
  function filtreler() {
    let f = V.el("filter", { id: "parilti", x: "-50%", y: "-50%", width: "200%", height: "200%" }, V.defs);
    V.el("feGaussianBlur", { stdDeviation: 14, result: "b" }, f);
    let m = V.el("feMerge", {}, f); V.el("feMergeNode", { in: "b" }, m); V.el("feMergeNode", { in: "SourceGraphic" }, m);
    f = V.el("filter", { id: "golge", x: "-30%", y: "-30%", width: "160%", height: "160%" }, V.defs);
    V.el("feDropShadow", { dx: 0, dy: 14, stdDeviation: 16, "flood-color": "#000", "flood-opacity": 0.35 }, f);
    f = V.el("filter", { id: "bulanik", x: "-50%", y: "-50%", width: "200%", height: "200%" }, V.defs);
    V.el("feGaussianBlur", { stdDeviation: 30 }, f);
    V.filtre = { parilti: "url(#parilti)", golge: "url(#golge)", bulanik: "url(#bulanik)" };
  }

  /* ---------------- kamera ---------------- */
  /** kare: [[t, [zoom, merkezX, merkezY]], ...]  merkez 0-1 oran */
  V.kameraAyarla = (t, kare) => {
    if (!kare._kontrol) {
      kare._kontrol = 1;
      let yon = 0;
      for (let i = 1; i < kare.length; i++) {
        const d = Math.sign(kare[i][1][0] - kare[i - 1][1][0]);
        if (d && yon && d !== yon) V.uyar("Kamera yön değiştiriyor (yaklaşıp sonra uzaklaşıyor ya da tersi). Tek yönlü, sürekli bir hareket daha akıcı görünür.");
        if (d) yon = d;
      }
    }
    const [z, mx, my] = V.kf(t, kare);
    V.kamera.setAttribute("transform", `translate(${V.W / 2} ${V.H / 2}) scale(${z}) translate(${-mx * V.W} ${-my * V.H})`);
  };

  /**
   * Tek, sürekli kamera itmesi: başta hızlı, sonra uzun süre yavaş (üstel yavaşlama). Yön hiç değişmez.
   * V.itme(t, {yakin: 1.08, mx: 0.5, my: 0.5, hedefX, hedefY, hiz: 3, sure})  mx/my başlangıç merkezi, hedefX/Y bitiş merkezi (0-1)
   */
  V.itme = (t, o = {}) => {
    const sure = o.sure ?? V.sure, hiz = o.hiz ?? 3;
    const p = (1 - Math.exp(-hiz * V.sinir(t / sure))) / (1 - Math.exp(-hiz));
    const z = V.ara(o.uzak ?? 1, o.yakin ?? 1.08, p);
    const mx = V.ara(o.mx ?? 0.5, o.hedefX ?? o.mx ?? 0.5, p), my = V.ara(o.my ?? 0.5, o.hedefY ?? o.my ?? 0.5, p);
    V.kamera.setAttribute("transform", `translate(${V.W / 2} ${V.H / 2}) scale(${z.toFixed(5)}) translate(${(-mx * V.W).toFixed(2)} ${(-my * V.H).toFixed(2)})`);
  };

  /* ---------------- yazı ---------------- */
  /**
   * V.yazi(ebeveyn, {metin, x, y, boyut, renk, agirlik, hiza, genislik, satir, golge, kutu})
   * Döndürür: {g, kelimeler:[tspan...], anim(t, t0, tur)}
   */
  V.yazi = (ebeveyn, o) => {
    const g = V.g(ebeveyn);
    const boyut = o.boyut ?? 64, satir = (o.satir ?? 1.18) * boyut;
    const hiza = o.hiza ?? "orta";
    const anchor = { orta: "middle", sol: "start", sag: "end" }[hiza];
    const yazi = String(V.metin(o.metin));
    const agirlik = o.agirlik ?? 800, renk = o.renk ?? "#fff";
    const olc = V.el("text", { "font-size": boyut, "font-weight": agirlik, "font-family": "Nunito, sans-serif" }, g);
    const genislik = o.genislik ?? 900;
    const satirlar = [];
    for (const par of yazi.split("\n")) {
      let cur = "";
      for (const w of par.split(" ")) {
        const dene = cur ? cur + " " + w : w;
        olc.textContent = dene;
        if (olc.getComputedTextLength() > genislik && cur) { satirlar.push(cur); cur = w; } else cur = dene;
      }
      satirlar.push(cur);
    }
    olc.remove();
    const y0 = (o.y ?? 0) - ((satirlar.length - 1) * satir) / 2;
    const kelimeler = [];
    if (o.kutu) {
      const pad = boyut * 0.5;
      const tmp = V.el("text", { "font-size": boyut, "font-weight": agirlik, "font-family": "Nunito, sans-serif" }, g);
      let maxw = 0; for (const s of satirlar) { tmp.textContent = s; maxw = Math.max(maxw, tmp.getComputedTextLength()); } tmp.remove();
      const x0 = hiza === "orta" ? (o.x ?? 0) - maxw / 2 : hiza === "sol" ? o.x ?? 0 : (o.x ?? 0) - maxw;
      V.el("rect", { x: x0 - pad, y: y0 - boyut * 0.95 - pad * 0.3, width: maxw + pad * 2, height: satirlar.length * satir + pad * 0.6,
        rx: Math.min(40, boyut * 0.6), fill: o.kutu, opacity: o.kutuOp ?? 0.85 }, g);
    }
    // degrade: harflerin üst yarısı düz, alt yarısı hafifçe koyulaşır (sadece koyu arka planlarda)
    const dolgu = o.degrade ? V.gradyan([[renk, 0, 1], [renk, 0.5, 1], [o.degradeRenk ?? shade(renk, -30), 1, 1]]) : renk;
    satirlar.forEach((s, i) => {
      if (!s) return;
      const yy = y0 + i * satir;
      const sg = V.g(g, { filter: o.golge === false ? null : "url(#golge)" });
      // önce satırı bütün yerleştir, kelimelerin x konumlarını ölç, sonra her kelimeyi ayrı öğe yap
      const te = V.el("text", { x: o.x ?? 0, y: yy, "text-anchor": anchor, "font-size": boyut, "font-weight": agirlik, "font-family": "Nunito, sans-serif" }, sg);
      te.textContent = s;
      const kel = s.split(" "); let idx = 0;
      const xs = kel.map((w) => { const px = te.getStartPositionOfChar(Math.min(idx, s.length - 1)).x; idx += w.length + 1; return px; });
      te.remove();
      kel.forEach((w, j) => {
        const wt = V.el("text", { x: xs[j].toFixed(2), y: yy, "font-size": boyut, "font-weight": agirlik,
          "font-family": "Nunito, sans-serif", fill: dolgu }, sg);
        wt.textContent = w;
        kelimeler.push(wt);
      });
    });
    const nesne = { g, kelimeler };
    const bulaniklik = (k, b) => {
      if (b < 0.05) { k.removeAttribute("filter"); return; }
      if (!k._f) {
        const id = V.id("kb");
        const f = V.el("filter", { id, x: "-40%", y: "-80%", width: "180%", height: "260%" }, V.defs);
        k._f = V.el("feGaussianBlur", { stdDeviation: 0 }, f); k._fid = `url(#${id})`;
      }
      k._f.setAttribute("stdDeviation", b.toFixed(2)); k.setAttribute("filter", k._fid);
    };
    /** tur: bulanik (önerilen) | kelime | zipla | yukari | solma | yazma ; bit: kaybolma zamanı */
    nesne.anim = (t, t0 = 0, tur = "bulanik", bit) => {
      let son = 1;
      if (bit !== undefined) son = 1 - V.sinir((t - bit) / 0.35);
      if (tur === "bulanik") {
        V.op(g, 1); g.removeAttribute("transform");
        const ara = o.aralik ?? 0.075;
        kelimeler.forEach((k, i) => {
          const e = V.e.cikis(V.sinir((t - t0 - i * ara) / 0.55));
          let op = e, b = (1 - e) * 11, dy = (1 - e) * 24;
          if (bit !== undefined) {
            const c = V.e.giris(V.sinir((t - bit - i * ara * 0.6) / 0.4));
            op *= 1 - c; b = Math.max(b, c * 11); dy -= c * 20;
          }
          k.setAttribute("opacity", op.toFixed(3));
          k.setAttribute("transform", `translate(0 ${dy.toFixed(2)})`);
          bulaniklik(k, op < 0.01 ? 0 : b);
        });
      } else if (tur === "kelime") {
        V.op(g, son); g.removeAttribute("transform");
        kelimeler.forEach((k, i) => {
          const p = V.p(t, t0 + i * 0.085, 0.35);
          k.setAttribute("opacity", p.toFixed(3));
        });
      } else if (tur === "zipla") {
        const p = V.sinir((t - t0) / 0.5);
        const cx = o.x ?? 0, cy = o.y ?? 0, s = Math.max(0, V.e.zipla(p));
        g.setAttribute("transform", `translate(${cx} ${cy}) scale(${s}) translate(${-cx} ${-cy})`);
        V.op(g, V.sinir(p * 4) * son);
      } else if (tur === "yukari" || tur === "solma") {
        const p = V.p(t, t0, 0.6);
        g.setAttribute("transform", tur === "yukari" ? `translate(0 ${(1 - p) * 50})` : "");
        V.op(g, p * son);
      } else if (tur === "yazma") {
        V.op(g, son);
        let kalan = Math.floor((t - t0) * 32);
        kelimeler.forEach((k) => { k.setAttribute("opacity", kalan > 0 ? 1 : 0); kalan -= k.textContent.length + 1; });
      }
    };
    return nesne;
  };

  /** sayaç: yazı öğesine a'dan b'ye sayan değer yazar. bicim: v => metin */
  V.sayac = (el, t, t0, d, a, b, bicim = (v) => Math.round(v)) => {
    const v = V.ara(a, b, V.p(t, t0, d, "iki"));
    el.textContent = bicim(v);
  };

  /** yol çizme (kendini çizen çizgi) */
  V.cizgi = (yol, p) => {
    if (!yol._uz) { yol.setAttribute("pathLength", 1); yol.setAttribute("stroke-dasharray", "1 1"); yol._uz = 1; }
    yol.setAttribute("stroke-dashoffset", (1 - V.sinir(p)).toFixed(4));
  };

  /* ---------------- hazır parçalar ---------------- */
  /** gece gökyüzü yıldızları; ciz'de V.yildizlar.guncelle(t) çağrılır */
  V.yildizlar = (ebeveyn, n = 90, yukseklik = 1100, tohum = 3) => {
    let s = tohum; const r = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
    const g = V.g(ebeveyn); const liste = [];
    for (let i = 0; i < n; i++) {
      const c = V.el("circle", { cx: r() * V.W, cy: r() * yukseklik, r: 1.5 + r() * 3, fill: "#fff" }, g);
      liste.push([c, r() * 6.28, 0.6 + r() * 1.6]);
    }
    return { g, guncelle: (t) => liste.forEach(([c, f, h]) => c.setAttribute("opacity", (0.35 + 0.45 * Math.sin(t * h + f)).toFixed(3))) };
  };

  /** süzülen ışık zerreleri */
  V.zerreler = (ebeveyn, n = 40, renk = "#ffe9c4", tohum = 7) => {
    let s = tohum; const r = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
    const g = V.g(ebeveyn); const liste = [];
    for (let i = 0; i < n; i++) liste.push([V.el("circle", { r: 2 + r() * 5, fill: renk }, g), r() * V.W, r() * V.H, 0.3 + r(), r() * 6.28]);
    return { g, guncelle: (t) => liste.forEach(([c, x, y, v, f]) => {
      c.setAttribute("cx", ((x + t * 14 * v) % V.W).toFixed(1));
      c.setAttribute("cy", (((y - t * 22 * v) % V.H + V.H) % V.H).toFixed(1));
      c.setAttribute("opacity", (0.25 + 0.35 * Math.sin(t * 1.7 * v + f)).toFixed(3));
    }) };
  };

  /**
   * Sevimli insan figürü. Merkez: ayak tabanı ortası (0,0). Yükseklik ~ 520 * olcek.
   * o: {gomlek, ten, sac, sacTip: "kisa|uzun|topuz|kel", ifade: "mutlu|uzgun|notr|saskin", telefon, kollar: "yan|yukari|kavus", pantolon}
   * Döndürür {g, guncelle(t)} -> göz kırpma ve telefon ışığı.
   */
  V.kisi = (ebeveyn, o = {}) => {
    const ten = o.ten ?? "#f6c49a", gom = o.gomlek ?? "#3ec7c0", pan = o.pantolon ?? "#3b4a85", sac = o.sac ?? "#3a2a24";
    const g = V.g(ebeveyn);
    const tenG = V.gradyan([ten, shade(ten, -18)], { yon: [0, 0, 0.6, 1] });
    const gomG = V.gradyan([shade(gom, 18), shade(gom, -22)], { yon: [0, 0, 0.5, 1] });
    const panG = V.gradyan([shade(pan, 12), shade(pan, -25)]);
    // gölge
    V.el("ellipse", { cx: 0, cy: 6, rx: 120, ry: 22, fill: "#000", opacity: 0.22 }, g);
    // bacaklar
    for (const sx of [-1, 1]) {
      V.el("rect", { x: sx * 38 - 32, y: -230, width: 64, height: 228, rx: 30, fill: panG }, g);
      V.el("ellipse", { cx: sx * 44, cy: -6, rx: 48, ry: 22, fill: "#2b2b38" }, g);
    }
    // kollar (arkada kalan)
    const kollar = V.g(g);
    const kolTip = o.kollar ?? "yan";
    const kolYol = {}, kolEl = {};
    for (const sx of [-1, 1]) {
      let d;
      if (kolTip === "yukari") d = `M ${sx * 70} -390 Q ${sx * 150} -470 ${sx * 120} -560`;
      else if (kolTip === "kavus") d = `M ${sx * 70} -390 Q ${sx * 30} -320 ${-sx * 30} -330`;
      else if (o.telefon) d = sx < 0 ? `M -70 -390 Q -110 -300 -40 -300` : `M 70 -390 Q 110 -300 40 -300`;
      else d = `M ${sx * 72} -390 Q ${sx * 110} -320 ${sx * 98} -250`;
      kolYol[sx] = V.el("path", { d, stroke: gomG, "stroke-width": 52, "stroke-linecap": "round", "stroke-linejoin": "round", fill: "none" }, kollar);
      const uc = d.split(" ").slice(-2).map(Number);
      kolEl[sx] = V.el("circle", { cx: uc[0], cy: uc[1], r: 27, fill: tenG }, kollar);
    }
    // gövde
    V.el("rect", { x: -88, y: -430, width: 176, height: 230, rx: 70, fill: gomG }, g);
    V.el("rect", { x: -70, y: -418, width: 60, height: 160, rx: 30, fill: "#fff", opacity: 0.12 }, g);
    // kollar öne (telefon tutuyorsa telefon da)
    g.appendChild(kollar);
    let ekranIsik = null;
    if (o.telefon) {
      V.el("rect", { x: -34, y: -362, width: 68, height: 110, rx: 12, fill: "#22263a" }, g);
      ekranIsik = V.el("rect", { x: -28, y: -356, width: 56, height: 98, rx: 8, fill: "#8fe3ff" }, g);
    }
    // boyun + baş
    V.el("rect", { x: -24, y: -470, width: 48, height: 60, rx: 20, fill: tenG }, g);
    const bas = V.g(g, { transform: "translate(0 -560)" });
    const sacTip = o.sacTip ?? "kisa";
    if (sacTip === "uzun") V.el("path", { d: "M -112 0 Q -120 150 -60 150 L 60 150 Q 120 150 112 0 Z", fill: sac }, bas);
    V.el("circle", { cx: 0, cy: 0, r: 110, fill: tenG }, bas);
    V.el("ellipse", { cx: -40, cy: -45, rx: 40, ry: 25, fill: "#fff", opacity: 0.18 }, bas);
    if (sacTip !== "kel") {
      V.el("path", { d: "M -112 10 Q -118 -118 0 -122 Q 118 -118 112 10 Q 90 -50 40 -58 Q -20 -40 -70 -62 Q -100 -40 -112 10 Z", fill: sac }, bas);
      if (sacTip === "topuz") V.el("circle", { cx: 0, cy: -128, r: 42, fill: sac }, bas);
    }
    // yüz
    const ifade = o.ifade ?? "mutlu";
    const bak = o.telefon ? [0, 0.45] : [0.05, 0.1];
    const gozler = [], kapali = [];
    for (const sx of [-1, 1]) {
      const ag = V.g(bas);
      V.el("ellipse", { cx: sx * 40, cy: 8, rx: 22, ry: 25, fill: "#fff" }, ag);
      V.el("circle", { cx: sx * 40 + bak[0] * 12, cy: 10 + bak[1] * 12, r: 13, fill: "#1e1a28" }, ag);
      V.el("circle", { cx: sx * 40 + bak[0] * 12 - 4, cy: 5 + bak[1] * 12, r: 4.5, fill: "#fff" }, ag);
      gozler.push(ag);
      const kg = V.el("path", { d: `M ${sx * 40 - 20} 10 Q ${sx * 40} 22 ${sx * 40 + 20} 10`, stroke: "#1e1a28", "stroke-width": 6, fill: "none", "stroke-linecap": "round", opacity: 0 }, bas);
      kapali.push(kg);
      if (ifade === "uzgun") V.el("path", { d: `M ${sx * 40 - 22} ${-30 + (sx < 0 ? 8 : -2)} L ${sx * 40 + 22} ${-30 + (sx < 0 ? -2 : 8)}`, stroke: sac, "stroke-width": 7, "stroke-linecap": "round" }, bas);
    }
    V.el("ellipse", { cx: -66, cy: 45, rx: 18, ry: 10, fill: "#ff8a8a", opacity: 0.4 }, bas);
    V.el("ellipse", { cx: 66, cy: 45, rx: 18, ry: 10, fill: "#ff8a8a", opacity: 0.4 }, bas);
    const agiz = {
      mutlu: "M -30 50 Q 0 82 30 50", uzgun: "M -26 70 Q 0 50 26 70", notr: "M -20 60 L 20 60", saskin: "M -10 60 a 10 12 0 1 0 20 0 a 10 12 0 1 0 -20 0",
    }[ifade];
    V.el("path", { d: agiz, stroke: "#5a2b2b", "stroke-width": 7, fill: ifade === "saskin" ? "#5a2b2b" : "none", "stroke-linecap": "round" }, bas);
    const faz = o.faz ?? Math.random() * 3;
    if (ekranIsik) {   // ekranın yüze yansıması
      V.el("circle", { cx: 0, cy: 30, r: 115, fill: "#8fe3ff", opacity: 0.16 }, bas);
    }
    return {
      g, bas,
      /**
       * Eklemli kol: taraf "sag" | "sol"; omuz: kolun aşağıdan dışarı doğru açısı (0 = aşağı sarkık, 90 = yana, 170 = yukarı),
       * dirsek: ön kolun üst kola göre ek açısı (0 = düz). Parçalar sert döner, hiçbir şey esnemez.
       */
      kol(taraf, omuz = 0, dirsek = 0) {
        const sx = taraf === "sol" ? -1 : 1;
        const S = [sx * 72, -390], a = (omuz * Math.PI) / 180, b = ((omuz + dirsek) * Math.PI) / 180;
        const E = [S[0] + sx * Math.sin(a) * 92, S[1] + Math.cos(a) * 92];
        const H = [E[0] + sx * Math.sin(b) * 88, E[1] + Math.cos(b) * 88];
        kolYol[sx].setAttribute("d", `M ${S[0]} ${S[1]} L ${E[0].toFixed(1)} ${E[1].toFixed(1)} L ${H[0].toFixed(1)} ${H[1].toFixed(1)}`);
        kolEl[sx].setAttribute("cx", H[0].toFixed(1)); kolEl[sx].setAttribute("cy", H[1].toFixed(1));
      },
      /** başı boyun etrafında eğer (derece) */
      basEg(aci = 0) { bas.setAttribute("transform", `translate(0 -470) rotate(${aci.toFixed(2)}) translate(0 -90)`); },
      guncelle(t) {
        const kirp = ((t + faz) % 3.3) < 0.12;
        gozler.forEach((e) => e.setAttribute("opacity", kirp ? 0 : 1));
        kapali.forEach((e) => e.setAttribute("opacity", kirp ? 1 : 0));
        if (ekranIsik) ekranIsik.setAttribute("opacity", (0.8 + 0.2 * Math.sin(t * 5 + faz)).toFixed(2));
      },
    };
  };

  /** apartman: {g, pencereler:[{rect, satir, sutun}], genislik, yukseklik}; merkez alt-orta (0,0) */
  V.bina = (ebeveyn, { kat = 8, sutun = 4, renk = "#2a3566", pg = 70, ph = 90, ara = 34 } = {}) => {
    const g = V.g(ebeveyn);
    const W = sutun * pg + (sutun + 1) * ara, H = kat * ph + (kat + 1) * ara + 40;
    V.el("rect", { x: -W / 2, y: -H, width: W, height: H, rx: 10, fill: V.gradyan([shade(renk, 10), shade(renk, -20)]) }, g);
    V.el("rect", { x: -W / 2 - 12, y: -H - 18, width: W + 24, height: 26, rx: 8, fill: shade(renk, -12) }, g);
    const pencereler = [];
    for (let i = 0; i < kat; i++) for (let j = 0; j < sutun; j++) {
      const x = -W / 2 + ara + j * (pg + ara), y = -H + 40 + ara + i * (ph + ara);
      V.el("rect", { x, y, width: pg, height: ph, rx: 6, fill: "#151b38" }, g);
      const isik = V.el("rect", { x, y, width: pg, height: ph, rx: 6, fill: "#ffd77a", opacity: 0 }, g);
      pencereler.push({ rect: isik, satir: i, sutun: j, x: x + pg / 2, y: y + ph / 2 });
    }
    return { g, pencereler, genislik: W, yukseklik: H };
  };

  /** analog saat; guncelle(t, hiz) */
  V.saat = (ebeveyn, r = 120) => {
    const g = V.g(ebeveyn);
    V.el("circle", { r: r + 16, fill: V.gradyan(["#ffd166", "#f08a24"]), filter: "url(#golge)" }, g);
    V.el("circle", { r, fill: V.gradyan(["#ffffff", "#e3e8f5"]) }, g);
    for (let k = 0; k < 12; k++) {
      const a = (k / 12) * Math.PI * 2;
      V.el("line", { x1: Math.cos(a) * r * 0.8, y1: Math.sin(a) * r * 0.8, x2: Math.cos(a) * r * 0.92, y2: Math.sin(a) * r * 0.92, stroke: "#3a4366", "stroke-width": 7, "stroke-linecap": "round" }, g);
    }
    const akrep = V.el("line", { x1: 0, y1: 0, x2: 0, y2: -r * 0.45, stroke: "#2b3150", "stroke-width": 12, "stroke-linecap": "round" }, g);
    const yel = V.el("line", { x1: 0, y1: 0, x2: 0, y2: -r * 0.72, stroke: "#e84b5a", "stroke-width": 8, "stroke-linecap": "round" }, g);
    V.el("circle", { r: 10, fill: "#2b3150" }, g);
    return { g, guncelle: (t, hiz = 1) => { yel.setAttribute("transform", `rotate(${t * 360 * hiz})`); akrep.setAttribute("transform", `rotate(${t * 30 * hiz})`); } };
  };

  /** yuvarlak çubuk: büyüyen çubuk grafik. dikey; alt-sol (x,y) */
  V.cubuk = (ebeveyn, { x, y, genislik = 140, yukseklik = 500, renk = "#ff6b8b" }) => {
    const g = V.g(ebeveyn);
    V.el("rect", { x, y: y - yukseklik, width: genislik, height: yukseklik, rx: 22, fill: "#ffffff", opacity: 0.06 }, g);
    const c = V.el("rect", { x, y, width: genislik, height: 0, rx: 22, fill: V.gradyan([shade(renk, 15), shade(renk, -20)]) }, g);
    return { g, ayarla: (p) => { const h = Math.max(0.01, p) * yukseklik; c.setAttribute("y", y - h); c.setAttribute("height", h); } };
  };

  /* ---------------- renk yardımcısı ---------------- */
  function shade(hex, yuzde) {
    const n = parseInt(hex.slice(1), 16);
    let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    const f = yuzde / 100;
    const k = (c) => Math.round(f > 0 ? c + (255 - c) * f : c * (1 + f));
    return "#" + [k(r), k(g), k(b)].map((v) => v.toString(16).padStart(2, "0")).join("");
  }
  V.ton = shade;

  /** hap şeklinde etiket (origin merkezde). V.yer ile konumlandırılır. */
  V.etiket = (ebeveyn, { metin, boyut = 40, renk = "#fff", arka = "#ffffff", arkaOp = 0.14, kenar = null, agirlik = 800 } = {}) => {
    const g = V.g(ebeveyn);
    const te = V.el("text", { x: 0, y: boyut * 0.35, "text-anchor": "middle", "font-size": boyut, "font-weight": agirlik,
      "font-family": "Nunito, sans-serif", fill: renk }, g);
    te.textContent = V.metin(metin);
    const w = te.getComputedTextLength() + boyut * 1.4, h = boyut * 1.7;
    const r = V.el("rect", { x: -w / 2, y: -h / 2, width: w, height: h, rx: h / 2, fill: arka, opacity: arkaOp,
      stroke: kenar, "stroke-width": kenar ? 4 : null }, g);
    g.insertBefore(r, te);
    return g;
  };

  /** büyük sayı: {g, yaz(metin)} origin merkezde */
  V.buyukSayi = (ebeveyn, { boyut = 220, renk = "#fff" } = {}) => {
    const g = V.g(ebeveyn);
    const te = V.el("text", { x: 0, y: boyut * 0.35, "text-anchor": "middle", "font-size": boyut, "font-weight": 900,
      "font-family": "Nunito, sans-serif", fill: renk, filter: "url(#golge)" }, g);
    return { g, yaz: (m) => { te.textContent = m; } };
  };

  /* ---------------- ikonlar, halka, çizgi grafik ---------------- */
  const IKONLAR = {
    kalp: (g, c) => V.el("path", { d: "M0 36 C-42 8 -46 -22 -25 -33 C-11 -40 0 -29 0 -20 C0 -29 11 -40 25 -33 C46 -22 42 8 0 36Z", fill: c }, g),
    yildiz: (g, c) => { let d = ""; for (let i = 0; i < 10; i++) { const r = i % 2 ? 19 : 44, a = -Math.PI / 2 + i * Math.PI / 5; d += (i ? "L" : "M") + (r * Math.cos(a)).toFixed(1) + " " + (r * Math.sin(a)).toFixed(1); }
      V.el("path", { d: d + "Z", fill: c, stroke: c, "stroke-width": 6, "stroke-linejoin": "round" }, g); },
    ev: (g, c, k) => { V.el("path", { d: "M-46 -2 L0 -42 L46 -2Z", fill: c, stroke: c, "stroke-width": 8, "stroke-linejoin": "round" }, g);
      V.el("rect", { x: -32, y: -6, width: 64, height: 46, rx: 7, fill: c }, g); V.el("rect", { x: -9, y: 12, width: 18, height: 28, rx: 4, fill: k }, g); },
    insan: (g, c) => { V.el("circle", { cx: 0, cy: -25, r: 16, fill: c }, g); V.el("path", { d: "M-30 42 C-30 8 -16 -3 0 -3 C16 -3 30 8 30 42Z", fill: c }, g); },
    para: (g, c, k) => { V.el("circle", { r: 42, fill: c }, g); V.el("circle", { r: 29, fill: "none", stroke: k, "stroke-width": 5, opacity: 0.55 }, g);
      V.el("path", { d: "M10 -12 C2 -20 -12 -16 -11 -7 C-10 4 11 -2 11 9 C11 18 -4 20 -12 12 M0 -22 V22", fill: "none", stroke: k, "stroke-width": 6, "stroke-linecap": "round" }, g); },
    saat: (g, c) => { V.el("circle", { r: 38, fill: "none", stroke: c, "stroke-width": 9 }, g);
      V.el("path", { d: "M0 -20 V0 L15 10", fill: "none", stroke: c, "stroke-width": 8, "stroke-linecap": "round", "stroke-linejoin": "round" }, g); },
    telefon: (g, c, k) => { V.el("rect", { x: -25, y: -44, width: 50, height: 88, rx: 11, fill: c }, g); V.el("rect", { x: -18, y: -33, width: 36, height: 58, rx: 4, fill: k }, g); V.el("circle", { cx: 0, cy: 34, r: 4, fill: k }, g); },
    dunya: (g, c) => { const o = { fill: "none", stroke: c, "stroke-width": 7 }; V.el("circle", { r: 39, ...o }, g); V.el("ellipse", { rx: 17, ry: 39, ...o }, g);
      V.el("path", { d: "M-39 0 H39 M-33 -20 Q0 -10 33 -20 M-33 20 Q0 10 33 20", ...o, "stroke-width": 6 }, g); },
    ampul: (g, c, k) => { V.el("path", { d: "M-12 18 C-12 6 -28 0 -28 -16 A28 28 0 0 1 28 -16 C28 0 12 6 12 18Z", fill: c }, g);
      V.el("rect", { x: -12, y: 23, width: 24, height: 8, rx: 4, fill: c }, g); V.el("rect", { x: -8, y: 35, width: 16, height: 7, rx: 3.5, fill: c }, g);
      V.el("path", { d: "M-8 -12 L0 -2 L8 -12", fill: "none", stroke: k, "stroke-width": 5, "stroke-linecap": "round", "stroke-linejoin": "round", opacity: 0.6 }, g); },
    simsek: (g, c) => V.el("path", { d: "M10 -44 L-26 6 H-3 L-12 44 L26 -9 H3Z", fill: c, stroke: c, "stroke-width": 5, "stroke-linejoin": "round" }, g),
    damla: (g, c) => V.el("path", { d: "M0 -44 C22 -12 31 2 31 15 A31 31 0 0 1 -31 15 C-31 2 -22 -12 0 -44Z", fill: c }, g),
    yaprak: (g, c, k) => { V.el("path", { d: "M-36 36 C-44 -10 -8 -42 40 -40 C42 8 10 44 -36 36Z", fill: c }, g);
      V.el("path", { d: "M-36 36 C-14 12 6 -8 24 -24", fill: "none", stroke: k, "stroke-width": 5, "stroke-linecap": "round", opacity: 0.5 }, g); },
    ok: (g, c) => V.el("path", { d: "M0 -44 L34 -6 H14 V42 H-14 V-6 H-34Z", fill: c, stroke: c, "stroke-width": 6, "stroke-linejoin": "round" }, g),
    tik: (g, c) => V.el("path", { d: "M-34 2 L-10 26 L36 -24", fill: "none", stroke: c, "stroke-width": 15, "stroke-linecap": "round", "stroke-linejoin": "round" }, g),
    carpi: (g, c) => V.el("path", { d: "M-30 -30 L30 30 M30 -30 L-30 30", fill: "none", stroke: c, "stroke-width": 15, "stroke-linecap": "round" }, g),
    soru: (g, c) => { V.el("path", { d: "M-20 -18 C-20 -46 22 -46 21 -18 C20 -2 0 -2 0 14", fill: "none", stroke: c, "stroke-width": 13, "stroke-linecap": "round" }, g); V.el("circle", { cx: 0, cy: 36, r: 8, fill: c }, g); },
    unlem: (g, c) => { V.el("rect", { x: -7.5, y: -44, width: 15, height: 58, rx: 7.5, fill: c }, g); V.el("circle", { cx: 0, cy: 35, r: 8.5, fill: c }, g); },
    konusma: (g, c, k) => { V.el("rect", { x: -43, y: -38, width: 86, height: 60, rx: 18, fill: c }, g); V.el("path", { d: "M-22 18 L-28 44 L4 20Z", fill: c, stroke: c, "stroke-width": 4, "stroke-linejoin": "round" }, g);
      [-20, 0, 20].forEach((x) => V.el("circle", { cx: x, cy: -8, r: 5.5, fill: k, opacity: 0.6 }, g)); },
    goz: (g, c, k) => { V.el("path", { d: "M-45 0 C-24 -31 24 -31 45 0 C24 31 -24 31 -45 0Z", fill: c }, g); V.el("circle", { r: 15, fill: k }, g); V.el("circle", { cx: 5, cy: -5, r: 4.5, fill: c }, g); },
    kilit: (g, c, k) => { V.el("path", { d: "M-18 -6 V-20 A18 18 0 0 1 18 -20 V-6", fill: "none", stroke: c, "stroke-width": 10, "stroke-linecap": "round" }, g);
      V.el("rect", { x: -29, y: -8, width: 58, height: 48, rx: 10, fill: c }, g); V.el("circle", { cx: 0, cy: 14, r: 7, fill: k }, g); },
    takvim: (g, c, k) => { V.el("rect", { x: -37, y: -32, width: 74, height: 72, rx: 11, fill: c }, g); V.el("rect", { x: -37, y: -14, width: 74, height: 5, fill: k, opacity: 0.6 }, g);
      [-18, 18].forEach((x) => V.el("rect", { x: x - 4, y: -43, width: 8, height: 20, rx: 4, fill: c, stroke: k, "stroke-width": 2 }, g));
      for (let i = 0; i < 6; i++) V.el("rect", { x: -25 + (i % 3) * 19, y: -2 + Math.floor(i / 3) * 17, width: 11, height: 10, rx: 3, fill: k, opacity: 0.55 }, g); },
    grafik: (g, c) => { [[-36, 8, 32], [-10, -12, 52], [16, -36, 76]].forEach(([x, y, h]) => V.el("rect", { x, y, width: 20, height: h, rx: 6, fill: c }, g)); },
    ates: (g, c, k) => { V.el("path", { d: "M2 -45 C8 -22 31 -12 31 13 A31 31 0 0 1 -31 13 C-31 -3 -19 -9 -15 -23 C-7 -16 -3 -30 2 -45Z", fill: c }, g);
      V.el("path", { d: "M0 2 C8 12 14 16 14 24 A14 14 0 0 1 -14 24 C-14 16 -6 12 0 2Z", fill: k, opacity: 0.45 }, g); },
    ay: (g, c) => V.el("path", { d: "M12 -42 A42 42 0 1 0 42 12 A33 33 0 0 1 12 -42Z", fill: c }, g),
    gunes: (g, c) => { V.el("circle", { r: 20, fill: c }, g); for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4;
      V.el("line", { x1: 30 * Math.cos(a), y1: 30 * Math.sin(a), x2: 43 * Math.cos(a), y2: 43 * Math.sin(a), stroke: c, "stroke-width": 8, "stroke-linecap": "round" }, g); } },
    bulut: (g, c) => V.el("path", { d: "M-28 28 A21 21 0 0 1 -33 -12 A27 27 0 0 1 17 -22 A24 24 0 0 1 30 28Z", fill: c }, g),
    kitap: (g, c, k) => { V.el("path", { d: "M-44 -30 C-28 -36 -12 -34 0 -26 C12 -34 28 -36 44 -30 V34 C28 28 12 30 0 38 C-12 30 -28 28 -44 34Z", fill: c }, g);
      V.el("path", { d: "M0 -24 V36", stroke: k, "stroke-width": 5, opacity: 0.55 }, g); },
    muzik: (g, c) => { V.el("ellipse", { cx: -14, cy: 30, rx: 16, ry: 12, fill: c, transform: "rotate(-18 -14 30)" }, g); V.el("path", { d: "M-1 28 V-40 C12 -30 28 -30 28 -10", fill: "none", stroke: c, "stroke-width": 9, "stroke-linecap": "round" }, g); },
    hedef: (g, c) => { [40, 24].forEach((r) => V.el("circle", { r, fill: "none", stroke: c, "stroke-width": 8 }, g)); V.el("circle", { r: 8, fill: c }, g); },
    kalkan: (g, c, k) => { V.el("path", { d: "M0 -45 L37 -31 V2 C37 24 19 38 0 45 C-19 38 -37 24 -37 2 V-31Z", fill: c }, g);
      V.el("path", { d: "M-16 0 L-4 12 L18 -12", fill: "none", stroke: k, "stroke-width": 8, "stroke-linecap": "round", "stroke-linejoin": "round", opacity: 0.6 }, g); },
    yatak: (g, c) => { V.el("rect", { x: -44, y: 0, width: 88, height: 24, rx: 8, fill: c }, g); V.el("rect", { x: -44, y: -30, width: 10, height: 64, rx: 5, fill: c }, g);
      V.el("rect", { x: 34, y: 0, width: 10, height: 34, rx: 5, fill: c }, g); V.el("rect", { x: -28, y: -16, width: 26, height: 14, rx: 7, fill: c }, g); },
    kahve: (g, c) => { V.el("path", { d: "M-34 -10 H22 V12 A28 28 0 0 1 -34 12Z", fill: c }, g); V.el("path", { d: "M22 -4 H30 A11 11 0 0 1 30 18 H20", fill: "none", stroke: c, "stroke-width": 7 }, g);
      V.el("path", { d: "M-18 -22 C-24 -30 -12 -34 -18 -42 M-2 -22 C-8 -30 4 -34 -2 -42", fill: "none", stroke: c, "stroke-width": 5, "stroke-linecap": "round", opacity: 0.7 }, g); },
  };
  V.ikonlar = Object.keys(IKONLAR);
  /** Hazır ikon (origin merkezde, V.yer ile konumlanır). V.ikon(ebeveyn, "kalp", {boyut: 160, renk: "#ff6b8b", ikinci: "#0b1022"})
   *  Adlar: V.ikonlar. ikinci: iç ayrıntı rengi (pencere, göz bebeği...). */
  V.ikon = (ebeveyn, ad, { boyut = 160, renk = "#fff", ikinci = "#0b1022", golge = false } = {}) => {
    const g = V.g(ebeveyn), ic = V.g(g, { transform: `scale(${boyut / 100})` });
    if (golge) ic.setAttribute("filter", "url(#golge)");
    if (!IKONLAR[ad]) { V.uyar(`Bilinmeyen ikon: ${ad} (olanlar: ${V.ikonlar.join(", ")})`); V.el("circle", { r: 40, fill: renk }, ic); }
    else IKONLAR[ad](ic, renk, ikinci);
    return { g };
  };

  /** Yüzde halkası (origin merkezde). h = V.halka(ebeveyn, {r: 180, kalinlik: 44, renk}); h.ayarla(0..1) */
  V.halka = (ebeveyn, { r = 180, kalinlik = 44, renk = "#3ec7c0", arka = "#ffffff", arkaOp = 0.1 } = {}) => {
    const g = V.g(ebeveyn), cevre = 2 * Math.PI * r;
    V.el("circle", { r, fill: "none", stroke: arka, "stroke-width": kalinlik, opacity: arkaOp }, g);
    const c = V.el("circle", { r, fill: "none", stroke: renk, "stroke-width": kalinlik, "stroke-linecap": "round",
      "stroke-dasharray": `0 ${cevre}`, transform: "rotate(-90)" }, g);
    return { g, ayarla: (p) => { const u = V.sinir(p) * cevre; c.setAttribute("stroke-dasharray", `${u.toFixed(1)} ${cevre}`); c.setAttribute("opacity", p > 0.002 ? 1 : 0); } };
  };

  /** Çizgi grafik (origin sol alt köşe). c = V.cizgiGrafik(ebeveyn, {degerler: [3, 5, 4, 9], genislik: 800, yukseklik: 500, renk});
   *  c.ayarla(0..1) çizgiyi soldan sağa çizer; c.nokta(i) i. değerin {x, y} konumu (etiket koymak için). */
  V.cizgiGrafik = (ebeveyn, { degerler, genislik = 800, yukseklik = 500, renk = "#ffd166", kalinlik = 12, dolgu = true, en_az = null, en_cok = null } = {}) => {
    const g = V.g(ebeveyn), n = degerler.length;
    const a = en_az ?? Math.min(...degerler), b = en_cok ?? Math.max(...degerler), ar = b - a || 1;
    const P = degerler.map((v, i) => ({ x: n > 1 ? genislik * i / (n - 1) : 0, y: -yukseklik * (v - a) / ar }));
    const d = P.map((p, i) => (i ? "L" : "M") + p.x.toFixed(1) + " " + p.y.toFixed(1)).join(" ");
    V.el("path", { d: `M0 0 H${genislik}`, stroke: "#ffffff", "stroke-width": 4, opacity: 0.18, "stroke-linecap": "round" }, g);
    const kid = V.id("kirp"), kirp = V.el("clipPath", { id: kid }, V.defs), kr = V.el("rect", { x: -kalinlik, y: -yukseklik - kalinlik * 2, width: 0, height: yukseklik + kalinlik * 3 }, kirp);
    const ic = V.g(g, { "clip-path": `url(#${kid})` });
    if (dolgu) V.el("path", { d: d + ` L${genislik} 0 L0 0Z`, fill: renk, opacity: 0.16 }, ic);
    V.el("path", { d, fill: "none", stroke: renk, "stroke-width": kalinlik, "stroke-linecap": "round", "stroke-linejoin": "round" }, ic);
    const uc = V.el("circle", { r: kalinlik * 1.25, fill: "#fff", stroke: renk, "stroke-width": kalinlik * 0.5, opacity: 0 }, g);
    return { g, nokta: (i) => P[i], ayarla: (p) => {
      p = V.sinir(p); const x = genislik * p; kr.setAttribute("width", x + kalinlik);
      let i = Math.min(n - 2, Math.floor(p * (n - 1))); if (n < 2) i = 0;
      const k = n > 1 ? p * (n - 1) - i : 0, p0 = P[i], p1 = P[Math.min(n - 1, i + 1)];
      uc.setAttribute("cx", x); uc.setAttribute("cy", p0.y + (p1.y - p0.y) * k); uc.setAttribute("opacity", p > 0.002 ? 1 : 0); } };
  };

  /* ---------------- kukla (PNG karakteri pinlerle oynatma) ---------------- */
  /**
   * Kesilmiş (arka planı saydam) bir PNG karakteri pinlerle büker: kol sallama, baş eğme, nefes.
   * V.kukla(ebeveyn, {resim: "../cizgi/kisi.png", pinler: [{x,y}, ...], genislik, sutun: 18, pay: 120})
   *   pinler resmin piksel koordinatlarında. Hareket etmeyecek pinler (ayaklar, omuzlar, kalça) sabitlemeye yarar:
   *   bir pin yalnızca yakınını büker, o yüzden oynayan parçanın çevresine sabit pinler koy.
   * Döndürür {g, w, h, ciz(hareketler)}: hareketler[i] = {dx, dy, rot (derece), s, ox, oy}  (ox/oy: dönme merkezi, yoksa pinin kendisi)
   * g'nin orijini resmin sol üst köşesi; genislik verilirse ölçeklenir. V.yer ile konumlandırılır.
   */
  V.kukla = (ebeveyn, o) => {
    const g = V.g(ebeveyn), ic = V.g(g);
    const pay = o.pay ?? 120, pinler = o.pinler || [];
    const nesne = { g, w: 0, h: 0, ciz: () => {} };
    const img = new Image();
    const kur = () => {
      const W = img.naturalWidth, H = img.naturalHeight;
      if (!W) { V.uyar("Kukla resmi yüklenemedi: " + o.resim); return; }
      nesne.w = W; nesne.h = H;
      const olcek = o.genislik ? o.genislik / W : 1;
      ic.setAttribute("transform", `scale(${olcek}) translate(${-pay} ${-pay})`);
      const fo = V.el("foreignObject", { x: 0, y: 0, width: W + 2 * pay, height: H + 2 * pay }, ic);
      const cv = document.createElementNS("http://www.w3.org/1999/xhtml", "canvas");
      cv.width = W + 2 * pay; cv.height = H + 2 * pay; cv.style.width = cv.width + "px"; cv.style.height = cv.height + "px";
      fo.appendChild(cv);
      const ctx = cv.getContext("2d");
      // saydam olmayan hücreleri bul (boş hücrelere üçgen çizme)
      const ac = document.createElement("canvas"); ac.width = W; ac.height = H;
      const actx = ac.getContext("2d"); actx.drawImage(img, 0, 0);
      let alfa = null; try { alfa = actx.getImageData(0, 0, W, H).data; } catch (e) {}
      const sut = o.sutun ?? 18, sat = Math.max(2, Math.round(sut * H / W));
      const cw = W / sut, ch = H / sat;
      const dolu = (i, j) => {
        if (!alfa) return true;
        for (let y = Math.floor(j * ch); y < Math.min(H, (j + 1) * ch); y += 3)
          for (let x = Math.floor(i * cw); x < Math.min(W, (i + 1) * cw); x += 3) if (alfa[(y * W + x) * 4 + 3] > 8) return true;
        return false;
      };
      const kv = [];   // köşe noktaları
      for (let j = 0; j <= sat; j++) for (let i = 0; i <= sut; i++) kv.push([i * cw, j * ch]);
      const ucgen = [];
      for (let j = 0; j < sat; j++) for (let i = 0; i < sut; i++) if (dolu(i, j)) {
        const a = j * (sut + 1) + i, b = a + 1, c = a + sut + 1, d = c + 1;
        ucgen.push([a, b, d], [a, d, c]);
      }
      // her köşenin pinlere ağırlığı (ters uzaklık kare)
      const agirlik = kv.map(([x, y]) => {
        const w = pinler.map((p) => { const d2 = (x - p.x) ** 2 + (y - p.y) ** 2 + 400; return 1 / (d2 * d2); });   // yerel etki
        const top = w.reduce((a, b) => a + b, 0) || 1; return w.map((v) => v / top);
      });
      nesne.ciz = (hareketler = []) => {
        const T = pinler.map((p, i) => {
          const h = hareketler[i] || {};
          const r = ((h.rot || 0) * Math.PI) / 180, sc = h.s ?? 1, ox = h.ox ?? p.x, oy = h.oy ?? p.y;
          return [Math.cos(r) * sc, Math.sin(r) * sc, ox, oy, h.dx || 0, h.dy || 0];
        });
        const yeni = kv.map(([x, y], k) => {
          if (!T.length) return [x, y];
          let nx = 0, ny = 0;
          T.forEach(([c, sn, ox, oy, dx, dy], i) => {
            const w = agirlik[k][i], px = x - ox, py = y - oy;
            nx += w * (c * px - sn * py + ox + dx); ny += w * (sn * px + c * py + oy + dy);
          });
          return [nx, ny];
        });
        ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, cv.width, cv.height);
        for (const [a, b, c] of ucgen) {
          const [x0, y0] = kv[a], [x1, y1] = kv[b], [x2, y2] = kv[c];
          let [u0, v0] = yeni[a], [u1, v1] = yeni[b], [u2, v2] = yeni[c];
          // dikiş çizgisi kalmasın diye hedef üçgeni ağırlık merkezinden hafifçe büyüt
          const mx = (u0 + u1 + u2) / 3, my = (v0 + v1 + v2) / 3, gen = 0.9;
          const bv = (u, v) => { const dx = u - mx, dy = v - my, l = Math.hypot(dx, dy) || 1; return [u + (dx / l) * gen, v + (dy / l) * gen]; };
          const [e0, f0] = bv(u0, v0), [e1, f1] = bv(u1, v1), [e2, f2] = bv(u2, v2);
          const den = x0 * (y1 - y2) + x1 * (y2 - y0) + x2 * (y0 - y1);
          if (!den) continue;
          const A = (u0 * (y1 - y2) + u1 * (y2 - y0) + u2 * (y0 - y1)) / den;
          const B = (v0 * (y1 - y2) + v1 * (y2 - y0) + v2 * (y0 - y1)) / den;
          const C = (u0 * (x2 - x1) + u1 * (x0 - x2) + u2 * (x1 - x0)) / den;
          const D = (v0 * (x2 - x1) + v1 * (x0 - x2) + v2 * (x1 - x0)) / den;
          const E = (u0 * (x1 * y2 - x2 * y1) + u1 * (x2 * y0 - x0 * y2) + u2 * (x0 * y1 - x1 * y0)) / den;
          const F = (v0 * (x1 * y2 - x2 * y1) + v1 * (x2 * y0 - x0 * y2) + v2 * (x0 * y1 - x1 * y0)) / den;
          ctx.save();
          ctx.setTransform(1, 0, 0, 1, pay, pay);
          ctx.beginPath(); ctx.moveTo(e0, f0); ctx.lineTo(e1, f1); ctx.lineTo(e2, f2); ctx.closePath(); ctx.clip();
          ctx.setTransform(A, B, C, D, E + pay, F + pay);
          ctx.drawImage(img, 0, 0);
          ctx.restore();
        }
      };
      nesne.ciz([]);
    };
    V._bekle.push(new Promise((r) => { img.onload = () => { kur(); r(); }; img.onerror = () => { V.uyar("Kukla resmi bulunamadı: " + o.resim); r(); }; }));
    img.src = o.resim;
    return nesne;
  };

  /* ---------------- renk karışımı ---------------- */
  function karistir(a, b, p) {
    const c = (h) => { h = h.replace("#", ""); if (h.length === 3) h = h.split("").map((x) => x + x).join(""); const n = parseInt(h.slice(0, 6), 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
    const x = c(a), y = c(b);
    return "#" + x.map((v, i) => Math.round(V.ara(v, y[i], V.sinir(p))).toString(16).padStart(2, "0")).join("");
  }
  V.karistir = karistir;

  /* ---------------- sahne yaşam döngüsü ---------------- */
  /**
   * V.sahne({ sure, arka, kur(s), ciz(t, s),
   *   giris: "siyah" | "beyaz" | "yok" | "devir",      devir: önceki sahnenin büyüyen şekli bu sahnenin rengiyle biter, bu sahne o renkten %93→%100 açılır
   *   cikis: "siyah" | "beyaz" | "yok" | "devir",
   *   devir: { oge: () => el  | x, y, r,  sekil: "daire" | "kare",  renk: "#şeklin rengi",  hedef: "#sonraki sahnenin rengi" (genelde otomatik),  sure: 0.9 },
   *   poz: 12,          // saniyede poz sayısı (el yapımı animasyon hissi; video fps: 24 önerilir)
   *   titreme: 1.5,     // çizgi titremesi (piksel), her pozda değişir
   *   cikartma: true | {dx, dy, op}   // düz, sert "çıkartma" gölgesi
   * })
   */
  V.sahne = (tanim) => {
    V._sahne = tanim;
    V.sure = Number(q.get("sure")) || tanim.sure || 5;
    const basla = async () => {
      try { await document.fonts.load("800 40px Nunito"); await document.fonts.ready; } catch (e) {}
      const arka = tanim.arka ?? ["#0d1430", "#1d2452"];
      V.arka0 = Array.isArray(arka) ? arka[0] : arka;
      document.body.style.background = Array.isArray(arka) ? arka[arka.length - 1] : arka;
      V.svg = V.el("svg", { viewBox: `0 0 ${V.W} ${V.H}`, preserveAspectRatio: "xMidYMid meet", width: "100%", height: "100%" }, document.body);
      V.defs = V.el("defs", {}, V.svg);
      filtreler();
      V.el("rect", { x: -2000, y: -2000, width: V.W + 4000, height: V.H + 4000, fill: Array.isArray(arka) ? V.gradyan(arka) : arka }, V.svg);
      V.icerik = V.g(V.svg);                 // giriş "devir" ölçeklemesi buna uygulanır
      V.kameraKap = V.g(V.icerik);            // el yapımı filtre (titreme, çıkartma gölgesi) buna uygulanır
      V.kamera = V.g(V.kameraKap);
      V.ust = V.g(V.icerik);                  // kameradan etkilenmeyen katman (yazılar için)
      elYapimiKur(tanim);
      V.devirSekil = V.g(V.svg);             // çıkış "devir" şekli (en üstte)
      V.gecis = V.el("rect", { x: -10, y: -10, width: V.W + 20, height: V.H + 20, fill: "#000", opacity: 0 }, V.svg);
      const s = { kamera: V.kamera, ust: V.ust };
      tanim.kur && tanim.kur(s);
      V._s = s;
      if (V._bekle.length) await Promise.all(V._bekle);
      if (tanim.poz && ![8, 12].includes(tanim.poz)) V.uyar("poz için 8 ya da 12 önerilir (video fps: 24).");
      V.git(0);
      window.HAZIR = true;
      if (V.mod === "oynat") oynat();
      if (V.mod === "gomulu") window.addEventListener("message", (e) => { if (e.data && e.data.komut === "git") V.git(e.data.t); });
      if (window.parent !== window) window.parent.postMessage({ hazir: true, sure: V.sure }, "*");
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", basla); else basla();
  };

  let elFiltre = null;
  function elYapimiKur(tn) {
    const tit = tn.titreme ?? 0, ck = tn.cikartma;
    if (!tit && !ck) return;
    const f = V.el("filter", { id: "elyapimi", filterUnits: "userSpaceOnUse", x: -400, y: -400, width: V.W + 800, height: V.H + 800 }, V.defs);
    let kaynak = "SourceGraphic";
    elFiltre = { tur: null };
    if (tit) {
      elFiltre.tur = V.el("feTurbulence", { type: "fractalNoise", baseFrequency: 0.018, numOctaves: 2, seed: 1, result: "gurultu" }, f);
      V.el("feDisplacementMap", { in: "SourceGraphic", in2: "gurultu", scale: (tit * 2.4).toFixed(2), xChannelSelector: "R", yChannelSelector: "G", result: "titrek" }, f);
      kaynak = "titrek";
    }
    if (ck) {
      const c = ck === true ? {} : ck;
      V.el("feFlood", { "flood-color": c.renk ?? "#000", "flood-opacity": c.op ?? 0.25, result: "gr" }, f);
      V.el("feComposite", { in: "gr", in2: kaynak, operator: "in", result: "gs" }, f);
      V.el("feOffset", { in: "gs", dx: c.dx ?? 16, dy: c.dy ?? 18, result: "go" }, f);
      const m = V.el("feMerge", {}, f); V.el("feMergeNode", { in: "go" }, m); V.el("feMergeNode", { in: kaynak }, m);
    }
    V.kameraKap.setAttribute("filter", "url(#elyapimi)");
  }

  /** t anına git (kayıt ve önizleme bunu çağırır) */
  V.git = (t) => {
    V.t = t;
    const tn = V._sahne;
    const tc = tn.poz ? Math.floor(t * tn.poz + 1e-6) / tn.poz : t;   // poz: zamanı basamaklara böl
    V.tc = tc;
    tn.ciz && tn.ciz(tc, V._s);
    if (elFiltre && elFiltre.tur) elFiltre.tur.setAttribute("seed", 1 + (Math.floor(t * (tn.poz || 12) + 1e-6) % 97));
    gecisler(t, tn);
  };

  function gecisler(t, tn) {
    const gr = tn.giris ?? "siyah", ck = tn.cikis ?? "siyah";
    let op = 0, renk = "#000";
    // giriş
    if (gr === "devir") {
      const gs = tn.devirGiris ?? 0.8;
      const p = V.e.cikis(V.sinir(t / gs));
      const s = 0.93 + 0.07 * p;
      V.icerik.setAttribute("transform", `translate(${V.W / 2} ${V.H / 2}) scale(${s.toFixed(4)}) translate(${-V.W / 2} ${-V.H / 2})`);
      const po = 1 - V.e.cikis(V.sinir(t / (gs * 0.55)));
      if (po > 0) { op = po; renk = V.arka0; }
    } else {
      V.icerik.removeAttribute("transform");
      if (gr !== "yok" && t < 0.35) { op = 1 - V.e.cikis(t / 0.35); renk = gr === "beyaz" ? "#fff" : "#000"; }
    }
    // çıkış
    V.devirSekil.textContent = "";
    if (ck === "devir") devirCikis(t, tn);
    else if (ck !== "yok" && V.sure - t < 0.35) { op = Math.max(op, 1 - (V.sure - t) / 0.35); renk = ck === "beyaz" ? "#fff" : "#000"; }
    V.gecis.setAttribute("fill", renk); V.op(V.gecis, op);
  }

  /** svg koordinatlarında bir öğenin merkezi, yarıçapı ve dönüşüm matrisi */
  function olc(el) {
    const bb = el.getBBox();
    const m = V.svg.getScreenCTM().inverse().multiply(el.getScreenCTM());
    const nok = [[bb.x, bb.y], [bb.x + bb.width, bb.y], [bb.x, bb.y + bb.height], [bb.x + bb.width, bb.y + bb.height]].map(([x, y]) => {
      const p = V.svg.createSVGPoint(); p.x = x; p.y = y; return p.matrixTransform(m);
    });
    const xs = nok.map((p) => p.x), ys = nok.map((p) => p.y);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    return { x: (x0 + x1) / 2, y: (y0 + y1) / 2, r: Math.max(x1 - x0, y1 - y0) / 2, ic: Math.min(x1 - x0, y1 - y0) / 2,
      m: [m.a, m.b, m.c, m.d, m.e, m.f] };
  }

  function duzRenk(el) {
    for (const e of [el, ...el.querySelectorAll("*")]) {
      const f = e.getAttribute && e.getAttribute("fill");
      if (f && /^#[0-9a-f]{3,8}$/i.test(f)) return f;
    }
    return null;
  }

  function devirCikis(t, tn) {
    const d = tn.devir || {};
    const D = d.sure ?? 1.1, t0 = V.sure - D;
    if (t < t0) return;
    const p = V.sinir((t - t0) / D);
    const el = typeof d.oge === "function" ? d.oge() : d.oge || (V._s && V._s.devirOge);
    // şeklin başlangıç yeri: verilen öğenin t0 anındaki hali ya da x, y, r
    let geo = d._geo;
    if (!geo || d._t0 !== t0) {
      if (el) {
        tn.ciz && tn.ciz(tn.poz ? Math.floor(t0 * tn.poz + 1e-6) / tn.poz : t0, V._s);
        try { geo = olc(el); } catch (e) { geo = null; }
        tn.ciz && tn.ciz(V.tc, V._s);
      }
      if (!geo) geo = { x: d.x ?? V.W / 2, y: d.y ?? V.H / 2, r: d.r ?? 80 };
      if (!el && d.x === undefined) V.uyar("Çıkış 'devir' için devir.oge ya da devir.x/y verilmeli; ekran ortası kullanıldı.");
      d._geo = geo; d._t0 = t0; tn.devir = d;
    }
    const hedef = q.get("sonraki") ? "#" + q.get("sonraki") : d.hedef ?? V.arka0;
    const kaynakRenk = d.renk ?? (el && duzRenk(el)) ?? "#ffffff";
    const Rmax = Math.hypot(Math.max(geo.x, V.W - geo.x), Math.max(geo.y, V.H - geo.y)) * 1.08;
    const r0 = Math.max(8, geo.r);
    const metinli = el && (el.tagName === "text" || el.querySelector("text"));
    const sekil = d.sekil ?? (el && !metinli && geo.m ? "oge" : "daire");
    // ön sıkışma (%8), sonra kesintisiz büyüme
    const on = 0.2;
    let k, renk, op;
    if (p < on) { k = 1 - 0.08 * V.e.iki(p / on); renk = kaynakRenk; op = V.e.cikis(p / on); }
    else { const b = V.sinir((p - on) / 0.7); k = b; renk = karistir(kaynakRenk, hedef, V.e.iki(V.sinir((b - 0.04) / 0.3))); op = 1; }
    const buyume = p < on ? 0 : V.e.giris(V.sinir((p - on) / 0.7)) * 0.35 + V.sinir((p - on) / 0.7) * 0.65;
    // arkadaki içerik şekle doğru hafifçe yaklaşır (tek yönlü)
    const z = 1 + 0.06 * V.e.giris(p);
    V.icerik.setAttribute("transform", `translate(${geo.x} ${geo.y}) scale(${z.toFixed(4)}) translate(${-geo.x} ${-geo.y})`);
    if (sekil === "oge") {
      // öğenin kendisi (kopyası) büyür ve sonraki sahnenin rengine dönüşür
      const ic = Math.max(6, (geo.ic ?? r0) * 0.42);
      const son = Rmax / ic;
      const olcek = p < on ? k : 0.92 * Math.pow(son / 0.92, buyume);   // üstel: göze eşit hızda büyür
      const kap = V.g(V.devirSekil, { transform: `translate(${geo.x} ${geo.y}) scale(${olcek.toFixed(4)}) translate(${-geo.x} ${-geo.y}) matrix(${geo.m.join(" ")})`, opacity: op });
      const kl = el.cloneNode(true); kl.removeAttribute("transform"); kl.removeAttribute("opacity");
      for (const e of [kl, ...kl.querySelectorAll("*")]) {
        if (e.getAttribute("fill") !== "none") e.setAttribute("fill", renk);
        e.removeAttribute("opacity"); if (e !== kl) e.removeAttribute("filter");
      }
      kap.appendChild(kl);
      el.setAttribute("opacity", 0);
      if (buyume > 0.72) V.el("rect", { x: -10, y: -10, width: V.W + 20, height: V.H + 20, fill: hedef, opacity: ((buyume - 0.72) / 0.28).toFixed(3) }, V.devirSekil);
    } else {
      const r = p < on ? r0 * k : r0 * 0.92 * Math.pow(Rmax / (r0 * 0.92), buyume);
      if (el) el.setAttribute("opacity", V.sinir(1 - p / on));
      if (sekil === "kare") {
        const yk = Math.max(0, 1 - (r - r0) / (Rmax - r0 || 1));
        V.el("rect", { x: geo.x - r, y: geo.y - r, width: Math.max(r * 2, 1), height: Math.max(r * 2, 1), rx: (r * (0.12 + 0.3 * yk)).toFixed(1), fill: renk, opacity: op }, V.devirSekil);
      } else {
        V.el("circle", { cx: geo.x, cy: geo.y, r: r.toFixed(1), fill: renk, opacity: op }, V.devirSekil);
      }
    }
  }

  function oynat() {
    const t0 = performance.now();
    const dongu = () => { V.git(((performance.now() - t0) / 1000) % V.sure); requestAnimationFrame(dongu); };
    requestAnimationFrame(dongu);
  }
})();
