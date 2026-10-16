"""motorlar paketi testleri: sahte motor betikleriyle (testler/sahte_motorlar/); gerçek CLI'lara istem GÖNDERİLMEZ.

Her motor `YZ_MOTOR_<ID>_EXE` ortam değişkeniyle sahte `.py` betiğine bağlanır. Çalışma klasörü, Codex ve Gemini
ev klasörleri geçici dizinlere yönlendirilir (gerçek ~/.codex, ~/.gemini ve %LOCALAPPDATA% ayarlarına dokunulmaz).
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _ortam  # noqa: E402,F401  (gerçek ayar dosyalarını korur; modüllerden önce)
import motorlar  # noqa: E402
from motorlar import taban  # noqa: E402

SAHTE = Path(__file__).resolve().parent / "sahte_motorlar"
BEKLENEN = "Merhaba dünya — ğüşıöç İ"


class MotorTestTabani(unittest.TestCase):
    motor_id = None

    def setUp(self):
        self.gecici = Path(tempfile.mkdtemp(prefix="yzmotor_"))
        self.addCleanup(shutil.rmtree, self.gecici, ignore_errors=True)
        (self.gecici / "gemini-ev" / ".gemini").mkdir(parents=True)
        (self.gecici / "gemini-ev" / ".gemini" / "oauth_creds.json").write_text("{\"x\": 1}", encoding="utf-8")
        (self.gecici / "codex-ev").mkdir()
        self.argv_dosyasi = self.gecici / "argv.json"
        ortam = {
            "YZ_MOTOR_CLAUDE_EXE": str(SAHTE / "sahte_claude.py"),
            "YZ_MOTOR_CODEX_EXE": str(SAHTE / "sahte_codex.py"),
            "YZ_MOTOR_GEMINI_EXE": str(SAHTE / "sahte_gemini.py"),
            "YZ_MOTOR_CALISMA": str(self.gecici / "calisma"),
            "GEMINI_CLI_HOME": str(self.gecici / "gemini-ev"),
            "CODEX_HOME": str(self.gecici / "codex-ev"),
            "SAHTE_ARGV_DOSYASI": str(self.argv_dosyasi),
            "SAHTE_GIRIS": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        yamalayici = mock.patch.dict(os.environ, ortam)
        yamalayici.start()
        self.addCleanup(yamalayici.stop)
        for ad in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_GENAI_USE_GCA"):
            os.environ.pop(ad, None)
        if self.motor_id:
            self.m = motorlar.MOTORLAR[self.motor_id]()

    def topla(self, istem="Selam", **secenekler):
        return list(self.m.sor(istem, **secenekler))

    def cagri(self):
        return json.loads(self.argv_dosyasi.read_text(encoding="utf-8"))


class OrtakDavranis:
    """Her motor için aynı beklentiler (alt sınıf MotorTestTabani ile birleşir)."""

    def test_parca_akisi_ve_bitti(self):
        olaylar = self.topla("Selam")
        turler = [o["tur"] for o in olaylar]
        self.assertEqual(turler[0], "durum")
        self.assertEqual(olaylar[0]["metin"], "düşünüyor…")
        self.assertEqual(turler.count("baslangic"), 1)
        self.assertLess(turler.index("baslangic"), turler.index("parca"))
        self.assertEqual(turler[-1], "bitti")
        parcalar = "".join(o["metin"] for o in olaylar if o["tur"] == "parca")
        self.assertIn(BEKLENEN, parcalar)
        bitti = olaylar[-1]
        self.assertIn(BEKLENEN, bitti["metin"])
        self.assertTrue(bitti["oturum"])
        self.assertIsInstance(bitti["sure"], float)
        baslangic = next(o for o in olaylar if o["tur"] == "baslangic")
        self.assertEqual(baslangic["oturum"], bitti["oturum"])

    def test_turkce_istem_standart_girdiden_gecer(self):
        istem = 'Çağrı "tırnak" & | % ^ < > ğüşİı\nikinci satır'
        olaylar = self.topla(istem)
        self.assertEqual(olaylar[-1]["tur"], "bitti")
        cagri = self.cagri()
        self.assertIn(istem, cagri["girdi"])
        self.assertNotIn(istem, " ".join(cagri["argv"]))

    def test_oturum_devami(self):
        ilk = self.topla("Selam")[-1]
        ikinci = self.topla("Devam", oturum=ilk["oturum"])[-1]
        self.assertEqual(ikinci["tur"], "bitti")
        self.assertEqual(ikinci["oturum"], ilk["oturum"])
        self.assertIn(ilk["oturum"], self.cagri()["argv"])

    def test_hata_olayi(self):
        olaylar = self.topla("HATA ver")
        self.assertEqual(olaylar[-1]["tur"], "hata")
        self.assertTrue(olaylar[-1]["mesaj"])
        self.assertNotIn("bitti", [o["tur"] for o in olaylar])

    def test_cokme_stderr_ozeti(self):
        olaylar = self.topla("COKME")
        son = olaylar[-1]
        self.assertEqual(son["tur"], "hata")
        self.assertIn("çıkış kodu 3", son["mesaj"])
        self.assertIn("ölümcül hata", son["mesaj"])

    def test_iptal(self):
        iptal = threading.Event()
        olaylar = []
        baslama = time.monotonic()
        for olay in self.m.sor("YAVAS yanıt", iptal=iptal):
            olaylar.append(olay)
            if olay["tur"] == "parca":
                iptal.set()
        self.assertLess(time.monotonic() - baslama, 15)
        self.assertEqual(olaylar[-1]["tur"], "hata")
        self.assertTrue(olaylar[-1].get("iptal"))
        self.assertEqual(olaylar[-1]["mesaj"], "İptal edildi.")

    def test_ilk_bayt_zaman_asimi(self):
        self.m.ilk_bayt_zaman_asimi = 1.0
        baslama = time.monotonic()
        olaylar = self.topla("SESSIZ")
        self.assertLess(time.monotonic() - baslama, 15)
        self.assertEqual(olaylar[-1]["tur"], "hata")
        self.assertIn("zaman aşımı", olaylar[-1]["mesaj"])

    def test_toplam_zaman_asimi(self):
        self.m.toplam_zaman_asimi = 2.0
        baslama = time.monotonic()
        olaylar = self.topla("YAVAS")
        self.assertLess(time.monotonic() - baslama, 15)
        self.assertEqual(olaylar[-1]["tur"], "hata")
        self.assertIn("bitmedi", olaylar[-1]["mesaj"])
        self.assertIn("parca", [o["tur"] for o in olaylar])

    def test_erken_kapatilan_generator_sureci_durdurur(self):
        akis = self.m.sor("YAVAS")
        for olay in akis:
            if olay["tur"] == "parca":
                break
        with mock.patch.object(taban, "sureci_durdur", wraps=taban.sureci_durdur) as durdur:
            akis.close()
        self.assertTrue(durdur.called)

    def test_hazir_mi_ve_onbellek(self):
        sonuc = self.m.hazir_mi()
        self.assertTrue(sonuc["hazir"], sonuc)
        self.assertTrue(sonuc["giris"])
        self.assertTrue(sonuc["surum"])
        with mock.patch.object(self.m, "_hazirlik_hesapla") as hesapla:
            self.assertEqual(self.m.hazir_mi(), sonuc)
            hesapla.assert_not_called()

    def test_exe_bulunamazsa(self):
        os.environ[self.m.ortam_degiskeni()] = str(self.gecici / "yok.exe")
        sonuc = self.m.hazir_mi(yenile=True)
        self.assertFalse(sonuc["hazir"])
        self.assertIn("kurulu değil", sonuc["sebep"])
        olaylar = self.topla("Selam")
        self.assertEqual([o["tur"] for o in olaylar], ["hata"])

    def test_modeller_siniflari(self):
        liste = self.m.modeller()
        self.assertTrue(liste)
        for model in liste:
            self.assertEqual(set(model), {"id", "ad", "sinif"})
            self.assertIn(model["sinif"], ("hizli", "dengeli", "guclu"))
        self.assertEqual({m["sinif"] for m in liste}, {"hizli", "dengeli", "guclu"})

    def test_calisma_klasoru_olusturulur(self):
        self.topla("Selam")
        self.assertTrue((self.gecici / "calisma").is_dir())


class ClaudeTestleri(OrtakDavranis, MotorTestTabani):
    motor_id = "claude"

    def test_sohbet_bayraklari(self):
        self.topla("Selam", model="sonnet", sistem="Kısa yanıt ver.")
        argv = self.cagri()["argv"]
        self.assertEqual(argv[0], "-p")
        self.assertNotIn("--bare", argv)
        for bayrak in ("--output-format", "stream-json", "--verbose", "--include-partial-messages",
                       "--strict-mcp-config"):
            self.assertIn(bayrak, argv)
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(argv[-2:], ["--tools", ""])
        self.assertEqual(argv[argv.index("--model") + 1], "sonnet")
        self.assertEqual(argv[argv.index("--append-system-prompt") + 1], "Kısa yanıt ver.")

    def test_varsayilan_sistem_turkce(self):
        self.topla("Selam")
        argv = self.cagri()["argv"]
        self.assertIn("Türkçe", argv[argv.index("--append-system-prompt") + 1])

    def test_model_bitti_olayinda(self):
        self.assertEqual(self.topla("Selam", model="opus")[-1]["model"], "opus")

    def test_giris_yok(self):
        os.environ["SAHTE_GIRIS"] = "0"
        sonuc = self.m.hazir_mi(yenile=True)
        self.assertFalse(sonuc["hazir"])
        self.assertFalse(sonuc["giris"])
        self.assertIn("Giriş gerekli", sonuc["sebep"])

    def test_ic_ice_oturum_degiskeni_temizlenir(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            self.assertNotIn("CLAUDECODE", self.m._ortam())

    def test_kismi_ileti_yoksa_tam_ileti_kullanilir(self):
        durum = {"oturum": None, "model": None, "parcalar": [], "tam_metin": None, "bitti": False, "hata": None}
        olaylar = self.m._satir_isle({"type": "assistant", "session_id": "s1",
                                      "message": {"content": [{"type": "text", "text": "Tam yanıt"}]}}, durum)
        self.assertEqual(olaylar, [{"tur": "parca", "metin": "Tam yanıt"}])
        self.assertEqual(durum["oturum"], "s1")


class CodexTestleri(OrtakDavranis, MotorTestTabani):
    motor_id = "codex"

    def test_yeni_konusma_bayraklari(self):
        self.topla("Selam", model="gpt-6-luna")
        argv = self.cagri()["argv"]
        self.assertEqual(argv[:2], ["exec", "--json"])
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
        self.assertIn("--skip-git-repo-check", argv)
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-luna")
        self.assertEqual(argv[-1], "-")

    def test_devam_bayraklari(self):
        self.topla("Selam", oturum="019a-oturum", model="gpt-6-sol")
        argv = self.cagri()["argv"]
        self.assertEqual(argv[:3], ["exec", "resume", "--json"])
        self.assertIn('sandbox_mode="read-only"', argv)
        self.assertEqual(argv[-2:], ["019a-oturum", "-"])

    def test_sistem_istemi_basa_eklenir(self):
        self.topla("Selam", sistem="Kısa yanıt ver.")
        girdi = self.cagri()["girdi"]
        self.assertTrue(girdi.startswith("[Talimat]\nKısa yanıt ver."))
        self.assertTrue(girdi.endswith("Selam"))

    def test_birden_cok_ileti_ve_durum(self):
        olaylar = self.topla("Selam")
        bitti = olaylar[-1]
        self.assertEqual(bitti["metin"], BEKLENEN + "\n\nİkinci ileti.")
        self.assertEqual(sum(1 for o in olaylar if o["tur"] == "durum"), 1)  # yinelenen "düşünüyor…" bastırılır

    def test_hata_mesaji_turkce_onekli(self):
        son = self.topla("HATA")[-1]
        self.assertEqual(son["mesaj"], "Codex: kota aşıldı")

    def test_model_listesi_onbellekten(self):
        (self.gecici / "codex-ev" / "models_cache.json").write_text(json.dumps({"models": [
            {"slug": "m-hizli", "display_name": "Hızlı", "description": "Fast and affordable", "visibility": "list",
             "priority": 2},
            {"slug": "m-guclu", "display_name": "Güçlü", "description": "Frontier intelligence", "visibility": "list",
             "priority": 1},
            {"slug": "m-orta", "display_name": "Orta", "description": "Workhorse", "visibility": "list",
             "priority": 3},
            {"slug": "gizli", "description": "x", "visibility": "hide"},
        ]}), encoding="utf-8")
        self.assertEqual(self.m.modeller(), [
            {"id": "m-guclu", "ad": "Güçlü", "sinif": "guclu"},
            {"id": "m-hizli", "ad": "Hızlı", "sinif": "hizli"},
            {"id": "m-orta", "ad": "Orta", "sinif": "dengeli"},
        ])

    def test_varsayilan_model_config_toml(self):
        (self.gecici / "codex-ev" / "config.toml").write_text('model = "gpt-x"\n[profiles]\nmodel = "y"\n',
                                                               encoding="utf-8")
        self.assertEqual(self.topla("Selam")[-1]["model"], "gpt-x")

    def test_giris_yok(self):
        os.environ["SAHTE_GIRIS"] = "0"
        sonuc = self.m.hazir_mi(yenile=True)
        self.assertFalse(sonuc["hazir"])
        self.assertIn("codex login", sonuc["sebep"])

    def test_exe_en_yeni_klasorden(self):
        kok = self.gecici / "yerel" / "OpenAI" / "Codex" / "bin"
        eski, yeni = kok / "a" / "codex.exe", kok / "b" / "codex.exe"
        for yol in (eski, yeni):
            yol.parent.mkdir(parents=True)
            yol.write_bytes(b"")
        os.utime(eski, (1, 1))
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(self.gecici / "yerel")}):
            self.assertEqual(Path(self.m._exe_bul()), yeni)


class GeminiTestleri(OrtakDavranis, MotorTestTabani):
    motor_id = "gemini"

    def test_bayraklar_ve_ortam(self):
        self.topla("Selam", model="gemini-2.5-flash")
        argv = self.cagri()["argv"]
        self.assertEqual(argv[argv.index("--output-format") + 1], "stream-json")
        self.assertIn("--skip-trust", argv)
        self.assertEqual(argv[argv.index("--approval-mode") + 1], "default")
        self.assertNotIn("--yolo", argv)
        self.assertNotIn("-p", argv)
        self.assertEqual(argv[argv.index("-m") + 1], "gemini-2.5-flash")
        ortam = self.m._ortam()
        self.assertEqual(ortam["GEMINI_CLI_TRUST_WORKSPACE"], "true")
        self.assertEqual(ortam["NO_BROWSER"], "true")

    def test_model_init_olayindan(self):
        self.assertEqual(self.topla("Selam")[-1]["model"], "gemini-2.5-pro")

    def test_giris_yoksa_surec_baslatilmaz(self):
        (self.gecici / "gemini-ev" / ".gemini" / "oauth_creds.json").unlink()
        sonuc = self.m.hazir_mi(yenile=True)
        self.assertFalse(sonuc["hazir"])
        self.assertFalse(sonuc["giris"])
        self.assertEqual(sonuc["sebep"],
                         "Giriş gerekli: terminalde `gemini` çalıştırıp Google hesabınla giriş yap.")
        with mock.patch.object(taban.subprocess, "Popen") as popen:
            olaylar = self.topla("Selam")
        popen.assert_not_called()
        self.assertEqual(olaylar[-1]["tur"], "hata")
        self.assertTrue(olaylar[-1]["giris_gerekli"])

    def test_api_anahtari_giris_sayilir(self):
        (self.gecici / "gemini-ev" / ".gemini" / "oauth_creds.json").unlink()
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "sahte"}):
            self.assertTrue(self.m._giris_denetle())

    def test_guven_hatasi_yorumlanir(self):
        self.assertIn("güvenmedi", self.m._hata_yorumla(55, "not running in a trusted directory"))
        self.assertIn("Giriş gerekli", self.m._hata_yorumla(41, ""))

    def test_cmd_yolu_reddedilir(self):
        cmd = self.gecici / "gemini.cmd"
        cmd.write_text("@echo off", encoding="utf-8")
        os.environ["YZ_MOTOR_GEMINI_EXE"] = str(cmd)
        with self.assertRaises(motorlar.MotorHatasi):
            self.m.komut_onu()

    def test_npm_klasorunden_js_bulunur(self):
        npm = self.gecici / "npm"
        js = npm / "node_modules" / "@google" / "gemini-cli" / "bundle" / "gemini.js"
        js.parent.mkdir(parents=True)
        js.write_text("", encoding="utf-8")
        (npm / "gemini.cmd").write_text("", encoding="utf-8")
        with mock.patch.object(shutil, "which", return_value=str(npm / "gemini.cmd")):
            self.assertEqual(Path(self.m._exe_bul()).resolve(), js.resolve())


class PaketTestleri(MotorTestTabani):
    def test_kayit_ve_tekil_ornek(self):
        self.assertEqual(set(motorlar.MOTORLAR), {"claude", "codex", "gemini"})
        self.assertIs(motorlar.motor("Claude"), motorlar.motor("claude"))
        for kimlik, sinif in motorlar.MOTORLAR.items():
            ornek = sinif()
            self.assertEqual(ornek.id, kimlik)
            self.assertTrue(ornek.ad and ornek.renk.startswith("#"))

    def test_bilinmeyen_motor(self):
        with self.assertRaises(motorlar.MotorHatasi):
            motorlar.motor("yok")

    def test_varsayilan_calisma_klasoru(self):
        os.environ.pop("YZ_MOTOR_CALISMA")
        yol = taban.calisma_klasoru_varsayilan()
        self.assertEqual(yol, Path(os.environ["YZ_VERI_KLASORU"]) / "calisma")
        self.assertTrue(yol.is_dir())


if __name__ == "__main__":
    unittest.main()
