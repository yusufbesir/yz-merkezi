"""ChatGPT, Gemini ve Claude web siteleri için sayfada çalıştırılacak JavaScript parçaları.

Uygulama bu üç siteyi kendi tarayıcı penceresinde açar ve CDP `Runtime.evaluate`
(`returnByValue=True`, `awaitPromise=True`) ile buradaki JS metinlerini çalıştırır.
Bu modül yalnızca JS metinleri ve saf Python yardımcıları içerir; ağa, tarayıcıya
ya da başka bir modüle bağımlı değildir.

ÖNEMLİ: Seçiciler siteler güncellendikçe bozulabilir. Bir site arayüzünü değiştirirse
yalnızca aşağıdaki `_AYARLAR` sözlüğündeki ilgili sitenin seçici listesini güncellemek
yeterlidir; tek yer burasıdır. Her işlem için birkaç alternatif seçici ve genel bir
yedek yöntem vardır, listedeki ilk sonuç veren seçici kullanılır.

Her JS parçası `js_sar` ile `(async () => { try { ... } catch ... })()` biçiminde sarılır;
hata olursa `{"hata": "mesaj"}` döner, böylece Python tarafı hep geçerli JSON alır.
Hiçbir parça çerez, belirteç, e-posta ya da parola okumaz; yalnızca sohbet başlığı,
sohbet metni ve arayüz durumuna bakar.

Dönüş değerleri (anahtar: değer):
- giris_var_mi:       {"giris": bool, "sebep": str}
- sohbet_listesi:     [{"id": str, "baslik": str, "url": str}] (en çok 100)
- mesajlar:           {"baslik": str, "mesajlar": [{"rol": "kullanici"|"asistan", "metin": str}]}
- yaziyor_mu:         bool
- yazi_kutusunu_bul:  {"tamam": bool, "tur": "contenteditable"|"textarea", "sebep": str}
- gonder:             {"tamam": bool, "yontem": "dugme"|"enter_gerekli", "sebep": str}
                      ("enter_gerekli" ise düğme tıklanmadı, çağıran taraf Enter göndermelidir)
- son_yanit:          str
"""
import hashlib
import ipaddress
import json
import re
import urllib.parse

JS_ANAHTARLARI = (
    "giris_var_mi", "sohbet_listesi", "mesajlar", "yaziyor_mu",
    "yazi_kutusunu_bul", "gonder", "son_yanit",
)

# Genel yedek: site özel desen bulunamazsa her sitedeki sohbet adresleri bu desenlerle aranır.
# Her giriş (önek, düzenli ifade): ifadenin ilk grubu sohbet kimliğidir.
_GENEL_DESENLER = [
    ["", "/c/([^/?#]+)"],
    ["", "/app/([^/?#]+)"],
    ["", "/chat/([^/?#]+)"],
]

# ----------------------------------------------------------------- site ayarları
# Seçiciler burada; siteler değişince yalnızca bu bölümü güncelle.
_AYARLAR = {
    "chatgpt": {
        "url_desenleri": [["", "/c/([^/?#]+)"]],
        "giris_url": r"/auth/|/login|auth0\.com|auth\.openai\.com|/create-account",
        "giris_dugmeleri": [
            '[data-testid="login-button"]',
            '[data-testid="signup-button"]',
            'a[href^="/auth/login"]',
        ],
        "sohbet_gruplari": [[
            'nav a[href^="/c/"]',
            '[data-testid^="history-item"] a',
            'a[href*="/c/"]',
        ]],
        "kullanici": ['[data-message-author-role="user"]'],
        "asistan": ['[data-message-author-role="assistant"]'],
        "baslik_secicileri": ['nav a[aria-current="page"]', "nav a[data-active]"],
        "baslik_soneki": r"\s*[-|–—·]\s*ChatGPT\s*$",
        "durdur": [
            'button[data-testid="stop-button"]',
            'button[aria-label*="Stop streaming" i]',
            'button[aria-label*="Stop generating" i]',
        ],
        "yazi_kutusu": [
            "#prompt-textarea",
            'div.ProseMirror[contenteditable="true"]',
            'textarea[name="prompt-textarea"]',
        ],
        "gonder": [
            'button[data-testid="send-button"]',
            'button[aria-label*="Send" i]',
            'button[aria-label*="Gönder" i]',
            'button[aria-label*="Submit" i]',
            ".send-button",
        ],
    },
    "gemini": {
        "url_desenleri": [["", "/app/([^/?#]+)"]],
        "giris_url": r"accounts\.google\.com|/signin|ServiceLogin",
        "giris_dugmeleri": [
            'a[href*="accounts.google.com/ServiceLogin"]',
            'a[href*="accounts.google.com/signin"]',
            'a[href*="accounts.google.com/v3/signin"]',
            'a[href*="ServiceLogin"]',
        ],
        "sohbet_gruplari": [[
            'a[data-test-id="conversation"]',
            'conversations-list a[href*="/app/"]',
            '[data-test-id="conversation"]',
            ".conversation",
            'side-navigation-v2 a[href*="/app/"]',
        ]],
        "kullanici": [
            "user-query .query-text",
            ".query-text",
            "user-query",
            '[data-test-id="user-query"]',
        ],
        "asistan": [
            "model-response message-content",
            "model-response .markdown",
            ".model-response-text",
            "model-response",
            ".markdown",
        ],
        "baslik_secicileri": [
            ".conversation.selected .conversation-title",
            '[data-test-id="conversation"].selected',
            'a[data-test-id="conversation"][aria-current="page"]',
            'a[aria-current="page"]',
        ],
        "baslik_soneki": r"\s*[-|–—·]\s*(Google )?Gemini\s*$",
        "durdur": [
            "button.stop",
            'button[aria-label*="Stop response" i]',
            'button[aria-label*="Yanıtı durdur" i]',
            'mat-icon[fonticon="stop"]',
            ".stop-icon",
        ],
        "yazi_kutusu": [
            '.ql-editor[contenteditable="true"]',
            'rich-textarea .ql-editor',
            'rich-textarea [contenteditable="true"]',
            'div[contenteditable="true"][role="textbox"]',
        ],
        "gonder": [
            "button.send-button",
            'button[aria-label*="Send message" i]',
            'button[aria-label*="Mesajı gönder" i]',
            'button[aria-label*="Send" i]',
            'button[aria-label*="Gönder" i]',
            'button[aria-label*="Submit" i]',
            ".send-button",
        ],
    },
    "claude": {
        "url_desenleri": [["", "/chat/([^/?#]+)"], ["proje-", "/project/([^/?#]+)"]],
        "giris_url": r"/login|/signup|/magic-link|/logout",
        "giris_dugmeleri": [
            '[data-testid="login-button"]',
            'a[href^="/login"]',
            'a[href*="/login?"]',
        ],
        "sohbet_gruplari": [
            ['nav a[href^="/chat/"]', 'a[href^="/chat/"]'],
            ['a[href^="/project/"]'],
        ],
        "kullanici": [
            '[data-testid="user-message"]',
            ".font-user-message",
        ],
        "asistan": [
            ".font-claude-message",
            ".font-claude-response",
            '[data-testid="assistant-message"]',
            "[data-is-streaming]",
        ],
        "baslik_secicileri": [
            '[data-testid="chat-title-button"]',
            'header [data-testid*="title"]',
        ],
        "baslik_soneki": r"\s*[-|–—·]\s*Claude\s*$",
        "durdur": [
            'button[aria-label="Stop response"]',
            'button[aria-label*="Stop response" i]',
            '[data-is-streaming="true"]',
        ],
        "yazi_kutusu": [
            'div.ProseMirror[contenteditable="true"]',
            '.ProseMirror[contenteditable="true"]',
            'fieldset div[contenteditable="true"]',
            'div[contenteditable="true"]',
        ],
        "gonder": [
            'button[aria-label="Send message"]',
            'button[aria-label*="Send" i]',
            'button[aria-label*="Gönder" i]',
            'button[aria-label*="Submit" i]',
            'button[type="submit"]',
        ],
    },
}

# kimlik -> (ad, adres, yeni sohbet adresi, renk, pencere parçası, giriş sayfası parçaları)
# pencere parçası: sitenin sekmesini tanımak için adreste aranan metin (alan adı);
# giriş sayfası parçaları: oturum açma sırasında sekmenin gittiği başka alan adları.
_BILGILER = {
    "chatgpt": ("ChatGPT", "https://chatgpt.com", "https://chatgpt.com/", "#10a37f",
                "chatgpt.com", ["auth.openai.com"]),
    "gemini": ("Gemini", "https://gemini.google.com/app", "https://gemini.google.com/app", "#4285f4",
               "gemini.google.com", ["accounts.google.com"]),
    "claude": ("Claude", "https://claude.ai", "https://claude.ai/new", "#d97757",
               "claude.ai", []),
}

# ----------------------------------------------------------------- ortak JS yardımcıları

_YARDIMCI = r"""
const gorunur = (e) => { try { return !!e && (e.offsetParent !== null || e.getClientRects().length > 0); } catch (x) { return false; } };
const kes = (s, n) => { s = String(s == null ? "" : s); return s.length > n ? s.slice(0, n) : s; };
const temiz = (s) => String(s == null ? "" : s).replace(/\s+/g, " ").trim();
const bekle = (ms) => new Promise((coz) => setTimeout(coz, ms));
const sec = (secici, kok) => { try { return Array.prototype.slice.call((kok || document).querySelectorAll(secici)); } catch (x) { return []; } };
const ilkDolu = (secenekler, suz, kok) => {
  for (const s of (secenekler || [])) {
    let l = sec(s, kok);
    if (suz) { l = l.filter(suz); }
    if (l.length) { return l; }
  }
  return [];
};
const mutlak = (h) => { try { return new URL(h, location.href).href; } catch (x) { return ""; } };
const urlKimligi = (url) => {
  let yol = "";
  try { yol = new URL(url, location.href).pathname; } catch (x) { yol = String(url); }
  const desenler = AYAR.url_desenleri.concat(AYAR.genel_desenler);
  for (const d of desenler) {
    const m = new RegExp(d[1]).exec(yol);
    if (m && m[1]) { return d[0] + m[1]; }
  }
  return "";
};
"""

_YAZI_YARDIMCI = r"""
const yaziKutusuBul = () => {
  let adaylar = ilkDolu(AYAR.yazi_kutusu, gorunur);
  if (!adaylar.length) {
    adaylar = sec('[contenteditable="true"], [contenteditable="plaintext-only"], textarea').filter(gorunur);
  }
  return adaylar.length ? adaylar[adaylar.length - 1] : null;
};
const kutuTuru = (el) => (el.tagName === "TEXTAREA" || el.tagName === "INPUT") ? "textarea" : "contenteditable";
"""

_MESAJ_YARDIMCI = r"""
const sayfaBasligi = () => {
  for (const s of AYAR.baslik_secicileri) {
    const l = sec(s).filter(gorunur);
    const t = l.length ? temiz(l[0].innerText || l[0].textContent) : "";
    if (t) { return kes(t, 200); }
  }
  const ham = temiz(document.title);
  const kisa = ham.replace(new RegExp(AYAR.baslik_soneki, "i"), "");
  return kes(kisa || ham, 200);
};
const rolIpucu = (el) => {
  let e = el;
  for (let i = 0; i < 3 && e && e !== document.body; i++) {
    let s = Array.prototype.map.call(e.attributes || [], (a) => a.name + "=" + a.value).join(" ").toLowerCase();
    s = s.replace(/user-select[\w-]*/g, "").replace(/prompt/g, "");
    if (/user|human|query|kullanıcı/.test(s)) { return "kullanici"; }
    if (/assistant|model|claude|bot|response|gemini|chatgpt|answer/.test(s)) { return "asistan"; }
    e = e.parentElement;
  }
  return "";
};
const genelMesajlar = () => {
  const kok = document.querySelector("main") || document.body;
  let bloklar = sec("article, section, [data-testid*='message' i], [class*='message' i]", kok).filter(gorunur);
  bloklar = bloklar.filter((e) => !bloklar.some((o) => o !== e && e.contains(o)));
  let sonRol = "";
  const cikti = [];
  bloklar.forEach((e) => {
    let rol = rolIpucu(e);
    if (!rol) { rol = sonRol === "kullanici" ? "asistan" : "kullanici"; }
    sonRol = rol;
    cikti.push({ el: e, rol: rol });
  });
  return cikti;
};
const mesajlariTopla = () => {
  let liste = [];
  const grupEkle = (secenekler, rol) => {
    const l = ilkDolu(secenekler);
    l.filter((e) => !l.some((o) => o !== e && o.contains(e))).forEach((e) => liste.push({ el: e, rol: rol }));
  };
  grupEkle(AYAR.kullanici, "kullanici");
  const kullanicilar = liste.slice();
  grupEkle(AYAR.asistan, "asistan");
  liste = liste.filter((m) => m.rol === "kullanici" || !kullanicilar.some((k) => m.el.contains(k.el)));
  if (!liste.length) { liste = genelMesajlar(); }
  liste.sort((a, b) => (a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1);
  const sonuc = [];
  liste.forEach((m) => {
    const metin = String(m.el.innerText || m.el.textContent || "").trim();
    if (metin) { sonuc.push({ rol: m.rol, metin: metin }); }
  });
  return sonuc.slice(-400);
};
"""

# ----------------------------------------------------------------- JS gövdeleri

_GIRIS_VAR_MI = r"""
if (new RegExp(AYAR.giris_url).test(location.href)) {
  return { giris: false, sebep: "Giriş sayfasındasın (" + location.pathname + ")" };
}
for (const s of AYAR.giris_dugmeleri) {
  if (sec(s).some(gorunur)) { return { giris: false, sebep: "Giriş yap düğmesi görünüyor" }; }
}
const girisMetni = /^(log ?in|sign ?in|sign up|sign up for free|continue with (google|email)|oturum aç|oturum açın|giriş yap|kaydol|ücretsiz kaydol)$/i;
const dugmeler = sec("a, button, [role='button']").filter(gorunur);
const bulunan = dugmeler.find((b) => {
  const t = temiz(b.textContent);
  return t.length > 0 && t.length <= 30 && girisMetni.test(t);
});
if (bulunan) { return { giris: false, sebep: "Giriş düğmesi görünüyor: " + kes(temiz(bulunan.textContent), 30) }; }
const kutu = ilkDolu(AYAR.yazi_kutusu, gorunur);
const sohbetler = sec("a[href]").some((a) => urlKimligi(a.getAttribute("href")) !== "");
if (kutu.length || sohbetler) { return { giris: true, sebep: "Yazı kutusu ya da sohbet listesi var, giriş düğmesi yok" }; }
if (document.readyState !== "complete") { return { giris: false, sebep: "Sayfa henüz yükleniyor" }; }
return { giris: false, sebep: "Yazı kutusu bulunamadı; oturum açılmamış ya da sayfa hazır değil" };
"""

_SOHBET_LISTESI = r"""
const girdiyeCevir = (el) => {
  const a = el.tagName === "A" ? el : (el.closest("a[href]") || el.querySelector("a[href]"));
  const href = a ? String(a.getAttribute("href") || "") : "";
  if (!href || href.charAt(0) === "#" || /^(javascript|mailto):/i.test(href)) { return null; }
  const url = mutlak(href);
  const id = urlKimligi(url);
  if (!url || !id || id === "new") { return null; }
  const satirlar = String(el.innerText || el.textContent || "").split("\n").map(temiz).filter(Boolean);
  const baslik = satirlar[0] || temiz(el.getAttribute("aria-label")) || temiz(a.getAttribute("title"));
  return { id: id, baslik: kes(baslik, 200), url: url };
};
const gruptan = (secenekler) => {
  for (const s of secenekler) {
    const sonuc = sec(s).map(girdiyeCevir).filter(Boolean);
    if (sonuc.length) { return sonuc; }
  }
  return [];
};
const tekilYap = (liste) => {
  const goruldu = new Set();
  return liste.filter((k) => {
    const anahtar = k.url.split("#")[0];
    if (goruldu.has(anahtar)) { return false; }
    goruldu.add(anahtar);
    return true;
  });
};
const topla = () => {
  let sonuc = [];
  for (const grup of AYAR.sohbet_gruplari) { sonuc = sonuc.concat(gruptan(grup)); }
  sonuc = tekilYap(sonuc);
  if (!sonuc.length) { sonuc = tekilYap(sec("a[href]").map(girdiyeCevir).filter(Boolean)); }
  return sonuc;
};
const kenarCubuguAc = async () => {
  const ara = /sidebar|kenar|menü|menu/i;
  const yok = /profil|profile|account|hesap|user|kullanıcı|settings|ayarlar/i;
  const dugme = sec("button, [role='button']").filter(gorunur).find((b) => {
    const e = temiz(b.getAttribute("aria-label") || b.getAttribute("title") || "");
    return e !== "" && ara.test(e) && !yok.test(e);
  });
  if (!dugme) { return false; }
  dugme.click();
  return true;
};
let sonuc = topla();
if (!sonuc.length && await kenarCubuguAc()) {
  await bekle(800);
  sonuc = topla();
}
return sonuc.slice(0, 100);
"""

_MESAJLAR = r"""
const m = mesajlariTopla();
return {
  baslik: sayfaBasligi(),
  mesajlar: m.map((x) => ({ rol: x.rol, metin: kes(x.metin, 20000) }))
};
"""

_YAZIYOR_MU = r"""
if (sec('[data-is-streaming="true"]').length) { return true; }
for (const s of AYAR.durdur) {
  if (sec(s).some(gorunur)) { return true; }
}
const durdurMetni = /^stop$|stop (generating|streaming|response|answer|thinking)|durdur/i;
return sec("button, [role='button']").filter(gorunur).some((b) =>
  durdurMetni.test(temiz(b.getAttribute("aria-label") || b.getAttribute("title") || ""))
);
"""

_YAZI_KUTUSUNU_BUL = r"""
const el = yaziKutusuBul();
if (!el) { return { tamam: false, tur: "contenteditable", sebep: "Yazı kutusu bulunamadı" }; }
const tur = kutuTuru(el);
try { el.scrollIntoView({ block: "nearest" }); } catch (x) { /* önemsiz */ }
el.focus();
if (tur === "textarea") {
  const ayarla = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value");
  if (ayarla && ayarla.set) { ayarla.set.call(el, ""); } else { el.value = ""; }
  el.dispatchEvent(new Event("input", { bubbles: true }));
} else {
  const secim = window.getSelection();
  const aralik = document.createRange();
  aralik.selectNodeContents(el);
  secim.removeAllRanges();
  secim.addRange(aralik);
  try { document.execCommand("delete"); } catch (x) { /* yedek aşağıda */ }
  if (temiz(el.innerText) !== "") {
    el.textContent = "";
    el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContent" }));
  }
  const son = document.createRange();
  son.selectNodeContents(el);
  son.collapse(false);
  secim.removeAllRanges();
  secim.addRange(son);
}
const bos = tur === "textarea" ? el.value === "" : temiz(el.innerText) === "";
const odakta = document.activeElement === el || el.contains(document.activeElement);
if (!bos) { return { tamam: false, tur: tur, sebep: "Yazı kutusunun içeriği temizlenemedi" }; }
if (!odakta) { return { tamam: false, tur: tur, sebep: "Yazı kutusu odaklanamadı" }; }
return { tamam: true, tur: tur, sebep: "Yazı kutusu hazır" };
"""

_GONDER = r"""
const etkin = (b) => !!b && gorunur(b) && !b.disabled && b.getAttribute("aria-disabled") !== "true";
const a = document.activeElement;
const kutu = (a && (a.isContentEditable || a.tagName === "TEXTAREA" || a.tagName === "INPUT")) ? a : yaziKutusuBul();
const secenekler = AYAR.gonder.concat(['form button[type="submit"]']);
const kapsamlar = [];
if (kutu) {
  const form = kutu.closest("form");
  if (form) { kapsamlar.push(form); }
  let ata = kutu;
  for (let i = 0; i < 6 && ata.parentElement; i++) { ata = ata.parentElement; }
  kapsamlar.push(ata);
}
kapsamlar.push(document);
const dugmeBul = (suz) => {
  for (const kapsam of kapsamlar) {
    for (const s of secenekler) {
      const b = sec(s, kapsam).filter(suz)[0];
      if (b) { return b; }
    }
  }
  return null;
};
let pasif = null;
for (let i = 0; i < 8; i++) {
  const b = dugmeBul(etkin);
  if (b) {
    b.click();
    return { tamam: true, yontem: "dugme", sebep: "Gönder düğmesine tıklandı" };
  }
  pasif = dugmeBul((x) => gorunur(x));
  await bekle(250);
}
return {
  tamam: false,
  yontem: "enter_gerekli",
  sebep: pasif ? "Gönder düğmesi pasif; Enter ile denenmeli" : "Gönder düğmesi bulunamadı; Enter ile denenmeli"
};
"""

_SON_YANIT = r"""
const asistan = mesajlariTopla().filter((x) => x.rol === "asistan");
return asistan.length ? kes(asistan[asistan.length - 1].metin, 20000) : "";
"""

# anahtar -> (ek yardımcılar, gövde)
_PARCALAR = {
    "giris_var_mi": ("", _GIRIS_VAR_MI),
    "sohbet_listesi": ("", _SOHBET_LISTESI),
    "mesajlar": (_MESAJ_YARDIMCI, _MESAJLAR),
    "yaziyor_mu": ("", _YAZIYOR_MU),
    "yazi_kutusunu_bul": (_YAZI_YARDIMCI, _YAZI_KUTUSUNU_BUL),
    "gonder": (_YAZI_YARDIMCI, _GONDER),
    "son_yanit": (_MESAJ_YARDIMCI, _SON_YANIT),
}


# ----------------------------------------------------------------- Python yardımcıları

def js_sar(parca):
    """JS gövdesini async IIFE içinde try/catch ile sarar; hata olursa {"hata": mesaj} döner.

    `parca`, `return` ile değer döndüren deyimler dizisidir (await kullanabilir).
    """
    return (
        "(async () => {\n"
        "  try {\n"
        + parca
        + "\n  } catch (hata) {\n"
        "    return { hata: String(hata && hata.message ? hata.message : hata) };\n"
        "  }\n"
        "})()"
    )


def _parca_uret(site_id, anahtar):
    """Bir sitenin bir işlemi için tam, sarılmış JS metnini üretir."""
    ayar = dict(_AYARLAR[site_id])
    ayar["genel_desenler"] = _GENEL_DESENLER
    ek, govde = _PARCALAR[anahtar]
    giris = "const AYAR = " + json.dumps(ayar, ensure_ascii=True) + ";\n"
    return js_sar(giris + _YARDIMCI + ek + govde)


def _kayit(site_id):
    ad, adres, yeni, renk, parca, giris_parcalari = _BILGILER[site_id]
    return {
        "id": site_id,
        "ad": ad,
        "adres": adres,
        "yeni_sohbet_adresi": yeni,
        "renk": renk,
        "pencere_parcasi": parca,
        "giris_parcalari": list(giris_parcalari),
        "js": {anahtar: _parca_uret(site_id, anahtar) for anahtar in JS_ANAHTARLARI},
    }


SITELER = {site_id: _kayit(site_id) for site_id in _BILGILER}


def site(site_id):
    """Site kaydını döndürür; bilinmeyen kimlik için KeyError verir."""
    try:
        return SITELER[site_id]
    except KeyError:
        raise KeyError("Bilinmeyen site: %r (olanlar: %s)" % (site_id, ", ".join(SITELER))) from None


def adres_eslesir_mi(url, parca):
    """Adres (url), parça ("alanadi[:port][/yol-oneki]") ile tam bir alan adı sınırında eşleşiyor mu?

    Kurallar (alt dize eşleşmesi YOK):
    - şema http veya https olmalı; boşluk, denetim karakteri ve ters bölü içeren adresler reddedilir;
    - ana bilgisayar adı (küçük harf, sondaki nokta atılmış) parçanın alan adına tam eşit ya da onun
      alt alanı ("." + alan ile biten) olmalı (IP adresinde yalnızca tam eşitlik);
    - parçada port varsa adresin (açık ya da şemanın varsayılan) portu tam eşit olmalı;
    - parçada yol öneki varsa adresin yolu o önekle başlamalı (".", ".." yol parçaları reddedilir).
    """
    if not isinstance(url, str) or not isinstance(parca, str) or not url or not parca:
        return False
    if any(ord(c) <= 32 or ord(c) == 127 or c == "\\" for c in url + parca):
        return False
    try:
        u = urllib.parse.urlsplit(url)
        p = urllib.parse.urlsplit("//" + parca)
        host, alan = u.hostname, p.hostname
        url_port, parca_port = u.port, p.port
    except ValueError:
        return False
    sema = u.scheme.lower()
    if sema not in ("http", "https") or not host or not alan:
        return False
    host = host.lower().rstrip(".")
    alan = alan.lower().rstrip(".")
    if not host or not alan:
        return False
    try:
        ipaddress.ip_address(alan)
        ip_mi = True
    except ValueError:
        ip_mi = False
    if host != alan and (ip_mi or not host.endswith("." + alan)):
        return False
    if parca_port is not None and (url_port or (443 if sema == "https" else 80)) != parca_port:
        return False
    if p.path and p.path != "/":
        if any(s in (".", "..") for s in u.path.split("/")) or not u.path.startswith(p.path):
            return False
    return True


def sohbet_kimligi(site_id, url):
    """Sohbet adresinden kararlı kimlik üretir: 'chatgpt:abc123', 'claude:uuid'.

    Tanınan bir sohbet deseni yoksa adresin SHA-1 karmasının ilk 12 hanesi kullanılır.
    """
    url = str(url or "")
    yol = re.sub(r"^[a-z][a-z0-9+.-]*://[^/]*", "", url, flags=re.I)  # alan adını at
    yol = re.split(r"[?#]", yol, maxsplit=1)[0]
    desenler = list(_AYARLAR.get(site_id, {}).get("url_desenleri", [])) + _GENEL_DESENLER
    for onek, desen in desenler:
        eslesme = re.search(desen, yol)
        if eslesme and eslesme.group(1):
            return "%s:%s%s" % (site_id, onek, eslesme.group(1))
    return "%s:%s" % (site_id, hashlib.sha1(url.encode("utf-8")).hexdigest()[:12])


def _dengeli_mi(js):
    """Parantez, köşeli ve küme ayraçlarının dengesini denetler; sorun yoksa None, varsa açıklama döner.

    Metinleri, yorumları ve düzenli ifade değişmezlerini (regex) atlar.
    """
    eslesen = {")": "(", "]": "[", "}": "{"}
    yigin = []
    i, n = 0, len(js)
    onceki = ""  # son anlamlı karakter
    regex_oncesi = "(,=:[!&|?{};+-*%<>~^"
    while i < n:
        c = js[i]
        sonraki = js[i + 1] if i + 1 < n else ""
        if c.isspace():
            i += 1
            continue
        if c in "'\"`":
            j = i + 1
            while j < n and js[j] != c:
                if js[j] == "\\":
                    j += 1
                elif c != "`" and js[j] == "\n":
                    return "kapanmamış metin (satır sonu)"
                j += 1
            if j >= n:
                return "kapanmamış metin"
            i, onceki = j + 1, "a"
            continue
        if c == "/" and sonraki == "/":
            j = js.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and sonraki == "*":
            j = js.find("*/", i + 2)
            if j < 0:
                return "kapanmamış yorum"
            i = j + 2
            continue
        if c == "/":
            if onceki == "" or onceki in regex_oncesi or js[:i].rstrip().endswith("return"):
                j, sinif = i + 1, False
                while j < n:
                    ch = js[j]
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "[":
                        sinif = True
                    elif ch == "]":
                        sinif = False
                    elif ch == "/" and not sinif:
                        break
                    elif ch == "\n":
                        return "kapanmamış düzenli ifade"
                    j += 1
                if j >= n:
                    return "kapanmamış düzenli ifade"
                j += 1
                while j < n and js[j].isalpha():
                    j += 1
                i, onceki = j, "a"
            else:
                i, onceki = i + 1, "/"
            continue
        if c in "([{":
            yigin.append(c)
        elif c in ")]}":
            if not yigin or yigin.pop() != eslesen[c]:
                return "dengesiz ayraç %r (konum %d)" % (c, i)
        onceki = c
        i += 1
    if yigin:
        return "kapatılmamış ayraç: " + "".join(yigin)
    return None


def js_dogrula():
    """Tüm JS parçalarını kabaca denetler; sorun listesi döndürür (boş liste = sorun yok)."""
    sorunlar = []
    for site_id, kayit in SITELER.items():
        js = kayit["js"]
        for anahtar in JS_ANAHTARLARI:
            ad = "%s/%s" % (site_id, anahtar)
            parca = js.get(anahtar)
            if not parca:
                sorunlar.append("%s: parça yok" % ad)
                continue
            if not parca.startswith("(async () =>") or not parca.rstrip().endswith("})()"):
                sorunlar.append("%s: async IIFE ile sarılı değil" % ad)
            if "catch (hata)" not in parca:
                sorunlar.append("%s: try/catch yok" % ad)
            sorun = _dengeli_mi(parca)
            if sorun:
                sorunlar.append("%s: %s" % (ad, sorun))
    return sorunlar
