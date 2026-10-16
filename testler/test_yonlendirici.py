"""yonlendirici.py testleri: tür/zorluk sınıflandırma, yonlendirme.json yüklemesi (motor + sınıf), model seçimi."""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

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
                    self.assertEqual(len(liste), 3, "her sırada üç motor da var")
                    self.assertEqual({t["motor"] for t in liste}, set(y.MOTORLAR))
                    self.assertTrue(all(t["sinif"] in y.SINIFLAR for t in liste))

    def test_varsayilan_tercih_sirasi(self):
        k, _ = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        sira = lambda tur, z: [(t["motor"], t["sinif"]) for t in y.tercihler(k, tur, z)]  # noqa: E731
        # basit → hızlı sınıf: gemini › codex › claude
        self.assertEqual(sira("sohbet", "basit"), [("gemini", "hizli"), ("codex", "hizli"), ("claude", "hizli")])
        # orta → dengeli: claude › codex › gemini; zor → güçlü: claude › codex › gemini
        self.assertEqual(sira("sohbet", "orta"), [("claude", "dengeli"), ("codex", "dengeli"), ("gemini", "dengeli")])
        self.assertEqual(sira("sohbet", "zor"), [("claude", "guclu"), ("codex", "guclu"), ("gemini", "guclu")])
        for z, sinif in (("basit", "hizli"), ("orta", "dengeli"), ("zor", "guclu")):
            self.assertEqual(sira("kod", z)[0], ("claude", sinif), "kod: önce claude")
        for z in y.ZORLUKLAR:
            self.assertEqual(sira("ceviri", z)[0], ("gemini", "hizli"))
            self.assertEqual(sira("ozet", z)[0], ("gemini", "hizli"))
        self.assertEqual(sira("arastirma", "zor")[0], ("gemini", "guclu"))
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
            "varsayilan": {"basit": [{"motor": "claude", "sinif": "hizli"}, {"motor": "yok", "sinif": "hizli"},
                                     {"motor": "gemini"}, "metin", {"motor": "codex", "sinif": "cok-hizli"},
                                     {"site": "gemini", "model_icerir": "flash"}],     # eski biçim geçersiz sayılır
                           "orta": "liste degil"},
            "turler": {"kod": {"zor": [{"motor": "gemini", "sinif": "guclu"}], "cok_zor": [], "orta": []},
                       "bilinmeyen": {"hepsi": []}, "ozet": "x"},
        }
        k, uyarilar = y.kurallari_dogrula(ham)
        self.assertEqual(k["varsayilan"]["basit"], [{"motor": "claude", "sinif": "hizli"}])
        self.assertEqual(k["varsayilan"]["orta"], y.YERLESIK["varsayilan"]["orta"])    # geçersiz: yerleşik
        self.assertEqual(k["varsayilan"]["zor"], y.YERLESIK["varsayilan"]["zor"])      # eksik: yerleşik
        self.assertEqual(k["turler"], {"kod": {"zor": [{"motor": "gemini", "sinif": "guclu"}]}})
        self.assertGreaterEqual(len(uyarilar), 5)

    def test_tamamen_eski_biçim_yerlesige_duser(self):
        eski = {"varsayilan": {z: [{"site": "claude", "model_icerir": "sonnet"}] for z in y.ZORLUKLAR}}
        k, uyarilar = y.kurallari_dogrula(eski)
        self.assertEqual(k["varsayilan"], y.YERLESIK["varsayilan"])
        self.assertEqual(len(uyarilar), 3)

    def test_ozel_dosya_etkili_olur(self):
        ozel = {"varsayilan": y.YERLESIK["varsayilan"],
                "turler": {"sohbet": {"hepsi": [{"motor": "codex", "sinif": "guclu"}]}}}
        with tempfile.TemporaryDirectory() as klasor:
            dosya = Path(klasor) / "y.json"
            dosya.write_text(json.dumps(ozel), "utf-8")
            k, uyarilar = y.kurallari_yukle(dosya)
        self.assertEqual(uyarilar, [])
        o = y.oner("selam", k)["oneriler"][0]
        self.assertEqual((o["motor"], o["sinif"]), ("codex", "guclu"))

    def test_tablo_21_satir(self):
        k, _ = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        t = y.tablo(k)
        self.assertEqual(len(t), len(y.TURLER) * len(y.ZORLUKLAR))
        satir = next(r for r in t if r["tur"] == "kod" and r["zorluk"] == "basit")
        self.assertEqual((satir["tur_ad"], satir["zorluk_ad"]), ("kod", "basit"))
        self.assertEqual(satir["tercihler"][0], {"motor": "claude", "motor_ad": "Claude", "sinif": "hizli", "sinif_ad": "hızlı"})


class KullaniciKopyasiTesti(unittest.TestCase):
    """yonlendirme.json kullanıcı veri klasöründedir; güncelleme (şablonun değişmesi) kullanıcı kopyasına dokunmaz."""

    def setUp(self):
        import os
        from unittest import mock
        self.klasor = Path(tempfile.mkdtemp(prefix="yzyon_"))
        self.addCleanup(__import__("shutil").rmtree, self.klasor, True)
        self.kopya = self.klasor / "veri" / "yonlendirme.json"
        self.sablon = self.klasor / "paket" / "yonlendirme.json"
        self.sablon.parent.mkdir()
        self.sablon.write_bytes((y.KOK / "yonlendirme.json").read_bytes())
        for yama in (mock.patch.dict(os.environ, {"YZ_YONLENDIRME": str(self.kopya)}),
                     mock.patch.object(y, "YONLENDIRME_DOSYASI", self.kopya),
                     mock.patch.object(y, "SABLON_DOSYASI", self.sablon)):
            yama.start()
            self.addCleanup(yama.stop)

    def test_varsayilan_yol_veri_klasorunde(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"YZ_YONLENDIRME": "", "YZ_VERI_KLASORU": str(self.klasor / "v")}):
            self.assertEqual(y.varsayilan_yonlendirme_dosyasi(), self.klasor / "v" / "yonlendirme.json")
        self.assertNotEqual(y.varsayilan_yonlendirme_dosyasi().parent, y.KOK)

    def test_ilk_okumada_sablon_kopyalanir(self):
        self.assertFalse(self.kopya.exists())
        k, uyarilar = y.kurallari_yukle()
        self.assertEqual(uyarilar, [])
        self.assertEqual(self.kopya.read_bytes(), self.sablon.read_bytes())
        self.assertEqual(k["varsayilan"]["basit"][0]["motor"], "gemini")

    def test_guncelleme_sonrasi_kullanici_kopyasi_aynen_kalir(self):
        y.kurallari_yukle()
        kullanici = json.loads(self.kopya.read_text("utf-8"))
        kullanici["varsayilan"]["basit"] = [{"motor": "claude", "sinif": "hizli"}]
        self.kopya.write_text(json.dumps(kullanici, ensure_ascii=False, indent=2), "utf-8")
        once = self.kopya.read_bytes()
        # yeni sürüm: paketteki şablon değişti (ör. varsayılan sıra başka)
        yeni = json.loads(self.sablon.read_text("utf-8"))
        yeni["varsayilan"]["basit"] = [{"motor": "codex", "sinif": "hizli"}]
        self.sablon.write_text(json.dumps(yeni), "utf-8")
        k, _ = y.kurallari_yukle()
        y.kullanici_kopyasini_hazirla()
        self.assertEqual(self.kopya.read_bytes(), once)
        self.assertEqual(k["varsayilan"]["basit"][0]["motor"], "claude")

    def test_sablon_yoksa_yerlesige_duser(self):
        self.sablon.unlink()
        k, uyarilar = y.kurallari_yukle()
        self.assertFalse(self.kopya.exists())
        self.assertTrue(uyarilar)
        self.assertEqual(k["varsayilan"]["basit"][0]["motor"], "gemini")


class OneriTesti(unittest.TestCase):
    def test_oner_bicimi(self):
        k, _ = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        o = y.oner("Bu makaleyi özetle", k)
        self.assertEqual((o["tur"], o["zorluk"], o["kaynak"]), ("ozet", "basit", "kural"))
        self.assertEqual((o["tur_ad"], o["zorluk_ad"]), ("özet", "basit"))
        self.assertEqual([x["motor"] for x in o["oneriler"]], ["gemini", "claude", "codex"])
        self.assertEqual(o["oneriler"][0]["sinif"], "hizli")
        self.assertEqual((o["oneriler"][0]["motor_ad"], o["oneriler"][0]["sinif_ad"]), ("Gemini", "hızlı"))
        self.assertIn("1. tercih", o["oneriler"][0]["sebep"])
        self.assertIn("özet", o["oneriler"][0]["sebep"])
        self.assertNotIn("model", o["oneriler"][0], "model adı burada uydurulmaz; motorun listesinden seçilir")

    def test_zor_arastirma_once_gemini_guclu(self):
        k, _ = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        o = y.oner("Elektrikli araçları kapsamlı karşılaştır. " + "a" * 300, k)
        self.assertEqual((o["tur"], o["zorluk"]), ("arastirma", "zor"))
        self.assertEqual((o["oneriler"][0]["motor"], o["oneriler"][0]["sinif"]), ("gemini", "guclu"))

    def test_dis_siniflandirma_kullanilir_gecersizse_kurala_doner(self):
        k, _ = y.kurallari_yukle(y.KOK / "yonlendirme.json")
        o = y.oner("Bu makaleyi özetle", k, sinif={"tur": "kod", "zorluk": "zor"}, kaynak="jev")
        self.assertEqual((o["tur"], o["zorluk"], o["kaynak"]), ("kod", "zor", "jev"))
        self.assertEqual(o["oneriler"][0]["motor"], "claude")
        o = y.oner("Bu makaleyi özetle", k, sinif={"tur": "yok", "zorluk": "zor"}, kaynak="jev")
        self.assertEqual((o["tur"], o["kaynak"]), ("ozet", "kural"))

    def test_kural_verilmezse_dosyadan_yuklenir(self):
        self.assertEqual(y.oner("Merhaba")["oneriler"][0]["motor"], "gemini")


class ModelSecTesti(unittest.TestCase):
    MODELLER = [{"id": "h", "ad": "Hızlı", "sinif": "hizli"}, {"id": "d1", "ad": "Dengeli 1", "sinif": "dengeli"},
                {"id": "d2", "ad": "Dengeli 2", "sinif": "dengeli"}, {"id": "g", "ad": "Güçlü", "sinif": "guclu"}]

    def test_sinifa_gore_ilk_model(self):
        self.assertEqual(y.model_sec(self.MODELLER, "hizli")["id"], "h")
        self.assertEqual(y.model_sec(self.MODELLER, "dengeli")["id"], "d1")
        self.assertEqual(y.model_sec(self.MODELLER, "guclu")["id"], "g")

    def test_tercih_edilen_model_oncelikli(self):
        self.assertEqual(y.model_sec(self.MODELLER, "dengeli", "d2")["id"], "d2")
        self.assertEqual(y.model_sec(self.MODELLER, "hizli", "d2")["id"], "d2", "kullanıcı başka sınıftan da seçebilir")
        self.assertEqual(y.model_sec(self.MODELLER, "hizli", "yok")["id"], "h", "listede olmayan tercih yok sayılır")

    def test_sinif_bossa_en_yakin_sinif(self):
        yalniz_dengeli = [{"id": "d", "ad": "D", "sinif": "dengeli"}]
        for sinif in y.SINIFLAR:
            self.assertEqual(y.model_sec(yalniz_dengeli, sinif)["id"], "d")
        self.assertEqual(y.model_sec([{"id": "g", "sinif": "guclu"}, {"id": "h", "sinif": "hizli"}], "dengeli")["id"], "g")
        self.assertEqual(y.model_sec([{"id": "x"}], "guclu")["id"], "x", "sınıfsız model yine de verilir")

    def test_bos_ya_da_bozuk_liste(self):
        for liste in ([], None, [None, 5, {"ad": "kimliksiz"}, {"id": ""}]):
            self.assertIsNone(y.model_sec(liste, "dengeli"))


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
