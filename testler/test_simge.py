"""Simge testleri: SVG/PNG/ICO dosyaları var, 7 boyut tamam, ICO başlığı geçerli, SVG ayrışıyor ve yazı içermiyor."""
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
ARAYUZ = KOK / "arayuz-masaustu"
BOYUTLAR = [16, 24, 32, 48, 64, 128, 256]
PNG_IMZA = b"\x89PNG\r\n\x1a\n"
sys.path.insert(0, str(KOK / "araclar"))
import simge_uret  # noqa: E402


def ico_girdileri(veri):
    """ICO başlığını ve girdilerini okur: [(genislik, yukseklik, bit, boyut, ofset)]."""
    rezerve, tur, adet = struct.unpack("<HHH", veri[:6])
    assert (rezerve, tur) == (0, 1), "ICO başlığı geçersiz"
    girdiler = []
    for i in range(adet):
        w, h, _renk, _rez, _pl, bit, boyut, ofset = struct.unpack("<BBBBHHII", veri[6 + 16 * i:22 + 16 * i])
        girdiler.append((w or 256, h or 256, bit, boyut, ofset))
    return girdiler


class SimgeTesti(unittest.TestCase):
    def test_dosyalar_var(self):
        for ad in ("simge.svg", "simge-kucuk.svg", "simge.ico", "simge-256.png"):
            self.assertTrue((ARAYUZ / ad).is_file(), ad)
        self.assertTrue((KOK / "araclar" / "simge_uret.py").is_file())
        self.assertTrue((KOK / "kisayol-olustur.ps1").is_file())
        for ad in ("simge.svg", "simge.ico"):  # eski arayüz de aynı simgeyi kullanır
            self.assertEqual((KOK / "arayuz" / ad).read_bytes(), (ARAYUZ / ad).read_bytes(), ad)

    def test_png_256(self):
        veri = (ARAYUZ / "simge-256.png").read_bytes()
        self.assertEqual(simge_uret.png_boyutu(veri), (256, 256))

    def test_ico_yedi_boyut(self):
        veri = (ARAYUZ / "simge.ico").read_bytes()
        girdiler = ico_girdileri(veri)
        self.assertEqual([g[0] for g in girdiler], BOYUTLAR)
        for w, h, bit, boyut, ofset in girdiler:
            self.assertEqual(w, h)
            self.assertEqual(bit, 32)
            png = veri[ofset:ofset + boyut]
            self.assertEqual(len(png), boyut)
            self.assertEqual(png[:8], PNG_IMZA)
            self.assertEqual(simge_uret.png_boyutu(png), (w, h), f"{w} px girdisinin PNG boyutu uyuşmuyor")
        self.assertEqual(veri[6 + 16 * 6], 0)  # 256 px için genişlik baytı 0
        self.assertEqual(girdiler[-1][3], (ARAYUZ / "simge-256.png").stat().st_size)

    def test_ico_yazici(self):
        png = PNG_IMZA + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 256, 256) + b"x" * 10
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            hedef = Path(d) / "a.ico"
            simge_uret.ico_yaz([(256, png)], hedef)
            veri = hedef.read_bytes()
        (w, h, bit, boyut, ofset), = ico_girdileri(veri)
        self.assertEqual((w, h, bit, boyut, ofset), (256, 256, 32, len(png), 22))
        self.assertEqual(veri[22:], png)

    def test_svg_ayristirilir_ve_yazi_icermez(self):
        for ad in ("simge.svg", "simge-kucuk.svg"):
            kok = ET.parse(ARAYUZ / ad).getroot()
            self.assertTrue(kok.tag.endswith("svg"), ad)
            self.assertEqual(kok.get("viewBox"), "0 0 256 256", ad)
            etiketler = {e.tag.split("}")[-1] for e in kok.iter()}
            self.assertNotIn("text", etiketler, f"{ad} içinde <text> var")
            self.assertNotIn("image", etiketler, f"{ad} dış görsel içermemeli")

    def test_sunucular_simge_turlerini_taniyor(self):
        import _ortam  # noqa: F401
        import masaustu_sunucu
        import sunucu
        for tablo in (masaustu_sunucu.ICERIK, sunucu.ICERIK_TURLERI):
            self.assertEqual(tablo[".ico"], "image/x-icon")
            self.assertEqual(tablo[".png"], "image/png")
            self.assertEqual(tablo[".svg"], "image/svg+xml")

    def test_arayuzler_simgeye_bagli(self):
        for klasor in ("arayuz-masaustu", "arayuz"):
            html = (KOK / klasor / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="simge.svg" type="image/svg+xml"', html, klasor)
            self.assertIn('href="simge.ico" sizes="any"', html, klasor)
            self.assertNotIn('rel="icon" href="data:', html, klasor)


if __name__ == "__main__":
    unittest.main()
