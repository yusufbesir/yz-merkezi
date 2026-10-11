"""Edge'i uzaktan hata ayıklama (CDP) bağlantısıyla başlatır ve pencere/sekme denetimini sağlar.

Yalnızca projeye ait ayrı bir profil (.tarayici-profili) kullanılır; kullanıcının kendi Edge profiline dokunulmaz.
"""
import os
import subprocess
import time
import webbrowser
from pathlib import Path

import cdp

KOK = Path(__file__).resolve().parent
EDGE_YOLLARI = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
PROFIL = Path(os.environ.get("YZ_TARAYICI_PROFILI", KOK / ".tarayici-profili"))
CDP_PORT = int(os.environ.get("YZ_CDP_PORT", "9230"))
HAZIR_BEKLEME = 15  # saniye


def calisiyor_mu():
    """Bu profille açılmış Edge denetim bağlantısına yanıt veriyor mu?"""
    try:
        cdp.tarayici_ws(CDP_PORT)
        return True
    except cdp.CdpHatasi:
        return False


def _hazir_olana_kadar_bekle():
    """Denetim bağlantısı yanıt verene dek (en çok HAZIR_BEKLEME sn) bekler."""
    bitis = time.monotonic() + HAZIR_BEKLEME
    while time.monotonic() < bitis:
        if calisiyor_mu():
            return True
        time.sleep(0.2)
    return False


def baslat(ilk_url):
    """Edge'i uygulama modunda açar. Sorun varsa Türkçe uyarı metni, sorunsuzsa None döndürür."""
    if calisiyor_mu():
        return pencere_ac(ilk_url)
    edge = next((y for y in EDGE_YOLLARI if Path(y).exists()), None)
    if not edge:
        webbrowser.open(ilk_url)
        return "Microsoft Edge bulunamadı; adres varsayılan tarayıcıda açıldı (pencere denetimi çalışmaz)."
    # Arka plandaki site pencerelerinde sayfa zamanlayıcıları kısılmasın (CDP ile gönderme beklemesin).
    subprocess.Popen([edge, f"--remote-debugging-port={CDP_PORT}", f"--user-data-dir={PROFIL}",
                      "--no-first-run", "--disable-features=TranslateUI,msEdgeSidebar",
                      "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                      "--disable-backgrounding-occluded-windows",
                      "--window-size=1100,760", f"--app={ilk_url}"])
    if not _hazir_olana_kadar_bekle():
        return (f"Edge açıldı ama {HAZIR_BEKLEME} saniyede denetim bağlantısı (port {CDP_PORT}) hazır olmadı. "
                "Aynı profille açık eski bir Edge penceresi varsa kapatıp yeniden deneyin.")
    return None


def pencere_ac(url):
    """Edge çalışıyorsa yeni üst düzey pencere açar, çalışmıyorsa Edge'i başlatır."""
    if not calisiyor_mu():
        return baslat(url)
    try:
        cdp.yeni_pencere(CDP_PORT, url)
    except cdp.CdpHatasi as h:
        return f"Yeni pencere açılamadı: {h}"
    return None


def uygulama_penceresi_ac(url):
    """Adresi uygulama kipinde (adres çubuksuz) açar; aynı profille çalışan Edge'e devredilir.

    Port zaten meşgulken (uygulama başka bir süreçte çalışıyorken) arayüz penceresini yeniden açmak
    için kullanılır. Edge hiç çalışmıyorsa denetim portuyla birlikte başlatılır.
    """
    edge = next((y for y in EDGE_YOLLARI if Path(y).exists()), None)
    if not edge:
        webbrowser.open(url)
        return "Microsoft Edge bulunamadı; adres varsayılan tarayıcıda açıldı (pencere denetimi çalışmaz)."
    komut = [edge, f"--app={url}", f"--user-data-dir={PROFIL}"]
    if not calisiyor_mu():
        komut.insert(1, f"--remote-debugging-port={CDP_PORT}")
    subprocess.Popen(komut)
    return None


def hedef(parca):
    """Adresi "alanadi[:port][/yol-oneki]" parçasıyla eşleşen ilk sekmenin DevTools kaydı; yoksa None."""
    try:
        return cdp.pencere_bul(CDP_PORT, parca)
    except cdp.CdpHatasi:
        return None


def sayfa(parca):
    """Adresi "alanadi[:port][/yol-oneki]" parçasıyla eşleşen sekmenin bağlantısını (cdp.Baglanti) döndürür; yoksa None."""
    try:
        hedef = cdp.pencere_bul(CDP_PORT, parca)
        return cdp.Baglanti(hedef["webSocketDebuggerUrl"]) if hedef else None
    except cdp.CdpHatasi:
        return None
