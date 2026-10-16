"""Sunucu testleri: sahte bir sağlayıcı sunucusu üç API biçimini (OpenAI, Anthropic, Gemini) taklit eder.

Çalıştırma:  python -m unittest discover testler
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import json
import os
import sys
import tempfile
import threading
import unittest
import unittest.mock
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _ortam  # noqa: E402,F401  (gerçek ayar dosyalarını korur; sunucu modülünden önce)
import sunucu  # noqa: E402

GECICI = tempfile.mkdtemp()
sunucu.AYAR_DOSYASI = Path(GECICI) / "ayarlar.json"  # bu dosyanın kendi geçici ayarı (modül içe aktarılmış olsa da)

ANAHTAR = "test-anahtari"


class SahteSaglayici(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _sse(self, olaylar):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for olay in olaylar:
            veri = olay if isinstance(olay, str) else json.dumps(olay)
            self.wfile.write(f"data: {veri}\n\n".encode())

    def _json(self, veri, kod=200):
        govde = json.dumps(veri).encode()
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def _yetkili(self):
        return ANAHTAR in (self.headers.get("Authorization", "") + self.headers.get("x-api-key", "")
                           + self.headers.get("x-goog-api-key", ""))

    def do_GET(self):
        if not self._yetkili():
            return self._json({"error": {"message": "invalid key"}}, 401)
        if self.path.startswith("/oa/models"):
            return self._json({"data": [{"id": "gpt-eski", "created": 1}, {"id": "gpt-yeni", "created": 2},
                                        {"id": "text-embedding-3", "created": 3}]})
        if self.path.startswith("/an/models"):
            return self._json({"data": [{"id": "claude-x", "display_name": "Claude X"}]})
        if self.path.startswith("/ge/models"):
            return self._json({"models": [
                {"name": "models/gemini-x", "displayName": "Gemini X", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/embedding", "supportedGenerationMethods": ["embedContent"]}]})
        self._json({}, 404)

    def do_POST(self):
        govde = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.son_govde = govde
        if not self._yetkili():
            return self._json({"error": {"message": "invalid key"}}, 401)
        if self.path == "/oa/chat/completions":
            return self._sse([{"choices": [{"delta": {"content": "Mer"}}]},
                              {"choices": [{"delta": {"content": "haba"}}]}, "[DONE]"])
        if self.path == "/an/messages":
            return self._sse([{"type": "message_start"},
                              {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Selam"}},
                              {"type": "message_stop"}])
        if self.path.startswith("/ge/models/gemini-x:streamGenerateContent"):
            return self._sse([{"candidates": [{"content": {"parts": [{"text": "düşünce", "thought": True}]}}]},
                              {"candidates": [{"content": {"parts": [{"text": "Günaydın"}]}}]}])
        self._json({"error": {"message": "yok"}}, 404)


class SunucuTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sahte = ThreadingHTTPServer(("127.0.0.1", 0), SahteSaglayici)
        threading.Thread(target=cls.sahte.serve_forever, daemon=True).start()
        cls.uygulama = ThreadingHTTPServer(("127.0.0.1", 0), sunucu.Isleyici)
        threading.Thread(target=cls.uygulama.serve_forever, daemon=True).start()
        cls.kok = f"http://127.0.0.1:{cls.uygulama.server_port}"
        sahte_adres = f"http://127.0.0.1:{cls.sahte.server_port}"
        for ad, tur, yol in [("Sahte OA", "openai", "/oa"), ("Sahte AN", "anthropic", "/an"), ("Sahte GE", "gemini", "/ge")]:
            cls.post("/api/saglayici-ekle", {"ad": ad, "tur": tur, "adres": sahte_adres + yol, "anahtar": ANAHTAR})

    @classmethod
    def tearDownClass(cls):
        cls.sahte.shutdown()
        cls.uygulama.shutdown()

    @classmethod
    def post(cls, yol, veri, basliklar=None):
        talep = urllib.request.Request(cls.kok + yol, json.dumps(veri).encode(),
                                       {"Content-Type": "application/json", "X-YZ-Token": sunucu.BELIRTEC,
                                        **(basliklar or {})})
        with urllib.request.urlopen(talep) as y:
            return y.read().decode()

    def get(self, yol):
        with urllib.request.urlopen(urllib.request.Request(self.kok + yol, headers={"X-YZ-Token": sunucu.BELIRTEC})) as y:
            return json.load(y)

    def sohbet(self, sid, model):
        cikti = self.post("/api/sohbet", {"saglayici": sid, "model": model, "sistem": "Kısa yanıtla",
                                          "mesajlar": [{"rol": "kullanici", "icerik": "Merhaba"}]})
        return [json.loads(s) for s in cikti.splitlines() if s]

    def test_saglayici_listesi_anahtar_sizdirmaz(self):
        liste = self.get("/api/saglayicilar")
        ids = {s["id"] for s in liste}
        self.assertTrue({"openai", "gemini", "anthropic", "ozel-sahte-oa"} <= ids)
        self.assertNotIn(ANAHTAR, json.dumps(liste))

    def dosya_metni(self):
        return sunucu.AYAR_DOSYASI.read_text("utf-8")

    @unittest.skipUnless(os.name == "nt", "DPAPI yalnızca Windows'ta")
    def test_dpapi_gidis_donus(self):
        import guvenlik
        sifreli = guvenlik.dpapi_sifrele("gizli-deger-123")
        self.assertTrue(sifreli.startswith("dpapi:"))
        self.assertNotIn("gizli-deger-123", sifreli)
        self.assertEqual(guvenlik.dpapi_coz(sifreli), "gizli-deger-123")
        with self.assertRaises(ValueError):
            guvenlik.dpapi_coz("dpapi:!!!")
        with self.assertRaises(ValueError):
            guvenlik.dpapi_coz("duz-metin")

    @unittest.skipUnless(os.name == "nt", "DPAPI yalnızca Windows'ta")
    def test_dosyada_duz_anahtar_yok(self):
        metin = self.dosya_metni()
        self.assertNotIn(ANAHTAR, metin)
        anahtarlar = json.loads(metin)["anahtarlar"]
        self.assertTrue(anahtarlar and all(v.startswith("dpapi:") for v in anahtarlar.values()))
        self.assertNotIn(ANAHTAR, json.dumps(self.get("/api/saglayicilar")))

    @unittest.skipUnless(os.name == "nt", "DPAPI yalnızca Windows'ta")
    def test_duz_metin_gecisi(self):
        ayar = json.loads(self.dosya_metni())
        ayar["anahtarlar"]["ozel-sahte-oa"] = ANAHTAR  # eski sürümün düz metin kaydı
        sunucu.AYAR_DOSYASI.write_text(json.dumps(ayar), "utf-8")
        self.assertEqual(sunucu.anahtar_al(sunucu.saglayici_bul("ozel-sahte-oa"))[0], ANAHTAR)  # düz kabul edilir
        self.post("/api/anahtar", {"id": "ozel-sahte-an", "anahtar": ANAHTAR})  # ilk yazım
        self.assertNotIn(ANAHTAR, self.dosya_metni())
        self.assertEqual(sunucu.anahtar_al(sunucu.saglayici_bul("ozel-sahte-oa"))[0], ANAHTAR)

    @unittest.skipUnless(os.name == "nt", "DPAPI yalnızca Windows'ta")
    def test_dpapi_acilista_duz_anahtarlar_sifrelenir(self):
        eski = sunucu.AYAR_DOSYASI
        yeni = Path(tempfile.mkdtemp()) / "ayarlar.json"
        yeni.write_text(json.dumps({"anahtarlar": {"a": "duz-anahtar-1", "b": "duz-anahtar-2"},
                                    "ozel_saglayicilar": []}), "utf-8")
        sunucu.AYAR_DOSYASI = yeni
        try:
            self.assertEqual(sunucu.duz_anahtarlari_sifrele(), 2)
            metin = yeni.read_text("utf-8")
            self.assertNotIn("duz-anahtar", metin)
            anahtarlar = json.loads(metin)["anahtarlar"]
            self.assertTrue(all(v.startswith("dpapi:") for v in anahtarlar.values()))
            self.assertEqual(sunucu.guvenlik.dpapi_coz(anahtarlar["a"]), "duz-anahtar-1")
            self.assertEqual(sunucu.duz_anahtarlari_sifrele(), 0)  # ikinci çağrı: yapılacak şey yok
        finally:
            sunucu.AYAR_DOSYASI = eski

    def test_dpapi_yoksa_duz_metne_dusmez(self):
        with unittest.mock.patch("guvenlik.os.name", "posix"):
            with self.assertRaises(ValueError):
                sunucu.guvenlik.dpapi_sifrele("x")

    def test_adres_degisince_anahtar_silinir(self):
        adres = f"http://127.0.0.1:{self.sahte.server_port}/oa"
        self.post("/api/saglayici-ekle", {"ad": "Gecici Adr", "tur": "openai", "adres": adres, "anahtar": ANAHTAR})
        try:
            self.assertEqual(sunucu.anahtar_al(sunucu.saglayici_bul("ozel-gecici-adr"))[0], ANAHTAR)
            self.post("/api/saglayici-ekle", {"ad": "Gecici Adr", "tur": "openai", "adres": adres + "2"})
            self.assertEqual(sunucu.anahtar_al(sunucu.saglayici_bul("ozel-gecici-adr")), ("", None))
        finally:
            self.post("/api/saglayici-sil", {"id": "ozel-gecici-adr"})

    def test_loopback_disi_http_reddedilir(self):
        with self.assertRaises(urllib.error.HTTPError) as h:
            self.post("/api/saglayici-ekle", {"ad": "Dis", "tur": "openai", "adres": "http://example.com/v1", "anahtar": "k"})
        self.assertEqual(h.exception.code, 400)
        self.assertIsNone(sunucu.saglayici_bul("ozel-dis"))
        self.post("/api/saglayici-ekle", {"ad": "Dis", "tur": "openai", "adres": "https://example.com/v1"})
        self.post("/api/saglayici-sil", {"id": "ozel-dis"})

    def test_openai_modelleri_yeniden_eskiye(self):
        modeller = self.get("/api/modeller?id=ozel-sahte-oa")["modeller"]
        self.assertEqual([m["id"] for m in modeller][:2], ["text-embedding-3", "gpt-yeni"])

    def test_gemini_yalnizca_sohbet_modelleri(self):
        modeller = self.get("/api/modeller?id=ozel-sahte-ge")["modeller"]
        self.assertEqual([m["id"] for m in modeller], ["gemini-x"])

    def test_openai_akisi(self):
        olaylar = self.sohbet("ozel-sahte-oa", "gpt-yeni")
        self.assertEqual("".join(o.get("t", "") for o in olaylar), "Merhaba")
        self.assertTrue(olaylar[-1].get("bitti"))
        self.assertEqual(self.sahte.son_govde["messages"][0], {"role": "system", "content": "Kısa yanıtla"})

    def test_anthropic_akisi(self):
        olaylar = self.sohbet("ozel-sahte-an", "claude-x")
        self.assertEqual("".join(o.get("t", "") for o in olaylar), "Selam")
        self.assertEqual(self.sahte.son_govde["system"], "Kısa yanıtla")
        self.assertIn("max_tokens", self.sahte.son_govde)

    def test_gemini_akisi_dusunceyi_atlar(self):
        olaylar = self.sohbet("ozel-sahte-ge", "gemini-x")
        self.assertEqual("".join(o.get("t", "") for o in olaylar), "Günaydın")
        self.assertEqual(self.sahte.son_govde["contents"][0]["role"], "user")

    def test_anahtarsiz_saglayici_turkce_hata(self):
        os.environ.pop("OPENAI_API_KEY", None)
        olaylar = self.sohbet("openai", "gpt-yeni")
        self.assertIn("API anahtarı girilmemiş", olaylar[-1]["hata"])

    def test_yanlis_anahtar_turkce_hata(self):
        self.post("/api/anahtar", {"id": "ozel-sahte-oa", "anahtar": "yanlis"})
        try:
            olaylar = self.sohbet("ozel-sahte-oa", "gpt-yeni")
            self.assertIn("API anahtarı geçersiz", olaylar[-1]["hata"])
        finally:
            self.post("/api/anahtar", {"id": "ozel-sahte-oa", "anahtar": ANAHTAR})

    def test_baska_siteden_istek_reddedilir(self):
        with self.assertRaises(urllib.error.HTTPError) as h:
            self.post("/api/anahtar", {"id": "openai", "anahtar": "x"}, {"Origin": "http://kotu.site"})
        self.assertEqual(h.exception.code, 403)

    def test_yonlendirme_izlenmez_anahtar_ikinci_adrese_gitmez(self):
        ikinci = []

        class Hedef(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                ikinci.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

        hedef = ThreadingHTTPServer(("127.0.0.1", 0), Hedef)
        threading.Thread(target=hedef.serve_forever, daemon=True).start()
        self.addCleanup(hedef.shutdown)
        yonlendiren = type("Yonlendiren", (BaseHTTPRequestHandler,), {
            "log_message": lambda self, *a: None,
            "do_GET": lambda self: (self.send_response(302),
                                    self.send_header("Location", f"http://127.0.0.1:{hedef.server_port}/gizli"),
                                    self.send_header("Content-Length", "0"), self.end_headers())})
        kaynak = ThreadingHTTPServer(("127.0.0.1", 0), yonlendiren)
        threading.Thread(target=kaynak.serve_forever, daemon=True).start()
        self.addCleanup(kaynak.shutdown)
        with self.assertRaises(sunucu.SaglayiciHatasi) as h:
            sunucu.istek(f"http://127.0.0.1:{kaynak.server_port}/x", basliklar={"Authorization": "Bearer gizli"})
        self.assertIn("yönlendirme yaptı", str(h.exception))
        self.assertEqual(ikinci, [], "anahtar yönlendirilen ikinci adrese gitmemeli")

    def test_arayuz_dosyalari_sunulur(self):
        with urllib.request.urlopen(self.kok + "/") as y:
            self.assertIn("Yapay Zeka Merkezi", y.read().decode())
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.kok + "/../sunucu.py")


if __name__ == "__main__":
    unittest.main()
