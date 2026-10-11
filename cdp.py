"""Chrome DevTools Protocol (CDP) için minimal istemci: Edge'i WebSocket üzerinden denetler.

Yalnızca Python standart kütüphanesi kullanır (socket, json, base64, struct, urllib).
WebSocket çerçeve kodlama/çözme saf fonksiyonlardır (cerceve_olustur, cerceve_coz); bağlantı sınıfı
(Baglanti) bunların üstüne el sıkışma, parçalı mesaj birleştirme, ping/pong ve komut-yanıt eşlemesi koyar.
"""
import base64
import collections
import hashlib
import json
import os
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

import siteler

WS_ANAHTAR_EKI = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"  # RFC 6455 sabiti
OP_DEVAM, OP_METIN, OP_IKILI, OP_KAPAT, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA
EN_BUYUK_YUK = 256 * 1024 * 1024  # bozuk bir uzunluk bilgisi belleği doldurmasın
HTTP_ZAMANI = 5

# Sistem vekil (proxy) ayarı yerel adrese gitmeyi bozmasın.
_acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class CdpHatasi(Exception):
    """Kullanıcıya Türkçe gösterilecek tarayıcı denetimi hatası."""


# ---------------------------------------------------------------- WebSocket çerçeveleri

Cerceve = collections.namedtuple("Cerceve", "son opkod yuk maskeli uzunluk")


def _maskele(yuk, maske):
    """Yükü 4 baytlık maskeyle XOR'lar (aynı işlem hem maskeler hem açar)."""
    if not yuk:
        return b""
    tekrar = (maske * (len(yuk) // 4 + 1))[:len(yuk)]
    return (int.from_bytes(yuk, "big") ^ int.from_bytes(tekrar, "big")).to_bytes(len(yuk), "big")


def cerceve_olustur(yuk, opkod=OP_METIN, maskeli=True, son=True, maske=None):
    """Tek bir WebSocket çerçevesi üretir. İstemci→sunucu yönü maskeli, sunucu→istemci maskesizdir."""
    if isinstance(yuk, str):
        yuk = yuk.encode("utf-8")
    ilk = (0x80 if son else 0) | opkod
    n = len(yuk)
    maske_biti = 0x80 if maskeli else 0
    if n < 126:
        baslik = struct.pack(">BB", ilk, maske_biti | n)
    elif n < 65536:
        baslik = struct.pack(">BBH", ilk, maske_biti | 126, n)
    else:
        baslik = struct.pack(">BBQ", ilk, maske_biti | 127, n)
    if not maskeli:
        return baslik + yuk
    maske = maske or os.urandom(4)
    return baslik + maske + _maskele(yuk, maske)


def cerceve_coz(veri):
    """Tamponun başındaki çerçeveyi çözer; veri eksikse None döner. Çözülen bayt sayısı `uzunluk` alanındadır."""
    if len(veri) < 2:
        return None
    son, opkod = bool(veri[0] & 0x80), veri[0] & 0x0F
    maskeli, n, konum = bool(veri[1] & 0x80), veri[1] & 0x7F, 2
    if n == 126:
        if len(veri) < 4:
            return None
        n, konum = struct.unpack(">H", bytes(veri[2:4]))[0], 4
    elif n == 127:
        if len(veri) < 10:
            return None
        n, konum = struct.unpack(">Q", bytes(veri[2:10]))[0], 10
    if n > EN_BUYUK_YUK:
        raise CdpHatasi(f"Tarayıcıdan gelen veri çok büyük ({n} bayt), bağlantı kesildi.")
    maske = b""
    if maskeli:
        if len(veri) < konum + 4:
            return None
        maske, konum = bytes(veri[konum:konum + 4]), konum + 4
    if len(veri) < konum + n:
        return None
    yuk = bytes(veri[konum:konum + n])
    if maskeli:
        yuk = _maskele(yuk, maske)
    return Cerceve(son, opkod, yuk, maskeli, konum + n)


# ---------------------------------------------------------------- HTTP uçları

def _http_json(port, yol):
    """127.0.0.1:port üzerindeki DevTools HTTP ucundan JSON okur."""
    adres = f"http://127.0.0.1:{port}{yol}"
    try:
        with _acici.open(adres, timeout=HTTP_ZAMANI) as yanit:
            return json.loads(yanit.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as h:
        raise CdpHatasi(f"Tarayıcıya bağlanılamadı ({adres}): {h}") from h


def hedefler(port):
    """Açık sekme/hedeflerin listesi (id, type, url, title, webSocketDebuggerUrl)."""
    return _http_json(port, "/json/list")


def tarayici_ws(port):
    """Tarayıcı düzeyindeki WebSocket adresi (sekme değil, tüm tarayıcıyı denetler)."""
    adres = _http_json(port, "/json/version").get("webSocketDebuggerUrl")
    if not adres:
        raise CdpHatasi("Tarayıcı denetim adresi vermedi (/json/version).")
    return adres


def pencere_bul(port, parca):
    """Adresi parçayla eşleşen ilk "page" hedefi; yoksa None.

    parca: "alanadi[:port][/yol-oneki]" (ör. "chatgpt.com", "127.0.0.1:8799/test"). Eşleşme alt dize
    değil, alan adı sınırında yapılır (bkz. siteler.adres_eslesir_mi): "chatgpt.com.kotu.net" eşleşmez.
    """
    return next((h for h in hedefler(port)
                 if h.get("type") == "page" and siteler.adres_eslesir_mi(h.get("url", ""), parca)), None)


def yeni_pencere(port, url):
    """Yeni bir ÜST DÜZEY pencere açar ve hedef kimliğini (targetId) döndürür."""
    with Baglanti(tarayici_ws(port)) as b:
        return b.komut("Target.createTarget", url=url, newWindow=True)["targetId"]


def pencere_sinirlari(port, hedef_id, sol, ust, genislik, yukseklik):
    """Hedefin (sekmenin) bulunduğu tarayıcı penceresini verilen konuma/boyuta getirir.

    Tarayıcı düzeyi bağlantıyla Browser.getWindowForTarget → Browser.setWindowBounds çağrılır;
    pencere simge/ekranı kaplama durumundaysa önce normale döndürülür. Değerler tarayıcının
    kullandığı mantıksal (DIP) pikseldir. Yeni sınırlar sözlük olarak döner.
    """
    with Baglanti(tarayici_ws(port)) as b:
        pencere = b.komut("Browser.getWindowForTarget", targetId=hedef_id)
        if pencere.get("bounds", {}).get("windowState", "normal") != "normal":
            b.komut("Browser.setWindowBounds", windowId=pencere["windowId"], bounds={"windowState": "normal"})
        b.komut("Browser.setWindowBounds", windowId=pencere["windowId"],
                bounds={"left": int(sol), "top": int(ust), "width": int(genislik), "height": int(yukseklik),
                        "windowState": "normal"})
        return b.komut("Browser.getWindowForTarget", targetId=hedef_id).get("bounds", {})


# ---------------------------------------------------------------- bağlantı

class Baglanti:
    """Tek bir CDP WebSocket bağlantısı (sekme ya da tarayıcı düzeyi)."""

    def __init__(self, ws_url, zaman=10):
        self._sonraki_id = 0
        self._tampon = bytearray()
        self._kapali = False
        self.son_olaylar = collections.deque(maxlen=200)
        parca = urllib.parse.urlparse(ws_url)
        if parca.scheme != "ws" or not parca.hostname:
            raise CdpHatasi(f"Geçersiz WebSocket adresi: {ws_url}")
        try:
            self._soket = socket.create_connection((parca.hostname, parca.port or 80), timeout=zaman)
        except OSError as h:
            raise CdpHatasi(f"Tarayıcıya bağlanılamadı ({ws_url}): {h}") from h
        try:
            self._el_sikis(parca, zaman)
        except BaseException:
            self._soket.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.kapat()

    def _el_sikis(self, parca, zaman):
        """HTTP Upgrade isteğini gönderir, 101 yanıtını ve Sec-WebSocket-Accept değerini doğrular."""
        anahtar = base64.b64encode(os.urandom(16)).decode("ascii")
        yol = (parca.path or "/") + (f"?{parca.query}" if parca.query else "")
        istek = (f"GET {yol} HTTP/1.1\r\nHost: {parca.hostname}:{parca.port or 80}\r\n"
                 f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                 f"Sec-WebSocket-Key: {anahtar}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        bitis = time.monotonic() + zaman
        try:
            self._soket.sendall(istek.encode("ascii"))
            yanit = bytearray()
            while b"\r\n\r\n" not in yanit:
                yanit += self._al(bitis)
        except OSError as h:
            raise CdpHatasi(f"WebSocket el sıkışması başarısız: {h}") from h
        baslik, _, kalan = bytes(yanit).partition(b"\r\n\r\n")
        satirlar = baslik.decode("latin-1").split("\r\n")
        if len(satirlar[0].split()) < 2 or satirlar[0].split()[1] != "101":
            raise CdpHatasi(f"WebSocket bağlantısı reddedildi: {satirlar[0]}")
        basliklar = {s.split(":", 1)[0].strip().lower(): s.split(":", 1)[1].strip() for s in satirlar[1:] if ":" in s}
        beklenen = base64.b64encode(hashlib.sha1((anahtar + WS_ANAHTAR_EKI).encode("ascii")).digest()).decode("ascii")
        if basliklar.get("sec-websocket-accept") != beklenen:
            raise CdpHatasi("WebSocket el sıkışması doğrulanamadı (Sec-WebSocket-Accept uyuşmuyor).")
        self._tampon += kalan

    def _al(self, bitis):
        """Sokette en geç `bitis` anına kadar veri bekler ve okur."""
        kalan = bitis - time.monotonic()
        if kalan <= 0:
            raise CdpHatasi("Tarayıcıdan yanıt gelmedi (zaman aşımı).")
        self._soket.settimeout(kalan)
        try:
            parca = self._soket.recv(65536)
        except socket.timeout as h:
            raise CdpHatasi("Tarayıcıdan yanıt gelmedi (zaman aşımı).") from h
        except OSError as h:
            raise CdpHatasi(f"Tarayıcı bağlantısı koptu: {h}") from h
        if not parca:
            self._kapali = True
            raise CdpHatasi("Tarayıcı bağlantıyı kapattı.")
        return parca

    def _gonder(self, yuk, opkod=OP_METIN):
        """Maskeli çerçeve olarak gönderir."""
        if self._kapali:
            raise CdpHatasi("Bağlantı kapalı.")
        try:
            self._soket.settimeout(10)
            self._soket.sendall(cerceve_olustur(yuk, opkod, maskeli=True))
        except OSError as h:
            raise CdpHatasi(f"Tarayıcıya veri gönderilemedi: {h}") from h

    def _mesaj_oku(self, bitis):
        """Bir mesajın tüm parçalarını birleştirir; araya giren ping'e pong döner, close'u işler."""
        parcalar, basladi = [], False
        while True:
            while (c := cerceve_coz(self._tampon)) is None:
                self._tampon += self._al(bitis)
            del self._tampon[:c.uzunluk]
            if c.opkod == OP_PING:
                self._gonder(c.yuk, OP_PONG)
            elif c.opkod == OP_PONG:
                continue
            elif c.opkod == OP_KAPAT:
                self._kapali = True
                try:
                    self._soket.sendall(cerceve_olustur(c.yuk[:2], OP_KAPAT))
                except OSError:
                    pass
                raise CdpHatasi("Tarayıcı bağlantıyı kapattı (close çerçevesi).")
            elif c.opkod in (OP_METIN, OP_IKILI) and not basladi:
                parcalar, basladi = [c.yuk], True
                if c.son:
                    return b"".join(parcalar)
            elif c.opkod == OP_DEVAM and basladi:
                parcalar.append(c.yuk)
                if c.son:
                    return b"".join(parcalar)
            else:
                raise CdpHatasi("Tarayıcıdan geçersiz WebSocket çerçevesi geldi.")

    def komut(self, yontem, *, zaman=30, **params):
        """CDP komutu gönderir, aynı kimlikli yanıtı bekler ve `result` değerini döndürür."""
        self._sonraki_id += 1
        kimlik = self._sonraki_id
        self._gonder(json.dumps({"id": kimlik, "method": yontem, "params": params}))
        bitis = time.monotonic() + zaman
        while True:
            try:
                mesaj = json.loads(self._mesaj_oku(bitis).decode("utf-8"))
            except ValueError as h:
                raise CdpHatasi(f"Tarayıcıdan okunamayan yanıt geldi: {h}") from h
            if mesaj.get("id") != kimlik:
                if "method" in mesaj:  # olay (event)
                    self.son_olaylar.append(mesaj)
                continue
            if "error" in mesaj:
                e = mesaj["error"]
                raise CdpHatasi(f"{yontem} komutu hata verdi: {e.get('message', e)} (kod {e.get('code', '?')})")
            return mesaj.get("result", {})

    # ------------------------------------------------------------ kolaylık fonksiyonları

    def degerlendir(self, js, zaman=30):
        """Sayfada JavaScript çalıştırır (Promise beklenir) ve değeri döndürür."""
        sonuc = self.komut("Runtime.evaluate", zaman=zaman, expression=js, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in sonuc:
            ayrinti = sonuc["exceptionDetails"]
            metin = ayrinti.get("exception", {}).get("description") or ayrinti.get("text", "bilinmeyen hata")
            raise CdpHatasi(f"Sayfadaki JavaScript hata verdi: {metin}")
        return sonuc.get("result", {}).get("value")

    def git(self, url):
        """Sayfayı adrese yönlendirir ve yüklenmesi için kısa bekler."""
        sonuc = self.komut("Page.navigate", url=url)
        if sonuc.get("errorText"):
            raise CdpHatasi(f"Sayfa açılamadı ({url}): {sonuc['errorText']}")
        time.sleep(0.5)
        return sonuc

    def yazi_ekle(self, metin):
        """Odaktaki alana yazı ekler (yapıştırma gibi, tuş basmadan)."""
        self.komut("Input.insertText", text=metin)

    def tus(self, key, code, windowsVirtualKeyCode, text=None):
        """Bir tuşa basıp bırakır. Enter için: tus("Enter", "Enter", 13, "\\r")."""
        ortak = {"key": key, "code": code, "windowsVirtualKeyCode": windowsVirtualKeyCode}
        asagi = dict(ortak, type="keyDown", **({"text": text} if text else {}))
        self.komut("Input.dispatchKeyEvent", **asagi)
        self.komut("Input.dispatchKeyEvent", type="keyUp", **ortak)

    def one_getir(self):
        """Sekmeyi/pencereyi öne getirir."""
        self.komut("Page.bringToFront")

    def kapat(self):
        """Bağlantıyı düzgünce kapatır (hata vermez)."""
        if not self._kapali:
            try:
                self._soket.sendall(cerceve_olustur(b"\x03\xe8", OP_KAPAT))
            except OSError:
                pass
            self._kapali = True
        try:
            self._soket.close()
        except OSError:
            pass
