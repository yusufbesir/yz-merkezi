"""İki yerel sunucunun (masaustu_sunucu.py ve sunucu.py) ortak güvenlik yardımcıları.

- Tüm yanıtlara güvenlik başlıkları (X-Frame-Options, CSP, ...) eklenir.
- /api/* istekleri açılışta üretilen rastgele belirteçle (X-YZ-Token) doğrulanır.
- İstek gövdesi 1 MB ile ve 10 sn okuma süresiyle sınırlanır; JSON nesnesi olmayan gövde reddedilir.
- Beklenmeyen hatalarda istemciye yalnızca kısa bir kod gider, ayrıntı hata.log dosyasına yazılır.
- Ayar dosyası bozulursa silinmez, zaman damgalı yedeğe taşınır; yazma fsync + os.replace ile yapılır.

Yalnızca standart kütüphane.
"""
import hmac
import json
import os
import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path

BELIRTEC_BASLIGI = "X-YZ-Token"
GOVDE_SINIRI = 1_000_000      # bayt: bir istek gövdesinin en çok boyu
GOVDE_ZAMAN_ASIMI = 10        # sn: gövdenin okunması için üst sınır
HATA_LOGU_SINIRI = 1_000_000  # bayt: hata.log bu boyu aşınca yedeğe alınır
KIMLIK = {"uygulama": "yz-merkezi", "surum": "1.0"}

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

    def _belirtec_dogru_mu(self):
        return belirtec_gecerli_mi(self.headers.get(BELIRTEC_BASLIGI, ""), self._beklenen_belirtec())

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
