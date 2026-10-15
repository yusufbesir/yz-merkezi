"""Motor yönlendiricisi (kural tabanlı, yalnızca standart kütüphane, ağa dokunmaz).

Yazılan mesajı sınıflandırır (tür ve zorluk) ve `yonlendirme.json` içindeki tercih sırasına göre hangi motorun
(claude / codex / gemini) ve hangi model sınıfının (hizli / dengeli / guclu) uygun olacağını önerir. Model adı burada
UYDURULMAZ: dosyada yalnızca sınıf yazılıdır; gerçek model, motorun `modeller()` listesinden sınıfa göre seçilir
(`model_sec`; masaustu_sunucu.py bunu çağırır).

yonlendirme.json biçimi:
    {
      "varsayilan": {"basit": [TERCIH, ...], "orta": [...], "zor": [...]},
      "turler": {"kod": {"basit": [...], "orta": [...], "zor": [...]},
                 "ceviri": {"hepsi": [...]}, ...}
    }
TERCIH = {"motor": "claude" | "codex" | "gemini", "sinif": "hizli" | "dengeli" | "guclu"}. Bir (tür, zorluk) için
aranış sırası: turler[tür][zorluk] → turler[tür]["hepsi"] → varsayilan[zorluk]. Dosya yoksa ya da bozuksa yerleşik
varsayılan kullanılır ve sebep döner (uygulama açılışta kırılmaz).

Konum: kullanıcının düzenlediği kopya uygulama veri klasöründedir (`%LOCALAPPDATA%\\YZMerkezi\\yonlendirme.json`,
`YZ_YONLENDIRME` ile değişir); böylece sürüm klasörü güncellemede değişip eski sürüm temizlense de kurallar kalır.
Kopya yoksa ilk okumada paketteki `yonlendirme.json` (şablon) oraya kopyalanır; var olan kopyaya hiç dokunulmaz.
"""
import json
import os
import re
from pathlib import Path

import guvenlik

KOK = Path(__file__).resolve().parent
SABLON_DOSYASI = KOK / "yonlendirme.json"  # pakette gelen başlangıç kuralları (güncellemeyle değişebilir)


def varsayilan_yonlendirme_dosyasi():
    """Kullanıcı kopyasının yolu: YZ_YONLENDIRME ya da veri klasöründeki yonlendirme.json."""
    return guvenlik.veri_yolu("YZ_YONLENDIRME", "yonlendirme.json")


YONLENDIRME_DOSYASI = varsayilan_yonlendirme_dosyasi()

TURLER = ("arastirma", "kod", "yazi", "ceviri", "ozet", "sohbet", "matematik")
ZORLUKLAR = ("basit", "orta", "zor")
MOTORLAR = ("claude", "codex", "gemini")
SINIFLAR = ("hizli", "dengeli", "guclu")

TUR_ADLARI = {"arastirma": "araştırma", "kod": "kod", "yazi": "yazı", "ceviri": "çeviri", "ozet": "özet",
              "sohbet": "sohbet", "matematik": "matematik"}
ZORLUK_ADLARI = {"basit": "basit", "orta": "orta", "zor": "zor"}
MOTOR_ADLARI = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini"}
SINIF_ADLARI = {"hizli": "hızlı", "dengeli": "dengeli", "guclu": "güçlü"}

# Uzunluk eşikleri (karakter): bunun altı basit, bunun altı orta, üstü zor.
BASIT_SINIRI = 200
ORTA_SINIRI = 1200
INCELEME_SINIRI = 20000  # karakter: desen araması metnin en çok bu kadar başına bakar


def _t(motor, sinif):
    return {"motor": motor, "sinif": sinif}


# Dosya yoksa/bozuksa kullanılan yerleşik varsayılan (yonlendirme.json'daki "varsayilan" bölümüyle aynı).
YERLESIK = {
    "varsayilan": {
        "basit": [_t("gemini", "hizli"), _t("codex", "hizli"), _t("claude", "hizli")],
        "orta": [_t("claude", "dengeli"), _t("codex", "dengeli"), _t("gemini", "dengeli")],
        "zor": [_t("claude", "guclu"), _t("codex", "guclu"), _t("gemini", "guclu")],
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
    return isinstance(t, dict) and t.get("motor") in MOTORLAR and t.get("sinif") in SINIFLAR


def _liste_temizle(liste):
    """Geçerli tercihleri ({"motor","sinif"}) sırayı koruyarak döndürür; liste değilse None."""
    if not isinstance(liste, list):
        return None
    return [{"motor": t["motor"], "sinif": t["sinif"]} for t in liste if _tercih_gecerli_mi(t)]


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


def kullanici_kopyasini_hazirla(yol=None, sablon=None):
    """Kullanıcı kopyası yoksa şablonu kopyalar (var olan kopyaya asla dokunmaz). Döner: kopyanın yolu.

    Kopyalanamazsa (izin, disk ...) sessizce geçer: kurallari_yukle yerleşik varsayılana düşer ve sebebi bildirir.
    """
    yol = Path(yol or YONLENDIRME_DOSYASI)
    sablon = Path(sablon or SABLON_DOSYASI)
    if os.path.lexists(yol) or not sablon.is_file():
        return yol
    gecici = yol.with_name(yol.name + ".tmp")
    try:
        yol.parent.mkdir(parents=True, exist_ok=True)
        gecici.write_bytes(sablon.read_bytes())
        if os.path.lexists(yol):  # bu arada başka bir süreç oluşturduysa onunkini koru
            gecici.unlink()
        else:
            os.replace(gecici, yol)
    except OSError as h:
        guvenlik.hata_yaz(f"yonlendirme.json kullanıcı kopyası oluşturulamadı: {h}")
    return yol


def kurallari_yukle(dosya=None):
    """yonlendirme.json'u okur. Döner: (kurallar, uyarilar); dosya yoksa/bozuksa yerleşik varsayılan + sebep.

    Dosya verilmezse kullanıcı kopyası (veri klasörü) okunur; yoksa önce paketteki şablon oraya kopyalanır.
    """
    yol = Path(dosya) if dosya else YONLENDIRME_DOSYASI
    if not dosya and yol == varsayilan_yonlendirme_dosyasi():
        kullanici_kopyasini_hazirla(yol)
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


def _tercih_gorunumu(t):
    return {"motor": t["motor"], "motor_ad": MOTOR_ADLARI[t["motor"]],
            "sinif": t["sinif"], "sinif_ad": SINIF_ADLARI[t["sinif"]]}


def tablo(kurallar):
    """Arayüzdeki salt okunur görünüm için: her tür × zorluk için etkin tercih sırası."""
    satirlar = []
    for tur in TURLER:
        for z in ZORLUKLAR:
            satirlar.append({"tur": tur, "tur_ad": TUR_ADLARI[tur], "zorluk": z, "zorluk_ad": ZORLUK_ADLARI[z],
                             "tercihler": [_tercih_gorunumu(t) for t in tercihler(kurallar, tur, z)]})
    return satirlar


# ---------------------------------------------------------------- öneri ve model seçimi

# Sınıf bulunamazsa en yakın sınıfa bakılır (sıra: önce istenen, sonra komşular).
SINIF_YEDEKLERI = {"hizli": ("hizli", "dengeli", "guclu"), "dengeli": ("dengeli", "guclu", "hizli"),
                   "guclu": ("guclu", "dengeli", "hizli")}


def model_sec(modeller, sinif, tercih_id=None):
    """Motorun `modeller()` listesinden ({"id","ad","sinif"}) sınıfa uygun modeli seçer; yoksa None.

    tercih_id (Ayarlar → Motorlar'da seçilen model) listede varsa o alınır; yoksa sınıfın ilk modeli, sınıf boşsa en
    yakın sınıfınki, hiçbiri yoksa listenin ilk modeli. Liste boşsa None (motor kendi varsayılanını kullanır).
    """
    gecerli = [m for m in modeller or [] if isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"]]
    if tercih_id:
        for m in gecerli:
            if m["id"] == tercih_id:
                return m
    for s in SINIF_YEDEKLERI.get(sinif, SINIF_YEDEKLERI["dengeli"]):
        for m in gecerli:
            if m.get("sinif") == s:
                return m
    return gecerli[0] if gecerli else None


def model_esles(modeller, model_icerir):
    """Menüdeki ilk eşleşen model adı (büyük/küçük harf duyarsız "içerir"), yoksa None (site menüsü yolu için)."""
    aranan = str(model_icerir or "").strip().casefold()
    if not aranan:
        return None
    for m in modeller or []:
        ad = m.get("ad") if isinstance(m, dict) else m
        if isinstance(ad, str) and aranan in ad.casefold():
            return ad
    return None


def oner(metin, kurallar=None, sinif=None, kaynak="kural"):
    """{"tur","zorluk","tur_ad","zorluk_ad","oneriler":[{"motor","motor_ad","sinif","sinif_ad","sebep"}],"kaynak"}.

    sinif: dışarıda (ör. Jev ile) bulunmuş {"tur", "zorluk"}; verilmezse ya da geçersizse kural tabanlı sınıflandırma
    kullanılır ve kaynak "kural" olur. Model adı burada uydurulmaz; çağıran motorun listesinden `model_sec` ile seçer.
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
            **_tercih_gorunumu(t),
            "sebep": f"{ZORLUK_ADLARI[s['zorluk']].capitalize()} {TUR_ADLARI[s['tur']]} isteği için {sira}. tercih",
        })
    return {"tur": s["tur"], "zorluk": s["zorluk"], "tur_ad": TUR_ADLARI[s["tur"]],
            "zorluk_ad": ZORLUK_ADLARI[s["zorluk"]], "oneriler": oneriler, "kaynak": kaynak}
