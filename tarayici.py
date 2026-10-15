"""Edge'i CDP BORUSUYLA (ağ portu olmadan) başlatır ve pencere/sekme denetimini sağlar.

Yalnızca uygulamaya ait ayrı bir profil kullanılır (varsayılan `%LOCALAPPDATA%\\YZMerkezi\\tarayici-profili`,
`YZ_TARAYICI_PROFILI` ile değiştirilebilir); kullanıcının kendi Edge profiline dokunulmaz.

Denetim bağlantısı bu süreçteki tek bir `cdp.BoruBaglantisi` nesnesidir: başka süreçler (ikinci bir uygulama
örneği dahil) tarayıcıya bağlanamaz. İkinci örnek, pencere açmayı çalışan örnekten `POST /api/pencere-ac`
ile ister (bkz. masaustu_sunucu.mevcut_ornegi_ac). Boru kapanınca (uygulama kapanınca) Edge de kapanır.

Komut satırı (Win32_Process ile her yerel süreçten okunabilir) oturum belirteci TAŞIMAZ: uygulama penceresi tek
kullanımlık açılış koduyla (`/ac/<kod>`) açılır; `#t=`/`?t=` biçimli adresler uygulama kipinde reddedilir.
"""
import re
import subprocess
import threading
import webbrowser
from pathlib import Path

import cdp
import guvenlik

KOK = Path(__file__).resolve().parent
EDGE_YOLLARI = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
ESKI_PROFIL = KOK / ".tarayici-profili"  # eski sürümlerin profil yeri (ilk açılışta taşınır)
PROFIL = guvenlik.veri_yolu("YZ_TARAYICI_PROFILI", "tarayici-profili")
HAZIR_BEKLEME = 15  # saniye
# Arka plandaki site pencerelerinde sayfa zamanlayıcıları kısılmasın (CDP ile gönderme beklemesin).
EDGE_BAYRAKLARI = ["--no-first-run", "--disable-features=TranslateUI,msEdgeSidebar",
                   "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                   "--disable-backgrounding-occluded-windows"]
PROFIL_ACIK_MESAJI = "Bu profille açık bir Edge penceresi var; önce onu kapatın, sonra uygulamayı yeniden açın."

_kilit = threading.RLock()
_boru = None  # bizim başlattığımız tarayıcıya giden cdp.BoruBaglantisi


class TarayiciHatasi(cdp.CdpHatasi):
    """Tarayıcı başlatılamadığında kullanıcıya gösterilecek Türkçe hata."""


_BELIRTECLI_ADRES = re.compile(r"[#?&]t=", re.IGNORECASE)


def _adres_denetle(url):
    """Uygulama penceresi adresinde belirteç parametresi olamaz (komut satırına sızmasın)."""
    if _BELIRTECLI_ADRES.search(str(url)):
        raise TarayiciHatasi("Adreste oturum belirteci var; güvenlik nedeniyle pencere açılmadı.")


def edge_komutu(edge, ilk_url, uygulama=True):
    """Denetim borulu ilk Edge sürecinin komut listesi (cdp.boruyla_baslat ekler: --remote-debugging-pipe)."""
    return [edge, f"--user-data-dir={PROFIL}", *EDGE_BAYRAKLARI, "--window-size=1100,760",
            f"--app={ilk_url}" if uygulama else ilk_url]


def devret_komutu(edge, url):
    """Çalışan Edge'e uygulama penceresi açtıran (adresi devredip çıkan) sürecin komut listesi."""
    return [edge, f"--app={url}", f"--user-data-dir={PROFIL}"]


def _edge_yolu():
    return next((y for y in EDGE_YOLLARI if Path(y).exists()), None)


def baglanti():
    """Çalışan tarayıcıya giden canlı boru bağlantısı; yoksa None."""
    with _kilit:
        return _boru if _boru is not None and _boru.canli_mi() else None


def calisiyor_mu():
    """Bu süreçte başlatılmış Edge'in denetim borusu canlı mı?"""
    return baglanti() is not None


def _gerekli_baglanti():
    b = baglanti()
    if b is None:
        raise cdp.CdpHatasi("Tarayıcı çalışmıyor.")
    return b


def _boruyla_baslat(edge, ilk_url, uygulama):
    """Edge'i boruyla başlatır ve hazır olmasını bekler; sorun varsa TarayiciHatasi."""
    global _boru
    if _boru is not None:  # kapanmış eski bağlantının yazma ucu açık kalmasın
        _boru.kapat(bekleme=0)
        _boru = None
    b = cdp.boruyla_baslat(edge_komutu(edge, ilk_url, uygulama))
    try:
        b.komut("Browser.getVersion", zaman=HAZIR_BEKLEME)
    except cdp.CdpHatasi as h:
        kapandi = b.kapali  # boru EOF: süreç açılışı aynı profildeki eski Edge'e devredip çıktı
        b.kapat()
        if kapandi:
            raise TarayiciHatasi(PROFIL_ACIK_MESAJI) from h
        if b.surec is not None and b.surec.poll() is None:
            b.surec.kill()
        raise TarayiciHatasi(f"Edge açıldı ama {HAZIR_BEKLEME} saniyede denetim bağlantısı hazır olmadı: {h}") from h
    _boru = b


def baslat(ilk_url, uygulama=True):
    """Edge'i boruyla başlatır; ilk pencere `uygulama` ise uygulama kipinde (adres çubuksuz) açılır.

    Edge zaten çalışıyorsa adres yeni pencerede açılır. Edge yoksa adres varsayılan tarayıcıda açılır ve
    Türkçe uyarı döner; sorunsuzsa None döner. Aynı profille açık eski bir Edge varsa TarayiciHatasi.
    """
    if uygulama:
        _adres_denetle(ilk_url)
    with _kilit:
        if calisiyor_mu():
            return _uygulama_kipinde_devret(ilk_url) if uygulama else pencere_ac(ilk_url)
        edge = _edge_yolu()
        if not edge:
            webbrowser.open(ilk_url)
            return "Microsoft Edge bulunamadı; adres varsayılan tarayıcıda açıldı (pencere denetimi çalışmaz)."
        _boruyla_baslat(edge, ilk_url, uygulama)
        return None


def _uygulama_kipinde_devret(url):
    """Çalışan Edge'e (aynı profil) uygulama kipinde pencere açtırır: yeni süreç adresi ona devredip çıkar.

    Bu süreç denetim bayrağı taşımaz; denetim yalnızca ilk süreçteki boru üzerindendir.
    """
    edge = _edge_yolu()
    if not edge:
        return "Microsoft Edge bulunamadı."
    try:
        _adres_denetle(url)
        subprocess.Popen(devret_komutu(edge, url), close_fds=True)
    except TarayiciHatasi as h:
        return str(h)
    except OSError as h:
        return f"Pencere açılamadı: {h}"
    return None


def pencere_ac(url):
    """Edge çalışıyorsa yeni üst düzey (normal) pencere açar, çalışmıyorsa Edge'i başlatır.

    Sorun varsa Türkçe uyarı metni, sorunsuzsa None döner.
    """
    with _kilit:
        b = baglanti()
        if b is None:
            try:
                return baslat(url, uygulama=False)
            except TarayiciHatasi as h:
                return str(h)
    try:
        cdp.yeni_pencere(b, url)
    except cdp.CdpHatasi as h:
        return f"Yeni pencere açılamadı: {h}"
    return None


def uygulama_penceresi_ac(url):
    """Adresi uygulama kipinde (adres çubuksuz) açar: Edge çalışıyorsa ona devredilir, yoksa boruyla başlatılır.

    Sorun varsa Türkçe uyarı metni, sorunsuzsa None döner.
    """
    try:
        return baslat(url, uygulama=True)
    except TarayiciHatasi as h:
        return str(h)


def hedef(parca):
    """Adresi "alanadi[:port][/yol-oneki]" parçasıyla eşleşen ilk sekmenin kaydı ({"id", "url", ...}); yoksa None."""
    b = baglanti()
    if b is None:
        return None
    try:
        return cdp.pencere_bul(b, parca)
    except cdp.CdpHatasi:
        return None


def sayfa(parca):
    """Adresi parçayla eşleşen sekmeye bağlı `cdp.Oturum`; yoksa None. Çağıran kapatmalıdır."""
    b = baglanti()
    if b is None:
        return None
    try:
        h = cdp.pencere_bul(b, parca)
        return cdp.sekmeye_baglan(b, h["id"]) if h else None
    except cdp.CdpHatasi:
        return None


def pencere_sinirlari(hedef_id, sol, ust, genislik, yukseklik):
    """Sekmenin penceresini konuma/boyuta getirir (bkz. cdp.pencere_sinirlari); tarayıcı yoksa CdpHatasi."""
    return cdp.pencere_sinirlari(_gerekli_baglanti(), hedef_id, sol, ust, genislik, yukseklik)


def sekmeyi_kapat(hedef_id):
    """Sekmeyi kapatır (Target.closeTarget); tarayıcı yoksa CdpHatasi."""
    _gerekli_baglanti().komut("Target.closeTarget", targetId=hedef_id)


def kapat():
    """Bizim başlattığımız Edge'e Browser.close gönderir ve boruyu kapatır (hata vermez)."""
    global _boru
    with _kilit:
        b, _boru = _boru, None
    if b is not None:
        b.kapat(tarayiciyi_kapat=True)
