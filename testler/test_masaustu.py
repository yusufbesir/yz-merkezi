"""masaustu_sunucu.py'nin site mantığı için hızlı testler: tarayıcıya ve ekrana dokunmaz (sahte bağlantılarla)."""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cdp  # noqa: E402
import masaustu_sunucu as ms  # noqa: E402
import siteler  # noqa: E402


class SahteBaglanti:
    """degerlendir() çağrılarını JS metnine göre yanıtlayan sahte CDP bağlantısı."""

    def __init__(self, yanitlar):
        self.yanitlar, self.kapandi, self.sorgular = yanitlar, False, []

    def degerlendir(self, js, zaman=30):
        self.sorgular.append(js)
        for anahtar, yanit in self.yanitlar.items():
            govde = anahtar if anahtar.startswith("(") else siteler.SITELER["chatgpt"]["js"].get(anahtar, anahtar)
            if js == govde:
                if isinstance(yanit, Exception):
                    raise yanit
                return yanit
        raise AssertionError("beklenmeyen JS: " + js[:60])

    def kapat(self):
        self.kapandi = True


def js(anahtar):
    return siteler.SITELER["chatgpt"]["js"][anahtar]


class HedefTesti(unittest.TestCase):
    def test_varsayilanlar(self):
        veri = {"secili": {}}
        self.assertTrue(ms.site_secili(veri, "chatgpt"))
        self.assertFalse(ms.program_secili(veri, "chatgpt"))  # aynı kimlikli masaüstü programı ayrı bir hedef
        veri["secili"] = {"site:gemini": False, "claude": True}
        self.assertFalse(ms.site_secili(veri, "gemini"))
        self.assertTrue(ms.program_secili(veri, "claude"))
        self.assertTrue(ms.site_secili(veri, "claude"))

    def test_durum_siteler_ve_programlar(self):
        sahte_siteler = [{"id": "chatgpt", "ad": "ChatGPT", "renk": "#10a37f", "acik": False, "giris": None,
                          "sebep": "Pencere kapalı", "secili": True}]
        veri = {"secili": {}, "konumlar": {}, "ek_uygulamalar": [], "ayarlar": {}, "sohbetler": []}
        with mock.patch.object(ms.pc, "pencereleri_listele", return_value=[]), \
                mock.patch.object(ms, "site_durumlari", return_value=sahte_siteler):
            d = ms.durum(veri)
        self.assertEqual(d["siteler"], sahte_siteler)
        self.assertEqual([p["id"] for p in d["programlar"]], ["chatgpt", "gemini", "claude"])
        self.assertFalse(any(p["secili"] for p in d["programlar"]))


class AdresTesti(unittest.TestCase):
    def test_site_adresi_mi(self):
        self.assertTrue(ms._site_adresi_mi("chatgpt", "https://chatgpt.com/c/abc"))
        self.assertTrue(ms._site_adresi_mi("chatgpt", "https://www.chatgpt.com/c/abc"))
        self.assertTrue(ms._site_adresi_mi("claude", "https://claude.ai/chat/1"))
        self.assertTrue(ms._site_adresi_mi("gemini", "https://gemini.google.com/app/x"))
        self.assertFalse(ms._site_adresi_mi("chatgpt", "https://evilchatgpt.com/c/abc"))
        self.assertFalse(ms._site_adresi_mi("chatgpt", "https://example.com/?u=chatgpt.com"))
        self.assertFalse(ms._site_adresi_mi("chatgpt", "javascript:alert(1)"))
        self.assertFalse(ms._site_adresi_mi("claude", "https://chatgpt.com/c/abc"))

    def test_ayni_adres_ve_yol_anahtari(self):
        self.assertTrue(ms._ayni_adres("https://chatgpt.com/c/1#x", "https://chatgpt.com/c/1/"))
        self.assertFalse(ms._ayni_adres("https://chatgpt.com/c/1", "https://chatgpt.com/c/2"))
        self.assertEqual(ms._yol_anahtari("https://chatgpt.com/?model=x"), ms._yol_anahtari("https://chatgpt.com"))
        self.assertNotEqual(ms._yol_anahtari("https://claude.ai/chat/1"), ms._yol_anahtari("https://claude.ai/new"))


class SiteDurumuTesti(unittest.TestCase):
    def test_pencere_kapali(self):
        with mock.patch.object(ms, "site_sayfasi", return_value=None):
            d = ms.site_durumu("chatgpt")
        self.assertEqual((d["acik"], d["giris"]), (False, None))

    def test_giris_yapilmis_ve_yapilmamis(self):
        for giris in (True, False):
            b = SahteBaglanti({"giris_var_mi": {"giris": giris, "sebep": "x"}, "location.href": "https://chatgpt.com/"})
            with mock.patch.object(ms, "site_sayfasi", return_value=b):
                d = ms.site_durumu("chatgpt")
            self.assertEqual((d["acik"], d["giris"], d["url"]), (True, giris, "https://chatgpt.com/"))
            self.assertTrue(b.kapandi)

    def test_js_hatasi_belirsiz_giris(self):
        b = SahteBaglanti({"giris_var_mi": {"hata": "TypeError: x"}, "location.href": "u"})
        with mock.patch.object(ms, "site_sayfasi", return_value=b):
            d = ms.site_durumu("chatgpt")
        self.assertEqual((d["acik"], d["giris"]), (True, None))
        self.assertIn("TypeError", d["sebep"])

    def test_baglanti_hatasi(self):
        b = SahteBaglanti({"giris_var_mi": cdp.CdpHatasi("koptu")})
        with mock.patch.object(ms, "site_sayfasi", return_value=b):
            d = ms.site_durumu("chatgpt")
        self.assertEqual((d["acik"], d["giris"], d["sebep"]), (True, None, "koptu"))
        self.assertTrue(b.kapandi)


class SohbetOnbellegiTesti(unittest.TestCase):
    def setUp(self):
        ms._SOHBET_ONBELLEGI.clear()
        self.addCleanup(ms._SOHBET_ONBELLEGI.clear)

    @staticmethod
    def okuyucu(sonuclar, sayac):
        def oku(sid):
            sayac.append(sid)
            return sonuclar[sid]
        return oku

    def sohbet(self, sid, n):
        return {"id": f"{sid}:{n}", "site": sid, "baslik": f"s{n}", "url": f"https://x/{n}"}

    def test_onbellek_ve_yenile(self):
        sayac = []
        sonuclar = {s: {"sohbetler": [self.sohbet(s, 1)], "hata": None} for s in siteler.SITELER}
        with mock.patch.object(ms, "_site_sohbetlerini_oku", self.okuyucu(sonuclar, sayac)):
            v = ms.site_sohbetleri()
            self.assertEqual([s["id"] for s in v["sohbetler"]], ["chatgpt:1", "gemini:1", "claude:1"])
            self.assertEqual(len(sayac), 3)
            ms.site_sohbetleri()
            self.assertEqual(len(sayac), 3, "15 sn içinde yeniden sorgulanmamalı")
            ms.site_sohbetleri(yenile=True)
            self.assertEqual(len(sayac), 6)
            for k in ms._SOHBET_ONBELLEGI.values():  # süre dolsun
                k["zaman"] -= ms.SOHBET_ONBELLEK_SURESI + 1
            ms.site_sohbetleri()
            self.assertEqual(len(sayac), 9)

    def test_hata_veren_site_atlanir_digerleri_gelir(self):
        sonuclar = {"chatgpt": {"sohbetler": [self.sohbet("chatgpt", 1)], "hata": None},
                    "gemini": {"sohbetler": [], "hata": "bozuk seçici"},
                    "claude": {"sohbetler": [], "hata": None}}
        with mock.patch.object(ms, "_site_sohbetlerini_oku", self.okuyucu(sonuclar, [])):
            v = ms.site_sohbetleri(yenile=True)
        self.assertEqual([s["site"] for s in v["sohbetler"]], ["chatgpt"])
        self.assertEqual(v["hatalar"], [{"site": "gemini", "ad": "Gemini", "sebep": "bozuk seçici"}])

    def test_zaman_asimi(self):
        def yavas(sid):
            if sid == "gemini":
                time.sleep(1.5)
            return {"sohbetler": [self.sohbet(sid, 1)], "hata": None}
        with mock.patch.object(ms, "_site_sohbetlerini_oku", yavas), mock.patch.object(ms, "SITE_ZAMAN_ASIMI", 0.4):
            baslangic = time.monotonic()
            v = ms.site_sohbetleri(yenile=True)
            gecen = time.monotonic() - baslangic
        self.assertLess(gecen, 1.2, "yavaş site diğerlerini bekletmemeli")
        self.assertEqual([s["site"] for s in v["sohbetler"]], ["chatgpt", "claude"])
        self.assertEqual([h["site"] for h in v["hatalar"]], ["gemini"])

    def test_hatada_eski_liste_korunur(self):
        eski = {s: {"sohbetler": [self.sohbet(s, 1)], "hata": None} for s in siteler.SITELER}
        with mock.patch.object(ms, "_site_sohbetlerini_oku", self.okuyucu(eski, [])):
            ms.site_sohbetleri(yenile=True)
        bozuk = {s: {"sohbetler": [], "hata": "koptu"} for s in siteler.SITELER}
        with mock.patch.object(ms, "_site_sohbetlerini_oku", self.okuyucu(bozuk, [])):
            v = ms.site_sohbetleri(yenile=True)
        self.assertEqual(len(v["sohbetler"]), 3)
        self.assertEqual(len(v["hatalar"]), 3)

    def test_sohbet_okuma_giris_yoksa_bos(self):
        b = SahteBaglanti({"giris_var_mi": {"giris": False, "sebep": "x"}})
        with mock.patch.object(ms, "site_sayfasi", return_value=b):
            self.assertEqual(ms._site_sohbetlerini_oku("chatgpt"), {"sohbetler": [], "hata": None})
        self.assertTrue(b.kapandi)

    def test_sohbet_okuma_kimlik_uretir(self):
        liste = [{"id": "ham", "baslik": "Merhaba", "url": "https://chatgpt.com/c/abc-1"}, {"baslik": "adressiz"}]
        b = SahteBaglanti({"giris_var_mi": {"giris": True, "sebep": "x"}, "sohbet_listesi": liste})
        with mock.patch.object(ms, "site_sayfasi", return_value=b):
            v = ms._site_sohbetlerini_oku("chatgpt")
        self.assertEqual(v["sohbetler"], [{"id": "chatgpt:abc-1", "site": "chatgpt", "baslik": "Merhaba",
                                           "url": "https://chatgpt.com/c/abc-1"}])


class YanitTesti(unittest.TestCase):
    def mesajlar(self, *roller):
        return {"baslik": "b", "mesajlar": [{"rol": r, "metin": f"{r}{i}"} for i, r in enumerate(roller)]}

    def test_taban_eski_yaniti_gizler(self):
        b = SahteBaglanti({"yaziyor_mu": False, "mesajlar": self.mesajlar("kullanici", "asistan", "kullanici")})
        with mock.patch.object(ms, "site_sayfasi", return_value=b):
            v = ms.site_yaniti("chatgpt", taban=1)
        self.assertEqual(v, {"yaziyor": False, "metin": "", "bekleniyor": True})

    def test_taban_yeni_yanit(self):
        b = SahteBaglanti({"yaziyor_mu": True, "mesajlar": self.mesajlar("kullanici", "asistan", "kullanici", "asistan")})
        with mock.patch.object(ms, "site_sayfasi", return_value=b):
            v = ms.site_yaniti("chatgpt", taban=1)
        self.assertEqual(v, {"yaziyor": True, "metin": "asistan3", "bekleniyor": False})

    def test_tabansiz_son_yanit(self):
        b = SahteBaglanti({"yaziyor_mu": False, "son_yanit": "Selam"})
        with mock.patch.object(ms, "site_sayfasi", return_value=b):
            self.assertEqual(ms.site_yaniti("chatgpt")["metin"], "Selam")

    def test_js_hatasi_hata_alani(self):
        b = SahteBaglanti({"yaziyor_mu": {"hata": "bozuk"}})
        with mock.patch.object(ms, "site_sayfasi", return_value=b):
            self.assertEqual(ms.site_yaniti("chatgpt"), {"hata": "bozuk"})

    def test_pencere_yoksa_is_hatasi(self):
        with mock.patch.object(ms, "site_sayfasi", return_value=None):
            with self.assertRaises(ms.IsHatasi):
                ms.site_yaniti("chatgpt")
        with self.assertRaises(ms.IsHatasi):
            ms.site_yaniti("yok")


class YerelGecmisTesti(unittest.TestCase):
    def test_ekle_ve_yaniti_kaydet(self):
        veri = {"sohbetler": []}
        sid, sira = ms.sohbete_ekle(veri, None, "Merhaba dünya", ["ChatGPT"], [])
        self.assertEqual(sira, 0)
        sid2, sira2 = ms.sohbete_ekle(veri, sid, "İkinci", ["ChatGPT"], [])
        self.assertEqual((sid2, sira2), (sid, 1))
        ms.yaniti_kaydet(veri, sid, 1, "chatgpt", "Yanıt")
        self.assertEqual(veri["sohbetler"][0]["mesajlar"][1]["yanitlar"], {"chatgpt": "Yanıt"})
        self.assertEqual(veri["sohbetler"][0]["mesajlar"][0]["yanitlar"], {})

    def test_gecersiz_kayit_reddedilir(self):
        veri = {"sohbetler": []}
        sid, _ = ms.sohbete_ekle(veri, None, "x", [], [])
        for sohbet, sira, site in [("yok", 0, "chatgpt"), (sid, 5, "chatgpt"), (sid, "0", "chatgpt"), (sid, 0, "yok")]:
            with self.assertRaises(ms.IsHatasi):
                ms.yaniti_kaydet(veri, sohbet, sira, site, "m")


class GonderimTesti(unittest.TestCase):
    """siteye_gonder akışı: sahte bağlantıyla sıra ve girişler denetlenir."""

    def kur(self, gonder_yaniti):
        b = mock.MagicMock()
        b.degerlendir.side_effect = lambda js, zaman=30: {
            js_("giris_var_mi"): {"giris": True, "sebep": "x"},
            js_("yazi_kutusunu_bul"): {"tamam": True, "tur": "contenteditable", "sebep": ""},
            js_("mesajlar"): {"baslik": "", "mesajlar": [{"rol": "asistan", "metin": "a"}]},
            js_("gonder"): gonder_yaniti,
            "location.href": "https://chatgpt.com/",
        }[js]
        return b

    def test_satirlar_ayri_insert_text_ve_dugme(self):
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""})
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            s = ms.siteye_gonder("chatgpt", "bir\niki", True)
        self.assertEqual(s, {"taban": 1, "yeni_pencere": False})
        self.assertEqual([c.args[0] for c in b.yazi_ekle.call_args_list], ["bir", "\n", "iki"])
        b.tus.assert_not_called()
        b.kapat.assert_called_once()

    def test_enter_gerekliyse_enter_tusu(self):
        b = self.kur({"tamam": False, "yontem": "enter_gerekli", "sebep": "pasif"})
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            ms.siteye_gonder("chatgpt", "x", True)
        b.tus.assert_called_once_with("Enter", "Enter", 13, "\r")

    def test_enter_kapaliysa_yalniz_yazar(self):
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""})
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            ms.siteye_gonder("chatgpt", "x", False)
        b.yazi_ekle.assert_called_once_with("x")
        self.assertNotIn(js("gonder"), [c.args[0] for c in b.degerlendir.call_args_list])

    def test_giris_yoksa_sorun(self):
        b = mock.MagicMock()
        b.degerlendir.return_value = {"giris": False, "sebep": "Giriş yap düğmesi görünüyor"}
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            with self.assertRaises(ms.SiteHatasi) as h:
                ms.siteye_gonder("chatgpt", "x", True)
        self.assertEqual(str(h.exception), "oturum açılmamış")
        b.yazi_ekle.assert_not_called()
        b.kapat.assert_called_once()

    def test_pencere_yoksa_once_acilir(self):
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""})
        sayfalar = iter([None, b])
        with mock.patch.object(ms, "site_sayfasi", side_effect=lambda sid: next(sayfalar)), \
                mock.patch.object(ms.tarayici, "pencere_ac", return_value=None) as ac, mock.patch.object(ms.time, "sleep"):
            s = ms.siteye_gonder("chatgpt", "x", True)
        ac.assert_called_once_with(siteler.SITELER["chatgpt"]["yeni_sohbet_adresi"])
        self.assertTrue(s["yeni_pencere"])

    def test_baska_sitenin_adresine_gidilmez(self):
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""})
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            ms.siteye_gonder("chatgpt", "x", True, sohbet_url="https://example.com/c/1")
        b.git.assert_not_called()

    def test_gonder_toplami(self):
        veri = {"konumlar": {}, "ek_uygulamalar": []}

        def sahte(sid, *a):
            if sid == "gemini":
                raise ms.SiteHatasi("oturum açılmamış")
            return {"taban": 2, "yeni_pencere": False}
        with mock.patch.object(ms, "siteye_gonder", side_effect=sahte):
            gonderilen, sorunlar, bekleyen, one = ms.gonder(veri, "m", ["chatgpt", "gemini"], [], True)
        self.assertEqual(gonderilen, ["ChatGPT"])
        self.assertEqual(sorunlar, [{"ad": "Gemini", "sebep": "oturum açılmamış"}])
        self.assertEqual([(b["site"], b["taban"]) for b in bekleyen], [("chatgpt", 2)])
        self.assertFalse(one)


class SiteKilidiTesti(unittest.TestCase):
    def test_ayni_sitede_gezinme_ve_gonderme_ust_uste_binmez(self):
        icinde, cakisma = [0], []

        def yavas(*a):
            icinde[0] += 1
            if icinde[0] > 1:
                cakisma.append(True)
            time.sleep(0.1)
            icinde[0] -= 1
            return {"baslik": "", "mesajlar": []}

        import threading
        with mock.patch.object(ms, "_site_sohbet_ac", yavas), mock.patch.object(ms, "_siteye_gonder", yavas):
            isler = [threading.Thread(target=ms.site_sohbet_ac, args=("chatgpt", "")) for _ in range(3)]
            isler.append(threading.Thread(target=ms.siteye_gonder, args=("chatgpt", "x", True)))
            for i in isler:
                i.start()
            for i in isler:
                i.join()
        self.assertEqual(cakisma, [])


def js_(anahtar):
    return js(anahtar)


if __name__ == "__main__":
    unittest.main()
