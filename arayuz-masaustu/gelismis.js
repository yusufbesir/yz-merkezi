"use strict";
/* Ayarlar → Gelişmiş: eski çoklu pencere yöntemi (ChatGPT / Gemini / Claude web siteleri ve masaüstü programları).
 *
 * Tek Asistan bu pencerelere hiçbir şey göndermez; bu bölüm yalnızca kullanıcı isterse pencereleri açmak, dizmek ve
 * aynı mesajı hepsine birden göndermek içindir. Sunucu uçları (/api/gonder, /api/yanit, /api/site-ac, ...) aynen durur.
 * uygulama.js'deki yardımcılar (api, el, nokta, bildir, yenile, ayarKaydet, acilirKapat ...) burada da kullanılır.
 */

const YANIT_SURESI = 180000;   // ms: bir yanıt için en çok bu kadar beklenir
const YANIT_ARALIGI = 2000;    // ms: yanıt yoklama aralığı
const hedefler = () => [...durum.siteler, ...durum.programlar];

// Site durumu: Kapalı (soluk) / Giriş gerekli (turuncu) / Giriş yapıldı (yeşil) / Açık (giriş ölçülemedi)
function siteDurumMetni(s) {
  if (!s.acik) return { metin: "Kapalı", sinif: "" };
  if (s.giris === true) return { metin: "Giriş yapıldı", sinif: "acik" };
  if (s.giris === false) return { metin: "Giriş gerekli", sinif: "uyari" };
  return { metin: "Açık", sinif: "" };
}

async function programAc(p) {
  try {
    const v = await api("/api/ac", { id: p.id });
    if (!v.zaten_acik) { bildir(`${p.ad} açılıyor…`); setTimeout(() => yenile().catch(() => {}), 4000); }
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
    bildir(`${v.adet} pencere yan yana dizildi.`);
    yenile().catch(() => {});
  } catch (h) { bildir(h.message); }
}

async function ogret(p) {
  let kalan = 4;
  const yaz = () => bildir(`Fareyi ${p.ad} programının yazı kutusunun üzerine getir… ${kalan}`, 1500);
  $("#ayarlar").close();
  yaz();
  const sayac = setInterval(() => { kalan -= 1; if (kalan > 0) yaz(); }, 1000);
  try {
    await api("/api/ogret", { id: p.id });
    bildir(`${p.ad} yazı kutusunun yeri kaydedildi.`);
  } catch (h) { bildir(h.message); }
  finally { clearInterval(sayac); yenile().catch(() => {}); }
}

// ---------------------------------------------------------------- listeler

function gelismisCiz() {
  const siteAlani = $("#siteAyarListesi");
  siteAlani.replaceChildren(...durum.siteler.map((s) => {
    const d = siteDurumMetni(s);
    const satir = el("div", "program-satir");
    const ad = el("div", "ad", s.ad);
    ad.append(el("small", "", s.acik && s.sebep && s.giris !== true ? `${d.metin} · ${s.sebep}` : d.metin));
    satir.append(nokta(s.renk), ad, el("span", `durum ${d.sinif}`, d.metin), dugme(s.acik ? "Öne getir" : "Pencereyi aç", "", () => siteAc(s)));
    return satir;
  }));
  $("#programAyarListesi").replaceChildren(...durum.programlar.map((p) => {
    const satir = el("div", "program-satir");
    const ad = el("div", "ad", p.ad);
    ad.append(el("small", "", `${p.acik ? "Açık" : "Kapalı"} · ${p.exe}${p.ogretildi ? " · yazı kutusu öğretildi" : ""}`));
    satir.append(nokta(p.renk), ad, dugme(p.acik ? "Öne getir" : "Aç", "", () => programAc(p)),
      dugme("Yazı kutusunu öğret", "", () => ogret(p)));
    if (p.ek) {
      satir.append(dugme("Kaldır", "", async () => {
        if (!confirm(`${p.ad} listeden kaldırılsın mı? (Programın kendisi silinmez.)`)) return;
        await api("/api/program-sil", { id: p.id }); yenile().catch(() => {});
      }));
    }
    return satir;
  }));
  cokluHedefleriCiz();
}

function cokluHedefleriCiz() {
  const alan = $("#cokluHedefler");
  alan.replaceChildren(...hedefler().map((h) => {
    const anahtar = h.ek !== undefined ? h.id : `site:${h.id}`;
    const satir = el("label", "coklu-hedef");
    const kutu = el("input"); kutu.type = "checkbox"; kutu.checked = Boolean(h.secili);
    kutu.addEventListener("change", async () => {
      h.secili = kutu.checked;
      try { await api("/api/ayar", { secili: { [anahtar]: kutu.checked } }); } catch (e) { bildir(e.message); }
    });
    satir.append(kutu, nokta(h.renk), el("span", "", h.ad));
    return satir;
  }));
}

// ---------------------------------------------------------------- program ekleme

// Tarayıcılar program olarak eklenemez (sunucu da reddeder): ChatGPT, Gemini ve Claude web hesabı olarak zaten var.
const TARAYICI_EXE = /^(msedge|chrome|firefox|brave|opera)\.exe$/i;

async function programEkleAc() {
  try {
    const { pencereler } = await api("/api/pencereler");
    const secim = $("#pencereSecimi");
    secim.replaceChildren();
    pencereler.forEach((p, i) => secim.append(new Option(`${p.baslik}  —  ${p.exe}`, i)));
    secim.pencereler = pencereler;
    secim.onchange = () => {
      const p = pencereler[secim.value];
      if (!p) return;
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

// ---------------------------------------------------------------- çoklu pencereye gönder (eski yöntem)

let cokluSuruyor = false;

function cokluDurum(metin, hata = false) {
  const k = $("#cokluDurum");
  k.textContent = metin; k.classList.toggle("hata", hata);
}

function cokluBlok(ad, renk) {
  const kok = el("div", "coklu-yanit");
  const baslik = el("div", "coklu-baslik");
  baslik.append(nokta(renk), el("b", "", ad));
  const govde = el("div", "coklu-govde");
  kok.append(baslik, govde);
  return {
    kok, baslik,
    yaz(metin, yaziyor) { govde.textContent = metin || (yaziyor ? "Yanıt bekleniyor…" : ""); kok.classList.toggle("yaziyor", Boolean(yaziyor)); },
    rozetKoy(puan) {
      if (baslik.querySelector(".rozet")) return;
      const r = el("span", "rozet", "Önerilen yanıt (Jev)");
      if (typeof puan === "number") r.title = `Jev'e göre olasılık: %${Math.round(puan * 100)}`;
      baslik.append(r);
    },
  };
}

async function cokluGonder(onayli = false, baglamKarari = null, baglamKimligi = null) {
  const kutu = $("#cokluMesaj");
  const metin = kutu.value.trim();
  if (!metin || cokluSuruyor) return;
  cokluSuruyor = true;
  $("#cokluGonder").disabled = true;
  cokluDurum("Gönderiliyor…");
  try {
    const v = await api("/api/gonder", { metin, sohbet: null, ...(onayli ? { onayli: true } : {}),
      ...(baglamKarari ? { baglam_karari: baglamKarari } : {}), ...(baglamKimligi ? { baglam_kimligi: baglamKimligi } : {}) });
    if (v.baglam_onay) {
      // Hafıza bağlamı sitelere gitmeden önce gösterilir (Ayarlar → Hafıza → her seferinde onay iste).
      const kok = $("#cokluDurum");
      kok.replaceChildren();
      kok.classList.remove("hata");
      const ayrinti = el("details", "baglam");
      ayrinti.open = true;
      ayrinti.append(el("summary", "", `Hafızadan şu bağlam eklenecek (${v.karakter} karakter)`), el("pre", "", v.baglam || ""));
      kok.append(ayrinti,
        dugme("Ekleyerek gönder", "kucuk-dugme", () => { cokluSuruyor = false; cokluGonder(onayli, "ekle", v.baglam_kimligi); }),
        dugme("Bağlamsız gönder", "kucuk-dugme", () => { cokluSuruyor = false; cokluGonder(onayli, "ekleme"); }),
        dugme("Vazgeç", "kucuk-dugme", () => cokluDurum("Gönderme iptal edildi.")));
      return;
    }
    if (v.onay_gerekli) {
      const kok = $("#cokluDurum");
      kok.textContent = `Bu mesaj ${v.aciklama} içeriyor olabilir. `;
      kok.classList.add("hata");
      kok.append(dugme("Yine de gönder", "kucuk-dugme", () => { cokluSuruyor = false; cokluGonder(true); }),
        dugme("Vazgeç", "kucuk-dugme", () => cokluDurum("Gönderme iptal edildi.")));
      return;
    }
    kutu.value = "";
    durum.sohbetler = v.sohbetler || durum.sohbetler;
    const alan = $("#cokluYanitlar");
    alan.replaceChildren();
    const bloklar = {}, beklenenler = [];
    const kayit = { sohbet: v.sohbet, sira: v.mesaj_sira };
    for (const b of v.yanit_bekleyen || []) {
      const blok = cokluBlok(b.ad, b.renk);
      blok.yaz("", true);
      alan.append(blok.kok);
      bloklar[b.site] = blok;
      beklenenler.push(cokluYanitBekle(b, blok, kayit));
    }
    const sorun = (v.sorunlar || []).map((s) => `${s.ad}: ${s.sebep}`).join("; ");
    const not = v.hassas_uyari ? `  Not: mesaj ${v.hassas_uyari.aciklama} içeriyor.` : "";
    cokluDurum((v.gonderilen.length ? `Gönderildi: ${v.gonderilen.join(", ")}.` : "Hiçbir yere gönderilemedi.") + (sorun ? `  Sorun: ${sorun}` : "") + not, Boolean(sorun));
    if (beklenenler.length > 1) Promise.all(beklenenler).then((metinler) => cokluPuanla(kayit, bloklar, metinler));
  } catch (h) {
    cokluDurum(h.message, true);
  } finally {
    cokluSuruyor = false;
    $("#cokluGonder").disabled = false;
    yenile().catch(() => {});
  }
}

// Sitenin yanıtını 2 sn aralıkla okur; yazıyor=false ve metin iki yoklamada değişmediyse bitmiş sayar (en çok 180 sn).
async function cokluYanitBekle(b, blok, kayit) {
  const baslangic = Date.now();
  let metin = "", onceki = null, ardArdaHata = 0, bitti = false;
  while (Date.now() - baslangic < YANIT_SURESI) {
    await bekle(YANIT_ARALIGI);
    let y;
    try {
      y = await api(`/api/yanit?site=${encodeURIComponent(b.site)}&taban=${b.taban}`);
      ardArdaHata = 0;
    } catch (_) {
      if (++ardArdaHata >= 4) break;
      continue;
    }
    metin = y.metin || "";
    blok.yaz(metin, y.yaziyor || !metin);
    if (!y.yaziyor && metin && metin === onceki) { bitti = true; break; }
    onceki = !y.yaziyor && metin ? metin : null;
  }
  blok.yaz(metin || (bitti ? "" : "Yanıt okunamadı."), false);
  if (metin) {
    try { await api("/api/yanit-kaydet", { sohbet: kayit.sohbet, mesaj_sira: kayit.sira, site: b.site, metin }); }
    catch (h) { bildir(`Yanıt kaydedilemedi: ${h.message}`); }
  }
  return metin;
}

// Ayarlar → Gelişmiş → "Yanıtları Jev ile puanla" açıksa: en az iki yanıt kaydedildiyse sunucu Jev'e en iyisini sorar.
async function cokluPuanla(kayit, bloklar, metinler) {
  if (!durum.ayarlar.jev_yanit_puanla || durum.ayarlar.jev_acik === false) return;
  if (metinler.filter((m) => m && m.trim()).length < 2) return;
  try {
    const v = await api("/api/yanit-puanla", { sohbet: kayit.sohbet, mesaj_sira: kayit.sira });
    if (v.durum) cokluDurum(`Puanlama yapılmadı: ${v.durum}.`);
    else if (bloklar[v.onerilen]) bloklar[v.onerilen].rozetKoy(v.puan);
  } catch (h) { bildir(h.message); }
}

// ---------------------------------------------------------------- olaylar

$("#hepsiniAc").addEventListener("click", hepsiniAc);
$("#diz").addEventListener("click", diz);
$("#programEkleAc").addEventListener("click", programEkleAc);
$("#cokluGonder").addEventListener("click", () => cokluGonder());
$("#programEkleIptal").addEventListener("click", () => $("#programEkle").close());
$("#programEkleTamam").addEventListener("click", async () => {
  const secim = $("#pencereSecimi");
  const p = secim.pencereler && secim.pencereler[secim.value];
  const ad = $("#yeniAd").value.trim();
  if (!p || !ad) return bildir("Ad gerekli.");
  if (TARAYICI_EXE.test(p.exe)) return bildir("Tarayıcılar program olarak eklenemez.");
  try {
    await api("/api/program-ekle", { ad, exe: p.exe, yol: p.yol });
    $("#programEkle").close();
    bildir(`${ad} eklendi. Mesaj yanlış yere giderse "Yazı kutusunu öğret"i kullan.`, 6000);
    yenile().catch(() => {});
  } catch (h) { bildir(h.message); }
});
