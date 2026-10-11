"""Sunucu testleri: sahte bir sağlayıcı sunucusu üç API biçimini (OpenAI, Anthropic, Gemini) taklit eder.

Çalıştırma:  python -m unittest discover testler
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GECICI = tempfile.mkdtemp()
os.environ["YZ_AYAR_DOSYASI"] = str(Path(GECICI) / "ayarlar.json")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sunucu  # noqa: E402

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
                                       {"Content-Type": "application/json", **(basliklar or {})})
        with urllib.request.urlopen(talep) as y:
            return y.read().decode()

    def get(self, yol):
        with urllib.request.urlopen(self.kok + yol) as y:
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

    def test_arayuz_dosyalari_sunulur(self):
        with urllib.request.urlopen(self.kok + "/") as y:
            self.assertIn("Yapay Zeka Merkezi", y.read().decode())
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.kok + "/../sunucu.py")


if __name__ == "__main__":
    unittest.main()
