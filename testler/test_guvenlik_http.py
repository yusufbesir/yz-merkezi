"""Güvenlik denetimi bulgularının testleri: başlıklar, istek belirteci, gövde sınırı, hata metinleri, ayar şeması,
bozuk ayar dosyası, program yolu denetimi ve port gaspı. Ağ yalnızca 127.0.0.1 üzerindeki geçici sunuculardır;
tarayıcıya, ekrana, gerçek ayar dosyalarına ve 8766/8765/9230 portlarına dokunulmaz.
"""
import http.client
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _ortam  # noqa: E402,F401  (gerçek ayar dosyalarını korur; sunucu modüllerinden önce)
import guvenlik  # noqa: E402
import masaustu_sunucu as ms  # noqa: E402
import sunucu  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
BES_BASLIK = ("X-Frame-Options", "Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy",
              "Cross-Origin-Resource-Policy")


def sunucu_baslat(isleyici):
    s = ThreadingHTTPServer(("127.0.0.1", 0), isleyici)
    s.daemon_threads = True
    threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    return s


class SunucuTabani(unittest.TestCase):
    """Her test için geçici ayar dosyası, geçici veri klasörü (belirteç/hata.log) ve ayrı sunucu."""
    isleyici = None
    belirtec = None
    ayar_modulu = None
    ayar_adi = "AYAR_DOSYASI"

    def setUp(self):
        self.klasor = Path(tempfile.mkdtemp(prefix="yzguv_"))
        self.addCleanup(shutil.rmtree, self.klasor, ignore_errors=True)
        self.ayar = self.klasor / "ayar.json"
        yama = mock.patch.object(self.ayar_modulu, self.ayar_adi, self.ayar)
        yama.start()
        self.addCleanup(yama.stop)
        ortam = mock.patch.dict(os.environ, {"YZ_VERI_KLASORU": str(self.klasor / "veri")})
        ortam.start()
        self.addCleanup(ortam.stop)
        self.sunucu = sunucu_baslat(self.isleyici)
        self.addCleanup(self.sunucu.server_close)
        self.addCleanup(self.sunucu.shutdown)
        self.port = self.sunucu.server_port

    def istek(self, yontem, yol, govde=None, basliklar=None, belirtec=True, ham_govde=None):
        """(kod, yanıt başlıkları, gövde metni) döndürür."""
        b = {"Host": f"127.0.0.1:{self.port}"}
        if belirtec is True:
            b["X-YZ-Token"] = self.belirtec
        elif belirtec:
            b["X-YZ-Token"] = belirtec
        if govde is not None:
            ham_govde = json.dumps(govde)
        if ham_govde is not None:
            b["Content-Type"] = "application/json"
        b.update(basliklar or {})
        bag = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            bag.request(yontem, yol, body=ham_govde.encode("utf-8") if ham_govde is not None else None, headers=b)
            y = bag.getresponse()
            return y.status, y, y.read().decode("utf-8")
        finally:
            bag.close()

    def basliklar_tamam(self, y):
        self.assertEqual(y.getheader("X-Frame-Options"), "DENY")
        csp = y.getheader("Content-Security-Policy")
        self.assertEqual(csp, "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
                              "base-uri 'none'; form-action 'none'")
        self.assertEqual(y.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(y.getheader("Referrer-Policy"), "no-referrer")
        self.assertEqual(y.getheader("Cross-Origin-Resource-Policy"), "same-origin")


class OrtakSunucuTestleri:
    """Her iki sunucuda da aynı çalışan denetimler (karışım: alt sınıf `korumali_get` ve `korumali_post` verir)."""
    korumali_get = None
    korumali_post = None

    def test_guvenlik_basliklari_her_yanitta(self):
        for yol in ("/", "/uygulama.js", self.korumali_get, "/yok-sayfa.js"):
            with self.subTest(yol=yol):
                kod, y, _ = self.istek("GET", yol)
                self.basliklar_tamam(y)
        kod, y, _ = self.istek("GET", self.korumali_get, belirtec=False)   # 403 (belirteçsiz)
        self.assertEqual(kod, 403)
        self.basliklar_tamam(y)
        kod, y, _ = self.istek("GET", "/yok-sayfa.js")                     # 404
        self.assertEqual(kod, 404)
        self.basliklar_tamam(y)
        kod, y, _ = self.istek("GET", "/", basliklar={"Host": "kotu.site"})  # 403 (Host)
        self.assertEqual(kod, 403)
        self.basliklar_tamam(y)

    def test_belirtecsiz_ve_yanlis_belirtec_403(self):
        self.assertEqual(self.istek("GET", self.korumali_get, belirtec=False)[0], 403)
        self.assertEqual(self.istek("GET", self.korumali_get, belirtec="yanlis")[0], 403)
        self.assertEqual(self.istek("GET", self.korumali_get, belirtec=self.belirtec[:-1])[0], 403)
        yol, govde = self.korumali_post
        self.assertEqual(self.istek("POST", yol, govde, belirtec=False)[0], 403)
        self.assertEqual(self.istek("POST", yol, govde, belirtec="yanlis")[0], 403)

    def test_dogru_belirtec_200(self):
        self.assertEqual(self.istek("GET", self.korumali_get)[0], 200)
        yol, govde = self.korumali_post
        self.assertEqual(self.istek("POST", yol, govde)[0], 200)

    def test_dogru_belirtec_ama_yabanci_origin_403(self):
        self.assertEqual(self.istek("GET", self.korumali_get, basliklar={"Origin": "https://evil.com"})[0], 403)
        yol, govde = self.korumali_post
        self.assertEqual(self.istek("POST", yol, govde, basliklar={"Origin": "https://evil.com"})[0], 403)

    def test_kimlik_belirtecsiz_acik(self):
        kod, _, metin = self.istek("GET", "/api/kimlik", belirtec=False)
        self.assertEqual(kod, 200)
        self.assertEqual(json.loads(metin)["uygulama"], "yz-merkezi")
        # yabancı Origin yine reddedilir
        self.assertEqual(self.istek("GET", "/api/kimlik", belirtec=False, basliklar={"Origin": "https://evil.com"})[0], 403)

    def test_statik_dosya_belirtecsiz_acilir(self):
        self.assertEqual(self.istek("GET", "/", belirtec=False)[0], 200)
        self.assertEqual(self.istek("GET", "/uygulama.js", belirtec=False)[0], 200)

    def test_govde_sinirlari(self):
        yol, _ = self.korumali_post
        bas = time.monotonic()
        kod, y, _ = self.istek("POST", yol, basliklar={"Content-Length": "999999999"})
        self.assertEqual(kod, 413)
        self.assertLess(time.monotonic() - bas, 2, "büyük Content-Length gövde beklenmeden reddedilmeli")
        self.basliklar_tamam(y)
        self.assertIn(self.istek("POST", yol, basliklar={"Content-Length": "-1"})[0], (400, 413))
        self.assertEqual(self.istek("POST", yol, basliklar={"Content-Length": "abc"})[0], 400)
        self.assertEqual(self.istek("POST", yol, ham_govde="[1,2]")[0], 400)
        self.assertEqual(self.istek("POST", yol, ham_govde='"metin"')[0], 400)
        self.assertEqual(self.istek("POST", yol, ham_govde="{bozuk")[0], 400)

    def test_yavas_govde_zaman_asimi(self):
        yol, _ = self.korumali_post
        with mock.patch.object(guvenlik, "GOVDE_ZAMAN_ASIMI", 0.5):
            bag = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            bag.putrequest("POST", yol)
            bag.putheader("Host", f"127.0.0.1:{self.port}")
            bag.putheader("X-YZ-Token", self.belirtec)
            bag.putheader("Content-Length", "100")
            bag.endheaders()
            bag.send(b"{")  # gövdenin geri kalanı hiç gelmiyor
            bas = time.monotonic()
            y = bag.getresponse()
            self.assertEqual(y.status, 408)
            self.assertLess(time.monotonic() - bas, 3)
            bag.close()


class MasaustuHttpTesti(OrtakSunucuTestleri, SunucuTabani):
    isleyici = ms.Isleyici
    ayar_modulu = ms
    belirtec = ms.BELIRTEC
    korumali_get = "/api/pencereler"
    korumali_post = ("/api/ayar", {"tema": "koyu"})

    def setUp(self):
        super().setUp()
        for ad, deger in (("pencereleri_listele", []),):
            yama = mock.patch.object(ms.pc, ad, return_value=deger)
            yama.start()
            self.addCleanup(yama.stop)
        yama = mock.patch.object(ms, "kendi_pencere", return_value=None)
        yama.start()
        self.addCleanup(yama.stop)
        yama = mock.patch.object(ms, "AYAR_UYARISI", None)
        yama.start()
        self.addCleanup(yama.stop)
        # /api/durum CDP ile tarayıcıya sorar; testte sahte
        yama = mock.patch.object(ms, "site_durumlari", return_value=[])
        yama.start()
        self.addCleanup(yama.stop)

    # ---- başlıklar (durum ucu)
    def test_api_durum_basliklari_ve_belirteci(self):
        kod, y, metin = self.istek("GET", "/api/durum")
        self.assertEqual(kod, 200)
        self.basliklar_tamam(y)
        self.assertIn("uyari", json.loads(metin))
        self.assertEqual(self.istek("GET", "/api/durum", belirtec=False)[0], 403)

    # ---- hata metinleri
    def test_beklenmeyen_hata_ayrintisiz_ve_gunluklu(self):
        with mock.patch.object(ms, "ayarlari_yaz", side_effect=RuntimeError("gizli-ayrinti dict")):
            kod, _, metin = self.istek("POST", "/api/ayar", {"tema": "koyu"})
        self.assertEqual(kod, 500)
        hata = json.loads(metin)["hata"]
        self.assertRegex(hata, r"^Beklenmeyen bir sorun oluştu \(kod: [0-9a-f]{8}\)$")
        self.assertNotIn("gizli", hata)
        gunluk = (self.klasor / "veri" / "hata.log").read_text("utf-8")
        kod_ = re.search(r"kod: ([0-9a-f]{8})", hata).group(1)
        self.assertIn(f"kod={kod_}", gunluk)
        self.assertIn("RuntimeError", gunluk)
        self.assertIn("yol=/api/ayar", gunluk)

    def test_get_beklenmeyen_hata_ayrintisiz(self):
        with mock.patch.object(ms, "durum", side_effect=KeyError("gizli-anahtar")):
            kod, _, metin = self.istek("GET", "/api/durum")
        self.assertEqual(kod, 500)
        self.assertNotIn("gizli", metin)
        self.assertRegex(metin, r"kod: [0-9a-f]{8}")

    # ---- ayar şeması
    def test_ayar_semasi_gecersizleri_reddeder_dosya_degismez(self):
        self.assertEqual(self.istek("POST", "/api/ayar", {"tema": "acik"})[0], 200)
        once = self.ayar.read_bytes()
        gecersizler = [
            {"ad": ["x"]}, {"tema": "<x>"}, {"yazi_boyutu": "dev"}, {"yerlesim": "yan"}, {"enter_bas": "evet"},
            {"kutuyu_temizle": 1}, {"ad": "x" * 41}, {"secili": "metin"}, {"secili": ["a"]},
            {"secili": {"x": {"y": 1}}}, {"secili": {"site:chatgpt": "evet"}}, {"secili": {"site:yok": True}},
            {"secili": {"chatgpt-yok": True}}, {"tema": "koyu", "enter_bas": "hayir"},  # kısmen geçerli de tümden reddedilir
        ]
        for g in gecersizler:
            with self.subTest(g=g):
                kod, _, metin = self.istek("POST", "/api/ayar", g)
                self.assertEqual(kod, 400, metin)
                self.assertNotIn("dict", metin)
                self.assertEqual(self.ayar.read_bytes(), once)

    def test_ayar_semasi_gecerliyi_kabul_eder(self):
        program = ms.uygulamalar({"ek_uygulamalar": []})[0]["id"]
        g = {"tema": "koyu", "yazi_boyutu": "buyuk", "yerlesim": "alt", "enter_bas": False, "kutuyu_temizle": False,
             "ad": "Ali", "secili": {"site:chatgpt": False, "site:gemini": True, program: True}}
        self.assertEqual(self.istek("POST", "/api/ayar", g)[0], 200)
        kayit = json.loads(self.ayar.read_text("utf-8"))
        self.assertEqual(kayit["ayarlar"]["tema"], "koyu")
        self.assertEqual(kayit["secili"][program], True)
        self.assertEqual(kayit["secili"]["site:chatgpt"], False)

    # ---- bozuk ayar dosyası
    def test_bozuk_ayar_dosyasi_yedeklenir(self):
        self.ayar.write_text("{bu json degil", "utf-8")
        kod, _, _ = self.istek("POST", "/api/ayar", {"tema": "koyu"})
        self.assertEqual(kod, 200)
        yedekler = list(self.klasor.glob("ayar.bozuk-*.json"))
        self.assertEqual(len(yedekler), 1)
        self.assertRegex(yedekler[0].name, r"^ayar\.bozuk-\d{14}\.json$")
        self.assertEqual(yedekler[0].read_text("utf-8"), "{bu json degil")
        self.assertEqual(json.loads(self.ayar.read_text("utf-8"))["ayarlar"]["tema"], "koyu")
        _, _, metin = self.istek("GET", "/api/durum")
        self.assertIn("bozuk", json.loads(metin)["uyari"])

    def test_json_olmayan_kok_da_bozuk_sayilir(self):
        self.ayar.write_text("[1, 2]", "utf-8")
        veri = ms.ayarlari_oku()
        self.assertEqual(veri["secili"], {})
        self.assertEqual(len(list(self.klasor.glob("ayar.bozuk-*.json"))), 1)

    def test_olmayan_ayar_dosyasi_uyari_uretmez(self):
        ms.ayarlari_oku()
        self.assertIsNone(ms.AYAR_UYARISI)
        self.assertEqual(list(self.klasor.glob("ayar.bozuk-*")), [])

    def test_yazma_gecici_dosyayi_birakmaz(self):
        self.assertEqual(self.istek("POST", "/api/ayar", {"tema": "koyu"})[0], 200)
        self.assertFalse(self.ayar.with_suffix(".tmp").exists())

    # ---- program ekleme / açma
    def ekle(self, **g):
        govde = {"ad": "Deneme", "exe": "a.exe", "yol": r"C:\Prog\a.exe"}
        govde.update(g)
        return self.istek("POST", "/api/program-ekle", govde)

    def test_program_ekle_gecersiz_yollar(self):
        acik = ms.pc.Pencere(1, 2, "Deneme", r"C:\Prog\a.exe")
        with mock.patch.object(ms.pc, "pencereleri_listele", return_value=[acik]):
            for g in ({"yol": r"\\sunucu\pay\a.exe"}, {"yol": "\\\\?\\C:\\Prog\\a.exe"}, {"yol": r"C:\a.bat", "exe": "a.bat"},
                      {"yol": r"C:\yok\a.exe"}, {"yol": "a.exe"}, {"yol": r"Prog\a.exe"}, {"yol": ""}, {"yol": None},
                      {"yol": r"C:\Prog\a.exe", "exe": "b.exe"}, {"exe": "msedge.exe", "yol": r"C:\Prog\msedge.exe"},
                      {"ad": "x" * 41}, {"ad": ""}):
                with self.subTest(g=g):
                    kod, _, metin = self.ekle(**g)
                    self.assertEqual(kod, 400, metin)
        self.assertFalse(self.ayar.exists() and json.loads(self.ayar.read_text("utf-8")).get("ek_uygulamalar"))

    def test_program_ekle_tarayicilar_reddedilir_pencere_olsa_da(self):
        for exe in ("msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "opera.exe", "Chrome.EXE"):
            yol = rf"C:\Tarayici\{exe}"
            with mock.patch.object(ms.pc, "pencereleri_listele", return_value=[ms.pc.Pencere(1, 2, "T", yol)]):
                kod, _, metin = self.ekle(exe=exe, yol=yol)
            self.assertEqual(kod, 400, exe)
            self.assertIn("Tarayıcı", metin)

    def test_program_ekle_acik_pencere_varsa_kabul(self):
        acik = ms.pc.Pencere(1, 2, "Deneme", r"c:\prog\A.EXE")  # büyük/küçük harf farkı önemsiz
        with mock.patch.object(ms.pc, "pencereleri_listele", return_value=[acik]):
            kod, _, metin = self.ekle()
        self.assertEqual(kod, 200, metin)
        kayit = json.loads(self.ayar.read_text("utf-8"))["ek_uygulamalar"]
        self.assertEqual([(k["ad"], k["exe"], k["yol"]) for k in kayit], [("Deneme", "a.exe", r"C:\Prog\a.exe")])

    def test_ek_programi_acarken_yol_yeniden_denetlenir(self):
        kotu = {"id": "ek-1", "ad": "Kötü", "exe": "a.bat", "yol": r"C:\a.bat", "renk": "#000"}
        unc = {"id": "ek-2", "ad": "Ağ", "exe": "a.exe", "yol": r"\\sunucu\pay\a.exe", "renk": "#000"}
        iyi = {"id": "ek-3", "ad": "İyi", "exe": "a.exe", "yol": r"C:\Prog\a.exe", "appid": "Zararli!App", "renk": "#000"}
        self.ayar.write_text(json.dumps({"ek_uygulamalar": [kotu, unc, iyi]}), "utf-8")
        with mock.patch.object(ms.pc, "uygulamayi_ac") as ac:
            self.assertEqual(self.istek("POST", "/api/ac", {"id": "ek-1"})[0], 400)
            self.assertEqual(self.istek("POST", "/api/ac", {"id": "ek-2"})[0], 400)
            ac.assert_not_called()
            self.assertEqual(self.istek("POST", "/api/ac", {"id": "ek-3"})[0], 200)
            ac.assert_called_once_with({"ad": "İyi", "yol": r"C:\Prog\a.exe"})  # appid gibi ek alanlar aktarılmaz

    def test_yol_gecerli_mi(self):
        self.assertTrue(ms._yol_gecerli_mi(r"C:\Prog\a.exe", "a.exe"))
        self.assertTrue(ms._yol_gecerli_mi("D:/Prog/a.exe"))
        for yol in (r"\\s\p\a.exe", "\\\\?\\C:\\a.exe", r"C:\a.bat", "a.exe", r"C:a.exe", "", None, 5, "C:\\a\x00.exe"):
            self.assertFalse(ms._yol_gecerli_mi(yol), repr(yol))
        self.assertFalse(ms._yol_gecerli_mi(r"C:\Prog\a.exe", "b.exe"))

    def test_sahte_test_sayfasi_yalniz_test_kipinde_ve_csp_gevsemez(self):
        with mock.patch.dict(os.environ, {"YZ_TEST": "0"}):
            kod, y, _ = self.istek("GET", "/test/sahte-site.html", belirtec=False)
        self.assertEqual(kod, 404)
        self.basliklar_tamam(y)   # normal kipte CSP dahil beş başlık var
        with mock.patch.dict(os.environ, {"YZ_TEST": "1"}):
            for yol in ("/test/sahte-site.html", "/test/c/2", "/test/sahte-site.js", "/test/sahte-site.css"):
                kod, y, _ = self.istek("GET", yol, belirtec=False)
                self.assertEqual(kod, 200, yol)
                self.basliklar_tamam(y)   # sahte sayfa için de CSP gevşetilmez
        html = (KOK / "testler" / "sahte-site.html").read_text("utf-8")
        self.assertNotRegex(html, r"<style|<script(?![^>]*\ssrc=)")   # satır içi script/stil yok

    # ---- statik dosya güvenliği
    def test_arayuz_disina_cikilmaz(self):
        self.assertEqual(self.istek("GET", "/../masaustu_sunucu.py", belirtec=False)[0], 404)
        self.assertEqual(self.istek("GET", "/%2e%2e/masaustu_sunucu.py", belirtec=False)[0], 404)


class PortGaspiTesti(unittest.TestCase):
    """D3: port meşgulse çalışan örneğin gerçekten bu uygulama olduğu /api/kimlik ile doğrulanır."""

    class Ilgisiz(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            govde = b'{"uygulama": "baska-bir-sey"}' if self.path == "/api/kimlik" else b"merhaba"
            self.send_response(200)
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)

    def setUp(self):
        self.klasor = Path(tempfile.mkdtemp(prefix="yzport_"))
        self.addCleanup(shutil.rmtree, self.klasor, ignore_errors=True)
        ortam = mock.patch.dict(os.environ, {"YZ_VERI_KLASORU": str(self.klasor)})
        ortam.start()
        self.addCleanup(ortam.stop)

    def sunucu(self, isleyici):
        s = sunucu_baslat(isleyici)
        self.addCleanup(s.server_close)
        self.addCleanup(s.shutdown)
        return s

    def test_ilgisiz_sunucu_bizim_degil(self):
        s = self.sunucu(self.Ilgisiz)
        self.assertFalse(ms.calisan_ornek_mi(s.server_port))

    def test_kapali_port_bizim_degil(self):
        s = sunucu_baslat(self.Ilgisiz)
        port = s.server_port
        s.shutdown()
        s.server_close()
        self.assertFalse(ms.calisan_ornek_mi(port))

    def test_bizim_sunucu_taninir(self):
        s = self.sunucu(ms.Isleyici)
        self.assertTrue(ms.calisan_ornek_mi(s.server_port))

    def test_ilgisiz_sunucuda_pencere_acilmaz(self):
        s = self.sunucu(self.Ilgisiz)
        with mock.patch.object(ms.tarayici, "uygulama_penceresi_ac") as ac, redirect_stdout(io.StringIO()) as cikti:
            self.assertFalse(ms.mevcut_ornegi_ac(s.server_port))
        ac.assert_not_called()
        self.assertIn("başka bir program", cikti.getvalue())
        self.assertIn("pencere açılmadı", (self.klasor / "hata.log").read_text("utf-8"))

    def test_bizim_sunucu_pencereyi_kendisi_acar(self):
        # İkinci örnek tarayıcıya erişemez (CDP borusu çalışan örnektedir): pencereyi POST /api/pencere-ac ile
        # çalışan örneğe açtırır; çalışan örnek kendi belirteçli adresini uygulama kipinde açar.
        s = self.sunucu(ms.Isleyici)
        guvenlik.belirtec_yaz(ms.BELIRTEC)
        with mock.patch.object(ms.tarayici, "uygulama_penceresi_ac", return_value=None) as ac:
            self.assertTrue(ms.mevcut_ornegi_ac(s.server_port))
        ac.assert_called_once_with(f"http://127.0.0.1:{s.server_port}/#t={ms.BELIRTEC}")

    def test_yanlis_belirtecle_pencere_acilmaz(self):
        s = self.sunucu(ms.Isleyici)
        guvenlik.belirtec_yaz("eski-ornegin-belirteci")
        with mock.patch.object(ms.tarayici, "uygulama_penceresi_ac") as ac, redirect_stdout(io.StringIO()) as cikti:
            self.assertFalse(ms.mevcut_ornegi_ac(s.server_port))
        ac.assert_not_called()
        self.assertIn("403", cikti.getvalue())

    def test_belirtec_dosyasi_yoksa_pencere_acilmaz(self):
        s = self.sunucu(ms.Isleyici)
        with mock.patch.object(ms.tarayici, "uygulama_penceresi_ac") as ac, redirect_stdout(io.StringIO()) as cikti:
            self.assertFalse(ms.mevcut_ornegi_ac(s.server_port))
        ac.assert_not_called()
        self.assertIn("belirteç dosyası bulunamadı", cikti.getvalue())

    def test_pencere_ac_ucu_belirtecsiz_reddedilir(self):
        s = self.sunucu(ms.Isleyici)
        talep = urllib.request.Request(f"http://127.0.0.1:{s.server_port}/api/pencere-ac", b"{}", method="POST",
                                       headers={"Content-Type": "application/json"})
        with mock.patch.object(ms.tarayici, "uygulama_penceresi_ac") as ac:
            with self.assertRaises(urllib.error.HTTPError) as h:
                urllib.request.build_opener(urllib.request.ProxyHandler({})).open(talep, timeout=5)
        self.assertEqual(h.exception.code, 403)
        ac.assert_not_called()

    def test_pencere_acilamazsa_turkce_hata(self):
        s = self.sunucu(ms.Isleyici)
        guvenlik.belirtec_yaz(ms.BELIRTEC)
        with mock.patch.object(ms.tarayici, "uygulama_penceresi_ac", return_value="Bu profille açık bir Edge penceresi var"), \
                redirect_stdout(io.StringIO()) as cikti:
            self.assertFalse(ms.mevcut_ornegi_ac(s.server_port))
        self.assertIn("açık bir Edge penceresi var", cikti.getvalue())

    def test_main_port_mesgulken_ilgisiz_sunucuya_pencere_acmaz(self):
        s = self.sunucu(self.Ilgisiz)
        with mock.patch.object(ms, "PORT", s.server_port), mock.patch.object(ms.pc, "dpi_farkindaligi_ac"), \
                mock.patch.object(ms.tarayici, "uygulama_penceresi_ac") as ac, \
                mock.patch.object(ms.tarayici, "baslat") as baslat, redirect_stdout(io.StringIO()):
            ms.main()
        ac.assert_not_called()
        baslat.assert_not_called()

    def test_main_port_mesgulken_bizim_ornege_belirtecli_acar(self):
        s = self.sunucu(ms.Isleyici)
        guvenlik.belirtec_yaz(ms.BELIRTEC)
        with mock.patch.object(ms, "PORT", s.server_port), mock.patch.object(ms.pc, "dpi_farkindaligi_ac"), \
                mock.patch.object(ms.tarayici, "uygulama_penceresi_ac", return_value=None) as ac, \
                mock.patch.object(ms.tarayici, "baslat") as baslat:
            ms.main()
        ac.assert_called_once_with(f"http://127.0.0.1:{s.server_port}/#t={ms.BELIRTEC}")
        baslat.assert_not_called()

    def test_sunucu_sinifi_ayni_porta_ikinci_baglanmayi_reddeder(self):
        s = self.sunucu(self.Ilgisiz)   # SO_REUSEADDR'lı ilgisiz dinleyici
        with self.assertRaises(OSError):
            ms.Sunucu(("127.0.0.1", s.server_port), ms.Isleyici)


class ApiSurumuHttpTesti(OrtakSunucuTestleri, SunucuTabani):
    isleyici = sunucu.Isleyici
    ayar_modulu = sunucu
    belirtec = sunucu.BELIRTEC
    korumali_get = "/api/saglayicilar"
    korumali_post = ("/api/saglayici-sil", {"id": "yok"})

    def test_beklenmeyen_hata_ayrintisiz(self):
        with mock.patch.object(sunucu, "ayarlari_yaz", side_effect=RuntimeError("gizli-ayrinti")):
            kod, _, metin = self.istek("POST", "/api/anahtar", {"id": "openai", "anahtar": "x"})
        self.assertEqual(kod, 500)
        self.assertRegex(metin, r"kod: [0-9a-f]{8}")
        self.assertNotIn("gizli", metin)
        self.assertIn("RuntimeError", (self.klasor / "veri" / "hata.log").read_text("utf-8"))

    def test_bozuk_ayar_dosyasi_yedeklenir(self):
        self.ayar.write_text("{bozuk anahtar dosyasi", "utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.istek("POST", "/api/anahtar", {"id": "openai", "anahtar": "x"})[0], 200)
        yedekler = list(self.klasor.glob("ayar.bozuk-*.json"))
        self.assertEqual([y.read_text("utf-8") for y in yedekler], ["{bozuk anahtar dosyasi"])
        self.assertEqual(json.loads(self.ayar.read_text("utf-8"))["anahtarlar"], {"openai": "x"})


class YardimciTesti(unittest.TestCase):
    def test_belirtec_gecerli_mi(self):
        self.assertTrue(guvenlik.belirtec_gecerli_mi("abc", "abc"))
        self.assertFalse(guvenlik.belirtec_gecerli_mi("abd", "abc"))
        self.assertFalse(guvenlik.belirtec_gecerli_mi("", ""))
        self.assertFalse(guvenlik.belirtec_gecerli_mi(None, "abc"))
        self.assertFalse(guvenlik.belirtec_gecerli_mi("ğüş", "abc"))
        self.assertGreaterEqual(len(guvenlik.yeni_belirtec()), 40)
        self.assertNotEqual(guvenlik.yeni_belirtec(), guvenlik.yeni_belirtec())

    def test_modul_belirteclari_farkli_ve_bellekte(self):
        self.assertNotEqual(ms.BELIRTEC, sunucu.BELIRTEC)
        self.assertNotIn(ms.BELIRTEC, (KOK / "masaustu_sunucu.py").read_text("utf-8"))

    def test_belirtec_dosyasi_yazilir_ve_okunur(self):
        with tempfile.TemporaryDirectory() as k, mock.patch.dict(os.environ, {"YZ_VERI_KLASORU": k}):
            self.assertEqual(guvenlik.belirtec_oku(), "")
            self.assertTrue(guvenlik.belirtec_yaz("xyz"))
            self.assertEqual(guvenlik.belirtec_oku(), "xyz")
            self.assertTrue(guvenlik.belirtec_yaz("uzun-bir-belirtec-sonra-kisa"))
            self.assertTrue(guvenlik.belirtec_yaz("k"))
            self.assertEqual(guvenlik.belirtec_oku(), "k")

    def test_hata_gunlugu_boyut_sinirinda_doner(self):
        with tempfile.TemporaryDirectory() as k, mock.patch.dict(os.environ, {"YZ_VERI_KLASORU": k}), \
                mock.patch.object(guvenlik, "HATA_LOGU_SINIRI", 100):
            for i in range(10):
                guvenlik.hata_yaz("x" * 40 + str(i))
            self.assertTrue((Path(k) / "hata.log.eski").exists())
            self.assertLess((Path(k) / "hata.log").stat().st_size, 400)

    def test_ortam_korumasi_gercek_dosyalara_yonlendirmez(self):
        # _ortam, ayar dosyalarını ve profili geçici klasöre yönlendirir (ortamda önceden yoksa).
        self.assertNotEqual(Path(os.environ["YZ_MASAUSTU_AYAR"]).parent, KOK)
        self.assertNotEqual(Path(os.environ["YZ_AYAR_DOSYASI"]).parent, KOK)


class ArayuzDosyalariTesti(unittest.TestCase):
    """CSP satır içi script/style'a izin vermez; arayüz bunlara ihtiyaç duymamalı. Belirteç akışı arayüzde olmalı."""

    def test_satir_ici_script_ve_stil_yok(self):
        for klasor in ("arayuz", "arayuz-masaustu"):
            html = (KOK / klasor / "index.html").read_text("utf-8")
            with self.subTest(klasor=klasor):
                self.assertNotRegex(html, r"<style")
                self.assertNotRegex(html, r"\sstyle\s*=")
                self.assertNotRegex(html, r"\son[a-z]+\s*=")   # onclick vb.
                for m in re.finditer(r"<script\b([^>]*)>", html):
                    self.assertIn("src=", m.group(1))
                self.assertNotRegex(html, r"(src|href)\s*=\s*[\"']https?://")   # dış kaynak yüklenmez
                self.assertNotRegex((KOK / klasor / "stil.css").read_text("utf-8"), r"@import|url\(\s*['\"]?https?:")

    def test_arayuz_belirtec_akisi(self):
        for klasor in ("arayuz", "arayuz-masaustu"):
            js = (KOK / klasor / "uygulama.js").read_text("utf-8")
            with self.subTest(klasor=klasor):
                self.assertIn("X-YZ-Token", js)
                self.assertIn("location.hash", js)
                self.assertIn("sessionStorage", js)
                self.assertIn("history.replaceState", js)
        # /api/ isteği yapan her fetch çağrısı başlığı taşımalı
        for klasor in ("arayuz", "arayuz-masaustu"):
            js = (KOK / klasor / "uygulama.js").read_text("utf-8")
            for m in re.finditer(r"fetch\(", js):
                parca = js[m.start():m.start() + 300]
                self.assertTrue("X-YZ-Token" in parca or "secenek" in parca or "basliklar" in parca, parca)

    def test_masaustu_tek_asistan_arayuzu(self):
        js = (KOK / "arayuz-masaustu" / "uygulama.js").read_text("utf-8")
        self.assertIn("/api/sor", js)
        self.assertIn("onay_gerekli", js)          # hassas bilgi onayı akışta da var
        self.assertNotRegex(js, r"innerHTML")      # güvenli DOM üretimi
        md = (KOK / "arayuz-masaustu" / "markdown.js").read_text("utf-8")
        self.assertNotRegex(md, r"innerHTML")
        html = (KOK / "arayuz-masaustu" / "index.html").read_text("utf-8")
        self.assertIn('data-sekme="gelismis"', html)   # eski pencere yolları Gelişmiş altında
        self.assertIn('id="hepsiniAc"', html)


if __name__ == "__main__":
    unittest.main()
