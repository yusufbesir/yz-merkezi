"""İki yerel sunucunun (masaustu_sunucu.py ve sunucu.py) ortak güvenlik yardımcıları.

- Tüm yanıtlara güvenlik başlıkları (X-Frame-Options, CSP, ...) eklenir.
- /api/* istekleri açılışta üretilen rastgele belirteçle (X-YZ-Token başlığı) doğrulanır. Masaüstü sürümünde arayüz
  belirteci hiç görmez: tek kullanımlık, kısa ömürlü bir açılış koduyla (/ac/<kod>) HttpOnly; SameSite=Strict
  çerezine alınır (AcilisKodlari, oturum_cerezi); çerezli istekte Sec-Fetch-Site varsa same-origin olmalıdır.
- İstek gövdesi 1 MB ile ve 10 sn okuma süresiyle sınırlanır; JSON nesnesi olmayan gövde reddedilir.
- Beklenmeyen hatalarda istemciye yalnızca kısa bir kod gider, ayrıntı hata.log dosyasına yazılır.
- Ayar dosyası bozulursa silinmez, zaman damgalı yedeğe taşınır; yazma fsync + os.replace ile yapılır.

Yalnızca standart kütüphane.
"""
import base64
import hmac
import threading
import time
from http.cookies import CookieError, SimpleCookie
import json
import os
import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path

import surum

BELIRTEC_BASLIGI = "X-YZ-Token"
CEREZ_ON_EKI = "yz_oturum"   # çerez adı porta özgüdür: yz_oturum_<port> (çerezler port ayırmaz)
ACILIS_KODU_SURESI = 30       # sn: Edge'e verilen açılış kodunun geçerlilik süresi (tek kullanımlık)
GOVDE_SINIRI = 1_000_000      # bayt: bir istek gövdesinin en çok boyu
GOVDE_ZAMAN_ASIMI = 10        # sn: gövdenin okunması için üst sınır
HATA_LOGU_SINIRI = 1_000_000  # bayt: hata.log bu boyu aşınca yedeğe alınır
KIMLIK = surum.kimlik()  # /api/kimlik yanıtı (surum.py: uygulama adı ve semver sürüm)

GUVENLIK_BASLIKLARI = (
    ("X-Frame-Options", "DENY"),
    ("Content-Security-Policy",
     "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
)


class IstekHatasi(Exception):
    """İstemciye Türkçe `mesaj` ve HTTP `kod` ile dönecek istek sorunu."""

    def __init__(self, kod, mesaj):
        super().__init__(mesaj)
        self.kod, self.mesaj = kod, mesaj


# ---------------------------------------------------------------- dosya yolları

def veri_klasoru():
    """Uygulama veri klasörü: %LOCALAPPDATA%\\YZMerkezi (YZ_VERI_KLASORU ile değiştirilebilir).

    Belirteç, hata günlüğü, ayar dosyaları ve tarayıcı profili varsayılan olarak buradadır (depoda değil).
    """
    ozel = os.environ.get("YZ_VERI_KLASORU")
    if ozel:
        return Path(ozel)
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YZMerkezi"


def veri_yolu(ortam_degiskeni, ad):
    """Ayar dosyası/profil yolu: ortam değişkeni varsa o, yoksa veri klasöründeki `ad`."""
    ozel = os.environ.get(ortam_degiskeni)
    return Path(ozel) if ozel else veri_klasoru() / ad


def _profil_kullanimda_mi(klasor):
    """Chromium profili açık bir tarayıcı tarafından kullanılıyor mu? (çalışırken `lockfile` paylaşımsız açıktır)"""
    kilit = Path(klasor) / "lockfile"
    if not kilit.exists():
        return False
    try:
        with open(kilit, "ab"):
            pass
    except OSError:
        return True
    return False


def eski_veriyi_tasi(eski, yeni):
    """Proje klasöründeki eski ayar dosyasını/profil klasörünü yeni konuma BİR KEZ taşır; kullanılacak yolu döndürür.

    - Eski yoksa ya da yeni konumda zaten veri varsa hiçbir şey yapılmaz (yeni yol döner).
    - Önce `<yeni>.tasiniyor` adına kopyalanır, sonra yerine konur, en son eski silinir (shutil.move'un güvenli
      sırası): yarıda kesilen taşıma veriyi kaybettirmez. Kopyalama başarısızsa eski yol döner (bu açılışta
      eski yerde çalışılır, sonraki açılışta yeniden denenir).
    - Profil açık bir Edge tarafından kullanılıyorsa taşınmaz (eski yol döner).
    """
    eski, yeni = Path(eski), Path(yeni)
    if not eski.exists() or yeni.exists():
        return yeni
    if eski.is_dir() and _profil_kullanimda_mi(eski):
        hata_yaz(f"Eski veri taşınmadı, kullanımda: {eski.name}")
        return eski
    gecici = yeni.with_name(yeni.name + ".tasiniyor")
    try:
        yeni.parent.mkdir(parents=True, exist_ok=True)
        if gecici.is_dir():
            shutil.rmtree(gecici)
        elif gecici.exists():
            gecici.unlink()
        if eski.is_dir():
            shutil.copytree(eski, gecici, symlinks=True)
        else:
            shutil.copy2(eski, gecici)
        os.replace(gecici, yeni)
    except OSError as h:
        hata_yaz(f"Eski veri taşınamadı ({eski.name}): {h}")
        if gecici.is_dir():
            shutil.rmtree(gecici, ignore_errors=True)
        elif gecici.exists():
            try:
                gecici.unlink()
            except OSError:
                pass
        return eski
    try:
        if eski.is_dir():
            shutil.rmtree(eski)
        else:
            eski.unlink()
    except OSError as h:
        hata_yaz(f"Eski veri yeni yere kopyalandı ama eski kopya silinemedi ({eski.name}): {h}")
    hata_yaz(f"Eski veri taşındı: {eski.name} -> {yeni}")
    return yeni


def belirtec_dosyasi():
    return veri_klasoru() / "belirtec"


def hata_dosyasi():
    return veri_klasoru() / "hata.log"


# ---------------------------------------------------------------- belirteç

def yeni_belirtec():
    return secrets.token_urlsafe(32)


def belirtec_yaz(belirtec):
    """Çalışan örneğin belirtecini, ikinci örneğin okuyabilmesi için kullanıcı klasörüne yazar (hata verirse False)."""
    try:
        yol = belirtec_dosyasi()
        yol.parent.mkdir(parents=True, exist_ok=True)
        akis = os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(akis, "w", encoding="utf-8") as f:
            f.write(belirtec)
        return True
    except OSError as h:
        hata_yaz(f"Belirteç dosyası yazılamadı: {h}")
        return False


def belirtec_oku():
    try:
        return belirtec_dosyasi().read_text("utf-8").strip()
    except OSError:
        return ""


def belirtec_gecerli_mi(gelen, beklenen):
    """Sabit zamanlı karşılaştırma; boş belirteç hiçbir zaman geçerli sayılmaz."""
    if not gelen or not beklenen:
        return False
    return hmac.compare_digest(str(gelen).encode("utf-8"), str(beklenen).encode("utf-8"))


def cerez_adi(port):
    """Bu sunucunun çerez adı: yz_oturum_<port>. Çerezler portu ayırmaz (127.0.0.1'deki her port aynı çerez
    kavanozunu görür); porta özgü ad, başka bir portta çalışan örneğin ya da başka bir uygulamanın çerezinin
    bu sunucuda geçerli sayılmasını önler."""
    return f"{CEREZ_ON_EKI}_{int(port)}"


def oturum_cerezi(belirtec, port):
    """Set-Cookie değeri: belirteç JS'e görünmez (HttpOnly), başka siteden gelen isteklere eklenmez (SameSite=Strict)."""
    return f"{cerez_adi(port)}={belirtec}; HttpOnly; SameSite=Strict; Path=/"


def cerezden_belirtec(cerez_basligi, port):
    """Cookie başlığındaki bu porta ait oturum belirteci (yoksa, başka portun çerezi ise ya da okunamazsa "")."""
    if not cerez_basligi:
        return ""
    try:
        c = SimpleCookie()
        c.load(str(cerez_basligi))
    except CookieError:
        return ""
    m = c.get(cerez_adi(port))
    return m.value if m is not None else ""


class AcilisKodlari:
    """Tek kullanımlık, kısa ömürlü açılış kodları (Edge komut satırında belirteç yerine bu kod geçer).

    Kod yalnızca bellekte durur; `tuket` ilk başarılı çağrıda kodu siler. Süresi dolan kodlar her çağrıda atılır.
    """

    def __init__(self, sure=ACILIS_KODU_SURESI, saat=time.monotonic):
        self.sure, self._saat = sure, saat
        self._kodlar = {}
        self._kilit = threading.Lock()

    def _temizle(self, simdi):
        for k in [k for k, bitis in self._kodlar.items() if bitis <= simdi]:
            del self._kodlar[k]

    def uret(self, sure=None):
        """Yeni kod (geçerlilik: `sure` sn, verilmezse sınıfın süresi)."""
        kod = secrets.token_urlsafe(24)
        with self._kilit:
            simdi = self._saat()
            self._temizle(simdi)
            self._kodlar[kod] = simdi + (self.sure if sure is None else sure)
        return kod

    def tuket(self, kod):
        """Kod geçerliyse siler ve True döner (ikinci kullanım, süresi dolmuş ya da bilinmeyen kod: False)."""
        if not isinstance(kod, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", kod):
            return False
        with self._kilit:
            simdi = self._saat()
            self._temizle(simdi)
            for k in list(self._kodlar):
                if hmac.compare_digest(k.encode("ascii"), kod.encode("ascii")):
                    del self._kodlar[k]
                    return True
        return False


# ---------------------------------------------------------------- hata günlüğü

def hata_yaz(satir):
    """hata.log dosyasına tek satır ekler (günlük yazılamıyorsa sessizce vazgeçer)."""
    try:
        yol = hata_dosyasi()
        yol.parent.mkdir(parents=True, exist_ok=True)
        if yol.exists() and yol.stat().st_size > HATA_LOGU_SINIRI:
            os.replace(yol, yol.with_suffix(".log.eski"))
        with open(yol, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {satir}\n")
    except OSError:
        pass


def beklenmeyen_hata(yol, istisna):
    """Beklenmeyen istisnayı günlüğe yazar (istek içeriği olmadan: tür, metin, yol, zaman).

    İstemciye gösterilecek Türkçe, ayrıntısız metni döndürür.
    """
    kod = secrets.token_hex(4)
    metin = re.sub(r"\s+", " ", str(istisna))[:500]
    hata_yaz(f"kod={kod} yol={yol} tur={type(istisna).__name__} metin={metin}")
    return f"Beklenmeyen bir sorun oluştu (kod: {kod})"


# ---------------------------------------------------------------- ayar dosyası

def bozuk_dosyayi_tasi(yol):
    """Okunamayan ayar dosyasını `<ad>.bozuk-YYYYmmddHHMMSS.json` adıyla yanına taşır; yeni yolu döndürür."""
    yol = Path(yol)
    yedek = yol.with_name(f"{yol.stem}.bozuk-{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
    sayac = 1
    while yedek.exists():  # aynı saniyede ikinci bozulma
        yedek = yol.with_name(f"{yol.stem}.bozuk-{datetime.now().strftime('%Y%m%d%H%M%S')}-{sayac}.json")
        sayac += 1
    try:
        os.replace(yol, yedek)
    except OSError as h:
        hata_yaz(f"Bozuk ayar dosyası taşınamadı ({yol.name}): {h}")
        return None
    hata_yaz(f"Ayar dosyası bozuktu, yedeğe taşındı: {yedek.name}")
    return yedek


def json_oku(yol):
    """Ayar dosyasını sözlük olarak okur. Dosya yoksa/açılamıyorsa ({}, None); bozuksa yedeğe taşıyıp ({}, uyarı) döner."""
    try:
        metin = Path(yol).read_text("utf-8")
    except FileNotFoundError:
        return {}, None
    except OSError as h:
        hata_yaz(f"Ayar dosyası okunamadı ({Path(yol).name}): {h}")
        return {}, None
    try:
        veri = json.loads(metin)
        if not isinstance(veri, dict):
            raise ValueError("kök nesne değil")
        return veri, None
    except ValueError:
        yedek = bozuk_dosyayi_tasi(yol)
        uyari = (f"Ayar dosyası okunamadı; bozuk dosya '{yedek.name}' adıyla saklandı ve varsayılan ayarlarla "
                 "devam edildi." if yedek else "Ayar dosyası okunamadı; varsayılan ayarlarla devam edildi.")
        return {}, uyari


def json_yaz(yol, veri):
    """Yaz → boşalt → diske işle → yerine koy: yarım yazılmış dosya asıl dosyayı bozamaz."""
    yol = Path(yol)
    gecici = yol.with_suffix(".tmp")
    with open(gecici, "w", encoding="utf-8") as f:
        f.write(json.dumps(veri, ensure_ascii=False, indent=2))
        f.flush()
        os.fsync(f.fileno())
    os.replace(gecici, yol)


# ---------------------------------------------------------------- DPAPI (API anahtarlarını diskte şifreleme)

DPAPI_ONEKI = "dpapi:"


def _dpapi_cagir(veri, sifrele):
    """Windows DPAPI (kullanıcı kapsamı). Windows dışında ya da hata olursa ValueError (düz metne DÜŞMEZ)."""
    if os.name != "nt":
        raise ValueError("DPAPI yalnızca Windows'ta kullanılabilir; anahtar düz metin olarak saklanmadı.")
    import ctypes
    from ctypes import wintypes

    class VeriBlogu(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    islev = crypt32.CryptProtectData if sifrele else crypt32.CryptUnprotectData
    islev.argtypes = [ctypes.POINTER(VeriBlogu), wintypes.LPCWSTR if sifrele else ctypes.POINTER(wintypes.LPWSTR),
                      ctypes.POINTER(VeriBlogu), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                      ctypes.POINTER(VeriBlogu)]
    islev.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    tampon = ctypes.create_string_buffer(veri, len(veri))
    girdi = VeriBlogu(len(veri), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char)))
    cikti = VeriBlogu()
    if not islev(ctypes.byref(girdi), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(cikti)):
        raise ValueError("DPAPI işlemi başarısız oldu (anahtar bu kullanıcı/bilgisayar için çözülemiyor olabilir).")
    try:
        return ctypes.string_at(cikti.pbData, cikti.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(cikti.pbData, ctypes.c_void_p))


def dpapi_sifrele(metin):
    """Metni DPAPI ile şifreler: "dpapi:" + base64. Başarısızsa ValueError (düz metin döndürmez)."""
    return DPAPI_ONEKI + base64.b64encode(_dpapi_cagir(metin.encode("utf-8"), True)).decode("ascii")


def dpapi_sifreli_mi(deger):
    return isinstance(deger, str) and deger.startswith(DPAPI_ONEKI)


def dpapi_coz(deger):
    """"dpapi:" değerini çözer; önek yoksa ya da çözülemezse ValueError."""
    if not dpapi_sifreli_mi(deger):
        raise ValueError("Değer DPAPI ile şifreli değil.")
    try:
        ham = base64.b64decode(deger[len(DPAPI_ONEKI):], validate=True)
    except ValueError:
        raise ValueError("DPAPI değeri geçersiz.") from None
    return _dpapi_cagir(ham, False).decode("utf-8")


# ---------------------------------------------------------------- HTTP karışımı

class GuvenlikKarisimi:
    """BaseHTTPRequestHandler alt sınıflarına eklenir: güvenlik başlıkları, belirteç ve gövde sınırı.

    Alt sınıf `_beklenen_belirtec()` ile geçerli belirteci verir ve `_json(veri, kod)` yöntemini tanımlar.
    """
    server_version = "YZMerkezi"
    sys_version = ""

    def _ortak_basliklar(self):
        """Her yanıta (JSON, dosya, 403/404, akış, send_error) eklenen güvenlik başlıkları."""
        for ad, deger in GUVENLIK_BASLIKLARI:
            self.send_header(ad, deger)

    def end_headers(self):
        self._ortak_basliklar()
        super().end_headers()

    def _beklenen_belirtec(self):
        raise NotImplementedError

    def _cerez_kabul_edilir_mi(self):
        """Alt sınıf çerezle kimlik doğrulamayı açar (CSRF denetimiyle). Varsayılan: çerez kabul edilmez."""
        return False

    def _belirtec_dogru_mu(self):
        """Belirteç X-YZ-Token başlığında YA DA (alt sınıf izin veriyorsa) yz_oturum_<port> çerezinde; sabit zamanlı karşılaştırma."""
        beklenen = self._beklenen_belirtec()
        if belirtec_gecerli_mi(self.headers.get(BELIRTEC_BASLIGI, ""), beklenen):
            return True
        cerez = cerezden_belirtec(self.headers.get("Cookie", ""), self.server.server_port)
        return bool(cerez) and self._cerez_kabul_edilir_mi() and belirtec_gecerli_mi(cerez, beklenen)

    def _govdeyi_at(self):
        """Reddedilen (403) POST'un gövdesini okuyup atar: okunmamış veriyle bağlantı kapanırsa istemci
        (özellikle Windows'ta) yanıtı alamadan bağlantı sıfırlandı hatası görür."""
        ham = (self.headers.get("Content-Length") or "").strip()
        if not ham.isdigit() or not 0 < int(ham) <= GOVDE_SINIRI:
            return
        try:
            self.connection.settimeout(2)
            self.rfile.read(int(ham))
            self.connection.settimeout(None)
        except OSError:
            self.close_connection = True

    def _govde(self):
        """İstek gövdesini JSON nesnesi olarak okur; sorunda IstekHatasi (413/400/408) atar."""
        ham = self.headers.get("Content-Length")
        ham = (ham or "0").strip()
        if not re.fullmatch(r"-?[0-9]{1,20}", ham):
            raise IstekHatasi(400, "Geçersiz içerik uzunluğu.")
        uzunluk = int(ham)
        if not 0 <= uzunluk <= GOVDE_SINIRI:
            self.close_connection = True
            raise IstekHatasi(413, "İstek çok büyük.")
        if uzunluk == 0:
            return {}
        self.connection.settimeout(GOVDE_ZAMAN_ASIMI)
        try:
            ham_govde = self.rfile.read(uzunluk)
        except (TimeoutError, OSError):
            self.close_connection = True
            raise IstekHatasi(408, "İstek zamanında alınamadı.") from None
        finally:
            try:
                self.connection.settimeout(None)
            except OSError:
                pass
        try:
            veri = json.loads(ham_govde.decode("utf-8"))
        except ValueError:
            raise IstekHatasi(400, "İstek gövdesi geçerli JSON değil.") from None
        if not isinstance(veri, dict):
            raise IstekHatasi(400, "İstek gövdesi bir JSON nesnesi olmalı.")
        return veri
