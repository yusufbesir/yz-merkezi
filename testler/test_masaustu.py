"""masaustu_sunucu.py'nin site mantığı için hızlı testler: tarayıcıya ve ekrana dokunmaz (sahte bağlantılarla)."""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import json
import sys
import threading
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

# ---------------------------------------------------------------- Tek Asistan: sahte motorlar paketi
# `motorlar` paketi başka bir geliştirme kolunda yazılıyor; bu testler gerçek pakete ve gerçek komut satırı araçlarına
# hiç dokunmaz: sys.modules'a sahte bir paket konur (sözleşme: MOTORLAR, motor(id), MotorHatasi).

MODELLER = {
    "claude": [{"id": "claude-haiku", "ad": "Claude Haiku", "sinif": "hizli"},
               {"id": "claude-sonnet", "ad": "Claude Sonnet 5.5", "sinif": "dengeli"},
               {"id": "claude-opus", "ad": "Claude Opus", "sinif": "guclu"}],
    "codex": [{"id": "gpt-mini", "ad": "GPT mini", "sinif": "hizli"}, {"id": "gpt", "ad": "GPT", "sinif": "dengeli"},
              {"id": "gpt-pro", "ad": "GPT pro", "sinif": "guclu"}],
    "gemini": [{"id": "gemini-flash", "ad": "Gemini Flash", "sinif": "hizli"},
               {"id": "gemini-pro", "ad": "Gemini Pro", "sinif": "dengeli"},
               {"id": "gemini-ultra", "ad": "Gemini Ultra", "sinif": "guclu"}],
}


class SahteMotor:
    """motorlar sözleşmesini taklit eder: id, ad, renk, hazir_mi(), modeller(), sor(...) -> olay üreteci."""

    def __init__(self, kimlik, ad, renk, hazir=True, giris=True, parcalar=None, yavas=False):
        self.id, self.ad, self.renk = kimlik, ad, renk
        self.hazir, self.giris, self.parcalar, self.yavas = hazir, giris, parcalar or ["Merhaba ", f"ben {kimlik}."], yavas
        self.cagrilar, self.hazir_mi_sayisi, self.sayac = [], 0, 0
        self.hata, self.istisna = None, None

    def hazir_mi(self):
        self.hazir_mi_sayisi += 1
        return {"hazir": self.hazir, "sebep": "" if self.hazir else f"{self.ad} kurulu değil", "surum": "1.2.3",
                "giris": self.giris}

    def modeller(self):
        return MODELLER[self.id]

    def sor(self, istem, oturum=None, model=None, sistem=None, calisma_klasoru=None, iptal=None):
        self.cagrilar.append({"istem": istem, "oturum": oturum, "model": model, "sistem": sistem,
                              "calisma_klasoru": calisma_klasoru})
        self.sayac += 1
        yeni = f"{self.id}-oturum-{self.sayac}" if oturum is None else oturum
        yield {"tur": "baslangic", "oturum": yeni}
        if self.istisna:
            raise self.istisna
        if self.hata:
            yield {"tur": "hata", "mesaj": self.hata}
            return
        verilen = []
        for parca in self.parcalar:
            if iptal is not None and iptal.is_set():
                return
            verilen.append(parca)
            yield {"tur": "parca", "metin": parca}
            if self.yavas:
                if iptal is not None:
                    iptal.wait(0.05)
                else:
                    time.sleep(0.05)
        while self.yavas == "bekle" and iptal is not None and not iptal.wait(0.05):
            pass
        if iptal is not None and iptal.is_set():
            return
        yield {"tur": "bitti", "oturum": yeni, "metin": "".join(verilen), "model": model or f"{self.id}-varsayilan",
               "sure": 0.25}


class MotorHatasi(Exception):
    pass


def sahte_motorlar():
    return {"claude": SahteMotor("claude", "Claude", "#d97757"),
            "codex": SahteMotor("codex", "Codex (ChatGPT)", "#10a37f"),
            "gemini": SahteMotor("gemini", "Gemini", "#4285f4")}


def sahte_paket(motorlar):
    import types
    paket = types.ModuleType("motorlar")
    paket.MOTORLAR = motorlar
    paket.MotorHatasi = MotorHatasi

    def motor(kimlik):
        if kimlik not in motorlar:
            raise MotorHatasi(f"Bilinmeyen motor: {kimlik}")
        return motorlar[kimlik]
    paket.motor = motor
    return paket


class MotorluHttpTabani(HttpTabani):
    """HttpTabani + sahte motorlar paketi (sys.modules). Motor durumu önbelleği ve iptal kayıtları temizlenir."""

    def setUp(self):
        super().setUp()
        self.motorlar = sahte_motorlar()
        yama = mock.patch.dict(sys.modules, {"motorlar": sahte_paket(self.motorlar)})
        yama.start()
        self.addCleanup(yama.stop)
        self.motor_onbellegini_temizle()
        self.addCleanup(self.motor_onbellegini_temizle)
        ms._IPTALLER.clear()
        ms.ayarlari_yaz({"ayarlar": dict(HAFIZASIZ)})

    @staticmethod
    def motor_onbellegini_temizle():
        ms._MOTOR_ONBELLEGI.update(zaman=0.0, liste=None)

    def sor(self, govde, belirtec=True):
        """POST /api/sor: (HTTP kodu, olay listesi). Hata gövdesi tek elemanlı liste olarak döner."""
        import urllib.error
        import urllib.request
        basliklar = {"Content-Type": "application/json"}
        if belirtec:
            basliklar["X-YZ-Token"] = ms.BELIRTEC
        talep = urllib.request.Request(f"http://127.0.0.1:{self.sunucu.server_port}/api/sor", json.dumps(govde).encode(),
                                       headers=basliklar, method="POST")
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with acici.open(talep, timeout=20) as y:
                return y.status, [json.loads(s) for s in y.read().decode("utf-8").splitlines() if s.strip()]
        except urllib.error.HTTPError as h:
            return h.code, [json.loads(h.read().decode("utf-8"))]

    def sohbet(self, sohbet_id):
        return next(s for s in ms.ayarlari_oku()["sohbetler"] if s["id"] == sohbet_id)

    @staticmethod
    def turler(olaylar):
        return [o["tur"] for o in olaylar]


class TekAsistanAkisTesti(MotorluHttpTabani):
    """POST /api/sor: akış sırası, hassas onay, hafıza bağlamı, yedek motor, oturum sürekliliği, durdurma, kayıt."""

    def test_akis_sirasi_ve_kayit(self):
        kod, o = self.sor({"metin": "Merhaba nasılsın"})   # sohbet/basit: ilk tercih gemini (hızlı)
        self.assertEqual(kod, 200)
        self.assertEqual(self.turler(o), ["secim", "baslangic", "parca", "parca", "bitti", "kayit"])
        secim = o[0]
        self.assertEqual((secim["motor"], secim["motor_ad"], secim["renk"]), ("gemini", "Gemini", "#4285f4"))
        self.assertEqual((secim["model"], secim["model_ad"], secim["sinif"]), ("gemini-flash", "Gemini Flash", "hizli"))
        self.assertEqual((secim["kaynak"], secim["yedek"]), ("kural", False))
        self.assertIn("sebep", secim)
        self.assertEqual("".join(x["metin"] for x in o if x["tur"] == "parca"), "Merhaba ben gemini.")
        self.assertEqual(o[4]["model"], "gemini-flash")
        kayit = o[-1]
        self.assertEqual(kayit["mesaj_sira"], 1)
        self.assertEqual(secim["sohbet"], kayit["sohbet"])
        m = self.motorlar["gemini"].cagrilar
        self.assertEqual(len(m), 1)
        self.assertEqual((m[0]["istem"], m[0]["oturum"], m[0]["model"]), ("Merhaba nasılsın", None, "gemini-flash"))
        self.assertIn("Türkçe", m[0]["sistem"])
        self.assertEqual(self.motorlar["claude"].cagrilar, [])
        s = self.sohbet(kayit["sohbet"])
        self.assertEqual(s["baslik"], "Merhaba nasılsın")
        self.assertEqual([x["rol"] for x in s["mesajlar"]], ["kullanici", "asistan"])
        asistan = s["mesajlar"][1]
        self.assertEqual((asistan["metin"], asistan["motor"], asistan["model"]), ("Merhaba ben gemini.", "gemini", "gemini-flash"))
        self.assertEqual(asistan["sure"], 0.25)
        self.assertEqual(asistan["model_ad"], "Gemini Flash")
        self.assertEqual(s["motor_oturumlari"], {"gemini": "gemini-oturum-1"})

    def test_otomatik_isin_turune_gore_motor_secer(self):
        _, o = self.sor({"metin": "Python fonksiyonundaki hatayı bul"})    # kod/basit → claude hızlı
        self.assertEqual((o[0]["motor"], o[0]["sinif"], o[0]["istek_turu"]), ("claude", "hizli", "kod"))
        _, o = self.sor({"metin": "Bu makaleyi özetle: " + "a" * 400 + ". Önce oku, sonra özetle."})
        self.assertEqual(o[0]["motor"], "gemini")                           # özet → gemini hızlı
        _, o = self.sor({"metin": "Ayrıntılı bir strateji planı hazırla " + "a" * 300})   # sohbet/zor → claude güçlü
        self.assertEqual((o[0]["motor"], o[0]["model"]), ("claude", "claude-opus"))

    def test_motor_elle_secilirse_o_motor_kullanilir(self):
        _, o = self.sor({"metin": "Merhaba", "motor": "codex"})
        self.assertEqual((o[0]["motor"], o[0]["kaynak"], o[0]["yedek"]), ("codex", "kullanici", False))
        self.assertEqual(self.motorlar["codex"].cagrilar[0]["model"], "gpt-mini")   # sohbet/basit tercihinde codex hızlı
        self.assertEqual(o[0]["sinif"], "hizli")

    def test_elle_secilen_modelin_kimligi_gecer(self):
        _, o = self.sor({"metin": "Merhaba", "motor": "claude", "model": "claude-opus"})
        self.assertEqual((o[0]["model"], self.motorlar["claude"].cagrilar[0]["model"]), ("claude-opus", "claude-opus"))
        _, o = self.sor({"metin": "Merhaba", "motor": "claude", "model": "olmayan-model"})   # listede yok: sınıfa göre
        self.assertEqual(o[0]["model"], "claude-haiku")

    def test_tercih_edilen_model_ayardan_gelir(self):
        ms.ayarlari_yaz({"ayarlar": {**HAFIZASIZ, "motor_modelleri": {"gemini": {"hizli": "gemini-pro"}}}})
        _, o = self.sor({"metin": "Merhaba nasılsın"})
        self.assertEqual((o[0]["motor"], o[0]["model"]), ("gemini", "gemini-pro"))

    def test_hassas_metin_tek_olay_ve_kayit_yok(self):
        anahtar = "bu anahtarı kullan: sk-" + "abcdefghijklmnop1234567890"
        kod, o = self.sor({"metin": anahtar})
        self.assertEqual(kod, 200)
        self.assertEqual(self.turler(o), ["onay_gerekli"])
        self.assertEqual((o[0]["kategori"], o[0]["aciklama"], o[0]["kaynak"]), ("api_anahtari", "bir API anahtarı", "kural"))
        self.assertEqual(ms.ayarlari_oku()["sohbetler"], [])
        for m in self.motorlar.values():
            self.assertEqual(m.cagrilar, [])
        _, o = self.sor({"metin": anahtar, "onayli": True})
        self.assertEqual(o[0]["tur"], "secim")
        self.assertEqual(o[-1]["tur"], "kayit")
        _, o = self.sor({"metin": anahtar, "onayli": "evet"})        # yalnızca tam true sayılır
        self.assertEqual(self.turler(o), ["onay_gerekli"])

    def test_hassas_uyari_kapaliysa_onay_istenmez(self):
        ms.ayarlari_yaz({"ayarlar": {**HAFIZASIZ, "hassas_uyari": False}})
        _, o = self.sor({"metin": "şifre: Abc12345 ile giriş yap"})
        self.assertEqual(o[0]["tur"], "secim")

    BAGLAM = {"metin": "Yusuf çay sever", "mod": "yerel", "karakter": 15, "kimlikler": []}

    def baglam_yamasi(self, kayit=None):
        """hafiza_kopru.baglam_kaydi sahtesi (gerçek kasaya dokunulmaz); çağrı sayısı self.baglam_cagrilari'nda."""
        if not hasattr(self, "baglam_cagrilari"):   # ilk yamada bekleyen onaylar temizlenir (ikinci yama korur)
            ms._BAGLAM_ONAYLARI.clear()
        self.baglam_cagrilari = []

        def baglam_kaydi(metin):
            self.baglam_cagrilari.append(metin)
            return dict(kayit or self.BAGLAM)
        yama = mock.patch.object(ms.hafiza_kopru, "baglam_kaydi", baglam_kaydi)
        yama.start()
        self.addCleanup(yama.stop)

    def test_hafiza_baglami_motora_gider_ve_ayri_kaydedilir(self):
        ms.ayarlari_yaz({"ayarlar": {"hafiza_ekle": True, "hafiza_aday": False, "hafiza_onay": False}})
        self.baglam_yamasi()
        _, o = self.sor({"metin": "Ne içeyim?", "motor": "claude"})
        self.assertEqual(self.motorlar["claude"].cagrilar[0]["istem"],
                         ms.hafiza_kopru.BASLIK + "\nYusuf çay sever" + ms.hafiza_kopru.AYIRAC + "Ne içeyim?")
        k = self.sohbet(o[-1]["sohbet"])["mesajlar"][0]
        self.assertEqual((k["metin"], k["baglam"]), ("Ne içeyim?", self.BAGLAM))   # ham mesaj ve bağlam ayrı alanlarda

    def test_hafiza_kapaliysa_baglam_aranmaz(self):
        self.baglam_yamasi()
        self.sor({"metin": "Merhaba", "motor": "claude"})
        self.assertEqual(self.baglam_cagrilari, [])

    # ---- hafıza bağlamı onayı (bulgu 3)
    def test_baglam_onayi_olayi_gonderim_ve_kayit_yok(self):
        ms.ayarlari_yaz({"ayarlar": {"hafiza_ekle": True, "hafiza_aday": False}})   # hafiza_onay varsayılan AÇIK
        self.baglam_yamasi()
        kod, o = self.sor({"metin": "Ne içeyim?", "motor": "claude"})
        self.assertEqual(kod, 200)
        self.assertEqual(self.turler(o), ["baglam_onay"])
        self.assertEqual((o[0]["baglam"], o[0]["karakter"]), ("Yusuf çay sever", 15))
        self.assertRegex(o[0]["baglam_kimligi"], r"^[A-Za-z0-9_-]{8,64}$")
        self.assertEqual(self.motorlar["claude"].cagrilar, [], "onay gelmeden motora hiçbir şey gitmez")
        self.assertEqual(ms.ayarlari_oku()["sohbetler"], [], "kayıt da yapılmaz")
        return o[0]

    def test_baglam_ekle_karari_gosterileni_ekler(self):
        olay = self.test_baglam_onayi_olayi_gonderim_ve_kayit_yok()
        self.baglam_yamasi({"metin": "BAŞKA bağlam", "mod": "yerel", "karakter": 12, "kimlikler": []})
        _, o = self.sor({"metin": "Ne içeyim?", "motor": "claude", "baglam_karari": "ekle",
                         "baglam_kimligi": olay["baglam_kimligi"]})
        self.assertEqual(o[0]["tur"], "secim")
        istem = self.motorlar["claude"].cagrilar[0]["istem"]
        self.assertIn("Yusuf çay sever", istem, "kullanıcının gördüğü bağlam eklenir")
        self.assertNotIn("BAŞKA", istem)
        self.assertEqual(self.baglam_cagrilari, [], "onaylı bağlam yeniden aranmaz")
        k = self.sohbet(o[-1]["sohbet"])["mesajlar"][0]
        self.assertEqual(k["baglam"]["metin"], "Yusuf çay sever")

    def test_baglam_ekleme_karari_baglamsiz(self):
        ms.ayarlari_yaz({"ayarlar": {"hafiza_ekle": True, "hafiza_aday": False}})
        self.baglam_yamasi()
        _, o = self.sor({"metin": "Ne içeyim?", "motor": "claude", "baglam_karari": "ekleme"})
        self.assertEqual(self.motorlar["claude"].cagrilar[0]["istem"], "Ne içeyim?")
        self.assertEqual(self.baglam_cagrilari, [])
        self.assertNotIn("baglam", self.sohbet(o[-1]["sohbet"])["mesajlar"][0])

    def test_baglam_kimligi_gecersiz_ya_da_tukenmisse_yeniden_sorulur(self):
        olay = self.test_baglam_onayi_olayi_gonderim_ve_kayit_yok()
        govde = {"metin": "Ne içeyim?", "motor": "claude", "baglam_karari": "ekle", "baglam_kimligi": olay["baglam_kimligi"]}
        self.sor(govde)                                  # kimlik tüketildi
        _, o = self.sor(govde)
        self.assertEqual(self.turler(o), ["baglam_onay"])
        _, o = self.sor({**govde, "metin": "Başka soru"})   # başka mesaja geçmez
        self.assertEqual(self.turler(o), ["baglam_onay"])
        for kotu in ({"baglam_karari": "belki"}, {"baglam_kimligi": "a b"}):
            kod, _ = self.sor({"metin": "x", **kotu})
            self.assertEqual(kod, 400)

    def test_hassas_onayindan_sonra_baglam_onayi_sorulur(self):
        ms.ayarlari_yaz({"ayarlar": {"hafiza_ekle": True, "hafiza_aday": False}})
        self.baglam_yamasi()
        anahtar = "şifre: Gizli1234"
        _, o = self.sor({"metin": anahtar, "motor": "claude"})
        self.assertEqual(self.turler(o), ["onay_gerekli"])
        _, o = self.sor({"metin": anahtar, "motor": "claude", "onayli": True})
        self.assertEqual(self.turler(o), ["baglam_onay"])
        _, o = self.sor({"metin": anahtar, "motor": "claude", "onayli": True, "baglam_karari": "ekleme"})
        self.assertEqual(o[0]["tur"], "secim")

    # ---- geçmiş maskeleme (bulgu 5)
    def test_gecmise_maskeli_yazilir_motora_ham_gider(self):
        sir = "sk-" + "abcdefghijklmnop1234567890"
        self.motorlar["claude"].parcalar = ["Anahtarın ", sir, " olarak kaydedildi."]
        _, o = self.sor({"metin": f"bu anahtarı kullan: {sir}", "motor": "claude", "onayli": True})
        self.assertIn(sir, self.motorlar["claude"].cagrilar[0]["istem"], "motora giden metin maskelenmez")
        kayit = o[-1]
        self.assertEqual(kayit["kullanici_metin"], "bu anahtarı kullan: [GİZLİ:api_anahtari]")
        self.assertEqual(kayit["asistan_metin"], "Anahtarın [GİZLİ:api_anahtari] olarak kaydedildi.")
        ham = ms.AYAR_DOSYASI.read_text("utf-8")
        self.assertNotIn(sir, ham)
        s = self.sohbet(kayit["sohbet"])
        self.assertEqual(s["mesajlar"][0]["metin"], "bu anahtarı kullan: [GİZLİ:api_anahtari]")
        self.assertNotIn(sir, s["baslik"])

    def test_dusuk_onemli_bulgu_uyari_olayi_gonderim_surer(self):
        _, o = self.sor({"metin": "beni 0532 123 45 67 numarasından ara", "motor": "claude"})
        self.assertEqual(self.turler(o)[:2], ["hassas_uyari", "secim"])
        self.assertEqual((o[0]["kategori"], o[0]["onem"]), ("kisisel", "dusuk"))
        self.assertEqual(len(self.motorlar["claude"].cagrilar), 1)

    def test_hafiza_adayi_yazilir(self):
        ms.ayarlari_yaz({"ayarlar": {"hafiza_ekle": False, "hafiza_aday": True}})
        with mock.patch.object(ms.hafiza_kopru, "aday_yaz") as yaz:
            self.sor({"metin": "Merhaba", "motor": "claude"})
        yaz.assert_called_once_with("Claude", "Merhaba", "Merhaba ben claude.")

    def test_hazir_olmayan_motor_yerine_siradaki_gecer(self):
        self.motorlar["gemini"].hazir = False
        _, o = self.sor({"metin": "Merhaba nasılsın"})
        self.assertEqual(self.turler(o)[:3], ["secim", "durum", "baslangic"])
        self.assertEqual((o[0]["motor"], o[0]["yedek"]), ("codex", True))
        self.assertEqual(o[1]["metin"], "Gemini hazır değil, Codex (ChatGPT) ile devam ediyorum")
        self.assertEqual(self.motorlar["gemini"].cagrilar, [])
        self.assertEqual(len(self.motorlar["codex"].cagrilar), 1)

    def test_elle_secilen_motor_hazir_degilse_de_yedege_gecilir(self):
        self.motorlar["claude"].hazir = False
        _, o = self.sor({"metin": "Merhaba", "motor": "claude"})
        self.assertEqual(o[0]["yedek"], True)
        self.assertEqual(o[1]["metin"], f"Claude hazır değil, {o[0]['motor_ad']} ile devam ediyorum")

    def test_hic_motor_hazir_degilse_hata_ve_kayit(self):
        for m in self.motorlar.values():
            m.hazir, m.giris = False, False
        kod, o = self.sor({"metin": "Merhaba"})
        self.assertEqual(kod, 200)
        self.assertEqual(self.turler(o), ["secim", "hata", "kayit"])
        self.assertIsNone(o[0]["motor"])
        self.assertIn("Hazır bir motor yok", o[1]["mesaj"])
        self.assertIn("claude", o[1]["mesaj"])      # giriş talimatı eklenir
        s = self.sohbet(o[-1]["sohbet"])
        self.assertEqual([x["rol"] for x in s["mesajlar"]], ["kullanici", "asistan"])
        self.assertEqual(s["mesajlar"][1]["hata"], o[1]["mesaj"])

    def test_motorlar_paketi_yoksa_motorlar_hazir_degil(self):
        with mock.patch.dict(sys.modules, {"motorlar": None}):
            self.motor_onbellegini_temizle()
            kod, o = self.sor({"metin": "Merhaba"})
            _, d = self.get("/api/durum")
        self.assertEqual(kod, 200)
        self.assertEqual(self.turler(o), ["secim", "hata", "kayit"])
        self.assertIn("Motorlar hazır değil", o[1]["mesaj"])
        self.assertEqual([m["id"] for m in d["motorlar"]], ["claude", "codex", "gemini"])
        self.assertFalse(any(m["hazir"] for m in d["motorlar"]))
        self.assertIn("Motorlar hazır değil", d["motorlar"][0]["sebep"])

    def test_oturum_sureklilgi_ayni_motorda(self):
        _, o1 = self.sor({"metin": "ilk soru", "motor": "claude"})
        sid = o1[-1]["sohbet"]
        _, o2 = self.sor({"metin": "ikinci soru", "motor": "claude", "sohbet": sid})
        c = self.motorlar["claude"].cagrilar
        self.assertEqual((c[0]["oturum"], c[1]["oturum"]), (None, "claude-oturum-1"))
        self.assertEqual(c[1]["istem"], "ikinci soru", "aynı motorun oturumu konuşmayı biliyor: transkript eklenmez")
        self.assertEqual(o2[-1]["sohbet"], sid)
        self.assertEqual(o2[-1]["mesaj_sira"], 3)
        s = self.sohbet(sid)
        self.assertEqual([x["rol"] for x in s["mesajlar"]], ["kullanici", "asistan", "kullanici", "asistan"])
        self.assertEqual(s["motor_oturumlari"], {"claude": "claude-oturum-1"})

    def test_motor_degisince_transkript_eklenir(self):
        _, o1 = self.sor({"metin": "ilk soru", "motor": "claude"})
        sid = o1[-1]["sohbet"]
        _, o2 = self.sor({"metin": "devam et", "motor": "codex", "sohbet": sid})
        istem = self.motorlar["codex"].cagrilar[0]["istem"]
        self.assertTrue(istem.startswith("Önceki konuşma özeti"))
        self.assertIn("- Kullanıcı: ilk soru", istem)
        self.assertIn("- Asistan (Claude): Merhaba ben claude.", istem)
        self.assertTrue(istem.endswith("Yeni mesaj:\ndevam et"))
        self.assertIsNone(self.motorlar["codex"].cagrilar[0]["oturum"])
        _, o3 = self.sor({"metin": "bir daha", "motor": "codex", "sohbet": sid})
        c = self.motorlar["codex"].cagrilar[1]
        self.assertEqual((c["istem"], c["oturum"]), ("bir daha", "codex-oturum-1"))
        # Claude'a geri dönüş: kendi oturumu var ama araya Codex girdi, yine de özet verilir
        self.sor({"metin": "claude'a dön", "motor": "claude", "sohbet": sid})
        c = self.motorlar["claude"].cagrilar[1]
        self.assertEqual(c["oturum"], "claude-oturum-1")
        self.assertTrue(c["istem"].startswith("Önceki konuşma özeti"))
        self.assertEqual(self.sohbet(sid)["motor_oturumlari"], {"claude": "claude-oturum-1", "codex": "codex-oturum-1"})

    def test_transkript_son_6_mesajla_sinirli(self):
        mesajlar = []
        for i in range(5):
            mesajlar += [{"rol": "kullanici", "metin": f"soru {i}"}, {"rol": "asistan", "metin": f"yanıt {i}", "motor": "claude"}]
        t = ms.transkript_olustur(mesajlar)
        self.assertEqual(t.count("\n- "), 6)           # son 6 mesaj, her biri "- " ile başlar
        self.assertIn("- Kullanıcı: soru 2", t)
        self.assertNotIn("soru 1", t)
        self.assertEqual(ms.transkript_olustur([]), "")
        eski = ms.transkript_olustur([{"metin": "eski soru", "yanitlar": {"gemini": "eski yanıt"}, "gonderilen": []}])
        self.assertIn("Kullanıcı: eski soru", eski)
        self.assertIn("Asistan (gemini): eski yanıt", eski)

    def test_yeniden_sor_son_yaniti_degistirir(self):
        _, o1 = self.sor({"metin": "ilk soru", "motor": "claude"})
        sid = o1[-1]["sohbet"]
        _, o2 = self.sor({"metin": "ilk soru", "motor": "codex", "sohbet": sid, "yeniden": True})
        self.assertEqual((o2[0]["motor"], o2[-1]["mesaj_sira"]), ("codex", 1))
        s = self.sohbet(sid)
        self.assertEqual([(m["rol"], m.get("motor")) for m in s["mesajlar"]], [("kullanici", None), ("asistan", "codex")])
        self.assertEqual(self.motorlar["codex"].cagrilar[0]["istem"], "ilk soru", "silinen yanıt özete girmez")
        # soru eşleşmezse normal yeni mesaj gibi eklenir
        self.sor({"metin": "başka soru", "motor": "codex", "sohbet": sid, "yeniden": True})
        self.assertEqual(len(self.sohbet(sid)["mesajlar"]), 4)

    def test_motor_hatasi_olayi_aynen_gecer_ve_kaydedilir(self):
        self.motorlar["claude"].hata = "Claude oturumu süresi dolmuş"
        _, o = self.sor({"metin": "Merhaba", "motor": "claude"})
        self.assertEqual(self.turler(o), ["secim", "baslangic", "hata", "kayit"])
        self.assertEqual(o[2]["mesaj"], "Claude oturumu süresi dolmuş")
        a = self.sohbet(o[-1]["sohbet"])["mesajlar"][1]
        self.assertEqual((a["hata"], a["metin"], a["motor"]), ("Claude oturumu süresi dolmuş", "", "claude"))

    def test_motor_istisnasi_hata_olayina_cevrilir(self):
        self.motorlar["claude"].istisna = MotorHatasi("Claude komutu bulunamadı")
        _, o = self.sor({"metin": "Merhaba", "motor": "claude"})
        self.assertEqual(self.turler(o)[-2:], ["hata", "kayit"])
        self.assertEqual(o[-2]["mesaj"], "Claude komutu bulunamadı")
        self.motorlar["claude"].istisna = ValueError("gizli iç ayrıntı")
        _, o = self.sor({"metin": "Merhaba", "motor": "claude"})
        self.assertEqual(o[-2]["tur"], "hata")
        self.assertNotIn("gizli iç ayrıntı", o[-2]["mesaj"])

    def test_dogrulama_hatalari_400(self):
        for g in ({}, {"metin": ""}, {"metin": "   "}, {"metin": 5}, {"metin": "x", "motor": "yok"},
                  {"metin": "x", "motor": 3}, {"metin": "x", "model": 5}, {"metin": "x", "sohbet": 5},
                  {"metin": "x" * (ms.SOR_METIN_EN_FAZLA + 1)}):
            with self.subTest(g=str(g)[:40]):
                kod, o = self.sor(g)
                self.assertEqual(kod, 400)
                self.assertIn("hata", o[0])
        self.assertEqual(self.sor({"metin": "x", "motor": None})[0], 200)    # null = otomatik

    def test_belirtecsiz_403(self):
        kod, _ = self.sor({"metin": "Merhaba"}, belirtec=False)
        self.assertEqual(kod, 403)
        for m in self.motorlar.values():
            self.assertEqual(m.cagrilar, [])

    def test_ayni_sohbette_ikinci_istek_reddedilir(self):
        ms._IPTALLER["mesgul-sohbet"] = threading.Event()
        ms.ayarlari_yaz({"ayarlar": dict(HAFIZASIZ), "sohbetler": [{"id": "mesgul-sohbet", "baslik": "x", "mesajlar": []}]})
        _, o = self.sor({"metin": "Merhaba", "sohbet": "mesgul-sohbet"})
        self.assertEqual(self.turler(o), ["hata"])
        self.assertIn("sürüyor", o[0]["mesaj"])
        self.assertEqual(self.sohbet("mesgul-sohbet")["mesajlar"], [])

    def canli_istek(self, govde):
        import http.client
        baglanti = http.client.HTTPConnection("127.0.0.1", self.sunucu.server_port, timeout=15)
        baglanti.request("POST", "/api/sor", json.dumps(govde), {"Content-Type": "application/json", "X-YZ-Token": ms.BELIRTEC})
        return baglanti, baglanti.getresponse()

    def test_durdur(self):
        self.motorlar["claude"].parcalar = ["bir ", "iki ", "üç "]
        self.motorlar["claude"].yavas = "bekle"        # parçaları verir, sonra iptali bekler
        baglanti, yanit = self.canli_istek({"metin": "uzun iş", "motor": "claude"})
        self.addCleanup(baglanti.close)
        secim = json.loads(yanit.readline())
        self.assertEqual(secim["tur"], "secim")
        olaylar = [secim]
        while True:       # üç parça gelene kadar oku
            olaylar.append(json.loads(yanit.readline()))
            if sum(1 for x in olaylar if x["tur"] == "parca") == 3:
                break
        kod, d = self.post("/api/durdur", {"sohbet": secim["sohbet"]})
        self.assertEqual((kod, d), (200, {"tamam": True, "durduruldu": True}))
        kalan = [json.loads(s) for s in yanit.read().decode("utf-8").splitlines() if s.strip()]
        self.assertEqual(kalan[-1]["tur"], "kayit")
        a = self.sohbet(secim["sohbet"])["mesajlar"][1]
        self.assertTrue(a["durduruldu"])
        self.assertEqual(a["metin"], "bir iki üç ")                # kısmi yanıt saklanır
        self.assertEqual(ms._IPTALLER, {})
        self.assertEqual(self.post("/api/durdur", {"sohbet": secim["sohbet"]})[1], {"tamam": True, "durduruldu": False})

    def test_istemci_kopunca_yanit_iptal_edilir_ve_kismi_metin_saklanir(self):
        import socket
        import struct
        self.motorlar["claude"].parcalar = [f"p{i} " for i in range(400)]
        self.motorlar["claude"].yavas = True
        govde = json.dumps({"metin": "uzun iş", "motor": "claude"}).encode()
        istek = (f"POST /api/sor HTTP/1.1\r\nHost: 127.0.0.1:{self.sunucu.server_port}\r\nContent-Type: application/json\r\n"
                 f"X-YZ-Token: {ms.BELIRTEC}\r\nContent-Length: {len(govde)}\r\n\r\n").encode() + govde
        soket = socket.create_connection(("127.0.0.1", self.sunucu.server_port), timeout=10)
        self.addCleanup(soket.close)
        soket.sendall(istek)
        gelen = b""
        while gelen.count(b'"tur": "parca"') < 1:   # ilk parça gelene kadar oku
            gelen += soket.recv(4096)
        secim = json.loads(gelen.split(b"\r\n\r\n", 1)[1].splitlines()[0])
        soket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))   # sekme kapandı: bağlantı sıfırlanır
        soket.close()
        bitis = time.monotonic() + 8
        mesajlar = []
        while time.monotonic() < bitis:
            s = next((x for x in ms.ayarlari_oku()["sohbetler"] if x["id"] == secim["sohbet"]), None)
            mesajlar = s["mesajlar"] if s else []
            if len(mesajlar) == 2:
                break
            time.sleep(0.1)
        self.assertEqual(len(mesajlar), 2, "kopan bağlantıda yanıt kaydedilmeli")
        self.assertTrue(mesajlar[1]["durduruldu"])
        self.assertTrue(mesajlar[1]["metin"].startswith("p0 "))
        self.assertLess(len(mesajlar[1]["metin"]), 400 * 4)
        self.assertEqual(ms._IPTALLER, {})

    def test_durdur_sohbet_vermeden_hepsini_durdurur(self):
        olay = threading.Event()
        ms._IPTALLER["a"] = olay
        self.assertEqual(self.post("/api/durdur", {})[1], {"tamam": True, "durduruldu": True})
        self.assertTrue(olay.is_set())
        ms._IPTALLER.clear()
        self.assertEqual(self.post("/api/durdur", {})[1]["durduruldu"], False)


class TekAsistanDurumTesti(MotorluHttpTabani):
    """/api/durum "motorlar", /api/motor-modelleri, /api/ayar şeması, /api/oneri (yeni biçim)."""

    def test_durum_motorlar_alanlari(self):
        self.motorlar["codex"].hazir, self.motorlar["codex"].giris = False, False
        self.motorlar["gemini"].hazir, self.motorlar["gemini"].giris = False, None
        kod, d = self.get("/api/durum")
        self.assertEqual(kod, 200)
        self.assertEqual([m["id"] for m in d["motorlar"]], ["claude", "codex", "gemini"])
        claude, codex, gemini = d["motorlar"]
        self.assertEqual(set(claude), {"id", "ad", "renk", "hazir", "sebep", "giris", "surum"})
        self.assertEqual((claude["ad"], claude["renk"], claude["hazir"], claude["giris"], claude["surum"]),
                         ("Claude", "#d97757", True, True, "1.2.3"))
        self.assertFalse(codex["hazir"])
        self.assertIn("codex login", codex["sebep"])        # giriş talimatı sebepte
        self.assertFalse(gemini["hazir"])
        self.assertEqual(gemini["sebep"], "Gemini kurulu değil")
        self.assertIn("programlar", d)
        self.assertIn("siteler", d)

    def test_durum_60_sn_onbellek_ve_yenile(self):
        self.get("/api/durum")
        self.get("/api/durum")
        self.assertEqual(self.motorlar["claude"].hazir_mi_sayisi, 1)
        self.get("/api/durum?motor_yenile=1")
        self.assertEqual(self.motorlar["claude"].hazir_mi_sayisi, 2)
        ms._MOTOR_ONBELLEGI["zaman"] -= ms.MOTOR_ONBELLEK_SURESI + 1
        self.get("/api/durum")
        self.assertEqual(self.motorlar["claude"].hazir_mi_sayisi, 3)

    def test_hazir_mi_istisnasi_hazir_degil_sayilir(self):
        def bozuk():
            raise RuntimeError("beklenmedik")
        self.motorlar["claude"].hazir_mi = bozuk
        _, d = self.get("/api/durum")
        self.assertFalse(d["motorlar"][0]["hazir"])
        self.assertIn("Durum okunamadı", d["motorlar"][0]["sebep"])
        self.assertTrue(d["motorlar"][1]["hazir"])

    def test_motor_modelleri_ucu(self):
        kod, v = self.get("/api/motor-modelleri")
        self.assertEqual(kod, 200)
        self.assertEqual(set(v), {"claude", "codex", "gemini"})
        self.assertEqual(v["claude"][1], {"id": "claude-sonnet", "ad": "Claude Sonnet 5.5", "sinif": "dengeli"})

    def test_motor_ayarlari_sema(self):
        a = ms.ayarlari_oku()["ayarlar"]
        self.assertEqual((a["varsayilan_motor"], a["motor_modelleri"]), ("otomatik", {}))
        self.assertEqual(self.post("/api/ayar", {"varsayilan_motor": "codex",
                                                 "motor_modelleri": {"claude": {"hizli": "claude-haiku"}}})[0], 200)
        a = ms.ayarlari_oku()["ayarlar"]
        self.assertEqual((a["varsayilan_motor"], a["motor_modelleri"]), ("codex", {"claude": {"hizli": "claude-haiku"}}))
        for g in ({"varsayilan_motor": "yok"}, {"varsayilan_motor": 5}, {"motor_modelleri": []},
                  {"motor_modelleri": {"yok": {}}}, {"motor_modelleri": {"claude": {"cok": "x"}}},
                  {"motor_modelleri": {"claude": {"hizli": 5}}}, {"motor_modelleri": {"claude": []}}):
            with self.subTest(g=g):
                self.assertEqual(self.post("/api/ayar", g)[0], 400)

    def test_varsayilan_ayar_ortak_sozlugu_bozmaz(self):
        a = ms.ayarlari_oku()
        a["ayarlar"]["motor_modelleri"]["claude"] = {"hizli": "x"}
        self.assertEqual(ms.VARSAYILAN_AYARLAR["motor_modelleri"], {})


class OneriHttpTesti(MotorluHttpTabani):
    """/api/oneri (motor + sınıf), /api/yonlendirme ve eski /api/modeller."""

    def test_oneri_siniflandirir_ve_model_secer(self):
        self.motorlar["codex"].hazir = False
        kod, v = self.post("/api/oneri", {"metin": "Bu makaleyi özetle"})
        self.assertEqual(kod, 200)
        self.assertEqual((v["tur"], v["zorluk"], v["kaynak"]), ("ozet", "basit", "kural"))
        o = v["oneriler"]
        self.assertEqual([x["motor"] for x in o], ["gemini", "claude", "codex"])     # özet: gemini › claude › codex
        self.assertEqual((o[0]["sinif"], o[0]["model"], o[0]["model_ad"]), ("hizli", "gemini-flash", "Gemini Flash"))
        self.assertEqual((o[1]["model"], o[2]["model"]), ("claude-haiku", "gpt-mini"))
        self.assertEqual([x["hazir"] for x in o], [True, True, False])
        self.assertIn("kurulu değil", o[2]["hazir_sebep"])
        self.assertIn("sebep", o[0])
        self.assertEqual(o[0]["motor_ad"], "Gemini")

    def test_zor_arastirma_gemini_guclu(self):
        _, v = self.post("/api/oneri", {"metin": "Elektrikli araçları karşılaştır ve kaynak göster. " + "a" * 1300})
        self.assertEqual((v["tur"], v["zorluk"]), ("arastirma", "zor"))
        self.assertEqual((v["oneriler"][0]["motor"], v["oneriler"][0]["model"]), ("gemini", "gemini-ultra"))

    def test_motor_yoksa_model_none(self):
        with mock.patch.dict(sys.modules, {"motorlar": None}):
            self.motor_onbellegini_temizle()
            _, v = self.post("/api/oneri", {"metin": "Merhaba nasılsın"})
        self.assertTrue(all(x["model"] is None and x["hazir"] is False for x in v["oneriler"]))

    def test_bos_metin_reddedilir(self):
        for g in ({"metin": ""}, {"metin": "   "}, {}, {"metin": 5}):
            with self.subTest(g=g):
                kod, v = self.post("/api/oneri", g)
                self.assertEqual(kod, 400)
                self.assertIn("boş", v["hata"])

    def test_oneri_ayar_dosyasina_dokunmaz(self):
        import os
        once = os.path.getmtime(ms.AYAR_DOSYASI)
        self.post("/api/oneri", {"metin": "merhaba dünya"})
        self.assertEqual(os.path.getmtime(ms.AYAR_DOSYASI), once)

    def test_son_siniflandirma_yonlendirme_durumunda(self):
        kod, v = self.get("/api/yonlendirme")
        self.assertEqual(kod, 200)
        self.assertIsNone(v["son"])
        self.assertEqual(len(v["tablo"]), 21)
        self.assertEqual(v["dosya"], str(ms.yonlendirici.YONLENDIRME_DOSYASI))
        self.assertEqual(v["uyarilar"], [])
        satir = next(r for r in v["tablo"] if r["tur"] == "kod" and r["zorluk"] == "orta")
        self.assertEqual(satir["tercihler"][0], {"motor": "claude", "motor_ad": "Claude", "sinif": "dengeli", "sinif_ad": "dengeli"})
        self.post("/api/oneri", {"metin": "Python hatasını bul"})
        _, v = self.get("/api/yonlendirme")
        self.assertEqual((v["son"]["tur"], v["son"]["zorluk"], v["son"]["tur_ad"]), ("kod", "basit", "kod"))
        self.assertRegex(v["son"]["zaman"], r"^\d\d:\d\d:\d\d$")
        self.assertNotIn("Python", json.dumps(v, ensure_ascii=False), "mesaj metni saklanmaz")

    def test_sor_da_son_siniflandirmayi_gunceller(self):
        self.sor({"metin": "SQL sorgusunu düzelt"})
        _, v = self.get("/api/yonlendirme")
        self.assertEqual(v["son"]["tur"], "kod")

    def test_bozuk_kural_dosyasi_yerlesige_duser(self):
        import tempfile
        with tempfile.TemporaryDirectory() as klasor:
            dosya = Path(klasor) / "y.json"
            dosya.write_text("{bozuk", "utf-8")
            with mock.patch.object(ms.yonlendirici, "YONLENDIRME_DOSYASI", dosya):
                kod, v = self.post("/api/oneri", {"metin": "merhaba dünya"})
                _, d = self.get("/api/yonlendirme")
                _, o = self.sor({"metin": "merhaba dünya"})
        self.assertEqual(kod, 200)
        self.assertEqual(v["oneriler"][0]["motor"], "gemini")
        self.assertTrue(v["uyarilar"] and d["uyarilar"])
        self.assertEqual(o[0]["tur"], "secim")        # kural dosyası bozuksa akış yine çalışır

    def test_eski_biçimli_kural_dosyasi_uyari_verir_ve_yerlesige_duser(self):
        import tempfile
        eski = {"varsayilan": {"basit": [{"site": "gemini", "model_icerir": "flash"}]}}
        with tempfile.TemporaryDirectory() as klasor:
            dosya = Path(klasor) / "y.json"
            dosya.write_text(json.dumps(eski), "utf-8")
            with mock.patch.object(ms.yonlendirici, "YONLENDIRME_DOSYASI", dosya):
                _, d = self.get("/api/yonlendirme")
        self.assertTrue(d["uyarilar"])
        self.assertEqual(d["tablo"][0]["tercihler"][0]["motor"], "gemini")

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

    def test_ucler_belirtecsiz_403(self):
        import urllib.error
        import urllib.request
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for yol in ("/api/modeller?site=gemini", "/api/yonlendirme", "/api/motor-modelleri", "/api/durum"):
            with self.subTest(yol=yol), self.assertRaises(urllib.error.HTTPError) as h:
                acici.open(f"http://127.0.0.1:{self.sunucu.server_port}{yol}", timeout=10)
            self.assertEqual(h.exception.code, 403)


MODEL_LISTELERI = {
    "gemini": {"modeller": [{"id": "g1", "ad": "Gemini 3 Flash", "secili": True},
                            {"id": "g2", "ad": "Gemini 3 Pro", "secili": False}], "sebep": ""},
}


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

    def test_onayli_sir_siteye_ham_gecmise_maskeli(self):
        gelen = []
        (kod, v), = self.calistir(gelen, [{"metin": self.ANAHTAR, "onayli": True}])
        self.assertEqual(kod, 200)
        self.assertIn("abcdefghijklmnop1234567890", gelen[0]["metin"], "siteye giden metin maskelenmez")
        self.assertEqual(v["sohbetler"][0]["mesajlar"][0]["metin"], "bu anahtarı kullan: [GİZLİ:api_anahtari]")
        self.assertNotIn("abcdefghijklmnop1234567890", ms.AYAR_DOSYASI.read_text("utf-8"))
        with mock.patch.object(ms, "site_konumu", return_value=None), \
                mock.patch.object(ms.hafiza_kopru, "aday_yaz"):
            kod, _ = self.post("/api/yanit-kaydet", {"sohbet": v["sohbet"], "mesaj_sira": 0, "site": "chatgpt",
                                                     "metin": "Tamam, parola: Gizli1234 kaydedildi"})
        self.assertEqual(kod, 200)
        kayit = ms.ayarlari_oku()["sohbetler"][0]["mesajlar"][0]["yanitlar"]["chatgpt"]
        self.assertEqual(kayit, "Tamam, parola: [GİZLİ:parola] kaydedildi")
        self.assertNotIn("Gizli1234", ms.AYAR_DOSYASI.read_text("utf-8"))

    def test_hassas_metin_onay_ister_ve_gonderilmez(self):
        gelen = []
        (kod, v), = self.calistir(gelen, [{"metin": self.ANAHTAR}])
        self.assertEqual(kod, 200)
        self.assertEqual((v["onay_gerekli"], v["kategori"], v["aciklama"]), (True, "api_anahtari", "bir API anahtarı"))
        self.assertEqual(gelen, [], "onay gelmeden hiçbir siteye gönderilmez")
        self.assertEqual(ms.ayarlari_oku()["sohbetler"], [], "yerel geçmişe de eklenmez")
        self.assertNotIn("abcdefghijklmnop1234567890", json.dumps(v))

    def test_150k_metnin_sonundaki_anahtar_onay_ister(self):
        gelen = []
        uzun = "lorem ipsum " * 12500 + "sk-" + "A1b2C3d4E5f6G7h8I9j0"
        (_, v), = self.calistir(gelen, [{"metin": uzun}])
        self.assertEqual((v["onay_gerekli"], v["kategori"]), (True, "api_anahtari"))
        self.assertEqual(gelen, [])

    def test_cok_uzun_temiz_metin_yalniz_onayli_gider(self):
        gelen = []
        uzun = "merhaba dünya " * 8000
        (_, v1), (_, v2) = self.calistir(gelen, [{"metin": uzun}, {"metin": uzun, "onayli": True}])
        self.assertEqual((v1["onay_gerekli"], v1["kategori"]), (True, "uzun_metin"))
        self.assertNotIn("onay_gerekli", v2)
        self.assertEqual(len(gelen), 1)

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


class JevBaglantiHttpTesti(MotorluHttpTabani):
    """Jev bağlantıları: /api/oneri (kaynak jev/kural), hassas uyarısı, /api/yanit-puanla, /api/jev-durum.

    jev.sinifla ve jev.hazir_mi yamalanır; ağa hiç çıkılmaz (gerçek Jev'e istek gitmez).
    """

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
        kod, v = self.post("/api/oneri", {"metin": "Bu makaleyi özetle"})   # kurala göre özet/basit olurdu
        self.assertEqual(kod, 200)
        self.assertEqual((v["tur"], v["zorluk"], v["kaynak"]), ("kod", "zor", "jev"))
        self.assertEqual(v["oneriler"][0]["motor"], "claude")   # kod/zor tercih sırası
        self.assertEqual(len(self.cagrilar), 2)
        self.assertEqual(sorted(tuple(sorted(c["secenekler"])) for c in self.cagrilar),
                         sorted([tuple(sorted(ms.yonlendirici.TURLER)), ("basit", "orta", "zor")]))
        _, d = self.get("/api/yonlendirme")
        self.assertEqual(d["son"]["kaynak"], "jev")

    def test_oneri_hassas_metni_jeve_gondermez(self):
        # Yazarken otomatik çağrılan /api/oneri, parola/anahtar içeren metni onay alınmadan Jev'e göndermemeli.
        self.jev_yamasi(lambda m, s: self.secim("kod"))
        ms.ayarlari_yaz({"ayarlar": dict(HAFIZASIZ)})
        kod, v = self.post("/api/oneri", {"metin": "şifre: Abc12345 ile giriş yap"})
        self.assertEqual(kod, 200)
        self.assertEqual(v["kaynak"], "kural")
        self.assertEqual(self.cagrilar, [])

    def test_oneri_jev_hata_verince_kural(self):
        self.jev_yamasi(lambda m, s: ms.jev.JevHatasi("Jev 8 saniyede yanıt vermedi."))
        kod, v = self.post("/api/oneri", {"metin": "Bu makaleyi özetle"})
        self.assertEqual(kod, 200)
        self.assertEqual((v["tur"], v["zorluk"], v["kaynak"]), ("ozet", "basit", "kural"))

    def test_oneri_jev_kapali_ya_da_hazir_degilse_cagrilmaz(self):
        self.jev_yamasi(lambda m, s: self.secim("kod"))
        ms.ayarlari_yaz({"ayarlar": {"jev_acik": False}})
        _, v = self.post("/api/oneri", {"metin": "Bu makaleyi özetle"})
        self.assertEqual(v["kaynak"], "kural")
        self.jev_yamasi(lambda m, s: self.secim("kod"), hazir=False)
        ms.ayarlari_yaz({"ayarlar": {"jev_acik": True}})
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

    # ---- jev_guvenli_sinifla: her Jev yolunda önce hassas tarama (bulgu 2)
    def test_sarmalayici_hassas_metni_gondermez(self):
        self.jev_yamasi(lambda m, s: self.secim("kod"))
        for metinler in (["şifre: Gizli1234"], ["temiz soru", "yanıt AKIA" + "IOSFODNN7EXAMPLE"], ["ara 0532 123 45 67"]):
            with self.subTest(metinler=metinler), self.assertRaises(ms.JevHassasHatasi) as h:
                ms.jev_guvenli_sinifla(metinler, ["a", "b"])
            self.assertEqual(str(h.exception), "hassas içerik, Jev'e gönderilmedi")
            self.assertIsInstance(h.exception, ms.jev.JevHatasi)
        with self.assertRaises(ms.JevHassasHatasi):     # gönderilecek birleşik metin de taranır
            ms.jev_guvenli_sinifla(["temiz"], ["a", "b"], gonderilecek="parola: x1y2z3")
        self.assertEqual(self.cagrilar, [])
        self.assertEqual(ms.jev_guvenli_sinifla(["temiz", "metin"], ["a", "b"])["secim"], "kod")
        self.assertEqual(self.cagrilar[0]["metin"], "temiz\nmetin")

    def test_sor_yonlendirme_hassasta_jeve_gitmez(self):
        self.jev_yamasi(lambda m, s: self.secim("kod") if "kod" in s else self.secim("zor"))
        ms.ayarlari_yaz({"ayarlar": dict(HAFIZASIZ)})
        _, o = self.sor({"metin": "şifre: Gizli1234 ile giriş yap", "onayli": True})
        self.assertEqual(o[0]["tur"], "secim")
        self.assertEqual((o[0]["kaynak"], o[0]["jev_notu"]), ("kural", "hassas içerik, Jev'e gönderilmedi"))
        self.assertEqual(self.cagrilar, [])
        _, o = self.sor({"metin": "Bu makaleyi özetle"})
        self.assertEqual((o[0]["kaynak"], o[0]["jev_notu"]), ("jev", None))
        self.assertEqual(len([c for c in self.cagrilar if "parola" not in c["secenekler"]]), 2)   # tür + zorluk

    def test_oneri_kisisel_bilgide_jev_notu(self):
        self.jev_yamasi(lambda m, s: self.secim("kod"))
        ms.ayarlari_yaz({"ayarlar": dict(HAFIZASIZ)})
        _, v = self.post("/api/oneri", {"metin": "ali@ornek.com adresine yaz"})
        self.assertEqual((v["kaynak"], v["jev_notu"]), ("kural", "hassas içerik, Jev'e gönderilmedi"))
        self.assertEqual(self.cagrilar, [])

    def test_gonder_on_tarama_dusuk_onemli_bulguda_jeve_gitmez(self):
        self.jev_yamasi(lambda m, s: self.secim("parola", 0.99))
        ((kod, v),), gelen = self.gonder_dene([{"metin": "beni 0532 123 45 67 numarasından ara"}])
        self.assertEqual((kod, v["gonderilen"]), (200, ["ChatGPT"]))
        self.assertEqual(v["hassas_uyari"]["kategori"], "kisisel")
        self.assertEqual(self.cagrilar, [])
        self.assertEqual(len(gelen), 1)

    def test_yanit_puanla_hassas_yanitta_jeve_gitmez(self):
        self.jev_yamasi(lambda m, s: self.secim("chatgpt"))
        for yanitlar in ({"chatgpt": "Anahtar: AKIA" + "IOSFODNN7EXAMPLE", "gemini": "B"},
                         {"chatgpt": "A", "gemini": "ara 0532 123 45 67"}):
            with self.subTest(yanitlar=yanitlar):
                self.sohbet_kur(yanitlar)
                kod, v = self.post("/api/yanit-puanla", {"sohbet": "s1", "mesaj_sira": 0})
                self.assertEqual(kod, 200)
                self.assertEqual((v["onerilen"], v["durum"]), (None, "hassas içerik, Jev'e gönderilmedi"))
                self.assertNotIn("jev_onerilen", ms.ayarlari_oku()["sohbetler"][0]["mesajlar"][0])
        ms.ayarlari_yaz({"ayarlar": {**HAFIZASIZ, "jev_yanit_puanla": True},
                         "sohbetler": [{"id": "s1", "baslik": "x", "mesajlar": [
                             {"metin": "şifre: Gizli1234 doğru mu?", "gonderilen": [], "sorunlar": [],
                              "yanitlar": {"chatgpt": "A", "gemini": "B"}}]}]})
        kod, v = self.post("/api/yanit-puanla", {"sohbet": "s1", "mesaj_sira": 0})
        self.assertEqual(v["durum"], "hassas içerik, Jev'e gönderilmedi")
        self.assertEqual(self.cagrilar, [])

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
