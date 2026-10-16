"""Model menüsü JS parçaları (`model_listesi`, `model_sec`) için gerçek Edge testi.

Gerçek ChatGPT/Gemini/Claude sitelerine hiç bağlanılmaz: `testler/sahte-site.html` (ChatGPT benzeri model seçicisi
olan yerel sayfa) geçici bir sunucuda YZ_TEST=1 ile sunulur; Edge geçici bir profille açılır ve JS parçaları
CDP ile bu sayfada çalıştırılır. Edge yoksa test atlanır.

Çalıştırma:  python -m unittest testler.test_model_menu   (ya da  python -m unittest discover testler)
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ortam  # noqa: E402,F401  (gerçek ayar dosyalarını korur; sunucu modülünden önce)
import masaustu_sunucu as ms  # noqa: E402
import siteler  # noqa: E402
import tarayici  # noqa: E402
from test_cdp import _edge_var_mi, _profil_sureclerini_kapat  # noqa: E402

DUGME = 'button[data-testid="model-switcher-dropdown-button"]'


@unittest.skipUnless(_edge_var_mi(), "Microsoft Edge bulunamadı, model menüsü testi atlandı")
class ModelMenusuTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.mkdtemp(prefix="yzmodel_")
        cls.profil = Path(cls.klasor) / "profil"
        cls.sayfa = None
        cls.sunucu = None
        cls.eski_test_kipi = os.environ.get("YZ_TEST")
        os.environ["YZ_TEST"] = "1"  # sunucu, sahte siteyi yalnızca bu kipte sunar
        cls.yamalar = [mock.patch.object(tarayici, "PROFIL", cls.profil), mock.patch.object(tarayici, "_boru", None)]
        for y in cls.yamalar:
            y.start()
        try:
            cls.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), ms.Isleyici)
            cls.sunucu.daemon_threads = True
            threading.Thread(target=cls.sunucu.serve_forever, daemon=True).start()
            cls.parca = f"127.0.0.1:{cls.sunucu.server_port}/test"
            cls.adres = f"http://127.0.0.1:{cls.sunucu.server_port}/test/sahte-site.html"
            uyari = tarayici.baslat(cls.adres, uygulama=False)
            if uyari:
                raise unittest.SkipTest(uyari)
            bitis = time.monotonic() + 20
            while cls.sayfa is None and time.monotonic() < bitis:
                cls.sayfa = tarayici.sayfa(cls.parca)
                if cls.sayfa is None:
                    time.sleep(0.3)
            if cls.sayfa is None:
                raise AssertionError("sahte site sekmesi 20 sn içinde açılmadı")
        except BaseException:
            cls.temizle()
            raise

    @classmethod
    def temizle(cls):
        if cls.sayfa is not None:
            try:
                cls.sayfa.kapat()
            except Exception:  # noqa: BLE001
                pass
        if cls.sunucu is not None:
            cls.sunucu.shutdown()
            cls.sunucu.server_close()
        tarayici.kapat()  # Browser.close + boru kapanır
        for y in reversed(cls.yamalar):
            y.stop()
        if cls.eski_test_kipi is None:
            os.environ.pop("YZ_TEST", None)
        else:
            os.environ["YZ_TEST"] = cls.eski_test_kipi
        _profil_sureclerini_kapat(cls.profil)
        shutil.rmtree(cls.klasor, ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        cls.temizle()

    def setUp(self):
        # Her test temiz sayfayla başlar (önceki testin seçtiği model sıfırlanır).
        self.sayfa.git(self.adres)
        self.bekle(lambda: self.js("document.querySelector(%r) ? document.querySelector(%r).textContent : ''" % (DUGME, DUGME))
                   == "GPT-5 Deneme", "sahte site yüklenmedi")

    # ------------------------------------------------------------ yardımcılar

    def js(self, kod):
        return self.sayfa.degerlendir(kod)

    def bekle(self, kosul, ne, sure=15):
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            if kosul():
                return
            time.sleep(0.2)
        self.fail(f"{ne} ({sure} sn)")

    def liste(self, site="chatgpt"):
        return self.js(siteler.SITELER[site]["js"]["model_listesi"])

    def sec(self, hedef, site="chatgpt"):
        return self.js(siteler.js_parca(site, "model_sec", hedef_model=hedef))

    def dugme_metni(self):
        return self.js("document.querySelector(%r).textContent.trim()" % DUGME)

    def menu_acik_mi(self):
        return self.js("document.querySelectorAll('[role=\"menu\"]').length > 0 "
                       "|| document.querySelector(%r).getAttribute('aria-expanded') === 'true'" % DUGME)

    # ------------------------------------------------------------ model_listesi

    def test_liste_uc_model_ve_secili(self):
        v = self.liste()
        self.assertNotIn("hata", v)
        self.assertEqual([m["ad"] for m in v["modeller"]], ["GPT-5 Deneme", "GPT-5 mini", "o-deneme"])
        self.assertEqual([m["id"] for m in v["modeller"]], ["gpt-5-deneme", "gpt-5-mini", "o-deneme"])
        self.assertEqual([m["secili"] for m in v["modeller"]], [True, False, False])
        self.assertIsInstance(v["sebep"], str)
        self.assertEqual(set(v), {"modeller", "sebep"})

    def test_liste_menuyu_kapatir(self):
        self.liste()
        self.assertFalse(self.menu_acik_mi(), "model_listesi menüyü kapatmalı")
        self.assertEqual(self.dugme_metni(), "GPT-5 Deneme", "okuma modeli değiştirmemeli")
        # iki kez üst üste çağrı da aynı sonucu verir (menü açık kalmadığının kanıtı)
        self.assertEqual(len(self.liste()["modeller"]), 3)
        self.assertFalse(self.menu_acik_mi())

    def test_liste_menu_bulunamadi(self):
        # Claude/Gemini seçicileri bu sahte sayfada yok: sözleşmedeki sabit yanıt.
        for site in ("claude", "gemini"):
            with self.subTest(site=site):
                self.assertEqual(self.liste(site), {"modeller": [], "sebep": "model menüsü bulunamadı"})
        self.assertEqual(self.dugme_metni(), "GPT-5 Deneme")

    # ------------------------------------------------------------ model_sec

    def test_sec_tam_ad(self):
        v = self.sec("GPT-5 mini")
        self.assertEqual(set(v), {"tamam", "secilen", "sebep"})
        self.assertTrue(v["tamam"], v)
        self.assertEqual(v["secilen"], "GPT-5 mini")
        self.assertEqual(self.dugme_metni(), "GPT-5 mini")
        self.assertFalse(self.menu_acik_mi())
        yeni = self.liste()["modeller"]
        self.assertEqual([m["secili"] for m in yeni], [False, True, False])

    def test_sec_buyuk_kucuk_harf_ve_id(self):
        self.assertTrue(self.sec("O-DENEME")["tamam"])
        self.assertEqual(self.dugme_metni(), "o-deneme")
        self.assertTrue(self.sec("gpt-5-mini")["tamam"])  # id ile
        self.assertEqual(self.dugme_metni(), "GPT-5 mini")

    def test_sec_icerir_tek_aday(self):
        v = self.sec("mini")
        self.assertTrue(v["tamam"], v)
        self.assertEqual(self.dugme_metni(), "GPT-5 mini")

    def test_sec_belirsiz_birden_cok_aday(self):
        v = self.sec("gpt-5")  # "GPT-5 Deneme" ve "GPT-5 mini" içerir
        self.assertFalse(v["tamam"])
        self.assertIn("GPT-5 Deneme", v["sebep"])
        self.assertIn("GPT-5 mini", v["sebep"])
        self.assertEqual(self.dugme_metni(), "GPT-5 Deneme", "belirsizlikte hiçbir şey seçilmemeli")
        self.assertFalse(self.menu_acik_mi())

    def test_sec_olmayan_model(self):
        v = self.sec("yok")
        self.assertFalse(v["tamam"])
        self.assertIn("yok", v["sebep"])
        self.assertEqual(self.dugme_metni(), "GPT-5 Deneme")
        self.assertFalse(self.menu_acik_mi(), "başarısız seçimde de menü kapanmalı")

    def test_sec_zaten_secili(self):
        v = self.sec("GPT-5 Deneme")
        self.assertTrue(v["tamam"], v)
        self.assertEqual(v["secilen"], "GPT-5 Deneme")
        self.assertFalse(self.menu_acik_mi())

    def test_sec_hedef_yok_ve_menu_yok(self):
        self.assertEqual(self.js(siteler.SITELER["chatgpt"]["js"]["model_sec"]),
                         {"tamam": False, "secilen": "", "sebep": "hedef model verilmedi"})
        v = self.sec("GPT-5 mini", site="claude")
        self.assertFalse(v["tamam"])
        self.assertEqual(v["sebep"], "model menüsü bulunamadı")
        self.assertEqual(self.dugme_metni(), "GPT-5 Deneme")


    # ------------------------------------------------------------ alt menü ("Diğer modeller")

    ALT_MENU_KURULUMU = """
    (() => {
      const eski = document.querySelector(%r);
      const dugme = eski.cloneNode(true);  // sahte sitenin kendi dinleyicileri düşer
      eski.replaceWith(dugme);
      dugme.textContent = "Ana-1";
      let ana = null, alt = null;
      const kapat = () => { [ana, alt].forEach((x) => x && x.remove()); ana = alt = null; dugme.setAttribute("aria-expanded", "false"); };
      const oge = (ad, kap) => {
        const e = document.createElement("div");
        e.setAttribute("role", "menuitem"); e.textContent = ad; kap.appendChild(e); return e;
      };
      dugme.addEventListener("click", () => {
        if (ana) { kapat(); return; }
        ana = document.createElement("div"); ana.setAttribute("role", "menu");
        oge("Ana-1", ana).setAttribute("aria-checked", "true");
        const ikinci = oge("Ana-2", ana);
        ikinci.addEventListener("click", () => { dugme.textContent = "Ana-2"; kapat(); });
        const diger = oge("Diğer modeller", ana);
        diger.setAttribute("aria-haspopup", "menu");
        diger.addEventListener("click", () => {
          if (alt) { return; }
          alt = document.createElement("div"); alt.setAttribute("role", "menu");
          ["Eski-1", "Eski-2"].forEach((ad) => oge(ad, alt).addEventListener("click", () => { dugme.textContent = ad; kapat(); }));
          document.body.appendChild(alt);
        });
        document.body.appendChild(ana);
        dugme.setAttribute("aria-expanded", "true");
      });
      document.addEventListener("keydown", (o) => { if (o.key === "Escape") { kapat(); } });
      return true;
    })()
    """ % DUGME

    def test_alt_menu_okunur_ve_secilir(self):
        self.assertTrue(self.js(self.ALT_MENU_KURULUMU))
        v = self.liste()
        self.assertEqual([m["ad"] for m in v["modeller"]], ["Ana-1", "Ana-2", "Eski-1", "Eski-2"], v)
        self.assertEqual([m["secili"] for m in v["modeller"]], [True, False, False, False])
        self.assertFalse(self.menu_acik_mi(), "alt menü de dahil hepsi kapanmalı")
        self.assertEqual(self.dugme_metni(), "Ana-1")
        v = self.sec("eski-2")  # yalnızca alt menüde var
        self.assertTrue(v["tamam"], v)
        self.assertEqual(v["secilen"], "Eski-2")
        self.assertEqual(self.dugme_metni(), "Eski-2")
        self.assertFalse(self.menu_acik_mi())
        self.assertFalse(self.sec("Eski")["tamam"], "alt menüde iki aday: belirsiz")


if __name__ == "__main__":
    unittest.main()
