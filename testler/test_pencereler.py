"""Masaüstü sürümünün hesaplama ve eşleştirme mantığı için testler (ekrana dokunmaz)."""
import ctypes
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pencereler as pc  # noqa: E402


class PencereMantigiTesti(unittest.TestCase):
    def test_yan_yana_esit_sutunlar(self):
        konumlar = pc.yan_yana_konumlar((0, 0, 1920, 1040), 3, 200)
        self.assertEqual(konumlar, [(0, 0, 640, 840), (640, 0, 640, 840), (1280, 0, 640, 840)])

    def test_konum_gidis_donus(self):
        dortgen = (100, 50, 740, 890)
        konum = pc.konum_hesapla(dortgen, (420, 800))
        self.assertEqual(konum, {"oran_x": 0.5, "alttan": 90})
        self.assertEqual(pc.giris_noktasi(dortgen, konum), (420, 800))

    def test_konum_pencere_boyutu_degisince_uyar(self):
        # Yazı kutusu ortada ve alttan sabit uzaklıkta kalır; pencere daralsa da doğru yere tıklanır.
        self.assertEqual(pc.giris_noktasi((0, 0, 400, 600), {"oran_x": 0.5, "alttan": 90}), (200, 510))

    def test_eslestirme(self):
        claude = {"exe": "Claude.exe", "yol_icerir": "WindowsApps"}
        masaustu = pc.Pencere(1, 1, "Claude", r"C:\Program Files\WindowsApps\Claude_2\app\Claude.exe")
        komut_satiri = pc.Pencere(2, 2, "claude", r"C:\Users\x\AppData\Roaming\Claude\claude-code\claude.exe")
        self.assertTrue(pc.eslesir_mi(claude, masaustu))
        self.assertFalse(pc.eslesir_mi(claude, komut_satiri))

    def test_tarayici_basligiyla_eslestirme(self):
        grok = {"exe": "msedge.exe", "baslik_icerir": "Grok"}
        self.assertTrue(pc.eslesir_mi(grok, pc.Pencere(1, 1, "Grok - Microsoft Edge", r"C:\x\msedge.exe")))
        self.assertFalse(pc.eslesir_mi(grok, pc.Pencere(2, 1, "Haberler - Microsoft Edge", r"C:\x\msedge.exe")))


UYGULAMALAR = json.loads((Path(__file__).resolve().parent.parent / "uygulamalar.json").read_text("utf-8"))


def kayit(kimlik):
    return next(u for u in UYGULAMALAR if u["id"] == kimlik)


class PencereEslesmeGuvenligiTesti(unittest.TestCase):
    """Yanlış pencereye yazı gitmesin: yol ve tarayıcı başlığı eşleşmesi sıkı olmalı."""

    GERCEK_CHATGPT = r"C:\Program Files\WindowsApps\OpenAI.Codex_26.1007.2314.0_x64__2p2nqsd0c76g0\app\ChatGPT.exe"
    GERCEK_GEMINI = r"C:\Users\x\AppData\Local\Google\Gemini\Gemini.exe"

    def test_chatgpt_yol_denetimi(self):
        chatgpt = kayit("chatgpt")
        self.assertIn("WindowsApps", chatgpt["yol_icerir"])
        self.assertTrue(pc.eslesir_mi(chatgpt, pc.Pencere(1, 1, "ChatGPT", self.GERCEK_CHATGPT)))
        self.assertFalse(pc.eslesir_mi(chatgpt, pc.Pencere(2, 2, "ChatGPT", r"C:\kotu\ChatGPT.exe")))
        self.assertFalse(pc.eslesir_mi(chatgpt, pc.Pencere(3, 3, "ChatGPT", r"C:\Users\x\Downloads\WindowsApps\ChatGPT.exe")))

    def test_gemini_yol_denetimi(self):
        gemini = kayit("gemini")
        self.assertTrue(pc.eslesir_mi(gemini, pc.Pencere(1, 1, "Gemini", self.GERCEK_GEMINI)))
        self.assertFalse(pc.eslesir_mi(gemini, pc.Pencere(2, 2, "Gemini", r"C:\kotu\Gemini.exe")))

    def test_claude_yol_denetimi(self):
        claude = kayit("claude")
        self.assertTrue(pc.eslesir_mi(claude, pc.Pencere(1, 1, "Claude", r"C:\Program Files\WindowsApps\Claude_2\app\Claude.exe")))
        self.assertFalse(pc.eslesir_mi(claude, pc.Pencere(2, 2, "Claude", r"C:\kotu\Claude.exe")))

    def test_tarayici_basligi_tam_eslesir(self):
        grok = {"exe": "msedge.exe", "baslik_icerir": "Grok"}
        edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        # Başlığında "Grok" geçmeyen ya da başka sayfa başlığı olan pencere eşleşmez.
        self.assertFalse(pc.eslesir_mi(grok, pc.Pencere(1, 1, "ChatGPT", edge)))
        self.assertFalse(pc.eslesir_mi(grok, pc.Pencere(2, 1, "ChatGPT - Microsoft Edge", edge)))
        # Alt dize olarak geçmesi yetmez.
        self.assertFalse(pc.eslesir_mi(grok, pc.Pencere(3, 1, "Grok hakkında haber - Microsoft Edge", edge)))
        self.assertFalse(pc.eslesir_mi(grok, pc.Pencere(4, 1, "Neden Grok kullanmalı? - Microsoft Edge", edge)))
        # Tam başlık ve "<parça> - <tarayıcı adı>" kabul edilir (büyük/küçük harf önemsiz).
        self.assertTrue(pc.eslesir_mi(grok, pc.Pencere(5, 1, "Grok", edge)))
        self.assertTrue(pc.eslesir_mi(grok, pc.Pencere(6, 1, "grok - Microsoft Edge", edge)))

    def test_chatgpt_basliginda_edge_grok_kaydina_gitmez(self):
        grok = {"exe": "msedge.exe", "baslik_icerir": "Grok"}
        edge = pc.Pencere(1, 1, "ChatGPT", r"C:\x\msedge.exe")
        self.assertFalse(pc.eslesir_mi(grok, edge))

    def test_diger_tarayicilar_da_tam_eslesme(self):
        for exe, ad in [("chrome.exe", "Google Chrome"), ("firefox.exe", "Mozilla Firefox"),
                        ("brave.exe", "Brave"), ("opera.exe", "Opera")]:
            with self.subTest(exe=exe):
                kayit_ = {"exe": exe, "baslik_icerir": "Grok"}
                self.assertTrue(pc.eslesir_mi(kayit_, pc.Pencere(1, 1, f"Grok - {ad}", rf"C:\x\{exe}")))
                self.assertFalse(pc.eslesir_mi(kayit_, pc.Pencere(2, 1, f"Grok rehberi - {ad}", rf"C:\x\{exe}")))

    def test_tarayici_olmayan_programda_baslik_alt_dize_kalir(self):
        uyg = {"exe": "Program.exe", "baslik_icerir": "Proje"}
        self.assertTrue(pc.eslesir_mi(uyg, pc.Pencere(1, 1, "Benim Projem - Program", r"C:\x\Program.exe")))

    def test_pencere_bul_kesin(self):
        chatgpt = kayit("chatgpt")
        a = pc.Pencere(1, 1, "ChatGPT", self.GERCEK_CHATGPT)
        b = pc.Pencere(2, 2, "ChatGPT", self.GERCEK_CHATGPT)
        baska = pc.Pencere(3, 3, "Not Defteri", r"C:\Windows\notepad.exe")
        self.assertIs(pc.pencere_bul_kesin(chatgpt, [baska, a]), a)
        self.assertIsNone(pc.pencere_bul_kesin(chatgpt, [a, b, baska]))  # iki aday: belirsiz
        self.assertIsNone(pc.pencere_bul_kesin(chatgpt, [baska]))        # hiç aday yok
        self.assertIsNone(pc.pencere_bul_kesin(chatgpt, []))


class PanoGizliligiTesti(unittest.TestCase):
    """Gerçek Windows panosunu kullanır; başlamadan önceki metni geri koyar."""

    def setUp(self):
        self.yedek = pc.panoyu_oku()
        self.addCleanup(pc.panoyu_geri_yukle, self.yedek)

    @staticmethod
    def bicim(ad):
        return pc.user32.RegisterClipboardFormatW(ad)

    def bicim_var_mi(self, ad):
        return bool(pc.user32.IsClipboardFormatAvailable(self.bicim(ad)))

    def dword_oku(self, ad):
        pc._pano_ac()
        try:
            tutamac = pc.user32.GetClipboardData(self.bicim(ad))
            if not tutamac:
                return None
            adres = pc.kernel32.GlobalLock(tutamac)
            try:
                return ctypes.c_uint32.from_address(adres).value
            finally:
                pc.kernel32.GlobalUnlock(tutamac)
        finally:
            pc.user32.CloseClipboard()

    def test_panoya_yaz_gizlilik_bicimlerini_koyar(self):
        pc.panoyu_geri_yukle("eski")
        self.assertEqual(pc.panoyu_oku(), "eski")
        self.assertFalse(self.bicim_var_mi("CanIncludeInClipboardHistory"))  # düz geri yükleme gizlilik eklemez
        pc.panoya_yaz("gizli")
        self.assertEqual(pc.panoyu_oku(), "gizli")
        for ad in ("ExcludeClipboardContentFromMonitorProcessing", "CanIncludeInClipboardHistory",
                   "CanUploadToCloudClipboard"):
            with self.subTest(bicim=ad):
                self.assertTrue(self.bicim_var_mi(ad))
        self.assertEqual(self.dword_oku("CanIncludeInClipboardHistory"), 0)
        self.assertEqual(self.dword_oku("CanUploadToCloudClipboard"), 0)

    def test_geri_yukleme(self):
        pc.panoyu_geri_yukle("eski")
        yedek = pc.panoyu_oku()
        pc.panoya_yaz("gizli mesaj ğüşiöç")
        self.assertEqual(pc.panoyu_oku(), "gizli mesaj ğüşiöç")
        pc.panoyu_geri_yukle(yedek)
        self.assertEqual(pc.panoyu_oku(), "eski")
        self.assertFalse(self.bicim_var_mi("CanIncludeInClipboardHistory"))

    def test_bos_yedek_panoyu_temizler(self):
        pc.panoya_yaz("gizli")
        pc.panoyu_geri_yukle(None)
        self.assertIsNone(pc.panoyu_oku())

    def test_son_temizlik_eski_kalmaz(self):
        pc.panoyu_geri_yukle("eski")
        pc.panoyu_geri_yukle(self.yedek)
        self.assertNotEqual(pc.panoyu_oku(), "eski")


if __name__ == "__main__":
    unittest.main()
