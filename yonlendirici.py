"""Ajan seçimi / yönlendirici (kural tabanlı, yalnızca standart kütüphane, ağa dokunmaz).

Yazılan mesajı sınıflandırır (tür ve zorluk) ve `yonlendirme.json` içindeki tercih sırasına göre
hangi siteye (ve hangi modele) gitmesinin uygun olacağını önerir. Model adı burada UYDURULMAZ:
dosyada yalnızca bir ad parçası (`model_icerir`, ör. "flash", "sonnet") yazılıdır; gerçek model adı,
sitenin canlı model menüsünden büyük/küçük harf duyarsız "içerir" eşleşmesiyle bulunur
(masaustu_sunucu.py → /api/oneri).

yonlendirme.json biçimi:
    {
      "varsayilan": {"basit": [TERCIH, ...], "orta": [...], "zor": [...]},
      "turler": {"kod": {"basit": [...], "orta": [...], "zor": [...]},
                 "ceviri": {"hepsi": [...]}, ...}
    }
TERCIH = {"site": "gemini" | "chatgpt" | "claude", "model_icerir": "flash"}. Bir (tür, zorluk) için aranış sırası:
turler[tür][zorluk] → turler[tür]["hepsi"] → varsayilan[zorluk]. Dosya yoksa ya da bozuksa yerleşik varsayılan
kullanılır ve sebep döner (uygulama açılışta kırılmaz).
"""
import json
import os
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent
YONLENDIRME_DOSYASI = Path(os.environ.get("YZ_YONLENDIRME") or KOK / "yonlendirme.json")

TURLER = ("arastirma", "kod", "yazi", "ceviri", "ozet", "sohbet", "matematik")
ZORLUKLAR = ("basit", "orta", "zor")
SITELER = ("chatgpt", "gemini", "claude")

TUR_ADLARI = {"arastirma": "araştırma", "kod": "kod", "yazi": "yazı", "ceviri": "çeviri", "ozet": "özet",
              "sohbet": "sohbet", "matematik": "matematik"}
ZORLUK_ADLARI = {"basit": "basit", "orta": "orta", "zor": "zor"}
SITE_ADLARI = {"chatgpt": "ChatGPT", "gemini": "Gemini", "claude": "Claude"}

# Uzunluk eşikleri (karakter): bunun altı basit, bunun altı orta, üstü zor.
BASIT_SINIRI = 200
ORTA_SINIRI = 1200
INCELEME_SINIRI = 20000  # karakter: desen araması metnin en çok bu kadar başına bakar

# Dosya yoksa/bozuksa kullanılan yerleşik varsayılan (yonlendirme.json'daki "varsayilan" bölümüyle aynı).
YERLESIK = {
    "varsayilan": {
        "basit": [{"site": "gemini", "model_icerir": "flash"}, {"site": "chatgpt", "model_icerir": "mini"},
                  {"site": "claude", "model_icerir": "haiku"}],
        "orta": [{"site": "claude", "model_icerir": "sonnet"}, {"site": "chatgpt", "model_icerir": "gpt"},
                 {"site": "gemini", "model_icerir": "pro"}],
        "zor": [{"site": "claude", "model_icerir": "opus"}, {"site": "chatgpt", "model_icerir": "pro"},
                {"site": "gemini", "model_icerir": "pro"}],
    },
    "turler": {},
}


# ---------------------------------------------------------------- sınıflandırma

_TURK_HARFLERI = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u"})


def normallestir(metin):
    """Küçük harfe çevirir ve Türkçe harfleri ASCII'ye indirir ("Özetle" → "ozetle"); desenler bu biçimde yazılır."""
    s = str(metin or "").replace("İ", "i").replace("I", "ı").lower()
    return s.translate(_TURK_HARFLERI)


_KOD = re.compile(r"```|\b(?:fonksiyon|hata|python|javascript|sql)")
_CEVIRI = re.compile(r"cevir|translat|ingilizce|turkceye")
_OZET = re.compile(r"ozetle|kisaca")
_ARASTIRMA = re.compile(r"arastir|karsilastir|kaynak|neden")
_YAZI = re.compile(r"\byaz(?!ilim)|\b(?:taslak|mail|makale)")
_MATEMATIK = re.compile(r"\d\s*(?:[+*/^×÷=]|\s-\s)\s*\d|\b(?:denklem|integral|turev|hesapla)")
_ZORLASTIRICI = re.compile(r"\b(?:ayrintili|kapsamli|analiz|mimari|strateji|plan)")
_ONCE_SONRA = re.compile(r"\bonce\b.*\bsonra\b", re.DOTALL)
_MADDE = re.compile(r"^[ \t]*(?:[-*•]|\d+[.)])[ \t]+\S", re.MULTILINE)


def tur_bul(normal):
    """Normalleştirilmiş metinden tür: kod → çeviri → özet → araştırma → yazı → matematik → sohbet (ilk eşleşen)."""
    for tur, kalip in (("kod", _KOD), ("ceviri", _CEVIRI), ("ozet", _OZET), ("arastirma", _ARASTIRMA),
                       ("yazi", _YAZI), ("matematik", _MATEMATIK)):
        if kalip.search(normal):
            return tur
    return "sohbet"


def zorluk_bul(metin, normal, uzunluk=None):
    """Zorluk: uzunluğa göre basit/orta/zor; zorlaştırıcı sözcük +1, çok adımlı istek +1 kademe (en çok zor)."""
    if uzunluk is None:
        uzunluk = len(str(metin or "").strip())
    kademe = 0 if uzunluk < BASIT_SINIRI else 1 if uzunluk < ORTA_SINIRI else 2
    if _ZORLASTIRICI.search(normal):
        kademe += 1
    if _ONCE_SONRA.search(normal) or len(_MADDE.findall(str(metin or ""))) >= 3:
        kademe += 1
    return ZORLUKLAR[min(kademe, 2)]


def siniflandir(metin):
    """{"tur", "zorluk"}: kural tabanlı sınıflandırma (hiçbir şey kaydedilmez)."""
    metin = str(metin or "")
    kisa = metin[:INCELEME_SINIRI]  # çok uzun metinde desen aramasını sınırla; uzunluk yine de tam metinden ölçülür
    normal = normallestir(kisa)
    return {"tur": tur_bul(normal), "zorluk": zorluk_bul(kisa, normal, len(metin.strip()))}


# ---------------------------------------------------------------- kurallar (yonlendirme.json)

def _tercih_gecerli_mi(t):
    return (isinstance(t, dict) and t.get("site") in SITELER
            and isinstance(t.get("model_icerir"), str) and 0 < len(t["model_icerir"].strip()) <= 60)


def _liste_temizle(liste):
    """Geçerli tercihleri ({"site","model_icerir"}) sırayı koruyarak döndürür; liste değilse None."""
    if not isinstance(liste, list):
        return None
    return [{"site": t["site"], "model_icerir": t["model_icerir"].strip()} for t in liste if _tercih_gecerli_mi(t)]


def kurallari_dogrula(ham):
    """Ham JSON nesnesini temizler. Döner: (kurallar, uyarilar). Geçersiz bölümler yerleşik varsayılana düşer."""
    uyarilar = []
    if not isinstance(ham, dict):
        return json.loads(json.dumps(YERLESIK)), ["Kural dosyasının kökü bir nesne olmalı; yerleşik varsayılan kullanıldı."]
    varsayilan = {}
    ham_varsayilan = ham.get("varsayilan") if isinstance(ham.get("varsayilan"), dict) else {}
    for z in ZORLUKLAR:
        liste = _liste_temizle(ham_varsayilan.get(z))
        if not liste:
            uyarilar.append(f"varsayilan/{z} geçersiz ya da boş; yerleşik değer kullanıldı.")
            liste = json.loads(json.dumps(YERLESIK["varsayilan"][z]))
        varsayilan[z] = liste
    turler = {}
    ham_turler = ham.get("turler") if isinstance(ham.get("turler"), dict) else {}
    for tur, icerik in ham_turler.items():
        if tur not in TURLER or not isinstance(icerik, dict):
            uyarilar.append(f"turler/{tur} tanınmıyor; yok sayıldı.")
            continue
        temiz = {}
        for z, liste in icerik.items():
            if z not in ZORLUKLAR + ("hepsi",):
                uyarilar.append(f"turler/{tur}/{z} tanınmıyor; yok sayıldı.")
                continue
            t = _liste_temizle(liste)
            if not t:
                uyarilar.append(f"turler/{tur}/{z} geçersiz ya da boş; yok sayıldı.")
                continue
            temiz[z] = t
        if temiz:
            turler[tur] = temiz
    return {"varsayilan": varsayilan, "turler": turler}, uyarilar


def kurallari_yukle(dosya=None):
    """yonlendirme.json'u okur. Döner: (kurallar, uyarilar); dosya yoksa/bozuksa yerleşik varsayılan + sebep."""
    yol = Path(dosya) if dosya else YONLENDIRME_DOSYASI
    try:
        ham = json.loads(yol.read_text("utf-8"))
    except FileNotFoundError:
        return json.loads(json.dumps(YERLESIK)), [f"{yol.name} bulunamadı; yerleşik varsayılan kullanıldı."]
    except (OSError, ValueError) as h:
        return json.loads(json.dumps(YERLESIK)), [f"{yol.name} okunamadı ({h}); yerleşik varsayılan kullanıldı."]
    return kurallari_dogrula(ham)


def tercihler(kurallar, tur, zorluk):
    """(tür, zorluk) için tercih sırası: turler[tür][zorluk] → turler[tür]["hepsi"] → varsayilan[zorluk]."""
    ozel = kurallar.get("turler", {}).get(tur, {})
    return ozel.get(zorluk) or ozel.get("hepsi") or kurallar["varsayilan"][zorluk]


def tablo(kurallar):
    """Arayüzdeki salt okunur görünüm için: her tür × zorluk için etkin tercih sırası."""
    satirlar = []
    for tur in TURLER:
        for z in ZORLUKLAR:
            satirlar.append({"tur": tur, "tur_ad": TUR_ADLARI[tur], "zorluk": z, "zorluk_ad": ZORLUK_ADLARI[z],
                             "tercihler": [{"site": t["site"], "site_ad": SITE_ADLARI[t["site"]],
                                            "model_icerir": t["model_icerir"]}
                                           for t in tercihler(kurallar, tur, z)]})
    return satirlar


# ---------------------------------------------------------------- öneri ve model eşleştirme

def model_esles(modeller, model_icerir):
    """Canlı menüdeki ilk eşleşen model adı (büyük/küçük harf duyarsız "içerir"), yoksa None.

    modeller: [{"id", "ad", "secili"}] ya da ad listesi. Birden çok eşleşmede menü sırasındaki ilki alınır.
    """
    aranan = str(model_icerir or "").strip().casefold()
    if not aranan:
        return None
    for m in modeller or []:
        ad = m.get("ad") if isinstance(m, dict) else m
        if isinstance(ad, str) and aranan in ad.casefold():
            return ad
    return None


def oner(metin, kurallar=None, sinif=None, kaynak="kural"):
    """{"tur","zorluk","tur_ad","zorluk_ad","oneriler":[{"site","site_ad","model_icerir","sebep"}],"kaynak"}.

    sinif: dışarıda (ör. Jev ile) bulunmuş {"tur", "zorluk"}; verilmezse ya da geçersizse kural tabanlı sınıflandırma
    kullanılır ve kaynak "kural" olur. "model" alanını çağıran doldurur (canlı menüden); burada model adı uydurulmaz.
    """
    if kurallar is None:
        kurallar, _ = kurallari_yukle()
    if isinstance(sinif, dict) and sinif.get("tur") in TURLER and sinif.get("zorluk") in ZORLUKLAR:
        s = {"tur": sinif["tur"], "zorluk": sinif["zorluk"]}
    else:
        s, kaynak = siniflandir(metin), "kural"
    oneriler = []
    for sira, t in enumerate(tercihler(kurallar, s["tur"], s["zorluk"]), 1):
        oneriler.append({
            "site": t["site"], "site_ad": SITE_ADLARI[t["site"]], "model_icerir": t["model_icerir"],
            "sebep": f"{ZORLUK_ADLARI[s['zorluk']].capitalize()} {TUR_ADLARI[s['tur']]} isteği için {sira}. tercih",
        })
    return {"tur": s["tur"], "zorluk": s["zorluk"], "tur_ad": TUR_ADLARI[s["tur"]],
            "zorluk_ad": ZORLUK_ADLARI[s["zorluk"]], "oneriler": oneriler, "kaynak": kaynak}
