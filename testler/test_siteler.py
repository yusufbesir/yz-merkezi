"""siteler.py için testler: gerçek siteye bağlanmaz, DOM çalıştırmaz."""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import siteler  # noqa: E402

NODE_YOLLARI = [r"D:\n8n\nodejs\node.exe"]


def node_bul():
    for yol in NODE_YOLLARI:
        if os.path.exists(yol):
            return yol
    return shutil.which("node")


class JsParcalariTesti(unittest.TestCase):
    def test_uc_site_ve_alanlar(self):
        self.assertEqual(set(siteler.SITELER), {"chatgpt", "gemini", "claude"})
        beklenen = {"chatgpt": "ChatGPT", "gemini": "Gemini", "claude": "Claude"}
        for kimlik, ad in beklenen.items():
            kayit = siteler.site(kimlik)
            self.assertEqual(kayit["id"], kimlik)
            self.assertEqual(kayit["ad"], ad)
            self.assertTrue(kayit["adres"].startswith("https://"))
            self.assertTrue(kayit["yeni_sohbet_adresi"].startswith("https://"))
            self.assertRegex(kayit["renk"], r"^#[0-9a-fA-F]{6}$")

    def test_bilinmeyen_site(self):
        with self.assertRaises(KeyError):
            siteler.site("yok")

    def test_her_anahtar_var_ve_sarili(self):
        for kimlik, kayit in siteler.SITELER.items():
            for anahtar in siteler.JS_ANAHTARLARI:
                with self.subTest(site=kimlik, anahtar=anahtar):
                    parca = kayit["js"][anahtar]
                    self.assertTrue(parca.startswith("(async () =>"))
                    self.assertTrue(parca.endswith("})()"))
                    self.assertIn("catch (hata)", parca)
                    self.assertIn('{ hata: String(', parca)

    def test_parantez_dengesi(self):
        self.assertEqual(siteler.js_dogrula(), [])

    def test_dogrulama_bozuk_js_yakalar(self):
        self.assertIsNotNone(siteler._dengeli_mi("const a = (1 + 2;"))
        self.assertIsNotNone(siteler._dengeli_mi("if (x) { return 1; "))
        self.assertIsNotNone(siteler._dengeli_mi("const s = 'kapanmadı;"))
        self.assertIsNone(siteler._dengeli_mi("const r = /[(]/.test('(') ? [1] : {a: ')'};  // ("))

    def test_js_sar(self):
        sarili = siteler.js_sar("return 1;")
        self.assertTrue(sarili.startswith("(async () =>"))
        self.assertIn("return 1;", sarili)
        self.assertIn("hata", sarili)
        self.assertEqual(siteler._dengeli_mi(sarili), None)

    def test_hassas_veri_okunmuyor(self):
        for kayit in siteler.SITELER.values():
            for parca in kayit["js"].values():
                for yasak in ("document.cookie", "localStorage", "sessionStorage", "password", "type=\"password\""):
                    self.assertNotIn(yasak, parca)

    def test_node_sozdizimi(self):
        node = node_bul()
        if not node:
            self.skipTest("node bulunamadı")
        with tempfile.TemporaryDirectory() as klasor:
            for kimlik, kayit in siteler.SITELER.items():
                for anahtar, parca in kayit["js"].items():
                    with self.subTest(site=kimlik, anahtar=anahtar):
                        dosya = Path(klasor) / ("%s_%s.js" % (kimlik, anahtar))
                        dosya.write_text(parca, "utf-8")
                        sonuc = subprocess.run([node, "--check", str(dosya)], capture_output=True, text=True)
                        self.assertEqual(sonuc.returncode, 0, sonuc.stderr)


class SohbetKimligiTesti(unittest.TestCase):
    def test_bilinen_adresler(self):
        self.assertEqual(siteler.sohbet_kimligi("chatgpt", "/c/abc"), "chatgpt:abc")
        self.assertEqual(siteler.sohbet_kimligi("chatgpt", "https://chatgpt.com/c/abc-123?x=1#y"), "chatgpt:abc-123")
        self.assertEqual(siteler.sohbet_kimligi("gemini", "/app/xyz"), "gemini:xyz")
        self.assertEqual(siteler.sohbet_kimligi("gemini", "https://gemini.google.com/u/1/app/xyz"), "gemini:xyz")
        self.assertEqual(siteler.sohbet_kimligi("claude", "/chat/uuid"), "claude:uuid")
        self.assertEqual(
            siteler.sohbet_kimligi("claude", "https://claude.ai/chat/1b2c-3d4e"), "claude:1b2c-3d4e")

    def test_claude_proje(self):
        self.assertEqual(siteler.sohbet_kimligi("claude", "https://claude.ai/project/p1"), "claude:proje-p1")

    def test_bilinmeyen_adres_karma(self):
        url = "https://claude.ai/baska/yol"
        beklenen = "claude:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        self.assertEqual(siteler.sohbet_kimligi("claude", url), beklenen)
        self.assertEqual(siteler.sohbet_kimligi("claude", url), beklenen)  # kararlı
        self.assertNotEqual(siteler.sohbet_kimligi("claude", url + "2"), beklenen)

    def test_bos_adres(self):
        self.assertTrue(siteler.sohbet_kimligi("gemini", "").startswith("gemini:"))


if __name__ == "__main__":
    unittest.main()
