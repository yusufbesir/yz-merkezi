#!/usr/bin/env python3
"""Yapay Zeka Merkezi (masaüstü sürümü) arka ucu.

Birincil yol: ChatGPT, Gemini ve Claude WEB siteleri, kendi Edge profilimizde (tarayici.py) açılır ve
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
import pencereler as pc
import siteler
import tarayici

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
AD_EN_FAZLA = 40
# Web hesapları (CDP) varken bu tarayıcılar masaüstü programı olarak eklenemez.
TARAYICI_EXELERI = {"msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "opera.exe"}

# İstek belirteci: açılışta bir kez üretilir, yalnızca bellekte (ve kullanıcıya özel klasördeki belirtec dosyasında) durur.
BELIRTEC = guvenlik.yeni_belirtec()
AYAR_UYARISI = None  # ayar dosyası bozuk çıkıp yedeklenirse arayüze gösterilecek Türkçe uyarı

KILIT = threading.Lock()
KILITSIZ = {"/api/site-ac", "/api/site-sohbet-ac", "/api/pencere-ac"}
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
        veri["ayarlar"].setdefault(k, v)
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


def siteye_gonder(site_id, metin, enter, sohbet_url=None, site_adresi=None):
    """Mesajı sitenin yazı kutusuna CDP ile ekler ve gönderir.

    sohbet_url: arayüzde açık olan site sohbeti; site_adresi: ortak sohbette bu site için kaydedilmiş adres.
    Döner: {"taban": gönderme anındaki asistan mesajı sayısı, "yeni_pencere": bool}. Sorunda SiteHatasi.
    """
    with _SITE_KILITLERI[site_id]:
        return _siteye_gonder(site_id, metin, enter, sohbet_url, site_adresi)


def _siteye_gonder(site_id, metin, enter, sohbet_url, site_adresi):
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
        return {"taban": taban, "yeni_pencere": yeni_pencere}
    except cdp.CdpHatasi as h:
        raise SiteHatasi(str(h)) from h
    finally:
        b.kapat()


def gonder(veri, metin, site_idleri, program_idleri, enter, sohbet_url=None, site_adresleri=None):
    """Mesajı seçili sitelere (CDP) ve masaüstü programlarına (pano + tuş) gönderir.

    site_adresleri: ortak sohbette site kimliği -> o sitenin bu sohbete ait adresi (yoksa yeni sohbet açılır).

    Döner: (gönderilen adlar, sorunlar, yanıt bekleyen siteler, uygulama penceresi öne getirilsin mi)
    """
    gonderilen, sorunlar, bekleyen = [], [], []
    isler = {}
    havuz = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(site_idleri)))
    for sid in site_idleri:
        isler[sid] = havuz.submit(siteye_gonder, sid, metin, enter, sohbet_url, (site_adresleri or {}).get(sid))
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


def sohbete_ekle(veri, sohbet_id, metin, gonderilen, sorunlar):
    """Mesajı yerel sohbet geçmişine ekler; (sohbet kimliği, mesajın sırası) döndürür."""
    sohbet = next((s for s in veri["sohbetler"] if s["id"] == sohbet_id), None)
    if not sohbet:
        sohbet = {"id": sohbet_id or datetime.now().strftime("%Y%m%d%H%M%S%f"),
                  "baslik": metin.strip().splitlines()[0][:48], "zaman": datetime.now().isoformat(timespec="minutes"),
                  "mesajlar": []}
        veri["sohbetler"].insert(0, sohbet)
    sohbet["mesajlar"].append({"metin": metin, "zaman": datetime.now().strftime("%H:%M"),
                               "gonderilen": gonderilen, "sorunlar": sorunlar, "yanitlar": {}})
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
            if yol == "/api/durum":
                return self._json(durum(ayarlari_oku()))
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
            if yol in KILITSIZ:  # ayar dosyasına dokunmayan, ağ/tarayıcı bekleyen istekler diğerlerini tutmasın
                return self._json(self._site_islemi(yol, g))
            # Yanıt kaydedilirken sitenin o anki sohbet adresi kilit dışında okunur (tarayıcı beklemesi kilidi tutmasın).
            site_adresi = site_konumu(str(g.get("site") or "")) if yol == "/api/yanit-kaydet" else None
            with KILIT:
                veri = ayarlari_oku()
                sonuc = self._islem(yol, g, veri, site_adresi)
                ayarlari_yaz(veri)
            return self._json(sonuc)
        except (IsHatasi, pc.PencereHatasi) as h:
            return self._json({"hata": str(h)}, 400)
        except Exception as h:  # noqa: BLE001
            return self._json({"hata": guvenlik.beklenmeyen_hata(yol, h)}, 500)

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
        raise IsHatasi("Bilinmeyen istek.")

    def _islem(self, yol, g, veri, site_adresi=None):
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
            sohbet_url = (g.get("sohbet_url") or "").strip() or None
            site_adresleri = {}
            if not sohbet_url and g.get("sohbet"):  # ortak sohbet: her site o sohbete ait kendi adresine gider
                yerel = next((s for s in veri["sohbetler"] if s.get("id") == g["sohbet"]), None)
                if yerel and isinstance(yerel.get("site_adresleri"), dict):
                    site_adresleri = yerel["site_adresleri"]
            if not is_kilidi.acquire(blocking=False):
                raise IsHatasi("Önceki gönderme hâlâ sürüyor.")
            try:
                gonderilen, sorunlar, bekleyen, one_getir = gonder(
                    veri, metin, site_idleri, program_idleri, veri["ayarlar"]["enter_bas"], sohbet_url, site_adresleri)
            finally:
                is_kilidi.release()
            if one_getir:  # masaüstü programlarına tıklandı ya da yeni site penceresi açıldı: uygulamaya dön
                ben = kendi_pencere()
                if ben:
                    pc.one_getir(ben.hwnd)
            sid = sira = None
            if not sohbet_url:  # bir site sohbetine yazılıyorsa yerel geçmişe eklenmez
                sid, sira = sohbete_ekle(veri, g.get("sohbet"), metin, gonderilen, sorunlar)
            return {"gonderilen": gonderilen, "sorunlar": sorunlar, "sohbet": sid, "mesaj_sira": sira,
                    "yanit_bekleyen": bekleyen, "sohbetler": veri["sohbetler"]}
        if yol == "/api/yanit-kaydet":
            yaniti_kaydet(veri, g.get("sohbet"), g.get("mesaj_sira"), g.get("site"), g.get("metin"), site_adresi)
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
