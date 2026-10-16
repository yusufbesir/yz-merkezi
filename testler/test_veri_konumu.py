"""Veri konumu testleri: ayar dosyaları ve tarayıcı profili varsayılan olarak %LOCALAPPDATA%\\YZMerkezi altında,
ortam değişkenleri öncelikli; proje klasöründeki eski dosya/profil ilk açılışta bir kez taşınır.

Gerçek %LOCALAPPDATA% ve proje kökündeki gerçek dosyalara dokunulmaz: her şey geçici klasörlerde olur.
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(KOK))
import _ortam  # noqa: E402,F401  (gerçek ayar dosyalarını korur; sunucu modüllerinden önce)
import guvenlik  # noqa: E402
import masaustu_sunucu as ms  # noqa: E402
import tarayici  # noqa: E402

YZ_DEGISKENLERI = ("YZ_MASAUSTU_AYAR", "YZ_AYAR_DOSYASI", "YZ_TARAYICI_PROFILI", "YZ_VERI_KLASORU")

YOLLARI_YAZ = """
import json, masaustu_sunucu, sunucu, tarayici, guvenlik
print(json.dumps({"masaustu": str(masaustu_sunucu.AYAR_DOSYASI), "api": str(sunucu.AYAR_DOSYASI),
                  "profil": str(tarayici.PROFIL), "belirtec": str(guvenlik.belirtec_dosyasi())}))
"""


class VarsayilanYolTesti(unittest.TestCase):
    """Modüller yolları içe aktarılırken hesapladığından ayrı bir Python sürecinde denetlenir (dosya yazılmaz)."""

    def yollar(self, ortam):
        tam = {k: v for k, v in os.environ.items() if k not in YZ_DEGISKENLERI}
        tam.update(ortam)
        cikti = subprocess.run([sys.executable, "-c", YOLLARI_YAZ], cwd=str(KOK), env=tam,
                               capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(cikti.returncode, 0, cikti.stderr)
        return {k: Path(v) for k, v in json.loads(cikti.stdout.strip().splitlines()[-1]).items()}

    def test_ortam_degiskeni_yokken_localappdata_altinda(self):
        sahte_yerel = Path(tempfile.mkdtemp(prefix="yzyerel_"))
        self.addCleanup(shutil.rmtree, sahte_yerel, True)
        y = self.yollar({"LOCALAPPDATA": str(sahte_yerel)})
        klasor = sahte_yerel / "YZMerkezi"
        self.assertEqual(y["masaustu"], klasor / "masaustu-ayarlar.json")
        self.assertEqual(y["api"], klasor / "ayarlar.json")
        self.assertEqual(y["profil"], klasor / "tarayici-profili")
        self.assertEqual(y["belirtec"], klasor / "belirtec")
        for yol in y.values():
            self.assertNotEqual(yol.parent, KOK, "veri proje klasöründe olmamalı")
        self.assertEqual(list(sahte_yerel.iterdir()), [], "içe aktarma hiçbir dosya oluşturmamalı")

    def test_veri_klasoru_degiskeni(self):
        klasor = Path(tempfile.gettempdir()) / "yz-veri-deneme-yok"
        y = self.yollar({"YZ_VERI_KLASORU": str(klasor)})
        self.assertEqual({k: v.parent for k, v in y.items()}, dict.fromkeys(y, klasor))
        self.assertFalse(klasor.exists())

    def test_tek_tek_ortam_degiskenleri_oncelikli(self):
        ozel = Path(tempfile.gettempdir()) / "yz-ozel-deneme-yok"
        y = self.yollar({"YZ_VERI_KLASORU": str(ozel / "veri"), "YZ_MASAUSTU_AYAR": str(ozel / "m.json"),
                         "YZ_AYAR_DOSYASI": str(ozel / "a.json"), "YZ_TARAYICI_PROFILI": str(ozel / "p")})
        self.assertEqual((y["masaustu"], y["api"], y["profil"]), (ozel / "m.json", ozel / "a.json", ozel / "p"))


class TasimaTesti(unittest.TestCase):
    def setUp(self):
        self.kok = Path(tempfile.mkdtemp(prefix="yztasima_"))
        self.addCleanup(shutil.rmtree, self.kok, True)
        self.eski_proje = self.kok / "proje"
        self.yeni_veri = self.kok / "yerel" / "YZMerkezi"
        self.eski_proje.mkdir()
        ortam = mock.patch.dict(os.environ, {"YZ_VERI_KLASORU": str(self.yeni_veri)})
        ortam.start()
        self.addCleanup(ortam.stop)

    def eski_profil(self):
        profil = self.eski_proje / ".tarayici-profili"
        (profil / "Default").mkdir(parents=True)
        (profil / "Default" / "Cookies").write_bytes(b"cerez")
        (profil / "Local State").write_text("{}", "utf-8")
        return profil

    def test_dosya_tasinir(self):
        eski = self.eski_proje / "masaustu-ayarlar.json"
        eski.write_text('{"ayarlar": {"ad": "Yusuf"}}', "utf-8")
        yeni = self.yeni_veri / "masaustu-ayarlar.json"
        self.assertEqual(guvenlik.eski_veriyi_tasi(eski, yeni), yeni)
        self.assertFalse(eski.exists())
        self.assertEqual(json.loads(yeni.read_text("utf-8")), {"ayarlar": {"ad": "Yusuf"}})
        self.assertFalse(yeni.with_name(yeni.name + ".tasiniyor").exists())
        self.assertIn("Eski veri taşındı", (self.yeni_veri / "hata.log").read_text("utf-8"))

    def test_klasor_tasinir(self):
        eski = self.eski_profil()
        yeni = self.yeni_veri / "tarayici-profili"
        self.assertEqual(guvenlik.eski_veriyi_tasi(eski, yeni), yeni)
        self.assertFalse(eski.exists())
        self.assertEqual((yeni / "Default" / "Cookies").read_bytes(), b"cerez")
        self.assertTrue((yeni / "Local State").exists())

    def test_tek_seferlik_yenisi_varsa_dokunulmaz(self):
        eski = self.eski_proje / "ayarlar.json"
        eski.write_text('{"eski": 1}', "utf-8")
        yeni = self.yeni_veri / "ayarlar.json"
        yeni.parent.mkdir(parents=True)
        yeni.write_text('{"yeni": 1}', "utf-8")
        self.assertEqual(guvenlik.eski_veriyi_tasi(eski, yeni), yeni)
        self.assertEqual(json.loads(yeni.read_text("utf-8")), {"yeni": 1})
        self.assertTrue(eski.exists(), "yeni konumda veri varken eski dosya silinmemeli")

    def test_eskisi_yoksa_bir_sey_yapilmaz(self):
        yeni = self.yeni_veri / "ayarlar.json"
        self.assertEqual(guvenlik.eski_veriyi_tasi(self.eski_proje / "ayarlar.json", yeni), yeni)
        self.assertFalse(self.yeni_veri.exists())

    def test_kopyalama_basarisizsa_eski_yerde_kalinir(self):
        eski = self.eski_profil()
        yeni = self.yeni_veri / "tarayici-profili"
        with mock.patch.object(guvenlik.shutil, "copytree", side_effect=OSError("disk dolu")):
            self.assertEqual(guvenlik.eski_veriyi_tasi(eski, yeni), eski)
        self.assertTrue((eski / "Default" / "Cookies").exists())
        self.assertFalse(yeni.exists())

    @unittest.skipUnless(sys.platform == "win32", "Windows dosya kilidi")
    def test_kullanimdaki_profil_tasinmaz(self):
        import ctypes
        from ctypes import wintypes
        eski = self.eski_profil()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                         wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        # Chromium çalışırken profildeki "lockfile" paylaşımsız açıktır; aynısı taklit edilir.
        tutamac = kernel32.CreateFileW(str(eski / "lockfile"), 0x40000000, 0, None, 2, 0x80, None)
        self.assertNotEqual(tutamac, wintypes.HANDLE(-1).value)
        try:
            yeni = self.yeni_veri / "tarayici-profili"
            self.assertEqual(guvenlik.eski_veriyi_tasi(eski, yeni), eski)
            self.assertFalse(yeni.exists())
        finally:
            kernel32.CloseHandle(tutamac)
        self.assertEqual(guvenlik.eski_veriyi_tasi(eski, yeni), yeni)  # tarayıcı kapanınca taşınır

    def test_masaustu_sunucusu_acilista_tasir(self):
        eski_ayar = self.eski_proje / "masaustu-ayarlar.json"
        eski_ayar.write_text('{"sohbetler": []}', "utf-8")
        eski_profil = self.eski_profil()
        yeni_ayar, yeni_profil = self.yeni_veri / "masaustu-ayarlar.json", self.yeni_veri / "tarayici-profili"
        ortam = {k: v for k, v in os.environ.items() if k not in ("YZ_MASAUSTU_AYAR", "YZ_TARAYICI_PROFILI")}
        with mock.patch.dict(os.environ, ortam, clear=True), \
                mock.patch.object(ms, "ESKI_AYAR_DOSYASI", eski_ayar), mock.patch.object(ms, "AYAR_DOSYASI", yeni_ayar), \
                mock.patch.object(tarayici, "ESKI_PROFIL", eski_profil), mock.patch.object(tarayici, "PROFIL", yeni_profil):
            ms.eski_verileri_tasi()
            self.assertEqual((ms.AYAR_DOSYASI, tarayici.PROFIL), (yeni_ayar, yeni_profil))
        self.assertTrue(yeni_ayar.exists() and (yeni_profil / "Default" / "Cookies").exists())
        self.assertFalse(eski_ayar.exists() or eski_profil.exists())

    def test_ortam_degiskeni_verilmisse_tasinmaz(self):
        eski_ayar = self.eski_proje / "masaustu-ayarlar.json"
        eski_ayar.write_text("{}", "utf-8")
        ozel = self.kok / "ozel.json"
        with mock.patch.dict(os.environ, {"YZ_MASAUSTU_AYAR": str(ozel), "YZ_TARAYICI_PROFILI": str(self.kok / "p")}), \
                mock.patch.object(ms, "ESKI_AYAR_DOSYASI", eski_ayar), mock.patch.object(ms, "AYAR_DOSYASI", ozel), \
                mock.patch.object(tarayici, "ESKI_PROFIL", self.eski_proje / "yok"):
            ms.eski_verileri_tasi()
            self.assertEqual(ms.AYAR_DOSYASI, ozel)
        self.assertTrue(eski_ayar.exists())
        self.assertFalse(ozel.exists())


if __name__ == "__main__":
    unittest.main()
