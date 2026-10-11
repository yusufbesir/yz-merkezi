"""Masaüstü sürümünün hesaplama ve eşleştirme mantığı için testler (ekrana dokunmaz)."""
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


if __name__ == "__main__":
    unittest.main()
