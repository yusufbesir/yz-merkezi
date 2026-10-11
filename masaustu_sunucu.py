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
import concurrent.futures
import json
import os
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cdp
import pencereler as pc
import siteler
import tarayici

KOK = Path(__file__).resolve().parent
ARAYUZ = KOK / "arayuz-masaustu"
UYGULAMA_DOSYASI = KOK / "uygulamalar.json"
AYAR_DOSYASI = Path(os.environ.get("YZ_MASAUSTU_AYAR", KOK / "masaustu-ayarlar.json"))
PORT = int(os.environ.get("YZ_MASAUSTU_PORT", "8766"))
PENCERE_BASLIGI = "Yapay Zeka Merkezi"
VARSAYILAN_KONUM = {"oran_x": 0.5, "alttan": 90}
OGRETME_SURESI = 4
SOHBET_ONBELLEK_SURESI = 15   # sn: site sohbet listesi bu süre içinde yeniden sorgulanmaz
SITE_ZAMAN_ASIMI = 8          # sn: bir sitenin tek sorgusu için üst sınır
SOHBET_YUKLEME_SURESI = 10    # sn: sohbet adresine gidince mesajların yüklenmesi için üst sınır
SAYFA_ACILMA_SURESI = 15      # sn: yeni açılan site penceresinin görünmesi için üst sınır
YANIT_KAYIT_SINIRI = 100000   # yerel geçmişe kaydedilecek tek yanıtın en uzun boyu
VARSAYILAN_AYARLAR = {
    "tema": "sistem", "yazi_boyutu": "orta", "enter_bas": True, "kutuyu_temizle": True,
    "yerlesim": "sol", "ad": "Yusuf",
}

KILIT = threading.Lock()
KILITSIZ = {"/api/site-ac", "/api/site-sohbet-ac"}
is_kilidi = threading.Lock()  # aynı anda tek gönderme/öğretme işlemi


class IsHatasi(Exception):
    pass


class SiteHatasi(Exception):
    """Bir siteye gönderme/okuma sırasında oluşan, kullanıcıya Türkçe gösterilecek sorun."""


# ---------------------------------------------------------------- ayarlar ve veri

def ayarlari_oku():
    try:
        veri = json.loads(AYAR_DOSYASI.read_text("utf-8"))
    except (OSError, ValueError):
        veri = {}
    veri.setdefault("ayarlar", {})
    for k, v in VARSAYILAN_AYARLAR.items():
        veri["ayarlar"].setdefault(k, v)
    veri.setdefault("konumlar", {})
    veri.setdefault("ek_uygulamalar", [])
    veri.setdefault("secili", {})
    veri.setdefault("sohbetler", [])
    return veri


def ayarlari_yaz(veri):
    gecici = AYAR_DOSYASI.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2), "utf-8")
    os.replace(gecici, AYAR_DOSYASI)


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
    """Sitenin açık sekmesine bağlantı (cdp.Baglanti); sekme yoksa None. Çağıran kapatmalıdır."""
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
            "sohbetler": veri["sohbetler"]}


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
            cdp.pencere_sinirlari(tarayici.CDP_PORT, h["id"], x / olcek, y / olcek, g / olcek, yk / olcek)
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


def siteye_gonder(site_id, metin, enter, sohbet_url=None, yeni_sohbet=False):
    """Mesajı sitenin yazı kutusuna CDP ile ekler ve gönderir.

    Döner: {"taban": gönderme anındaki asistan mesajı sayısı, "yeni_pencere": bool}. Sorunda SiteHatasi.
    """
    with _SITE_KILITLERI[site_id]:
        return _siteye_gonder(site_id, metin, enter, sohbet_url, yeni_sohbet)


def _siteye_gonder(site_id, metin, enter, sohbet_url, yeni_sohbet):
    kayit = siteler.site(site_id)
    js = kayit["js"]
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
        # Hedef sayfa: istenen sohbet; yoksa yeni ortak sohbette yeni sohbet sayfası; yoksa pencere ne gösteriyorsa o.
        gidilecek = None
        if sohbet_url and _site_adresi_mi(site_id, sohbet_url):
            gidilecek = sohbet_url
        elif yeni_sohbet and not yeni_pencere:
            gidilecek = kayit["yeni_sohbet_adresi"]
        if gidilecek:
            mevcut = b.degerlendir("location.href", zaman=SITE_ZAMAN_ASIMI)
            if gidilecek == sohbet_url:
                ayni = _ayni_adres(mevcut, gidilecek)
            else:
                ayni = _yol_anahtari(mevcut) == _yol_anahtari(gidilecek)
            if not ayni:
                b.git(gidilecek)
        _kutuyu_hazirla(b, js, 12 if (yeni_pencere or gidilecek) else 4)
        try:
            taban = sum(1 for x in _mesajlari_oku(b, js)["mesajlar"] if x.get("rol") == "asistan")
        except SiteHatasi:
            taban = 0  # mesajlar okunamıyorsa (seçici bozuk) yanıt yine de denenir
        try:  # arka plandaki pencerede de sayfa "odaklı" sayılsın
            b.komut("Emulation.setFocusEmulationEnabled", enabled=True)
        except cdp.CdpHatasi:
            pass
        # Çok satırlı metinde satır aralarını da insertText ile ver: Enter tuşu göndermeyi tetikleyebilir.
        for i, satir in enumerate(metin.replace("\r\n", "\n").replace("\r", "\n").split("\n")):
            if i:
                b.yazi_ekle("\n")
            if satir:
                b.yazi_ekle(satir)
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


def gonder(veri, metin, site_idleri, program_idleri, enter, sohbet_url=None, yeni_sohbet=False):
    """Mesajı seçili sitelere (CDP) ve masaüstü programlarına (pano + tuş) gönderir.

    Döner: (gönderilen adlar, sorunlar, yanıt bekleyen siteler, uygulama penceresi öne getirilsin mi)
    """
    gonderilen, sorunlar, bekleyen = [], [], []
    isler = {}
    havuz = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(site_idleri)))
    for sid in site_idleri:
        isler[sid] = havuz.submit(siteye_gonder, sid, metin, enter, sohbet_url, yeni_sohbet)
    program_sonuclari = []
    if program_idleri:
        acik = pc.pencereleri_listele()
        pc.panoya_yaz(metin)
        for uid in program_idleri:
            u = uygulama_bul(veri, uid)
            if not u:
                continue
            p = pc.pencere_bul(u, acik)
            if not p:
                program_sonuclari.append((u["ad"], "açık değil"))
                continue
            try:
                pc.yaziyi_gonder(p.hwnd, veri["konumlar"].get(uid, VARSAYILAN_KONUM), enter=enter)
                program_sonuclari.append((u["ad"], None))
            except pc.PencereHatasi as h:
                program_sonuclari.append((u["ad"], str(h)))
    one_getir = bool(program_idleri)
    for sid, is_ in isler.items():
        ad = siteler.site(sid)["ad"]
        try:
            s = is_.result()
        except SiteHatasi as h:
            sorunlar.append({"ad": ad, "sebep": str(h)})
            continue
        except Exception as h:  # noqa: BLE001
            sorunlar.append({"ad": ad, "sebep": f"beklenmeyen hata: {h}"})
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


def yaniti_kaydet(veri, sohbet_id, sira, site_id, metin):
    """Bir site yanıtını yerel sohbetteki ilgili mesajın altına kaydeder."""
    sohbet = next((s for s in veri["sohbetler"] if s["id"] == sohbet_id), None)
    if not sohbet or not isinstance(sira, int) or not 0 <= sira < len(sohbet["mesajlar"]):
        raise IsHatasi("Sohbet ya da mesaj bulunamadı.")
    if site_id not in siteler.SITELER:
        raise IsHatasi("Site bulunamadı.")
    sohbet["mesajlar"][sira].setdefault("yanitlar", {})[site_id] = str(metin or "")[:YANIT_KAYIT_SINIRI]


# ---------------------------------------------------------------- HTTP

ICERIK = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}


class Isleyici(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

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

    def _govde(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n)) if n else {}
        except ValueError:
            return {}

    def do_GET(self):
        if not self._guvenli():
            return self._json({"hata": "İzin verilmeyen istek."}, 403)
        adres = urlparse(self.path)
        yol, sorgu = adres.path, parse_qs(adres.query)
        try:
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
            return self._json({"hata": f"Beklenmeyen hata: {h}"}, 500)
        sahte_site = os.environ.get("YZ_TEST") == "1" and (yol == "/test/sahte-site.html" or yol.startswith("/test/c/"))
        if sahte_site:
            hedef = KOK / "testler" / "sahte-site.html"  # yalnızca testlerde: ChatGPT'yi taklit eden yerel sayfa
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
            return self._json({"hata": "İzin verilmeyen istek."}, 403)
        yol = urlparse(self.path).path
        g = self._govde()
        try:
            if yol in KILITSIZ:  # ayar dosyasına dokunmayan, ağ/tarayıcı bekleyen istekler diğerlerini tutmasın
                return self._json(self._site_islemi(yol, g))
            with KILIT:
                veri = ayarlari_oku()
                sonuc = self._islem(yol, g, veri)
                ayarlari_yaz(veri)
            return self._json(sonuc)
        except (IsHatasi, pc.PencereHatasi) as h:
            return self._json({"hata": str(h)}, 400)
        except Exception as h:  # noqa: BLE001
            return self._json({"hata": f"Beklenmeyen hata: {h}"}, 500)

    def _site_islemi(self, yol, g):
        if yol == "/api/site-ac":
            return site_ac(g.get("id", ""))
        if yol == "/api/site-sohbet-ac":
            return site_sohbet_ac(g.get("site", ""), g.get("url", ""))
        raise IsHatasi("Bilinmeyen istek.")

    def _islem(self, yol, g, veri):
        if yol == "/api/ayar":
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
            pc.uygulamayi_ac(u)
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
                    pc.uygulamayi_ac(u)
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
            yeni_sohbet = not g.get("sohbet") and not sohbet_url
            if not is_kilidi.acquire(blocking=False):
                raise IsHatasi("Önceki gönderme hâlâ sürüyor.")
            try:
                gonderilen, sorunlar, bekleyen, one_getir = gonder(
                    veri, metin, site_idleri, program_idleri, veri["ayarlar"]["enter_bas"], sohbet_url, yeni_sohbet)
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
            yaniti_kaydet(veri, g.get("sohbet"), g.get("mesaj_sira"), g.get("site"), g.get("metin"))
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
            ad = (g.get("ad") or "").strip()
            exe = (g.get("exe") or "").strip()
            if not ad or not exe:
                raise IsHatasi("Ad ve program gerekli.")
            yeni = {"id": f"ek-{int(time.time())}", "ad": ad, "exe": exe, "renk": "#9b59b6"}
            if g.get("baslik_icerir"):
                yeni["baslik_icerir"] = g["baslik_icerir"].strip()
            elif g.get("yol"):
                yeni["yol"] = g["yol"]
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
    uyari = tarayici.baslat(adres)
    if uyari:
        print(uyari)


def main():
    if sys.platform != "win32":
        print("Bu sürüm yalnızca Windows'ta çalışır.")
        return
    pc.dpi_farkindaligi_ac()
    try:
        sunucu = ThreadingHTTPServer(("127.0.0.1", PORT), Isleyici)
    except OSError:
        # Zaten çalışıyor: arayüz penceresini yine uygulama kipinde aç (çalışan Edge sürecine devredilir).
        uyari = tarayici.uygulama_penceresi_ac(f"http://127.0.0.1:{PORT}")
        if uyari:
            print(uyari)
        return
    sunucu.daemon_threads = True
    adres = f"http://127.0.0.1:{PORT}"
    if "--pencere-acma" not in sys.argv:
        threading.Thread(target=pencereyi_ac, args=(adres,), daemon=True).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
