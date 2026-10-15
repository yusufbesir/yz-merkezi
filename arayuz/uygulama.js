"use strict";

const KAYIT_ANAHTARI = "yzm.pencereler";
const SISTEM_ANAHTARI = "yzm.sistem";
const ELLE_YAZ = "__elle__";
const VARSAYILAN_PENCERELER = ["openai", "gemini", "anthropic"];

const durum = {
  saglayicilar: [],
  modeller: {},      // saglayici id -> Promise<[{id, ad}]>
  pencereler: [],    // {id, saglayici, model, gecmis, gonderilsin, el, denetleyici}
  calisan: 0,
};

const $ = (secici, kok = document) => kok.querySelector(secici);
const pencereAlani = $("#pencereler");
const mesajKutusu = $("#mesaj");
const sistemKutusu = $("#sistem");

// ------------------------------------------------------------ oturum
// Oturum belirteci bu sayfaya HİÇ gelmez: sunucu tarayıcıyı tek kullanımlık açılış koduyla (/ac/<kod>) açar ve
// belirteci HttpOnly; SameSite=Strict çerezine koyar. /api/ istekleri yalnızca bu çerezle (aynı köken) gider.

// ------------------------------------------------------------ yardımcılar

async function api(yol, govde) {
  const secenek = govde === undefined ? { credentials: "same-origin" } : {
    method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(govde),
  };
  const yanit = await fetch(yol, secenek);
  const veri = await yanit.json().catch(() => ({}));
  if (!yanit.ok || veri.hata) throw new Error(veri.hata || `Sunucu hatası (${yanit.status})`);
  return veri;
}

let bildirimZamani;
function bildir(metin, sure = 4000) {
  const kutu = $("#bildirim");
  kutu.textContent = metin;
  kutu.hidden = false;
  clearTimeout(bildirimZamani);
  bildirimZamani = setTimeout(() => { kutu.hidden = true; }, sure);
}

function olustur(etiket, sinif, metin) {
  const e = document.createElement(etiket);
  if (sinif) e.className = sinif;
  if (metin !== undefined) e.textContent = metin;
  return e;
}

// Satır içi işaretler: `kod` ve **kalın**. Her şey metin düğümü olarak eklenir (HTML çözümlenmez).
function satirIci(kok, metin) {
  const kalip = /`([^`\n]+)`|\*\*([^*\n]+)\*\*/g;
  let son = 0, e;
  while ((e = kalip.exec(metin))) {
    if (e.index > son) kok.append(metin.slice(son, e.index));
    kok.append(olustur(e[1] !== undefined ? "code" : "strong", "", e[1] !== undefined ? e[1] : e[2]));
    son = kalip.lastIndex;
  }
  if (son < metin.length) kok.append(metin.slice(son));
}

// Küçük bir Markdown çevirici (DOM döndürür): kod blokları, satır içi kod, kalın yazı, başlıklar.
function mdDom(metin) {
  const parca = document.createDocumentFragment();
  metin.split("```").forEach((bolum, i) => {
    if (i % 2 === 1) {
      const satirSonu = bolum.indexOf("\n");
      const kod = satirSonu >= 0 ? bolum.slice(satirSonu + 1) : bolum;
      const pre = olustur("pre");
      pre.append(olustur("code", "", kod.replace(/\n$/, "")));
      parca.append(pre);
      return;
    }
    bolum.split("\n").forEach((satir, n) => {
      if (n) parca.append(document.createElement("br"));
      const baslik = /^#{1,6} (.*)$/.exec(satir);
      if (baslik) {
        const b = olustur("strong", "baslik");
        satirIci(b, baslik[1]);
        parca.append(b);
      } else satirIci(parca, satir);
    });
  });
  return parca;
}

function saglayici(id) {
  return durum.saglayicilar.find((s) => s.id === id);
}

function kullanilabilir(s) {
  return s && (!s.anahtar_gerekli || s.anahtar_kaynagi);
}

function kaydet() {
  const veri = durum.pencereler.map(({ id, saglayici, model, gecmis, gonderilsin }) => ({ id, saglayici, model, gecmis, gonderilsin }));
  try { localStorage.setItem(KAYIT_ANAHTARI, JSON.stringify(veri)); } catch { /* depolama kapalıysa sessizce geç */ }
}

function yukle() {
  try { return JSON.parse(localStorage.getItem(KAYIT_ANAHTARI)) || null; } catch { return null; }
}

// ------------------------------------------------------------ sağlayıcı ve model listeleri

async function saglayicilariYukle() {
  durum.saglayicilar = await api("/api/saglayicilar");
  durum.pencereler.forEach(saglayiciSeciminiCiz);
}

function modelleriGetir(id, yenile = false) {
  if (yenile || !durum.modeller[id]) {
    durum.modeller[id] = api(`/api/modeller?id=${encodeURIComponent(id)}`).then((v) => v.modeller);
    durum.modeller[id].catch(() => { delete durum.modeller[id]; });
  }
  return durum.modeller[id];
}

function saglayiciSeciminiCiz(p) {
  const secim = $(".saglayici", p.el);
  const gruplar = { hazir: "Bulut sağlayıcıları", yerel: "Bu bilgisayardaki modeller", ozel: "Eklediğim sağlayıcılar" };
  secim.innerHTML = "";
  secim.append(new Option("Sağlayıcı seçin…", ""));
  for (const [kaynak, baslik] of Object.entries(gruplar)) {
    const uyeler = durum.saglayicilar.filter((s) => s.kaynak === kaynak);
    if (!uyeler.length) continue;
    const grup = document.createElement("optgroup");
    grup.label = baslik;
    for (const s of uyeler) {
      const secenek = new Option(kullanilabilir(s) ? s.ad : `${s.ad} (anahtar yok)`, s.id);
      grup.append(secenek);
    }
    secim.append(grup);
  }
  if (p.saglayici && !saglayici(p.saglayici)) {
    secim.append(new Option(`${p.saglayici} (bulunamadı)`, p.saglayici));
  }
  secim.value = p.saglayici || "";
  const s = saglayici(p.saglayici);
  $(".nokta", p.el).style.background = s ? s.renk : "";
}

async function modelSeciminiCiz(p) {
  const secim = $(".model", p.el);
  const s = saglayici(p.saglayici);
  secim.innerHTML = "";
  durumYaz(p, "");
  if (!s) {
    secim.append(new Option("Önce sağlayıcı seçin", ""));
    return;
  }
  if (!kullanilabilir(s)) {
    secim.append(new Option("API anahtarı gerekli", ""));
    durumYaz(p, `${s.ad} için Ayarlar'dan API anahtarı ekleyin.`);
    return;
  }
  secim.append(new Option("Modeller yükleniyor…", ""));
  let modeller = [];
  try {
    modeller = await modelleriGetir(s.id);
  } catch (h) {
    durumYaz(p, h.message, true);
  }
  if (p.saglayici !== s.id) return; // bu arada sağlayıcı değişti
  secim.innerHTML = "";
  secim.append(new Option(modeller.length ? "Model seçin…" : "Model listesi alınamadı", ""));
  for (const m of modeller) {
    secim.append(new Option(m.ad && m.ad !== m.id ? `${m.ad} — ${m.id}` : m.id, m.id));
  }
  if (p.model && !modeller.some((m) => m.id === p.model)) {
    secim.append(new Option(p.model, p.model));
  }
  secim.append(new Option("✎ Model adını elle yaz…", ELLE_YAZ));
  secim.value = p.model || "";
  if (!p.model && modeller.length) {
    durumYaz(p, `${modeller.length} model bulundu. Listenin en üstünde en yeniler var.`);
  }
}

// ------------------------------------------------------------ pencereler

function durumYaz(p, metin, hata = false) {
  const kutu = $(".durum", p.el);
  kutu.textContent = metin;
  kutu.classList.toggle("hata", hata);
}

function pencereEkle(ayar = {}) {
  const p = {
    id: ayar.id || crypto.randomUUID(),
    saglayici: ayar.saglayici || "",
    model: ayar.model || "",
    gecmis: ayar.gecmis || [],
    gonderilsin: ayar.gonderilsin !== false,
    el: $("#pencereSablon").content.firstElementChild.cloneNode(true),
    denetleyici: null,
  };
  durum.pencereler.push(p);
  pencereAlani.append(p.el);

  const gonderilsin = $(".gonderilsin", p.el);
  gonderilsin.checked = p.gonderilsin;
  gonderilsin.addEventListener("change", () => { p.gonderilsin = gonderilsin.checked; kaydet(); });

  $(".saglayici", p.el).addEventListener("change", (e) => {
    p.saglayici = e.target.value;
    p.model = "";
    saglayiciSeciminiCiz(p);
    modelSeciminiCiz(p);
    kaydet();
  });

  $(".model", p.el).addEventListener("change", (e) => {
    if (e.target.value === ELLE_YAZ) {
      const ad = (prompt("Model adını tam olarak yazın (ör. yeni çıkan bir modelin kimliği):", p.model) || "").trim();
      if (ad) p.model = ad;
      modelSeciminiCiz(p);
    } else {
      p.model = e.target.value;
      durumYaz(p, "");
    }
    kaydet();
  });

  $(".temizle", p.el).addEventListener("click", () => {
    p.denetleyici?.abort();
    p.gecmis = [];
    mesajlariCiz(p);
    durumYaz(p, "");
    kaydet();
  });

  $(".kapat", p.el).addEventListener("click", () => {
    p.denetleyici?.abort();
    p.el.remove();
    durum.pencereler = durum.pencereler.filter((x) => x !== p);
    kaydet();
  });

  saglayiciSeciminiCiz(p);
  modelSeciminiCiz(p);
  mesajlariCiz(p);
  return p;
}

function balonOlustur(m) {
  const balon = document.createElement("div");
  balon.className = `balon ${m.rol}${m.hata && !m.icerik ? " hata" : ""}`;
  const govde = document.createElement("div");
  govde.className = "govde";
  balon.append(govde);
  balonDoldur(balon, m);
  return balon;
}

function balonDoldur(balon, m) {
  const govde = $(".govde", balon);
  govde.replaceChildren(m.icerik ? mdDom(m.icerik) : (m.hata || ""));
  govde.classList.toggle("yaziyor", Boolean(m.yaziyor));
  $(".ek", balon)?.remove();
  if (m.rol !== "asistan" || m.yaziyor) return;
  const ek = document.createElement("div");
  ek.className = "ek";
  const parcalar = [m.model, m.sure && `${m.sure} sn`, m.durduruldu && "durduruldu"].filter(Boolean);
  ek.append(parcalar.join(" · "));
  if (m.icerik) {
    const kopyala = document.createElement("button");
    kopyala.textContent = "Kopyala";
    kopyala.addEventListener("click", async () => {
      await navigator.clipboard.writeText(m.icerik);
      kopyala.textContent = "Kopyalandı";
      setTimeout(() => { kopyala.textContent = "Kopyala"; }, 1500);
    });
    ek.append(kopyala);
  }
  if (m.hata && m.icerik) {
    const not = document.createElement("span");
    not.style.color = "var(--hata)";
    not.textContent = m.hata;
    ek.append(not);
  }
  balon.append(ek);
}

function mesajlariCiz(p) {
  const alan = $(".mesajlar", p.el);
  alan.innerHTML = "";
  if (!p.gecmis.length) {
    alan.append(olustur("div", "bos", "Bir sağlayıcı ve model seçin, sonra alttaki kutuya mesajınızı yazın."));
    return;
  }
  for (const m of p.gecmis) alan.append(balonOlustur(m));
  alan.scrollTop = alan.scrollHeight;
}

// Başarısız yanıtları ve onlara ait soruları modele tekrar göndermemek için geçmişi süzer.
function gonderilecekGecmis(gecmis) {
  const sonuc = [];
  for (const m of gecmis) {
    if (m.rol === "asistan" && !m.icerik) {
      if (sonuc.at(-1)?.rol === "kullanici") sonuc.pop();
      continue;
    }
    sonuc.push({ rol: m.rol, icerik: m.icerik });
  }
  return sonuc;
}

async function pencereyeGonder(p, metin, sistem) {
  p.gecmis.push({ rol: "kullanici", icerik: metin });
  const mesajlar = gonderilecekGecmis(p.gecmis);
  const cevap = { rol: "asistan", icerik: "", model: p.model, yaziyor: true };
  p.gecmis.push(cevap);
  mesajlariCiz(p);

  const alan = $(".mesajlar", p.el);
  const balon = alan.lastElementChild;
  const baslangic = performance.now();
  p.denetleyici = new AbortController();
  calisanDegisti(+1);
  durumYaz(p, `${p.model} yanıtlıyor…`);

  try {
    const yanit = await fetch("/api/sohbet", {
      method: "POST",
      credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ saglayici: p.saglayici, model: p.model, mesajlar, sistem }),
      signal: p.denetleyici.signal,
    });
    const okuyucu = yanit.body.getReader();
    const cozucu = new TextDecoder();
    let tampon = "";
    for (;;) {
      const { value, done } = await okuyucu.read();
      if (done) break;
      tampon += cozucu.decode(value, { stream: true });
      let satirSonu;
      while ((satirSonu = tampon.indexOf("\n")) >= 0) {
        const satir = tampon.slice(0, satirSonu).trim();
        tampon = tampon.slice(satirSonu + 1);
        if (!satir) continue;
        const olay = JSON.parse(satir);
        if (olay.t) {
          const altta = alan.scrollHeight - alan.scrollTop - alan.clientHeight < 60;
          cevap.icerik += olay.t;
          balonDoldur(balon, cevap);
          if (altta) alan.scrollTop = alan.scrollHeight;
        } else if (olay.hata) {
          cevap.hata = olay.hata;
        }
      }
    }
  } catch (h) {
    if (h.name === "AbortError") cevap.durduruldu = true;
    else cevap.hata = `Uygulama sunucusuna ulaşılamadı: ${h.message}`;
  } finally {
    delete cevap.yaziyor;
    cevap.sure = ((performance.now() - baslangic) / 1000).toFixed(1);
    if (!cevap.icerik && !cevap.hata && !cevap.durduruldu) cevap.hata = "Model boş yanıt döndürdü.";
    balon.className = `balon asistan${cevap.hata && !cevap.icerik ? " hata" : ""}`;
    balonDoldur(balon, cevap);
    durumYaz(p, cevap.hata ? "Yanıt alınamadı." : `${cevap.icerik.length} karakter, ${cevap.sure} saniye`, Boolean(cevap.hata));
    p.denetleyici = null;
    calisanDegisti(-1);
    kaydet();
  }
}

function calisanDegisti(fark) {
  durum.calisan += fark;
  $("#durdur").hidden = durum.calisan === 0;
}

function gonder() {
  const metin = mesajKutusu.value.trim();
  if (!metin) return;
  const hedefler = durum.pencereler.filter((p) => p.gonderilsin);
  if (!hedefler.length) return bildir("Mesajın gideceği en az bir pencerede \"Gönder\" kutusunu işaretleyin.");
  const hazir = hedefler.filter((p) => p.saglayici && p.model && !p.denetleyici);
  const eksik = hedefler.length - hazir.length;
  if (!hazir.length) return bildir("İşaretli pencerelerde sağlayıcı ve model seçin (ya da önceki yanıtın bitmesini bekleyin).");
  if (eksik) bildir(`${eksik} pencere atlandı: model seçilmemiş ya da hâlâ yanıt yazıyor.`);
  mesajKutusu.value = "";
  const sistem = sistemKutusu.value.trim();
  hazir.forEach((p) => pencereyeGonder(p, metin, sistem));
}

// ------------------------------------------------------------ ayarlar penceresi

function ayarlariCiz() {
  const liste = $("#anahtarListesi");
  liste.innerHTML = "";
  for (const s of durum.saglayicilar.filter((x) => x.anahtar_gerekli)) {
    const satir = document.createElement("div");
    satir.className = "anahtar-satiri";
    const rozet = s.anahtar_kaynagi === "dosya" ? "Kayıtlı"
      : s.anahtar_kaynagi === "ortam" ? `Ortam değişkeni (${s.anahtar_ortam})` : "Anahtar yok";
    const ad = olustur("div", "ad", s.ad);
    const kucuk = olustur("small");
    if (s.nereden && /^https?:\/\//.test(s.nereden)) {
      const bag = olustur("a", "", "Anahtar al");
      bag.href = s.nereden; bag.target = "_blank"; bag.rel = "noopener";
      kucuk.append(bag);
    } else kucuk.append(s.adres);
    ad.append(kucuk);
    const girdi0 = olustur("input");
    girdi0.type = "password"; girdi0.autocomplete = "off";
    girdi0.placeholder = s.anahtar_kaynagi ? "Değiştirmek için yeni anahtar yazın" : "API anahtarını yapıştırın";
    const dugmeler = olustur("span");
    dugmeler.append(olustur("button", "birincil kaydet", "Kaydet"));
    if (s.anahtar_kaynagi === "dosya") dugmeler.append(" ", olustur("button", "sil", "Sil"));
    satir.append(ad, girdi0, olustur("span", `rozet ${s.anahtar_kaynagi ? "var" : ""}`, rozet), dugmeler);
    const girdi = $("input", satir);
    $(".kaydet", satir).addEventListener("click", () => anahtarKaydet(s, girdi.value));
    girdi.addEventListener("keydown", (e) => { if (e.key === "Enter") anahtarKaydet(s, girdi.value); });
    $(".sil", satir)?.addEventListener("click", () => {
      if (confirm(`${s.ad} anahtarı silinsin mi?`)) anahtarKaydet(s, null);
    });
    liste.append(satir);
  }

  const ozel = $("#ozelListe");
  ozel.innerHTML = "";
  for (const s of durum.saglayicilar.filter((x) => x.kaynak === "ozel")) {
    const satir = document.createElement("div");
    satir.className = "ozel-satir";
    const etiket = olustur("span", "", `${s.ad} `);
    etiket.append(olustur("small", "", `${s.adres} · ${s.tur}`));
    satir.append(etiket, olustur("button", "", "Kaldır"));
    $("button", satir).addEventListener("click", async () => {
      if (!confirm(`${s.ad} sağlayıcısı kaldırılsın mı?`)) return;
      await api("/api/saglayici-sil", { id: s.id });
      await yenidenYukle();
    });
    ozel.append(satir);
  }
}

async function yenidenYukle() {
  durum.modeller = {};
  await saglayicilariYukle();
  durum.pencereler.forEach(modelSeciminiCiz);
  ayarlariCiz();
}

// anahtar null ise kayıtlı anahtar silinir.
async function anahtarKaydet(s, anahtar) {
  if (anahtar !== null && !anahtar.trim()) return bildir("Önce anahtarı kutuya yapıştırın.");
  try {
    await api("/api/anahtar", { id: s.id, anahtar: anahtar === null ? "" : anahtar.trim() });
    bildir(anahtar === null ? `${s.ad} anahtarı silindi.` : `${s.ad} anahtarı kaydedildi.`);
    await yenidenYukle();
  } catch (h) {
    bildir(h.message);
  }
}

$("#saglayiciFormu").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  try {
    await api("/api/saglayici-ekle", Object.fromEntries(new FormData(form)));
    bildir(`${form.ad.value} eklendi. Artık pencerelerdeki sağlayıcı listesinde.`);
    form.reset();
    await yenidenYukle();
  } catch (h) {
    bildir(h.message);
  }
});

// ------------------------------------------------------------ olaylar ve başlangıç

$("#pencereEkle").addEventListener("click", () => { pencereEkle(); kaydet(); });
$("#ayarlarAc").addEventListener("click", () => { ayarlariCiz(); $("#ayarlar").showModal(); });
$("#gonder").addEventListener("click", gonder);
$("#durdur").addEventListener("click", () => durum.pencereler.forEach((p) => p.denetleyici?.abort()));
mesajKutusu.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    gonder();
  }
});
sistemKutusu.addEventListener("input", () => {
  try { localStorage.setItem(SISTEM_ANAHTARI, sistemKutusu.value); } catch { /* yok say */ }
});

$("#yerelTara").addEventListener("click", async (e) => {
  const dugme = e.currentTarget;
  dugme.disabled = true;
  dugme.textContent = "Taranıyor…";
  try {
    const { bulunanlar } = await api("/api/tara", {});
    await yenidenYukle();
    bildir(bulunanlar.length
      ? `Bulunan yerel servisler: ${bulunanlar.map((s) => `${s.ad} (${s.model_sayisi} model)`).join(", ")}`
      : "Çalışan yerel model servisi bulunamadı. Ollama ya da LM Studio'yu açıp tekrar tarayın.", 6000);
  } catch (h) {
    bildir(h.message);
  } finally {
    dugme.disabled = false;
    dugme.textContent = "Yerel modelleri tara";
  }
});

(async function baslat() {
  try { sistemKutusu.value = localStorage.getItem(SISTEM_ANAHTARI) || ""; } catch { /* yok say */ }
  try {
    durum.saglayicilar = await api("/api/saglayicilar");
  } catch (h) {
    bildir(`Uygulama sunucusuna ulaşılamadı: ${h.message}`, 10000);
  }
  const kayitli = yukle();
  if (kayitli && kayitli.length) kayitli.forEach(pencereEkle);
  else VARSAYILAN_PENCERELER.forEach((id) => pencereEkle({ saglayici: id }));
  kaydet();
  if (!durum.saglayicilar.some((s) => s.anahtar_gerekli && s.anahtar_kaynagi)) {
    bildir("Başlamak için Ayarlar'dan en az bir API anahtarı ekleyin ya da yerel modelleri tarayın.", 8000);
  }
  mesajKutusu.focus();
})();
