#!/usr/bin/env python3
"""Yapay Zeka Merkezi (masaüstü sürümü) arka ucu.

VARSAYILAN KİP: Tek Asistan. Arayüz tek bir yapay zeka gibi davranır; `POST /api/sor` mesajı hassas bilgi taramasından
ve Hafıza OS bağlamından geçirir, yönlendirici (yonlendirici.py + Jev) ile bir motor (claude / codex / gemini; `motorlar/`
paketi, yerel komut satırı araçları) seçer ve yanıtı NDJSON akışı olarak verir. Hiçbir dış pencereye mesaj gitmez.

Gelişmiş kip (Ayarlar → Gelişmiş; kod korunur): ChatGPT, Gemini ve Claude WEB siteleri / masaüstü programları.
Eski yol: ChatGPT, Gemini ve Claude WEB siteleri, kendi Edge profilimizde (tarayici.py) açılır ve
CDP ile (cdp.py) arka planda denetlenir; sohbet listesi, mesajlar ve yanıtlar siteler.py'deki JS
parçalarıyla okunur, yazı Input.insertText ile eklenir. Kullanıcı her sitede bir kez oturum açar.
Yedek yol: bilgisayarda kurulu masaüstü programlarına pano + tuş taklidiyle gönderme (pencereler.py).

Hedef kavramı: `veri["secili"]` iki tür anahtar taşır: "site:<id>" (web siteleri) ve masaüstü
program kimlikleri. İlk açılışta siteler seçili, programlar seçili değildir.
Arayüz, Claude masaüstü uygulamasının düzeninde hazırlanmış bir web sayfasıdır ve Edge'in
uygulama penceresinde açılır. API anahtarı gerekmez.
"""
import atexit
import concurrent.futures
import copy
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PureWindowsPath
from urllib.parse import parse_qs, urlparse

import cdp
import guvenlik
import hassas
import hafiza_kopru
import jev
import pencereler as pc
import siteler
import tarayici
import yonlendirici

KOK = Path(__file__).resolve().parent
ARAYUZ = KOK / "arayuz-masaustu"
UYGULAMA_DOSYASI = KOK / "uygulamalar.json"
AYAR_DOSYASI = guvenlik.veri_yolu("YZ_MASAUSTU_AYAR", "masaustu-ayarlar.json")  # varsayılan: %LOCALAPPDATA%\YZMerkezi
ESKI_AYAR_DOSYASI = KOK / "masaustu-ayarlar.json"  # eski sürümlerin yeri (ilk açılışta taşınır)
PORT = int(os.environ.get("YZ_MASAUSTU_PORT", "8766"))
PENCERE_BASLIGI = "Yapay Zeka Merkezi"
VARSAYILAN_KONUM = {"oran_x": 0.5, "alttan": 90}
OGRETME_SURESI = 4
SOHBET_ONBELLEK_SURESI = 15   # sn: site sohbet listesi bu süre içinde yeniden sorgulanmaz
SITE_ZAMAN_ASIMI = 8          # sn: bir sitenin tek sorgusu için üst sınır
SOHBET_YUKLEME_SURESI = 10    # sn: sohbet adresine gidince mesajların yüklenmesi için üst sınır
SAYFA_ACILMA_SURESI = 15      # sn: yeni açılan site penceresinin görünmesi için üst sınır
ADRES_DOGRULAMA_SURESI = 6    # sn: gezinmeden sonra adres çubuğunun hedefe varması için üst sınır
MODEL_ONBELLEK_SURESI = 60    # sn: bir sitenin model listesi bu süre içinde yeniden okunmaz
MODEL_HATA_ONBELLEK_SURESI = 10  # sn: liste alınamayan site (kapalı, giriş yok, destek yok) bu süre yeniden sorulmaz
MODEL_ZAMAN_ASIMI = 12        # sn: model menüsü JS'i için üst sınır
MODEL_KILIT_BEKLEME = 2       # sn: site meşgulse (gönderme/gezinme sürüyor) model listesi için en çok bu kadar beklenir
MODEL_DESTEGI_YOK = "model menüsü desteği henüz yok"
KUTU_DOGRULAMA_SINIRI = 90000  # karakter: bundan uzun metinde yazılan metin karşılaştırılmaz
YANIT_KAYIT_SINIRI = 100000   # yerel geçmişe kaydedilecek tek yanıtın en uzun boyu
VARSAYILAN_AYARLAR = {
    "tema": "sistem", "yazi_boyutu": "orta", "enter_bas": True, "kutuyu_temizle": True,
    "yerlesim": "sol", "ad": "Yusuf",
}
# /api/ayar şeması: metin ayarlarında izinli değerler (mantıksal olanlar bool, "ad" en çok 40 karakter str).
AYAR_SECENEKLERI = {"tema": {"acik", "koyu", "sistem"}, "yazi_boyutu": {"kucuk", "orta", "buyuk"},
                    "yerlesim": {"sol", "alt"}}
AYAR_MANTIKSAL = ("enter_bas", "kutuyu_temizle")
# Hafıza OS köprüsü (hafiza_kopru.py): hafızayı mesaja ekle / yanıtları hafızaya aday olarak yaz (ikisi de varsayılan açık).
VARSAYILAN_AYARLAR.update(hafiza_ekle=True, hafiza_aday=True)
AYAR_MANTIKSAL += ("hafiza_ekle", "hafiza_aday")
# Hassas bilgi uyarısı (hassas.py) ve ajan seçimi (yonlendirici.py): uyarı varsayılan açık, otomatik yönlendirme kapalı.
VARSAYILAN_AYARLAR.update(hassas_uyari=True, otomatik_yonlendirme=False)
AYAR_MANTIKSAL += ("hassas_uyari", "otomatik_yonlendirme")
# Jev (jev.py, TypeSafe karar modeli): açık/kapalı varsayılan AÇIK; yanıt puanlama varsayılan KAPALI (yanıtlar Jev'e gider).
# Jev varsayılan AÇIK: kullanıcı kararı 2026-10-11 (proje sohbeti); mesaj metni TypeSafe'in uzak Jev sunucusuna gider.
VARSAYILAN_AYARLAR.update(jev_acik=True, jev_yanit_puanla=False)
AYAR_MANTIKSAL += ("jev_acik", "jev_yanit_puanla")
JEV_HASSAS_ESIGI = 0.6        # Jev'in "yok" dışı seçiminin olasılığı en az bu kadarsa onay istenir
JEV_PUANLAMA_BUTCESI = 3800   # karakter: puanlamada soru + yanıtların toplamı (jev.METIN_EN_FAZLA'nın altında)
JEV_YANIT_EN_FAZLA = 1500     # karakter: puanlamada her yanıttan en çok bu kadar
JEV_SORU_EN_FAZLA = 600       # karakter: puanlamada sorudan en çok bu kadar
# Tek Asistan: son seçilen motor ("otomatik" ya da bir motor kimliği) ve motor/sınıf başına tercih edilen modeller.
VARSAYILAN_AYARLAR.update(varsayilan_motor="otomatik", motor_modelleri={})
AYAR_SECENEKLERI["varsayilan_motor"] = {"otomatik", *yonlendirici.MOTORLAR}
AD_EN_FAZLA = 40
# Web hesapları (CDP) varken bu tarayıcılar masaüstü programı olarak eklenemez.
TARAYICI_EXELERI = {"msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "opera.exe"}

# İstek belirteci: açılışta bir kez üretilir, yalnızca bellekte (ve kullanıcıya özel klasördeki belirtec dosyasında) durur.
BELIRTEC = guvenlik.yeni_belirtec()
AYAR_UYARISI = None  # ayar dosyası bozuk çıkıp yedeklenirse arayüze gösterilecek Türkçe uyarı

KILIT = threading.Lock()
KILITSIZ = {"/api/site-ac", "/api/site-sohbet-ac", "/api/pencere-ac", "/api/oneri", "/api/yonlendirme-ac",
            "/api/yanit-puanla", "/api/durdur"}  # yanıt puanlama Jev'i beklerken ayar kilidini tutmaz (kilidi kendisi kısa süre alır)
is_kilidi = threading.Lock()  # aynı anda tek gönderme/öğretme işlemi


class IsHatasi(Exception):
    pass


class SiteHatasi(Exception):
    """Bir siteye gönderme/okuma sırasında oluşan, kullanıcıya Türkçe gösterilecek sorun."""


# ---------------------------------------------------------------- ayarlar ve veri

def ayarlari_oku():
    """Ayar dosyasını okur. Bozuksa (JSON değilse) silinmez: `<ad>.bozuk-<zaman>.json` olarak saklanır."""
    global AYAR_UYARISI
    veri, uyari = guvenlik.json_oku(AYAR_DOSYASI)
    if uyari:
        AYAR_UYARISI = uyari
    for anahtar, tur in (("ayarlar", dict), ("konumlar", dict), ("secili", dict),
                         ("ek_uygulamalar", list), ("sohbetler", list)):
        if not isinstance(veri.get(anahtar), tur):
            veri[anahtar] = tur()
    for k, v in VARSAYILAN_AYARLAR.items():
        veri["ayarlar"].setdefault(k, copy.deepcopy(v))
    return veri


def ayarlari_yaz(veri):
    guvenlik.json_yaz(AYAR_DOSYASI, veri)


def uygulamalar(veri):
    return json.loads(UYGULAMA_DOSYASI.read_text("utf-8")) + veri["ek_uygulamalar"]


def uygulama_bul(veri, uid):
    return next((u for u in uygulamalar(veri) if u["id"] == uid), None)


def kendi_pencere():
    """Arayüzün açıldığı tarayıcı penceresi (başlığından tanınır)."""
    return pc.pencere_bul({"exe": "msedge.exe", "baslik_icerir": PENCERE_BASLIGI}, pc.pencereleri_listele()) \
        or next((p for p in pc.pencereleri_listele() if PENCERE_BASLIGI in p.baslik), None)


def site_secili(veri, site_id):
    """Web sitesi hedef olarak işaretli mi? (varsayılan: evet)"""
    return veri["secili"].get("site:" + site_id, True)


def program_secili(veri, uid):
    """Masaüstü programı hedef olarak işaretli mi? (varsayılan: hayır)"""
    return veri["secili"].get(uid, False)


# ---------------------------------------------------------------- site yardımcıları (CDP)

def _site_parcalari(site_id):
    """Sitenin sekmesini tanımak için adreste aranacak parçalar: önce alan adı, sonra giriş sayfaları."""
    kayit = siteler.site(site_id)
    return [kayit["pencere_parcasi"]] + list(kayit.get("giris_parcalari", []))


def site_sayfasi(site_id):
    """Sitenin açık sekmesine bağlı CDP oturumu (cdp.Oturum); sekme yoksa None. Çağıran kapatmalıdır."""
    for parca in _site_parcalari(site_id):
        b = tarayici.sayfa(parca)
        if b:
            return b
    return None


def site_hedefi(site_id):
    """Sitenin açık sekmesinin DevTools kaydı (id, url, ...); yoksa None."""
    for parca in _site_parcalari(site_id):
        h = tarayici.hedef(parca)
        if h:
            return h
    return None


def _js_hatasi(sonuc):
    """Site JS'i {"hata": ...} döndürdüyse hata metni, değilse None."""
    if isinstance(sonuc, dict) and sonuc.get("hata"):
        return str(sonuc["hata"])
    return None


def site_durumu(site_id):
    """{"acik", "giris", "sebep", "url"}: giris, pencere açıksa giris_var_mi ile ölçülür (belirsizse None)."""
    b = site_sayfasi(site_id)
    if not b:
        return {"acik": False, "giris": None, "sebep": "Pencere kapalı", "url": ""}
    js = siteler.site(site_id)["js"]
    try:
        sonuc = b.degerlendir(js["giris_var_mi"], zaman=SITE_ZAMAN_ASIMI)
        url = b.degerlendir("location.href", zaman=SITE_ZAMAN_ASIMI)
    except cdp.CdpHatasi as h:
        return {"acik": True, "giris": None, "sebep": str(h), "url": ""}
    finally:
        b.kapat()
    hata = _js_hatasi(sonuc)
    if hata:
        return {"acik": True, "giris": None, "sebep": hata, "url": url or ""}
    if not isinstance(sonuc, dict) or "giris" not in sonuc:
        return {"acik": True, "giris": None, "sebep": "Sayfadan beklenmeyen yanıt geldi", "url": url or ""}
    return {"acik": True, "giris": bool(sonuc["giris"]), "sebep": str(sonuc.get("sebep", "")), "url": url or ""}


def site_durumlari(veri):
    """Üç sitenin durumu (paralel ölçülür), arayüze gidecek biçimde."""
    kimlikler = list(siteler.SITELER)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(kimlikler)) as havuz:
        olculen = list(havuz.map(site_durumu, kimlikler))
    liste = []
    for sid, d in zip(kimlikler, olculen):
        k = siteler.site(sid)
        liste.append({"id": sid, "ad": k["ad"], "renk": k["renk"], "acik": d["acik"], "giris": d["giris"],
                      "sebep": d["sebep"], "secili": site_secili(veri, sid)})
    return liste


def durum(veri):
    acik = pc.pencereleri_listele()
    liste = []
    for u in uygulamalar(veri):
        p = pc.pencere_bul(u, acik)
        liste.append({
            "id": u["id"], "ad": u["ad"], "renk": u.get("renk", "#888"), "acik": bool(p),
            "ogretildi": u["id"] in veri["konumlar"], "secili": program_secili(veri, u["id"]),
            "ek": u in veri["ek_uygulamalar"], "exe": u["exe"],
        })
    return {"programlar": liste, "siteler": site_durumlari(veri), "ayarlar": veri["ayarlar"],
            "sohbetler": veri["sohbetler"], "uyari": AYAR_UYARISI}


def site_ac(site_id):
    """Site penceresini açar; zaten açıksa öne getirir. Türkçe sonuç metni döndürür."""
    try:
        kayit = siteler.site(site_id)
    except KeyError:
        raise IsHatasi("Site bulunamadı.") from None
    b = site_sayfasi(site_id)
    if b:
        try:
            b.one_getir()
        except cdp.CdpHatasi as h:
            raise IsHatasi(f"{kayit['ad']} penceresi öne getirilemedi: {h}") from h
        finally:
            b.kapat()
        return {"tamam": True, "zaten_acik": True, "mesaj": f"{kayit['ad']} penceresi öne getirildi."}
    uyari = tarayici.pencere_ac(kayit["adres"])
    if uyari:
        raise IsHatasi(uyari)
    return {"tamam": True, "zaten_acik": False,
            "mesaj": f"{kayit['ad']} açılıyor. Açılan pencerede bir kez giriş yap; oturum bu profilde kalır."}


# ---------------------------------------------------------------- site sohbetleri

# Aynı site penceresinde aynı anda iki gezinme/gönderme çakışmasın (ör. kullanıcı art arda iki sohbete tıklarsa).
_SITE_KILITLERI = {sid: threading.Lock() for sid in siteler.SITELER}
_SOHBET_ONBELLEGI = {}  # site kimliği -> {"zaman": monotonic, "sohbetler": [...], "hata": str | None}
_ONBELLEK_KILIDI = threading.Lock()


def _site_sohbetlerini_oku(site_id):
    """Tek site için sohbet listesi. Pencere kapalı ya da giriş yoksa boş liste (hata sayılmaz)."""
    b = site_sayfasi(site_id)
    if not b:
        return {"sohbetler": [], "hata": None}
    js = siteler.site(site_id)["js"]
    try:
        giris = b.degerlendir(js["giris_var_mi"], zaman=SITE_ZAMAN_ASIMI)
        hata = _js_hatasi(giris)
        if hata:
            return {"sohbetler": [], "hata": hata}
        if not (isinstance(giris, dict) and giris.get("giris")):
            return {"sohbetler": [], "hata": None}
        liste = b.degerlendir(js["sohbet_listesi"], zaman=SITE_ZAMAN_ASIMI)
    except cdp.CdpHatasi as h:
        return {"sohbetler": [], "hata": str(h)}
    finally:
        b.kapat()
    hata = _js_hatasi(liste)
    if hata:
        return {"sohbetler": [], "hata": hata}
    if not isinstance(liste, list):
        return {"sohbetler": [], "hata": "Sohbet listesi beklenmeyen biçimde geldi"}
    sonuc = []
    for k in liste:
        if isinstance(k, dict) and k.get("url"):
            sonuc.append({"id": siteler.sohbet_kimligi(site_id, k["url"]), "site": site_id,
                          "baslik": k.get("baslik") or "(başlıksız)", "url": k["url"]})
    return {"sohbetler": sonuc, "hata": None}


def site_sohbetleri(yenile=False):
    """Açık ve giriş yapılmış her sitenin sohbetlerini birleşik listede döndürür.

    Site başına 15 sn bellek önbelleği vardır (yenile=True ile atlanır). Süresi dolan siteler paralel
    sorgulanır, her biri en çok 8 sn bekler; hata veren site atlanır ve "hatalar" alanında bildirilir.
    """
    simdi = time.monotonic()
    eskiler = []
    with _ONBELLEK_KILIDI:
        for sid in siteler.SITELER:
            k = _SOHBET_ONBELLEGI.get(sid)
            if yenile or not k or simdi - k["zaman"] >= SOHBET_ONBELLEK_SURESI:
                eskiler.append(sid)
    if eskiler:
        havuz = concurrent.futures.ThreadPoolExecutor(max_workers=len(eskiler))
        isler = {sid: havuz.submit(_site_sohbetlerini_oku, sid) for sid in eskiler}
        bitis = time.monotonic() + SITE_ZAMAN_ASIMI
        for sid, is_ in isler.items():
            try:
                sonuc = is_.result(timeout=max(0.05, bitis - time.monotonic()))
            except concurrent.futures.TimeoutError:
                sonuc = {"sohbetler": [], "hata": "Zaman aşımı"}
            except Exception as h:  # noqa: BLE001
                sonuc = {"sohbetler": [], "hata": str(h)}
            with _ONBELLEK_KILIDI:
                onceki = _SOHBET_ONBELLEGI.get(sid, {}).get("sohbetler", [])
                # Hata varsa eski liste görünmeye devam etsin.
                _SOHBET_ONBELLEGI[sid] = {"zaman": time.monotonic(), "hata": sonuc["hata"],
                                          "sohbetler": onceki if sonuc["hata"] else sonuc["sohbetler"]}
        havuz.shutdown(wait=False)  # zaman aşımına uğrayan iş arka planda kendi bitişini beklesin
    birlesik, hatalar = [], []
    with _ONBELLEK_KILIDI:
        for sid in siteler.SITELER:
            k = _SOHBET_ONBELLEGI.get(sid)
            if not k:
                continue
            birlesik.extend(k["sohbetler"])
            if k["hata"]:
                hatalar.append({"site": sid, "ad": siteler.site(sid)["ad"], "sebep": k["hata"]})
    return {"sohbetler": birlesik, "hatalar": hatalar}


def _site_adresi_mi(site_id, url):
    """Adres bu sitenin alan adına ait mi? (başka siteye yönlendirmeyi engeller)"""
    u = urlparse(str(url or ""))
    if u.scheme not in ("http", "https"):
        return False
    return siteler.adres_eslesir_mi(str(url), siteler.site(site_id)["pencere_parcasi"])


def _ayni_adres(a, b):
    """İki adres (parça işareti ve sondaki / hariç) aynı mı?"""
    def kes(x):
        return str(x or "").split("#", 1)[0].rstrip("/")
    return kes(a) == kes(b)


def _yol_anahtari(url):
    """Adresin yalnızca alan adı + yolu (sorgu ve parça yok); yeni sohbet sayfası denetimi için."""
    u = urlparse(str(url or ""))
    return (u.netloc + u.path).rstrip("/")


def _mesajlari_oku(b, js):
    """mesajlar JS'ini çalıştırır; {"baslik", "mesajlar"} döndürür, hata varsa SiteHatasi."""
    try:
        m = b.degerlendir(js["mesajlar"], zaman=SITE_ZAMAN_ASIMI)
    except cdp.CdpHatasi as h:
        raise SiteHatasi(str(h)) from h
    hata = _js_hatasi(m)
    if hata:
        raise SiteHatasi(hata)
    if not isinstance(m, dict) or not isinstance(m.get("mesajlar"), list):
        raise SiteHatasi("Mesajlar sayfadan okunamadı")
    return m


def site_sohbet_ac(site_id, url):
    """Sitenin penceresini sohbet adresine götürür (gerekirse) ve mesajları okur."""
    try:
        kayit = siteler.site(site_id)
    except KeyError:
        raise IsHatasi("Site bulunamadı.") from None
    url = str(url or "").strip()
    if url and not _site_adresi_mi(site_id, url):
        raise IsHatasi(f"Bu adres {kayit['ad']} sitesine ait değil.")
    with _SITE_KILITLERI[site_id]:
        return _site_sohbet_ac(site_id, kayit, url)


def _site_sohbet_ac(site_id, kayit, url):
    b = site_sayfasi(site_id)
    if not b:
        raise IsHatasi(f"{kayit['ad']} penceresi açık değil. Önce kenar çubuğundan açın.")
    try:
        if url and not _ayni_adres(b.degerlendir("location.href", zaman=SITE_ZAMAN_ASIMI), url):
            b.git(url)
        bitis = time.monotonic() + SOHBET_YUKLEME_SURESI
        onceki, sonuc = None, None
        while True:
            try:
                hazir = b.degerlendir("document.readyState", zaman=SITE_ZAMAN_ASIMI) == "complete"
                sonuc = _mesajlari_oku(b, kayit["js"]) if hazir else None
            except (cdp.CdpHatasi, SiteHatasi):
                sonuc = None  # sayfa yönlenirken geçici hata; süre dolana dek yeniden dene
            adet = len(sonuc["mesajlar"]) if sonuc else 0
            if adet and adet == onceki:
                break  # mesaj sayısı iki yoklamada aynı: yükleme bitti
            onceki = adet
            if time.monotonic() >= bitis:
                break
            time.sleep(0.4)
        if sonuc is None:
            sonuc = _mesajlari_oku(b, kayit["js"])
        return {"baslik": sonuc.get("baslik", ""), "mesajlar": sonuc["mesajlar"]}
    except cdp.CdpHatasi as h:
        raise IsHatasi(f"{kayit['ad']} sohbeti açılamadı: {h}") from h
    except SiteHatasi as h:
        raise IsHatasi(f"{kayit['ad']} mesajları okunamadı: {h}") from h
    finally:
        b.kapat()


def site_yaniti(site_id, taban=None):
    """Sitenin son yanıtı: {"yaziyor": bool, "metin": str, "bekleniyor": bool}.

    `taban` (gönderme anındaki asistan mesajı sayısı) verilirse, yeni yanıt başlayana kadar "metin"
    boş döner; böylece önceki sohbetin eski yanıtı yeni yanıt sanılmaz.
    """
    try:
        kayit = siteler.site(site_id)
    except KeyError:
        raise IsHatasi("Site bulunamadı.") from None
    b = site_sayfasi(site_id)
    if not b:
        raise IsHatasi(f"{kayit['ad']} penceresi açık değil.")
    js = kayit["js"]
    try:
        yaziyor = b.degerlendir(js["yaziyor_mu"], zaman=SITE_ZAMAN_ASIMI)
        hata = _js_hatasi(yaziyor)
        if hata:
            return {"hata": hata}
        if taban is None:
            metin = b.degerlendir(js["son_yanit"], zaman=SITE_ZAMAN_ASIMI)
            hata = _js_hatasi(metin)
            if hata:
                return {"hata": hata}
            bekleniyor = False
        else:
            asistan = [x for x in _mesajlari_oku(b, js)["mesajlar"] if x.get("rol") == "asistan"]
            bekleniyor = len(asistan) <= taban
            metin = "" if bekleniyor else asistan[-1]["metin"]
    except cdp.CdpHatasi as h:
        raise IsHatasi(f"{kayit['ad']} yanıtı okunamadı: {h}") from h
    except SiteHatasi as h:
        return {"hata": str(h)}
    finally:
        b.kapat()
    return {"yaziyor": bool(yaziyor), "metin": metin if isinstance(metin, str) else "", "bekleniyor": bekleniyor}


# ---------------------------------------------------------------- model menüsü ve yönlendirme

_MODEL_ONBELLEGI = {}      # site kimliği -> {"zaman": monotonic, "modeller": [...], "sebep": str}
_MODEL_KILIDI = threading.Lock()
_SON_SINIFLANDIRMA = {}    # son /api/oneri sınıflandırması (yalnızca tür/zorluk/zaman; mesaj metni saklanmaz)


def _modelleri_temizle(ham):
    """Sayfadan gelen model listesini [{"id", "ad", "secili"}] biçimine indirir (en çok 100 kayıt)."""
    sonuc = []
    for m in ham if isinstance(ham, list) else []:
        ad = m.get("ad") if isinstance(m, dict) else None
        if isinstance(ad, str) and ad.strip():
            sonuc.append({"id": str(m.get("id") or ad)[:120], "ad": ad.strip()[:120], "secili": bool(m.get("secili"))})
        if len(sonuc) >= 100:
            break
    return sonuc


def _model_listesi_oku(site_id):
    """Sitenin model menüsünü (siteler.js_parca "model_listesi") okur: {"modeller": [...], "sebep": str}.

    Site açık ve giriş yapılmışsa okunur; değilse boş liste ve Türkçe sebep döner. Aynı site penceresinde
    gönderme/gezinme sürüyorsa en çok MODEL_KILIT_BEKLEME sn beklenir (menüye dokunup gönderimi bozmamak için).
    """
    kayit = siteler.site(site_id)
    ad = kayit["ad"]
    try:
        parca = siteler.js_parca(site_id, "model_listesi")
    except (ValueError, KeyError):
        return {"modeller": [], "sebep": MODEL_DESTEGI_YOK}
    kilit = _SITE_KILITLERI[site_id]
    if not kilit.acquire(timeout=MODEL_KILIT_BEKLEME):
        return {"modeller": [], "sebep": f"{ad} şu an meşgul"}
    try:
        b = site_sayfasi(site_id)
        if not b:
            return {"modeller": [], "sebep": f"{ad} penceresi kapalı"}
        try:
            giris = b.degerlendir(kayit["js"]["giris_var_mi"], zaman=SITE_ZAMAN_ASIMI)
            hata = _js_hatasi(giris)
            if hata:
                return {"modeller": [], "sebep": hata}
            if not (isinstance(giris, dict) and giris.get("giris")):
                return {"modeller": [], "sebep": f"{ad} için giriş yapılmamış"}
            sonuc = b.degerlendir(parca, zaman=MODEL_ZAMAN_ASIMI)
        except cdp.CdpHatasi as h:
            return {"modeller": [], "sebep": str(h)}
        finally:
            b.kapat()
    finally:
        kilit.release()
    hata = _js_hatasi(sonuc)
    if hata:
        return {"modeller": [], "sebep": hata}
    if not isinstance(sonuc, dict) or not isinstance(sonuc.get("modeller"), list):
        return {"modeller": [], "sebep": "Model listesi beklenmeyen biçimde geldi"}
    modeller = _modelleri_temizle(sonuc["modeller"])
    return {"modeller": modeller, "sebep": "" if modeller else str(sonuc.get("sebep") or "Menüde model bulunamadı")[:200]}


def site_modelleri(site_id, yenile=False):
    """{"site", "modeller", "sebep"}: sitenin canlı model listesi, başarılıysa 60 sn önbellekli.

    Liste alınamazsa (pencere kapalı, giriş yok, menü desteği yok) boş liste ve sebep döner; bu durum
    10 sn önbelleğe alınır (her tuş vuruşunda sayfaya yeniden sorulmasın).
    """
    if site_id not in siteler.SITELER:
        raise IsHatasi("Site bulunamadı.")
    simdi = time.monotonic()
    with _MODEL_KILIDI:
        k = _MODEL_ONBELLEGI.get(site_id)
        if k and not yenile and simdi - k["zaman"] < (MODEL_ONBELLEK_SURESI if k["modeller"] else MODEL_HATA_ONBELLEK_SURESI):
            return {"site": site_id, "modeller": k["modeller"], "sebep": k["sebep"]}
    try:
        sonuc = _model_listesi_oku(site_id)
    except Exception as h:  # noqa: BLE001
        sonuc = {"modeller": [], "sebep": guvenlik.beklenmeyen_hata(f"modeller/{site_id}", h)}
    with _MODEL_KILIDI:
        _MODEL_ONBELLEGI[site_id] = {"zaman": time.monotonic(), "modeller": sonuc["modeller"], "sebep": sonuc["sebep"]}
    return {"site": site_id, "modeller": sonuc["modeller"], "sebep": sonuc["sebep"]}


# ---------------------------------------------------------------- Jev (jev.py): kural tabanlı yolların önünde, yedekli

# Seçenek açıklamaları Jev'e gider (kullanıcıya görünmez); anahtarlar uygulamanın kendi kategori adlarıdır.
JEV_HASSAS_SECENEKLERI = {
    "parola": "The text contains a password, PIN or passphrase (in any wording, e.g. spelled out in words).",
    "api_anahtari": "The text contains an API key, access token, private key or other machine credential.",
    "kimlik_bilgisi": "The text contains a personal identity number or identity document data (national ID, passport).",
    "finansal": "The text contains a bank account number, IBAN, card number or similar financial account data.",
    "yok": "The text contains none of these secrets (ordinary text, or only mentions such things without a value).",
}
JEV_HASSAS_ACIKLAMALARI = {"parola": "bir parola", "api_anahtari": "bir API anahtarı",
                           "kimlik_bilgisi": "kimlik bilgisi", "finansal": "finansal bilgi (hesap/kart)"}
JEV_TUR_SECENEKLERI = {
    "arastirma": "Research, comparison or a question asking for sources or reasons.",
    "kod": "Programming: writing, fixing or explaining code, errors, SQL.",
    "yazi": "Writing a text: email, article, draft, story.",
    "ceviri": "Translation between languages.",
    "ozet": "Summarizing or shortening a given text.",
    "sohbet": "Casual chat, greeting or a simple everyday question.",
    "matematik": "Mathematics: calculation, equation, proof.",
}
JEV_ZORLUK_SECENEKLERI = {
    "basit": "Simple: short, one step, a fast small model is enough.",
    "orta": "Medium: needs some reasoning or a longer answer.",
    "zor": "Hard: long, multi-step, deep analysis, architecture or strategy; needs the strongest model.",
}


def jev_kullanilabilir(ayarlar):
    """Ayarlar → Jev açık ve jev.py hazır (ayar + anahtar dosyası) ise True; ağa çıkmaz."""
    return ayarlar.get("jev_acik", True) is not False and jev.hazir_mi()


def jev_hassas_tara(metin, ayarlar):
    """Yerel tarama temiz çıkınca Jev'in ikinci görüşü: {"kategori", "aciklama", "puan", "kaynak": "jev"} ya da None.

    Jev kapalı/hazır değil/hata verirse sessizce None (yerel sonuç geçerli kalır).
    """
    if not jev_kullanilabilir(ayarlar):
        return None
    try:
        s = jev.sinifla(metin, JEV_HASSAS_SECENEKLERI, acik=True)
    except Exception:  # noqa: BLE001  (Jev hatası gönderimi hiçbir koşulda engellemez)
        return None
    if s["secim"] == "yok" or s["secim"] not in JEV_HASSAS_ACIKLAMALARI or s["puan"] < JEV_HASSAS_ESIGI:
        return None
    return {"kategori": s["secim"], "aciklama": f"{JEV_HASSAS_ACIKLAMALARI[s['secim']]} (Jev'in değerlendirmesine göre)",
            "puan": round(s["puan"], 3), "kaynak": "jev"}


def jev_ile_siniflandir(metin, ayarlar):
    """Yönlendirici için Jev'le tür ve zorluk (iki istek paralel): {"tur", "zorluk"} ya da None (kurala dönülür)."""
    if not jev_kullanilabilir(ayarlar):
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as havuz:
        tur = havuz.submit(jev.sinifla, metin, JEV_TUR_SECENEKLERI)
        zorluk = havuz.submit(jev.sinifla, metin, JEV_ZORLUK_SECENEKLERI)
        try:
            return {"tur": tur.result()["secim"], "zorluk": zorluk.result()["secim"]}
        except Exception:  # noqa: BLE001  (JevHatasi ya da beklenmeyen: kural tabanlı yol)
            return None


def jev_durumu():
    """/api/jev-durum: jev.durum() + uygulamadaki iki anahtar. Anahtar değeri ve mesaj içeriği yoktur."""
    ayarlar = ayarlari_oku()["ayarlar"]
    return {**jev.durum(), "acik": ayarlar.get("jev_acik", True) is not False,
            "yanit_puanla": ayarlar.get("jev_yanit_puanla") is True}


def _puanlama_metni(soru, yanitlar):
    """"Soru: …\\nYanıtlar: [site: …] …" metni; her yanıt en çok JEV_YANIT_EN_FAZLA karakter ve toplam bütçeye sığar."""
    soru = " ".join(str(soru or "").split())[:JEV_SORU_EN_FAZLA]
    pay = max(200, min(JEV_YANIT_EN_FAZLA, (JEV_PUANLAMA_BUTCESI - len(soru)) // max(1, len(yanitlar)) - 16))
    parcalar = [f"[{site}: {metin.strip()[:pay]}]" for site, metin in yanitlar.items()]
    return f"Soru: {soru}\nYanıtlar: " + "\n".join(parcalar)


def yanit_puanla(g):
    """/api/yanit-puanla {sohbet, mesaj_sira}: ortak sohbetteki site yanıtlarından en iyisini Jev'e seçtirir.

    Ayar kilidi yalnızca okuma ve sonucu kaydetme sırasında kısa süre tutulur (Jev beklenirken tutulmaz).
    Döner: {"onerilen": site, "site_ad", "puan", "olasiliklar"}; sonuç mesaja "jev_onerilen" olarak da kaydedilir.
    """
    sohbet_id, sira = g.get("sohbet"), g.get("mesaj_sira")
    with KILIT:
        veri = ayarlari_oku()
    ayarlar = veri["ayarlar"]
    if ayarlar.get("jev_yanit_puanla") is not True:
        raise IsHatasi("Yanıt puanlama kapalı (Ayarlar → Jev).")
    if ayarlar.get("jev_acik", True) is False:
        raise IsHatasi("Jev kapalı (Ayarlar → Jev).")
    sohbet = next((s for s in veri["sohbetler"] if s.get("id") == sohbet_id), None)
    if not sohbet or not isinstance(sira, int) or isinstance(sira, bool) or not 0 <= sira < len(sohbet["mesajlar"]):
        raise IsHatasi("Sohbet ya da mesaj bulunamadı.")
    mesaj = sohbet["mesajlar"][sira]
    kayitli = mesaj.get("yanitlar") if isinstance(mesaj.get("yanitlar"), dict) else {}
    yanitlar = {sid: kayitli[sid] for sid in siteler.SITELER if isinstance(kayitli.get(sid), str) and kayitli[sid].strip()}
    if len(yanitlar) < 2:
        raise IsHatasi("Puanlamak için en az iki site yanıtı gerekli.")
    try:
        s = jev.sinifla(_puanlama_metni(mesaj.get("metin", ""), yanitlar),
                        {sid: f"The answer labelled [{sid}] is the best answer to the question "
                              "(most correct, complete and helpful)." for sid in yanitlar},
                        baglam="Pick the single best answer among the labelled answers to the question.")
    except jev.JevHatasi as h:
        raise IsHatasi(f"Yanıtlar puanlanamadı: {h}") from None
    with KILIT:  # sonucu kaydet (arada sohbet silindiyse sessizce atla)
        veri = ayarlari_oku()
        sohbet = next((x for x in veri["sohbetler"] if x.get("id") == sohbet_id), None)
        if sohbet and sira < len(sohbet["mesajlar"]):
            sohbet["mesajlar"][sira]["jev_onerilen"] = {"site": s["secim"], "puan": round(s["puan"], 3)}
            ayarlari_yaz(veri)
    return {"onerilen": s["secim"], "site_ad": siteler.SITELER[s["secim"]]["ad"], "puan": s["puan"],
            "olasiliklar": s["olasiliklar"]}


# ---------------------------------------------------------------- Tek Asistan: motorlar (motorlar/ paketi)

# Motor kimliği -> (ad, renk): motorlar paketi yoksa ya da motor bulunamazsa arayüzün yine de gösterebilmesi için.
MOTOR_BILGILERI = {"claude": ("Claude", "#d97757"), "codex": ("Codex (ChatGPT)", "#10a37f"),
                   "gemini": ("Gemini", "#4285f4")}
MOTOR_ONBELLEK_SURESI = 60        # sn: motor durumları (hazir_mi) bu süre içinde yeniden ölçülmez
MOTOR_OLCME_ZAMAN_ASIMI = 20      # sn: tüm motorların durum ölçümü için üst sınır
GIRIS_TALIMATLARI = {
    "claude": "Giriş için terminalde `claude` komutunu çalıştırıp oturum aç (/login).",
    "codex": "Giriş için terminalde `codex login` komutunu çalıştırıp ChatGPT hesabınla oturum aç.",
    "gemini": "Giriş için terminalde `gemini` komutunu çalıştırıp Google hesabınla oturum aç.",
}
SOR_METIN_EN_FAZLA = 100000       # karakter: tek mesajın üst sınırı
TRANSKRIPT_MESAJ_SAYISI = 6       # motor değişince yeni motora verilen son mesaj sayısı
TRANSKRIPT_MESAJ_EN_FAZLA = 700   # karakter: transkriptte her mesajdan en çok bu kadar
OTURUM_EN_FAZLA = 2000            # karakter: kayıtlı motor oturumunun (JSON) üst sınırı
SISTEM_ISTEMI = ("Sen Yapay Zeka Merkezi'nin tek asistanısın; kullanıcı Yusuf ile konuşuyorsun. Kullanıcı Türkçe "
                 "yazdıysa Türkçe yanıt ver. Doğru, açık ve gereksiz uzatmayan yanıtlar yaz; kod için kod bloğu kullan. "
                 "Arkanda birden fazla motor olduğundan söz etme.")

_MOTOR_ONBELLEGI = {"zaman": 0.0, "liste": None}   # son motor durumları (/api/durum "motorlar")
_MOTOR_KILIDI = threading.Lock()
_IPTALLER = {}                                      # sohbet kimliği -> sürmekte olan yanıtın iptal Event'i
_IPTAL_KILIDI = threading.Lock()


def _motorlar_paketi():
    """(motorlar paketi, hata sebebi). Paket her çağrıda sys.modules'tan alınır; yoksa (None, Türkçe sebep)."""
    try:
        import motorlar
        return motorlar, None
    except Exception as h:  # noqa: BLE001  (ImportError ya da paketin kendi hatası: uygulama kırılmaz)
        return None, f"Motorlar hazır değil: motorlar paketi yüklenemedi ({type(h).__name__})."


def _motor(motor_id):
    """Motor nesnesi (motorlar.motor(id)); paket ya da motor yoksa None."""
    paket, _ = _motorlar_paketi()
    if paket is None:
        return None
    try:
        return paket.motor(motor_id)
    except Exception:  # noqa: BLE001
        return None


def _motor_durumu_olc(motor_id):
    """{"id","ad","renk","hazir","sebep","giris","surum"}; hata ya da eksik motor "hazır değil" sayılır."""
    ad, renk = MOTOR_BILGILERI[motor_id]
    _, paket_sebebi = _motorlar_paketi()
    m = _motor(motor_id)
    if m is None:
        return {"id": motor_id, "ad": ad, "renk": renk, "hazir": False, "giris": None, "surum": None,
                "sebep": paket_sebebi or f"{ad} motoru bulunamadı."}
    ad, renk = str(getattr(m, "ad", None) or ad), str(getattr(m, "renk", None) or renk)
    try:
        h = m.hazir_mi()
        h = h if isinstance(h, dict) else {}
    except Exception as hata:  # noqa: BLE001
        h = {"hazir": False, "sebep": f"Durum okunamadı ({type(hata).__name__})."}
    hazir, giris = h.get("hazir") is True, h.get("giris") if isinstance(h.get("giris"), bool) else None
    sebep = str(h.get("sebep") or "").strip()
    if not hazir:
        sebep = sebep or f"{ad} hazır değil."
        if giris is False and "giriş" not in sebep.lower():
            sebep = f"{sebep} {GIRIS_TALIMATLARI[motor_id]}"
    surum = h.get("surum") if isinstance(h.get("surum"), str) else None
    return {"id": motor_id, "ad": ad, "renk": renk, "hazir": hazir, "sebep": sebep, "giris": giris, "surum": surum}


def motor_durumlari(yenile=False):
    """Üç motorun durumu (paralel ölçülür, MOTOR_ONBELLEK_SURESI sn önbelleklenir)."""
    with _MOTOR_KILIDI:
        simdi = time.monotonic()
        if not yenile and _MOTOR_ONBELLEGI["liste"] is not None and simdi - _MOTOR_ONBELLEGI["zaman"] < MOTOR_ONBELLEK_SURESI:
            return copy.deepcopy(_MOTOR_ONBELLEGI["liste"])
        kimlikler = list(yonlendirici.MOTORLAR)
        havuz = concurrent.futures.ThreadPoolExecutor(max_workers=len(kimlikler))
        isler = {mid: havuz.submit(_motor_durumu_olc, mid) for mid in kimlikler}
        concurrent.futures.wait(isler.values(), timeout=MOTOR_OLCME_ZAMAN_ASIMI)
        havuz.shutdown(wait=False)
        liste = []
        for mid in kimlikler:
            ad, renk = MOTOR_BILGILERI[mid]
            if isler[mid].done() and isler[mid].exception() is None:
                liste.append(isler[mid].result())
            else:
                liste.append({"id": mid, "ad": ad, "renk": renk, "hazir": False, "giris": None, "surum": None,
                              "sebep": f"{ad} durumu zamanında okunamadı."})
        _MOTOR_ONBELLEGI.update(zaman=time.monotonic(), liste=liste)
        return copy.deepcopy(liste)


def _modeller(m):
    """Motorun model listesi ([{"id","ad","sinif"}]); hata olursa boş."""
    try:
        return [x for x in (m.modeller() or []) if isinstance(x, dict)]
    except Exception:  # noqa: BLE001
        return []


def _model_coz(motor_id, m, sinif, ayarlar, istenen=None):
    """Motorun listesinden modeli seçer: istenen kimlik, Ayarlar → Motorlar tercihi, sınıfa uyan ilk model. Yoksa None."""
    modeller = _modeller(m) if m is not None else []
    if istenen and any(x.get("id") == istenen for x in modeller):
        return next(x for x in modeller if x.get("id") == istenen)
    tercih = ((ayarlar.get("motor_modelleri") or {}).get(motor_id) or {}).get(sinif)
    return yonlendirici.model_sec(modeller, sinif, tercih if isinstance(tercih, str) else None)


def motor_modelleri():
    """/api/motor-modelleri: {motor kimliği: [{"id","ad","sinif"}]} (Ayarlar → Motorlar'daki model seçimi için)."""
    cikti = {}
    for mid in yonlendirici.MOTORLAR:
        m = _motor(mid)
        cikti[mid] = [{"id": str(x.get("id")), "ad": str(x.get("ad") or x.get("id")), "sinif": x.get("sinif")}
                      for x in (_modeller(m) if m is not None else []) if x.get("id")]
    return cikti


def plan_olustur(metin, ayarlar, motor_istegi="otomatik"):
    """(yonlendirici sonucu, adaylar, uyarılar). Adaylar tercih sırasıdır: [{"motor","sinif","sebep"}].

    Otomatikte Jev açık ve hazırsa tür/zorluk Jev'le bulunur (kaynak "jev"), değilse kurallarla. Metin hassas bilgi
    içeriyorsa Jev'e hiç gitmez. Motor elle seçildiyse o motor başa alınır (kaynak "kullanici"), diğerleri yedektir.
    """
    kurallar, uyarilar = yonlendirici.kurallari_yukle()
    sinif = None
    if motor_istegi == "otomatik" and hassas.tara(metin)["kategori"] == "yok":
        sinif = jev_ile_siniflandir(metin, ayarlar)
    sonuc = yonlendirici.oner(metin, kurallar, sinif=sinif, kaynak="jev")
    _SON_SINIFLANDIRMA.clear()
    _SON_SINIFLANDIRMA.update(tur=sonuc["tur"], tur_ad=sonuc["tur_ad"], zorluk=sonuc["zorluk"],
                              zorluk_ad=sonuc["zorluk_ad"], kaynak=sonuc["kaynak"],
                              zaman=datetime.now().strftime("%H:%M:%S"))
    adaylar = [{"motor": o["motor"], "sinif": o["sinif"], "sebep": o["sebep"]} for o in sonuc["oneriler"]]
    if motor_istegi != "otomatik":
        ad = MOTOR_BILGILERI[motor_istegi][0]
        ilk = next((a for a in adaylar if a["motor"] == motor_istegi), None) or {"motor": motor_istegi, "sinif": "dengeli"}
        adaylar = [{**ilk, "sebep": f"{ad} senin seçimin"}] + [a for a in adaylar if a["motor"] != motor_istegi]
        sonuc["kaynak"] = "kullanici"
    return sonuc, adaylar, uyarilar


def oneri_olustur(metin):
    """/api/oneri: metni sınıflandırır, tercih sırasındaki her öneriye motorun durumunu ve sınıfa uyan modeli ekler.

    Jev açık ve hazırsa tür ve zorluk Jev'le bulunur (kaynak "jev"); kapalı/hata → kural tabanlı (kaynak "kural").
    Her öneri: motor, motor_ad, sinif, sinif_ad, sebep, hazir, hazir_sebep, model, model_ad (model yoksa None).
    """
    if not isinstance(metin, str) or not metin.strip():
        raise IsHatasi("Mesaj boş.")
    ayarlar = ayarlari_oku()["ayarlar"]  # ayar dosyası yalnızca okunur
    sonuc, _, uyarilar = plan_olustur(metin, ayarlar)
    durumlar = {d["id"]: d for d in motor_durumlari()}
    for o in sonuc["oneriler"]:
        d = durumlar.get(o["motor"]) or {}
        model = _model_coz(o["motor"], _motor(o["motor"]), o["sinif"], ayarlar)
        o.update(hazir=bool(d.get("hazir")), hazir_sebep=d.get("sebep", ""),
                 model=model.get("id") if model else None, model_ad=(model.get("ad") or model.get("id")) if model else None)
    sonuc["uyarilar"] = uyarilar
    return sonuc


# ---------------------------------------------------------------- Tek Asistan: /api/sor akışı

def sor_hazirla(g):
    """/api/sor gövdesini denetler. Döner: {"metin","motor","model","sohbet","onayli"}; geçersizse IsHatasi (400)."""
    metin = g.get("metin")
    if not isinstance(metin, str) or not metin.strip():
        raise IsHatasi("Mesaj boş.")
    if len(metin) > SOR_METIN_EN_FAZLA:
        raise IsHatasi(f"Mesaj en çok {SOR_METIN_EN_FAZLA} karakter olabilir.")
    motor_istegi = g.get("motor", "otomatik")
    if motor_istegi is None:
        motor_istegi = "otomatik"
    if motor_istegi != "otomatik" and motor_istegi not in yonlendirici.MOTORLAR:
        raise IsHatasi("Geçersiz motor.")
    model = g.get("model")
    if model is not None and not (isinstance(model, str) and len(model) <= 120):
        raise IsHatasi("Geçersiz model.")
    sohbet = g.get("sohbet")
    if sohbet is not None and not (isinstance(sohbet, str) and len(sohbet) <= 80):
        raise IsHatasi("Geçersiz sohbet.")
    return {"metin": metin.strip(), "motor": motor_istegi, "model": (model or "").strip() or None,
            "sohbet": sohbet or None, "onayli": g.get("onayli") is True, "yeniden": g.get("yeniden") is True}


def _kisa(metin, sinir):
    metin = " ".join(str(metin or "").split())
    return metin if len(metin) <= sinir else metin[:sinir - 1].rstrip() + "…"


def transkript_olustur(mesajlar):
    """Motor değişince yeni motora verilecek kısa özet: son TRANSKRIPT_MESAJ_SAYISI mesaj (yoksa boş metin)."""
    satirlar = []
    for m in mesajlar:
        if m.get("rol") == "asistan":
            if m.get("metin"):
                ad = MOTOR_BILGILERI.get(m.get("motor"), (m.get("motor") or "?",))[0]
                satirlar.append(f"Asistan ({ad}): {m['metin']}")
        elif m.get("rol") == "kullanici" or "rol" not in m:
            satirlar.append(f"Kullanıcı: {m.get('metin', '')}")
            for site, yanit in (m.get("yanitlar") or {}).items():  # eski çoklu pencere kaydı
                if isinstance(yanit, str) and yanit.strip():
                    satirlar.append(f"Asistan ({site}): {yanit}")
    son = satirlar[-TRANSKRIPT_MESAJ_SAYISI:]
    if not son:
        return ""
    govde = "\n".join("- " + _kisa(s, TRANSKRIPT_MESAJ_EN_FAZLA) for s in son)
    return ("Önceki konuşma özeti (bu sohbet daha önce başka bir asistanla sürdü; yalnızca bağlam olarak kullan, "
            f"tekrar etme):\n{govde}\n\nYeni mesaj:\n")


def _son_asistan_motoru(mesajlar):
    return next((m.get("motor") for m in reversed(mesajlar) if m.get("rol") == "asistan" and m.get("motor")), None)


def _oturum_gecerli(oturum):
    try:
        return oturum is not None and len(json.dumps(oturum, ensure_ascii=False)) <= OTURUM_EN_FAZLA
    except (TypeError, ValueError):
        return False


def _tek_sohbet_hazirla(veri, sohbet_id, metin, yeniden=False):
    """Sohbeti bulur (yoksa Tek Asistan sohbeti oluşturur) ve kullanıcı mesajını ekler. Döner: sohbet, önceki mesajlar.

    yeniden=True ("Yeniden sor"): sohbetin son kullanıcı mesajı aynı metinse yeni mesaj eklenmez; varsa onun asistan
    yanıtı silinir ve soru başka bir motora yeniden sorulur. Eşleşmezse normal mesaj gibi eklenir.
    """
    sohbet = next((s for s in veri["sohbetler"] if s["id"] == sohbet_id), None) if sohbet_id else None
    if not sohbet:
        sohbet = {"id": sohbet_id or datetime.now().strftime("%Y%m%d%H%M%S%f"),
                  "baslik": metin.strip().splitlines()[0][:48], "zaman": datetime.now().isoformat(timespec="minutes"),
                  "mesajlar": [], "kip": "tek"}
        veri["sohbetler"].insert(0, sohbet)
    mesajlar = sohbet["mesajlar"]
    if yeniden:
        if mesajlar and mesajlar[-1].get("rol") == "asistan":
            soru_sirasi = len(mesajlar) - 2
        else:
            soru_sirasi = len(mesajlar) - 1
        if soru_sirasi >= 0 and mesajlar[soru_sirasi].get("rol") == "kullanici" and mesajlar[soru_sirasi].get("metin") == metin:
            del mesajlar[soru_sirasi + 1:]
            sohbet["guncelleme"] = datetime.now().isoformat(timespec="minutes")
            return sohbet, list(mesajlar[:soru_sirasi])
    onceki = list(mesajlar)
    mesajlar.append({"rol": "kullanici", "metin": metin, "zaman": datetime.now().strftime("%H:%M")})
    sohbet["guncelleme"] = datetime.now().isoformat(timespec="minutes")
    return sohbet, onceki


def _baglam_kaydet(sohbet_id, baglam):
    """Hafıza OS bağlamını, sohbetin son kullanıcı mesajına ayrı alan olarak yazar (ham mesaj değişmez)."""
    with KILIT:
        veri = ayarlari_oku()
        sohbet = next((s for s in veri["sohbetler"] if s["id"] == sohbet_id), None)
        if sohbet and sohbet["mesajlar"] and sohbet["mesajlar"][-1].get("rol") == "kullanici":
            sohbet["mesajlar"][-1]["baglam"] = baglam
            ayarlari_yaz(veri)


def _asistan_kaydet(sohbet_id, kayit, motor_id, oturum):
    """Asistan mesajını sohbete ekler ve motor oturumunu saklar. Döner: mesajın sırası (sohbet silindiyse None)."""
    with KILIT:
        veri = ayarlari_oku()
        sohbet = next((s for s in veri["sohbetler"] if s["id"] == sohbet_id), None)
        if not sohbet:
            return None
        sohbet["mesajlar"].append(kayit)
        if motor_id and _oturum_gecerli(oturum):
            if not isinstance(sohbet.get("motor_oturumlari"), dict):
                sohbet["motor_oturumlari"] = {}
            sohbet["motor_oturumlari"][motor_id] = oturum
        sohbet["guncelleme"] = datetime.now().isoformat(timespec="minutes")
        ayarlari_yaz(veri)
        return len(sohbet["mesajlar"]) - 1


def sor_durdur(g):
    """/api/durdur {sohbet}: o sohbette süren yanıtı iptal eder (sohbet verilmezse sürenlerin hepsini)."""
    sohbet = g.get("sohbet")
    with _IPTAL_KILIDI:
        olaylar = [_IPTALLER[sohbet]] if sohbet in _IPTALLER else ([] if sohbet else list(_IPTALLER.values()))
    for olay in olaylar:
        olay.set()
    return {"tamam": True, "durduruldu": bool(olaylar)}


def sor_akisi(p):
    """/api/sor için olay üreteci (NDJSON satırları). Sıra: [onay_gerekli] | secim, [durum], motor olayları, kayit.

    Motor olayları parca / durum / bitti / hata aynen geçer. Her yol sonunda asistan mesajı kaydedilir (hata ya da
    durdurulmuş yanıt dahil); istemci bağlantıyı koparırsa üreteç kapanır, yanıt iptal edilir ve o ana kadarki metin saklanır.
    """
    metin = p["metin"]
    with KILIT:
        ayarlar = ayarlari_oku()["ayarlar"]
    if ayarlar.get("hassas_uyari", True) and not p["onayli"]:  # onay gerekiyorsa hiçbir şey kaydedilmez/gönderilmez
        tarama = hassas.tara(metin)
        if tarama["kategori"] != "yok":
            yield {"tur": "onay_gerekli", "kategori": tarama["kategori"], "aciklama": hassas.uyari_metni(tarama),
                   "eslesme_sayisi": tarama["eslesme_sayisi"], "kaynak": "kural"}
            return
        jev_h = jev_hassas_tara(metin, ayarlar)
        if jev_h:
            yield {"tur": "onay_gerekli", **jev_h}
            return
    if p["sohbet"]:
        with _IPTAL_KILIDI:
            mesgul = p["sohbet"] in _IPTALLER
        if mesgul:
            yield {"tur": "hata", "mesaj": "Bu sohbette bir yanıt hâlâ sürüyor; bitmesini bekle ya da Durdur'a bas."}
            return
    # Hafıza bağlamı ve yönlendirme (Jev) birbirinden bağımsız ağ/alt süreç işleri: paralel yürütülür.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as havuz:
        baglam_is = havuz.submit(hafiza_kopru.baglam_ekle, metin) if ayarlar.get("hafiza_ekle", True) else None
        plan_is = havuz.submit(plan_olustur, metin, ayarlar, p["motor"])
        gonderilecek, baglam = baglam_is.result() if baglam_is else (metin, None)
        sonuc, adaylar, _ = plan_is.result()
    durumlar = {d["id"]: d for d in motor_durumlari()}
    secilen = next((a for a in adaylar if durumlar[a["motor"]]["hazir"]), None)
    iptal = threading.Event()
    with KILIT:  # kullanıcı mesajı akış başlamadan kaydedilir (bağlantı kopsa da geçmişte kalır)
        veri = ayarlari_oku()
        sohbet, onceki = _tek_sohbet_hazirla(veri, p["sohbet"], metin, p["yeniden"])
        sid = sohbet["id"]
        oturumlar = dict(sohbet.get("motor_oturumlari") or {})
        son_motor = _son_asistan_motoru(onceki)
        ayarlari_yaz(veri)
    if baglam:
        _baglam_kaydet(sid, baglam)
    with _IPTAL_KILIDI:
        _IPTALLER[sid] = iptal
    try:
        if not secilen:
            neden = " ".join(f"{d['ad']}: {d['sebep']}" for d in durumlar.values())
            hata = f"Hazır bir motor yok. {neden}".strip()
            sira = _asistan_kaydet(sid, {"rol": "asistan", "metin": "", "hata": hata, "motor": None, "model": None,
                                         "sure": 0, "zaman": datetime.now().strftime("%H:%M")}, "", None)
            yield {"tur": "secim", "sohbet": sid, "motor": None, "motor_ad": None, "renk": None, "model": None,
                   "model_ad": None, "sebep": "Hazır motor yok", "kaynak": sonuc["kaynak"], "yedek": False}
            yield {"tur": "hata", "mesaj": hata}
            yield {"tur": "kayit", "sohbet": sid, "mesaj_sira": sira}
            return
        mid, d = secilen["motor"], durumlar[secilen["motor"]]
        m = _motor(mid)
        model = _model_coz(mid, m, secilen["sinif"], ayarlar, p["model"] if p["motor"] == mid else None)
        atlanan = [durumlar[a["motor"]] for a in adaylar[:adaylar.index(secilen)]]
        sebep = secilen["sebep"] + (f" ({atlanan[0]['ad']} hazır değil)" if atlanan else "")
        yield {"tur": "secim", "sohbet": sid, "motor": mid, "motor_ad": d["ad"], "renk": d["renk"],
               "model": model.get("id") if model else None,
               "model_ad": (model.get("ad") or model.get("id")) if model else None,
               "sinif": secilen["sinif"], "istek_turu": sonuc["tur"], "zorluk": sonuc["zorluk"],
               "sebep": sebep, "kaynak": sonuc["kaynak"], "yedek": bool(atlanan)}
        if atlanan:
            yield {"tur": "durum", "metin": f"{atlanan[0]['ad']} hazır değil, {d['ad']} ile devam ediyorum"}
        oturum = oturumlar.get(mid)
        giris = ""
        if onceki and (son_motor != mid or not oturum):  # yeni motor önceki konuşmayı bilmiyor: kısa transkript ver
            giris = transkript_olustur(onceki[-TRANSKRIPT_MESAJ_SAYISI * 3:])
        istem = giris + gonderilecek
        parcalar, yeni_oturum, bitti, hata = [], oturum, None, None
        baslangic = time.monotonic()
        akis = None
        try:
            akis = m.sor(istem, oturum=oturum, model=model.get("id") if model else None, sistem=SISTEM_ISTEMI,
                         calisma_klasoru=None, iptal=iptal)
            for olay in akis:
                if not isinstance(olay, dict):
                    continue
                tur = olay.get("tur")
                if tur == "baslangic":
                    yeni_oturum = olay.get("oturum") or yeni_oturum
                elif tur == "parca":
                    parcalar.append(str(olay.get("metin") or ""))
                elif tur == "bitti":
                    bitti = olay
                    yeni_oturum = olay.get("oturum") or yeni_oturum
                elif tur == "hata":
                    if olay.get("iptal") and iptal.is_set():
                        break  # kullanıcı durdurdu: gerçek motorun "İptal edildi." olayı hata sayılmaz (kayıtta durduruldu işaretlenir)
                    hata = str(olay.get("mesaj") or "Bilinmeyen hata")[:500]
                elif tur != "durum":
                    continue
                yield olay
                if iptal.is_set():
                    break
        except GeneratorExit:
            iptal.set()  # istemci koptu: motor işi bırakmalı; finally kısmi yanıtı kaydeder
            raise
        except Exception as h:  # noqa: BLE001  (MotorHatasi Türkçe mesajını taşır; gerisi kısa kodla)
            hata = str(h)[:500] if type(h).__name__ == "MotorHatasi" else guvenlik.beklenmeyen_hata("sor/" + mid, h)
            yield {"tur": "hata", "mesaj": hata}
        finally:
            if akis is not None and hasattr(akis, "close"):
                try:
                    akis.close()
                except Exception:  # noqa: BLE001
                    pass
            govde = bitti["metin"] if bitti and isinstance(bitti.get("metin"), str) and bitti["metin"] else "".join(parcalar)
            sure = (bitti or {}).get("sure")
            kayit = {"rol": "asistan", "metin": govde[:YANIT_KAYIT_SINIRI], "motor": mid,
                     "model": (bitti or {}).get("model") or (model.get("id") if model else None),
                     "model_ad": (model.get("ad") or model.get("id")) if model else None,
                     "sure": sure if isinstance(sure, (int, float)) else round(time.monotonic() - baslangic, 1),
                     "zaman": datetime.now().strftime("%H:%M")}
            if hata:
                kayit["hata"] = hata
            if iptal.is_set():
                kayit["durduruldu"] = True
            try:
                sira = _asistan_kaydet(sid, kayit, mid, yeni_oturum)
                if kayit["metin"] and not hata and not iptal.is_set() and ayarlar.get("hafiza_aday", True):
                    hafiza_kopru.aday_yaz(d["ad"], metin, kayit["metin"])  # Hafıza OS gelen kutusuna aday (yalnızca ekleme)
            except Exception as h:  # noqa: BLE001
                sira = None
                guvenlik.beklenmeyen_hata("sor/kayit", h)
        yield {"tur": "kayit", "sohbet": sid, "mesaj_sira": sira}
    finally:
        with _IPTAL_KILIDI:
            _IPTALLER.pop(sid, None)


def yonlendirme_durumu():
    """/api/yonlendirme: Ayarlar → Yönlendirme sekmesi için salt okunur tablo, dosya yolu ve son sınıflandırma."""
    kurallar, uyarilar = yonlendirici.kurallari_yukle()
    return {"dosya": str(yonlendirici.YONLENDIRME_DOSYASI), "tablo": yonlendirici.tablo(kurallar),
            "uyarilar": uyarilar, "son": dict(_SON_SINIFLANDIRMA) or None}


def yonlendirme_dosyasini_ac():
    """yonlendirme.json'u varsayılan düzenleyicide açar (yol sabittir, istekten alınmaz)."""
    yol = yonlendirici.YONLENDIRME_DOSYASI
    if not yol.is_file():
        raise IsHatasi(f"{yol.name} bulunamadı: {yol}")
    ac = getattr(os, "startfile", None)
    if ac is None:
        raise IsHatasi(f"Dosya otomatik açılamadı; elle açın: {yol}")
    try:
        ac(str(yol))
    except OSError as h:
        raise IsHatasi(f"Dosya açılamadı ({h}); elle açın: {yol}") from h
    return {"tamam": True, "dosya": str(yol)}


def _model_sec_dogrula(ham):
    """İstekteki `model_sec` ({"site", "model"}) şemasını denetler; yoksa None, geçersizse IsHatasi."""
    if ham is None:
        return None
    if (not isinstance(ham, dict) or ham.get("site") not in siteler.SITELER
            or not isinstance(ham.get("model"), str) or not 0 < len(ham["model"].strip()) <= 120):
        raise IsHatasi("Geçersiz model seçimi.")
    return {"site": ham["site"], "model": ham["model"].strip()}


def _model_sec(b, site_id, model):
    """Sitenin model menüsünden `model`i seçer. Döner: None (seçildi) ya da sorunun Türkçe sebebi.

    Seçilemezse gönderim engellenmez: mesaj mevcut modelle gider ve çağıran "model seçilemedi: <sebep>" ekler.
    """
    try:
        parca = siteler.js_parca(site_id, "model_sec", hedef_model=model)
    except (ValueError, KeyError):
        return MODEL_DESTEGI_YOK
    try:
        sonuc = b.degerlendir(parca, zaman=MODEL_ZAMAN_ASIMI)
    except cdp.CdpHatasi as h:
        return str(h)
    hata = _js_hatasi(sonuc)
    if hata:
        return hata
    if not isinstance(sonuc, dict):
        return "Sayfadan beklenmeyen yanıt geldi"
    if sonuc.get("tamam"):
        return None
    return str(sonuc.get("sebep") or "bilinmeyen sebep")[:200]


# ---------------------------------------------------------------- doğrulamalar

def _uzak_surucu_mu(yol):
    """Yol ağ sürücüsünde mi? (Windows dışında ya da ölçülemezse False)"""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return ctypes.windll.kernel32.GetDriveTypeW(yol[:2] + "\\") == 4  # DRIVE_REMOTE
    except (AttributeError, OSError):
        return False


def _yol_hatasi(yol, exe=None):
    r"""Eklenen/başlatılan program yolu güvenli mi? Sorun varsa Türkçe metin, yoksa None.

    Mutlak ve yerel sürücüde (UNC `\\sunucu\pay` ve `\\?\` yasak), `.exe` uzantılı olmalı ve
    verilmişse `exe` yolun dosya adıyla aynı olmalı.
    """
    if not isinstance(yol, str) or not yol.strip() or "\x00" in yol or len(yol) > 520:
        return "Program yolu gerekli."
    if yol.startswith(("\\\\", "//")):
        return "Ağ yolları ve özel (\\\\?\\) yollar kabul edilmez."
    if not re.match(r"^[A-Za-z]:[\\/]", yol):
        return "Program yolu mutlak olmalı (ör. C:\\Program Files\\...)."
    if _uzak_surucu_mu(yol):
        return "Ağ sürücüsündeki programlar kabul edilmez."
    ad = PureWindowsPath(yol).name
    if not ad.lower().endswith(".exe"):
        return "Yalnızca .exe uzantılı programlar eklenebilir."
    if exe is not None and str(exe).strip().lower() != ad.lower():
        return "Program adı ile yol uyuşmuyor."
    return None


def _yol_gecerli_mi(yol, exe=None):
    return _yol_hatasi(yol, exe) is None


def _normal_yol(yol):
    return os.path.normcase(os.path.normpath(str(yol)))


def _program_acik_mi(yol):
    """İstek anında bu yola sahip açık bir pencere var mı? (program eklerken kullanıcı programı açmış olmalı)"""
    hedef = _normal_yol(yol)
    return any(p.yol and _normal_yol(p.yol) == hedef for p in pc.pencereleri_listele())


def _programi_baslat(veri, u):
    """Programı açar. Kullanıcının eklediği programlar önce yol denetiminden geçer, yalnızca ad ve yol kullanılır."""
    if u in veri["ek_uygulamalar"]:
        if u.get("yol"):
            hata = _yol_hatasi(u["yol"], u.get("exe"))
            if hata:
                raise IsHatasi(f"{u.get('ad', 'Program')} açılamadı: {hata}")
        u = {"ad": u.get("ad", "Program"), "yol": u.get("yol")}
    pc.uygulamayi_ac(u)


def _mantiksal_mi(x):
    return isinstance(x, bool)


def _ayar_dogrula(g, veri):
    """/api/ayar gövdesini şemaya göre denetler; geçersizse IsHatasi (hiçbir şey kaydedilmez)."""
    for k, izinli in AYAR_SECENEKLERI.items():
        if k in g and not (isinstance(g[k], str) and g[k] in izinli):
            raise IsHatasi(f"Geçersiz ayar değeri: {k}.")
    for k in AYAR_MANTIKSAL:
        if k in g and not _mantiksal_mi(g[k]):
            raise IsHatasi(f"Geçersiz ayar değeri: {k}.")
    if "motor_modelleri" in g:
        mm = g["motor_modelleri"]
        if not (isinstance(mm, dict) and all(
                k in yonlendirici.MOTORLAR and isinstance(v, dict) and all(
                    sk in yonlendirici.SINIFLAR and isinstance(mid, str) and len(mid) <= 120 for sk, mid in v.items())
                for k, v in mm.items())):
            raise IsHatasi("Geçersiz ayar değeri: motor_modelleri.")
    if "ad" in g and not (isinstance(g["ad"], str) and len(g["ad"]) <= AD_EN_FAZLA):
        raise IsHatasi(f"Ad en çok {AD_EN_FAZLA} karakter olabilir.")
    if "secili" in g:
        secili = g["secili"]
        if not isinstance(secili, dict):
            raise IsHatasi("Geçersiz hedef seçimi.")
        bilinen = {"site:" + sid for sid in siteler.SITELER} | {u["id"] for u in uygulamalar(veri)}
        for anahtar, deger in secili.items():
            if anahtar not in bilinen or not _mantiksal_mi(deger):
                raise IsHatasi("Geçersiz hedef seçimi.")


# ---------------------------------------------------------------- işlemler

def hepsini_diz(veri):
    """Seçili ve açık site pencerelerini (CDP ile) ve masaüstü programlarını (HWND ile) yan yana dizer."""
    acik = pc.pencereleri_listele()
    programlar = [pc.pencere_bul(u, acik) for u in uygulamalar(veri) if program_secili(veri, u["id"])]
    programlar = [h for h in programlar if h]
    site_pencereleri = [site_hedefi(sid) for sid in siteler.SITELER if site_secili(veri, sid)]
    site_pencereleri = [h for h in site_pencereleri if h]
    adet = len(programlar) + len(site_pencereleri)
    if not adet:
        raise IsHatasi("Dizilecek açık hesap ya da program yok. Önce açın.")
    sol, ust, sag, alt = pc.calisma_alani()
    ben = kendi_pencere()
    if veri["ayarlar"]["yerlesim"] == "alt":
        cubuk = 300
        konumlar = pc.yan_yana_konumlar((sol, ust, sag, alt), adet, cubuk)
        benim = (sol, alt - cubuk, sag - sol, cubuk)
    else:
        benim_genislik = max(400, (sag - sol) * 28 // 100)
        konumlar = pc.yan_yana_konumlar((sol + benim_genislik, ust, sag, alt), adet, 0)
        benim = (sol, ust, benim_genislik, alt - ust)
    olcek = pc.olcek()  # tarayıcı pencere sınırları mantıksal (DIP) pikseldir, konumlar fiziksel
    for h, (x, y, g, yk) in zip(site_pencereleri, konumlar):
        try:
            tarayici.pencere_sinirlari(h["id"], x / olcek, y / olcek, g / olcek, yk / olcek)
        except cdp.CdpHatasi as e:
            raise IsHatasi(f"Site penceresi yerleştirilemedi: {e}") from e
    for h, (x, y, g, yk) in zip(programlar, konumlar[len(site_pencereleri):]):
        pc.yerlestir(h.hwnd, x, y, g, yk)
    if ben:
        pc.yerlestir(ben.hwnd, *benim)
        pc.one_getir(ben.hwnd)
    return adet


def _kutuyu_hazirla(b, js, bekleme):
    """Yazı kutusunu bulur, odaklar ve boşaltır; sayfa yeni yüklendiyse `bekleme` sn'ye kadar yeniden dener."""
    bitis = time.monotonic() + bekleme
    while True:
        try:
            s = b.degerlendir(js["yazi_kutusunu_bul"], zaman=SITE_ZAMAN_ASIMI)
        except cdp.CdpHatasi as h:
            if time.monotonic() >= bitis:
                raise SiteHatasi(str(h)) from h
            s = None
        if isinstance(s, dict) and s.get("tamam"):
            return
        if time.monotonic() >= bitis:
            raise SiteHatasi((s or {}).get("sebep") or _js_hatasi(s) or "yazı kutusu bulunamadı")
        time.sleep(0.5)


def _kutu_odakta_mi(b, js):
    """Odak işaretli yazı kutusunda değilse SiteHatasi (yazı eklenmeden önce)."""
    sonuc = b.degerlendir(js["kutu_hazir_mi"], zaman=SITE_ZAMAN_ASIMI)
    hata = _js_hatasi(sonuc)
    if hata:
        raise SiteHatasi(hata)
    if not (isinstance(sonuc, dict) and sonuc.get("hazir")):
        raise SiteHatasi("yazı kutusu odaklanamadı; gönderilmedi")


def _bosluksuz(metin):
    """Karşılaştırma için: boşluk ve satır sonu biçimi sitelere göre değiştiğinden tüm boşluklar atılır."""
    return re.sub(r"\s+", "", str(metin or "").replace("\u00a0", " "))


def _yazilani_dogrula(b, js, metin):
    """Kutudaki metin gönderilmek istenen metinle aynı mı? Değilse SiteHatasi (gönderme yapılmaz)."""
    if len(metin) > KUTU_DOGRULAMA_SINIRI:  # kutu_metni çok uzun metni kırpar; karşılaştırma anlamsız olur
        return
    yazilan = b.degerlendir(js["kutu_metni"], zaman=SITE_ZAMAN_ASIMI)
    hata = _js_hatasi(yazilan)
    if hata:
        raise SiteHatasi(hata)
    if _bosluksuz(yazilan) != _bosluksuz(metin):
        raise SiteHatasi("yazı kutusundaki metin gönderilen metinle uyuşmuyor; gönderilmedi")


def _giris_denetle(b, js, bekleme):
    """Giriş yapılmış mı? Sayfa yükleniyor görünüyorsa `bekleme` sn'ye kadar bekler."""
    bitis = time.monotonic() + bekleme
    while True:
        try:
            g = b.degerlendir(js["giris_var_mi"], zaman=SITE_ZAMAN_ASIMI)
        except cdp.CdpHatasi as h:
            if time.monotonic() >= bitis:
                raise SiteHatasi(str(h)) from h
            g = None
        if isinstance(g, dict) and g.get("giris"):
            return
        sebep = str(g.get("sebep", "")) if isinstance(g, dict) else ""
        belirsiz = g is None or "yükleniyor" in sebep or "hazır değil" in sebep
        if not belirsiz or time.monotonic() >= bitis:
            raise SiteHatasi("oturum açılmamış")
        time.sleep(0.5)


def _hedef_adres(site_id, kayit, sohbet_url, site_adresi):
    """Mesajın yazılacağı sayfa (yanlış sohbete gitmesin diye her gönderimde açıkça seçilir).

    - Bir site sohbetine yazılıyorsa (sohbet_url) ve adres bu sitenin: o sohbet. Adres başka bir sitenin
      sohbetiyse bu site yeni sohbet sayfasına gider; hiçbir sitenin değilse SiteHatasi (gönderme yok).
    - Ortak (yerel) sohbette bu site için kaydedilmiş sohbet adresi varsa: o adres (allowlist'ten geçmeli).
    - Aksi halde: sitenin yeni sohbet sayfası (pencere hangi sohbeti gösteriyorsa ona yazılmaz).
    """
    if sohbet_url:
        if _site_adresi_mi(site_id, sohbet_url):
            return sohbet_url
        if any(_site_adresi_mi(sid, sohbet_url) for sid in siteler.SITELER if sid != site_id):
            return kayit["yeni_sohbet_adresi"]
        raise SiteHatasi("sohbet adresi tanınan bir siteye ait değil; gönderilmedi")
    if site_adresi:
        if not _site_adresi_mi(site_id, site_adresi):
            raise SiteHatasi("kayıtlı sohbet adresi bu siteye ait değil; gönderilmedi")
        return site_adresi
    return kayit["yeni_sohbet_adresi"]


def _adres(b):
    """Sekmenin şu anki adresi (location.href)."""
    href = b.degerlendir("location.href", zaman=SITE_ZAMAN_ASIMI)
    return href if isinstance(href, str) else ""


def _hedefe_git(b, hedef):
    """Sayfa hedefte (alan adı + yol) değilse oraya gider ve vardığını doğrular; gidildiyse True.

    Gezinmeden sonra adres yeniden okunur; ADRES_DOGRULAMA_SURESI içinde hedefle uyuşmazsa (ör. site başka
    sayfaya yönlendirdi) SiteHatasi verilir ve hiçbir şey yazılmaz.
    """
    if _yol_anahtari(_adres(b)) == _yol_anahtari(hedef):
        return False
    b.git(hedef)
    bitis = time.monotonic() + ADRES_DOGRULAMA_SURESI
    while True:
        try:
            mevcut = _adres(b)
        except cdp.CdpHatasi:
            mevcut = None  # sayfa yüklenirken geçici hata
        if mevcut is not None and _yol_anahtari(mevcut) == _yol_anahtari(hedef):
            return True
        if time.monotonic() >= bitis:
            gorunen = _yol_anahtari(mevcut) if mevcut else "bilinmiyor"
            raise SiteHatasi(f"sayfa beklenen sohbete gitmedi (açılan: {gorunen}); gönderilmedi")
        time.sleep(0.3)


def siteye_gonder(site_id, metin, enter, sohbet_url=None, site_adresi=None, model=None):
    """Mesajı sitenin yazı kutusuna CDP ile ekler ve gönderir.

    sohbet_url: arayüzde açık olan site sohbeti; site_adresi: ortak sohbette bu site için kaydedilmiş adres.
    model: verilirse yazmadan önce sitenin model menüsünden seçilir (seçilemezse mevcut modelle gönderilir).
    Döner: {"taban": gönderme anındaki asistan mesajı sayısı, "yeni_pencere": bool}; model verildiyse ayrıca
    "model_uyarisi" (seçilemediyse Türkçe sebep, seçildiyse None). Sorunda SiteHatasi.
    """
    with _SITE_KILITLERI[site_id]:
        return _siteye_gonder(site_id, metin, enter, sohbet_url, site_adresi, model)


def _siteye_gonder(site_id, metin, enter, sohbet_url, site_adresi, model=None):
    kayit = siteler.site(site_id)
    js = kayit["js"]
    hedef = _hedef_adres(site_id, kayit, sohbet_url, site_adresi)  # pencereye dokunmadan önce
    yeni_pencere = False
    b = site_sayfasi(site_id)
    if not b:
        uyari = tarayici.pencere_ac(kayit["yeni_sohbet_adresi"])
        if uyari:
            raise SiteHatasi(uyari)
        yeni_pencere = True
        bitis = time.monotonic() + SAYFA_ACILMA_SURESI
        while not b and time.monotonic() < bitis:
            time.sleep(0.4)
            b = site_sayfasi(site_id)
        if not b:
            raise SiteHatasi("pencere açılamadı")
    try:
        _giris_denetle(b, js, 10 if yeni_pencere else 3)
        gezildi = _hedefe_git(b, hedef)
        _kutuyu_hazirla(b, js, 12 if (yeni_pencere or gezildi) else 4)
        model_uyarisi = None
        if model:  # model seçimi yazmadan önce; menü kapanınca yazı kutusu yeniden odaklansın
            model_uyarisi = _model_sec(b, site_id, model)
            _kutuyu_hazirla(b, js, 4)
        try:
            taban = sum(1 for x in _mesajlari_oku(b, js)["mesajlar"] if x.get("rol") == "asistan")
        except SiteHatasi:
            taban = 0  # mesajlar okunamıyorsa (seçici bozuk) yanıt yine de denenir
        try:  # arka plandaki pencerede de sayfa "odaklı" sayılsın
            b.komut("Emulation.setFocusEmulationEnabled", enabled=True)
        except cdp.CdpHatasi:
            pass
        if _yol_anahtari(_adres(b)) != _yol_anahtari(hedef):  # bekleme sırasında site başka sayfaya geçtiyse
            raise SiteHatasi("sayfa beklenen sohbette değil; gönderilmedi")
        _kutu_odakta_mi(b, js)  # metin yanlış öğeye (ör. başka bir forma) eklenmesin
        # Çok satırlı metinde satır aralarını da insertText ile ver: Enter tuşu göndermeyi tetikleyebilir.
        for i, satir in enumerate(metin.replace("\r\n", "\n").replace("\r", "\n").split("\n")):
            if i:
                b.yazi_ekle("\n")
            if satir:
                b.yazi_ekle(satir)
        _yazilani_dogrula(b, js, metin)  # kutudaki metin gönderilecek metinle aynı değilse gönderilmez
        if enter:
            time.sleep(0.4)
            sonuc = b.degerlendir(js["gonder"], zaman=15)
            hata = _js_hatasi(sonuc)
            if hata:
                raise SiteHatasi(hata)
            if isinstance(sonuc, dict) and not sonuc.get("tamam"):
                if sonuc.get("yontem") == "enter_gerekli":
                    b.tus("Enter", "Enter", 13, "\r")
                else:
                    raise SiteHatasi(sonuc.get("sebep") or "gönderilemedi")
        sonuc_ = {"taban": taban, "yeni_pencere": yeni_pencere}
        if model:
            sonuc_["model_uyarisi"] = model_uyarisi
        return sonuc_
    except cdp.CdpHatasi as h:
        raise SiteHatasi(str(h)) from h
    finally:
        b.kapat()


def gonder(veri, metin, site_idleri, program_idleri, enter, sohbet_url=None, site_adresleri=None, model_sec=None):
    """Mesajı seçili sitelere (CDP) ve masaüstü programlarına (pano + tuş) gönderir.

    site_adresleri: ortak sohbette site kimliği -> o sitenin bu sohbete ait adresi (yoksa yeni sohbet açılır).
    model_sec: {"site", "model"}; yalnızca o siteye gönderilirken yazmadan önce model seçilir. Seçilemezse
    mesaj mevcut modelle gider ve sorunlara "model seçilemedi: <sebep>" eklenir.

    Döner: (gönderilen adlar, sorunlar, yanıt bekleyen siteler, uygulama penceresi öne getirilsin mi)
    """
    gonderilen, sorunlar, bekleyen = [], [], []
    isler = {}
    havuz = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(site_idleri)))
    for sid in site_idleri:
        model = [model_sec["model"]] if model_sec and model_sec.get("site") == sid else []
        isler[sid] = havuz.submit(siteye_gonder, sid, metin, enter, sohbet_url, (site_adresleri or {}).get(sid), *model)
    program_sonuclari = []
    if program_idleri:
        acik = pc.pencereleri_listele()
        eski_pano, pano_yedeklendi = None, False
        try:
            eski_pano, pano_yedeklendi = pc.panoyu_oku(), True  # kullanıcının panosu gönderimden sonra geri verilir
        except pc.PencereHatasi as h:
            guvenlik.hata_yaz(f"Pano yedeklenemedi: {h}")
        try:
            pc.panoya_yaz(metin)
            for uid in program_idleri:
                u = uygulama_bul(veri, uid)
                if not u:
                    continue
                p = pc.pencere_bul_kesin(u, acik)
                if not p:
                    program_sonuclari.append((u["ad"], "program penceresi kesin olarak bulunamadı"
                                                       " (kapalı ya da birden fazla pencere açık)"))
                    continue
                try:
                    pc.yaziyi_gonder(p.hwnd, veri["konumlar"].get(uid, VARSAYILAN_KONUM), enter=enter)
                    program_sonuclari.append((u["ad"], None))
                except pc.PencereHatasi as h:
                    program_sonuclari.append((u["ad"], str(h)))
        finally:
            if pano_yedeklendi:
                try:
                    pc.panoyu_geri_yukle(eski_pano)
                except pc.PencereHatasi as h:
                    guvenlik.hata_yaz(f"Pano geri yüklenemedi: {h}")
    one_getir = bool(program_idleri)
    for sid, is_ in isler.items():
        ad = siteler.site(sid)["ad"]
        try:
            s = is_.result()
        except SiteHatasi as h:
            sorunlar.append({"ad": ad, "sebep": str(h)})
            continue
        except Exception as h:  # noqa: BLE001
            sorunlar.append({"ad": ad, "sebep": guvenlik.beklenmeyen_hata(f"gonder/{sid}", h)})
            continue
        gonderilen.append(ad)
        if s.get("model_uyarisi"):
            sorunlar.append({"ad": ad, "sebep": f"model seçilemedi: {s['model_uyarisi']}"})
        one_getir = one_getir or s["yeni_pencere"]
        if enter:
            bekleyen.append({"site": sid, "ad": ad, "renk": siteler.site(sid)["renk"], "taban": s["taban"]})
    havuz.shutdown(wait=False)
    for ad, sebep in program_sonuclari:
        if sebep:
            sorunlar.append({"ad": ad, "sebep": sebep})
        else:
            gonderilen.append(ad)
    return gonderilen, sorunlar, bekleyen, one_getir


def ogret(veri, uid):
    u = uygulama_bul(veri, uid)
    p = u and pc.pencere_bul(u, pc.pencereleri_listele())
    if not p:
        raise IsHatasi("Program açık değil. Önce açın.")
    pc.one_getir(p.hwnd)
    time.sleep(OGRETME_SURESI)
    konum = pc.konum_hesapla(pc.dikdortgen(p.hwnd), pc.fare_konumu())
    ben = kendi_pencere()
    if ben:
        pc.one_getir(ben.hwnd)
    if not (0 <= konum["oran_x"] <= 1 and konum["alttan"] > 0):
        raise IsHatasi("Fare programın penceresinin dışındaydı, tekrar deneyin.")
    return konum


def sohbete_ekle(veri, sohbet_id, metin, gonderilen, sorunlar, baglam=None):
    """Mesajı yerel sohbet geçmişine ekler; (sohbet kimliği, mesajın sırası) döndürür.

    baglam: Hafıza OS'tan eklenen bağlam kaydı; ham mesajdan ayrı alanda ("baglam") saklanır.
    """
    sohbet = next((s for s in veri["sohbetler"] if s["id"] == sohbet_id), None)
    if not sohbet:
        sohbet = {"id": sohbet_id or datetime.now().strftime("%Y%m%d%H%M%S%f"),
                  "baslik": metin.strip().splitlines()[0][:48], "zaman": datetime.now().isoformat(timespec="minutes"),
                  "mesajlar": []}
        veri["sohbetler"].insert(0, sohbet)
    sohbet["mesajlar"].append({"metin": metin, "zaman": datetime.now().strftime("%H:%M"),
                               "gonderilen": gonderilen, "sorunlar": sorunlar, "yanitlar": {}})
    if baglam:
        sohbet["mesajlar"][-1]["baglam"] = baglam
    sohbet["guncelleme"] = datetime.now().isoformat(timespec="minutes")
    return sohbet["id"], len(sohbet["mesajlar"]) - 1


def site_konumu(site_id):
    """Sitenin penceresinin şu anki adresi (location.href); pencere yoksa ya da okunamazsa None."""
    if site_id not in siteler.SITELER:
        return None
    b = site_sayfasi(site_id)
    if not b:
        return None
    try:
        return _adres(b) or None
    except cdp.CdpHatasi:
        return None
    finally:
        b.kapat()


def site_adresini_kaydet(sohbet, site_id, adres):
    """Ortak sohbette sitenin ilk yanıttan sonra oluşan sohbet adresini kaydeder; kaydedildiyse True.

    ChatGPT/Claude/Gemini ilk mesajdan sonra yeni sohbet sayfasından /c/<id>, /chat/<id>, /app/<id> adresine
    geçer; sonraki mesajlar bu adrese gider. Adres sitenin alan adına ait olmalı (allowlist) ve hâlâ yeni
    sohbet sayfası olmamalı. İlk kaydedilen adres korunur (pencere sonradan başka sohbete geçse de değişmez).
    """
    if site_id not in siteler.SITELER or not isinstance(adres, str) or not _site_adresi_mi(site_id, adres):
        return False
    if _yol_anahtari(adres) == _yol_anahtari(siteler.site(site_id)["yeni_sohbet_adresi"]):
        return False
    adresler = sohbet.get("site_adresleri")
    if not isinstance(adresler, dict):
        adresler = sohbet["site_adresleri"] = {}
    if adresler.get(site_id):
        return False
    adresler[site_id] = adres.split("#", 1)[0]
    return True


def yaniti_kaydet(veri, sohbet_id, sira, site_id, metin, site_adresi=None):
    """Bir site yanıtını yerel sohbetteki ilgili mesajın altına kaydeder.

    site_adresi (yanıt geldikten sonra okunan location.href) verilirse sitenin bu sohbete ait adresi de kaydedilir.
    """
    sohbet = next((s for s in veri["sohbetler"] if s["id"] == sohbet_id), None)
    if not sohbet or not isinstance(sira, int) or not 0 <= sira < len(sohbet["mesajlar"]):
        raise IsHatasi("Sohbet ya da mesaj bulunamadı.")
    if site_id not in siteler.SITELER:
        raise IsHatasi("Site bulunamadı.")
    sohbet["mesajlar"][sira].setdefault("yanitlar", {})[site_id] = str(metin or "")[:YANIT_KAYIT_SINIRI]
    if site_adresi:
        site_adresini_kaydet(sohbet, site_id, site_adresi)


def _soru_metni(veri, sohbet_id, sira):
    """Yerel sohbetteki mesajın ham metni (hafızaya eklenen bağlam hariç); bulunamazsa boş."""
    sohbet = next((s for s in veri["sohbetler"] if s["id"] == sohbet_id), None)
    if sohbet and isinstance(sira, int) and 0 <= sira < len(sohbet["mesajlar"]):
        return sohbet["mesajlar"][sira].get("metin", "")
    return ""


# ---------------------------------------------------------------- HTTP

SAHTE_SITE_DOSYALARI = {"/test/sahte-site.js": "sahte-site.js", "/test/sahte-site.css": "sahte-site.css"}
ICERIK = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
          ".ico": "image/x-icon", ".png": "image/png"}


class Isleyici(guvenlik.GuvenlikKarisimi, BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _beklenen_belirtec(self):
        return BELIRTEC

    def _guvenli(self):
        izinli = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        koken = self.headers.get("Origin")
        return self.headers.get("Host", "") in izinli and (not koken or koken in {f"http://{h}" for h in izinli})

    def _json(self, veri, kod=200):
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def _api_izni_yok(self, yol, govde_var=False):
        """/api/* isteği belirteçsiz ya da yanlış belirteçliyse 403 yanıtlar (True döner). /api/kimlik hariç."""
        if not yol.startswith("/api/") or yol == "/api/kimlik":
            return False
        if self._belirtec_dogru_mu():
            return False
        if govde_var:
            self._govdeyi_at()
        self._json({"hata": "Oturum belirteci eksik ya da geçersiz. Uygulamayı baslat.bat ile yeniden açın."}, 403)
        return True

    def do_GET(self):
        if not self._guvenli():
            return self._json({"hata": "İzin verilmeyen istek."}, 403)
        adres = urlparse(self.path)
        yol, sorgu = adres.path, parse_qs(adres.query)
        if self._api_izni_yok(yol):
            return
        try:
            if yol == "/api/kimlik":  # belirteçsiz: port meşgulse çalışan örneğin bizim uygulamamız olduğunu doğrulamak için
                return self._json(guvenlik.KIMLIK)
            if yol == "/api/hafiza-durum":
                return self._json(hafiza_kopru.durum())
            if yol == "/api/jev-durum":  # anahtar dosyası bulundu mu, model, son çağrı (anahtar değeri yok)
                return self._json(jev_durumu())
            if yol == "/api/durum":
                yenile_motor = sorgu.get("motor_yenile", [""])[0] in ("1", "true")
                return self._json({**durum(ayarlari_oku()), "motorlar": motor_durumlari(yenile_motor)})
            if yol == "/api/motor-modelleri":
                return self._json(motor_modelleri())
            if yol == "/api/modeller":
                return self._json(site_modelleri(sorgu.get("site", [""])[0], sorgu.get("yenile", [""])[0] in ("1", "true")))
            if yol == "/api/yonlendirme":
                return self._json(yonlendirme_durumu())
            if yol == "/api/site-sohbetler":
                return self._json(site_sohbetleri(yenile=sorgu.get("yenile", [""])[0] in ("1", "true")))
            if yol == "/api/yanit":
                taban = sorgu.get("taban", [""])[0]
                return self._json(site_yaniti(sorgu.get("site", [""])[0], int(taban) if taban.isdigit() else None))
            if yol == "/api/pencereler":
                ben = kendi_pencere()
                liste = [{"baslik": p.baslik, "exe": p.exe, "yol": p.yol} for p in pc.pencereleri_listele()
                         if not ben or p.hwnd != ben.hwnd]
                return self._json({"pencereler": liste})
        except IsHatasi as h:
            return self._json({"hata": str(h)}, 400)
        except Exception as h:  # noqa: BLE001
            return self._json({"hata": guvenlik.beklenmeyen_hata(yol, h)}, 500)
        test_kipi = os.environ.get("YZ_TEST") == "1"
        sahte_site = test_kipi and (yol == "/test/sahte-site.html" or yol.startswith("/test/c/"))
        if sahte_site:
            hedef = KOK / "testler" / "sahte-site.html"  # yalnızca testlerde: ChatGPT'yi taklit eden yerel sayfa
        elif test_kipi and yol in SAHTE_SITE_DOSYALARI:
            hedef = KOK / "testler" / SAHTE_SITE_DOSYALARI[yol]  # sahte sayfanın betiği/stili (CSP satır içine izin vermez)
            sahte_site = True
        else:
            hedef = (ARAYUZ / ("index.html" if yol == "/" else yol.lstrip("/"))).resolve()
        if (not sahte_site and ARAYUZ.resolve() not in hedef.parents) or not hedef.is_file():
            return self._json({"hata": "Sayfa bulunamadı."}, 404)
        govde = hedef.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ICERIK.get(hedef.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(govde)

    def do_POST(self):
        if not self._guvenli():
            self._govdeyi_at()
            return self._json({"hata": "İzin verilmeyen istek."}, 403)
        yol = urlparse(self.path).path
        if self._api_izni_yok(yol, govde_var=True):
            return
        try:
            g = self._govde()
        except guvenlik.IstekHatasi as h:
            return self._json({"hata": h.mesaj}, h.kod)
        try:
            if yol == "/api/sor":  # Tek Asistan: NDJSON akışı (ayar kilidi yalnızca kısa okuma/yazma anlarında alınır)
                return self._sor(g)
            if yol in KILITSIZ:  # ayar dosyasına dokunmayan, ağ/tarayıcı bekleyen istekler diğerlerini tutmasın
                return self._json(self._site_islemi(yol, g))
            # Yanıt kaydedilirken sitenin o anki sohbet adresi kilit dışında okunur (tarayıcı beklemesi kilidi tutmasın).
            site_adresi = site_konumu(str(g.get("site") or "")) if yol == "/api/yanit-kaydet" else None
            # Hassas bilgi için Jev'in ikinci görüşü de kilit dışında alınır (en çok jev.ZAMAN_ASIMI sn).
            jev_hassas = self._jev_hassas_on_tarama(g) if yol == "/api/gonder" else None
            with KILIT:
                veri = ayarlari_oku()
                sonuc = self._islem(yol, g, veri, site_adresi, jev_hassas)
                ayarlari_yaz(veri)
            return self._json(sonuc)
        except (IsHatasi, pc.PencereHatasi) as h:
            return self._json({"hata": str(h)}, 400)
        except Exception as h:  # noqa: BLE001
            return self._json({"hata": guvenlik.beklenmeyen_hata(yol, h)}, 500)

    def _sor(self, g):
        """/api/sor: doğrulama hatası akış başlamadan 400 olarak döner; akış başladıktan sonra hatalar "hata" olayıdır."""
        parametreler = sor_hazirla(g)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True
        akis = sor_akisi(parametreler)
        try:
            for olay in akis:
                self.wfile.write((json.dumps(olay, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
        except OSError:
            pass  # istemci koptu (sekme kapandı ya da Durdur): üreteç kapanınca yanıt iptal edilir ve kısmi metin saklanır
        except Exception as h:  # noqa: BLE001
            try:
                kisa = guvenlik.beklenmeyen_hata("/api/sor", h)
                self.wfile.write((json.dumps({"tur": "hata", "mesaj": kisa}, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
            except OSError:
                pass
        finally:
            akis.close()

    def _site_islemi(self, yol, g):
        if yol == "/api/site-ac":
            return site_ac(g.get("id", ""))
        if yol == "/api/site-sohbet-ac":
            return site_sohbet_ac(g.get("site", ""), g.get("url", ""))
        if yol == "/api/pencere-ac":  # ikinci örnek (baslat.bat yeniden açıldı) arayüz penceresini buradan ister
            uyari = tarayici.uygulama_penceresi_ac(f"http://127.0.0.1:{self.server.server_port}/#t={BELIRTEC}")
            if uyari:
                raise IsHatasi(uyari)
            return {"tamam": True}
        if yol == "/api/oneri":  # kural tabanlı sınıflandırma + canlı menüden model eşleştirme (ayar dosyasına dokunmaz)
            return oneri_olustur(g.get("metin"))
        if yol == "/api/yonlendirme-ac":
            return yonlendirme_dosyasini_ac()
        if yol == "/api/durdur":  # Tek Asistan: süren yanıtı iptal et
            return sor_durdur(g)
        if yol == "/api/yanit-puanla":  # ortak sohbette bütün site yanıtları bitince (ayar: jev_yanit_puanla)
            return yanit_puanla(g)
        raise IsHatasi("Bilinmeyen istek.")

    @staticmethod
    def _jev_hassas_on_tarama(g):
        """/api/gonder için: uyarı açık, onaysız, metin dolu ve yerel tarama temizse Jev'e sorar; yoksa None."""
        metin = g.get("metin")
        if not isinstance(metin, str) or not metin.strip() or g.get("onayli") is True:
            return None
        ayarlar = ayarlari_oku()["ayarlar"]
        if not ayarlar.get("hassas_uyari", True) or hassas.tara(metin.strip())["kategori"] != "yok":
            return None
        return jev_hassas_tara(metin.strip(), ayarlar)

    def _islem(self, yol, g, veri, site_adresi=None, jev_hassas=None):
        if yol == "/api/ayar":
            _ayar_dogrula(g, veri)
            for k in VARSAYILAN_AYARLAR:
                if k in g:
                    veri["ayarlar"][k] = g[k]
            if "secili" in g:
                veri["secili"].update(g["secili"])
            return {"tamam": True}
        if yol == "/api/ac":
            u = uygulama_bul(veri, g.get("id", ""))
            if not u:
                raise IsHatasi("Program bulunamadı.")
            p = pc.pencere_bul(u, pc.pencereleri_listele())
            if p:
                pc.one_getir(p.hwnd)
                return {"tamam": True, "zaten_acik": True}
            _programi_baslat(veri, u)
            return {"tamam": True}
        if yol == "/api/hepsini-ac":
            acilan = []
            acik = pc.pencereleri_listele()
            for sid, kayit in siteler.SITELER.items():
                if site_secili(veri, sid) and not site_hedefi(sid):
                    uyari = tarayici.pencere_ac(kayit["adres"])
                    if uyari:
                        raise IsHatasi(uyari)
                    acilan.append(kayit["ad"])
            for u in uygulamalar(veri):
                if program_secili(veri, u["id"]) and not pc.pencere_bul(u, acik):
                    _programi_baslat(veri, u)
                    acilan.append(u["ad"])
            return {"acilan": acilan}
        if yol == "/api/diz":
            return {"adet": hepsini_diz(veri)}
        if yol == "/api/gonder":
            metin = (g.get("metin") or "").strip()
            if not metin:
                raise IsHatasi("Mesaj boş.")
            site_idleri = [sid for sid in siteler.SITELER if site_secili(veri, sid)]
            program_idleri = [u["id"] for u in uygulamalar(veri) if program_secili(veri, u["id"])]
            if not site_idleri and not program_idleri:
                raise IsHatasi("En az bir hesap ya da program seçin.")
            model_sec = _model_sec_dogrula(g.get("model_sec"))
            if veri["ayarlar"].get("hassas_uyari", True) and g.get("onayli") is not True:
                tarama = hassas.tara(metin)  # gönderilmeden önce; onay gerekiyorsa hiçbir yere yazılmaz/gönderilmez
                if tarama["kategori"] != "yok":
                    return {"onay_gerekli": True, "kategori": tarama["kategori"], "aciklama": hassas.uyari_metni(tarama),
                            "eslesme_sayisi": tarama["eslesme_sayisi"], "kaynak": "kural"}
                if jev_hassas:  # yerel kurallar temiz, Jev (olasılık ≥ JEV_HASSAS_ESIGI) bir sır görüyor
                    return {"onay_gerekli": True, **jev_hassas}
            gonder_ek = {"model_sec": model_sec} if model_sec and model_sec["site"] in site_idleri else {}
            sohbet_url = (g.get("sohbet_url") or "").strip() or None
            site_adresleri = {}
            if not sohbet_url and g.get("sohbet"):  # ortak sohbet: her site o sohbete ait kendi adresine gider
                yerel = next((s for s in veri["sohbetler"] if s.get("id") == g["sohbet"]), None)
                if yerel and isinstance(yerel.get("site_adresleri"), dict):
                    site_adresleri = yerel["site_adresleri"]
            if not is_kilidi.acquire(blocking=False):
                raise IsHatasi("Önceki gönderme hâlâ sürüyor.")
            try:
                # Hafıza OS bağlamı (hafiza_kopru.py): boşsa hiçbir şey eklenmez; hata mesajı engellemez.
                gonderilecek, baglam = hafiza_kopru.baglam_ekle(metin) if veri["ayarlar"].get("hafiza_ekle", True) else (metin, None)
                gonderilen, sorunlar, bekleyen, one_getir = gonder(
                    veri, gonderilecek, site_idleri, program_idleri, veri["ayarlar"]["enter_bas"], sohbet_url, site_adresleri,
                    **gonder_ek)
            finally:
                is_kilidi.release()
            if one_getir:  # masaüstü programlarına tıklandı ya da yeni site penceresi açıldı: uygulamaya dön
                ben = kendi_pencere()
                if ben:
                    pc.one_getir(ben.hwnd)
            sid = sira = None
            if not sohbet_url:  # bir site sohbetine yazılıyorsa yerel geçmişe eklenmez
                sid, sira = sohbete_ekle(veri, g.get("sohbet"), metin, gonderilen, sorunlar, baglam)
            return {"gonderilen": gonderilen, "sorunlar": sorunlar, "sohbet": sid, "mesaj_sira": sira,
                    "yanit_bekleyen": bekleyen, "sohbetler": veri["sohbetler"], "baglam": baglam}
        if yol == "/api/yanit-kaydet":
            yaniti_kaydet(veri, g.get("sohbet"), g.get("mesaj_sira"), g.get("site"), g.get("metin"), site_adresi)
            if veri["ayarlar"].get("hafiza_aday", True):  # Hafıza OS gelen kutusuna aday kayıt (yalnızca ekleme)
                hafiza_kopru.aday_yaz(g.get("site"), _soru_metni(veri, g.get("sohbet"), g.get("mesaj_sira")), g.get("metin"))
            return {"tamam": True}
        if yol == "/api/ogret":
            if not is_kilidi.acquire(blocking=False):
                raise IsHatasi("Başka bir işlem sürüyor.")
            try:
                veri["konumlar"][g.get("id", "")] = ogret(veri, g.get("id", ""))
            finally:
                is_kilidi.release()
            return {"tamam": True}
        if yol == "/api/program-ekle":
            ad, exe, yol = (str(g.get(k) or "").strip() for k in ("ad", "exe", "yol"))
            if not ad or not exe:
                raise IsHatasi("Ad ve program gerekli.")
            if len(ad) > AD_EN_FAZLA:
                raise IsHatasi(f"Ad en çok {AD_EN_FAZLA} karakter olabilir.")
            if exe.lower() in TARAYICI_EXELERI:
                raise IsHatasi("Tarayıcılar program olarak eklenemez; ChatGPT, Gemini ve Claude web hesapları "
                               "zaten tarayıcı penceresi olarak desteklenir.")
            hata = _yol_hatasi(yol, exe)
            if hata:
                raise IsHatasi(hata)
            if not _program_acik_mi(yol):
                raise IsHatasi("Bu program şu an açık değil. Önce programı açın, sonra listeden seçip ekleyin.")
            yeni = {"id": f"ek-{int(time.time())}", "ad": ad, "exe": exe, "yol": yol, "renk": "#9b59b6"}
            if g.get("baslik_icerir"):
                yeni["baslik_icerir"] = str(g["baslik_icerir"]).strip()[:AD_EN_FAZLA]
            veri["ek_uygulamalar"].append(yeni)
            return {"tamam": True, "id": yeni["id"]}
        if yol == "/api/program-sil":
            veri["ek_uygulamalar"] = [u for u in veri["ek_uygulamalar"] if u["id"] != g.get("id")]
            veri["konumlar"].pop(g.get("id"), None)
            return {"tamam": True}
        if yol == "/api/sohbet-sil":
            veri["sohbetler"] = [s for s in veri["sohbetler"] if s["id"] != g.get("id")]
            return {"tamam": True, "sohbetler": veri["sohbetler"]}
        if yol == "/api/sohbet-adlandir":
            for s in veri["sohbetler"]:
                if s["id"] == g.get("id") and (g.get("baslik") or "").strip():
                    s["baslik"] = g["baslik"].strip()[:60]
            return {"tamam": True, "sohbetler": veri["sohbetler"]}
        raise IsHatasi("Bilinmeyen istek.")


def pencereyi_ac(adres):
    """Arayüzü kendi penceresinde (Edge uygulama modu) açar; Edge yoksa varsayılan tarayıcıda."""
    try:
        uyari = tarayici.baslat(adres)
    except tarayici.TarayiciHatasi as h:
        uyari = str(h)
    if uyari:
        print(uyari)
        guvenlik.hata_yaz(f"Tarayıcı açılamadı: {uyari}")


def calisan_ornek_mi(port):
    """Bu portta çalışan sunucu gerçekten Yapay Zeka Merkezi mi? (/api/kimlik, belirteçsiz uç)"""
    try:
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # yerel adres vekilden geçmesin
        with acici.open(f"http://127.0.0.1:{port}/api/kimlik", timeout=2) as y:
            if y.status != 200:
                return False
            yanit = json.loads(y.read(4096).decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return False
    return isinstance(yanit, dict) and yanit.get("uygulama") == guvenlik.KIMLIK["uygulama"]


def mevcut_ornegi_ac(port):
    """Port meşgulken: çalışan örnek bizimse arayüz penceresini ONA açtırır (POST /api/pencere-ac).

    Tarayıcının denetim borusu yalnızca çalışan örnektedir; bu süreç tarayıcıya erişemez. İstek, çalışan
    örneğin kullanıcı klasörüne yazdığı belirteçle yapılır. Başka bir program portu tutuyorsa, belirteç yoksa
    ya da istek reddedilirse hiçbir pencere açılmaz; Türkçe uyarı yazılır ve hata.log'a işlenir.
    Pencere açıldıysa True döner.
    """
    if not calisan_ornek_mi(port):
        mesaj = (f"{port} numaralı portu başka bir program kullanıyor ve bu bir Yapay Zeka Merkezi değil; "
                 "pencere açılmadı. O programı kapatın ya da YZ_MASAUSTU_PORT ile başka bir port seçin.")
        print(mesaj)
        guvenlik.hata_yaz(mesaj)
        return False
    belirtec = guvenlik.belirtec_oku()
    if not belirtec:
        mesaj = "Çalışan örneğin belirteç dosyası bulunamadı; pencere açılamadı. Uygulamayı kapatıp yeniden açın."
        print(mesaj)
        guvenlik.hata_yaz(mesaj)
        return False
    talep = urllib.request.Request(f"http://127.0.0.1:{port}/api/pencere-ac", b"{}", method="POST",
                                   headers={"Content-Type": "application/json", guvenlik.BELIRTEC_BASLIGI: belirtec})
    acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # yerel adres vekilden geçmesin
    try:
        with acici.open(talep, timeout=30) as y:
            y.read(4096)
    except urllib.error.HTTPError as h:
        try:
            sebep = json.loads(h.read(4096).decode("utf-8")).get("hata", "")
        except (ValueError, OSError, AttributeError):
            sebep = ""
        mesaj = f"Çalışan uygulama pencereyi açamadı (HTTP {h.code}). {sebep}".strip()
        print(mesaj)
        guvenlik.hata_yaz(mesaj)
        return False
    except (OSError, urllib.error.URLError) as h:
        mesaj = f"Çalışan uygulamaya ulaşılamadı: {h}"
        print(mesaj)
        guvenlik.hata_yaz(mesaj)
        return False
    return True


def eski_verileri_tasi():
    """Proje klasöründeki eski ayar dosyasını ve tarayıcı profilini bir kez veri klasörüne taşır.

    Yol bir ortam değişkeniyle (YZ_MASAUSTU_AYAR, YZ_TARAYICI_PROFILI) verilmişse dokunulmaz.
    """
    global AYAR_DOSYASI
    if not os.environ.get("YZ_MASAUSTU_AYAR"):
        AYAR_DOSYASI = guvenlik.eski_veriyi_tasi(ESKI_AYAR_DOSYASI, AYAR_DOSYASI)
    if not os.environ.get("YZ_TARAYICI_PROFILI"):
        tarayici.PROFIL = guvenlik.eski_veriyi_tasi(tarayici.ESKI_PROFIL, tarayici.PROFIL)


class Sunucu(ThreadingHTTPServer):
    # Windows'ta SO_REUSEADDR, aynı porta ikinci bir dinleyicinin bağlanmasına izin verir (port gaspı):
    # kapatıyoruz, böylece port meşgulse bağlanma hata verir.
    allow_reuse_address = False
    daemon_threads = True


def main():
    if sys.platform != "win32":
        print("Bu sürüm yalnızca Windows'ta çalışır.")
        return
    pc.dpi_farkindaligi_ac()
    try:
        sunucu = Sunucu(("127.0.0.1", PORT), Isleyici)
    except OSError:
        # Port meşgul: çalışan örnek bizimse arayüz penceresini yine uygulama kipinde aç.
        mevcut_ornegi_ac(PORT)
        return
    eski_verileri_tasi()
    guvenlik.belirtec_yaz(BELIRTEC)
    atexit.register(tarayici.kapat)  # uygulama kapanınca Edge'e Browser.close (boru kapanınca Edge zaten kapanır)
    adres = f"http://127.0.0.1:{PORT}/#t={BELIRTEC}"  # parça (#) sunucuya gitmez; arayüz okuyup adresten siler
    if "--pencere-acma" not in sys.argv:
        threading.Thread(target=pencereyi_ac, args=(adres,), daemon=True).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        tarayici.kapat()


if __name__ == "__main__":
    main()
