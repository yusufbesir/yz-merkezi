"use strict";
/* Güvenli Markdown -> DOM üretimi (HTML dizgesi hiç üretilmez; yalnızca createElement / textContent).
 *
 * Akış sırasında titreme olmaması için metin üst düzey bloklara bölünür; mdDom(kok, metin) yalnızca değişen
 * blokları yeniden kurar, değişmeyenlerin DOM'una dokunmaz (seçili metin, "Kopyala" düğmesi, kaydırma bozulmaz).
 *
 * Desteklenen: başlıklar, kalın, italik, satır içi kod, kod blokları (dil etiketi + Kopyala), sıralı/sırasız
 * listeler (iç içe), alıntı, yatay çizgi, tablo, http(s) bağlantıları.
 */
(function () {
  const BOS_SATIR = /^\s*$/;
  const KOD_CIT = /^ {0,3}(`{3,}|~{3,})\s*([\w+#.-]*)\s*$/;
  const BASLIK = /^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
  const CIZGI = /^ {0,3}([-*_])(\s*\1){2,}\s*$/;
  const LISTE = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/;
  const ALINTI = /^ {0,3}>\s?(.*)$/;
  const TABLO_AYRAC = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

  function e(etiket, sinif, metin) {
    const x = document.createElement(etiket);
    if (sinif) x.className = sinif;
    if (metin !== undefined) x.textContent = metin;
    return x;
  }

  // ---- bloklara bölme: boş satırlar bloğu ayırır; kod çitinin içindeki ve liste devamındaki boşluklar ayırmaz
  function bloklaraBol(metin) {
    const satirlar = String(metin).replace(/\r\n?/g, "\n").split("\n");
    const bloklar = [];
    let gecerli = [], cit = null;
    const bitir = () => { if (gecerli.length) bloklar.push(gecerli.join("\n")); gecerli = []; };
    for (let i = 0; i < satirlar.length; i++) {
      const s = satirlar[i];
      if (cit) {
        gecerli.push(s);
        const k = s.match(/^ {0,3}(`{3,}|~{3,})\s*$/);
        if (k && k[1][0] === cit[0] && k[1].length >= cit.length) { cit = null; bitir(); }
        continue;
      }
      const kod = s.match(KOD_CIT);
      if (kod) { bitir(); gecerli.push(s); cit = kod[1]; continue; }
      if (BOS_SATIR.test(s)) {
        const sonraki = satirlar.slice(i + 1).find((x) => !BOS_SATIR.test(x));
        const listedeyiz = gecerli.length && LISTE.test(gecerli[0]);
        const tur = (x) => (/\d/.test(x.match(LISTE)[2]) ? "o" : "u");
        const ayniTur = sonraki !== undefined && LISTE.test(sonraki) && (/^ {2,}\S/.test(sonraki) || (!listedeyiz || tur(sonraki) === tur(gecerli[0])));
        if (listedeyiz && sonraki !== undefined && (ayniTur || (!LISTE.test(sonraki) && /^ {2,}\S/.test(sonraki)))) { gecerli.push(s); continue; }
        bitir();
        continue;
      }
      // bir başlık ya da çizgi önceki paragrafı keser
      if (gecerli.length && (BASLIK.test(s) || CIZGI.test(s)) && !LISTE.test(gecerli[0])) bitir();
      gecerli.push(s);
      if (BASLIK.test(s) || CIZGI.test(s)) bitir();
    }
    bitir();
    return bloklar;
  }

  // ---- satır içi: `kod`, **kalın**, *italik*, [metin](adres), çıplak adresler
  const SATIR_ICI = /(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)|\*\*(?=\S)([\s\S]+?)(?<=\S)\*\*|__(?=\S)([\s\S]+?)(?<=\S)__|(?<![\w*])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![\w*])|(?<![\w_])_(?=[^\s_])([^_\n]+?)(?<=[^\s_])_(?![\w_])|\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<>)\]]+[^\s<>)\].,;:!?])/g;

  function satirIci(kok, metin) {
    let son = 0, m;
    const kalip = new RegExp(SATIR_ICI.source, "g");   // özyinelemeli çağrılar lastIndex'i paylaşmasın
    while ((m = kalip.exec(metin))) {
      if (m.index > son) kok.append(document.createTextNode(metin.slice(son, m.index)));
      if (m[2] !== undefined) kok.append(e("code", "", m[2].replace(/^ (.*) $/, "$1")));
      else if (m[3] !== undefined || m[4] !== undefined) { const b = e("strong"); satirIci(b, m[3] ?? m[4]); kok.append(b); }
      else if (m[5] !== undefined || m[6] !== undefined) { const i = e("em"); satirIci(i, m[5] ?? m[6]); kok.append(i); }
      else if (m[7] !== undefined) kok.append(baglanti(m[8], m[7]));
      else kok.append(baglanti(m[9], m[9]));
      son = m.index + m[0].length;
    }
    if (son < metin.length) kok.append(document.createTextNode(metin.slice(son)));
  }

  function baglanti(adres, yazi) {
    const a = e("a");
    a.textContent = yazi;
    try {
      const u = new URL(adres);
      if (u.protocol === "http:" || u.protocol === "https:") { a.href = u.href; a.target = "_blank"; a.rel = "noopener noreferrer"; }
    } catch (_) { /* geçersiz adres: düz metin kalır */ }
    return a;
  }

  // Bir paragrafın satırları: satır sonları korunur (<br>), böylece şiir/adres gibi metinler bozulmaz.
  function paragraf(satirlar) {
    const p = e("p");
    satirlar.forEach((s, i) => {
      if (i) p.append(e("br"));
      satirIci(p, s.replace(/\s+$/, "").replace(/^\s+/, ""));
    });
    return p;
  }

  function kodBlogu(satirlar) {
    const acilis = satirlar[0].match(KOD_CIT);
    const cit = acilis[1], dil = acilis[2] || "";
    let govde = satirlar.slice(1);
    if (govde.length) {
      const k = govde[govde.length - 1].match(/^ {0,3}(`{3,}|~{3,})\s*$/);
      if (k && k[1][0] === cit[0] && k[1].length >= cit.length) govde = govde.slice(0, -1);
    }
    const kod = govde.join("\n");
    const kok = e("div", "kod-blogu");
    const ust = e("div", "kod-ust");
    ust.append(e("span", "kod-dil", dil || "kod"));
    const kopya = e("button", "kod-kopyala", "Kopyala");
    kopya.type = "button";
    kopya.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(kod); kopya.textContent = "Kopyalandı"; }
      catch (_) { kopya.textContent = "Kopyalanamadı"; }
      setTimeout(() => { kopya.textContent = "Kopyala"; }, 1600);
    });
    ust.append(kopya);
    const pre = e("pre"), c = e("code");
    c.textContent = kod;
    pre.append(c);
    kok.append(ust, pre);
    return kok;
  }

  function liste(satirlar) {
    // girinti düzeyine göre iç içe listeler; her düzeyde işaretçi türü (sıralı/sırasız) ilk öğeden anlaşılır
    const kok = e("div");
    const yigin = [{ girinti: -1, el: kok, li: null }];
    for (const s of satirlar) {
      const m = s.match(LISTE);
      if (!m) {
        const son = yigin[yigin.length - 1].li;
        if (son && !BOS_SATIR.test(s)) { son.append(document.createTextNode(" "), ...parcala(s.trim())); }
        continue;
      }
      const girinti = m[1].replace(/\t/g, "    ").length, sirali = /\d/.test(m[2]);
      while (yigin.length > 1 && girinti < yigin[yigin.length - 1].girinti) yigin.pop();
      let ust = yigin[yigin.length - 1];
      if (girinti > ust.girinti && ust.li) {
        const yeni = e(sirali ? "ol" : "ul");
        if (sirali) yeni.start = parseInt(m[2], 10) || 1;
        ust.li.append(yeni);
        ust = { girinti, el: yeni, li: null };
        yigin.push(ust);
      } else if (ust.el === kok) {
        const yeni = e(sirali ? "ol" : "ul");
        if (sirali) yeni.start = parseInt(m[2], 10) || 1;
        kok.append(yeni);
        ust.el = yeni; ust.girinti = girinti;
      }
      const li = e("li");
      satirIci(li, m[3]);
      // görev kutusu işaretleri düz metin kalır
      ust.el.append(li);
      ust.li = li;
    }
    return kok.firstElementChild || kok;
  }

  function parcala(metin) {
    const gecici = e("span");
    satirIci(gecici, metin);
    return [...gecici.childNodes];
  }

  function hucreler(satir) {
    let s = satir.trim();
    if (s.startsWith("|")) s = s.slice(1);
    if (s.endsWith("|")) s = s.slice(0, -1);
    return s.split("|").map((x) => x.trim());
  }

  function tablo(satirlar) {
    const hizalar = hucreler(satirlar[1]).map((h) => (h.startsWith(":") && h.endsWith(":") ? "center" : h.endsWith(":") ? "right" : ""));
    const t = e("table"), ust = e("thead"), gv = e("tbody");
    const satir = (veri, etiket) => {
      const tr = e("tr");
      veri.forEach((h, i) => { const c = e(etiket); satirIci(c, h); if (hizalar[i]) c.style.textAlign = hizalar[i]; tr.append(c); });
      return tr;
    };
    ust.append(satir(hucreler(satirlar[0]), "th"));
    for (const s of satirlar.slice(2)) gv.append(satir(hucreler(s), "td"));
    t.append(ust, gv);
    const kap = e("div", "tablo-kap");
    kap.append(t);
    return kap;
  }

  function blokKur(src) {
    const satirlar = src.split("\n");
    const ilk = satirlar[0];
    if (KOD_CIT.test(ilk)) return kodBlogu(satirlar);
    const b = ilk.match(BASLIK);
    if (b && satirlar.length === 1) { const h = e("h" + Math.min(6, b[1].length + 1)); satirIci(h, b[2]); return h; }
    if (CIZGI.test(ilk) && satirlar.length === 1) return e("hr");
    if (satirlar.length >= 2 && ilk.includes("|") && TABLO_AYRAC.test(satirlar[1])) return tablo(satirlar);
    if (ALINTI.test(ilk) && satirlar.every((s) => ALINTI.test(s) || BOS_SATIR.test(s))) {
      const q = e("blockquote");
      const ic = satirlar.map((s) => (s.match(ALINTI) || ["", ""])[1]).join("\n");
      for (const alt of bloklaraBol(ic)) q.append(blokKur(alt));
      return q;
    }
    if (LISTE.test(ilk)) return liste(satirlar);
    return paragraf(satirlar);
  }

  /** kok içindeki içeriği metne göre günceller; yalnızca değişen blokları yeniden kurar. */
  function mdDom(kok, metin) {
    const bloklar = bloklaraBol(metin);
    const eski = kok._bloklar || [];
    const dugumler = [...kok.children].filter((c) => !c.classList.contains("imlec-kutu"));
    let i = 0;
    for (; i < bloklar.length; i++) {
      if (eski[i] === bloklar[i] && dugumler[i]) continue;
      const yeni = blokKur(bloklar[i]);
      if (dugumler[i]) dugumler[i].replaceWith(yeni); else kok.append(yeni);
      dugumler[i] = yeni;
    }
    for (let j = bloklar.length; j < dugumler.length; j++) dugumler[j].remove();
    kok._bloklar = bloklar;
  }

  window.mdDom = mdDom;
  window.mdBloklaraBol = bloklaraBol;
})();
