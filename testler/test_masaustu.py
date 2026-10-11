"""masaustu_sunucu.py'nin site mantığı için hızlı testler: tarayıcıya ve ekrana dokunmaz (sahte bağlantılarla)."""
import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _ortam  # noqa: E402,F401  (gerçek ayar dosyalarını korur; sunucu modülünden önce)
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

    def kur(self, gonder_yaniti, kutu_hazir=True, kutu_metni=None, site="chatgpt", href=None, gezince=None):
        """Sahte site sekmesi.

        kutu_metni None ise kutu, yazi_ekle ile eklenenleri aynen gösterir (sorunsuz site).
        href: sekmenin başlangıç adresi (varsayılan: sitenin yeni sohbet sayfası); git() çağrılınca adres
        `gezince` olur (None ise gidilen adresin kendisi: yönlendirmesiz başarılı gezinme).
        """
        b = mock.MagicMock()
        konum = {"href": href or siteler.SITELER[site]["yeni_sohbet_adresi"]}
        b.git.side_effect = lambda url: konum.update(href=gezince or url)
        sjs = siteler.SITELER[site]["js"]

        def degerlendir(js, zaman=30):
            if js == sjs["kutu_metni"]:
                return "".join(c.args[0] for c in b.yazi_ekle.call_args_list) if kutu_metni is None else kutu_metni
            if js == "location.href":
                return konum["href"]
            return {
                sjs["giris_var_mi"]: {"giris": True, "sebep": "x"},
                sjs["yazi_kutusunu_bul"]: {"tamam": True, "tur": "contenteditable", "sebep": ""},
                sjs["kutu_hazir_mi"]: {"hazir": kutu_hazir},
                sjs["mesajlar"]: {"baslik": "", "mesajlar": [{"rol": "asistan", "metin": "a"}]},
                sjs["gonder"]: gonder_yaniti,
            }[js]
        b.degerlendir.side_effect = degerlendir
        return b

    def test_kutu_odakta_degilse_yazilmaz(self):
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""}, kutu_hazir=False)
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            with self.assertRaises(ms.SiteHatasi) as h:
                ms.siteye_gonder("chatgpt", "x", True)
        self.assertIn("odaklanamadı", str(h.exception))
        b.yazi_ekle.assert_not_called()
        self.assertNotIn(js("gonder"), [c.args[0] for c in b.degerlendir.call_args_list])

    def test_yazilan_metin_uyusmuyorsa_gonderilmez(self):
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""}, kutu_metni="baska bir sey")
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            with self.assertRaises(ms.SiteHatasi) as h:
                ms.siteye_gonder("chatgpt", "bir\niki", True)
        self.assertIn("uyuşmuyor", str(h.exception))
        self.assertNotIn(js("gonder"), [c.args[0] for c in b.degerlendir.call_args_list])
        b.tus.assert_not_called()
        b.kapat.assert_called_once()

    def test_bosluk_farki_uyusmazlik_sayilmaz(self):
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""}, kutu_metni="bir\n\niki\u00a0")
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            ms.siteye_gonder("chatgpt", "bir\niki", True)
        self.assertIn(js("gonder"), [c.args[0] for c in b.degerlendir.call_args_list])

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

    def test_taninmayan_sohbet_adresi_sorun_ve_yazilmaz(self):
        # Y2a: sohbet adresi hiçbir siteye ait değilse hiçbir şey yazılmaz, sayfaya gidilmez.
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""})
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            with self.assertRaises(ms.SiteHatasi) as h:
                ms.siteye_gonder("chatgpt", "x", True, sohbet_url="https://example.com/c/1")
        self.assertIn("gönderilmedi", str(h.exception))
        b.git.assert_not_called()
        b.yazi_ekle.assert_not_called()

    def test_sohbet_url_sahibi_site_o_sohbete_gider(self):
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""}, href="https://chatgpt.com/c/baska")
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            ms.siteye_gonder("chatgpt", "x", True, sohbet_url="https://chatgpt.com/c/abc")
        b.git.assert_called_once_with("https://chatgpt.com/c/abc")
        b.yazi_ekle.assert_called_once_with("x")

    def test_sohbet_url_baska_sitenin_ise_yeni_sohbete_gidilir(self):
        # Y2a: ChatGPT sohbetindeyken Gemini de seçiliyse Gemini, açık olan eski sohbetine değil yeni sohbete yazar.
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""}, site="gemini",
                     href="https://gemini.google.com/app/eski-sohbet")
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            ms.siteye_gonder("gemini", "x", True, sohbet_url="https://chatgpt.com/c/abc")
        b.git.assert_called_once_with(siteler.SITELER["gemini"]["yeni_sohbet_adresi"])
        b.yazi_ekle.assert_called_once_with("x")

    def test_ortak_sohbette_kayitli_adrese_gidilir(self):
        # Y2b: ikinci mesaj, ilk yanıttan sonra kaydedilen site adresine gider (pencere başka sohbette olsa da).
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""}, href="https://chatgpt.com/c/baska")
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            gonderilen, sorunlar, _, _ = ms.gonder({"konumlar": {}, "ek_uygulamalar": []}, "ikinci", ["chatgpt"], [],
                                                   True, None, {"chatgpt": "https://chatgpt.com/c/kayitli"})
        self.assertEqual((gonderilen, sorunlar), (["ChatGPT"], []))
        b.git.assert_called_once_with("https://chatgpt.com/c/kayitli")
        b.yazi_ekle.assert_called_once_with("ikinci")

    def test_ortak_sohbette_adres_yoksa_yeni_sohbet(self):
        # Kayıtlı adres yoksa pencere hangi sohbeti gösteriyorsa ona değil, yeni sohbet sayfasına yazılır.
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""}, href="https://chatgpt.com/c/baska")
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            ms.siteye_gonder("chatgpt", "x", True)
        b.git.assert_called_once_with("https://chatgpt.com/")

    def test_kayitli_adres_baska_siteninse_yazilmaz(self):
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""})
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            with self.assertRaises(ms.SiteHatasi):
                ms.siteye_gonder("chatgpt", "x", True, site_adresi="https://chatgpt.com.kotu.net/c/1")
        b.git.assert_not_called()
        b.yazi_ekle.assert_not_called()

    def test_gezinme_sonrasi_adres_uyusmazsa_yazilmaz(self):
        # Y2c: sohbet adresine gidildi ama site başka sayfaya yönlendirdi (ör. silinmiş sohbet): yazılmaz.
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""}, href="https://chatgpt.com/c/baska",
                     gezince="https://chatgpt.com/")
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"), \
                mock.patch.object(ms, "ADRES_DOGRULAMA_SURESI", 0):
            with self.assertRaises(ms.SiteHatasi) as h:
                ms.siteye_gonder("chatgpt", "x", True, sohbet_url="https://chatgpt.com/c/abc")
        self.assertIn("beklenen sohbete gitmedi", str(h.exception))
        b.git.assert_called_once_with("https://chatgpt.com/c/abc")
        b.yazi_ekle.assert_not_called()
        self.assertNotIn(js("gonder"), [c.args[0] for c in b.degerlendir.call_args_list])
        b.kapat.assert_called_once()

    def test_gezinme_yavas_tamamlanirsa_beklenir(self):
        # Page.navigate döndükten sonra adres bir süre eski kalabilir: hedefe varınca yazılır.
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""}, href="https://chatgpt.com/c/baska")
        adresler = iter(["https://chatgpt.com/c/baska", "https://chatgpt.com/c/baska", "https://chatgpt.com/c/abc"])
        b.git.side_effect = None
        onceki = b.degerlendir.side_effect

        def degerlendir(js, zaman=30):
            if js == "location.href":
                return next(adresler, "https://chatgpt.com/c/abc")
            return onceki(js, zaman)
        b.degerlendir.side_effect = degerlendir
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            ms.siteye_gonder("chatgpt", "x", True, sohbet_url="https://chatgpt.com/c/abc")
        b.yazi_ekle.assert_called_once_with("x")

    def test_yazmadan_once_adres_degistiyse_yazilmaz(self):
        # Kutu beklenirken site başka sohbete geçerse (adres değişirse) yazılmaz.
        b = self.kur({"tamam": True, "yontem": "dugme", "sebep": ""})
        onceki = b.degerlendir.side_effect
        okuma = []

        def degerlendir(js, zaman=30):
            if js == "location.href":
                okuma.append(1)
                return "https://chatgpt.com/" if len(okuma) == 1 else "https://chatgpt.com/c/baska"
            return onceki(js, zaman)
        b.degerlendir.side_effect = degerlendir
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"):
            with self.assertRaises(ms.SiteHatasi):
                ms.siteye_gonder("chatgpt", "x", True)
        b.yazi_ekle.assert_not_called()

    def test_masaustu_gonderimi_kesin_pencere_ve_pano_geri_yukleme(self):
        veri = {"konumlar": {}, "ek_uygulamalar": []}
        olaylar = []
        pencere = ms.pc.Pencere(77, 1, "ChatGPT", r"C:\x\ChatGPT.exe")
        with mock.patch.object(ms.pc, "pencereleri_listele", return_value=[pencere]), \
                mock.patch.object(ms.pc, "panoyu_oku", side_effect=lambda: olaylar.append("oku") or "eski pano"), \
                mock.patch.object(ms.pc, "panoya_yaz", side_effect=lambda m: olaylar.append(("yaz", m))), \
                mock.patch.object(ms.pc, "panoyu_geri_yukle", side_effect=lambda e: olaylar.append(("geri", e))), \
                mock.patch.object(ms.pc, "pencere_bul_kesin",
                                  side_effect=lambda u, acik: pencere if u["id"] == "chatgpt" else None), \
                mock.patch.object(ms.pc, "yaziyi_gonder", side_effect=lambda h, k, enter: olaylar.append(("gonder", h))):
            gonderilen, sorunlar, _, _ = ms.gonder(veri, "mesaj", [], ["chatgpt", "gemini"], True)
        self.assertEqual(olaylar, ["oku", ("yaz", "mesaj"), ("gonder", 77), ("geri", "eski pano")])
        self.assertEqual(gonderilen, ["ChatGPT"])
        self.assertEqual(len(sorunlar), 1)
        self.assertEqual(sorunlar[0]["ad"], "Gemini")
        self.assertIn("kesin olarak bulunamadı", sorunlar[0]["sebep"])

    def test_pano_hata_olsa_da_geri_yuklenir(self):
        veri = {"konumlar": {}, "ek_uygulamalar": []}
        pencere = ms.pc.Pencere(77, 1, "ChatGPT", r"C:\x\ChatGPT.exe")
        with mock.patch.object(ms.pc, "pencereleri_listele", return_value=[pencere]), \
                mock.patch.object(ms.pc, "panoyu_oku", return_value=None), \
                mock.patch.object(ms.pc, "panoya_yaz"), \
                mock.patch.object(ms.pc, "panoyu_geri_yukle") as geri, \
                mock.patch.object(ms.pc, "pencere_bul_kesin", return_value=pencere), \
                mock.patch.object(ms.pc, "yaziyi_gonder", side_effect=KeyError("beklenmedik")):
            with self.assertRaises(KeyError):
                ms.gonder(veri, "m", [], ["chatgpt"], True)
        geri.assert_called_once_with(None)

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


class SiteAdresiKaydiTesti(unittest.TestCase):
    """Y2b: ortak sohbette sitenin ilk yanıttan sonraki sohbet adresi kaydedilir."""

    def sohbet(self):
        veri = {"sohbetler": []}
        sid, _ = ms.sohbete_ekle(veri, None, "ilk", ["ChatGPT"], [])
        return veri, sid

    def test_yanit_kaydedilince_adres_kaydedilir(self):
        veri, sid = self.sohbet()
        ms.yaniti_kaydet(veri, sid, 0, "chatgpt", "Yanıt", "https://chatgpt.com/c/abc#alt")
        ms.yaniti_kaydet(veri, sid, 0, "claude", "Yanıt", "https://claude.ai/chat/u-1")
        self.assertEqual(veri["sohbetler"][0]["site_adresleri"],
                         {"chatgpt": "https://chatgpt.com/c/abc", "claude": "https://claude.ai/chat/u-1"})

    def test_ilk_adres_korunur(self):
        veri, sid = self.sohbet()
        ms.yaniti_kaydet(veri, sid, 0, "chatgpt", "Yanıt", "https://chatgpt.com/c/abc")
        self.assertFalse(ms.site_adresini_kaydet(veri["sohbetler"][0], "chatgpt", "https://chatgpt.com/c/baska"))
        self.assertEqual(veri["sohbetler"][0]["site_adresleri"], {"chatgpt": "https://chatgpt.com/c/abc"})

    def test_gecersiz_adresler_kaydedilmez(self):
        veri, sid = self.sohbet()
        sohbet = veri["sohbetler"][0]
        for site, adres in [("chatgpt", "https://chatgpt.com/"),          # hâlâ yeni sohbet sayfası
                            ("claude", "https://claude.ai/new"),
                            ("chatgpt", "https://chatgpt.com.kotu.net/c/1"),  # başka alan adı
                            ("chatgpt", "https://claude.ai/chat/1"),        # başka sitenin adresi
                            ("chatgpt", "javascript:alert(1)"),
                            ("yok", "https://chatgpt.com/c/1"),
                            ("chatgpt", None)]:
            with self.subTest(site=site, adres=adres):
                self.assertFalse(ms.site_adresini_kaydet(sohbet, site, adres))
        self.assertFalse(sohbet.get("site_adresleri"))
        ms.yaniti_kaydet(veri, sid, 0, "chatgpt", "Yanıt")  # adres okunamadıysa yalnız yanıt kaydedilir
        self.assertEqual(sohbet["mesajlar"][0]["yanitlar"], {"chatgpt": "Yanıt"})


class GonderHttpBaglantisiTesti(unittest.TestCase):
    """/api/gonder ve /api/yanit-kaydet, sohbetin site adreslerini gonder()'e iletir ve kaydeder."""

    def setUp(self):
        import tempfile
        import threading
        from http.server import ThreadingHTTPServer
        klasor = Path(tempfile.mkdtemp(prefix="yzgonder_"))
        self.addCleanup(__import__("shutil").rmtree, klasor, True)
        yama = mock.patch.object(ms, "AYAR_DOSYASI", klasor / "ayar.json")
        yama.start()
        self.addCleanup(yama.stop)
        ms.is_kilidi = threading.Lock()
        self.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), ms.Isleyici)
        threading.Thread(target=self.sunucu.serve_forever, daemon=True).start()
        self.addCleanup(self.sunucu.server_close)
        self.addCleanup(self.sunucu.shutdown)

    def post(self, yol, veri):
        import json
        import urllib.request
        talep = urllib.request.Request(f"http://127.0.0.1:{self.sunucu.server_port}{yol}", json.dumps(veri).encode(),
                                       {"Content-Type": "application/json", "X-YZ-Token": ms.BELIRTEC})
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with acici.open(talep, timeout=10) as y:
            return json.load(y)

    def test_adres_kaydi_ve_ikinci_mesajda_kullanimi(self):
        gelen = []

        def sahte_gonder(veri, metin, site_idleri, program_idleri, enter, sohbet_url=None, site_adresleri=None):
            gelen.append((sohbet_url, dict(site_adresleri or {})))
            return ["ChatGPT"], [], [{"site": "chatgpt", "ad": "ChatGPT", "renk": "#000", "taban": 0}], False
        ms.ayarlari_yaz({"secili": {"site:gemini": False, "site:claude": False}})
        with mock.patch.object(ms, "gonder", sahte_gonder), mock.patch.object(ms, "kendi_pencere", return_value=None), \
                mock.patch.object(ms, "site_konumu", return_value="https://chatgpt.com/c/yeni-1") as konum:
            v = self.post("/api/gonder", {"metin": "ilk"})
            sid = v["sohbet"]
            self.post("/api/yanit-kaydet", {"sohbet": sid, "mesaj_sira": 0, "site": "chatgpt", "metin": "Yanıt"})
            konum.assert_called_once_with("chatgpt")
            sohbet = next(s for s in ms.ayarlari_oku()["sohbetler"] if s["id"] == sid)
            self.assertEqual(sohbet["site_adresleri"], {"chatgpt": "https://chatgpt.com/c/yeni-1"})
            self.post("/api/gonder", {"metin": "ikinci", "sohbet": sid})
            self.post("/api/gonder", {"metin": "site sohbeti", "sohbet_url": "https://chatgpt.com/c/x"})
        self.assertEqual(gelen, [(None, {}), (None, {"chatgpt": "https://chatgpt.com/c/yeni-1"}),
                                 ("https://chatgpt.com/c/x", {})])


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


class HttpTabani(unittest.TestCase):
    """Geçici ayar dosyasıyla gerçek Isleyici'yi rastgele portta çalıştırır (tarayıcıya ve ağa dokunmaz)."""

    def setUp(self):
        import shutil
        import tempfile
        import threading
        from http.server import ThreadingHTTPServer
        klasor = Path(tempfile.mkdtemp(prefix="yzyonlendirme_"))
        self.addCleanup(shutil.rmtree, klasor, True)
        yama = mock.patch.object(ms, "AYAR_DOSYASI", klasor / "ayar.json")
        yama.start()
        self.addCleanup(yama.stop)
        ms.is_kilidi = threading.Lock()
        ms._MODEL_ONBELLEGI.clear()
        ms._SON_SINIFLANDIRMA.clear()
        self.addCleanup(ms._MODEL_ONBELLEGI.clear)
        self.addCleanup(ms._SON_SINIFLANDIRMA.clear)
        self.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), ms.Isleyici)
        threading.Thread(target=self.sunucu.serve_forever, daemon=True).start()
        self.addCleanup(self.sunucu.server_close)
        self.addCleanup(self.sunucu.shutdown)

    def istek(self, yontem, yol, veri=None):
        """(HTTP kodu, JSON gövde)."""
        import json
        import urllib.error
        import urllib.request
        govde = json.dumps(veri).encode() if veri is not None else None
        talep = urllib.request.Request(f"http://127.0.0.1:{self.sunucu.server_port}{yol}", govde, method=yontem,
                                       headers={"Content-Type": "application/json", "X-YZ-Token": ms.BELIRTEC})
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with acici.open(talep, timeout=10) as y:
                return y.status, json.load(y)
        except urllib.error.HTTPError as h:
            return h.code, json.loads(h.read().decode("utf-8"))

    def post(self, yol, veri):
        return self.istek("POST", yol, veri)

    def get(self, yol):
        return self.istek("GET", yol)


HAFIZASIZ = {"hafiza_ekle": False, "hafiza_aday": False}  # bu testler Hafıza OS kasasına dokunmasın

MODEL_LISTELERI = {
    "gemini": {"modeller": [{"id": "g1", "ad": "Gemini 3 Flash", "secili": True},
                            {"id": "g2", "ad": "Gemini 3 Pro", "secili": False}], "sebep": ""},
    "chatgpt": {"modeller": [{"id": "c1", "ad": "GPT-5 mini", "secili": False}], "sebep": ""},
    "claude": {"modeller": [], "sebep": "Claude penceresi kapalı"},
}


class OneriHttpTesti(HttpTabani):
    """/api/oneri, /api/modeller ve /api/yonlendirme."""

    def sahte_modeller(self, site_id, yenile=False):
        return {"site": site_id, **MODEL_LISTELERI[site_id]}

    def test_oneri_siniflandirir_ve_model_eslestirir(self):
        with mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
            kod, v = self.post("/api/oneri", {"metin": "Bu makaleyi özetle"})
        self.assertEqual(kod, 200)
        self.assertEqual((v["tur"], v["zorluk"], v["kaynak"]), ("ozet", "basit", "kural"))
        o = v["oneriler"]
        self.assertEqual([x["site"] for x in o], ["gemini", "chatgpt", "claude"])
        self.assertEqual(o[0]["model"], "Gemini 3 Flash")      # "flash" canlı menüden bulundu
        self.assertEqual(o[1]["model"], "GPT-5 mini")          # "mini"
        self.assertIsNone(o[2]["model"])                       # menü okunamadı: yalnızca site önerilir
        self.assertEqual(o[2]["model_notu"], "Claude penceresi kapalı")
        self.assertIn("sebep", o[0])

    def test_eslesen_model_yoksa_none_ve_not(self):
        with mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
            _, v = self.post("/api/oneri", {"metin": "Merhaba nasılsın"})   # sohbet/basit → gemini flash, chatgpt mini, claude haiku
            self.assertEqual(v["oneriler"][0]["model"], "Gemini 3 Flash")
            _, v = self.post("/api/oneri", {"metin": "Elektrikli araçları karşılaştır ve kaynak göster. " + "a" * 1300})
        self.assertEqual((v["tur"], v["zorluk"]), ("arastirma", "zor"))
        self.assertEqual((v["oneriler"][0]["site"], v["oneriler"][0]["model"]), ("gemini", "Gemini 3 Pro"))
        claude = next(x for x in v["oneriler"] if x["site"] == "claude")
        self.assertIsNone(claude["model"])
        chatgpt = next(x for x in v["oneriler"] if x["site"] == "chatgpt")   # "pro" aranır, menüde yok
        self.assertIsNone(chatgpt["model"])
        self.assertIn("pro", chatgpt["model_notu"])

    def test_bos_metin_reddedilir(self):
        for g in ({"metin": ""}, {"metin": "   "}, {}, {"metin": 5}):
            with self.subTest(g=g):
                kod, v = self.post("/api/oneri", g)
                self.assertEqual(kod, 400)
                self.assertIn("boş", v["hata"])

    def test_oneri_ayar_dosyasina_dokunmaz(self):
        with mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
            self.post("/api/oneri", {"metin": "merhaba dünya"})
        self.assertFalse(ms.AYAR_DOSYASI.exists())

    def test_son_siniflandirma_yonlendirme_durumunda(self):
        kod, v = self.get("/api/yonlendirme")
        self.assertEqual(kod, 200)
        self.assertIsNone(v["son"])
        self.assertEqual(len(v["tablo"]), 21)
        self.assertEqual(v["dosya"], str(ms.yonlendirici.YONLENDIRME_DOSYASI))
        self.assertEqual(v["uyarilar"], [])
        with mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
            self.post("/api/oneri", {"metin": "Python hatasını bul"})
        _, v = self.get("/api/yonlendirme")
        self.assertEqual((v["son"]["tur"], v["son"]["zorluk"], v["son"]["tur_ad"]), ("kod", "basit", "kod"))
        self.assertRegex(v["son"]["zaman"], r"^\d\d:\d\d:\d\d$")
        self.assertNotIn("Python", json.dumps(v, ensure_ascii=False), "mesaj metni saklanmaz")

    def test_bozuk_kural_dosyasi_yerlesige_duser(self):
        import tempfile
        with tempfile.TemporaryDirectory() as klasor:
            dosya = Path(klasor) / "y.json"
            dosya.write_text("{bozuk", "utf-8")
            with mock.patch.object(ms.yonlendirici, "YONLENDIRME_DOSYASI", dosya), \
                    mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
                kod, v = self.post("/api/oneri", {"metin": "merhaba dünya"})
                _, d = self.get("/api/yonlendirme")
        self.assertEqual(kod, 200)
        self.assertEqual(v["oneriler"][0]["site"], "gemini")
        self.assertTrue(v["uyarilar"] and d["uyarilar"])

    def test_yonlendirme_dosyasini_ac(self):
        with mock.patch.object(ms.os, "startfile", create=True) as ac:
            kod, v = self.post("/api/yonlendirme-ac", {})
        self.assertEqual(kod, 200)
        ac.assert_called_once_with(str(ms.yonlendirici.YONLENDIRME_DOSYASI))
        self.assertEqual(v["dosya"], str(ms.yonlendirici.YONLENDIRME_DOSYASI))
        with mock.patch.object(ms.yonlendirici, "YONLENDIRME_DOSYASI", Path("yok") / "yok.json"):
            kod, v = self.post("/api/yonlendirme-ac", {"yol": "C:\\Windows\\sistem.exe"})
        self.assertEqual(kod, 400)
        self.assertIn("bulunamadı", v["hata"])

    def test_modeller_ucu(self):
        with mock.patch.object(ms, "_model_listesi_oku", return_value=MODEL_LISTELERI["gemini"]) as oku:
            kod, v = self.get("/api/modeller?site=gemini")
            self.get("/api/modeller?site=gemini")
        self.assertEqual(kod, 200)
        self.assertEqual((v["site"], [m["ad"] for m in v["modeller"]]), ("gemini", ["Gemini 3 Flash", "Gemini 3 Pro"]))
        oku.assert_called_once_with("gemini")            # ikinci istek önbellekten
        for yol in ("/api/modeller?site=yok", "/api/modeller"):
            with self.subTest(yol=yol):
                self.assertEqual(self.get(yol)[0], 400)

    def test_modeller_ucu_belirtecsiz_403(self):
        import urllib.error
        import urllib.request
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for yol in ("/api/modeller?site=gemini", "/api/yonlendirme"):
            with self.subTest(yol=yol), self.assertRaises(urllib.error.HTTPError) as h:
                acici.open(f"http://127.0.0.1:{self.sunucu.server_port}{yol}", timeout=10)
            self.assertEqual(h.exception.code, 403)


class ModelListesiOkumaTesti(unittest.TestCase):
    """site_modelleri / _model_listesi_oku: sahte bağlantıyla; sitenin menüsüne gerçekten dokunulmaz."""

    PARCA = "(async () => 'model_listesi')()"

    def setUp(self):
        ms._MODEL_ONBELLEGI.clear()
        self.addCleanup(ms._MODEL_ONBELLEGI.clear)

    def kur(self, yanit, giris=None):
        giris = {"giris": True, "sebep": "x"} if giris is None else giris
        return SahteBaglanti({"giris_var_mi": giris, self.PARCA: yanit})

    def calistir(self, b, site="chatgpt", parca=None, **kw):
        with mock.patch.object(ms, "site_sayfasi", return_value=b) as s, \
                mock.patch.object(ms.siteler, "js_parca", return_value=parca or self.PARCA) as j:
            sonuc = ms.site_modelleri(site, **kw)
        return sonuc, s, j

    def test_liste_okunur_temizlenir_ve_onbellege_alinir(self):
        b = self.kur({"modeller": [{"id": "1", "ad": " GPT-5 ", "secili": True}, {"ad": ""}, "x", {"id": "2", "ad": "GPT-5 mini"}],
                      "sebep": ""})
        sonuc, _, j = self.calistir(b)
        j.assert_called_once_with("chatgpt", "model_listesi")
        self.assertEqual(sonuc["modeller"], [{"id": "1", "ad": "GPT-5", "secili": True},
                                             {"id": "2", "ad": "GPT-5 mini", "secili": False}])
        self.assertTrue(b.kapandi)
        n = len(b.sorgular)
        sonuc2, s, _ = self.calistir(b)
        self.assertEqual(sonuc2, sonuc)
        s.assert_not_called()                              # 60 sn içinde yeniden sorulmaz
        self.assertEqual(len(b.sorgular), n)
        ms._MODEL_ONBELLEGI["chatgpt"]["zaman"] -= ms.MODEL_ONBELLEK_SURESI + 1
        _, s, _ = self.calistir(b)
        s.assert_called_once()                             # süre doldu
        _, s, _ = self.calistir(b, yenile=True)
        s.assert_called_once()

    def test_menu_destegi_yoksa_sebep(self):
        for hata in (KeyError("model_listesi"), ValueError("Bilinmeyen ek ayar")):
            ms._MODEL_ONBELLEGI.clear()
            with self.subTest(hata=hata), mock.patch.object(ms.siteler, "js_parca", side_effect=hata), \
                    mock.patch.object(ms, "site_sayfasi") as s:
                sonuc = ms.site_modelleri("claude")
            self.assertEqual(sonuc, {"site": "claude", "modeller": [], "sebep": "model menüsü desteği henüz yok"})
            s.assert_not_called()

    def test_pencere_kapali_giris_yok_ve_hatalar(self):
        sonuc, _, _ = self.calistir(None)
        self.assertEqual((sonuc["modeller"], sonuc["sebep"]), ([], "ChatGPT penceresi kapalı"))
        ms._MODEL_ONBELLEGI.clear()
        sonuc, _, _ = self.calistir(self.kur({}, giris={"giris": False, "sebep": "x"}))
        self.assertEqual(sonuc["sebep"], "ChatGPT için giriş yapılmamış")
        ms._MODEL_ONBELLEGI.clear()
        sonuc, _, _ = self.calistir(self.kur({"hata": "TypeError: menü yok"}))
        self.assertIn("TypeError", sonuc["sebep"])
        ms._MODEL_ONBELLEGI.clear()
        sonuc, _, _ = self.calistir(self.kur(cdp.CdpHatasi("koptu")))
        self.assertEqual(sonuc["sebep"], "koptu")
        ms._MODEL_ONBELLEGI.clear()
        sonuc, _, _ = self.calistir(self.kur("liste değil"))
        self.assertIn("beklenmeyen", sonuc["sebep"])
        ms._MODEL_ONBELLEGI.clear()
        sonuc, _, _ = self.calistir(self.kur({"modeller": [], "sebep": "Menü açılamadı"}))
        self.assertEqual((sonuc["modeller"], sonuc["sebep"]), ([], "Menü açılamadı"))

    def test_hata_kisa_onbellege_alinir(self):
        _, s, _ = self.calistir(None)
        s.assert_called_once()
        _, s, _ = self.calistir(None)
        s.assert_not_called()                              # 10 sn içinde sayfaya yeniden sorulmaz
        ms._MODEL_ONBELLEGI["chatgpt"]["zaman"] -= ms.MODEL_HATA_ONBELLEK_SURESI + 1
        _, s, _ = self.calistir(None)
        s.assert_called_once()

    def test_site_mesgulse_bekleyip_vazgecer(self):
        kilit = ms._SITE_KILITLERI["chatgpt"]
        kilit.acquire()
        self.addCleanup(lambda: kilit.locked() and kilit.release())
        with mock.patch.object(ms, "MODEL_KILIT_BEKLEME", 0.05), mock.patch.object(ms.siteler, "js_parca", return_value=self.PARCA), \
                mock.patch.object(ms, "site_sayfasi") as s:
            sonuc = ms.site_modelleri("chatgpt")
        self.assertEqual(sonuc["sebep"], "ChatGPT şu an meşgul")
        s.assert_not_called()

    def test_bilinmeyen_site(self):
        with self.assertRaises(ms.IsHatasi):
            ms.site_modelleri("yok")


class ModelSecmeTesti(unittest.TestCase):
    """siteye_gonder / gonder: yazmadan önce model_sec JS'i çağrılır; seçilemezse mevcut modelle gönderilir."""

    MODEL_JS = "(async () => 'model_sec')()"

    def kur(self, model_yaniti, site="chatgpt"):
        b = mock.MagicMock()
        self.olaylar = []
        konum = {"href": siteler.SITELER[site]["yeni_sohbet_adresi"]}
        b.git.side_effect = lambda url: konum.update(href=url)
        b.yazi_ekle.side_effect = lambda t: self.olaylar.append("yazi")
        sjs = siteler.SITELER[site]["js"]

        def degerlendir(js, zaman=30):
            if js == self.MODEL_JS:
                self.olaylar.append("model_sec")
                if isinstance(model_yaniti, Exception):
                    raise model_yaniti
                return model_yaniti
            if js == sjs["kutu_metni"]:
                return "".join(c.args[0] for c in b.yazi_ekle.call_args_list)
            if js == "location.href":
                return konum["href"]
            if js == sjs["yazi_kutusunu_bul"]:
                self.olaylar.append("kutu")
            if js == sjs["gonder"]:
                self.olaylar.append("gonder")
            return {
                sjs["giris_var_mi"]: {"giris": True, "sebep": "x"},
                sjs["yazi_kutusunu_bul"]: {"tamam": True, "tur": "contenteditable", "sebep": ""},
                sjs["kutu_hazir_mi"]: {"hazir": True},
                sjs["mesajlar"]: {"baslik": "", "mesajlar": [{"rol": "asistan", "metin": "a"}]},
                sjs["gonder"]: {"tamam": True, "yontem": "dugme", "sebep": ""},
            }[js]
        b.degerlendir.side_effect = degerlendir
        return b

    def gonder(self, b, model="Gemini 3 Flash", site="chatgpt", parca=None):
        def js_parca(site_id, anahtar, **ek):
            if anahtar != "model_sec":
                raise AssertionError(anahtar)
            if parca is not None:
                raise parca
            self.cagrilar.append((site_id, ek))
            return self.MODEL_JS
        self.cagrilar = []
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"), \
                mock.patch.object(ms.siteler, "js_parca", side_effect=js_parca):
            return ms.siteye_gonder(site, "merhaba", True, model=model)

    def test_model_yazmadan_once_secilir(self):
        b = self.kur({"tamam": True, "secilen": "Gemini 3 Flash", "sebep": ""})
        s = self.gonder(b)
        self.assertEqual(self.cagrilar, [("chatgpt", {"hedef_model": "Gemini 3 Flash"})])
        self.assertIsNone(s["model_uyarisi"])
        self.assertLess(self.olaylar.index("model_sec"), self.olaylar.index("yazi"))
        self.assertEqual(self.olaylar[-1], "gonder")
        self.assertEqual(self.olaylar.count("kutu"), 2, "model menüsünden sonra yazı kutusu yeniden odaklanır")
        self.assertEqual(self.olaylar.index("kutu"), 0)

    def test_model_verilmezse_model_js_calismaz(self):
        b = self.kur({"tamam": True})
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"), \
                mock.patch.object(ms.siteler, "js_parca", side_effect=AssertionError("çağrılmamalı")):
            s = ms.siteye_gonder("chatgpt", "merhaba", True)
        self.assertEqual(s, {"taban": 1, "yeni_pencere": False})
        self.assertNotIn("model_sec", self.olaylar)

    def test_secilemezse_mevcut_modelle_gonderilir(self):
        b = self.kur({"tamam": False, "secilen": "", "sebep": "menüde Gemini 3 Flash yok"})
        s = self.gonder(b)
        self.assertEqual(s["model_uyarisi"], "menüde Gemini 3 Flash yok")
        self.assertEqual(self.olaylar[-1], "gonder")       # yine de gönderildi

    def test_hata_senaryolari_gonderimi_engellemez(self):
        for yanit, beklenen in ((cdp.CdpHatasi("koptu"), "koptu"), ({"hata": "TypeError: x"}, "TypeError: x"),
                                ("garip", "Sayfadan beklenmeyen yanıt geldi"), ({"tamam": False}, "bilinmeyen sebep")):
            with self.subTest(yanit=str(yanit)):
                b = self.kur(yanit)
                s = self.gonder(b)
                self.assertEqual(s["model_uyarisi"], beklenen)
                self.assertEqual(self.olaylar[-1], "gonder")

    def test_menu_destegi_henuz_yok(self):
        for hata in (ValueError("Bilinmeyen ek ayar"), KeyError("model_sec")):
            with self.subTest(hata=hata):
                b = self.kur({"tamam": True})
                s = self.gonder(b, parca=hata)
                self.assertEqual(s["model_uyarisi"], "model menüsü desteği henüz yok")
                self.assertNotIn("model_sec", self.olaylar)
                self.assertEqual(self.olaylar[-1], "gonder")

    def test_gonder_sorunlara_model_secilemedi_ekler(self):
        veri = {"konumlar": {}, "ek_uygulamalar": []}
        gelen = []

        def sahte(sid, metin, enter, sohbet_url, site_adresi, *model):
            gelen.append((sid, model))
            if sid == "gemini":
                return {"taban": 0, "yeni_pencere": False, "model_uyarisi": "menü açılamadı"}
            return {"taban": 0, "yeni_pencere": False}
        with mock.patch.object(ms, "siteye_gonder", side_effect=sahte):
            gonderilen, sorunlar, bekleyen, _ = ms.gonder(
                veri, "m", ["chatgpt", "gemini"], [], True, model_sec={"site": "gemini", "model": "Gemini 3 Flash"})
        self.assertEqual(sorted(gelen), [("chatgpt", ()), ("gemini", ("Gemini 3 Flash",))])  # yalnızca o siteye
        self.assertEqual(sorted(gonderilen), ["ChatGPT", "Gemini"])
        self.assertEqual(sorunlar, [{"ad": "Gemini", "sebep": "model seçilemedi: menü açılamadı"}])
        self.assertEqual(len(bekleyen), 2)

    def test_model_secilince_sorun_eklenmez(self):
        with mock.patch.object(ms, "siteye_gonder", return_value={"taban": 0, "yeni_pencere": False, "model_uyarisi": None}):
            _, sorunlar, _, _ = ms.gonder({"konumlar": {}, "ek_uygulamalar": []}, "m", ["gemini"], [], True,
                                          model_sec={"site": "gemini", "model": "x"})
        self.assertEqual(sorunlar, [])

    def test_model_sec_dogrulama(self):
        self.assertIsNone(ms._model_sec_dogrula(None))
        self.assertEqual(ms._model_sec_dogrula({"site": "claude", "model": "  Sonnet 5.5 "}), {"site": "claude", "model": "Sonnet 5.5"})
        for kotu in ({}, {"site": "claude"}, {"site": "yok", "model": "x"}, {"site": "claude", "model": ""},
                     {"site": "claude", "model": 5}, {"site": "claude", "model": "x" * 121}, "claude", ["claude"], False):
            with self.subTest(kotu=kotu), self.assertRaises(ms.IsHatasi):
                ms._model_sec_dogrula(kotu)


class HassasVeModelGonderHttpTesti(HttpTabani):
    """/api/gonder: hassas bilgi onayı (onay_gerekli / onayli) ve model_sec iletimi."""

    def sahte_gonder(self, gelen):
        def gonder(veri, metin, site_idleri, program_idleri, enter, sohbet_url=None, site_adresleri=None, **ek):
            gelen.append({"metin": metin, "siteler": list(site_idleri), **ek})
            return ["ChatGPT"], [], [], False
        return gonder

    def calistir(self, gelen, govdeler, ayar=None):
        ms.ayarlari_yaz({"secili": {"site:gemini": False, "site:claude": False}, "ayarlar": {**HAFIZASIZ, **(ayar or {})}})
        sonuclar = []
        with mock.patch.object(ms, "gonder", self.sahte_gonder(gelen)), mock.patch.object(ms, "kendi_pencere", return_value=None):
            for g in govdeler:
                sonuclar.append(self.post("/api/gonder", g))
        return sonuclar

    ANAHTAR = "bu anahtarı kullan: sk-" + "abcdefghijklmnop1234567890"

    def test_hassas_metin_onay_ister_ve_gonderilmez(self):
        gelen = []
        (kod, v), = self.calistir(gelen, [{"metin": self.ANAHTAR}])
        self.assertEqual(kod, 200)
        self.assertEqual((v["onay_gerekli"], v["kategori"], v["aciklama"]), (True, "api_anahtari", "bir API anahtarı"))
        self.assertEqual(gelen, [], "onay gelmeden hiçbir siteye gönderilmez")
        self.assertEqual(ms.ayarlari_oku()["sohbetler"], [], "yerel geçmişe de eklenmez")
        self.assertNotIn("abcdefghijklmnop1234567890", json.dumps(v))

    def test_onayli_true_ile_gonderilir(self):
        gelen = []
        (_, v1), (_, v2) = self.calistir(gelen, [{"metin": self.ANAHTAR}, {"metin": self.ANAHTAR, "onayli": True}])
        self.assertTrue(v1["onay_gerekli"])
        self.assertNotIn("onay_gerekli", v2)
        self.assertEqual(v2["gonderilen"], ["ChatGPT"])
        self.assertEqual(len(gelen), 1)
        self.assertEqual(len(ms.ayarlari_oku()["sohbetler"]), 1)

    def test_onayli_yalniz_true_sayilir(self):
        gelen = []
        sonuclar = self.calistir(gelen, [{"metin": self.ANAHTAR, "onayli": degeri} for degeri in ("true", 1, "evet", None)])
        self.assertTrue(all(v.get("onay_gerekli") for _, v in sonuclar))
        self.assertEqual(gelen, [])

    def test_kategoriler(self):
        ornekler = {"api_anahtari": "sk-" + "a" * 24, "parola": "şifre: Gizli1234", "kimlik": "TC 10000000146",
                    "finansal": "IBAN TR33 0006 1005 1978 6457 8413 26"}
        gelen = []
        sonuclar = self.calistir(gelen, [{"metin": m} for m in ornekler.values()])
        self.assertEqual([v["kategori"] for _, v in sonuclar], list(ornekler))
        self.assertEqual([v["aciklama"] for _, v in sonuclar],
                         ["bir API anahtarı", "bir parola", "bir T.C. kimlik numarası", "bir IBAN ya da kart numarası"])

    def test_temiz_metin_dogrudan_gider(self):
        gelen = []
        (_, v), = self.calistir(gelen, [{"metin": "Merhaba, bugün hava nasıl?"}])
        self.assertEqual(v["gonderilen"], ["ChatGPT"])
        self.assertEqual(len(gelen), 1)

    def test_ayar_kapaliysa_uyari_yok(self):
        gelen = []
        (_, v), = self.calistir(gelen, [{"metin": self.ANAHTAR}], ayar={"hassas_uyari": False})
        self.assertEqual(v["gonderilen"], ["ChatGPT"])
        self.assertEqual(len(gelen), 1)

    def test_ayarlar_varsayilan_ve_sema(self):
        v = ms.ayarlari_oku()["ayarlar"]
        self.assertIs(v["hassas_uyari"], True)
        self.assertIs(v["otomatik_yonlendirme"], False)
        self.assertEqual(self.post("/api/ayar", {"hassas_uyari": False, "otomatik_yonlendirme": True})[0], 200)
        v = ms.ayarlari_oku()["ayarlar"]
        self.assertEqual((v["hassas_uyari"], v["otomatik_yonlendirme"]), (False, True))
        once = ms.AYAR_DOSYASI.read_bytes()
        for g in ({"hassas_uyari": "evet"}, {"otomatik_yonlendirme": 1}, {"hassas_uyari": None}):
            with self.subTest(g=g):
                self.assertEqual(self.post("/api/ayar", g)[0], 400)
                self.assertEqual(ms.AYAR_DOSYASI.read_bytes(), once)

    def test_model_sec_gonder_e_iletilir(self):
        gelen = []
        self.calistir(gelen, [{"metin": "merhaba", "model_sec": {"site": "chatgpt", "model": "GPT-5 mini"}}])
        self.assertEqual(gelen[0]["model_sec"], {"site": "chatgpt", "model": "GPT-5 mini"})

    def test_model_sec_yoksa_ek_arguman_yok(self):
        gelen = []
        self.calistir(gelen, [{"metin": "merhaba"}])
        self.assertNotIn("model_sec", gelen[0])

    def test_secili_olmayan_site_icin_model_sec_yok_sayilir(self):
        gelen = []
        self.calistir(gelen, [{"metin": "merhaba", "model_sec": {"site": "gemini", "model": "Gemini 3 Flash"}}])
        self.assertNotIn("model_sec", gelen[0])

    def test_gecersiz_model_sec_400(self):
        gelen = []
        sonuclar = self.calistir(gelen, [{"metin": "merhaba", "model_sec": kotu}
                                         for kotu in ({"site": "yok", "model": "x"}, {"site": "chatgpt"}, "chatgpt", [])])
        self.assertTrue(all(kod == 400 and "model seçimi" in v["hata"] for kod, v in sonuclar))
        self.assertEqual(gelen, [])

    def test_model_sec_uctan_uca_sahte_baglantiyla(self):
        """/api/gonder → gonder → siteye_gonder → sayfa JS'i: model seçimi yazmadan önce, sorun listesine düşer."""
        b = mock.MagicMock()
        sjs = siteler.SITELER["chatgpt"]["js"]
        olaylar = []
        b.yazi_ekle.side_effect = lambda t: olaylar.append("yazi")

        def degerlendir(js, zaman=30):
            if js == "JS_MODEL_SEC":
                olaylar.append("model_sec")
                return {"tamam": False, "secilen": "", "sebep": "menüde bulunamadı"}
            if js == "location.href":
                return siteler.SITELER["chatgpt"]["yeni_sohbet_adresi"]
            if js == sjs["kutu_metni"]:
                return "merhaba"
            return {sjs["giris_var_mi"]: {"giris": True, "sebep": "x"},
                    sjs["yazi_kutusunu_bul"]: {"tamam": True, "tur": "contenteditable", "sebep": ""},
                    sjs["kutu_hazir_mi"]: {"hazir": True},
                    sjs["mesajlar"]: {"baslik": "", "mesajlar": []},
                    sjs["gonder"]: {"tamam": True, "yontem": "dugme", "sebep": ""}}[js]
        b.degerlendir.side_effect = degerlendir
        ms.ayarlari_yaz({"secili": {"site:gemini": False, "site:claude": False}, "ayarlar": dict(HAFIZASIZ)})
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"), \
                mock.patch.object(ms, "kendi_pencere", return_value=None), \
                mock.patch.object(ms.siteler, "js_parca", return_value="JS_MODEL_SEC") as j:
            kod, v = self.post("/api/gonder", {"metin": "merhaba", "model_sec": {"site": "chatgpt", "model": "GPT-5 mini"}})
        self.assertEqual(kod, 200)
        j.assert_called_once_with("chatgpt", "model_sec", hedef_model="GPT-5 mini")
        self.assertEqual(v["gonderilen"], ["ChatGPT"])                 # mevcut modelle yine de gitti
        self.assertEqual(v["sorunlar"], [{"ad": "ChatGPT", "sebep": "model seçilemedi: menüde bulunamadı"}])
        self.assertLess(olaylar.index("model_sec"), olaylar.index("yazi"))
        kayit = ms.ayarlari_oku()["sohbetler"][0]["mesajlar"][0]
        self.assertEqual(kayit["sorunlar"], v["sorunlar"])


class JevBaglantiHttpTesti(HttpTabani):
    """Jev bağlantıları: /api/oneri (kaynak jev/kural), hassas uyarısı, /api/yanit-puanla, /api/jev-durum.

    jev.sinifla ve jev.hazir_mi yamalanır; ağa hiç çıkılmaz (gerçek Jev'e istek gitmez).
    """

    def sahte_modeller(self, site_id, yenile=False):
        return {"site": site_id, **MODEL_LISTELERI[site_id]}

    def jev_yamasi(self, cevap, hazir=True):
        """cevap(metin, secenekler, **ek) → sonuç ya da istisna; çağrılar self.cagrilar'a kaydedilir."""
        self.cagrilar = []

        def sinifla(metin, secenekler, baglam="", acik=True, zaman_asimi=8):
            self.cagrilar.append({"metin": metin, "secenekler": list(secenekler), "baglam": baglam})
            sonuc = cevap(metin, list(secenekler))
            if isinstance(sonuc, Exception):
                raise sonuc
            return sonuc
        for yama in (mock.patch.object(ms.jev, "sinifla", sinifla),
                     mock.patch.object(ms.jev, "hazir_mi", return_value=hazir)):
            yama.start()
            self.addCleanup(yama.stop)

    @staticmethod
    def secim(ad, puan=0.9):
        return {"secim": ad, "puan": puan, "olasiliklar": {ad: puan}}

    # ---- yönlendirici
    def test_oneri_jev_hazirken_kaynak_jev(self):
        def cevap(metin, secenekler):
            return self.secim("kod") if "kod" in secenekler else self.secim("zor")
        self.jev_yamasi(cevap)
        ms.ayarlari_yaz({"ayarlar": dict(HAFIZASIZ)})
        with mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
            kod, v = self.post("/api/oneri", {"metin": "Bu makaleyi özetle"})   # kurala göre özet/basit olurdu
        self.assertEqual(kod, 200)
        self.assertEqual((v["tur"], v["zorluk"], v["kaynak"]), ("kod", "zor", "jev"))
        self.assertEqual(v["oneriler"][0]["site"], "claude")   # kod/zor tercih sırası
        self.assertEqual(len(self.cagrilar), 2)
        self.assertEqual(sorted(tuple(sorted(c["secenekler"])) for c in self.cagrilar),
                         sorted([tuple(sorted(ms.yonlendirici.TURLER)), ("basit", "orta", "zor")]))
        _, d = self.get("/api/yonlendirme")
        self.assertEqual(d["son"]["kaynak"], "jev")

    def test_oneri_hassas_metni_jeve_gondermez(self):
        # Yazarken otomatik çağrılan /api/oneri, parola/anahtar içeren metni onay alınmadan Jev'e göndermemeli.
        self.jev_yamasi(lambda m, s: self.secim("kod"))
        ms.ayarlari_yaz({"ayarlar": dict(HAFIZASIZ)})
        with mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
            kod, v = self.post("/api/oneri", {"metin": "şifre: Abc12345 ile giriş yap"})
        self.assertEqual(kod, 200)
        self.assertEqual(v["kaynak"], "kural")
        self.assertEqual(self.cagrilar, [])

    def test_oneri_jev_hata_verince_kural(self):
        self.jev_yamasi(lambda m, s: ms.jev.JevHatasi("Jev 8 saniyede yanıt vermedi."))
        with mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
            kod, v = self.post("/api/oneri", {"metin": "Bu makaleyi özetle"})
        self.assertEqual(kod, 200)
        self.assertEqual((v["tur"], v["zorluk"], v["kaynak"]), ("ozet", "basit", "kural"))

    def test_oneri_jev_kapali_ya_da_hazir_degilse_cagrilmaz(self):
        self.jev_yamasi(lambda m, s: self.secim("kod"))
        ms.ayarlari_yaz({"ayarlar": {"jev_acik": False}})
        with mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
            _, v = self.post("/api/oneri", {"metin": "Bu makaleyi özetle"})
        self.assertEqual(v["kaynak"], "kural")
        self.jev_yamasi(lambda m, s: self.secim("kod"), hazir=False)
        ms.ayarlari_yaz({"ayarlar": {"jev_acik": True}})
        with mock.patch.object(ms, "site_modelleri", self.sahte_modeller):
            _, v = self.post("/api/oneri", {"metin": "Bu makaleyi özetle"})
        self.assertEqual(v["kaynak"], "kural")
        self.assertEqual(self.cagrilar, [])

    # ---- hassas bilgi uyarısı
    def gonder_dene(self, govdeler, ayar=None):
        gelen = []

        def gonder(veri, metin, site_idleri, program_idleri, enter, sohbet_url=None, site_adresleri=None, **ek):
            gelen.append(metin)
            return ["ChatGPT"], [], [], False
        ms.ayarlari_yaz({"secili": {"site:gemini": False, "site:claude": False}, "ayarlar": {**HAFIZASIZ, **(ayar or {})}})
        with mock.patch.object(ms, "gonder", gonder), mock.patch.object(ms, "kendi_pencere", return_value=None):
            return [self.post("/api/gonder", g) for g in govdeler], gelen

    def test_hassas_jev_parola_gorurse_onay_ister(self):
        self.jev_yamasi(lambda m, s: self.secim("parola", 0.8))
        ((kod, v),), gelen = self.gonder_dene([{"metin": "parolam annemin doğum yılı artı kedimin adı"}])
        self.assertEqual(kod, 200)
        self.assertTrue(v["onay_gerekli"])
        self.assertEqual((v["kategori"], v["kaynak"]), ("parola", "jev"))
        self.assertIn("Jev", v["aciklama"])
        self.assertEqual(gelen, [])
        self.assertEqual(self.cagrilar[0]["secenekler"], ["parola", "api_anahtari", "kimlik_bilgisi", "finansal", "yok"])

    def test_hassas_jev_dusuk_olasilik_ya_da_yok_ise_gider(self):
        for sonuc in (self.secim("parola", 0.55), self.secim("yok", 0.95)):
            with self.subTest(sonuc=sonuc):
                self.jev_yamasi(lambda m, s, x=sonuc: x)
                ((_, v),), gelen = self.gonder_dene([{"metin": "merhaba"}])
                self.assertEqual(v["gonderilen"], ["ChatGPT"])
                self.assertEqual(len(gelen), 1)

    def test_hassas_jev_hatasi_sessizce_yerel_sonuc(self):
        self.jev_yamasi(lambda m, s: ms.jev.JevHatasi("Jev sunucusuna ulaşılamadı."))
        ((kod, v),), gelen = self.gonder_dene([{"metin": "merhaba"}])
        self.assertEqual((kod, v["gonderilen"]), (200, ["ChatGPT"]))
        self.jev_yamasi(lambda m, s: RuntimeError("beklenmeyen"))
        ((kod, v),), _ = self.gonder_dene([{"metin": "merhaba"}])
        self.assertEqual((kod, v["gonderilen"]), (200, ["ChatGPT"]))

    def test_hassas_yerel_bulursa_jev_sorulmaz_ve_onayli_gider(self):
        self.jev_yamasi(lambda m, s: self.secim("parola", 0.99))
        sonuclar, gelen = self.gonder_dene([{"metin": "şifre: Gizli1234"}, {"metin": "gizli şey", "onayli": True}])
        self.assertEqual((sonuclar[0][1]["kategori"], sonuclar[0][1]["kaynak"]), ("parola", "kural"))
        self.assertEqual(sonuclar[1][1]["gonderilen"], ["ChatGPT"])
        self.assertEqual(self.cagrilar, [], "yerel tarama buldu / kullanıcı onayladı: Jev'e gitmez")
        self.assertEqual(len(gelen), 1)

    def test_hassas_uyari_ya_da_jev_kapaliysa_jev_sorulmaz(self):
        self.jev_yamasi(lambda m, s: self.secim("parola", 0.99))
        for ayar in ({"hassas_uyari": False}, {"jev_acik": False}):
            with self.subTest(ayar=ayar):
                ((_, v),), _ = self.gonder_dene([{"metin": "merhaba"}], ayar)
                self.assertEqual(v["gonderilen"], ["ChatGPT"])
        self.assertEqual(self.cagrilar, [])

    # ---- yanıt puanlama
    def sohbet_kur(self, yanitlar, puanla=True, jev_acik=True):
        ms.ayarlari_yaz({"ayarlar": {**HAFIZASIZ, "jev_yanit_puanla": puanla, "jev_acik": jev_acik},
                         "sohbetler": [{"id": "s1", "baslik": "x", "mesajlar": [
                             {"metin": "Türkiye'nin başkenti neresi?", "gonderilen": [], "sorunlar": [],
                              "yanitlar": yanitlar}]}]})

    def test_yanit_puanla(self):
        self.jev_yamasi(lambda m, s: {"secim": "claude", "puan": 0.7,
                                      "olasiliklar": {"chatgpt": 0.2, "claude": 0.7, "gemini": 0.1}})
        self.sohbet_kur({"chatgpt": "Ankara." + "a" * 3000, "gemini": "Ankara'dır.", "claude": "Başkent Ankara."})
        kod, v = self.post("/api/yanit-puanla", {"sohbet": "s1", "mesaj_sira": 0})
        self.assertEqual(kod, 200)
        self.assertEqual((v["onerilen"], v["site_ad"], v["puan"]), ("claude", "Claude", 0.7))
        (c,) = self.cagrilar
        self.assertEqual(c["secenekler"], ["chatgpt", "gemini", "claude"])
        self.assertTrue(c["metin"].startswith("Soru: Türkiye'nin başkenti neresi?\nYanıtlar: [chatgpt: Ankara."))
        self.assertIn("[claude: Başkent Ankara.]", c["metin"])
        self.assertLessEqual(len(c["metin"]), ms.jev.METIN_EN_FAZLA, "her site yanıtı bütçeye sığar, sonuncusu kesilmez")
        self.assertNotIn("a" * (ms.JEV_YANIT_EN_FAZLA + 1), c["metin"])
        kayit = ms.ayarlari_oku()["sohbetler"][0]["mesajlar"][0]
        self.assertEqual(kayit["jev_onerilen"], {"site": "claude", "puan": 0.7})

    def test_yanit_puanla_kosullari(self):
        self.jev_yamasi(lambda m, s: self.secim("chatgpt"))
        iki = {"chatgpt": "A", "gemini": "B"}
        durumlar = [
            (dict(yanitlar=iki, puanla=False), {"sohbet": "s1", "mesaj_sira": 0}, "kapalı"),
            (dict(yanitlar=iki, jev_acik=False), {"sohbet": "s1", "mesaj_sira": 0}, "Jev kapalı"),
            (dict(yanitlar={"chatgpt": "A", "gemini": "  "}), {"sohbet": "s1", "mesaj_sira": 0}, "en az iki"),
            (dict(yanitlar=iki), {"sohbet": "yok", "mesaj_sira": 0}, "bulunamadı"),
            (dict(yanitlar=iki), {"sohbet": "s1", "mesaj_sira": 5}, "bulunamadı"),
            (dict(yanitlar=iki), {"sohbet": "s1", "mesaj_sira": True}, "bulunamadı"),
        ]
        for kurulum, govde, parca in durumlar:
            with self.subTest(kurulum=kurulum, govde=govde):
                self.sohbet_kur(**kurulum)
                kod, v = self.post("/api/yanit-puanla", govde)
                self.assertEqual(kod, 400)
                self.assertIn(parca, v["hata"])
        self.assertEqual(self.cagrilar, [])

    def test_yanit_puanla_jev_hatasi_400(self):
        self.jev_yamasi(lambda m, s: ms.jev.JevHatasi("Jev anahtarı reddedildi (401)."))
        self.sohbet_kur({"chatgpt": "A", "gemini": "B"})
        kod, v = self.post("/api/yanit-puanla", {"sohbet": "s1", "mesaj_sira": 0})
        self.assertEqual(kod, 400)
        self.assertIn("401", v["hata"])
        self.assertNotIn("jev_onerilen", ms.ayarlari_oku()["sohbetler"][0]["mesajlar"][0])

    # ---- durum ve ayarlar
    def test_jev_durum_ucu(self):
        kod, v = self.get("/api/jev-durum")
        self.assertEqual(kod, 200)
        for alan in ("ayar_bulundu", "anahtar_dosyasi_bulundu", "model", "hazir", "son_cagri", "son_sonuc", "acik",
                     "yanit_puanla"):
            self.assertIn(alan, v)
        self.assertFalse(v["hazir"], "testlerde gerçek jev.json kullanılmaz (_ortam.py)")
        self.assertEqual((v["acik"], v["yanit_puanla"]), (True, False))
        self.assertNotIn("credentials", json.dumps(v))

    def test_jev_ayarlari_varsayilan_ve_sema(self):
        a = ms.ayarlari_oku()["ayarlar"]
        self.assertEqual((a["jev_acik"], a["jev_yanit_puanla"]), (True, False))
        self.assertEqual(self.post("/api/ayar", {"jev_acik": False, "jev_yanit_puanla": True})[0], 200)
        a = ms.ayarlari_oku()["ayarlar"]
        self.assertEqual((a["jev_acik"], a["jev_yanit_puanla"]), (False, True))
        for g in ({"jev_acik": "evet"}, {"jev_yanit_puanla": 1}):
            with self.subTest(g=g):
                self.assertEqual(self.post("/api/ayar", g)[0], 400)


def js_(anahtar):
    return js(anahtar)


if __name__ == "__main__":
    unittest.main()
