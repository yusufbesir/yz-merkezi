"""yonlendirici.py testleri: tür/zorluk sınıflandırma, yonlendirme.json yüklemesi, model eşleştirme."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _ortam  # noqa: E402,F401
import yonlendirici as y  # noqa: E402


def sinif(metin):
    s = y.siniflandir(metin)
    return s["tur"], s["zorluk"]


class TurTesti(unittest.TestCase):
    def test_turler(self):
        ornekler = {
            "Merhaba, nasılsın?": "sohbet",
            "Bugün hava nasıl olur sence?": "sohbet",
            "Bu fonksiyon neden hata veriyor?": "kod",                    # kod, araştırmadan ("neden") önce gelir
            "Python'da liste nasıl sıralanır": "kod",
            "SQL sorgusunu düzelt": "kod",
            "JavaScript ile bir buton yap": "kod",
            "```\nprint(1)\n```": "kod",
            "Şu cümleyi İngilizceye çevir: merhaba": "ceviri",
            "translate this text": "ceviri",
            "Bunu Türkçeye aktar": "ceviri",
            "Bu makaleyi özetle": "ozet",
            "Kısaca anlatır mısın": "ozet",
            "Elektrikli araçları karşılaştır": "arastirma",
            "Gökyüzü neden mavi": "arastirma",
            "Bu konuda kaynak göster": "arastirma",
            "Patrona bir mail yaz": "yazi",
            "Blog için bir taslak hazırla": "yazi",
            "Makale giriş paragrafı lazım": "yazi",
            "12 + 30 kaç eder": "matematik",
            "3x = 12 denklemini çöz": "matematik",
            "2*5=10 mu": "matematik",
            "100 / 4": "matematik",
            "integral hesapla": "matematik",
        }
        for metin, beklenen in ornekler.items():
            with self.subTest(metin=metin):
                self.assertEqual(sinif(metin)[0], beklenen)

    def test_oncelik_sirasi(self):
        self.assertEqual(sinif("Bu python kodunu İngilizceye çevir")[0], "kod")
        self.assertEqual(sinif("Metni çevir ve özetle")[0], "ceviri")
        self.assertEqual(sinif("Özetle ve kaynakları karşılaştır")[0], "ozet")
        self.assertEqual(sinif("Kaynak göstererek makale yaz")[0], "arastirma")

    def test_turkce_buyuk_kucuk_harf(self):
        self.assertEqual(sinif("ŞUNU ÖZETLE")[0], "ozet")
        self.assertEqual(sinif("İNGİLİZCEYE ÇEVİR")[0], "ceviri")
        self.assertEqual(sinif("ARAŞTIR")[0], "arastirma")

    def test_yanlis_pozitif_azaltma(self):
        self.assertEqual(sinif("yazılım nedir")[0], "sohbet")      # "yaz" sözcük başı ama yazılım
        self.assertEqual(sinif("Tarih: 2026-10-11")[0], "sohbet")  # tireli tarih matematik değil
        self.assertEqual(sinif("mysql")[0], "sohbet")              # sözcük ortasında "sql"

    def test_normallestir(self):
        self.assertEqual(y.normallestir("Özetle ÇEVİR Işık"), "ozetle cevir isik")


class ZorlukTesti(unittest.TestCase):
    def test_uzunluk_esikleri(self):
        self.assertEqual(sinif("a" * 199)[1], "basit")
        self.assertEqual(sinif("a" * 200)[1], "orta")
        self.assertEqual(sinif("a" * 1199)[1], "orta")
        self.assertEqual(sinif("a" * 1200)[1], "zor")

    def test_bosluklar_uzunluga_sayilmaz(self):
        self.assertEqual(sinif("   " + "a" * 190 + "   \n\n")[1], "basit")

    def test_zorlastirici_sozcuk_bir_kademe(self):
        self.assertEqual(sinif("Kısa bir analiz yap")[1], "orta")
        self.assertEqual(sinif("Ayrıntılı anlat")[1], "orta")
        self.assertEqual(sinif("Kapsamlı bir strateji ve mimari planı")[1], "orta")  # sözcükler üst üste +1 değil
        self.assertEqual(sinif("Analiz " + "a" * 300)[1], "zor")                       # orta + 1

    def test_cok_adimli(self):
        self.assertEqual(sinif("Önce dosyayı oku, sonra düzelt")[1], "orta")
        self.assertEqual(sinif("1. dosyayı oku\n2. hatayı bul\n3. düzelt")[1], "orta")
        self.assertEqual(sinif("- bir\n- iki\n- üç\n- dört")[1], "orta")
        self.assertEqual(sinif("- bir\n- iki")[1], "basit")                            # 3'ten az madde
        self.assertEqual(sinif("Önce oku sonra özetle, ayrıntılı olsun")[1], "zor")   # çok adım + zorlaştırıcı

    def test_en_cok_zor(self):
        self.assertEqual(sinif("Önce analiz et, sonra plan yap. " + "a" * 1500)[1], "zor")

    def test_siniflandir_sonucu(self):
        self.assertEqual(set(y.siniflandir("x")), {"tur", "zorluk"})
        self.assertEqual(y.siniflandir("")["zorluk"], "basit")
        self.assertEqual(y.siniflandir(None)["tur"], "sohbet")


class KuralDosyasiTesti(unittest.TestCase):
    def test_depodaki_dosya_gecerli_ve_eksiksiz(self):
        kurallar, uyarilar = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        self.assertEqual(uyarilar, [])
        for tur in y.TURLER:
            for z in y.ZORLUKLAR:
                with self.subTest(tur=tur, zorluk=z):
                    liste = y.tercihler(kurallar, tur, z)
                    self.assertTrue(liste)
                    self.assertTrue(all(t["site"] in y.SITELER and t["model_icerir"] for t in liste))

    def test_varsayilan_tercih_sirasi(self):
        k, _ = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        sira = lambda tur, z: [(t["site"], t["model_icerir"]) for t in y.tercihler(k, tur, z)]  # noqa: E731
        self.assertEqual(sira("sohbet", "basit"), [("gemini", "flash"), ("chatgpt", "mini"), ("claude", "haiku")])
        self.assertEqual(sira("sohbet", "orta"), [("claude", "sonnet"), ("chatgpt", "gpt"), ("gemini", "pro")])
        self.assertEqual(sira("sohbet", "zor"), [("claude", "opus"), ("chatgpt", "pro"), ("gemini", "pro")])
        for z in y.ZORLUKLAR:
            self.assertEqual(sira("kod", z)[0][0], "claude", "kod: önce claude")
            self.assertEqual(sira("ceviri", z)[0], ("gemini", "flash"))
            self.assertEqual(sira("ozet", z)[0], ("gemini", "flash"))
        self.assertEqual(sira("arastirma", "zor")[0], ("gemini", "pro"))
        self.assertEqual(sira("arastirma", "basit"), sira("sohbet", "basit"))  # yalnızca zor için özel

    def test_dosya_yok_yerlesige_duser(self):
        with tempfile.TemporaryDirectory() as klasor:
            k, uyarilar = y.kurallari_yukle(Path(klasor) / "yok.json")
        self.assertEqual(k["varsayilan"], y.YERLESIK["varsayilan"])
        self.assertTrue(uyarilar and "bulunamadı" in uyarilar[0])

    def test_bozuk_json_yerlesige_duser(self):
        with tempfile.TemporaryDirectory() as klasor:
            dosya = Path(klasor) / "y.json"
            dosya.write_text("{bu json degil", "utf-8")
            k, uyarilar = y.kurallari_yukle(dosya)
            self.assertEqual(k["varsayilan"], y.YERLESIK["varsayilan"])
            self.assertIn("okunamadı", uyarilar[0])
            dosya.write_text("[1, 2]", "utf-8")
            k, uyarilar = y.kurallari_yukle(dosya)
            self.assertEqual(k["varsayilan"], y.YERLESIK["varsayilan"])
            self.assertTrue(uyarilar)

    def test_gecersiz_bolumler_ayiklanir(self):
        ham = {
            "varsayilan": {"basit": [{"site": "claude", "model_icerir": "haiku"}, {"site": "yok", "model_icerir": "x"},
                                     {"site": "gemini"}, "metin", {"site": "chatgpt", "model_icerir": "  "}],
                           "orta": "liste degil"},
            "turler": {"kod": {"zor": [{"site": "gemini", "model_icerir": "pro"}], "cok_zor": [], "orta": []},
                       "bilinmeyen": {"hepsi": []}, "ozet": "x"},
        }
        k, uyarilar = y.kurallari_dogrula(ham)
        self.assertEqual(k["varsayilan"]["basit"], [{"site": "claude", "model_icerir": "haiku"}])
        self.assertEqual(k["varsayilan"]["orta"], y.YERLESIK["varsayilan"]["orta"])    # geçersiz: yerleşik
        self.assertEqual(k["varsayilan"]["zor"], y.YERLESIK["varsayilan"]["zor"])      # eksik: yerleşik
        self.assertEqual(k["turler"], {"kod": {"zor": [{"site": "gemini", "model_icerir": "pro"}]}})
        self.assertGreaterEqual(len(uyarilar), 5)

    def test_ozel_dosya_etkili_olur(self):
        ozel = {"varsayilan": y.YERLESIK["varsayilan"],
                "turler": {"sohbet": {"hepsi": [{"site": "chatgpt", "model_icerir": "Sonnet 5.5"}]}}}
        with tempfile.TemporaryDirectory() as klasor:
            dosya = Path(klasor) / "y.json"
            dosya.write_text(json.dumps(ozel), "utf-8")
            k, uyarilar = y.kurallari_yukle(dosya)
        self.assertEqual(uyarilar, [])
        self.assertEqual(y.oner("selam", k)["oneriler"][0]["model_icerir"], "Sonnet 5.5")

    def test_tablo_21_satir(self):
        k, _ = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        t = y.tablo(k)
        self.assertEqual(len(t), len(y.TURLER) * len(y.ZORLUKLAR))
        satir = next(r for r in t if r["tur"] == "kod" and r["zorluk"] == "basit")
        self.assertEqual((satir["tur_ad"], satir["zorluk_ad"]), ("kod", "basit"))
        self.assertEqual(satir["tercihler"][0]["site_ad"], "Claude")


class OneriTesti(unittest.TestCase):
    def test_oner_bicimi(self):
        k, _ = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        o = y.oner("Bu makaleyi özetle", k)
        self.assertEqual((o["tur"], o["zorluk"], o["kaynak"]), ("ozet", "basit", "kural"))
        self.assertEqual((o["tur_ad"], o["zorluk_ad"]), ("özet", "basit"))
        self.assertEqual([x["site"] for x in o["oneriler"]], ["gemini", "chatgpt", "claude"])
        self.assertEqual(o["oneriler"][0]["model_icerir"], "flash")
        self.assertEqual(o["oneriler"][0]["site_ad"], "Gemini")
        self.assertIn("1. tercih", o["oneriler"][0]["sebep"])
        self.assertIn("özet", o["oneriler"][0]["sebep"])
        self.assertNotIn("model", o["oneriler"][0], "model adı burada uydurulmaz; canlı menüden eşleştirilir")

    def test_zor_arastirma_once_gemini_pro(self):
        k, _ = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        o = y.oner("Elektrikli araçları kapsamlı karşılaştır. " + "a" * 300, k)
        self.assertEqual((o["tur"], o["zorluk"]), ("arastirma", "zor"))
        self.assertEqual((o["oneriler"][0]["site"], o["oneriler"][0]["model_icerir"]), ("gemini", "pro"))

    def test_kural_verilmezse_dosyadan_yuklenir(self):
        self.assertEqual(y.oner("Merhaba")["oneriler"][0]["site"], "gemini")


class ModelEslemeTesti(unittest.TestCase):
    MODELLER = [{"id": "a", "ad": "Gemini 3 Flash", "secili": True}, {"id": "b", "ad": "Gemini 3 Pro", "secili": False},
                {"id": "c", "ad": "Gemini Flash-Lite"}]

    def test_buyuk_kucuk_harf_duyarsiz_icerir(self):
        self.assertEqual(y.model_esles(self.MODELLER, "flash"), "Gemini 3 Flash")
        self.assertEqual(y.model_esles(self.MODELLER, "PRO"), "Gemini 3 Pro")
        self.assertEqual(y.model_esles(self.MODELLER, "3 pro"), "Gemini 3 Pro")

    def test_ilk_eslesme_menu_sirasindadir(self):
        self.assertEqual(y.model_esles(self.MODELLER, "gemini"), "Gemini 3 Flash")
        self.assertEqual(y.model_esles(self.MODELLER, "lite"), "Gemini Flash-Lite")

    def test_eslesme_yoksa_none(self):
        self.assertIsNone(y.model_esles(self.MODELLER, "opus"))
        self.assertIsNone(y.model_esles([], "flash"))
        self.assertIsNone(y.model_esles(None, "flash"))
        self.assertIsNone(y.model_esles(self.MODELLER, ""))
        self.assertIsNone(y.model_esles(self.MODELLER, "   "))

    def test_ad_listesi_ve_bozuk_kayitlar(self):
        self.assertEqual(y.model_esles(["GPT-5 mini", "GPT-5"], "mini"), "GPT-5 mini")
        self.assertEqual(y.model_esles([{"id": "x"}, None, 5, {"ad": "Claude Sonnet 5.5"}], "sonnet 5.5"), "Claude Sonnet 5.5")

    def test_turkce_harf(self):
        self.assertEqual(y.model_esles([{"ad": "Hızlı Model"}], "hızlı"), "Hızlı Model")


if __name__ == "__main__":
    unittest.main()
