"""hassas.py testleri: her kalıp için pozitif/negatif, TC ve Luhn doğrulaması, maskeleme, öncelik."""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _ortam  # noqa: E402,F401
import hassas  # noqa: E402

GECERLI_TC = "10000000146"          # algoritmaya uyan örnek (gerçek kişi değil)
GECERLI_TC_2 = "12345678950"
GECERSIZ_TC = "12345678901"         # 10./11. hane kuralına uymuyor
GECERLI_KART = "4111 1111 1111 1111"  # Luhn'a uyan yaygın test kartı
GECERSIZ_KART = "4111 1111 1111 1112"
GECERLI_IBAN = "TR33 0006 1005 1978 6457 8413 26"


class ApiAnahtariTesti(unittest.TestCase):
    def kategori(self, metin):
        return hassas.tara(metin)["kategori"]

    def test_pozitifler(self):
        for metin in ("anahtarım sk-" + "abcdefghijklmnop1234 şu",
                      "sk-ant-" + "api03-abcdefghijklmnopqrst",
                      "OPENAI=sk-proj-" + "AbCdEfGhIjKlMnOp_12345",
                      "AIza" + "x" * 35,
                      "token ghp_" + "a1B2" * 8,
                      "xoxb-1234567890-abcdefghij",
                      "-----BEGIN RSA PRIVATE KEY-----\nMIIE...",
                      "-----BEGIN PRIVATE KEY-----"):
            with self.subTest(metin=metin[:30]):
                self.assertEqual(self.kategori(metin), "api_anahtari")

    def test_negatifler(self):
        for metin in ("sk-kisa",                                   # çok kısa
                      "risk-assessment-frameworkabcdefghijkl",      # sk- başka sözcüğün ortasında
                      "AIza kısa",
                      "ghp_kisa",
                      "Merhaba, nasılsın?",
                      "-----BEGIN CERTIFICATE-----"):               # özel anahtar değil
            with self.subTest(metin=metin[:30]):
                self.assertEqual(self.kategori(metin), "yok")


class FinansalTesti(unittest.TestCase):
    def test_iban_bosluklu_ve_bitisik(self):
        for metin in (GECERLI_IBAN, GECERLI_IBAN.replace(" ", ""), "iban: " + GECERLI_IBAN.lower() + " lütfen"):
            with self.subTest(metin=metin):
                s = hassas.tara(metin)
                self.assertEqual((s["kategori"], s["eslesme_sayisi"]), ("finansal", 1))

    def test_iban_negatif(self):
        for metin in ("TR33 0006 1005 1978 6457 8413",      # eksik hane
                      "TR33 0006 1005 1978 6457 8413 2678",  # fazla hane (rakam dizisi sürüyor)
                      "TRY 1000 TL"):
            with self.subTest(metin=metin):
                self.assertEqual(hassas.tara(metin)["kategori"], "yok")

    def test_kart_luhn(self):
        for kart in (GECERLI_KART, "4111111111111111", "5555-5555-5555-4444"):
            with self.subTest(kart=kart):
                self.assertEqual(hassas.tara(f"kartım {kart} son kullanma 12/30")["kategori"], "finansal")
        self.assertEqual(hassas.tara(f"kart {GECERSIZ_KART}")["kategori"], "yok")
        self.assertEqual(hassas.tara("0000 0000 0000 0000")["kategori"], "yok")
        self.assertEqual(hassas.tara("4111 1111 1111 111")["kategori"], "yok")  # 15 hane

    def test_luhn_birim(self):
        self.assertTrue(hassas.luhn_gecerli_mi("4111 1111 1111 1111"))
        self.assertTrue(hassas.luhn_gecerli_mi("5555-5555-5555-4444"))
        self.assertFalse(hassas.luhn_gecerli_mi("4111111111111112"))
        self.assertFalse(hassas.luhn_gecerli_mi("1111111111111111"))
        self.assertFalse(hassas.luhn_gecerli_mi("123"))

    def test_iban_icindeki_rakamlar_kart_sayilmaz(self):
        s = hassas.tara("iban " + GECERLI_IBAN)
        self.assertEqual(s["eslesme_sayisi"], 1)


class KimlikTesti(unittest.TestCase):
    def test_tc_algoritmasi_birim(self):
        self.assertTrue(hassas.tc_kimlik_gecerli_mi(GECERLI_TC))
        self.assertTrue(hassas.tc_kimlik_gecerli_mi(GECERLI_TC_2))
        self.assertFalse(hassas.tc_kimlik_gecerli_mi(GECERSIZ_TC))
        self.assertFalse(hassas.tc_kimlik_gecerli_mi("01234567890"))  # ilk hane 0 olamaz
        self.assertFalse(hassas.tc_kimlik_gecerli_mi("1234567890"))   # 10 hane
        # 11. hane yanlışsa (10. hane doğru) reddedilir
        self.assertFalse(hassas.tc_kimlik_gecerli_mi(GECERLI_TC[:10] + "7"))
        # 10. hane yanlışsa reddedilir
        self.assertFalse(hassas.tc_kimlik_gecerli_mi(GECERLI_TC[:9] + "5" + GECERLI_TC[10]))

    def test_tara_gecerli_tc(self):
        for metin in (f"TC kimlik no: {GECERLI_TC}", f"{GECERLI_TC_2} benim", f"({GECERLI_TC})"):
            with self.subTest(metin=metin):
                self.assertEqual(hassas.tara(metin)["kategori"], "kimlik")

    def test_tara_gecersiz_ya_da_baska_sayi(self):
        for metin in (f"numara {GECERSIZ_TC}",
                      "telefon 05321234567",            # 0 ile başlar
                      "tarih 2026-10-11",
                      "toplam 123456789012345 TL",      # 15 haneli sayı içinde 11 haneli değil
                      f"sipariş {GECERLI_TC}9"):        # 12 hane
            with self.subTest(metin=metin):
                self.assertEqual(hassas.tara(metin)["kategori"], "yok")


class ParolaTesti(unittest.TestCase):
    def test_anahtar_sozcuk_ve_deger(self):
        for metin in ("parola: Gizli123", "Parola = 'Gizli123'", "ŞİFRE: abc123xyz", "şifre=abc123", "Şifresi: abc123",
                      "password: hunter2", "PASSWORD=hunter2", "pin=1234", "PIN: 4821", "pwd: abcdef"):
            with self.subTest(metin=metin):
                self.assertEqual(hassas.tara(metin)["kategori"], "parola")

    def test_negatifler(self):
        for metin in ("parola nedir?", "şifre sıfırlama nasıl yapılır", "ping: yes", "pin kodu unutuldu",
                      "password manager önerir misin", "parola:", "şifre: x"):
            with self.subTest(metin=metin):
                self.assertEqual(hassas.tara(metin)["kategori"], "yok")

    def test_deger_ayni_satirda_aranir(self):
        self.assertEqual(hassas.tara("parola:\nyarın görüşürüz")["kategori"], "yok")

    def test_eposta_parola_cifti(self):
        for metin in ("giriş ali@ornek.com:Gizli123! dene", "ali.veli@ornek.com / Parola2024", "ali@ornek.com;S3cret#Pw"):
            with self.subTest(metin=metin):
                s = hassas.tara(metin)
                self.assertEqual((s["kategori"], s["eslesme_sayisi"]), ("parola", 1))

    def test_eposta_tek_basina_veya_duz_metin(self):
        for metin in ("bana ali@ornek.com adresinden yaz", "ali@ornek.com, toplantı yarın", "ali@ornek.com: yarın görüşelim",
                      "ali@ornek.com: https://ornek.com/sayfa", "ali@ornek.com: veli@ornek.com"):
            with self.subTest(metin=metin):
                self.assertEqual(hassas.tara(metin)["kategori"], "yok")


class SonucBicimiTesti(unittest.TestCase):
    def test_yok(self):
        self.assertEqual(hassas.tara("Merhaba dünya"),
                         {"kategori": "yok", "eslesme_sayisi": 0, "ornek": "", "kategoriler": []})
        self.assertEqual(hassas.tara("")["kategori"], "yok")
        self.assertEqual(hassas.tara(None)["kategori"], "yok")

    def test_maskeleme_ilk_dort_karakter(self):
        anahtar = "sk-" + "abcdefghijklmnop1234"
        s = hassas.tara("anahtar: " + anahtar)
        self.assertEqual(s["ornek"], "sk-a***")
        self.assertNotIn("bcdefgh", repr(s))
        self.assertEqual(hassas.maskele("12345678901"), "1234***")
        self.assertEqual(hassas.maskele("ab"), "ab***")

    def test_parola_maskesi_degeri_sizdirmaz(self):
        s = hassas.tara("password: hunter2xyz")
        self.assertEqual(s["ornek"], "pass***")
        self.assertNotIn("hunter", repr(s))

    def test_eslesme_sayisi_ayni_kategoride(self):
        s = hassas.tara(f"{GECERLI_TC} ve {GECERLI_TC_2}")
        self.assertEqual((s["kategori"], s["eslesme_sayisi"]), ("kimlik", 2))
        s = hassas.tara("sk-" + "a" * 20 + " ve sk-" + "b" * 20 + " ve ghp_" + "c" * 30)
        self.assertEqual((s["kategori"], s["eslesme_sayisi"]), ("api_anahtari", 3))

    def test_oncelik_api_parola_kimlik_finansal(self):
        karisik = f"{GECERLI_IBAN} {GECERLI_TC} parola: Gizli123 sk-{'a' * 20}"
        s = hassas.tara(karisik)
        self.assertEqual(s["kategori"], "api_anahtari")
        self.assertEqual(s["kategoriler"], ["api_anahtari", "parola", "kimlik", "finansal"])
        self.assertEqual(hassas.tara(f"{GECERLI_IBAN} {GECERLI_TC} parola: Gizli123")["kategori"], "parola")
        self.assertEqual(hassas.tara(f"{GECERLI_IBAN} {GECERLI_TC}")["kategori"], "kimlik")
        self.assertEqual(hassas.tara(GECERLI_IBAN)["kategori"], "finansal")

    def test_aciklama_metinleri(self):
        beklenen = {"api_anahtari": "bir API anahtarı", "parola": "bir parola",
                    "kimlik": "bir T.C. kimlik numarası", "finansal": "bir IBAN ya da kart numarası"}
        for kategori, metin in beklenen.items():
            self.assertEqual(hassas.ACIKLAMALAR[kategori], metin)
            self.assertEqual(hassas.uyari_metni({"kategori": kategori}), metin)
        self.assertIsNone(hassas.uyari_metni({"kategori": "yok"}))

    def test_cok_uzun_metin_hizli(self):
        baslangic = time.monotonic()
        for metin in ("a" * 500000, "a@" * 100000, "1" * 300000, "sk-" + "a" * 300000, "pin " * 100000):
            hassas.tara(metin)
        self.assertLess(time.monotonic() - baslangic, 10)


if __name__ == "__main__":
    unittest.main()
