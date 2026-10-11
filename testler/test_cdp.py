"""CDP istemcisi testleri: çerçeve kodlama, sahte WebSocket sunucusu ve (Edge varsa) gerçek bütünleşme.

Çalıştırma:  python -m unittest discover testler
"""
import json
import base64
import hashlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socket import socket, AF_INET, SOCK_STREAM
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cdp  # noqa: E402
import tarayici  # noqa: E402


# ---------------------------------------------------------------- çerçeve kodlama/çözme

class CerceveTesti(unittest.TestCase):
    def test_rfc_ornekleri(self):
        # RFC 6455 bölüm 5.7: "Hello" maskesiz ve maskeli
        self.assertEqual(cdp.cerceve_olustur("Hello", maskeli=False), bytes.fromhex("810548656c6c6f"))
        self.assertEqual(cdp.cerceve_olustur("Hello", maskeli=True, maske=bytes.fromhex("37fa213d")),
                         bytes.fromhex("818537fa213d7f9f4d5158"))

    def test_uzunluk_siniflari_gidis_donus(self):
        for n, baslik_boyu in [(0, 2), (5, 2), (125, 2), (126, 4), (65535, 4), (65536, 10), (100000, 10)]:
            for maskeli in (False, True):
                yuk = bytes(i % 251 for i in range(n))
                veri = cdp.cerceve_olustur(yuk, cdp.OP_IKILI, maskeli=maskeli)
                self.assertEqual(len(veri), baslik_boyu + (4 if maskeli else 0) + n, (n, maskeli))
                c = cdp.cerceve_coz(veri)
                self.assertEqual((c.son, c.opkod, c.yuk, c.maskeli, c.uzunluk),
                                 (True, cdp.OP_IKILI, yuk, maskeli, len(veri)), (n, maskeli))

    def test_uzunluk_basligi_bicimleri(self):
        self.assertEqual(cdp.cerceve_olustur(b"x" * 125, maskeli=False)[1], 125)
        self.assertEqual(cdp.cerceve_olustur(b"x" * 126, maskeli=False)[1], 126)
        self.assertEqual(cdp.cerceve_olustur(b"x" * 65536, maskeli=False)[1], 127)

    def test_maskeleme_yuku_degistirir(self):
        yuk = b"gizli yazi"
        veri = cdp.cerceve_olustur(yuk, maskeli=True, maske=b"\x01\x02\x03\x04")
        self.assertEqual(veri[1] & 0x80, 0x80)  # maske biti
        self.assertNotIn(yuk, veri)
        self.assertEqual(cdp.cerceve_coz(veri).yuk, yuk)

    def test_eksik_veri_none_doner(self):
        veri = cdp.cerceve_olustur(b"a" * 300, maskeli=True)
        for kesim in (0, 1, 3, 5, 100, len(veri) - 1):
            self.assertIsNone(cdp.cerceve_coz(veri[:kesim]), kesim)

    def test_art_arda_cerceveler(self):
        tampon = bytearray(cdp.cerceve_olustur("bir", maskeli=False) + cdp.cerceve_olustur("iki", maskeli=False) + b"\x81")
        ilk = cdp.cerceve_coz(tampon)
        del tampon[:ilk.uzunluk]
        ikinci = cdp.cerceve_coz(tampon)
        del tampon[:ikinci.uzunluk]
        self.assertEqual((ilk.yuk, ikinci.yuk), (b"bir", b"iki"))
        self.assertIsNone(cdp.cerceve_coz(tampon))

    def test_parca_bayragi(self):
        c = cdp.cerceve_coz(cdp.cerceve_olustur("a", cdp.OP_METIN, maskeli=False, son=False))
        self.assertFalse(c.son)
        self.assertEqual(c.opkod, cdp.OP_METIN)

    def test_asiri_buyuk_uzunluk_reddedilir(self):
        veri = bytes([0x82, 127]) + (cdp.EN_BUYUK_YUK + 1).to_bytes(8, "big")
        with self.assertRaises(cdp.CdpHatasi):
            cdp.cerceve_coz(veri)


# ---------------------------------------------------------------- sahte WebSocket sunucusu

class SahteSunucu:
    """Tek bağlantı kabul eden, el sıkışmayı yapan ve gelen JSON komutlarına `davranis` ile yanıt veren sunucu.

    davranis(istek, sunucu) -> gönderilecek ham çerçeve baytları listesi.
    """

    def __init__(self, davranis, el_sikisma_kodu="101 Switching Protocols", kotu_accept=False):
        self.davranis, self.kod, self.kotu_accept = davranis, el_sikisma_kodu, kotu_accept
        self.gelenler = []  # (opkod, maskeli_mi, çözülmüş yük)
        self.dinleyici = socket(AF_INET, SOCK_STREAM)
        self.dinleyici.bind(("127.0.0.1", 0))
        self.dinleyici.listen(1)
        self.port = self.dinleyici.getsockname()[1]
        self.ws_url = f"ws://127.0.0.1:{self.port}/devtools/page/TEST"
        self.istek_satiri = ""
        threading.Thread(target=self._calis, daemon=True).start()

    def _calis(self):
        try:
            baglanti, _ = self.dinleyici.accept()
        except OSError:
            return
        with baglanti:
            baglanti.settimeout(5)
            veri = bytearray()
            try:
                while b"\r\n\r\n" not in veri:
                    veri += baglanti.recv(4096)
                baslik, _, veri = bytes(veri).partition(b"\r\n\r\n")
                veri = bytearray(veri)
                satirlar = baslik.decode("latin-1").split("\r\n")
                self.istek_satiri = satirlar[0]
                anahtar = next(s.split(":", 1)[1].strip() for s in satirlar if s.lower().startswith("sec-websocket-key"))
                kabul = base64.b64encode(hashlib.sha1((anahtar + cdp.WS_ANAHTAR_EKI).encode()).digest()).decode()
                if self.kotu_accept:
                    kabul = "yanlis"
                baglanti.sendall((f"HTTP/1.1 {self.kod}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                                  f"Sec-WebSocket-Accept: {kabul}\r\n\r\n").encode())
                if not self.kod.startswith("101"):
                    return
                while True:
                    c = cdp.cerceve_coz(veri)
                    if c is None:
                        yeni = baglanti.recv(65536)
                        if not yeni:
                            return
                        veri += yeni
                        continue
                    del veri[:c.uzunluk]
                    self.gelenler.append((c.opkod, c.maskeli, c.yuk))
                    if c.opkod == cdp.OP_KAPAT:
                        return
                    if c.opkod == cdp.OP_METIN:
                        for cerceve in self.davranis(json.loads(c.yuk), self):
                            baglanti.sendall(cerceve)
            except (OSError, StopIteration):
                return

    def kapat(self):
        self.dinleyici.close()

    def bekle(self, kosul, sure=2):
        """Gelen çerçevelerde koşul sağlanana dek bekler (testler eşzamansız izlenen şeyi doğrulasın diye)."""
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            if any(kosul(g) for g in list(self.gelenler)):
                return True
            time.sleep(0.02)
        return False


def sunucusuz_sonuc(deger):
    """Her komuta {"result": {"result": {"value": deger}}} yanıtı veren davranış."""
    return lambda istek, s: [cdp.cerceve_olustur(json.dumps({"id": istek["id"], "result": {"result": {"value": deger}}}),
                                                  maskeli=False)]


class BaglantiTesti(unittest.TestCase):
    def kur(self, davranis, **kw):
        sunucu = SahteSunucu(davranis, **kw)
        self.addCleanup(sunucu.kapat)
        return sunucu

    def baglan(self, sunucu):
        b = cdp.Baglanti(sunucu.ws_url, zaman=3)
        self.addCleanup(b.kapat)
        return b

    def test_komut_ve_degerlendir(self):
        sunucu = self.kur(sunucusuz_sonuc(42))
        b = self.baglan(sunucu)
        self.assertEqual(b.komut("Runtime.evaluate", expression="1+41"), {"result": {"value": 42}})
        self.assertEqual(b.degerlendir("1+41"), 42)
        # istemci çerçeveleri maskeli, kimlikler artan ve parametreler doğru olmalı
        metinler = [(m, json.loads(y)) for o, m, y in sunucu.gelenler if o == cdp.OP_METIN]
        self.assertTrue(all(m for m, _ in metinler))
        self.assertEqual([i["id"] for _, i in metinler], [1, 2])
        self.assertEqual(metinler[1][1]["method"], "Runtime.evaluate")
        self.assertEqual(metinler[1][1]["params"], {"expression": "1+41", "returnByValue": True, "awaitPromise": True})
        self.assertIn("/devtools/page/TEST", sunucu.istek_satiri)

    def test_olaylar_son_olaylara_gider(self):
        def davranis(istek, s):
            olay = {"method": "Page.loadEventFired", "params": {"timestamp": 1}}
            yanit = {"id": istek["id"], "result": {"x": 1}}
            baska = {"id": 999, "result": {}}  # başkasına ait yanıt yok sayılır
            return [cdp.cerceve_olustur(json.dumps(m), maskeli=False) for m in (olay, baska, yanit)]
        b = self.baglan(self.kur(davranis))
        self.assertEqual(b.komut("Page.enable"), {"x": 1})
        self.assertEqual([o["method"] for o in b.son_olaylar], ["Page.loadEventFired"])

    def test_hata_yaniti_cdp_hatasi_firlatir(self):
        def davranis(istek, s):
            return [cdp.cerceve_olustur(json.dumps({"id": istek["id"], "error": {"code": -32601, "message": "yok boyle komut"}}),
                                        maskeli=False)]
        b = self.baglan(self.kur(davranis))
        with self.assertRaises(cdp.CdpHatasi) as h:
            b.komut("Bilinmeyen.komut")
        self.assertIn("yok boyle komut", str(h.exception))

    def test_js_istisnasi_cdp_hatasi_firlatir(self):
        def davranis(istek, s):
            sonuc = {"result": {"type": "object"}, "exceptionDetails": {"text": "Uncaught",
                     "exception": {"description": "ReferenceError: x is not defined"}}}
            return [cdp.cerceve_olustur(json.dumps({"id": istek["id"], "result": sonuc}), maskeli=False)]
        b = self.baglan(self.kur(davranis))
        with self.assertRaises(cdp.CdpHatasi) as h:
            b.degerlendir("x")
        self.assertIn("ReferenceError", str(h.exception))

    def test_parcali_yanit_ve_ping(self):
        def davranis(istek, s):
            tam = json.dumps({"id": istek["id"], "result": {"result": {"value": "ö" * 200}}}).encode("utf-8")
            a, o, u = tam[:30], tam[30:100], tam[100:]
            return [cdp.cerceve_olustur(a, cdp.OP_METIN, maskeli=False, son=False),
                    cdp.cerceve_olustur(b"nabiz", cdp.OP_PING, maskeli=False),  # parçalar arasında ping
                    cdp.cerceve_olustur(o, cdp.OP_DEVAM, maskeli=False, son=False),
                    cdp.cerceve_olustur(u, cdp.OP_DEVAM, maskeli=False, son=True)]
        sunucu = self.kur(davranis)
        b = self.baglan(sunucu)
        self.assertEqual(b.degerlendir("x"), "ö" * 200)
        self.assertTrue(sunucu.bekle(lambda g: g[0] == cdp.OP_PONG and g[1] and g[2] == b"nabiz"), "pong gelmedi")

    def test_buyuk_yanit_126_ve_127_bicimleri(self):
        for n in (300, 70000):
            sunucu = self.kur(sunucusuz_sonuc("a" * n))
            b = self.baglan(sunucu)
            self.assertEqual(b.degerlendir("x"), "a" * n)

    def test_buyuk_istek_gonderilir(self):
        sunucu = self.kur(sunucusuz_sonuc(1))
        b = self.baglan(sunucu)
        b.yazi_ekle("b" * 70000)
        istek = json.loads(next(y for o, m, y in sunucu.gelenler if o == cdp.OP_METIN))
        self.assertEqual(istek["method"], "Input.insertText")
        self.assertEqual(len(istek["params"]["text"]), 70000)

    def test_tus_iki_olay_gonderir(self):
        sunucu = self.kur(sunucusuz_sonuc(1))
        b = self.baglan(sunucu)
        b.tus("Enter", "Enter", 13, "\r")
        istekler = [json.loads(y) for o, m, y in sunucu.gelenler if o == cdp.OP_METIN]
        self.assertEqual([i["params"]["type"] for i in istekler], ["keyDown", "keyUp"])
        self.assertEqual(istekler[0]["params"]["text"], "\r")
        self.assertEqual(istekler[0]["params"]["windowsVirtualKeyCode"], 13)
        self.assertNotIn("text", istekler[1]["params"])

    def test_zaman_asimi(self):
        b = self.baglan(self.kur(lambda istek, s: []))  # hiç yanıt vermez
        with self.assertRaises(cdp.CdpHatasi) as h:
            b.komut("Page.enable", zaman=0.3)
        self.assertIn("zaman aşımı", str(h.exception))

    def test_close_cercevesi(self):
        b = self.baglan(self.kur(lambda istek, s: [cdp.cerceve_olustur(b"\x03\xe8", cdp.OP_KAPAT, maskeli=False)]))
        with self.assertRaises(cdp.CdpHatasi):
            b.komut("Page.enable")
        with self.assertRaises(cdp.CdpHatasi):  # kapandıktan sonra komut verilemez
            b.komut("Page.enable")

    def test_el_sikisma_reddedilirse(self):
        sunucu = self.kur(lambda i, s: [], el_sikisma_kodu="403 Forbidden")
        with self.assertRaises(cdp.CdpHatasi) as h:
            cdp.Baglanti(sunucu.ws_url, zaman=3)
        self.assertIn("403", str(h.exception))

    def test_yanlis_accept_reddedilir(self):
        sunucu = self.kur(lambda i, s: [], kotu_accept=True)
        with self.assertRaises(cdp.CdpHatasi):
            cdp.Baglanti(sunucu.ws_url, zaman=3)

    def test_baglanti_yoksa(self):
        s = socket(AF_INET, SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()  # dinleyen kimse yok
        with self.assertRaises(cdp.CdpHatasi):
            cdp.Baglanti(f"ws://127.0.0.1:{port}/x", zaman=1)


# ---------------------------------------------------------------- HTTP uçları (sahte DevTools sunucusu)

class SahteDevTools(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        port = self.server.server_port
        if self.path == "/json/version":
            veri = {"Browser": "Edge/1", "webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/browser/B"}
        elif self.path == "/json/list":
            veri = [{"id": "1", "type": "service_worker", "url": "http://a/sw.js", "title": "", "webSocketDebuggerUrl": "ws://x/1"},
                    {"id": "2", "type": "page", "url": "http://a/sohbet", "title": "Sohbet", "webSocketDebuggerUrl": "ws://x/2"},
                    {"id": "3", "type": "page", "url": "http://a/sohbet2", "title": "Diğer", "webSocketDebuggerUrl": "ws://x/3"}]
        else:
            self.send_response(404)
            self.end_headers()
            return
        govde = json.dumps(veri).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)


class HttpUclariTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), SahteDevTools)
        cls.port = cls.sunucu.server_port
        threading.Thread(target=cls.sunucu.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.sunucu.shutdown()
        cls.sunucu.server_close()

    def test_hedefler_ve_pencere_bul(self):
        self.assertEqual(len(cdp.hedefler(self.port)), 3)
        self.assertEqual(cdp.pencere_bul(self.port, "a/sohbet")["id"], "2")  # ilk "page" hedefi, service_worker değil
        self.assertEqual(cdp.pencere_bul(self.port, "a/sohbet2")["id"], "3")
        self.assertIsNone(cdp.pencere_bul(self.port, "a/yok-boyle-yol"))
        self.assertIsNone(cdp.pencere_bul(self.port, "sohbet"))  # alt dize eşleşmesi yok
        self.assertIsNone(cdp.pencere_bul(self.port, "b"))

    def test_tarayici_ws(self):
        self.assertEqual(cdp.tarayici_ws(self.port), f"ws://127.0.0.1:{self.port}/devtools/browser/B")

    def test_tarayici_yoksa_turkce_hata(self):
        s = socket(AF_INET, SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        bos = s.getsockname()[1]
        s.close()
        with self.assertRaises(cdp.CdpHatasi) as h:
            cdp.hedefler(bos)
        self.assertIn("bağlanılamadı", str(h.exception))
        with mock.patch.object(tarayici, "CDP_PORT", bos):
            self.assertFalse(tarayici.calisiyor_mu())
            self.assertIsNone(tarayici.sayfa("x"))

    def test_calisiyor_mu(self):
        with mock.patch.object(tarayici, "CDP_PORT", self.port):
            self.assertTrue(tarayici.calisiyor_mu())


class TarayiciYedekTesti(unittest.TestCase):
    def test_edge_yoksa_varsayilan_tarayici_ve_uyari(self):
        with mock.patch.object(tarayici, "calisiyor_mu", return_value=False), \
                mock.patch.object(tarayici, "EDGE_YOLLARI", [r"C:\yok\msedge.exe"]), \
                mock.patch.object(tarayici.webbrowser, "open") as ac:
            uyari = tarayici.baslat("http://127.0.0.1:1/")
        ac.assert_called_once_with("http://127.0.0.1:1/")
        self.assertIn("Edge bulunamadı", uyari)


# ---------------------------------------------------------------- gerçek Edge ile bütünleşme

def _edge_var_mi():
    return sys.platform == "win32" and any(Path(y).exists() for y in tarayici.EDGE_YOLLARI)


def _profil_sureclerini_kapat(profil):
    """Komut satırında geçici profil klasörünün adı geçen Edge süreçlerini durdurur (başka Edge'lere dokunmaz)."""
    ad = Path(profil).name
    komut = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains('%s') } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" % ad)
    subprocess.run(["powershell", "-NoProfile", "-Command", komut], capture_output=True, timeout=60)


@unittest.skipUnless(_edge_var_mi(), "Microsoft Edge bulunamadı, bütünleşme testi atlandı")
class EdgeButunlesmeTesti(unittest.TestCase):
    def test_baslat_ve_degerlendir(self):
        profil = tempfile.mkdtemp(prefix="yzcdp_")
        self.addCleanup(shutil.rmtree, profil, True)
        self.addCleanup(_profil_sureclerini_kapat, profil)
        with mock.patch.object(tarayici, "PROFIL", Path(profil)), mock.patch.object(tarayici, "CDP_PORT", 9231):
            self.assertIsNone(tarayici.baslat("about:blank"))
            self.assertTrue(tarayici.calisiyor_mu())
            # Edge, --app=about:blank adresini yeni sekmeye çevirir; ikinci pencereyi CDP ile açmak
            # hem pencere_ac yolunu sınar hem de adresi gerçekten about:blank olan bir sekme verir.
            self.assertIsNone(tarayici.pencere_ac("about:blank"))
            # about:blank http(s) değil; adres eşleştirmesi onu kabul etmez, hedef doğrudan CDP listesinden alınır.
            self.assertIsNone(tarayici.sayfa("about:blank"))
            hedef = next(h for h in cdp.hedefler(9231) if h.get("type") == "page" and h.get("url") == "about:blank")
            sayfa = cdp.Baglanti(hedef["webSocketDebuggerUrl"])
            self.assertIsNotNone(sayfa)
            try:
                self.assertEqual(sayfa.degerlendir("1+41"), 42)
            finally:
                sayfa.kapat()


if __name__ == "__main__":
    unittest.main()
