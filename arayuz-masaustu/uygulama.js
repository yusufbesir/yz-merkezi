"use strict";

const $ = (s, kok = document) => kok.querySelector(s);
const $$ = (s, kok = document) => [...kok.querySelectorAll(s)];
const durum = { programlar: [], ayarlar: {}, sohbetler: [], sohbet: null, gonderiliyor: false };
const mesajKutusu = $("#mesaj");

// ---------------------------------------------------------------- yardımcılar

async function api(yol, govde) {
  const secenek = govde === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(govde) };
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

// ---------------------------------------------------------------- durum ve çizim

async function yenile() {
  const v = await api("/api/durum");
  Object.assign(durum, { programlar: v.programlar, ayarlar: v.ayarlar, sohbetler: v.sohbetler });
  temayiUygula(); selamla();
  kenarProgramlariCiz(); hedefMenuCiz(); sohbetListesiCiz(); programAyarlariCiz(); ayarlariDoldur();
}

function kenarProgramlariCiz() {
  const alan = $("#kenarProgramlar");
  alan.innerHTML = "";
  for (const p of durum.programlar) {
    const satir = el("div", "kenar-program");
    const nokta = el("span", "nokta"); nokta.style.background = p.renk;
    satir.append(nokta, el("span", "ad", p.ad), el("span", `durum ${p.acik ? "acik" : ""}`, p.acik ? "Açık" : "Kapalı"));
    satir.title = p.acik ? "Öne getir" : "Aç";
    satir.addEventListener("click", () => programAc(p));
    alan.append(satir);
  }
}

function hedefMenuCiz() {
  const menu = $("#hedefMenu");
  menu.innerHTML = "";
  for (const p of durum.programlar) {
    const satir = el("label");
    const kutu = el("input"); kutu.type = "checkbox"; kutu.checked = p.secili;
    kutu.addEventListener("change", async () => {
      p.secili = kutu.checked;
      await api("/api/ayar", { secili: { [p.id]: kutu.checked } });
      hedefOzetYaz();
    });
    const nokta = el("span", "nokta"); nokta.style.background = p.renk;
    satir.append(kutu, nokta, el("span", "ad", p.ad), el("span", "durum", p.acik ? "açık" : "kapalı"));
    menu.append(satir);
  }
  hedefOzetYaz();
}

function hedefOzetYaz() {
  const secili = durum.programlar.filter((p) => p.secili);
  $("#hedefOzet").textContent = secili.length === 0 ? "Program seçilmedi"
    : secili.length <= 3 ? secili.map((p) => p.ad).join(", ") : `${secili.length} program`;
}

function sohbetListesiCiz() {
  const alan = $("#sohbetListesi");
  const suzgec = $("#ara").value.trim().toLowerCase();
  alan.innerHTML = "";
  for (const s of durum.sohbetler) {
    if (suzgec && !s.baslik.toLowerCase().includes(suzgec) && !s.mesajlar.some((m) => m.metin.toLowerCase().includes(suzgec))) continue;
    const satir = el("div", `sohbet-satir ${s.id === durum.sohbet ? "aktif" : ""}`);
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
}

function sohbetAc(id) {
  durum.sohbet = id;
  const s = durum.sohbetler.find((x) => x.id === id);
  $("#ustBaslik").textContent = s ? s.baslik : "Yeni sohbet";
  $("#karsilama").hidden = Boolean(s && s.mesajlar.length);
  const alan = $("#mesajlar");
  alan.innerHTML = "";
  for (const m of (s ? s.mesajlar : [])) alan.append(mesajBalonu(m));
  alan.scrollIntoView({ block: "end" });
  $("#icerik").scrollTop = $("#icerik").scrollHeight;
  sohbetListesiCiz();
  mesajKutusu.focus();
}

function mesajBalonu(m) {
  const kutu = el("div", "mesaj");
  kutu.append(el("div", "balon", m.metin));
  const ek = el("div", "ek");
  ek.append(el("span", "", m.zaman));
  if (m.gonderilen.length) ek.append(el("span", "", `${m.gonderilen.join(", ")} programına gönderildi`));
  for (const s of m.sorunlar || []) ek.append(el("span", "sorun", `${s.ad}: ${s.sebep}`));
  const tekrar = el("button", "", "Yeniden gönder"); tekrar.title = "Bu mesajı tekrar gönder";
  tekrar.addEventListener("click", () => { mesajKutusu.value = m.metin; boyutla(); gonder(); });
  const kopyala = el("button", "", "Kopyala");
  kopyala.addEventListener("click", () => navigator.clipboard.writeText(m.metin).then(() => bildir("Kopyalandı.")));
  ek.append(tekrar, kopyala);
  kutu.append(ek);
  return kutu;
}

function yeniSohbet() {
  durum.sohbet = null;
  sohbetAc(null);
}

// ---------------------------------------------------------------- işlemler

async function programAc(p) {
  try {
    const v = await api("/api/ac", { id: p.id });
    if (!v.zaten_acik) { bildir(`${p.ad} açılıyor…`); setTimeout(yenile, 4000); }
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
    durumSatiri(`${v.adet} program yan yana dizildi.`);
    yenile();
  } catch (h) { durumSatiri(h.message, true); }
}

async function gonder() {
  const metin = mesajKutusu.value.trim();
  if (!metin || durum.gonderiliyor) return;
  durum.gonderiliyor = true;
  $("#gonder").disabled = true;
  durumSatiri("Gönderiliyor… Fare bir iki saniye programlar arasında gezecek, dokunmayın.");
  try {
    const v = await api("/api/gonder", { metin, sohbet: durum.sohbet });
    durum.sohbetler = v.sohbetler;
    if (durum.ayarlar.kutuyu_temizle && v.gonderilen.length) { mesajKutusu.value = ""; boyutla(); }
    sohbetAc(v.sohbet);
    const sorun = v.sorunlar.map((s) => `${s.ad}: ${s.sebep}`).join("; ");
    durumSatiri((v.gonderilen.length ? `Gönderildi: ${v.gonderilen.join(", ")}.` : "Hiçbir programa gönderilemedi.") + (sorun ? `  Sorun: ${sorun}` : ""), Boolean(sorun));
  } catch (h) {
    durumSatiri(h.message, true);
  } finally {
    durum.gonderiliyor = false;
    $("#gonder").disabled = false;
    mesajKutusu.focus();
    yenile();
  }
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

// ---------------------------------------------------------------- ayarlar penceresi

function ayarlariDoldur() {
  const a = durum.ayarlar;
  $("#ayarAd").value = a.ad || "";
  $("#ayarEnter").checked = Boolean(a.enter_bas);
  $("#ayarTemizle").checked = Boolean(a.kutuyu_temizle);
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
  const alan = $("#programAyarListesi");
  alan.innerHTML = "";
  for (const p of durum.programlar) {
    const satir = el("div", "program-satir");
    const nokta = el("span", "nokta"); nokta.style.background = p.renk;
    const ad = el("div", "ad", p.ad);
    ad.append(el("small", "", `${p.acik ? "Açık" : "Kapalı"} · ${p.exe}${p.ogretildi ? " · yazı kutusu öğretildi" : ""}`));
    const acDugme = el("button", "", p.acik ? "Öne getir" : "Aç"); acDugme.addEventListener("click", () => programAc(p));
    const ogretDugme = el("button", "", "Yazı kutusunu öğret"); ogretDugme.addEventListener("click", () => ogret(p));
    satir.append(nokta, ad, acDugme, ogretDugme);
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

async function programEkleAc() {
  try {
    const { pencereler } = await api("/api/pencereler");
    const secim = $("#pencereSecimi");
    secim.innerHTML = "";
    pencereler.forEach((p, i) => secim.append(new Option(`${p.baslik}  —  ${p.exe}`, i)));
    secim.pencereler = pencereler;
    secim.onchange = () => {
      const p = pencereler[secim.value];
      const tarayici = /msedge|chrome|firefox|brave|opera/i.test(p.exe);
      $("#baslikAlani").hidden = !tarayici;
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
  if (!durum.sohbet) return bildir("Henüz sohbet yok.");
  const s = durum.sohbetler.find((x) => x.id === durum.sohbet);
  const ad = prompt("Sohbet adı:", s.baslik);
  if (ad && ad.trim()) { const v = await api("/api/sohbet-adlandir", { id: s.id, baslik: ad }); durum.sohbetler = v.sohbetler; sohbetAc(s.id); }
});

$("#ayarAd").addEventListener("change", (e) => ayarKaydet({ ad: e.target.value.trim() }));
$("#ayarEnter").addEventListener("change", (e) => ayarKaydet({ enter_bas: e.target.checked }));
$("#ayarTemizle").addEventListener("change", (e) => ayarKaydet({ kutuyu_temizle: e.target.checked }));
$("#ayarYerlesim").addEventListener("change", (e) => ayarKaydet({ yerlesim: e.target.value }));
$$("#ayarTema button").forEach((b) => b.addEventListener("click", () => ayarKaydet({ tema: b.dataset.deger })));
$$("#ayarYazi button").forEach((b) => b.addEventListener("click", () => ayarKaydet({ yazi_boyutu: b.dataset.deger })));

$("#programEkleIptal").addEventListener("click", () => $("#programEkle").close());
$("#programEkleTamam").addEventListener("click", async () => {
  const secim = $("#pencereSecimi");
  const p = secim.pencereler[secim.value];
  const ad = $("#yeniAd").value.trim();
  if (!p || !ad) return bildir("Ad gerekli.");
  const govde = { ad, exe: p.exe, yol: p.yol };
  if (!$("#baslikAlani").hidden) govde.baslik_icerir = $("#yeniBaslik").value.trim() || ad;
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
  setInterval(() => { if (!durum.gonderiliyor) yenile().catch(() => {}); }, 8000);
})();
