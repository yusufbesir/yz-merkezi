"use strict";
/* Yapay Zeka Merkezi: Tek Asistan arayüzü.
 *
 * Kullanıcı tek bir asistanla konuşur; hangi motorun (Claude / Codex / Gemini) yanıtladığını sunucu seçer ve
 * seçim yanıtın üstünde küçük bir rozet olarak görünür. Yanıt NDJSON akışıyla gelir (POST /api/sor).
 * Eski çoklu pencere yöntemi Ayarlar → Gelişmiş altındadır (gelismis.js).
 */

const $ = (s, kok = document) => kok.querySelector(s);
const $$ = (s, kok = document) => [...kok.querySelectorAll(s)];
const durum = {
  motorlar: [], siteler: [], programlar: [], ayarlar: {}, sohbetler: [],
  sohbet: null,        // açık sohbetin kimliği (yeni sohbette null; ilk yanıtta sunucu verir)
  motorSecimi: "otomatik",
  akis: null,          // sürmekte olan yanıt: { sohbet, kontrol, blok, durduruldu }
};
const mesajKutusu = $("#mesaj");
const mesajlarKutusu = $("#mesajlar");
const icerik = $("#icerik");
const ALTTA_SINIRI = 90;   // px: kullanıcı bu kadar yakınsa "alttadır" ve yanıt akarken otomatik kaydırılır
const bekle = (ms) => new Promise((coz) => setTimeout(coz, ms));

// ---------------------------------------------------------------- oturum
// Oturum belirteci bu sayfaya HİÇ gelmez: sunucu, Edge'i tek kullanımlık açılış koduyla (/ac/<kod>) açar ve belirteci
// HttpOnly; SameSite=Strict çerezine koyar. /api/ istekleri yalnızca bu çerezle (aynı köken) gider.

// ---------------------------------------------------------------- yardımcılar

async function api(yol, govde) {
  const secenek = govde === undefined ? { credentials: "same-origin" }
    : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(govde) };
  const yanit = await fetch(yol, secenek);
  const veri = await yanit.json().catch(() => ({}));
  if (!yanit.ok || veri.hata) throw new Error(veri.hata || `Sunucu hatası (${yanit.status})`);
  return veri;
}

let bildirimZamani;
function bildir(metin, sure = 4000) {
  const k = $("#bildirim");
  k.textContent = metin; k.hidden = false;
  clearTimeout(bildirimZamani);
  bildirimZamani = setTimeout(() => { k.hidden = true; }, sure);
}

function durumSatiri(metin, hata = false) {
  const k = $("#durumSatiri");
  k.textContent = metin; k.classList.toggle("hata", hata);
}
const VARSAYILAN_NOT = "Enter gönderir, Shift+Enter yeni satır açar.";

function el(etiket, sinif, metin) {
  const e = document.createElement(etiket);
  if (sinif) e.className = sinif;
  if (metin !== undefined) e.textContent = metin;
  return e;
}

function dugme(metin, sinif, tikla, baslik) {
  const d = el("button", sinif, metin);
  d.type = "button";
  if (baslik) d.title = baslik;
  if (tikla) d.addEventListener("click", tikla);
  return d;
}

function nokta(renk) {
  const n = el("span", "nokta");
  if (renk) n.style.background = renk;
  return n;
}

async function kopyala(metin, bildirimMetni = "Kopyalandı.") {
  try { await navigator.clipboard.writeText(metin); bildir(bildirimMetni, 1800); return true; }
  catch (_) { bildir("Kopyalanamadı."); return false; }
}

function sureMetni(sn) {
  if (typeof sn !== "number" || !isFinite(sn) || sn <= 0) return "";
  return sn < 10 ? `${sn.toFixed(1).replace(".", ",")} sn` : `${Math.round(sn)} sn`;
}

const motorBul = (id) => durum.motorlar.find((m) => m.id === id);
// "Codex (ChatGPT)" -> "Codex": rozet ve satırlarda kısa ad
const kisaMotorAdi = (ad) => String(ad || "").replace(/\s*\(.*\)\s*/, "").trim();
// "Claude Sonnet 5.5" -> "Sonnet 5.5": motor adı rozette zaten var
function kisaModelAdi(modelAdi, motorAdi) {
  const m = String(modelAdi || "").trim();
  const on = kisaMotorAdi(motorAdi).toLowerCase();
  return on && m.toLowerCase().startsWith(on + " ") ? m.slice(on.length + 1) : m;
}

function motorDurumu(m) {
  if (!m) return { sinif: "yok", etiket: "Bilinmiyor" };
  if (m.hazir) return { sinif: "hazir", etiket: "Hazır" };
  if (m.giris === false) return { sinif: "giris", etiket: "Giriş gerekli" };
  return { sinif: "yok", etiket: "Kurulu değil" };
}

function temayiUygula() {
  const t = durum.ayarlar.tema || "sistem";
  const koyu = t === "koyu" || (t === "sistem" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.tema = koyu ? "koyu" : "acik";
  document.documentElement.dataset.yazi = durum.ayarlar.yazi_boyutu || "orta";
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", temayiUygula);

function selamla() {
  const saat = new Date().getHours();
  const selam = saat < 6 ? "İyi geceler" : saat < 12 ? "Günaydın" : saat < 18 ? "İyi günler" : "İyi akşamlar";
  const ad = (durum.ayarlar.ad || "").trim();
  $("#selam").textContent = ad ? `${selam}, ${ad}` : selam;
  $("#kullaniciAd").textContent = ad || "Ben";
  $("#avatar").textContent = (ad || "B")[0].toUpperCase();
}

// ---------------------------------------------------------------- açılır katman (motor notu, menüler)

const acilir = $("#acilir");
let acilirCapa = null;

function acilirKapat() {
  acilir.hidden = true; acilir.classList.remove("gorunur"); acilir.replaceChildren();
  acilirCapa = null;
}

/** capa'nın yanında açılır katman gösterir; aynı çapaya yeniden tıklanırsa kapatır. yer: "ust" | "alt" */
function acilirGoster(capa, icerikDugumu, yer = "alt", hiza = "sol") {
  if (!acilir.hidden && acilirCapa === capa) { acilirKapat(); return; }
  acilir.replaceChildren(icerikDugumu);
  acilir.hidden = false; acilirCapa = capa;
  acilir.style.top = "0px"; acilir.style.left = "0px";
  const r = capa.getBoundingClientRect(), w = acilir.offsetWidth, h = acilir.offsetHeight;
  let ust = yer === "ust" ? r.top - h - 8 : r.bottom + 8;
  if (ust < 8) ust = r.bottom + 8;
  if (ust + h > innerHeight - 8) ust = Math.max(8, r.top - h - 8);
  let sol = hiza === "sag" ? r.right - w : r.left;
  sol = Math.max(8, Math.min(sol, innerWidth - w - 8));
  acilir.style.top = `${Math.round(ust)}px`; acilir.style.left = `${Math.round(sol)}px`;
  requestAnimationFrame(() => acilir.classList.add("gorunur"));
}
document.addEventListener("pointerdown", (e) => {
  if (acilir.hidden || acilir.contains(e.target) || (acilirCapa && acilirCapa.contains(e.target))) return;
  acilirKapat();
});

function menuOgesi(simge, ad, aciklama, secili, tikla, soluk = false) {
  const d = el("button", `menu-oge${soluk ? " soluk-oge" : ""}`);
  d.type = "button";
  d.append(simge, (() => { const y = el("span", "menu-yazi"); y.append(el("b", "", ad)); if (aciklama) y.append(el("small", "", aciklama)); return y; })(),
    el("span", "menu-tik", secili ? "✓" : ""));
  d.addEventListener("click", () => { acilirKapat(); tikla(); });
  return d;
}

// ---------------------------------------------------------------- motorlar: durum, not, seçici

const MOTOR_KURULUM = {
  claude: { kur: "npm install -g @anthropic-ai/claude-code", giris: "claude", girisAciklama: "Açılan ekranda /login yazıp Claude hesabınla giriş yap." },
  codex: { kur: "npm install -g @openai/codex", giris: "codex login", girisAciklama: "Açılan sayfada ChatGPT hesabınla giriş yap." },
  gemini: { kur: "npm install -g @google/gemini-cli", giris: "gemini", girisAciklama: "İlk açılışta Google hesabınla giriş yap." },
};

function komutSatiri(komut) {
  const s = el("div", "komut-satir");
  s.append(el("code", "", komut), dugme("Kopyala", "kucuk-dugme", () => kopyala(komut)));
  return s;
}

/** Bir motorun durumunu ve ne yapılacağını anlatan not (kenar çubuğu, karşılama ve Ayarlar → Motorlar'da ortak). */
function motorNotu(m, ayrinti = true) {
  const d = motorDurumu(m), k = MOTOR_KURULUM[m.id];
  const kok = el("div", "motor-not");
  const baslik = el("div", "motor-not-baslik");
  baslik.append(nokta(m.renk), el("b", "", m.ad), el("span", `etiket ${d.sinif}`, d.etiket));
  kok.append(baslik);
  if (d.sinif === "hazir") {
    kok.append(el("p", "", `${kisaMotorAdi(m.ad)} yanıt vermeye hazır.${m.surum ? ` Sürüm: ${m.surum}.` : ""}`));
  } else if (d.sinif === "giris") {
    kok.append(el("p", "", `${kisaMotorAdi(m.ad)} kurulu ama henüz giriş yapılmamış. Bir kez giriş yapman yeterli:`));
    const adimlar = el("ol");
    adimlar.append(el("li", "", "Başlat menüsünden bir terminal (PowerShell) aç."));
    const li = el("li", "", "Şu komutu çalıştır:"); li.append(komutSatiri(k.giris)); adimlar.append(li);
    adimlar.append(el("li", "", k.girisAciklama), el("li", "", "Buraya dön ve \"Yeniden denetle\"ye bas."));
    kok.append(adimlar);
  } else {
    kok.append(el("p", "", `${kisaMotorAdi(m.ad)} bulunamadı. Kurmak için (Node.js gerekir):`));
    kok.append(komutSatiri(k.kur));
    kok.append(el("p", "", "Kurulumdan sonra giriş yap:"), komutSatiri(k.giris), el("p", "soluk", k.girisAciklama));
  }
  if (ayrinti && m.sebep && d.sinif !== "hazir") kok.append(el("p", "soluk motor-sebep", m.sebep));
  const alt = el("div", "motor-not-alt");
  alt.append(dugme("Yeniden denetle", "kucuk-dugme", async (e) => {
    const d2 = e.currentTarget; d2.disabled = true; d2.textContent = "Denetleniyor…";
    try { await yenile(true); } catch (h) { bildir(h.message); }
    acilirKapat();
  }));
  kok.append(alt);
  return kok;
}

function motorSatiriCiz(m, sinif = "kenar-motor") {
  const d = motorDurumu(m);
  const satir = el("button", sinif);
  satir.type = "button";
  satir.dataset.motor = m.id;
  satir.append(el("span", `durum-nokta ${d.sinif}`), el("span", "ad", kisaMotorAdi(m.ad)), el("span", `durum ${d.sinif}`, d.etiket));
  satir.title = d.sinif === "hazir" ? "Hazır. Ayrıntı için tıkla." : "Ne yapman gerektiğini görmek için tıkla.";
  satir.addEventListener("click", () => acilirGoster(satir, motorNotu(m), "ust"));
  return satir;
}

function motorlariCiz() {
  const kenar = $("#kenarMotorlar");
  kenar.replaceChildren(...durum.motorlar.map((m) => motorSatiriCiz(m)));
  // karşılama: üç motorun durumu tek satırda
  const kars = $("#karsilamaMotorlar");
  kars.replaceChildren(...durum.motorlar.map((m) => {
    const d = motorDurumu(m);
    const c = el("button", `motor-cip ${d.sinif}`);
    c.type = "button";
    c.append(el("span", `durum-nokta ${d.sinif}`), el("b", "", kisaMotorAdi(m.ad)), el("span", "", d.etiket.toLowerCase()));
    c.addEventListener("click", () => acilirGoster(c, motorNotu(m), "alt"));
    return c;
  }));
  const hazir = durum.motorlar.filter((m) => m.hazir).length;
  const not = $("#karsilamaNot");
  not.hidden = !durum.motorlar.length || hazir > 0;
  not.textContent = "Hiçbir motor hazır değil. Yukarıdan bir motora tıklayıp ne yapman gerektiğini gör.";
  motorSeciciCiz();
}

function motorSeciciCiz() {
  const sec = durum.motorSecimi;
  const m = sec === "otomatik" ? null : motorBul(sec);
  $("#motorOzet").textContent = m ? kisaMotorAdi(m.ad) : "Otomatik";
  const n = $("#motorNokta");
  n.className = m ? "nokta" : "nokta otomatik";
  n.style.background = m ? m.renk : "";
}

function motorMenusuAc() {
  const kok = el("div", "menu-liste");
  kok.append(el("div", "menu-baslik", "Yanıtlayan motor"));
  const sec = durum.motorSecimi;
  const oto = el("span", "nokta otomatik");
  kok.append(menuOgesi(oto, "Otomatik", "Her mesaj için en uygununu seçer", sec === "otomatik", () => motorSec("otomatik")));
  for (const m of durum.motorlar) {
    const d = motorDurumu(m);
    kok.append(menuOgesi(nokta(m.renk), kisaMotorAdi(m.ad), d.etiket, sec === m.id, () => motorSec(m.id), d.sinif !== "hazir"));
  }
  acilirGoster($("#motorDugme"), kok, "ust", "sol");
}

function motorSec(id) {
  durum.motorSecimi = id;
  motorSeciciCiz();
  durum.ayarlar.varsayilan_motor = id;
  api("/api/ayar", { varsayilan_motor: id }).catch((h) => bildir(h.message));
  mesajKutusu.focus();
}

// ---------------------------------------------------------------- durum yenileme

let yenileniyor = null;
async function yenile(motorYenile = false) {
  if (yenileniyor && !motorYenile) return yenileniyor;
  const is = (async () => {
    const v = await api("/api/durum" + (motorYenile ? "?motor_yenile=1" : ""));
    Object.assign(durum, { programlar: v.programlar || [], siteler: v.siteler || [], ayarlar: v.ayarlar || {},
      sohbetler: v.sohbetler || [], motorlar: v.motorlar || [] });
    if (v.uyari && v.uyari !== durum.gosterilenUyari) { durum.gosterilenUyari = v.uyari; bildir(v.uyari, 15000); }
    if (!durum.motorSecimiBelirlendi) {
      durum.motorSecimi = ["otomatik", "claude", "codex", "gemini"].includes(durum.ayarlar.varsayilan_motor)
        ? durum.ayarlar.varsayilan_motor : "otomatik";
      durum.motorSecimiBelirlendi = true;
    }
    temayiUygula(); selamla(); motorlariCiz(); sohbetListesiCiz(); ayarlariDoldur();
    if (typeof gelismisCiz === "function") gelismisCiz();
    if (!$("#ayarlar").open || $('.ayarlar-sekmeler .aktif')?.dataset.sekme !== "motorlar") return;
    motorAyarlariniCiz();
  })();
  yenileniyor = is;
  try { await is; } finally { yenileniyor = null; }
}

// ---------------------------------------------------------------- kenar çubuğu: sohbet listesi

function sohbetZamani(s) {
  const t = Date.parse(s.guncelleme || s.zaman || "");
  return Number.isFinite(t) ? t : 0;
}

function grupAdi(t) {
  if (!t) return "Daha eski";
  const bugun = new Date(); bugun.setHours(0, 0, 0, 0);
  const gun = 86400000, fark = Math.floor((bugun.getTime() - t) / gun) + (t >= bugun.getTime() ? 0 : 1);
  if (t >= bugun.getTime()) return "Bugün";
  if (t >= bugun.getTime() - gun) return "Dün";
  if (t >= bugun.getTime() - 7 * gun) return "Son 7 gün";
  return fark > 30 ? "Daha eski" : "Son 30 gün";
}

function sohbetListesiCiz() {
  const alan = $("#sohbetListesi");
  const suzgec = $("#ara").value.trim().toLocaleLowerCase("tr");
  const eslesir = (s) => !suzgec || (s.baslik || "").toLocaleLowerCase("tr").includes(suzgec)
    || s.mesajlar.some((m) => (m.metin || "").toLocaleLowerCase("tr").includes(suzgec)
      || Object.values(m.yanitlar || {}).some((y) => String(y).toLocaleLowerCase("tr").includes(suzgec)));
  const liste = durum.sohbetler.filter(eslesir).sort((a, b) => sohbetZamani(b) - sohbetZamani(a));
  const parca = document.createDocumentFragment();
  let sonGrup = null;
  for (const s of liste) {
    const g = grupAdi(sohbetZamani(s));
    if (g !== sonGrup) { parca.append(el("div", "sohbet-grup", g)); sonGrup = g; }
    const satir = el("div", `sohbet-satir${s.id === durum.sohbet ? " aktif" : ""}`);
    satir.dataset.sohbet = s.id;
    satir.append(el("span", "ad", s.baslik || "Sohbet"));
    const sil = dugme("✕", "sil", (e) => { e.stopPropagation(); sohbetSilOnayi(s, sil); }, "Sohbeti sil");
    satir.append(sil);
    satir.addEventListener("click", () => sohbetAc(s.id));
    parca.append(satir);
  }
  if (!liste.length) parca.append(el("div", "sohbet-bos", suzgec ? "Eşleşen sohbet yok." : "Henüz sohbet yok."));
  alan.replaceChildren(parca);
}

function sohbetSilOnayi(s, capa) {
  const kok = el("div", "onay-kutusu");
  kok.append(el("p", "", `"${s.baslik}" sohbeti silinsin mi?`));
  const alt = el("div", "onay-dugmeleri");
  alt.append(dugme("Vazgeç", "", acilirKapat),
    dugme("Sil", "tehlike", async () => {
      acilirKapat();
      try {
        const v = await api("/api/sohbet-sil", { id: s.id });
        durum.sohbetler = v.sohbetler;
        if (durum.sohbet === s.id) yeniSohbet();
        sohbetListesiCiz();
      } catch (h) { bildir(h.message); }
    }));
  kok.append(alt);
  acilirGoster(capa, kok, "alt", "sag");
}

// ---------------------------------------------------------------- mesaj çizimi

const hareketAzalt = matchMedia("(prefers-reduced-motion: reduce)");

function altta() {
  return icerik.scrollHeight - icerik.scrollTop - icerik.clientHeight <= ALTTA_SINIRI;
}

function sonaKaydir() {
  icerik.scrollTop = icerik.scrollHeight;
  asagiDugmesiniGuncelle();
}

function asagiDugmesiniGuncelle() {
  $("#asagiGit").hidden = altta() || !mesajlarKutusu.children.length;
}

function girisAnimasyonu(dugum) {
  if (!hareketAzalt.matches) {
    dugum.classList.add("girer");
    dugum.addEventListener("animationend", () => dugum.classList.remove("girer"), { once: true });
  }
  return dugum;
}

function kullaniciBalonu(m) {
  const kok = el("div", "mesaj kullanici");
  kok.append(el("div", "balon", m.metin));
  const ek = el("div", "ek");
  if (m.zaman) ek.append(el("span", "", m.zaman));
  ek.append(dugme("Kopyala", "", () => kopyala(m.metin), "Mesajı kopyala"));
  kok.append(ek);
  if (m.baglam) {
    const b = el("details", "baglam");
    b.append(el("summary", "", `Hafızadan eklenen bağlam (${m.baglam.karakter ?? (m.baglam.metin || "").length} karakter)`),
      el("pre", "", m.baglam.metin || ""));
    kok.append(b);
  }
  return kok;
}

/** Asistan yanıtı: solda, üstte motor rozeti; yanıt rAF ile toplanarak akar (titreme yok). */
function asistanBlogu(soru = "") {
  const kok = el("div", "mesaj asistan");
  const ust = el("div", "asistan-ust");
  const rozet = el("span", "motor-rozet"); rozet.hidden = true;
  const degistir = el("span", "rozet-eylem");
  ust.append(rozet, degistir);
  const durumSatiri_ = el("div", "asistan-durum"); durumSatiri_.hidden = true;
  const dusunuyor = el("div", "dusunuyor");
  dusunuyor.append(el("span"), el("span"), el("span"));
  const govde = el("div", "asistan-govde"); govde.hidden = true;
  const hata = el("div", "asistan-hata"); hata.hidden = true;
  const alt = el("div", "asistan-alt"); alt.hidden = true;
  kok.append(ust, durumSatiri_, dusunuyor, govde, hata, alt);

  const b = {
    kok, soru, metin: "", secim: null, yaziyor: false, planli: false,
    rozetKoy(s) {
      b.secim = s;
      if (!s.motor) return;
      const renk = s.renk || (motorBul(s.motor) || {}).renk || "#888";
      rozet.style.setProperty("--motor", renk);
      rozet.replaceChildren(nokta(renk), el("b", "", kisaMotorAdi(s.motor_ad)));
      const model = kisaModelAdi(s.model_ad || s.model, s.motor_ad);
      if (model) rozet.append(el("span", "rozet-model", ` · ${model}`));
      rozet.title = s.sebep ? `${s.sebep}${s.kaynak === "jev" ? " (Jev)" : ""}` : "";
      rozet.hidden = false;
      girisAnimasyonu(rozet);
    },
    durum(metin) {
      durumSatiri_.textContent = metin; durumSatiri_.hidden = !metin;
    },
    yaz(metin, yaziyor) {
      b.metin = metin; b.yaziyor = yaziyor;
      if (b.planli) return;
      b.planli = true;
      requestAnimationFrame(b.ciz);
    },
    ciz() {
      b.planli = false;
      const alttaydi = altta();
      if (b.metin) { dusunuyor.hidden = true; govde.hidden = false; mdDom(govde, b.metin); }
      imlegiDuzenle(govde, b.yaziyor && Boolean(b.metin));
      if (alttaydi) sonaKaydir(); else asagiDugmesiniGuncelle();
    },
    hataKoy(mesaj) {
      dusunuyor.hidden = true;
      hata.textContent = mesaj; hata.hidden = false;
    },
    bitir({ sure, durduruldu, yenidenSorulabilir = false } = {}) {
      b.yaziyor = false;
      b.ciz();
      dusunuyor.hidden = true;
      if (durduruldu) alt.append(el("span", "alt-not", "Yanıt durduruldu."));
      if (b.metin) alt.append(dugme("Kopyala", "", () => kopyala(b.metin), "Yanıtı kopyala"));
      if (yenidenSorulabilir && b.soru) {
        const yd = dugme("Yeniden sor ▾", "yeniden-sor", () => yenidenSorMenusu(yd, b), "Aynı soruyu başka bir motora sor");
        alt.append(yd);
      }
      const s = sureMetni(sure);
      if (s) alt.append(el("span", "alt-not", s));
      alt.hidden = !alt.children.length;
      if (!alt.hidden) girisAnimasyonu(alt);
    },
  };
  return b;
}

// Akarken metnin sonunda yumuşak yanıp sönen imleç: son metin öğesinin içine konur.
function imlegiDuzenle(govde, goster) {
  const eski = govde.querySelector(":scope .imlec-kutu, .imlec-kutu");
  if (eski) eski.remove();
  if (!goster) return;
  let hedef = govde.lastElementChild;
  while (hedef && hedef.lastElementChild && /^(UL|OL|LI|BLOCKQUOTE)$/.test(hedef.tagName)) hedef = hedef.lastElementChild;
  const imlec = el("span", "imlec-kutu");
  imlec.append(el("span", "imlec"));
  if (hedef && /^(P|H[1-6]|LI)$/.test(hedef.tagName)) hedef.append(imlec); else govde.append(imlec);
}

function yenidenSorMenusu(capa, blok) {
  const kok = el("div", "menu-liste");
  kok.append(el("div", "menu-baslik", "Yeniden sor"));
  kok.append(menuOgesi(el("span", "nokta otomatik"), "Otomatik", "En uygun motoru yeniden seçtir", false,
    () => yenidenSor(blok, "otomatik")));
  const kullanilan = blok.secim && blok.secim.motor;
  for (const m of durum.motorlar) {
    const d = motorDurumu(m);
    kok.append(menuOgesi(nokta(m.renk), `Yeniden sor: ${kisaMotorAdi(m.ad)}`,
      m.id === kullanilan ? "Şu an yanıtlayan" : d.etiket, false, () => yenidenSor(blok, m.id), d.sinif !== "hazir"));
  }
  acilirGoster(capa, kok, "ust", "sol");
}

function yenidenSor(blok, motor) {
  if (durum.akis) return bildir("Önce süren yanıtın bitmesini bekle ya da Durdur'a bas.");
  blok.kok.remove();
  gonder({ metin: blok.soru, motor, yeniden: true });
}

function sonYenidenSorGorunumu() {
  // yalnızca son asistan yanıtında "Yeniden sor" gösterilir (sunucu son soru-yanıt çiftini değiştirir)
  $$(".mesaj.asistan .yeniden-sor", mesajlarKutusu).forEach((d, i, tum) => { d.hidden = i !== tum.length - 1; });
}

function gecmisMesajiCiz(m, soruMetni) {
  if (m.rol === "asistan") {
    const b = asistanBlogu(soruMetni);
    const motor = motorBul(m.motor);
    if (m.motor) b.rozetKoy({ motor: m.motor, motor_ad: motor ? motor.ad : m.motor, renk: motor && motor.renk,
      model: m.model, model_ad: m.model_ad || m.model });
    b.metin = m.metin || "";
    if (b.metin) b.ciz();
    if (m.hata) b.hataKoy(m.hata);
    b.bitir({ sure: m.sure, durduruldu: m.durduruldu, yenidenSorulabilir: true });
    return [b.kok];
  }
  const kutu = kullaniciBalonu(m);
  const dugumler = [kutu];
  // eski çoklu pencere kayıtları: site yanıtları salt okunur gösterilir
  for (const [siteId, metin] of Object.entries(m.yanitlar || {})) {
    const site = durum.siteler.find((s) => s.id === siteId);
    const b = asistanBlogu();
    b.rozetKoy({ motor: siteId, motor_ad: site ? site.ad : siteId, renk: site ? site.renk : "#888", sebep: "Eski çoklu pencere kaydı" });
    b.metin = String(metin); b.ciz(); b.bitir();
    dugumler.push(b.kok);
  }
  return dugumler;
}

// ---------------------------------------------------------------- sohbet açma / yeni sohbet

function sohbetBasligi() {
  const s = durum.sohbetler.find((x) => x.id === durum.sohbet);
  return s ? s.baslik : "Yeni sohbet";
}

function sohbetAc(id) {
  if (durum.akis) return bildir("Yanıt sürerken sohbet değiştirilemez. Durdur'a bas ya da bitmesini bekle.");
  durum.sohbet = id;
  const s = durum.sohbetler.find((x) => x.id === id);
  $("#ustBaslik").textContent = s ? s.baslik : "Yeni sohbet";
  $("#karsilama").hidden = Boolean(s && s.mesajlar.length);
  mesajlarKutusu.replaceChildren();
  let soru = "";
  for (const m of (s ? s.mesajlar : [])) {
    if (m.rol !== "asistan") soru = m.metin || "";
    for (const d of gecmisMesajiCiz(m, soru)) mesajlarKutusu.append(d);
  }
  sonYenidenSorGorunumu();
  sohbetListesiCiz();
  sonaKaydir();
  mesajKutusu.focus();
}

function yeniSohbet() {
  if (durum.akis) return bildir("Yanıt sürerken yeni sohbet açılamaz. Durdur'a bas ya da bitmesini bekle.");
  hassasSeridiGizle();
  sohbetAc(null);
}

// ---------------------------------------------------------------- gönderme ve akış

function mesgulYap(mesgul) {
  $("#gonder").hidden = mesgul;
  $("#durdur").hidden = !mesgul;
  $("#gonder").disabled = mesgul;
  document.body.classList.toggle("yanit-suruyor", mesgul);
}

async function akisiOku(yanit, isle) {
  const okuyucu = yanit.body.getReader(), cozucu = new TextDecoder("utf-8");
  let tampon = "";
  const satirlariIsle = (son) => {
    let i;
    while ((i = tampon.indexOf("\n")) >= 0) {
      const satir = tampon.slice(0, i).trim(); tampon = tampon.slice(i + 1);
      if (!satir) continue;
      let olay;
      try { olay = JSON.parse(satir); } catch (_) { continue; }
      isle(olay);
    }
    if (son && tampon.trim()) { try { isle(JSON.parse(tampon.trim())); } catch (_) { /* yarım satır */ } tampon = ""; }
  };
  for (;;) {
    const { done, value } = await okuyucu.read();
    if (done) break;
    tampon += cozucu.decode(value, { stream: true });
    satirlariIsle(false);
  }
  tampon += cozucu.decode();
  satirlariIsle(true);
}

/**
 * Mesajı sunucuya gönderip yanıtı akıtır.
 * yeniden: aynı soru başka bir motora yeniden sorulur (sunucu son soru-yanıt çiftini değiştirir); onayli: hassas uyarıda "Yine de gönder".
 * baglamKarari: "ekle" | "ekleme" (hafıza bağlamı onay panelinden); baglamKimligi: sunucunun gösterdiği bağlamın kimliği.
 */
async function gonder({ metin = null, motor = null, yeniden = false, onayli = false, baglamKarari = null, baglamKimligi = null } = {}) {
  metin = (metin ?? mesajKutusu.value).trim();
  if (!metin || durum.akis) return;
  motor = motor || durum.motorSecimi;
  hassasSeridiGizle();
  durumSatiri(VARSAYILAN_NOT);
  const bosSohbetti = !mesajlarKutusu.children.length;
  $("#karsilama").hidden = true;

  let kullaniciDugumu = null;
  if (!yeniden) {
    kullaniciDugumu = girisAnimasyonu(kullaniciBalonu({ metin, zaman: new Date().toTimeString().slice(0, 5) }));
    mesajlarKutusu.append(kullaniciDugumu);
  }
  const blok = asistanBlogu(metin);
  mesajlarKutusu.append(girisAnimasyonu(blok.kok));
  sonaKaydir();
  if (!yeniden) { mesajKutusu.value = ""; boyutla(); }

  const kontrol = new AbortController();
  const akis = { sohbet: durum.sohbet, kontrol, blok, durduruldu: false };
  durum.akis = akis;
  mesgulYap(true);

  let toplam = "", bitti = null, hataVar = false, onayIstendi = false;
  const isle = (o) => {
    switch (o.tur) {
      case "onay_gerekli":
        onayIstendi = true;
        blok.kok.remove();
        if (kullaniciDugumu) kullaniciDugumu.remove();
        if (bosSohbetti) $("#karsilama").hidden = false;
        if (!yeniden) { mesajKutusu.value = metin; boyutla(); }
        hassasSeridiGoster(o, { metin, motor, yeniden });
        break;
      case "baglam_onay":
        onayIstendi = true;
        blok.kok.remove();
        if (kullaniciDugumu) kullaniciDugumu.remove();
        if (bosSohbetti) $("#karsilama").hidden = false;
        if (!yeniden) { mesajKutusu.value = metin; boyutla(); }
        baglamOnayiGoster(o, { metin, motor, yeniden, onayli });
        break;
      case "hassas_uyari":
        durumSatiri(`Not: bu mesaj ${o.aciklama} içeriyor; seçilen motorun şirketine gidecek.`);
        break;
      case "kayit":
        // Geçmişe maskeli yazılan metinleri göster (ham anahtar/parola ekranda kalmasın).
        if (kullaniciDugumu && typeof o.kullanici_metin === "string") {
          const balon = kullaniciDugumu.querySelector(".balon");
          if (balon) balon.textContent = o.kullanici_metin;
        }
        if (typeof o.asistan_metin === "string" && o.asistan_metin) toplam = o.asistan_metin;
        break;
      case "secim":
        if (o.jev_notu) durumSatiri(`Yönlendirme: ${o.jev_notu}.`);
        if (o.sohbet && !durum.sohbet) {
          durum.sohbet = o.sohbet; akis.sohbet = o.sohbet;
          $("#ustBaslik").textContent = metin.split("\n")[0].slice(0, 48);
        } else if (o.sohbet) akis.sohbet = o.sohbet;
        blok.rozetKoy(o);
        break;
      case "durum": blok.durum(o.metin); break;
      case "parca": toplam += o.metin || ""; blok.yaz(toplam, true); break;
      case "bitti":
        bitti = o;
        if (typeof o.metin === "string" && o.metin) toplam = o.metin;
        break;
      case "hata": hataVar = true; blok.hataKoy(o.mesaj || "Bilinmeyen hata."); break;
      default: break;
    }
  };

  try {
    const yanit = await fetch("/api/sor", {
      method: "POST", signal: kontrol.signal,
      credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ metin, sohbet: durum.sohbet, motor, ...(yeniden ? { yeniden: true } : {}), ...(onayli ? { onayli: true } : {}),
        ...(baglamKarari ? { baglam_karari: baglamKarari } : {}), ...(baglamKimligi ? { baglam_kimligi: baglamKimligi } : {}) }),
    });
    if (!yanit.ok) {
      const v = await yanit.json().catch(() => ({}));
      throw new Error(v.hata || `Sunucu hatası (${yanit.status})`);
    }
    await akisiOku(yanit, isle);
    if (!onayIstendi) {
      blok.yaz(toplam, false);
      blok.bitir({ sure: bitti && bitti.sure, durduruldu: akis.durduruldu, yenidenSorulabilir: true });
      if (!toplam && !hataVar && !akis.durduruldu) blok.hataKoy("Yanıt gelmedi.");
    }
  } catch (h) {
    if (!onayIstendi) {
      blok.yaz(toplam, false);
      if (akis.durduruldu || h.name === "AbortError") blok.bitir({ durduruldu: true, yenidenSorulabilir: true });
      else { blok.hataKoy(`Bağlantı sorunu: ${h.message}`); blok.bitir({ yenidenSorulabilir: true }); }
    }
  } finally {
    durum.akis = null;
    mesgulYap(false);
    sonYenidenSorGorunumu();
    if (!onayIstendi) mesajKutusu.focus();
    yenile().catch(() => {});
  }
}

async function yaniDurdur() {
  const akis = durum.akis;
  if (!akis || akis.durduruldu) return;
  akis.durduruldu = true;
  $("#durdur").disabled = true;
  try { await api("/api/durdur", { sohbet: akis.sohbet || null }); } catch (_) { /* akış zaten bitmiş olabilir */ }
  // motor iptali birkaç saniyede işlemezse bağlantı kapatılır; sunucu kısmi yanıtı yine de kaydeder
  setTimeout(() => { if (durum.akis === akis) akis.kontrol.abort(); }, 3500);
}

// ---------------------------------------------------------------- hassas bilgi uyarısı

const hassasSeridi = $("#hassasSeridi");
let hassasMetin = null;

function hassasSeridiGizle() {
  hassasMetin = null;
  hassasSeridi.hidden = true;
  hassasSeridi.replaceChildren();
}

// Sunucu mesajda API anahtarı, parola, kimlik/IBAN/kart numarası kalıbı bulursa hiçbir şey göndermez ve onay ister.
// Şerit görünürken metin değişirse onay geçersiz sayılır ("Yine de gönder" metni yeniden denetletir).
function hassasSeridiGoster(o, istek) {
  hassasMetin = istek.metin;
  const satir = el("div", "hassas-satir");
  const yine = dugme("Yine de gönder", "", () => {
    const degisti = mesajKutusu.value.trim() !== hassasMetin && !istek.yeniden;
    hassasSeridiGizle();
    if (degisti) { durumSatiri("Metin değişti; yeniden denetleniyor."); gonder({ motor: istek.motor }); }
    else gonder({ metin: istek.metin, motor: istek.motor, yeniden: istek.yeniden, onayli: true });
  });
  const vazgec = dugme("Vazgeç", "", () => { hassasSeridiGizle(); durumSatiri("Gönderme iptal edildi."); mesajKutusu.focus(); });
  satir.append(el("span", "", `Bu mesaj ${o.aciklama} içeriyor olabilir. Seçilen motorun şirketine gideceği için göndermeden önce emin ol.`), yine, vazgec);
  hassasSeridi.replaceChildren(satir);
  hassasSeridi.hidden = false;
  durumSatiri("Göndermeden önce onay gerekiyor.", true);
}

// ---------------------------------------------------------------- hafıza bağlamı onayı

// Hafıza OS bağlamı motora (dış sunucuya) gitmeden önce gösterilir: Ekleyerek gönder / Bağlamsız gönder / Vazgeç.
// Ayarlar → Hafıza → "Hafıza bağlamı için her seferinde onay iste" kapalıysa sunucu bu olayı hiç göndermez.
function baglamOnayiGoster(o, istek) {
  hassasMetin = istek.metin;
  const kutu = el("div", "hassas-satir baglam-onay");
  const ayrinti = el("details", "baglam");
  ayrinti.open = true;
  ayrinti.append(el("summary", "", `Hafızadan şu bağlam eklenecek (${o.karakter ?? (o.baglam || "").length} karakter)`),
    el("pre", "", o.baglam || ""));
  const tekrar = (karar) => () => {
    const degisti = mesajKutusu.value.trim() !== hassasMetin && !istek.yeniden;
    hassasSeridiGizle();
    if (degisti) { durumSatiri("Metin değişti; yeniden denetleniyor."); gonder({ motor: istek.motor }); return; }
    gonder({ metin: istek.metin, motor: istek.motor, yeniden: istek.yeniden, onayli: istek.onayli,
      baglamKarari: karar, baglamKimligi: karar === "ekle" ? o.baglam_kimligi : null });
  };
  const ekle = dugme("Ekleyerek gönder", "", tekrar("ekle"));
  const eklemeden = dugme("Bağlamsız gönder", "", tekrar("ekleme"));
  const vazgec = dugme("Vazgeç", "", () => { hassasSeridiGizle(); durumSatiri("Gönderme iptal edildi."); mesajKutusu.focus(); });
  const dugmeler = el("div", "baglam-dugmeler");
  dugmeler.append(ekle, eklemeden, vazgec);
  kutu.append(ayrinti, dugmeler);
  hassasSeridi.replaceChildren(kutu);
  hassasSeridi.hidden = false;
  durumSatiri("Hafıza bağlamı dışarı gitmeden önce onay gerekiyor.", true);
}

// ---------------------------------------------------------------- ayarlar penceresi

const ONAY_ANAHTARI_ESKI = "yzm.cokluHedefOnayi";
function yerelOku(anahtar) { try { return localStorage.getItem(anahtar); } catch (_) { return null; } }
function yerelYaz(anahtar, deger) {
  try { if (deger === null) localStorage.removeItem(anahtar); else localStorage.setItem(anahtar, deger); } catch (_) { /* saklanamazsa varsayılan kalır */ }
}

function ayarlariDoldur() {
  const a = durum.ayarlar;
  $("#ayarAd").value = a.ad || "";
  $("#ayarVarsayilanMotor").value = durum.motorSecimi;
  $("#ayarHassasUyari").checked = a.hassas_uyari !== false;
  $("#ayarEnter").checked = Boolean(a.enter_bas);
  $("#ayarYerlesim").value = a.yerlesim || "sol";
  $("#ayarJevPuanla").checked = Boolean(a.jev_yanit_puanla);
  $$("#ayarTema button").forEach((b) => b.classList.toggle("aktif", b.dataset.deger === (a.tema || "sistem")));
  $$("#ayarYazi button").forEach((b) => b.classList.toggle("aktif", b.dataset.deger === (a.yazi_boyutu || "orta")));
}

async function ayarKaydet(degisiklik) {
  Object.assign(durum.ayarlar, degisiklik);
  temayiUygula(); selamla(); ayarlariDoldur();
  try { await api("/api/ayar", degisiklik); } catch (h) { bildir(h.message); }
}

function ayarlarAc(sekme = "genel") {
  acilirKapat();
  ayarlariDoldur();
  sekmeSec(sekme);
  $("#ayarlar").showModal();
}

const SEKME_ACILISLARI = {};
function sekmeSec(ad) {
  $$(".ayarlar-sekmeler button").forEach((b) => b.classList.toggle("aktif", b.dataset.sekme === ad));
  $$(".ayarlar-icerik section").forEach((s) => { s.hidden = s.dataset.sekme !== ad; });
  if (SEKME_ACILISLARI[ad]) SEKME_ACILISLARI[ad]();
}

// ---- Ayarlar → Motorlar

const SINIF_ETIKETLERI = { hizli: "Hızlı", dengeli: "Dengeli", guclu: "Güçlü" };
let motorModelleriOnbellek = null;

async function motorAyarlariniCiz() {
  const liste = $("#motorAyarListesi");
  if (!motorModelleriOnbellek) {
    try { motorModelleriOnbellek = await api("/api/motor-modelleri"); } catch (_) { motorModelleriOnbellek = {}; }
  }
  const tercihler = durum.ayarlar.motor_modelleri || {};
  liste.replaceChildren(...durum.motorlar.map((m) => {
    const kart = el("div", "motor-kart");
    kart.append(motorNotu(m, true));
    const modeller = motorModelleriOnbellek[m.id] || [];
    const bolum = el("div", "model-tercihleri");
    bolum.append(el("div", "model-baslik", "Tercih edilen modeller"));
    if (!modeller.length) {
      bolum.append(el("p", "soluk", "Bu motorun model listesi şu an okunamadı; motor kendi varsayılan modelini kullanır."));
    } else {
      for (const sinif of Object.keys(SINIF_ETIKETLERI)) {
        const satir = el("label", "model-satir");
        const sec = el("select");
        sec.dataset.motor = m.id; sec.dataset.sinif = sinif;
        sec.append(new Option("Otomatik (önerilen)", ""));
        const uygun = modeller.filter((x) => x.sinif === sinif);
        for (const x of (uygun.length ? uygun : modeller)) sec.append(new Option(x.ad, x.id));
        sec.value = (tercihler[m.id] || {})[sinif] || "";
        sec.addEventListener("change", modelTercihiKaydet);
        satir.append(el("span", "", SINIF_ETIKETLERI[sinif]), sec);
        bolum.append(satir);
      }
    }
    kart.append(bolum);
    return kart;
  }));
}

function modelTercihiKaydet() {
  const harita = {};
  $$("#motorAyarListesi select").forEach((s) => {
    if (!s.value) return;
    (harita[s.dataset.motor] = harita[s.dataset.motor] || {})[s.dataset.sinif] = s.value;
  });
  ayarKaydet({ motor_modelleri: harita });
}
SEKME_ACILISLARI.motorlar = motorAyarlariniCiz;

// ---- Ayarlar → Yönlendirme

async function yonlendirmeSekmesiniDoldur() {
  const tablo = $("#yonlendirmeTablo"), son = $("#yonlendirmeSon");
  try {
    const v = await api("/api/yonlendirme");
    $("#yonlendirmeDosya").textContent = v.dosya;
    son.textContent = v.son
      ? `Son sınıflandırma: ${v.son.tur_ad} · ${v.son.zorluk_ad} (${v.son.kaynak === "jev" ? "Jev" : "kurallar"}, saat ${v.son.zaman})`
      : "Son sınıflandırma: henüz yok. Bir mesaj gönderince burada görünür.";
    $("#yonlendirmeUyari").textContent = (v.uyarilar || []).join(" ");
    const ust = el("tr");
    ["Tür", "Basit", "Orta", "Zor"].forEach((b) => ust.append(el("th", "", b)));
    const satirlar = [ust];
    for (const tur of [...new Set(v.tablo.map((r) => r.tur))]) {
      const tr = el("tr"), grup = v.tablo.filter((r) => r.tur === tur);
      tr.append(el("td", "tur", grup[0].tur_ad));
      for (const r of grup) {
        const hucre = el("td", v.son && v.son.tur === r.tur && v.son.zorluk === r.zorluk ? "son" : "");
        hucre.textContent = r.tercihler.map((t) => `${kisaMotorAdi(t.motor_ad)} · ${t.sinif_ad}`).join("  ›  ");
        tr.append(hucre);
      }
      satirlar.push(tr);
    }
    tablo.replaceChildren(...satirlar);
  } catch (h) {
    son.textContent = `Yönlendirme kuralları okunamadı: ${h.message}`;
  }
}
SEKME_ACILISLARI.yonlendirme = yonlendirmeSekmesiniDoldur;

// ---- Ayarlar → Hafıza ve Jev

async function hafizaBolumunuDoldur() {
  $("#ayarHafizaEkle").checked = durum.ayarlar.hafiza_ekle !== false;
  $("#ayarHafizaAday").checked = durum.ayarlar.hafiza_aday !== false;
  $("#ayarHafizaOnay").checked = durum.ayarlar.hafiza_onay !== false;
  const d = $("#hafizaDurum");
  const onayDugmesi = $("#hafizaOnayla");
  try {
    const h = await api("/api/hafiza-durum");
    let metin, hata = false;
    onayDugmesi.hidden = !h.hash_degisti;
    if (h.hash_degisti) { metin = `${h.hash_uyarisi}. Onaylayana kadar hafıza aracı çalıştırılmaz; mesajlar bağlamsız gider.`; hata = true; }
    else if (!h.kasa_var) { metin = "Hafıza kasası bulunamadı; mesajlar bağlamsız gider."; hata = true; }
    else if (!h.hafiza_py_var) { metin = "Kasada araclar/hafiza.py bulunamadı; mesajlar bağlamsız gider."; hata = true; }
    else if (h.son_hata) { metin = `Son denemede sorun: ${h.son_hata}`; hata = true; }
    else if (h.son_mod) metin = `Hazır. Son sorgu modu: ${h.son_mod}.`;
    else metin = "Hazır (henüz sorgu yapılmadı).";
    d.textContent = `Durum: ${metin}`;
    d.classList.toggle("hata", hata);
    $("#hafizaKasa").textContent = `Kasa: ${h.kasa}`;
  } catch (e) {
    d.textContent = `Durum okunamadı: ${e.message}`;
    d.classList.add("hata");
  }
}
SEKME_ACILISLARI.hafiza = hafizaBolumunuDoldur;

async function jevBolumunuDoldur() {
  $("#ayarJevAcik").checked = durum.ayarlar.jev_acik !== false;
  const d = $("#jevDurum"), ayrinti = $("#jevAyrinti");
  try {
    const j = await api("/api/jev-durum");
    let metin, hata = false;
    if (!j.acik) metin = "Kapalı; hassas bilgi uyarısı ve motor seçimi kurallarla çalışır.";
    else if (j.hazir) metin = "Hazır (anahtar dosyası bulundu).";
    else { metin = `Hazır değil, kurallarla çalışılıyor. ${j.sebep || ""}`; hata = true; }
    d.textContent = `Durum: ${metin}`;
    d.classList.toggle("hata", hata);
    const parcalar = [`Anahtar dosyası: ${j.anahtar_dosyasi_bulundu ? "bulundu" : "bulunamadı"}`];
    if (j.model) parcalar.push(`Model: ${j.model}`);
    parcalar.push(j.son_cagri
      ? `Son çağrı: ${j.son_cagri.replace("T", " ")} · ${j.son_sonuc === "basarili" ? "başarılı" : `hata (${j.son_hata || "bilinmiyor"})`}` +
        ` · toplam ${j.cagri_sayisi} (${j.basarili} başarılı, ${j.hatali} hatalı)`
      : "Son çağrı: henüz yok");
    parcalar.push(`Ayar dosyası: ${j.ayar_dosyasi}`);
    ayrinti.textContent = parcalar.join(" · ");
  } catch (e) {
    d.textContent = `Durum okunamadı: ${e.message}`;
    d.classList.add("hata");
  }
}
SEKME_ACILISLARI.jev = jevBolumunuDoldur;

// ---- Ayarlar → Hakkında: sürüm ve güncelleme durumu

async function hakkindaBolumunuDoldur() {
  const s = $("#hakkindaSurum"), g = $("#hakkindaGuncelleme");
  try {
    const d = await api("/api/guncelleme-durum");
    s.textContent = `Sürüm: ${d.surum}`;
    const parcalar = [];
    if (d.guncel) parcalar.push(`Etkin kurulum: ${d.guncel.yol}`);
    else parcalar.push(d.gelistirme_kurulumu ? "Geliştirme kurulumu (proje klasöründen çalışıyor)" : "Kurulum klasöründen çalışıyor");
    if (d.kurulu_surumler && d.kurulu_surumler.length) parcalar.push(`Kurulu sürümler: ${d.kurulu_surumler.join(", ")}`);
    const son = (d.gunluk || []).slice(-1)[0];
    if (son) parcalar.push(`Son güncelleme kaydı: ${son}`);
    g.textContent = parcalar.join(" · ");
    g.classList.remove("hata");
  } catch (e) {
    g.textContent = `Güncelleme durumu okunamadı: ${e.message}`;
    g.classList.add("hata");
  }
}
SEKME_ACILISLARI.hakkinda = hakkindaBolumunuDoldur;

// ---------------------------------------------------------------- olaylar

function boyutla() {
  mesajKutusu.style.height = "auto";
  mesajKutusu.style.height = Math.min(mesajKutusu.scrollHeight, innerHeight * 0.4) + "px";
}
mesajKutusu.addEventListener("input", () => {
  boyutla();
  if (hassasMetin !== null && mesajKutusu.value.trim() !== hassasMetin) hassasSeridiGizle();
});
mesajKutusu.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); gonder(); }
});
$("#gonder").addEventListener("click", () => gonder());
$("#durdur").addEventListener("click", yaniDurdur);
$("#motorDugme").addEventListener("click", motorMenusuAc);
$("#yeniSohbet").addEventListener("click", yeniSohbet);
$("#ara").addEventListener("input", sohbetListesiCiz);
$("#asagiGit").addEventListener("click", sonaKaydir);
icerik.addEventListener("scroll", asagiDugmesiniGuncelle, { passive: true });
$("#ayarlarAc").addEventListener("click", () => ayarlarAc("genel"));
$("#ayarlarKapat").addEventListener("click", () => $("#ayarlar").close());
$$(".ayarlar-sekmeler button").forEach((b) => b.addEventListener("click", () => sekmeSec(b.dataset.sekme)));
$("#kenarKapat").addEventListener("click", () => kenarDegistir(true));
$("#kenarAc").addEventListener("click", () => kenarDegistir(false));
function kenarDegistir(gizle) {
  if (gizle === undefined) gizle = !$("#kenar").classList.contains("gizli");
  $("#kenar").classList.toggle("gizli", gizle);
  $("#kenarAc").hidden = !gizle;
}

// Sohbet başlığı menüsü: yeniden adlandır (yerinde düzenleme), Markdown olarak kopyala, sil.
$("#sohbetMenu").addEventListener("click", () => {
  const s = durum.sohbetler.find((x) => x.id === durum.sohbet);
  const kok = el("div", "menu-liste");
  if (!s) { kok.append(el("div", "menu-baslik", "Henüz bir sohbet açık değil")); acilirGoster($("#sohbetMenu"), kok, "alt", "sag"); return; }
  kok.append(
    menuOgesi(el("span", "menu-simge", "✎"), "Yeniden adlandır", "", false, () => basligiDuzenle(s)),
    menuOgesi(el("span", "menu-simge", "⧉"), "Sohbeti kopyala", "Markdown olarak", false, () => kopyala(sohbetMetni(s), "Sohbet kopyalandı.")),
    menuOgesi(el("span", "menu-simge", "🗑"), "Sohbeti sil", "", false, () => sohbetSilOnayi(s, $("#sohbetMenu"))));
  acilirGoster($("#sohbetMenu"), kok, "alt", "sag");
});

function sohbetMetni(s) {
  return s.mesajlar.map((m) => m.rol === "asistan"
    ? `**${motorBul(m.motor) ? kisaMotorAdi(motorBul(m.motor).ad) : "Asistan"}:**\n\n${m.metin || ""}`
    : `**Sen:**\n\n${m.metin || ""}`).join("\n\n---\n\n");
}

function basligiDuzenle(s) {
  const baslik = $("#ustBaslik");
  const giris = el("input", "baslik-giris");
  giris.value = s.baslik; giris.maxLength = 60;
  baslik.replaceChildren(giris);
  giris.focus(); giris.select();
  let bitti = false;
  const bitir = async (kaydet) => {
    if (bitti) return; bitti = true;
    const yeni = giris.value.trim();
    baslik.textContent = s.baslik;
    if (kaydet && yeni && yeni !== s.baslik) {
      try { const v = await api("/api/sohbet-adlandir", { id: s.id, baslik: yeni }); durum.sohbetler = v.sohbetler; } catch (h) { bildir(h.message); }
      baslik.textContent = sohbetBasligi(); sohbetListesiCiz();
    }
  };
  giris.addEventListener("keydown", (e) => { if (e.key === "Enter") bitir(true); else if (e.key === "Escape") { e.stopPropagation(); bitir(false); } });
  giris.addEventListener("blur", () => bitir(true));
}

$("#ayarAd").addEventListener("change", (e) => ayarKaydet({ ad: e.target.value.trim() }));
$("#ayarVarsayilanMotor").addEventListener("change", (e) => motorSec(e.target.value));
$("#ayarHassasUyari").addEventListener("change", (e) => ayarKaydet({ hassas_uyari: e.target.checked }));
$("#ayarEnter").addEventListener("change", (e) => ayarKaydet({ enter_bas: e.target.checked }));
$("#ayarYerlesim").addEventListener("change", (e) => ayarKaydet({ yerlesim: e.target.value }));
$("#ayarJevPuanla").addEventListener("change", (e) => ayarKaydet({ jev_yanit_puanla: e.target.checked }));
$("#ayarHafizaEkle").addEventListener("change", (e) => ayarKaydet({ hafiza_ekle: e.target.checked }));
$("#ayarHafizaAday").addEventListener("change", (e) => ayarKaydet({ hafiza_aday: e.target.checked }));
$("#ayarHafizaOnay").addEventListener("change", (e) => ayarKaydet({ hafiza_onay: e.target.checked }));
$("#hafizaOnayla").addEventListener("click", async (e) => {
  const d = e.currentTarget; d.disabled = true;
  try { await api("/api/hafiza-onayla", {}); bildir("hafiza.py'nin yeni sürümü onaylandı."); } catch (h) { bildir(h.message); }
  d.disabled = false;
  hafizaBolumunuDoldur();
});
$("#ayarJevAcik").addEventListener("change", async (e) => { await ayarKaydet({ jev_acik: e.target.checked }); jevBolumunuDoldur(); });
$$("#ayarTema button").forEach((b) => b.addEventListener("click", () => ayarKaydet({ tema: b.dataset.deger })));
$$("#ayarYazi button").forEach((b) => b.addEventListener("click", () => ayarKaydet({ yazi_boyutu: b.dataset.deger })));
$("#motorlariDenetle").addEventListener("click", async (e) => {
  const d = e.currentTarget; d.disabled = true; d.textContent = "Denetleniyor…";
  motorModelleriOnbellek = null;
  try { await yenile(true); await motorAyarlariniCiz(); } catch (h) { bildir(h.message); }
  d.disabled = false; d.textContent = "Motorları yeniden denetle";
});
$("#yonlendirmeAc").addEventListener("click", async () => {
  try {
    const v = await api("/api/yonlendirme-ac", {});
    bildir(`yonlendirme.json açılıyor: ${v.dosya}`, 6000);
  } catch (h) { bildir(h.message, 8000); }
});

document.addEventListener("keydown", (e) => {
  const ctrl = e.ctrlKey || e.metaKey;
  if (ctrl && e.shiftKey && e.key.toLowerCase() === "o") { e.preventDefault(); yeniSohbet(); }
  else if (ctrl && e.key.toLowerCase() === "b") { e.preventDefault(); kenarDegistir(); }
  else if (ctrl && e.key.toLowerCase() === "k") { e.preventDefault(); kenarDegistir(false); $("#ara").focus(); }
  else if (ctrl && e.key === ",") { e.preventDefault(); ayarlarAc(); }
  else if (e.key === "Escape") {
    if (!acilir.hidden) acilirKapat();
    else if (durum.akis && !$("#ayarlar").open) yaniDurdur();
    else if (!$("#ayarlar").open && !($("#programEkle") && $("#programEkle").open)) mesajKutusu.focus();
  }
});

(async function baslat() {
  try { await yenile(); } catch (h) { bildir(`Arka uca ulaşılamadı: ${h.message}`, 10000); }
  yeniSohbet();
  setInterval(() => { if (!durum.akis) yenile().catch(() => {}); }, 15000);
})();
