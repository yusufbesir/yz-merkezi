"""siteler.adres_eslesir_mi için testler: alt dize değil, alan adı sınırında eşleşme."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import siteler  # noqa: E402

eslesir = siteler.adres_eslesir_mi


class AdresEslesmeTesti(unittest.TestCase):
    def test_gercek_site_adresleri_eslesir(self):
        self.assertTrue(eslesir("https://chatgpt.com/c/1", "chatgpt.com"))
        self.assertTrue(eslesir("https://chatgpt.com", "chatgpt.com"))
        self.assertTrue(eslesir("https://CHATGPT.com./c/1", "chatgpt.com"))
        self.assertTrue(eslesir("https://gemini.google.com/app/abc", "gemini.google.com"))
        self.assertTrue(eslesir("https://claude.ai/new", "claude.ai"))
        self.assertTrue(eslesir("https://auth.openai.com/log-in", "auth.openai.com"))
        self.assertTrue(eslesir("https://accounts.google.com/signin?x=1", "accounts.google.com"))

    def test_alt_alan_eslesir(self):
        self.assertTrue(eslesir("https://www.chatgpt.com/", "chatgpt.com"))
        self.assertTrue(eslesir("https://a.b.claude.ai/x", "claude.ai"))

    def test_alt_dize_ve_taklit_alan_adlari_eslesmez(self):
        self.assertFalse(eslesir("https://chatgpt.com.kotu.net/", "chatgpt.com"))
        self.assertFalse(eslesir("https://kotuchatgpt.com/", "chatgpt.com"))
        self.assertFalse(eslesir("https://kotu.net/chatgpt.com/", "chatgpt.com"))
        self.assertFalse(eslesir("https://kotu.net/?u=chatgpt.com", "chatgpt.com"))
        self.assertFalse(eslesir("https://chatgpt.com@kotu.net/", "chatgpt.com"))
        self.assertFalse(eslesir("https://kotu.net\\@chatgpt.com/", "chatgpt.com"))
        self.assertFalse(eslesir("https://kotu.net#@chatgpt.com/", "chatgpt.com"))
        self.assertFalse(eslesir("https://claude.ai.evil.com/", "claude.ai"))
        self.assertFalse(eslesir("https://gemini.google.com.evil.com/", "gemini.google.com"))
        self.assertFalse(eslesir("https://google.com/", "gemini.google.com"))

    def test_yerel_adres_port_ve_yol_oneki(self):
        url = "http://127.0.0.1:8799/test/sahte-site.html"
        self.assertTrue(eslesir(url, "127.0.0.1:8799/test"))
        self.assertTrue(eslesir(url, "127.0.0.1:8799"))
        self.assertTrue(eslesir(url, "127.0.0.1"))  # parçada port yoksa port denetlenmez
        self.assertFalse(eslesir(url, "127.0.0.1:8798/test"))
        self.assertFalse(eslesir(url, "127.0.0.1:8799/baska"))
        self.assertFalse(eslesir("http://127.0.0.1:8799/test/../x", "127.0.0.1:8799/test"))
        self.assertFalse(eslesir("http://11.127.0.0.1:8799/test", "127.0.0.1:8799/test"))

    def test_varsayilan_port(self):
        self.assertTrue(eslesir("https://chatgpt.com/", "chatgpt.com:443"))
        self.assertFalse(eslesir("https://chatgpt.com/", "chatgpt.com:80"))
        self.assertTrue(eslesir("http://chatgpt.com/", "chatgpt.com:80"))

    def test_baska_semalar_eslesmez(self):
        self.assertFalse(eslesir("file:///C:/chatgpt.com/index.html", "chatgpt.com"))
        self.assertFalse(eslesir("javascript:alert('chatgpt.com')", "chatgpt.com"))
        self.assertFalse(eslesir("about:blank", "about:blank"))
        self.assertFalse(eslesir("data:text/html,chatgpt.com", "chatgpt.com"))
        self.assertFalse(eslesir("ftp://chatgpt.com/", "chatgpt.com"))
        self.assertFalse(eslesir("//chatgpt.com/", "chatgpt.com"))

    def test_bos_ve_gecersiz_girdiler(self):
        for url in ("", None, 5, "https://", " https://chatgpt.com/", "https://chatgpt.com/ x",
                    "https://chatgpt.com:abc/"):
            self.assertFalse(eslesir(url, "chatgpt.com"), repr(url))
        for parca in ("", None, "/yol", ":80"):
            self.assertFalse(eslesir("https://chatgpt.com/", parca), repr(parca))

    def test_masaustu_site_adresi_mi(self):
        import masaustu_sunucu as m
        self.assertTrue(m._site_adresi_mi("chatgpt", "https://chatgpt.com/c/1"))
        self.assertTrue(m._site_adresi_mi("chatgpt", "https://www.chatgpt.com/"))
        self.assertFalse(m._site_adresi_mi("chatgpt", "https://chatgpt.com.kotu.net/c/1"))
        self.assertFalse(m._site_adresi_mi("claude", "https://chatgpt.com/"))
        self.assertFalse(m._site_adresi_mi("chatgpt", None))


if __name__ == "__main__":
    unittest.main()
