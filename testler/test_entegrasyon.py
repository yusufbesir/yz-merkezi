"""Site entegrasyonu uçtan uca testi: gerçek Edge + geçici profil + ChatGPT'yi taklit eden yerel sayfa.

Gerçek ChatGPT/Gemini/Claude sitelerine hiç bağlanılmaz; `siteler.SITELER["chatgpt"]` kaydı test süresince
uygulama sunucusunun `/test/sahte-site.html` sayfasına yönlendirilir (YZ_TEST=1). Edge yoksa test atlanır.

Çalıştırma:  python -m unittest discover testler
"""
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cdp  # noqa: E402
import masaustu_sunucu as ms  # noqa: E402
import pencereler as pc  # noqa: E402
import siteler  # noqa: E402
import tarayici  # noqa: E402
from test_cdp import _edge_var_mi, _profil_sureclerini_kapat  # noqa: E402


def _bos_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@unittest.skipUnless(_edge_var_mi(), "Microsoft Edge bulunamadı, site entegrasyon testi atlandı")
class SiteEntegrasyonTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.mkdtemp(prefix="yzent_")
        cls.profil = Path(cls.klasor) / "profil"
        cdp_portu = _bos_port()
        cls.yamalar = []

        def yama(nesne, ad, deger):
            p = mock.patch.object(nesne, ad, deger)
            p.start()
            cls.yamalar.append(p)

        # Ortam değişkenleri ayrı süreçler için; modüller bunları içe aktarılırken okuduğundan öznitelikler de yamalanır.
        cls.eski_ortam = {k: os.environ.get(k) for k in
                          ("YZ_TEST", "YZ_TARAYICI_PROFILI", "YZ_CDP_PORT", "YZ_MASAUSTU_AYAR", "YZ_MASAUSTU_PORT")}
        os.environ.update({"YZ_TEST": "1", "YZ_TARAYICI_PROFILI": str(cls.profil), "YZ_CDP_PORT": str(cdp_portu),
                           "YZ_MASAUSTU_AYAR": str(Path(cls.klasor) / "ayar.json")})
        yama(tarayici, "PROFIL", cls.profil)
        yama(tarayici, "CDP_PORT", cdp_portu)
        yama(ms, "AYAR_DOSYASI", Path(cls.klasor) / "ayar.json")
        yama(ms, "kendi_pencere", lambda: None)  # kullanıcının gerçek "Yapay Zeka Merkezi" penceresine dokunma
        ms.is_kilidi = threading.Lock()

        cls.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), ms.Isleyici)
        cls.sunucu.daemon_threads = True
        threading.Thread(target=cls.sunucu.serve_forever, daemon=True).start()
        cls.kok = f"http://127.0.0.1:{cls.sunucu.server_port}"
        os.environ["YZ_MASAUSTU_PORT"] = str(cls.sunucu.server_port)

        sahte = cls.kok + "/test/sahte-site.html"
        kayit = siteler.SITELER["chatgpt"]
        cls.eski_kayit = {k: kayit[k] for k in ("adres", "yeni_sohbet_adresi", "pencere_parcasi", "giris_parcalari")}
        kayit.update(adres=sahte, yeni_sohbet_adresi=sahte,
                     pencere_parcasi=f"127.0.0.1:{cls.sunucu.server_port}/test", giris_parcalari=[])
        # Gerçek Gemini ve Claude siteleri hiçbir koşulda açılmasın.
        cls.post("/api/ayar", {"secili": {"site:gemini": False, "site:claude": False}})
        cls.sohbet_id = None

    @classmethod
    def tearDownClass(cls):
        cls.sunucu.shutdown()
        cls.sunucu.server_close()
        siteler.SITELER["chatgpt"].update(cls.eski_kayit)
        for p in reversed(cls.yamalar):
            p.stop()
        for k, v in cls.eski_ortam.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _profil_sureclerini_kapat(cls.profil)
        shutil.rmtree(cls.klasor, ignore_errors=True)

    # ------------------------------------------------------------ yardımcılar

    @classmethod
    def post(cls, yol, veri):
        talep = urllib.request.Request(cls.kok + yol, json.dumps(veri).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(talep, timeout=60) as y:
            return json.load(y)

    @classmethod
    def get(cls, yol):
        with urllib.request.urlopen(cls.kok + yol, timeout=60) as y:
            return json.load(y)

    def chatgpt_durumu(self):
        return next(s for s in self.get("/api/durum")["siteler"] if s["id"] == "chatgpt")

    def bekle(self, kosul, sure=20, ne="koşul"):
        bitis = time.monotonic() + sure
        son = None
        while time.monotonic() < bitis:
            son = kosul()
            if son:
                return son
            time.sleep(0.4)
        self.fail(f"{ne} {sure} sn içinde gerçekleşmedi (son değer: {son!r})")

    def yanit_bekle(self, taban):
        """Arayüzün yaptığı gibi 2 sn aralıksız birkaç kez yoklar; yazıyor=false ve metin dolu olunca döner."""
        def kosul():
            v = self.get(f"/api/yanit?site=chatgpt&taban={taban}")
            return v if not v["yaziyor"] and v["metin"] else None
        return self.bekle(kosul, 20, "yanıt")

    # ------------------------------------------------------------ adımlar (sıra önemli)

    def test_01_varsayilan_hedefler(self):
        d = self.get("/api/durum")
        self.assertEqual([s["id"] for s in d["siteler"]], ["chatgpt", "gemini", "claude"])
        self.assertFalse(self.chatgpt_durumu()["acik"])
        self.assertTrue(self.chatgpt_durumu()["secili"])
        self.assertFalse(any(p["secili"] for p in d["programlar"]), "masaüstü programları varsayılan olarak seçili olmamalı")

    def test_02_site_ac_ve_giris(self):
        v = self.post("/api/site-ac", {"id": "chatgpt"})
        self.assertTrue(v["tamam"])
        self.assertIn("ChatGPT", v["mesaj"])
        d = self.bekle(lambda: (lambda s: s if s["acik"] and s["giris"] else None)(self.chatgpt_durumu()), 30, "giriş yapıldı durumu")
        self.assertTrue(d["giris"])
        # ikinci çağrı: pencere zaten açık, öne getirilir
        self.assertTrue(self.post("/api/site-ac", {"id": "chatgpt"})["zaten_acik"])

    def test_03_site_sohbetleri(self):
        v = self.get("/api/site-sohbetler?yenile=1")
        self.assertEqual(v["hatalar"], [])
        self.assertEqual([s["site"] for s in v["sohbetler"]], ["chatgpt"] * 3)
        self.assertEqual([s["id"] for s in v["sohbetler"]], ["chatgpt:1", "chatgpt:2", "chatgpt:3"])
        self.assertEqual([s["baslik"] for s in v["sohbetler"]], ["Birinci sohbet", "İkinci sohbet", "Üçüncü sohbet"])
        self.assertTrue(v["sohbetler"][0]["url"].endswith("/test/c/1"))

    def test_04_gonder_ve_yanit(self):
        v = self.post("/api/gonder", {"metin": "Merhaba"})
        self.assertEqual(v["gonderilen"], ["ChatGPT"])
        self.assertEqual(v["sorunlar"], [])
        self.assertEqual(len(v["yanit_bekleyen"]), 1)
        self.assertEqual((v["yanit_bekleyen"][0]["site"], v["yanit_bekleyen"][0]["taban"]), ("chatgpt", 0))
        type(self).sohbet_id, sira = v["sohbet"], v["mesaj_sira"]
        self.assertEqual(sira, 0)
        y = self.yanit_bekle(0)
        self.assertEqual(y["metin"], "Yanıt: Merhaba")
        # arayüzün yanıt bitince yaptığı kayıt
        self.post("/api/yanit-kaydet", {"sohbet": self.sohbet_id, "mesaj_sira": 0, "site": "chatgpt", "metin": y["metin"]})
        sohbet = next(s for s in self.get("/api/durum")["sohbetler"] if s["id"] == self.sohbet_id)
        self.assertEqual(sohbet["mesajlar"][0]["yanitlar"], {"chatgpt": "Yanıt: Merhaba"})

    def test_05_mesajlar_sohbet_acilinca(self):
        v = self.post("/api/site-sohbet-ac", {"site": "chatgpt", "url": self.kok + "/test/sahte-site.html"})
        self.assertEqual([m["rol"] for m in v["mesajlar"]], ["kullanici", "asistan"])
        self.assertEqual([m["metin"] for m in v["mesajlar"]], ["Merhaba", "Yanıt: Merhaba"])

    def test_06_cok_satirli_mesaj_enter_tetiklemez(self):
        v = self.post("/api/gonder", {"metin": "Satır 1\nSatır 2\nSatır 3", "sohbet": self.sohbet_id})
        self.assertEqual(v["gonderilen"], ["ChatGPT"])
        self.assertEqual(v["yanit_bekleyen"][0]["taban"], 1)
        y = self.yanit_bekle(1)
        self.assertEqual(y["metin"], "Yanıt: Satır 1\nSatır 2\nSatır 3")
        m = self.post("/api/site-sohbet-ac", {"site": "chatgpt", "url": ""})["mesajlar"]
        self.assertEqual(len(m), 4, "çok satırlı metin tek mesaj olarak gitmeli (satır arasında Enter göndermemeli)")

    def test_07_sohbet_adresine_gitme(self):
        v = self.post("/api/site-sohbet-ac", {"site": "chatgpt", "url": self.kok + "/test/c/2"})
        self.assertEqual(len(v["mesajlar"]), 2)
        self.assertEqual(v["mesajlar"][0], {"rol": "kullanici", "metin": "Soru 2"})
        self.assertEqual(v["mesajlar"][1], {"rol": "asistan", "metin": "Yanıt 2"})
        self.assertEqual(v["baslik"], "İkinci sohbet")

    def test_08_sohbet_url_ile_gonder(self):
        # Yeni bir ortak sohbette (sohbet_url yok) pencere sohbet sayfasında olsa da yeni sohbet sayfasına dönülür.
        v = self.post("/api/gonder", {"metin": "Yeni"})
        self.assertEqual(v["yanit_bekleyen"][0]["taban"], 0, "yeni sohbet sayfasında asistan mesajı olmamalı")
        self.yanit_bekle(0)
        # Belirli bir site sohbetine gönderme: o adrese gidilir, yerel geçmişe eklenmez.
        yerel_once = len(self.get("/api/durum")["sohbetler"])
        v = self.post("/api/gonder", {"metin": "Üçe", "sohbet_url": self.kok + "/test/c/3"})
        self.assertIsNone(v["sohbet"])
        self.assertEqual(v["yanit_bekleyen"][0]["taban"], 1)
        self.assertEqual(self.yanit_bekle(1)["metin"], "Yanıt: Üçe")
        self.assertEqual(len(self.get("/api/durum")["sohbetler"]), yerel_once)
        m = self.post("/api/site-sohbet-ac", {"site": "chatgpt", "url": self.kok + "/test/c/3"})["mesajlar"]
        self.assertEqual([x["metin"] for x in m], ["Soru 3", "Yanıt 3", "Üçe", "Yanıt: Üçe"])

    def test_09_baska_siteye_yonlendirme_reddedilir(self):
        with self.assertRaises(urllib.error.HTTPError) as h:
            self.post("/api/site-sohbet-ac", {"site": "chatgpt", "url": "https://example.com/c/1"})
        self.assertEqual(h.exception.code, 400)

    def test_10_yan_yana_diz_site_penceresi(self):
        v = self.post("/api/diz", {})
        self.assertEqual(v["adet"], 1)
        hedef = tarayici.hedef(f"127.0.0.1:{self.sunucu.server_port}/test")
        with cdp.Baglanti(cdp.tarayici_ws(tarayici.CDP_PORT)) as b:
            sinir = b.komut("Browser.getWindowForTarget", targetId=hedef["id"])["bounds"]
        sol, ust, sag, alt = pc.calisma_alani()
        benim_genislik = max(400, (sag - sol) * 28 // 100)  # varsayılan yerleşim: uygulama solda, siteler sağda
        olcek = pc.olcek()
        beklenen = ((sol + benim_genislik) / olcek, ust / olcek, (sag - sol - benim_genislik) / olcek, (alt - ust) / olcek)
        for gercek, beklenen_deger in zip((sinir["left"], sinir["top"], sinir["width"], sinir["height"]), beklenen):
            self.assertAlmostEqual(gercek, beklenen_deger, delta=20, msg=f"{sinir} != {beklenen}")
        # bağımsız olarak elle de yerleştirilebilir
        yeni = cdp.pencere_sinirlari(tarayici.CDP_PORT, hedef["id"], 100, 80, 640, 480)
        self.assertEqual((yeni["left"], yeni["top"], yeni["width"], yeni["height"]), (100, 80, 640, 480))

    def test_11_kapali_site_sorunu_turkce(self):
        # Pencere kapatılınca (Edge'in açık sekmesi kapanınca) site "kapalı" görünür.
        hedef = tarayici.hedef(f"127.0.0.1:{self.sunucu.server_port}/test")
        with cdp.Baglanti(cdp.tarayici_ws(tarayici.CDP_PORT)) as b:
            b.komut("Target.closeTarget", targetId=hedef["id"])
        d = self.bekle(lambda: (lambda s: s if not s["acik"] else None)(self.chatgpt_durumu()), 10, "kapalı durumu")
        self.assertIsNone(d["giris"])
        with self.assertRaises(urllib.error.HTTPError) as h:
            self.get("/api/yanit?site=chatgpt")
        self.assertEqual(h.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
