/* =====================================================================
   3D Animasyon Kütüphanesi (U) — Three.js üzerine
   Her sahne bir HTML dosyasıdır ve modül olarak yazılır:
     <script type="importmap">{"imports":{"three":"../../../engine/3d/three.module.min.js","three/addons/":"../../../engine/3d/addons/"}}</script>
     <script type="module">
       import { U, THREE } from "../../../engine/3d/3d.js";
       U.sahne({ sure, arka, isik, kur(s) {...}, ciz(t, s) {...} });
     </script>
   - kur(s): nesneleri bir kez oluştur. s.sahne (THREE.Scene), s.kamera, s.ust (yazılar için 2D katman)
   - ciz(t, s): t saniyesindeki görünümü ayarla (zamanın saf fonksiyonu; önceki kareye bağlı durum tutma)
   Tasarım alanı (yazılar için) 1080 x 1920. 3D birim: 1 ≈ 1 metre.
   ===================================================================== */
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
export { THREE };

const q = new URLSearchParams(location.search);
{ let r = 20261111; Math.random = () => ((r = (Math.imul(r, 1664525) + 1013904223) >>> 0) / 4294967296); }

export const U = {
  dil: q.get("dil") || "tr", mod: q.get("mod") || "oynat", W: 1080, H: 1920, sure: 5, t: 0,
  uyarilar: [], _bekle: [], _sahne: null, THREE,
};
window.U = U;
window.V = U;                       // stüdyo ve kayıt aracı V.git(t) çağırır
window.UYARILAR = U.uyarilar;
U.uyar = (m) => { if (!U.uyarilar.includes(m)) { U.uyarilar.push(m); console.warn("[3d] " + m); } };

/* ---------------- zaman ---------------- */
U.sinir = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
U.e = { lin: (x) => x, giris: (x) => x * x * x, cikis: (x) => 1 - Math.pow(1 - x, 3), iki: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2) };
U.p = (t, t0, sure, y = "iki") => U.e[y](U.sinir((t - t0) / sure));
U.ara = (a, b, p) => a + (b - a) * p;
U.kf = (t, k, y = "iki") => {
  if (t <= k[0][0]) return k[0][1];
  for (let i = 1; i < k.length; i++) if (t <= k[i][0]) return U.ara(k[i - 1][1], k[i][1], U.e[y]((t - k[i - 1][0]) / (k[i][0] - k[i - 1][0])));
  return k[k.length - 1][1];
};
U.tohum = (s) => { let r = (s * 2654435761) >>> 0 || 1; return () => ((r = (Math.imul(r, 1664525) + 1013904223) >>> 0) / 4294967296); };

/* ---------------- çok dilli yazı ---------------- */
let CEVIRI;
U.metin = (v) => {
  if (!v || typeof v !== "object") return v ?? "";
  if (v[U.dil] != null) return v[U.dil];
  if (CEVIRI === undefined) {
    CEVIRI = null;
    try { const m = location.pathname.match(/^(.*\/projeler\/[^/]+\/)/); if (m) { const x = new XMLHttpRequest(); x.open("GET", m[1] + "ceviri.json?v=" + Date.now(), false); x.send(); if (x.status === 200) CEVIRI = JSON.parse(x.responseText); } } catch (e) {}
  }
  const e = (((CEVIRI || {}).diller || {})[U.dil] || {}).ekran || {};
  for (const k in v) if (e[v[k]]) return e[v[k]];
  return v.en ?? Object.values(v)[0];
};

/* ---------------- malzeme ve hazır şekiller ---------------- */
/** U.malzeme("#5cb24a", {parlak: 0.3, metal: 0, duz: false, isik: false}) — "kil" görünümlü yumuşak malzeme */
U.malzeme = (renk, { parlak = 0.25, metal = 0, duz = false, isik = false, saydam = null, yayilim = 0 } = {}) => {
  if (isik) return new THREE.MeshBasicMaterial({ color: renk });
  const m = new THREE.MeshStandardMaterial({ color: renk, roughness: 1 - parlak, metalness: metal, flatShading: duz });
  if (yayilim) { m.emissive = new THREE.Color(renk); m.emissiveIntensity = yayilim; }
  if (saydam != null) { m.transparent = true; m.opacity = saydam; }
  return m;
};
const golgeli = (o) => { o.traverse((c) => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } }); return o; };
U.golgeli = golgeli;
const mesh = (geo, renk, o) => golgeli(new THREE.Mesh(geo, renk instanceof THREE.Material ? renk : U.malzeme(renk, o)));
U.kure = (r = 1, renk = "#ffffff", o = {}) => mesh(new THREE.SphereGeometry(r, o.detay ?? 48, Math.round((o.detay ?? 48) * 0.66)), renk, o);
U.kutu = (g = 1, y = 1, d = 1, renk = "#ffffff", o = {}) => {
  const k = o.yuvarlak ?? 0.06;
  const geo = k > 0 ? yuvarlakKutu(g, y, d, Math.min(k, g / 2, y / 2, d / 2)) : new THREE.BoxGeometry(g, y, d);
  return mesh(geo, renk, o);
};
U.silindir = (r = 0.5, y = 1, renk = "#ffffff", o = {}) => mesh(new THREE.CylinderGeometry(o.ust ?? r, r, y, o.detay ?? 40), renk, o);
U.koni = (r = 0.5, y = 1, renk = "#ffffff", o = {}) => mesh(new THREE.ConeGeometry(r, y, o.detay ?? 40), renk, o);
U.halka = (r = 1, kal = 0.15, renk = "#ffffff", o = {}) => mesh(new THREE.TorusGeometry(r, kal, 24, 96), renk, o);
function yuvarlakKutu(w, h, d, r) {   // köşeleri yuvarlatılmış kutu (oyuncak / kil görünümü)
  const s = new THREE.Shape(), x = -w / 2 + r, y = -h / 2 + r, ww = w - 2 * r, hh = h - 2 * r;
  s.moveTo(x, y - r); s.lineTo(x + ww, y - r); s.quadraticCurveTo(x + ww + r, y - r, x + ww + r, y); s.lineTo(x + ww + r, y + hh);
  s.quadraticCurveTo(x + ww + r, y + hh + r, x + ww, y + hh + r); s.lineTo(x, y + hh + r); s.quadraticCurveTo(x - r, y + hh + r, x - r, y + hh);
  s.lineTo(x - r, y); s.quadraticCurveTo(x - r, y - r, x, y - r);
  const g = new THREE.ExtrudeGeometry(s, { depth: d - 2 * r, bevelEnabled: true, bevelThickness: r, bevelSize: r * 0.98, bevelSegments: 4, curveSegments: 6 });
  g.translate(0, 0, -(d - 2 * r) / 2); g.computeVertexNormals(); return g;
}

/** zemin: büyük yuvarlak düzlem (gölge alır) */
U.zemin = (renk = "#5cb24a", { boyut = 300, y = 0 } = {}) => {
  const m = new THREE.Mesh(new THREE.CircleGeometry(boyut, 64), U.malzeme(renk, { parlak: 0.05 }));
  m.rotation.x = -Math.PI / 2; m.position.y = y; m.receiveShadow = true; return m;
};
/** ağaç: tur "yuvarlak" | "cam" */
U.agac = ({ tur = "yuvarlak", boy = 1, renk = null, tohum = 1 } = {}) => {
  const R = U.tohum(tohum), g = new THREE.Group();
  const gov = U.silindir(0.08 * boy, 0.6 * boy, "#8a5a3b", { ust: 0.06 * boy, detay: 10 }); gov.position.y = 0.3 * boy; g.add(gov);
  if (tur === "cam") {
    for (let i = 0; i < 3; i++) { const k = U.koni((0.55 - i * 0.13) * boy, 0.7 * boy, renk || "#2f8f5b", { detay: 18 }); k.position.y = (0.75 + i * 0.38) * boy; g.add(k); }
  } else {
    const ana = U.kure(0.5 * boy, renk || (R() < 0.5 ? "#4fae5a" : "#62bd5f"), { detay: 24 }); ana.position.y = 0.95 * boy; g.add(ana);
    for (let i = 0; i < 2; i++) { const k = U.kure((0.28 + R() * 0.1) * boy, renk || "#4fae5a", { detay: 18 }); k.position.set((R() - 0.5) * 0.6 * boy, (0.85 + R() * 0.3) * boy, (R() - 0.5) * 0.6 * boy); g.add(k); }
  }
  return g;
};
/** ev: duvar, çatı rengi; pencereler yanar */
U.ev = ({ duvar = "#f4e9d8", cati = "#e8695d", gen = 1, pencere = "#ffd166" } = {}) => {
  const g = new THREE.Group();
  const d = U.kutu(1 * gen, 0.8, 0.9, duvar, { yuvarlak: 0.05 }); d.position.y = 0.4; g.add(d);
  const c = U.koni(0.85 * gen, 0.6, cati, { detay: 4 }); c.position.y = 1.1; c.rotation.y = Math.PI / 4; c.scale.z = 0.8; g.add(c);
  const kapi = U.kutu(0.22, 0.4, 0.04, "#8a5a3b", { yuvarlak: 0.02 }); kapi.position.set(0, 0.2, 0.46); g.add(kapi);
  for (const x of [-0.3, 0.3]) { const p = new THREE.Mesh(new THREE.PlaneGeometry(0.18, 0.18), U.malzeme(pencere, { yayilim: 0.9 })); p.position.set(x * gen, 0.5, 0.452); g.add(p); }
  return g;
};
/** bulut: birleşik küreler */
U.bulut = ({ boy = 1, renk = "#ffffff", tohum = 2 } = {}) => {
  const R = U.tohum(tohum), g = new THREE.Group();
  for (let i = 0; i < 5; i++) { const k = U.kure((0.25 + R() * 0.2) * boy, renk, { parlak: 0, detay: 20 }); k.position.set((i - 2) * 0.3 * boy, R() * 0.15 * boy, (R() - 0.5) * 0.2 * boy); k.castShadow = false; g.add(k); }
  return g;
};
/** yıldız alanı (uzak küre üzerinde noktalar) */
U.yildizlar = (n = 600, { r = 80, boyut = 0.25, renk = "#ffffff" } = {}) => {
  const R = U.tohum(5), p = [];
  for (let i = 0; i < n; i++) { const v = new THREE.Vector3().setFromSphericalCoords(r * (0.9 + R() * 0.2), Math.acos(1 - 2 * R()), R() * Math.PI * 2); p.push(v.x, v.y, v.z); }
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ color: renk, size: boyut, sizeAttenuation: true }));
};
/** dosyadan hazır model (glTF / .glb), sahne klasörüne göre yol. Ücretsiz CC0 modeller: Kenney, Quaternius, Poly Pizza.
 *  const m = U.model("modeller/kopek.glb", {boy: 1}); m.g sahneye eklenir; m.anim(t, "Walk") ile modelin kendi animasyonu oynar */
U.model = (url, { boy = null } = {}) => {
  const g = new THREE.Group(), o = { g, karisim: null, kliple: {}, anim: () => {} };
  U._bekle.push(new Promise((ok) => new GLTFLoader().load(url, (gltf) => {
    const m = gltf.scene; golgeli(m);
    if (boy) { const b = new THREE.Box3().setFromObject(m), h = b.max.y - b.min.y || 1; m.scale.setScalar(boy / h); m.position.y = -b.min.y * (boy / h); }
    g.add(m);
    if (gltf.animations.length) {
      o.karisim = new THREE.AnimationMixer(m);
      for (const k of gltf.animations) o.kliple[k.name] = o.karisim.clipAction(k);
      o.anim = (t, ad) => { const a = o.kliple[ad] || Object.values(o.kliple)[0]; for (const x of Object.values(o.kliple)) x.enabled = x === a; a.play(); o.karisim.setTime(t); };
    }
    ok();
  }, undefined, (e) => { U.uyar(`Model yüklenemedi: ${url}`); ok(); })));
  return o;
};

/* ---------------- hareket ---------------- */
/** nesneyi yerleştir ve canlandır: U.yer(obj, t, {x, y, z, s, bas, giris: "buyu|yukari|dus", gs, bekle: "suz|don|nabiz|salla", faz}) */
U.yer = (o, t, { x = 0, y = 0, z = 0, s = 1, r = 0, bas = 0, giris = null, gs = 0.6, bit = null, cikis = "kucul", cs = 0.4, bekle = null, faz = 0 } = {}) => {
  let px = x, py = y, pz = z, sc = s, ry = r;
  if (giris && t < bas + gs) {
    const p = U.sinir((t - bas) / gs);
    if (giris === "buyu") { const e = p < 0.7 ? U.e.cikis(p / 0.7) * 1.08 : 1.08 - 0.08 * U.e.iki((p - 0.7) / 0.3); sc = s * Math.max(0.0001, e); }
    else if (giris === "yukari") { py = y - 1.5 * (1 - U.e.cikis(p)); sc = s * Math.max(0.0001, U.e.cikis(Math.min(1, p * 1.5))); }
    else if (giris === "dus") { const e = U.e.giris(p); py = y + 4 * (1 - e) + (p > 0.85 ? Math.sin((p - 0.85) / 0.15 * Math.PI) * 0.12 : 0); }
    if (t < bas) sc = 0.0001;
  }
  if (bit != null && t > bit) { const p = U.sinir((t - bit) / cs); if (cikis === "kucul") sc *= Math.max(0.0001, 1 - U.e.giris(p)); else if (cikis === "yukari") py += U.e.giris(p) * 3; }
  if (bekle) {
    const tt = t + faz;
    if (bekle.includes("suz")) py += Math.sin(tt * 1.6) * 0.06 * s;
    if (bekle.includes("don")) ry += tt * 0.5;
    if (bekle.includes("nabiz")) sc *= 1 + Math.sin(tt * 4) * 0.03;
    if (bekle.includes("salla")) o.rotation.z = Math.sin(tt * 2) * 0.06;
  }
  o.position.set(px, py, pz); o.scale.setScalar(sc); o.rotation.y = ry;
};
/** tek, sürekli kamera hareketi: başta hızlı, sonra uzun süre yavaş. bas → son konum, bakılan nokta hedef */
U.itme = (t, { bas = [0, 2, 12], son = [0, 1.6, 9], hedef = [0, 1, 0], sure = null } = {}) => {
  const p = U.e.cikis(U.sinir(t / (sure ?? U.sure)));
  U.kamera.position.set(U.ara(bas[0], son[0], p), U.ara(bas[1], son[1], p), U.ara(bas[2], son[2], p));
  U.kamera.lookAt(...hedef);
};
/** kamera hedefin etrafında döner: U.yorunge(t, {merkez, yaricap, yukseklik, hiz, aci}) */
U.yorunge = (t, { merkez = [0, 1, 0], yaricap = 9, yukseklik = 2.5, hiz = 0.15, aci = 0 } = {}) => {
  const a = aci + t * hiz;
  U.kamera.position.set(merkez[0] + Math.sin(a) * yaricap, merkez[1] + yukseklik, merkez[2] + Math.cos(a) * yaricap);
  U.kamera.lookAt(...merkez);
};

/* ---------------- 2D yazı katmanı ---------------- */
/** U.yazi(s.ust, {metin: {tr: "..."}, x: 540, y: 300, boyut: 80, renk, golge}) → .anim(t, t0, "bulanik", bit) */
U.yazi = (ebeveyn, { metin, x = 540, y = 300, boyut = 72, renk = "#ffffff", agirlik = 800, genislik = 920, golge = true, hiza = "center" } = {}) => {
  const d = document.createElement("div");
  d.style.cssText = `position:absolute;left:${x - genislik / 2}px;top:${y}px;width:${genislik}px;text-align:${hiza};font:${agirlik} ${boyut}px/1.15 Nunito,system-ui,sans-serif;color:${renk};` +
    (golge ? "text-shadow:0 6px 24px rgba(0,0,0,.35);" : "");
  const kel = U.metin(metin).split(" ").map((w) => { const s = document.createElement("span"); s.textContent = w + " "; s.style.display = "inline-block"; s.style.whiteSpace = "pre"; d.appendChild(s); return s; });
  ebeveyn.appendChild(d);
  return {
    el: d,
    anim(t, t0 = 0, efekt = "bulanik", bit = null) {
      kel.forEach((s, i) => {
        let p = U.sinir((t - t0 - i * 0.06) / 0.5), op = U.e.cikis(p), bl = (1 - U.e.cikis(p)) * 14, ty = (1 - U.e.cikis(p)) * 18;
        if (efekt === "solma") { bl = 0; ty = 0; }
        if (bit != null && t > bit) { const c = U.sinir((t - bit - i * 0.03) / 0.4); op *= 1 - c; bl += c * 14; ty -= c * 12; }
        s.style.opacity = op.toFixed(3); s.style.filter = bl > 0.1 ? `blur(${bl.toFixed(1)}px)` : "none"; s.style.transform = `translateY(${ty.toFixed(1)}px)`;
      });
    },
  };
};

/* ---------------- sahne ---------------- */
let RENDERER, SAHNE, UST, ORTU;
/**
 * U.sahne({
 *   sure: 5, arka: ["#0b1440", "#2a1f5c"],    // gökyüzü degradesi (üst, alt); ilk renk geçişlerde kullanılır
 *   isik: "gun" | "gece" | "studyo",           // hazır ışık düzeni
 *   sis: 0.02,                                  // uzak nesneler arka renge karışır (0 kapalı)
 *   gorus: 35,                                  // kamera görüş açısı (derece)
 *   giris: "siyah" | "beyaz" | "devir" | "yok",  cikis: aynı; cikis "devir" için devir: { renk, x, y, sure }
 *   kur(s) {...}, ciz(t, s) {...}
 * })
 */
U.sahne = (tanim) => {
  U._sahne = tanim;
  U.sure = Number(q.get("sure")) || tanim.sure || 5;
  const basla = async () => {
    const arka = tanim.arka ?? ["#0b1440", "#2a1f5c"], A = Array.isArray(arka) ? arka : [arka, arka];
    U.arka0 = A[0];
    document.body.style.cssText = `margin:0;overflow:hidden;background:${A[A.length - 1]}`;
    const W = innerWidth, H = innerHeight, olcek = Math.min(W / U.W, H / U.H);
    RENDERER = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    RENDERER.setPixelRatio(1); RENDERER.setSize(W, H);
    RENDERER.shadowMap.enabled = true; RENDERER.shadowMap.type = THREE.PCFSoftShadowMap;
    RENDERER.outputColorSpace = THREE.SRGBColorSpace; RENDERER.toneMapping = THREE.ACESFilmicToneMapping; RENDERER.toneMappingExposure = tanim.pozlama ?? 1;
    RENDERER.domElement.style.cssText = "position:fixed;inset:0";
    document.body.appendChild(RENDERER.domElement);
    // yazı katmanı: 1080 x 1920 tasarım alanı, ekrana ortalanarak ölçeklenir
    UST = document.createElement("div");
    UST.style.cssText = `position:fixed;left:${(W - U.W * olcek) / 2}px;top:${(H - U.H * olcek) / 2}px;width:${U.W}px;height:${U.H}px;transform:scale(${olcek});transform-origin:0 0;pointer-events:none`;
    document.body.appendChild(UST);
    ORTU = document.createElement("div"); ORTU.style.cssText = "position:fixed;inset:0;pointer-events:none;opacity:0"; document.body.appendChild(ORTU);

    SAHNE = new THREE.Scene();
    const c = document.createElement("canvas"); c.width = 2; c.height = 512;
    const g = c.getContext("2d"), gr = g.createLinearGradient(0, 0, 0, 512); A.forEach((r, i) => gr.addColorStop(i / Math.max(1, A.length - 1), r));
    g.fillStyle = gr; g.fillRect(0, 0, 2, 512);
    const bg = new THREE.CanvasTexture(c); bg.colorSpace = THREE.SRGBColorSpace; SAHNE.background = bg;
    const pm = new THREE.PMREMGenerator(RENDERER); SAHNE.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    SAHNE.environmentIntensity = tanim.yansima ?? (tanim.isik === "gece" ? 0.2 : 0.35);
    if (tanim.sis) SAHNE.fog = new THREE.FogExp2(A[A.length - 1], tanim.sis);
    U.kamera = new THREE.PerspectiveCamera(tanim.gorus ?? 35, W / H, 0.1, 400);
    U.kamera.position.set(0, 2, 12); U.kamera.lookAt(0, 1, 0);
    isiklar(tanim.isik ?? "gun");
    const s = { sahne: SAHNE, kamera: U.kamera, ust: UST, THREE, renderer: RENDERER };
    tanim.kur && tanim.kur(s);
    U._s = s;
    try { await document.fonts.load("800 60px Nunito"); } catch (e) {}
    if (U._bekle.length) await Promise.all(U._bekle);
    U.git(0);
    window.HAZIR = true;
    if (U.mod === "oynat") { const t0 = performance.now(); const d = () => { U.git(((performance.now() - t0) / 1000) % U.sure); requestAnimationFrame(d); }; requestAnimationFrame(d); }
    if (U.mod === "gomulu") window.addEventListener("message", (e) => { if (e.data && e.data.komut === "git") U.git(e.data.t); });
    if (window.parent !== window) window.parent.postMessage({ hazir: true, sure: U.sure }, "*");
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", basla); else basla();
};

function isiklar(tur) {
  const gun = tur === "gun", gece = tur === "gece";
  SAHNE.add(new THREE.HemisphereLight(gece ? "#8fa3ff" : "#dfe8ff", gece ? "#1a1430" : "#4a3f3a", gece ? 0.45 : 0.8));
  const g = new THREE.DirectionalLight(gece ? "#b7c6ff" : "#fff1d6", gece ? 1.3 : gun ? 3.2 : 2.4);
  g.position.set(6, 10, 7); g.castShadow = true; g.shadow.mapSize.set(2048, 2048); g.shadow.bias = -0.0005; g.shadow.normalBias = 0.02; g.shadow.radius = 4;
  Object.assign(g.shadow.camera, { left: -12, right: 12, top: 12, bottom: -12, near: 1, far: 50 });
  SAHNE.add(g);
  if (tur === "studyo") { const d = new THREE.DirectionalLight("#bcd4ff", 1.0); d.position.set(-8, 4, -6); SAHNE.add(d); }
  U.gunes = g;
}

U.git = (t) => {
  U.t = t;
  const tn = U._sahne;
  tn.ciz && tn.ciz(t, U._s);
  gecisler(t, tn);
  RENDERER.render(SAHNE, U.kamera);
};

function gecisler(t, tn) {
  const gr = tn.giris ?? "siyah", ck = tn.cikis ?? "siyah", kalan = U.sure - t;
  let op = 0, renk = "#000", clip = "none";
  if (gr === "siyah" || gr === "beyaz") { if (t < 0.4) { op = 1 - U.e.cikis(t / 0.4); renk = gr === "beyaz" ? "#fff" : "#000"; } }
  else if (gr === "devir" && t < 0.45) { op = 1 - U.e.cikis(t / 0.45); renk = U.arka0; }
  if (ck === "siyah" || ck === "beyaz") { if (kalan < 0.4) { op = Math.max(op, 1 - kalan / 0.4); renk = ck === "beyaz" ? "#fff" : "#000"; } }
  else if (ck === "devir") {
    const d = tn.devir || {}, sure = d.sure ?? 1, p = U.sinir((t - (U.sure - sure)) / sure);
    if (p > 0) {
      const hedef = q.get("sonraki") ? "#" + q.get("sonraki") : d.hedef ?? U.arka0;
      const kaynak = new THREE.Color(d.renk ?? "#ffffff"), son = new THREE.Color(hedef);
      const x = (d.x ?? 0.5) * 100, y = (d.y ?? 0.5) * 100, r0 = d.r ?? 6;
      const b = U.e.giris(U.sinir((p - 0.15) / 0.8)) * 0.4 + U.sinir((p - 0.15) / 0.8) * 0.6;
      const r = p < 0.15 ? r0 * (1 - 0.08 * U.e.iki(p / 0.15)) : r0 * 0.92 * Math.pow(130 / (r0 * 0.92), b);
      renk = "#" + kaynak.lerp(son, U.e.iki(U.sinir((p - 0.2) / 0.4))).getHexString(); op = 1;
      clip = `circle(${r.toFixed(2)}vmax at ${x}% ${y}%)`;
    }
  }
  ORTU.style.background = renk; ORTU.style.opacity = op.toFixed(3); ORTU.style.clipPath = clip;
}
