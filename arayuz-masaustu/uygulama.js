"use strict";

const $ = (s, kok = document) => kok.querySelector(s);
const $$ = (s, kok = document) => [...kok.querySelectorAll(s)];
const durum = {
  programlar: [], siteler: [], ayarlar: {}, sohbetler: [],
  siteSohbetleri: [], siteHatalari: [],
  sohbet: null,        // açık yerel (ortak) sohbetin kimliği
  siteSohbet: null,    // açık site sohbeti: { site, url, baslik, mesajlar }
  secimYedegi: null,   // site sohbetine geçerken hedef seçiminin yedeği
  gonderiliyor: false,
  bekleyenYanit: 0,    // yanıtı hâlâ beklenen site sayısı
};
const mesajKutusu = $("#mesaj");
const YANIT_SURESI = 180000;   // ms: bir yanıt için en çok bu kadar beklenir
const YANIT_ARALIGI = 2000;    // ms: yanıt yoklama aralığı
const bekle = (ms) => new Promise((coz) => setTimeout(coz, ms));

// ---------------------------------------------------------------- istek belirteci
// Sunucu belirteci adresin parçasında (#t=...) verir: sunucuya gitmez, burada sessionStorage'a alınır ve
// adresten silinir. Her /api/ isteği X-YZ-Token başlığıyla gider; belirteçsiz istekler 403 alır.
const BELIRTEC_ANAHTARI = "yzm.belirtec";
let bellekBelirteci = "";
(function belirteciAl() {
  const m = /[#&]t=([A-Za-z0-9_-]+)/.exec(location.hash);
  if (m) {
    bellekBelirteci = m[1];
    try { sessionStorage.setItem(BELIRTEC_ANAHTARI, m[1]); } catch (_) { /* saklanamazsa bellekte kalır */ }
    history.replaceState(null, "", location.pathname + location.search);
  }
})();
function belirtec() {
  if (bellekBelirteci) return bellekBelirteci;
  try { return sessionStorage.getItem(BELIRTEC_ANAHTARI) || ""; } catch (_) { return ""; }
}

// ---------------------------------------------------------------- yardımcılar

async function api(yol, govde) {
  const basliklar = { "X-YZ-Token": belirtec() };
  const secenek = govde === undefined ? { headers: basliklar }
    : { method: "POST", headers: { ...basliklar, "Content-Type": "application/json" }, body: JSON.stringify(govde) };
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

function el(etiket, sinif, metin) {
  const e = document.createElement(etiket);
  if (sinif) e.className = sinif;
  if (metin !== undefined) e.textContent = metin;
  return e;
}

function nokta(renk) {
  const n = el("span", "nokta");
  n.style.background = renk;
  return n;
}

const siteBul = (id) => durum.siteler.find((s) => s.id === id);
const hedefler = () => [...durum.siteler, ...durum.programlar];
// "ChatGPT'de", "Gemini'de", "Claude'da": Türkçe bulunma eki
const bulunmaEki = (ad) => `${ad}'${ad === "Claude" ? "da" : "de"}`;

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

// Site durumu: Kapalı (soluk) / Giriş gerekli (turuncu) / Giriş yapıldı (yeşil) / Açık (giriş ölçülemedi)
function siteDurumMetni(s) {
  if (!s.acik) return { metin: "Kapalı", sinif: "" };
  if (s.giris === true) return { metin: "Giriş yapıldı", sinif: "acik" };
  if (s.giris === false) return { metin: "Giriş gerekli", sinif: "uyari" };
  return { metin: "Açık", sinif: "" };
}

// ---------------------------------------------------------------- durum ve çizim

async function yenile() {
  const v = await api("/api/durum");
  const onceki = new Map(durum.siteler.map((s) => [s.id, s.giris]));
  Object.assign(durum, { programlar: v.programlar, siteler: v.siteler || [], ayarlar: v.ayarlar, sohbetler: v.sohbetler });
  if (v.uyari && v.uyari !== durum.gosterilenUyari) { durum.gosterilenUyari = v.uyari; bildir(v.uyari, 15000); }
  temayiUygula(); selamla();
  kenarProgramlariCiz(); hedefMenuCiz(); sohbetListesiCiz(); programAyarlariCiz(); ayarlariDoldur(); girisSeridiCiz();
  // bir sitede yeni giriş yapıldıysa sohbetleri hemen oku
  if (durum.siteler.some((s) => s.giris === true && onceki.get(s.id) !== true)) siteSohbetleriYukle(true);
}

function kenarProgramlariCiz() {
  const alan = $("#kenarProgramlar");
  alan.innerHTML = "";
  for (const s of durum.siteler) {
    const d = siteDurumMetni(s);
    const satir = el("div", "kenar-program");
    satir.dataset.site = s.id;
    satir.append(nokta(s.renk), el("span", "ad", s.ad), el("span", `durum ${d.sinif}`, d.metin));
    satir.title = s.acik ? `${s.sebep || d.metin} — tıkla: öne getir` : "Tıkla: pencereyi aç, bir kez giriş yap";
    satir.addEventListener("click", () => siteAc(s));
    alan.append(satir);
  }
  if (!durum.programlar.length) return;
  // Masaüstü programları yedek yoldur: bir program işaretliyse açık görünür, değilse başlığa tıklayınca açılır.
  const acik = durum.yedekAcik !== undefined ? durum.yedekAcik : durum.programlar.some((p) => p.secili);
  const baslik = el("div", "kenar-alt-baslik tikla", `${acik ? "▾" : "▸"} Masaüstü programları (yedek)`);
  baslik.addEventListener("click", () => { durum.yedekAcik = !acik; kenarProgramlariCiz(); });
  alan.append(baslik);
  if (!acik) return;
  for (const p of durum.programlar) {
    const satir = el("div", "kenar-program");
    satir.append(nokta(p.renk), el("span", "ad", p.ad), el("span", `durum ${p.acik ? "acik" : ""}`, p.acik ? "Açık" : "Kapalı"));
    satir.title = p.acik ? "Öne getir" : "Aç";
    satir.addEventListener("click", () => programAc(p));
    alan.append(satir);
  }
}

function hedefSatiri(h, anahtar, durumMetni) {
  const satir = el("label");
  const kutu = el("input"); kutu.type = "checkbox"; kutu.checked = h.secili;
  kutu.addEventListener("change", async () => {
    h.secili = kutu.checked;
    durum.secimYedegi = null;  // kullanıcı seçimi elle değiştirdi: otomatik geri yükleme iptal
    try { await api("/api/ayar", { secili: { [anahtar]: kutu.checked } }); } catch (e) { bildir(e.message); }
    hedefOzetYaz();
  });
  satir.append(kutu, nokta(h.renk), el("span", "ad", h.ad), el("span", "durum", durumMetni));
  return satir;
}

function hedefMenuCiz() {
  const menu = $("#hedefMenu");
  menu.innerHTML = "";
  if (durum.siteler.length) menu.append(el("div", "menu-baslik", "Hesaplar (web)"));
  for (const s of durum.siteler) menu.append(hedefSatiri(s, `site:${s.id}`, siteDurumMetni(s).metin.toLowerCase()));
  if (durum.programlar.length) menu.append(el("div", "menu-baslik", "Masaüstü programları"));
  for (const p of durum.programlar) menu.append(hedefSatiri(p, p.id, p.acik ? "açık" : "kapalı"));
  hedefOzetYaz();
}

function hedefOzetYaz() {
  const secili = hedefler().filter((h) => h.secili);
  $("#hedefOzet").textContent = secili.length === 0 ? "Hedef seçilmedi"
    : secili.length <= 3 ? secili.map((h) => h.ad).join(", ") : `${secili.length} hedef`;
}

// ---------------------------------------------------------------- kenar çubuğu: sohbet listesi

function grupBasligi(ad, renk) {
  const b = el("div", "sohbet-grup");
  if (renk) b.append(nokta(renk));
  b.append(el("span", "", ad));
  return b;
}

function sohbetListesiCiz() {
  const alan = $("#sohbetListesi");
  const suzgec = $("#ara").value.trim().toLowerCase();
  alan.innerHTML = "";
  let adet = 0;

  const yerel = durum.sohbetler.filter((s) => !suzgec || s.baslik.toLowerCase().includes(suzgec)
    || s.mesajlar.some((m) => m.metin.toLowerCase().includes(suzgec)
      || Object.values(m.yanitlar || {}).some((y) => y.toLowerCase().includes(suzgec))));
  if (yerel.length) alan.append(grupBasligi("Yapay Zeka Merkezi"));
  for (const s of yerel) {
    adet++;
    const satir = el("div", `sohbet-satir ${!durum.siteSohbet && s.id === durum.sohbet ? "aktif" : ""}`);
    satir.append(el("span", "ad", s.baslik));
    const sil = el("button", "sil", "✕"); sil.title = "Sohbeti sil";
    sil.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(`"${s.baslik}" sohbeti silinsin mi?`)) return;
      const v = await api("/api/sohbet-sil", { id: s.id });
      durum.sohbetler = v.sohbetler;
      if (durum.sohbet === s.id) yeniSohbet();
      sohbetListesiCiz();
    });
    satir.append(sil);
    satir.addEventListener("click", () => sohbetAc(s.id));
    alan.append(satir);
  }

  for (const site of durum.siteler) {
    const liste = durum.siteSohbetleri.filter((x) => x.site === site.id && (!suzgec || x.baslik.toLowerCase().includes(suzgec)));
    if (!liste.length) continue;
    alan.append(grupBasligi(site.ad, site.renk));
    for (const x of liste) {
      adet++;
      const satir = el("div", `sohbet-satir ${durum.siteSohbet && durum.siteSohbet.url === x.url ? "aktif" : ""}`);
      satir.dataset.site = x.site;
      satir.append(nokta(site.renk), el("span", "ad", x.baslik));
      satir.title = `${site.ad} sohbeti`;
      satir.addEventListener("click", () => siteSohbetiAc(x));
      alan.append(satir);
    }
  }

  if (!adet) alan.append(el("div", "sohbet-bos", suzgec ? "Eşleşen sohbet yok." : "Henüz sohbet yok."));
  for (const h of durum.siteHatalari) alan.append(el("div", "sohbet-hata", `${h.ad}: sohbetler okunamadı (${h.sebep})`));
}

let siteSohbetYukleniyor = false;
async function siteSohbetleriYukle(yenileIste = false) {
  if (siteSohbetYukleniyor) return;
  siteSohbetYukleniyor = true;
  try {
    const v = await api("/api/site-sohbetler" + (yenileIste ? "?yenile=1" : ""));
    durum.siteSohbetleri = v.sohbetler || [];
    durum.siteHatalari = v.hatalar || [];
    sohbetListesiCiz();
  } catch (h) {
    if (yenileIste) bildir(`Sohbetler yenilenemedi: ${h.message}`);
  } finally { siteSohbetYukleniyor = false; }
}

// ---------------------------------------------------------------- orta alan: mesajlar

function sohbetAc(id) {
  durum.sohbet = id;
  durum.siteSohbet = null;
  secimiGeriYukle();
  const s = durum.sohbetler.find((x) => x.id === id);
  $("#ustBaslik").textContent = s ? s.baslik : "Yeni sohbet";
  $("#karsilama").hidden = Boolean(s && s.mesajlar.length);
  const alan = $("#mesajlar");
  alan.innerHTML = "";
  for (const m of (s ? s.mesajlar : [])) alan.append(mesajBalonu(m));
  sonaKaydir();
  sohbetListesiCiz();
  mesajKutusu.focus();
}

function sonaKaydir() {
  $("#mesajlar").scrollIntoView({ block: "end" });
  $("#icerik").scrollTop = $("#icerik").scrollHeight;
}

// Asistan yanıtı: solda, başında site rengi nokta ve site adı. yaz() canlı yanıt için güncelleme yapar.
function asistanBlogu(ad, renk, metin = "") {
  const kok = el("div", "asistan-mesaj");
  const durumEtiketi = el("span", "asistan-durum");
  const baslik = el("div", "asistan-baslik");
  baslik.append(nokta(renk), el("b", "", ad), durumEtiketi);
  const govde = el("div", "asistan-metin", metin);
  kok.append(baslik, govde);
  return {
    kok,
    yaz(yeniMetin, yaziyor, not = "") {
      govde.textContent = yeniMetin;
      govde.classList.toggle("imlec", Boolean(yaziyor));
      durumEtiketi.textContent = yaziyor ? "yazıyor…" : not;
    },
  };
}

function kullaniciBalonu(metin) {
  const kutu = el("div", "mesaj");
  kutu.append(el("div", "balon", metin));
  return kutu;
}

function mesajBalonu(m) {
  const kutu = kullaniciBalonu(m.metin);
  const ek = el("div", "ek");
  ek.append(el("span", "", m.zaman));
  if (m.gonderilen.length) ek.append(el("span", "", `Gönderilen: ${m.gonderilen.join(", ")}`));
  for (const s of m.sorunlar || []) ek.append(el("span", "sorun", `${s.ad}: ${s.sebep}`));
  const tekrar = el("button", "", "Yeniden gönder"); tekrar.title = "Bu mesajı tekrar gönder";
  tekrar.addEventListener("click", () => { mesajKutusu.value = m.metin; boyutla(); gonder(); });
  const kopyala = el("button", "", "Kopyala");
  kopyala.addEventListener("click", () => navigator.clipboard.writeText(m.metin).then(() => bildir("Kopyalandı.")));
  ek.append(tekrar, kopyala);
  kutu.append(ek);
  const yanitlar = el("div", "yanitlar");
  for (const [siteId, metin] of Object.entries(m.yanitlar || {})) {
    const site = siteBul(siteId);
    yanitlar.append(asistanBlogu(site ? site.ad : siteId, site ? site.renk : "#888", metin).kok);
  }
  kutu.append(yanitlar);
  return kutu;
}

function yeniSohbet() {
  durum.sohbet = null;
  sohbetAc(null);
}

// ---------------------------------------------------------------- site sohbetini açma

let acmaSayaci = 0;
async function siteSohbetiAc(x) {
  const sayac = ++acmaSayaci;
  durum.sohbet = null;
  durum.siteSohbet = { site: x.site, url: x.url, baslik: x.baslik, mesajlar: [] };
  $("#ustBaslik").textContent = x.baslik;
  $("#karsilama").hidden = true;
  $("#mesajlar").innerHTML = "";
  $("#mesajlar").append(el("div", "yukleniyor", "Sohbet okunuyor…"));
  sohbetListesiCiz();
  try {
    const v = await api("/api/site-sohbet-ac", { site: x.site, url: x.url });
    if (sayac !== acmaSayaci) return;  // kullanıcı bu arada başka sohbete geçti
    Object.assign(durum.siteSohbet, { baslik: v.baslik || x.baslik, mesajlar: v.mesajlar });
    await yalnizcaSiteSec(x.site);
    siteSohbetiCiz();
  } catch (h) {
    if (sayac !== acmaSayaci) return;
    $("#mesajlar").innerHTML = "";
    $("#mesajlar").append(el("div", "yukleniyor sorun", h.message));
  }
}

function siteSohbetiCiz() {
  const sc = durum.siteSohbet;
  if (!sc) return;
  const site = siteBul(sc.site) || { ad: sc.site, renk: "#888" };
  $("#ustBaslik").textContent = sc.baslik;
  $("#karsilama").hidden = true;
  const alan = $("#mesajlar");
  alan.innerHTML = "";
  if (!sc.mesajlar.length) alan.append(el("div", "yukleniyor", "Bu sohbette okunabilen mesaj yok."));
  for (const m of sc.mesajlar) {
    if (m.rol === "kullanici") {
      const kutu = kullaniciBalonu(m.metin);
      kutu.append(el("div", "yanitlar"));
      alan.append(kutu);
    } else alan.append(asistanBlogu(site.ad, site.renk, m.metin).kok);
  }
  sonaKaydir();
  sohbetListesiCiz();
  mesajKutusu.focus();
}

// Hedef seçimi: site sohbetinde yalnızca o site işaretlenir; yeni/yerel sohbete dönünce eski seçim geri gelir.
async function secimiUygula(harita) {
  for (const h of hedefler()) {
    const anahtar = h.ek !== undefined ? h.id : `site:${h.id}`;
    if (anahtar in harita) h.secili = harita[anahtar];
  }
  hedefMenuCiz();
  await api("/api/ayar", { secili: harita });
}

async function yalnizcaSiteSec(siteId) {
  if (!durum.secimYedegi) {
    durum.secimYedegi = {};
    for (const s of durum.siteler) durum.secimYedegi[`site:${s.id}`] = s.secili;
    for (const p of durum.programlar) durum.secimYedegi[p.id] = p.secili;
  }
  const yeni = {};
  for (const s of durum.siteler) yeni[`site:${s.id}`] = s.id === siteId;
  for (const p of durum.programlar) yeni[p.id] = false;
  try { await secimiUygula(yeni); } catch (h) { bildir(h.message); }
}

function secimiGeriYukle() {
  if (!durum.secimYedegi) return;
  const yedek = durum.secimYedegi;
  durum.secimYedegi = null;
  secimiUygula(yedek).catch((h) => bildir(h.message));
}

// ---------------------------------------------------------------- işlemler

async function programAc(p) {
  try {
    const v = await api("/api/ac", { id: p.id });
    if (!v.zaten_acik) { bildir(`${p.ad} açılıyor…`); setTimeout(yenile, 4000); }
  } catch (h) { bildir(h.message); }
}

async function siteAc(s) {
  try {
    const v = await api("/api/site-ac", { id: s.id });
    bildir(v.mesaj, 6000);
    if (!v.zaten_acik) [3000, 8000, 15000].forEach((ms) => setTimeout(() => yenile().catch(() => {}), ms));
  } catch (h) { bildir(h.message); }
}

async function hepsiniAc() {
  try {
    const v = await api("/api/hepsini-ac", {});
    if (v.acilan.length) {
      bildir(`Açılıyor: ${v.acilan.join(", ")}. Birkaç saniye sonra yan yana dizilecek.`, 6000);
      setTimeout(async () => { await yenile(); diz(); }, 6000);
    } else diz();
  } catch (h) { bildir(h.message); }
}

async function diz() {
  try {
    const v = await api("/api/diz", {});
    durumSatiri(`${v.adet} pencere yan yana dizildi.`);
    yenile();
  } catch (h) { durumSatiri(h.message, true); }
}

// Çoklu hedef onayı: birden fazla hedef seçiliyken ilk gönderimde "Şu hesaplara gidecek" sorulur; onaylanınca
// localStorage'a "onaylandi" yazılır ve bir daha sorulmaz. Ayarlar → Genel'deki anahtar kapatılırsa hiç sorulmaz,
// yeniden açılırsa onay sıfırlanır.
const ONAY_ANAHTARI = "yzm.cokluHedefOnayi";   // "onaylandi" | (yok)
const ONAY_ISTE_ANAHTARI = "yzm.cokluHedefOnayIste";   // "hayir" | (yok = iste)
function yerelOku(anahtar) { try { return localStorage.getItem(anahtar); } catch (_) { return null; } }
function yerelYaz(anahtar, deger) {
  try { if (deger === null) localStorage.removeItem(anahtar); else localStorage.setItem(anahtar, deger); } catch (_) { /* saklanamazsa her seferinde sorulur */ }
}
const onayIsteniyor = () => yerelOku(ONAY_ISTE_ANAHTARI) !== "hayir";

function cokluHedefOnaylandiMi() {
  const secili = hedefler().filter((h) => h.secili);
  if (secili.length < 2 || !onayIsteniyor() || yerelOku(ONAY_ANAHTARI) === "onaylandi") return true;
  if (!confirm(`Şu hesaplara gidecek: ${secili.map((h) => h.ad).join(", ")}.

Mesaj bunların hepsine aynı anda gönderilsin mi? (Bir kez onaylayınca bir daha sorulmaz.)`)) return false;
  yerelYaz(ONAY_ANAHTARI, "onaylandi");
  return true;
}

async function gonder() {
  const metin = mesajKutusu.value.trim();
  if (!metin || durum.gonderiliyor) return;
  if (!cokluHedefOnaylandiMi()) { durumSatiri("Gönderme iptal edildi.", false); return; }
  durum.gonderiliyor = true;
  $("#gonder").disabled = true;
  const siteModu = Boolean(durum.siteSohbet);
  const sc = durum.siteSohbet;
  const programVar = durum.programlar.some((p) => p.secili);
  durumSatiri(programVar ? "Gönderiliyor… Fare bir iki saniye programlar arasında gezecek, dokunmayın." : "Gönderiliyor…");
  try {
    const govde = { metin, sohbet: siteModu ? null : durum.sohbet };
    if (siteModu) govde.sohbet_url = sc.url;
    const v = await api("/api/gonder", govde);
    durum.sohbetler = v.sohbetler;
    if (durum.ayarlar.kutuyu_temizle && v.gonderilen.length) { mesajKutusu.value = ""; boyutla(); }
    let kapsayici, kayit = null;
    if (siteModu) {
      const kutu = kullaniciBalonu(metin);
      kapsayici = el("div", "yanitlar");
      kutu.append(kapsayici);
      $("#mesajlar").append(kutu);
      sonaKaydir();
    } else {
      sohbetAc(v.sohbet);
      kapsayici = $("#mesajlar").lastElementChild.querySelector(".yanitlar");
      kayit = { sohbet: v.sohbet, sira: v.mesaj_sira };
    }
    for (const b of v.yanit_bekleyen || []) {
      const blok = asistanBlogu(b.ad, b.renk);
      blok.yaz("", true);
      kapsayici.append(blok.kok);
      yanitBekle(b, blok, kayit, siteModu ? sc : null);  // arka planda sürer
    }
    sonaKaydir();
    const sorun = v.sorunlar.map((s) => `${s.ad}: ${s.sebep}`).join("; ");
    durumSatiri((v.gonderilen.length ? `Gönderildi: ${v.gonderilen.join(", ")}.` : "Hiçbir yere gönderilemedi.") + (sorun ? `  Sorun: ${sorun}` : ""), Boolean(sorun));
  } catch (h) {
    durumSatiri(h.message, true);
  } finally {
    durum.gonderiliyor = false;
    $("#gonder").disabled = false;
    mesajKutusu.focus();
    yenile().catch(() => {});
  }
}

// Sitenin yanıtını 2 sn aralıkla okur; yazıyor=false ve metin iki yoklamada değişmediyse bitmiş sayar (en çok 180 sn).
async function yanitBekle(b, blok, kayit, siteSohbeti) {
  durum.bekleyenYanit++;
  const baslangic = Date.now();
  let metin = "", onceki = null, ardArdaHata = 0, bitti = false, not = "";
  try {
    while (Date.now() - baslangic < YANIT_SURESI) {
      await bekle(YANIT_ARALIGI);
      let y;
      try {
        y = await api(`/api/yanit?site=${encodeURIComponent(b.site)}&taban=${b.taban}`);
        ardArdaHata = 0;
      } catch (h) {
        if (++ardArdaHata >= 4) { not = `Yanıt okunamadı: ${h.message}`; break; }
        continue;
      }
      metin = y.metin || "";
      blok.yaz(metin, y.yaziyor || !metin);
      if (!y.yaziyor && metin && metin === onceki) { bitti = true; break; }
      onceki = !y.yaziyor && metin ? metin : null;
    }
    if (!bitti && !not) not = metin ? "Yanıt tamamlanmadı (süre doldu)." : "Yanıt gelmedi (süre doldu).";
    blok.yaz(metin, false, not);
    if (kayit && metin) await yanitiKaydet(kayit, b.site, metin);
  } finally {
    durum.bekleyenYanit--;
  }
  siteSohbetleriYukle(true);  // site yeni sohbet oluşturduysa listede görünsün
  if (siteSohbeti && durum.bekleyenYanit === 0) siteSohbetiYenile(siteSohbeti);
}

async function yanitiKaydet(kayit, siteId, metin) {
  try {
    await api("/api/yanit-kaydet", { sohbet: kayit.sohbet, mesaj_sira: kayit.sira, site: siteId, metin });
    const s = durum.sohbetler.find((x) => x.id === kayit.sohbet);
    const m = s && s.mesajlar[kayit.sira];
    if (m) (m.yanitlar = m.yanitlar || {})[siteId] = metin;
  } catch (h) { bildir(`Yanıt kaydedilemedi: ${h.message}`); }
}

// Site sohbetine yazılan mesajın yanıtı bitince sohbeti siteden yeniden okuyup gösterir.
async function siteSohbetiYenile(sc) {
  if (durum.siteSohbet !== sc) return;
  try {
    const v = await api("/api/site-sohbet-ac", { site: sc.site, url: sc.url });
    if (durum.siteSohbet !== sc || durum.bekleyenYanit > 0) return;
    Object.assign(sc, { baslik: v.baslik || sc.baslik, mesajlar: v.mesajlar });
    siteSohbetiCiz();
  } catch (h) { /* canlı görünüm olduğu gibi kalır */ }
}

async function ogret(p) {
  const kapat = $("#ayarlar").open; if (kapat) $("#ayarlar").close();
  let kalan = 4;
  durumSatiri(`Fareyi ${p.ad} programının yazı kutusunun üzerine getir… ${kalan}`);
  const sayac = setInterval(() => { kalan -= 1; if (kalan > 0) durumSatiri(`Fareyi ${p.ad} programının yazı kutusunun üzerine getir… ${kalan}`); }, 1000);
  try {
    await api("/api/ogret", { id: p.id });
    durumSatiri(`${p.ad} yazı kutusunun yeri kaydedildi.`);
  } catch (h) { durumSatiri(h.message, true); }
  finally { clearInterval(sayac); yenile(); }
}

// ---------------------------------------------------------------- giriş uyarısı şeridi

function girisSeridiCiz() {
  const serit = $("#girisSeridi");
  const eksik = durum.siteler.filter((s) => s.acik && s.giris === false);
  serit.hidden = eksik.length === 0;
  serit.innerHTML = "";
  for (const s of eksik) {
    const satir = el("div", "giris-satir");
    const ac = el("button", "", "Pencereyi aç"); ac.addEventListener("click", () => siteAc(s));
    satir.append(nokta(s.renk), el("b", "", bulunmaEki(s.ad)), el("span", "", " oturum açılmamış. "), ac,
      el("span", "soluk", " Açılan pencerede giriş yap, sonra bu şerit kaybolur."));
    serit.append(satir);
  }
}

// ---------------------------------------------------------------- ayarlar penceresi

function ayarlariDoldur() {
  const a = durum.ayarlar;
  $("#ayarAd").value = a.ad || "";
  $("#ayarEnter").checked = Boolean(a.enter_bas);
  $("#ayarTemizle").checked = Boolean(a.kutuyu_temizle);
  $("#ayarCokluOnay").checked = onayIsteniyor();
  $("#ayarYerlesim").value = a.yerlesim || "sol";
  $$("#ayarTema button").forEach((b) => b.classList.toggle("aktif", b.dataset.deger === (a.tema || "sistem")));
  $$("#ayarYazi button").forEach((b) => b.classList.toggle("aktif", b.dataset.deger === (a.yazi_boyutu || "orta")));
}

async function ayarKaydet(degisiklik) {
  Object.assign(durum.ayarlar, degisiklik);
  temayiUygula(); selamla(); ayarlariDoldur();
  try { await api("/api/ayar", degisiklik); } catch (h) { bildir(h.message); }
}

function programAyarlariCiz() {
  const siteAlani = $("#siteAyarListesi");
  siteAlani.innerHTML = "";
  for (const s of durum.siteler) {
    const d = siteDurumMetni(s);
    const satir = el("div", "program-satir");
    const ad = el("div", "ad", s.ad);
    ad.append(el("small", "", s.acik && s.sebep && s.giris !== true ? `${d.metin} · ${s.sebep}` : d.metin));
    const dugme = el("button", "", s.acik ? "Öne getir" : "Pencereyi aç");
    dugme.addEventListener("click", () => siteAc(s));
    satir.append(nokta(s.renk), ad, el("span", `durum ${d.sinif}`, d.metin), dugme);
    siteAlani.append(satir);
  }
  const alan = $("#programAyarListesi");
  alan.innerHTML = "";
  for (const p of durum.programlar) {
    const satir = el("div", "program-satir");
    const ad = el("div", "ad", p.ad);
    ad.append(el("small", "", `${p.acik ? "Açık" : "Kapalı"} · ${p.exe}${p.ogretildi ? " · yazı kutusu öğretildi" : ""}`));
    const acDugme = el("button", "", p.acik ? "Öne getir" : "Aç"); acDugme.addEventListener("click", () => programAc(p));
    const ogretDugme = el("button", "", "Yazı kutusunu öğret"); ogretDugme.addEventListener("click", () => ogret(p));
    satir.append(nokta(p.renk), ad, acDugme, ogretDugme);
    if (p.ek) {
      const sil = el("button", "", "Kaldır");
      sil.addEventListener("click", async () => {
        if (!confirm(`${p.ad} listeden kaldırılsın mı? (Programın kendisi silinmez.)`)) return;
        await api("/api/program-sil", { id: p.id }); yenile();
      });
      satir.append(sil);
    }
    alan.append(satir);
  }
}

function ayarlarAc(sekme = "genel") {
  ayarlariDoldur();
  sekmeSec(sekme);
  $("#ayarlar").showModal();
}

function sekmeSec(ad) {
  $$(".ayarlar-sekmeler button").forEach((b) => b.classList.toggle("aktif", b.dataset.sekme === ad));
  $$(".ayarlar-icerik section").forEach((s) => { s.hidden = s.dataset.sekme !== ad; });
}

// Tarayıcılar program olarak eklenemez (sunucu da reddeder): ChatGPT, Gemini ve Claude web hesabı olarak zaten var.
const TARAYICI_EXE = /^(msedge|chrome|firefox|brave|opera)\.exe$/i;

async function programEkleAc() {
  try {
    const { pencereler } = await api("/api/pencereler");
    const secim = $("#pencereSecimi");
    secim.innerHTML = "";
    pencereler.forEach((p, i) => secim.append(new Option(`${p.baslik}  —  ${p.exe}`, i)));
    secim.pencereler = pencereler;
    secim.onchange = () => {
      const p = pencereler[secim.value];
      const tarayici = TARAYICI_EXE.test(p.exe);
      $("#baslikAlani").hidden = true;
      $("#tarayiciUyari").hidden = !tarayici;
      $("#programEkleTamam").disabled = tarayici;
      $("#yeniAd").value = p.baslik.replace(/ [-–—] .*$/, "").slice(0, 30);
      $("#yeniBaslik").value = $("#yeniAd").value;
    };
    secim.onchange();
    $("#programEkle").showModal();
  } catch (h) { bildir(h.message); }
}

// ---------------------------------------------------------------- olaylar

function boyutla() {
  mesajKutusu.style.height = "auto";
  mesajKutusu.style.height = Math.min(mesajKutusu.scrollHeight, innerHeight * 0.4) + "px";
}
mesajKutusu.addEventListener("input", boyutla);
mesajKutusu.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); gonder(); }
});
$("#gonder").addEventListener("click", gonder);
$("#yeniSohbet").addEventListener("click", yeniSohbet);
$("#ara").addEventListener("input", sohbetListesiCiz);
$("#sohbetYenile").addEventListener("click", async () => {
  const d = $("#sohbetYenile");
  d.disabled = true; d.textContent = "↻ Yenileniyor…";
  await siteSohbetleriYukle(true);
  d.disabled = false; d.textContent = "↻ Yenile";
});
$("#hepsiniAc").addEventListener("click", hepsiniAc);
$("#diz").addEventListener("click", diz);
$("#dizKucuk").addEventListener("click", diz);
$("#ekleMenu").addEventListener("click", programEkleAc);
$("#programEkleAc").addEventListener("click", programEkleAc);
$("#ayarlarAc").addEventListener("click", () => ayarlarAc("genel"));
$("#ayarlarKapat").addEventListener("click", () => $("#ayarlar").close());
$$(".ayarlar-sekmeler button").forEach((b) => b.addEventListener("click", () => sekmeSec(b.dataset.sekme)));
$$(".kenar-nav button").forEach((b) => b.addEventListener("click", () => {
  $$(".kenar-nav button").forEach((x) => x.classList.toggle("aktif", x === b));
  if (b.dataset.bolum === "programlar") ayarlarAc("programlar");
}));
$("#kenarKapat").addEventListener("click", () => kenarDegistir(true));
$("#kenarAc").addEventListener("click", () => kenarDegistir(false));
function kenarDegistir(gizle) {
  if (gizle === undefined) gizle = !$("#kenar").classList.contains("gizli");
  $("#kenar").classList.toggle("gizli", gizle);
  $("#kenarAc").hidden = !gizle;
}
$("#hedefDugme").addEventListener("click", (e) => { e.stopPropagation(); $("#hedefMenu").hidden = !$("#hedefMenu").hidden; });
document.addEventListener("click", (e) => { if (!e.target.closest(".hedef-secici")) $("#hedefMenu").hidden = true; });
$("#sohbetMenu").addEventListener("click", async () => {
  if (durum.siteSohbet) return bildir("Site sohbetlerini sitenin kendi sayfasından yeniden adlandırabilirsin.");
  if (!durum.sohbet) return bildir("Henüz sohbet yok.");
  const s = durum.sohbetler.find((x) => x.id === durum.sohbet);
  const ad = prompt("Sohbet adı:", s.baslik);
  if (ad && ad.trim()) { const v = await api("/api/sohbet-adlandir", { id: s.id, baslik: ad }); durum.sohbetler = v.sohbetler; sohbetAc(s.id); }
});

$("#ayarAd").addEventListener("change", (e) => ayarKaydet({ ad: e.target.value.trim() }));
$("#ayarEnter").addEventListener("change", (e) => ayarKaydet({ enter_bas: e.target.checked }));
$("#ayarTemizle").addEventListener("change", (e) => ayarKaydet({ kutuyu_temizle: e.target.checked }));
$("#ayarYerlesim").addEventListener("change", (e) => ayarKaydet({ yerlesim: e.target.value }));
$("#ayarCokluOnay").addEventListener("change", (e) => {
  yerelYaz(ONAY_ISTE_ANAHTARI, e.target.checked ? null : "hayir");
  if (e.target.checked) yerelYaz(ONAY_ANAHTARI, null);  // yeniden açılınca bir sonraki çoklu gönderimde tekrar sorulur
});
$$("#ayarTema button").forEach((b) => b.addEventListener("click", () => ayarKaydet({ tema: b.dataset.deger })));
$$("#ayarYazi button").forEach((b) => b.addEventListener("click", () => ayarKaydet({ yazi_boyutu: b.dataset.deger })));

$("#programEkleIptal").addEventListener("click", () => $("#programEkle").close());
$("#programEkleTamam").addEventListener("click", async () => {
  const secim = $("#pencereSecimi");
  const p = secim.pencereler[secim.value];
  const ad = $("#yeniAd").value.trim();
  if (!p || !ad) return bildir("Ad gerekli.");
  if (TARAYICI_EXE.test(p.exe)) return bildir("Tarayıcılar program olarak eklenemez.");
  const govde = { ad, exe: p.exe, yol: p.yol };
  try {
    await api("/api/program-ekle", govde);
    $("#programEkle").close();
    bildir(`${ad} eklendi. Mesaj yanlış yere giderse Ayarlar → Programlar'dan yazı kutusunu öğret.`, 6000);
    yenile();
  } catch (h) { bildir(h.message); }
});

document.addEventListener("keydown", (e) => {
  const ctrl = e.ctrlKey || e.metaKey;
  if (ctrl && e.shiftKey && e.key.toLowerCase() === "o") { e.preventDefault(); yeniSohbet(); }
  else if (ctrl && e.key.toLowerCase() === "b") { e.preventDefault(); kenarDegistir(); }
  else if (ctrl && e.key === ",") { e.preventDefault(); ayarlarAc(); }
  else if (ctrl && e.shiftKey && e.key.toLowerCase() === "d") { e.preventDefault(); diz(); }
  else if (e.key === "Escape" && !$("#ayarlar").open && !$("#programEkle").open) mesajKutusu.focus();
});

(async function baslat() {
  try { await yenile(); } catch (h) { bildir(`Arka uca ulaşılamadı: ${h.message}`, 10000); }
  yeniSohbet();
  siteSohbetleriYukle();
  setInterval(() => { if (!durum.gonderiliyor) yenile().catch(() => {}); }, 8000);
  setInterval(() => siteSohbetleriYukle(), 30000);
})();
