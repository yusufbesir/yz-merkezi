"""Gönderme öncesi hassas bilgi taraması ve geçmiş için maskeleme (kural tabanlı, yalnızca standart kütüphane).

Mesaj metninde API anahtarı/erişim belirteci, özel anahtar bloğu, parolalı bağlantı dizesi, parola, T.C. kimlik
numarası, IBAN, kart numarası; düşük önemle Türk cep telefonu ve e-posta adresi; yalnız uyarı olarak da yüksek
entropili (rastgele görünen) uzun dizeler aranır. Hiçbir şey ağa gitmez, hiçbir şey kaydedilmez; `tara()` yalnızca
kategori, eşleşme sayısı ve maskeli bir örnek (ilk 4 karakter + ***) döndürür.

Kategoriler ve öncelik (birden çok varsa ilk bulunan seçilir):
    api_anahtari > parola > kimlik > finansal       önem "yuksek": gönderimden önce onay istenir
    olasi_anahtar > kisisel                          önem "dusuk": yalnızca uyarı (gönderimi durdurmaz)

`maskele(metin)` bulunan değerleri `[GİZLİ:<kategori>]` etiketiyle değiştirir (sohbet geçmişine yazmadan önce);
e-posta ve telefon (kişisel, düşük önem) geçmişte maskelenmez.
"""
import math
import re
from collections import Counter

KATEGORILER = ("api_anahtari", "parola", "kimlik", "finansal", "olasi_anahtar", "kisisel")
YUKSEK = ("api_anahtari", "parola", "kimlik", "finansal")
DUSUK = ("olasi_anahtar", "kisisel")
MASKELENEN = ("api_anahtari", "parola", "kimlik", "finansal", "olasi_anahtar")

ACIKLAMALAR = {
    "api_anahtari": "bir API anahtarı",
    "parola": "bir parola",
    "kimlik": "bir T.C. kimlik numarası",
    "finansal": "bir IBAN ya da kart numarası",
    "olasi_anahtar": "rastgele görünen uzun bir dize (bir anahtar ya da belirteç olabilir)",
    "kisisel": "kişisel iletişim bilgisi (telefon numarası ya da e-posta adresi)",
}
UZUN_ACIKLAMA = "çok uzun bir metin (tamamı taranır; yine de göndermeden önce onay gerekir)"
ENTROPI_ESIGI = 4.5        # bit/karakter: base64 benzeri dizeler için
HEX_ENTROPI_ESIGI = 3.5    # bit/karakter: onaltılık dizelerin en yüksek entropisi 4'tür
ENTROPI_EN_AZ = 32         # karakter
GIRDI_SINIRI = 100_000     # karakter: tek tarama parçasının boyu (daha uzun metin parça parça taranır; süre doğrusal kalır)
ORTUSME = 512              # karakter: ardışık parçaların örtüşmesi (parça sınırındaki sır kaçmasın)

_SOL = r"(?<![A-Za-z0-9_])"  # kalıp başka bir sözcüğün ortasında başlamasın
_SAG = r"(?![A-Za-z0-9_])"


def _k(desen, bayrak=0):
    return re.compile(desen, bayrak)


# ---- API anahtarları, erişim belirteçleri ve özel anahtar blokları
_API_KALIPLARI = [
    # özel anahtar bloğu (RSA/EC/DSA/OPENSSH/PGP/ENCRYPTED): BEGIN satırından END satırına (yoksa metnin sonuna) kadar
    _k(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----(?:[\s\S]*?-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----|[\s\S]*\Z)"),
    _k(r"-----BEGIN [A-Z ]*PRIVATE KEY"),
    _k(_SOL + r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),                 # JWT
    _k(r"(?<![A-Za-z0-9_])[Bb]earer[ \t]+(?P<deger>[A-Za-z0-9._~+/=-]{16,})"),                  # Authorization: Bearer
    _k(_SOL + r"(?:AKIA|ASIA)[0-9A-Z]{16}" + _SAG),                                               # AWS erişim anahtarı
    _k(r"(?i)aws[\w .-]{0,20}?(?:secret|private)[\w .-]{0,20}?[\"']?[ \t]*[:=][ \t]*[\"']?"
       r"(?P<deger>[A-Za-z0-9/+=]{40})(?![A-Za-z0-9/+=])"),                                      # AWS gizli anahtarı
    _k(_SOL + r"ya29\.[0-9A-Za-z_-]{20,}"),                                                       # Google OAuth
    _k(_SOL + r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}"),                                       # GitHub
    _k(_SOL + r"github_pat_[A-Za-z0-9_]{30,}"),
    _k(_SOL + r"xox[abprs]-[0-9A-Za-z-]{10,}"),                                                   # Slack
    _k(_SOL + r"(?:sk|rk)_live_[0-9A-Za-z]{16,}"),                                                # Stripe
    _k(_SOL + r"SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),                                     # SendGrid
    _k(_SOL + r"SK[0-9a-f]{32}" + _SAG),                                                          # Twilio
    _k(_SOL + r"sk-(?:ant|proj|svcacct)-[A-Za-z0-9_-]{10,}"),
    _k(_SOL + r"sk-[A-Za-z0-9]{16,}"),
    _k(_SOL + r"AIza[0-9A-Za-z_-]{30,}"),
]

# ---- parolalı bağlantı dizeleri (değer kısmı maskelenir)
_BAGLANTI_KALIPLARI = [
    _k(r"(?i)(?<![A-Za-z0-9+])(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqps?|mssql|sqlserver)"
       r"://[^\s:/@]+:(?P<deger>[^\s@/]+)@"),
    _k(r"(?i)(?:Server|Data Source|Host|Address)[ \t]{0,8}=[^;\n]{1,200};[^\n]{0,200}?(?:Password|Pwd)[ \t]{0,8}=[ \t]{0,8}(?P<deger>[^;\s]{1,128})"),
]

# ---- IBAN (TR + 2 kontrol hanesi + 22 hane, 4'lü gruplar boşluklu ya da bitişik)
_IBAN = _k(_SOL + r"TR\d{2}[ ]?(?:\d{4}[ ]?){5}\d{2}(?!\d)", re.IGNORECASE)

# ---- 11 haneli kimlik ve 16 haneli kart adayları (sayının ortasından başlamasın)
_ONBIR_HANE = _k(r"(?<!\d)[1-9]\d{10}(?!\d)")
_KART = _k(r"(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)")

# ---- parola: "parola|şifre|password|pin" + [:=] + değer (aynı satırda)
_PAROLA_ANAHTARI = r"(?:(?:parola|[sşSŞ][iİıI]fre|password|passwd|pwd)[a-zA-ZçğıöşüÇĞİÖŞÜ]{0,6}|pin)"
_PAROLA = _k(_SOL + _PAROLA_ANAHTARI + r"[ \t]{0,8}[:=][ \t]{0,8}[\"']?(?P<deger>[^\s\"',;]{3,128})", re.IGNORECASE)

# ---- e-posta + parola çifti: "kisi@ornek.com:Parola123!" ya da "kisi@ornek.com / Parola123!"
# Geri izleme yaratmamak için her niceleyici sınırlıdır (yerel kısım {1,64}, alan adı etiketleri {1,63} x en çok 8).
_EPOSTA_PAROLA = _k(
    r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}[ \t]{0,8}[:|/;,][ \t]{0,8}"
    r"(?=\S{0,128}[A-Za-z])(?=\S{0,128}[\d!@#$%^&*?])(?![\w.+-]{1,64}@)(?!https?:)(?P<deger>[^\s\"',;]{6,128})"
)

# ---- kişisel (düşük önem): Türk cep telefonu ve e-posta adresi
_TELEFON = _k(r"(?<![\d+])(?:\+90[ \t]?|0)?5\d{2}[ \t]?\d{3}[ \t]?\d{2}[ \t]?\d{2}(?!\d)")
_EPOSTA = _k(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){0,8}\.[A-Za-z]{2,63}(?![\w-])")

# ---- yalnız uyarı: yüksek entropili uzun dizeler. URL'nin şema/ana makine/yol kısmı taramadan muaftır; sorgu ve
# parça kısmı (?token=..., &key=...) MUAF DEĞİLDİR: oradaki değerler de taranır.
_URL = _k(r"(?i)\b(?:https?|ftp)://[^\s<>\"'?#]+")
_ENTROPI_ADAYI = _k(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{%d,}(?![A-Za-z0-9+/=_-])" % ENTROPI_EN_AZ)

_ENGEL = "\x00"


def ornek_maskele(parca):
    """İlk 4 karakter + ***: kimlik ve anahtarın geri kalanı hiçbir zaman gösterilmez (sonuçtaki "ornek" alanı)."""
    return str(parca)[:4] + "***"


def shannon_entropisi(metin):
    """Karakter başına Shannon entropisi (bit)."""
    if not metin:
        return 0.0
    n = len(metin)
    return -sum(c / n * math.log2(c / n) for c in Counter(metin).values())


def _yuksek_entropili_mi(aday):
    s = aday.rstrip("=")
    if len(s) < ENTROPI_EN_AZ or not re.search(r"\d", s) or not re.search(r"[A-Za-z]", s):
        return False
    if re.fullmatch(r"[0-9a-fA-F]+", s):
        return shannon_entropisi(s.lower()) > HEX_ENTROPI_ESIGI
    if not (re.search(r"[a-z]", s) and re.search(r"[A-Z]", s)):  # tireli sözcük dizileri, küçük harfli yollar ...
        return False
    return shannon_entropisi(s) > ENTROPI_ESIGI


def tc_kimlik_gecerli_mi(sayi):
    """11 haneli T.C. kimlik numarası algoritması: 10. ve 11. hane kuralları, ilk hane 0 olamaz."""
    s = re.sub(r"\D", "", str(sayi))
    if len(s) != 11 or s[0] == "0":
        return False
    h = [int(c) for c in s]
    if ((sum(h[0:9:2]) * 7 - sum(h[1:8:2])) % 10) != h[9]:
        return False
    return sum(h[:10]) % 10 == h[10]


def luhn_gecerli_mi(sayi):
    """Kart numarası Luhn sağlaması (yalnızca rakamlar dikkate alınır)."""
    s = re.sub(r"\D", "", str(sayi))
    if len(s) < 13 or len(set(s)) == 1:  # 0000... gibi tek rakamlı diziler kart sayılmaz
        return False
    toplam = 0
    for i, c in enumerate(reversed(s)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        toplam += d
    return toplam % 10 == 0


# Tarama sırası: (kategori ya da None = yalnızca engelle, kalıp, doğrulayıcı). Eşleşen aralık sonraki kalıplara kapanır.
_SIRA = (
    [("api_anahtari", k, None) for k in _API_KALIPLARI]
    + [("parola", k, None) for k in _BAGLANTI_KALIPLARI]
    + [("parola", _EPOSTA_PAROLA, None), ("parola", _PAROLA, None),
       ("finansal", _IBAN, None), ("finansal", _KART, luhn_gecerli_mi),
       ("kimlik", _ONBIR_HANE, tc_kimlik_gecerli_mi),
       ("kisisel", _TELEFON, None), ("kisisel", _EPOSTA, None),
       (None, _URL, None),
       ("olasi_anahtar", _ENTROPI_ADAYI, _yuksek_entropili_mi)]
)


def _eslesmeler(metin):
    """[(kategori, eşleşen metin, (maske başı, maske sonu), (eşleşme başı, eşleşme sonu))]: her yer en çok bir kez sayılır."""
    kalan = str(metin or "")
    bulunan = []
    for kategori, kalip, dogrula in _SIRA:
        parcalar, son = [], 0
        for m in kalip.finditer(kalan):
            if _ENGEL in m.group(0) or (dogrula and not dogrula(m.group(0))):
                continue
            if kategori:
                aralik = m.span("deger") if "deger" in kalip.groupindex and m.group("deger") else m.span()
                bulunan.append((kategori, m.group(0), aralik, m.span()))
            parcalar.append(kalan[son:m.start()])
            parcalar.append(_ENGEL * (m.end() - m.start()))
            son = m.end()
        if parcalar:
            parcalar.append(kalan[son:])
            kalan = "".join(parcalar)
    return bulunan


def _parcali_eslesmeler(metin):
    """Metni GIRDI_SINIRI'lık, ORTUSME örtüşmeli parçalara bölüp her parçayı tarar; konumlar mutlak indekstir.

    Aynı kategorideki çakışan eşleşmeler (örtüşme bölgesi) tek sayılır. Süre metin uzunluğuyla doğrusal artar.
    Döner: [(kategori, eşleşen metin, (maske başı, maske sonu))], konuma göre sıralı.
    """
    if len(metin) <= GIRDI_SINIRI:
        return [(k, e, a) for k, e, a, _ in _eslesmeler(metin)]
    adim = GIRDI_SINIRI - ORTUSME
    tum = []
    for bas in range(0, len(metin), adim):
        parca = metin[bas:bas + GIRDI_SINIRI]
        for k, e, (a0, a1), (t0, t1) in _eslesmeler(parca):
            tum.append((k, e, (a0 + bas, a1 + bas), (t0 + bas, t1 + bas)))
        if bas + GIRDI_SINIRI >= len(metin):
            break
    tum.sort(key=lambda x: (x[3][0], -x[3][1]))
    sonuc, son_bitis = [], {}
    for k, e, a, t in tum:
        # aynı kategoride önceki bir eşleşmeyle çakışıyorsa (örtüşmede iki kez bulunmuş ya da sınırda kesilmiş) say-ma
        if t[0] < son_bitis.get(k, -1):
            son_bitis[k] = max(son_bitis[k], t[1])
            if sonuc and sonuc[-1][0] == k and a[1] > sonuc[-1][2][1]:
                sonuc[-1] = (k, sonuc[-1][1], (sonuc[-1][2][0], a[1]))  # kesik eşleşmenin maskesi tam hâline uzar
            continue
        son_bitis[k] = t[1]
        sonuc.append((k, e, a))
    return sonuc


def tara(metin):
    """Metni tarar. Döner: {"kategori", "eslesme_sayisi", "ornek", "kategoriler", "onem", "kirpildi"}.

    kategori: KATEGORILER'den biri ya da "yok"; eslesme_sayisi seçilen kategorideki eşleşmelerin adedi; ornek ilk
    eşleşmenin maskeli hâli (hiç yoksa ""); kategoriler bulunan tüm kategoriler; onem "yuksek" | "dusuk" | None;
    kirpildi geriye uyumluluk için hep False: metnin tamamı GIRDI_SINIRI'lık örtüşmeli parçalarla taranır.
    """
    bulunanlar = {k: [] for k in KATEGORILER}
    for kategori, parca, _ in _parcali_eslesmeler(str(metin or "")):
        bulunanlar[kategori].append(parca)
    bulunan_kategoriler = [k for k in KATEGORILER if bulunanlar[k]]
    if not bulunan_kategoriler:
        return {"kategori": "yok", "eslesme_sayisi": 0, "ornek": "", "kategoriler": [], "onem": None,
                "kirpildi": False}
    secilen = bulunan_kategoriler[0]
    return {"kategori": secilen, "eslesme_sayisi": len(bulunanlar[secilen]),
            "ornek": ornek_maskele(bulunanlar[secilen][0]), "kategoriler": bulunan_kategoriler,
            "onem": "yuksek" if secilen in YUKSEK else "dusuk", "kirpildi": False}


def uzun_mu(metin):
    """Metin tek tarama parçasından (GIRDI_SINIRI) uzun mu? Sunucu bu durumda yalnızca onaylı gönderime izin verir."""
    return len(str(metin or "")) > GIRDI_SINIRI


def uzun_onay_bilgisi(metin):
    """Çok uzun metin için onay isteği alanları: yüksek önemli bulgu varsa onun kategorisi, yoksa "uzun_metin"."""
    sonuc = tara(metin)
    if onay_gerekli_mi(sonuc):
        return {"kategori": sonuc["kategori"], "aciklama": uyari_metni(sonuc),
                "eslesme_sayisi": sonuc["eslesme_sayisi"]}
    return {"kategori": "uzun_metin", "aciklama": UZUN_ACIKLAMA, "eslesme_sayisi": 0}


def onay_gerekli_mi(sonuc):
    """Gönderimden önce onay istenecek (yüksek önemli) bir bulgu var mı?"""
    return sonuc.get("kategori") in YUKSEK


def hassas_var_mi(metin):
    """Herhangi bir bulgu (düşük önemliler dahil) var mı? Uzak sınıflandırıcıya (Jev) gönderim kararı için."""
    sonuc = tara(metin)
    # tarama tam yapılamadıysa (kırpılmış/atlanmış parça) güvenli taraf: hassas var say
    return sonuc["kategori"] != "yok" or bool(sonuc.get("kirpildi"))


def maskele(metin):
    """Bulunan anahtar/parola/kimlik/IBAN/kart ve olası anahtar değerlerini `[GİZLİ:<kategori>]` ile değiştirir.

    Parola, bağlantı dizesi ve Bearer gibi kalıplarda yalnızca değer maskelenir ("parola: [GİZLİ:parola]").
    E-posta ve telefon (kişisel, düşük önem) maskelenmez.
    """
    metin = str(metin or "")
    araliklar = sorted((a, k) for k, _, a in _parcali_eslesmeler(metin) if k in MASKELENEN)
    parcalar, son = [], 0
    for (bas, bit), kategori in araliklar:
        if bas < son:   # önceki maskeyle çakışıyorsa (parça sınırında kesik eşleşme) maske gerekirse uzar
            if bit > son:
                parcalar.pop()
                parcalar.append(f"[GİZLİ:{kategori_onceki}]")
                son = bit
            continue
        parcalar.append(metin[son:bas])
        parcalar.append(f"[GİZLİ:{kategori}]")
        kategori_onceki = kategori
        son = bit
    parcalar.append(metin[son:])
    return "".join(parcalar)


def uyari_metni(sonuc):
    """Arayüzdeki şerit için Türkçe açıklama (ör. "bir API anahtarı"); hassas bilgi yoksa None."""
    return ACIKLAMALAR.get(sonuc.get("kategori"))
