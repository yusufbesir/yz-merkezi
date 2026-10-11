"""Gönderme öncesi hassas bilgi taraması (kural tabanlı, yalnızca standart kütüphane).

Mesaj metninde API anahtarı, T.C. kimlik numarası, IBAN, kart numarası ve parola kalıpları aranır.
Hiçbir şey ağa gitmez, hiçbir şey kaydedilmez; sonuçta yalnızca kategori, eşleşme sayısı ve maskeli
bir örnek (ilk 4 karakter + ***) döner.

Kategoriler (birden çok varsa bu öncelikle tek kategori seçilir): api_anahtari > parola > kimlik > finansal.
"""
import re

KATEGORILER = ("api_anahtari", "parola", "kimlik", "finansal")

ACIKLAMALAR = {
    "api_anahtari": "bir API anahtarı",
    "parola": "bir parola",
    "kimlik": "bir T.C. kimlik numarası",
    "finansal": "bir IBAN ya da kart numarası",
}

_SOL = r"(?<![A-Za-z0-9_])"  # kalıp başka bir sözcüğün ortasında başlamasın

# ---- API anahtarları ve özel anahtar başlığı
_API_KALIPLARI = [
    re.compile(_SOL + r"sk-[A-Za-z0-9]{16,}"),
    re.compile(_SOL + r"sk-(?:ant|proj|svcacct)-[A-Za-z0-9_-]{10,}"),
    re.compile(_SOL + r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(_SOL + r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(_SOL + r"xoxb-[0-9A-Za-z-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),
]

# ---- IBAN (TR + 2 kontrol hanesi + 22 hane, 4'lü gruplar boşluklu ya da bitişik)
_IBAN = re.compile(_SOL + r"TR\d{2}[ ]?(?:\d{4}[ ]?){5}\d{2}(?!\d)", re.IGNORECASE)

# ---- 11 haneli kimlik ve 16 haneli kart adayları (sayının ortasından başlamasın)
_ONBIR_HANE = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")
_KART = re.compile(r"(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)")

# ---- parola: "parola|şifre|password|pin" + [:=] + değer (aynı satırda)
_PAROLA_ANAHTARI = r"(?:(?:parola|[sşSŞ][iİıI]fre|password|passwd|pwd)[a-zA-ZçğıöşüÇĞİÖŞÜ]{0,6}|pin)"
_PAROLA = re.compile(
    _SOL + _PAROLA_ANAHTARI + r"[ \t]*[:=][ \t]*[\"']?[^\s\"',;]{3,}",
    re.IGNORECASE,
)

# ---- e-posta + parola çifti: "kisi@ornek.com:Parola123!" ya da "kisi@ornek.com / Parola123!"
_EPOSTA_PAROLA = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+[ \t]*[:|/;,][ \t]*"
    r"(?=\S*[A-Za-z])(?=\S*[\d!@#$%^&*?])(?![\w.+-]+@)(?!https?:)[^\s\"',;]{6,}"
)

_ENGEL = "\x00"


def maskele(parca):
    """İlk 4 karakter + ***: kimlik ve anahtarın geri kalanı hiçbir zaman gösterilmez."""
    return str(parca)[:4] + "***"


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


def _tara_kalip(kalip, metin, dogrula=None):
    """Kalıbın eşleşmelerini döndürür ve eşleşen aralıkları metinde engelleyerek (aynı yer iki kez sayılmasın) metni verir."""
    bulunan = []
    parcalar = []
    son = 0
    for m in kalip.finditer(metin):
        if dogrula and not dogrula(m.group(0)):
            continue
        bulunan.append(m.group(0))
        parcalar.append(metin[son:m.start()])
        parcalar.append(_ENGEL * (m.end() - m.start()))
        son = m.end()
    parcalar.append(metin[son:])
    return bulunan, "".join(parcalar)


def tara(metin):
    """Metni tarar. Döner: {"kategori", "eslesme_sayisi", "ornek", "kategoriler"}.

    kategori: "api_anahtari" | "parola" | "kimlik" | "finansal" | "yok". eslesme_sayisi seçilen kategorideki
    eşleşmelerin adedi; ornek ilk eşleşmenin maskeli hâli (hiç yoksa ""); kategoriler bulunan tüm kategoriler.
    """
    kalan = str(metin or "")
    bulunanlar = {k: [] for k in KATEGORILER}

    for kalip in _API_KALIPLARI:
        b, kalan = _tara_kalip(kalip, kalan)
        bulunanlar["api_anahtari"] += b
    b, kalan = _tara_kalip(_EPOSTA_PAROLA, kalan)
    bulunanlar["parola"] += b
    b, kalan = _tara_kalip(_PAROLA, kalan)
    bulunanlar["parola"] += b
    b, kalan = _tara_kalip(_IBAN, kalan)
    bulunanlar["finansal"] += b
    b, kalan = _tara_kalip(_KART, kalan, luhn_gecerli_mi)
    bulunanlar["finansal"] += b
    b, kalan = _tara_kalip(_ONBIR_HANE, kalan, tc_kimlik_gecerli_mi)
    bulunanlar["kimlik"] += b

    bulunan_kategoriler = [k for k in KATEGORILER if bulunanlar[k]]
    if not bulunan_kategoriler:
        return {"kategori": "yok", "eslesme_sayisi": 0, "ornek": "", "kategoriler": []}
    secilen = bulunan_kategoriler[0]
    return {"kategori": secilen, "eslesme_sayisi": len(bulunanlar[secilen]),
            "ornek": maskele(bulunanlar[secilen][0]), "kategoriler": bulunan_kategoriler}


def uyari_metni(sonuc):
    """Arayüzdeki şerit için Türkçe açıklama (ör. "bir API anahtarı"); hassas bilgi yoksa None."""
    return ACIKLAMALAR.get(sonuc.get("kategori"))
