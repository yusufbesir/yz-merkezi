"""Windows pencerelerini bulma, dizme ve onlara yazı gönderme yardımcıları.

Yalnızca Python standart kütüphanesi (ctypes) kullanır.
"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
kernel32.OpenProcess.restype = wintypes.HANDLE
# 64 bit işaretçiler ctypes'ın varsayılan 32 bit int dönüşüne sığmaz; tipler açıkça verilmeli.
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.OpenClipboard.argtypes = [wintypes.HWND]

SW_RESTORE = 9
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
GW_OWNER = 4
DWMWA_CLOAKED = 14
SPI_GETWORKAREA = 0x0030
VK_CONTROL, VK_V, VK_RETURN = 0x11, 0x56, 0x0D
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004


class PencereHatasi(Exception):
    """Kullanıcıya Türkçe gösterilecek pencere işlemi hatası."""


def dpi_farkindaligi_ac():
    """Koordinatların ekran pikseliyle birebir olması için (yüksek DPI ekranlarda kaymayı önler)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()


def olcek():
    """Ekran ölçek çarpanı (%125 ekran için 1.25). Tarayıcı pencere sınırları mantıksal (DIP) pikseldir."""
    try:
        return max(1.0, user32.GetDpiForSystem() / 96)
    except (AttributeError, OSError):
        return 1.0


class Pencere:
    def __init__(self, hwnd, pid, baslik, yol):
        self.hwnd, self.pid, self.baslik, self.yol = hwnd, pid, baslik, yol

    @property
    def exe(self):
        return Path(self.yol).name

    def __repr__(self):
        return f"Pencere({self.baslik!r}, {self.exe})"


def _islem_yolu(pid):
    tutamac = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not tutamac:
        return ""
    try:
        boyut = wintypes.DWORD(1024)
        tampon = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(tutamac, 0, tampon, ctypes.byref(boyut)):
            return tampon.value
        return ""
    finally:
        kernel32.CloseHandle(tutamac)


def _gizli_mi(hwnd):
    gizli = wintypes.DWORD()
    dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(gizli), ctypes.sizeof(gizli))
    return bool(gizli.value)


def pencereleri_listele():
    """Görünür, başlıklı, ana uygulama pencerelerini döndürür."""
    sonuc = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def geri_cagir(hwnd, _):
        if (user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0
                and not user32.GetWindow(hwnd, GW_OWNER) and not _gizli_mi(hwnd)):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            tampon = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, tampon, 512)
            sonuc.append(Pencere(hwnd, pid.value, tampon.value, _islem_yolu(pid.value)))
        return True

    user32.EnumWindows(geri_cagir, 0)
    return sonuc


def eslesir_mi(uygulama, pencere):
    """Pencere bu uygulamaya mı ait? exe adı, isteğe bağlı yol ve başlık parçasıyla karşılaştırılır."""
    if pencere.exe.lower() != uygulama["exe"].lower():
        return False
    if uygulama.get("yol_icerir") and uygulama["yol_icerir"].lower() not in pencere.yol.lower():
        return False
    if uygulama.get("baslik_icerir") and uygulama["baslik_icerir"].lower() not in pencere.baslik.lower():
        return False
    return True


def dikdortgen(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def _normal_alan(hwnd):
    # Simge durumundaki pencerelerin gerçek boyutu için kayıtlı "normal" konumu kullan.
    class YERLESIM(ctypes.Structure):
        _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT), ("showCmd", wintypes.UINT),
                    ("ptMin", wintypes.POINT), ("ptMax", wintypes.POINT), ("rc", wintypes.RECT)]
    y = YERLESIM(length=ctypes.sizeof(YERLESIM))
    user32.GetWindowPlacement(hwnd, ctypes.byref(y))
    return (y.rc.right - y.rc.left) * (y.rc.bottom - y.rc.top)


def pencere_bul(uygulama, pencereler):
    adaylar = [p for p in pencereler if eslesir_mi(uygulama, p)]
    return max(adaylar, key=lambda p: _normal_alan(p.hwnd), default=None)


def uygulamayi_ac(uygulama):
    if uygulama.get("appid"):
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{uygulama['appid']}"])
    elif uygulama.get("yol"):
        yol = os.path.expandvars(uygulama["yol"])
        if not Path(yol).exists():
            raise PencereHatasi(f"{uygulama['ad']} bulunamadı: {yol}")
        os.startfile(yol)
    else:
        raise PencereHatasi(f"{uygulama['ad']} için başlatma yolu tanımlı değil. Programı elle açın.")


def calisma_alani():
    r = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0)
    return r.left, r.top, r.right, r.bottom


def yan_yana_konumlar(alan, adet, alt_bosluk):
    """Çalışma alanını alt tarafta alt_bosluk bırakarak adet kadar eşit sütuna böler."""
    sol, ust, sag, alt = alan
    genislik = (sag - sol) // adet
    yukseklik = (alt - alt_bosluk) - ust
    return [(sol + i * genislik, ust, genislik, yukseklik) for i in range(adet)]


def yerlestir(hwnd, x, y, genislik, yukseklik):
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, None, x, y, genislik, yukseklik, SWP_NOZORDER | SWP_SHOWWINDOW)


def one_getir(hwnd):
    """Pencereyi öne getirir; Windows'un odak kilidini aşmak için giriş kuyruklarını geçici olarak bağlar."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    on_plan = user32.GetForegroundWindow()
    on_is = user32.GetWindowThreadProcessId(on_plan, None)
    benim = kernel32.GetCurrentThreadId()
    bagli = on_is and on_is != benim and user32.AttachThreadInput(benim, on_is, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if bagli:
            user32.AttachThreadInput(benim, on_is, False)
    time.sleep(0.3)
    return user32.GetForegroundWindow() == hwnd


def giris_noktasi(dortgen, konum):
    """Yazı kutusunun ekran koordinatı. konum: {'oran_x': 0-1 arası, 'alttan': pencere altından piksel}."""
    sol, _, sag, alt = dortgen
    return sol + int((sag - sol) * konum["oran_x"]), alt - int(konum["alttan"])


def konum_hesapla(dortgen, nokta):
    """giris_noktasi'nın tersi: fare noktasından pencereye göre konum çıkarır."""
    sol, _, sag, alt = dortgen
    return {"oran_x": round((nokta[0] - sol) / max(1, sag - sol), 3), "alttan": alt - nokta[1]}


def panoya_yaz(metin):
    """Yazıyı Windows panosuna koyar (Ctrl+V ile yapıştırılabilsin diye)."""
    GMEM_MOVEABLE, CF_UNICODETEXT = 0x0002, 13
    veri = metin.encode("utf-16-le") + b"\x00\x00"
    for _ in range(10):  # başka bir program panoyu tutuyorsa kısa süre bekle
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise PencereHatasi("pano başka bir program tarafından kilitli")
    try:
        user32.EmptyClipboard()
        tutamac = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(veri))
        adres = kernel32.GlobalLock(tutamac)
        ctypes.memmove(adres, veri, len(veri))
        kernel32.GlobalUnlock(tutamac)
        user32.SetClipboardData(CF_UNICODETEXT, tutamac)
    finally:
        user32.CloseClipboard()


def fare_konumu():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def tikla(x, y):
    user32.SetCursorPos(x, y)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def tus(vk, ctrl=False):
    if ctrl:
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    if ctrl:
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def yaziyi_gonder(hwnd, konum, enter=True):
    """Panodaki yazıyı pencerenin yazı kutusuna yapıştırır, istenirse Enter'a basar.

    Pencere öne gelmezse hiçbir tuşa basılmaz; böylece yazı yanlış programa gitmez.
    """
    if not one_getir(hwnd):
        raise PencereHatasi("pencere öne getirilemedi, yazı gönderilmedi")
    eski_fare = fare_konumu()
    tikla(*giris_noktasi(dikdortgen(hwnd), konum))
    time.sleep(0.25)
    if user32.GetForegroundWindow() != hwnd:
        raise PencereHatasi("tıklamadan sonra başka bir pencere öne geçti, yazı gönderilmedi")
    tus(VK_V, ctrl=True)
    time.sleep(0.3)
    if enter:
        tus(VK_RETURN)
        time.sleep(0.15)
    user32.SetCursorPos(*eski_fare)
