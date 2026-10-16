"""CDP boru istemcisi testleri: sahte "tarayıcı" (os.pipe ile iki uç) ve (Edge varsa) gerçek bütünleşme.

Çalıştırma:  python -m unittest discover testler
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
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _ortam  # noqa: E402,F401  (profil/ayar yollarını geçici klasöre yönlendirir; modüllerden önce)
import cdp  # noqa: E402
import tarayici  # noqa: E402


# ---------------------------------------------------------------- sahte tarayıcı

class SahteTarayici:
    """Bizim BoruBaglantisi'na karşı uçta duran sahte tarayıcı.

    İki anonim boru açılır; ayrı bir thread gelen `\\0` ayraçlı komutları okur, `gelenler` listesine ekler ve
    `davranis(istek, sahte)` ile dönen mesajları (sözlük ya da ham bayt) geri yazar.
    """

    def __init__(self, davranis):
        self.davranis = davranis
        self.gelenler = []
        self._t_okur, biz_yazariz = os.pipe()
        biz_okuruz, self._t_yazar = os.pipe()
        self._yazma_kilidi = threading.Lock()
        self._yazma_kapali = False
        self.eof_goruldu = threading.Event()
        threading.Thread(target=self._calis, daemon=True).start()
        self.boru = cdp.BoruBaglantisi(biz_okuruz, biz_yazariz)

    def _calis(self):
        tampon = bytearray()
        try:
            while True:
                parca = os.read(self._t_okur, 65536)
                if not parca:
                    break
                tampon += parca
                while b"\0" in tampon:
                    i = tampon.index(b"\0")
                    istek = json.loads(bytes(tampon[:i]).decode("utf-8"))
                    del tampon[:i + 1]
                    self.gelenler.append(istek)
                    for cevap in self.davranis(istek, self) or []:
                        self.yaz(cevap)
        except OSError:
            pass
        finally:
            self.eof_goruldu.set()
            os.close(self._t_okur)
            self.yazmayi_kapat()

    def yaz(self, mesaj):
        veri = mesaj if isinstance(mesaj, bytes) else json.dumps(mesaj).encode("utf-8") + b"\0"
        with self._yazma_kilidi:
            if not self._yazma_kapali:
                os.write(self._t_yazar, veri)

    def yazmayi_kapat(self):
        """Tarayıcı kapandı gibi: bizim okuyucumuz EOF görür."""
        with self._yazma_kilidi:
            if not self._yazma_kapali:
                self._yazma_kapali = True
                os.close(self._t_yazar)

    def bekle(self, kosul, sure=2):
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            if any(kosul(g) for g in list(self.gelenler)):
                return True
            time.sleep(0.02)
        return False


def sonuc_ver(deger):
    """Her komuta {"result": {"result": {"value": deger}}} yanıtı veren davranış (sessionId korunur)."""
    def davranis(istek, s):
        yanit = {"id": istek["id"], "result": {"result": {"value": deger}}}
        if "sessionId" in istek:
            yanit["sessionId"] = istek["sessionId"]
        return [yanit]
    return davranis


class BoruTabani(unittest.TestCase):
    def kur(self, davranis):
        s = SahteTarayici(davranis)
        self.addCleanup(s.boru.kapat)
        self.addCleanup(s.yazmayi_kapat)
        return s


class BoruBaglantisiTesti(BoruTabani):
    def test_komut_ve_degerlendir(self):
        s = self.kur(sonuc_ver(42))
        self.assertEqual(s.boru.komut("Runtime.evaluate", expression="1+41"), {"result": {"value": 42}})
        self.assertEqual([g["id"] for g in s.gelenler], [1])
        self.assertEqual(s.gelenler[0], {"id": 1, "method": "Runtime.evaluate", "params": {"expression": "1+41"}})
        self.assertNotIn("sessionId", s.gelenler[0])
        s.boru.komut("Browser.getVersion")
        self.assertEqual([g["id"] for g in s.gelenler], [1, 2])  # kimlikler artar

    def test_yanitlar_kimlige_gore_eslenir_sira_karisik_olsa_da(self):
        bekleyen = []

        def davranis(istek, s):
            bekleyen.append(istek)
            if len(bekleyen) < 2:
                return []
            # iki komut da geldi: ters sırayla, araya başkasının yanıtını ve bir olayı katarak yanıtla
            return ([{"id": 999, "result": {"kim": "kimse"}}, {"method": "Page.loadEventFired", "params": {}}]
                    + [{"id": i["id"], "result": {"kim": i["params"]["ad"]}} for i in reversed(bekleyen)])
        s = self.kur(davranis)
        sonuclar = {}

        def calistir(ad):
            sonuclar[ad] = s.boru.komut("Deneme.komut", zaman=5, ad=ad)
        isler = [threading.Thread(target=calistir, args=(ad,)) for ad in ("bir", "iki")]
        for i in isler:
            i.start()
            time.sleep(0.05)
        for i in isler:
            i.join(5)
        self.assertEqual(sonuclar, {"bir": {"kim": "bir"}, "iki": {"kim": "iki"}})
        self.assertEqual([o["method"] for o in s.boru.olaylar], ["Page.loadEventFired"])

    def test_parcali_ve_birlesik_mesajlar(self):
        def davranis(istek, s):
            tam = json.dumps({"id": istek["id"], "result": {"result": {"value": "ö" * 3000}}}).encode("utf-8") + b"\0"
            olay = json.dumps({"method": "Olay.bir", "params": {}}).encode() + b"\0"
            for i in range(0, len(tam), 700):  # yanıt birkaç parçada gelir
                s.yaz(tam[i:i + 700])
                time.sleep(0.01)
            s.yaz(olay + olay)  # iki mesaj tek yazımda
            return []
        s = self.kur(davranis)
        self.assertEqual(cdp.Oturum(s.boru, "H", "O").degerlendir("x"), "ö" * 3000)
        self.assertTrue(self._bekle(lambda: len(s.boru.olaylar) == 2))

    def _bekle(self, kosul, sure=2):
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            if kosul():
                return True
            time.sleep(0.02)
        return False

    def test_bozuk_mesaj_atlanir(self):
        def davranis(istek, s):
            return [b"{bozuk json\0", b"[1,2]\0", {"id": istek["id"], "result": {"tamam": True}}]
        s = self.kur(davranis)
        self.assertEqual(s.boru.komut("X.y"), {"tamam": True})
        self.assertTrue(s.boru.canli_mi())

    def test_hata_yaniti_cdp_hatasi(self):
        s = self.kur(lambda i, s: [{"id": i["id"], "error": {"code": -32601, "message": "yok boyle komut"}}])
        with self.assertRaises(cdp.CdpHatasi) as h:
            s.boru.komut("Bilinmeyen.komut")
        self.assertIn("yok boyle komut", str(h.exception))
        self.assertIn("-32601", str(h.exception))

    def test_js_istisnasi_cdp_hatasi(self):
        sonuc = {"result": {"type": "object"},
                 "exceptionDetails": {"text": "Uncaught", "exception": {"description": "ReferenceError: x is not defined"}}}
        s = self.kur(lambda i, s: [{"id": i["id"], "sessionId": i.get("sessionId"), "result": sonuc}])
        with self.assertRaises(cdp.CdpHatasi) as h:
            cdp.Oturum(s.boru, "H", "O").degerlendir("x")
        self.assertIn("ReferenceError", str(h.exception))

    def test_zaman_asimi_ve_gec_yanit_atilir(self):
        ilk = []

        def davranis(istek, s):
            if not ilk:  # ilk komut yanıtsız kalır; yanıtı ikinci komutla birlikte (geç) gelir
                ilk.append(istek["id"])
                return []
            return [{"id": ilk[0], "result": {"gec": True}}, {"id": istek["id"], "result": {"ikinci": True}}]
        s = self.kur(davranis)
        baslangic = time.monotonic()
        with self.assertRaises(cdp.CdpHatasi) as h:
            s.boru.komut("Page.enable", zaman=0.3)
        self.assertLess(time.monotonic() - baslangic, 2)
        self.assertIn("zaman aşımı", str(h.exception))
        self.assertEqual(s.boru.komut("Page.enable"), {"ikinci": True})
        self.assertTrue(s.boru.canli_mi())

    def test_eof_turkce_hata_ve_bekleyen_uyanir(self):
        s = self.kur(lambda i, s: [])  # hiç yanıt vermez
        hata = []

        def bekle():
            try:
                s.boru.komut("Browser.getVersion", zaman=10)
            except cdp.CdpHatasi as h:
                hata.append(str(h))
        t = threading.Thread(target=bekle)
        t.start()
        self.assertTrue(s.bekle(lambda g: g["method"] == "Browser.getVersion"))
        baslangic = time.monotonic()
        s.yazmayi_kapat()  # tarayıcı kapandı
        t.join(5)
        self.assertLess(time.monotonic() - baslangic, 2, "bekleyen komut EOF ile hemen uyanmalı")
        self.assertEqual(hata, ["Tarayıcı bağlantıyı kapattı."])
        self.assertTrue(s.boru.kapali)
        self.assertFalse(s.boru.canli_mi())
        with self.assertRaises(cdp.CdpHatasi) as h:  # kapandıktan sonra komut verilemez
            s.boru.komut("Browser.getVersion")
        self.assertIn("kapattı", str(h.exception))

    def test_kapat_karsi_uca_eof_gonderir(self):
        s = self.kur(sonuc_ver(1))
        s.boru.kapat()
        self.assertTrue(s.eof_goruldu.wait(2), "sahte tarayıcı EOF görmeli (gerçek Edge bu durumda kapanır)")
        self.assertTrue(s.boru.kapali)
        with self.assertRaises(cdp.CdpHatasi):
            s.boru.komut("X.y")

    def test_kapat_tarayiciyi_kapat_browser_close_gonderir(self):
        s = self.kur(lambda i, s: [{"id": i["id"], "result": {}}])
        s.boru.kapat(tarayiciyi_kapat=True)
        self.assertEqual([g["method"] for g in s.gelenler], ["Browser.close"])

    def test_olay_siniri(self):
        def davranis(istek, s):
            return [{"method": "Olay.n", "params": {"n": n}} for n in range(250)] + [{"id": istek["id"], "result": {}}]
        s = self.kur(davranis)
        s.boru.komut("X.y")
        self.assertEqual(len(s.boru.olaylar), cdp.OLAY_SINIRI)
        self.assertEqual(s.boru.olaylar[-1]["params"]["n"], 249)
        self.assertEqual(s.boru.olaylar[0]["params"]["n"], 250 - cdp.OLAY_SINIRI)

    def test_buyuk_istek_tek_mesaj(self):
        s = self.kur(sonuc_ver(1))
        cdp.Oturum(s.boru, "H", "O").yazi_ekle("b" * 70000)
        self.assertEqual(s.gelenler[0]["method"], "Input.insertText")
        self.assertEqual(len(s.gelenler[0]["params"]["text"]), 70000)

    def test_metindeki_nul_ayraci_bozmaz(self):
        s = self.kur(sonuc_ver(1))
        cdp.Oturum(s.boru, "H", "O").yazi_ekle("a\0b")
        self.assertEqual(s.gelenler[0]["params"]["text"], "a\0b")


class OturumTesti(BoruTabani):
    @staticmethod
    def tarayici_davranisi(istek, s):
        """attachToTarget'e olay + oturum kimliği, detachFromTarget'e olay döner; diğerlerine değer 7."""
        yontem = istek["method"]
        if yontem == "Target.attachToTarget":
            return [{"method": "Target.attachedToTarget",
                     "params": {"sessionId": "OT1", "targetInfo": {"targetId": istek["params"]["targetId"]}}},
                    {"id": istek["id"], "result": {"sessionId": "OT1"}}]
        if yontem == "Target.detachFromTarget":
            return [{"method": "Target.detachedFromTarget", "params": {"sessionId": istek["params"]["sessionId"]}},
                    {"id": istek["id"], "result": {}}]
        return sonuc_ver(7)(istek, s)

    def test_sessionid_yonlendirme_ve_oturum_takibi(self):
        s = self.kur(self.tarayici_davranisi)
        o = cdp.sekmeye_baglan(s.boru, "HEDEF")
        self.assertEqual(s.gelenler[0], {"id": 1, "method": "Target.attachToTarget",
                                         "params": {"targetId": "HEDEF", "flatten": True}})
        self.assertEqual((o.hedef_id, o.oturum_id), ("HEDEF", "OT1"))
        self.assertEqual(s.boru.oturumlar, {"OT1": "HEDEF"})
        self.assertEqual(o.degerlendir("1+6"), 7)
        istek = s.gelenler[-1]
        self.assertEqual(istek["sessionId"], "OT1")  # sekme komutu oturuma gider
        self.assertEqual(istek["params"], {"expression": "1+6", "returnByValue": True, "awaitPromise": True})
        o.kapat()
        ayril = s.gelenler[-1]
        self.assertEqual(ayril["method"], "Target.detachFromTarget")
        self.assertEqual(ayril["params"], {"sessionId": "OT1"})  # parametre olarak, tarayıcı düzeyinde
        self.assertNotIn("sessionId", ayril)
        self.assertEqual(s.boru.oturumlar, {})
        with self.assertRaises(cdp.CdpHatasi):  # kapalı oturuma komut verilemez
            o.degerlendir("1")
        o.kapat()  # ikinci kapatma sessizdir
        self.assertEqual(sum(1 for g in s.gelenler if g["method"] == "Target.detachFromTarget"), 1)

    def test_git_tus_one_getir(self):
        s = self.kur(lambda i, s: [{"id": i["id"], "sessionId": i.get("sessionId"), "result": {"frameId": "F"}}])
        o = cdp.Oturum(s.boru, "H", "OT")
        with mock.patch.object(cdp.time, "sleep"):
            o.git("https://chatgpt.com/")
        o.tus("Enter", "Enter", 13, "\r")
        o.one_getir()
        yontemler = [(g["method"], g.get("sessionId")) for g in s.gelenler]
        self.assertEqual(yontemler, [("Page.navigate", "OT"), ("Input.dispatchKeyEvent", "OT"),
                                     ("Input.dispatchKeyEvent", "OT"), ("Page.bringToFront", "OT")])
        self.assertEqual([g["params"]["type"] for g in s.gelenler[1:3]], ["keyDown", "keyUp"])
        self.assertEqual(s.gelenler[1]["params"]["text"], "\r")
        self.assertNotIn("text", s.gelenler[2]["params"])

    def test_git_hata_metni(self):
        s = self.kur(lambda i, s: [{"id": i["id"], "result": {"errorText": "net::ERR_NAME_NOT_RESOLVED"}}])
        with self.assertRaises(cdp.CdpHatasi) as h:
            cdp.Oturum(s.boru, "H", "OT").git("https://yok.example/")
        self.assertIn("Sayfa açılamadı", str(h.exception))


class TarayiciDuzeyiTesti(BoruTabani):
    HEDEFLER = [
        {"targetId": "1", "type": "service_worker", "url": "https://chatgpt.com/sw.js", "title": ""},
        {"targetId": "2", "type": "page", "url": "https://chatgpt.com.kotu.net/c/1", "title": "Taklit"},
        {"targetId": "3", "type": "page", "url": "https://chatgpt.com/c/abc", "title": "Sohbet"},
        {"targetId": "4", "type": "page", "url": "https://claude.ai/new", "title": "Claude"},
    ]

    def davranis(self, istek, s):
        y = istek["method"]
        if y == "Target.getTargets":
            return [{"id": istek["id"], "result": {"targetInfos": self.HEDEFLER}}]
        if y == "Target.attachToTarget":
            return [{"id": istek["id"], "result": {"sessionId": "S-" + istek["params"]["targetId"]}}]
        if y == "Target.createTarget":
            return [{"id": istek["id"], "result": {"targetId": "YENI"}}]
        if y == "Browser.getWindowForTarget":
            return [{"id": istek["id"], "result": {"windowId": 5, "bounds": {"left": 1, "windowState": "minimized"}}}]
        return [{"id": istek["id"], "result": {}}]

    def test_pencere_bul_alan_adi_siniri(self):
        s = self.kur(self.davranis)
        self.assertEqual(cdp.pencere_bul(s.boru, "chatgpt.com")["id"], "3")  # service_worker ve taklit alan adı değil
        self.assertEqual(cdp.pencere_bul(s.boru, "claude.ai")["url"], "https://claude.ai/new")
        self.assertIsNone(cdp.pencere_bul(s.boru, "gemini.google.com"))

    def test_yeni_pencere_ve_pencere_sinirlari(self):
        s = self.kur(self.davranis)
        self.assertEqual(cdp.yeni_pencere(s.boru, "https://claude.ai/"), "YENI")
        self.assertEqual(s.gelenler[-1]["params"], {"url": "https://claude.ai/", "newWindow": True})
        cdp.pencere_sinirlari(s.boru, "3", 10.6, 20, 640, 480)
        sinirlar = [g["params"]["bounds"] for g in s.gelenler if g["method"] == "Browser.setWindowBounds"]
        self.assertEqual(sinirlar, [{"windowState": "normal"},  # simge durumundan önce normale
                                    {"left": 10, "top": 20, "width": 640, "height": 480, "windowState": "normal"}])

    def test_tarayici_modulu_boru_uzerinden(self):
        s = self.kur(self.davranis)
        with mock.patch.object(tarayici, "_boru", s.boru):
            self.assertTrue(tarayici.calisiyor_mu())
            self.assertEqual(tarayici.hedef("chatgpt.com")["id"], "3")
            o = tarayici.sayfa("chatgpt.com")
            self.assertIsInstance(o, cdp.Oturum)
            self.assertEqual((o.hedef_id, o.oturum_id), ("3", "S-3"))
            self.assertIsNone(tarayici.sayfa("gemini.google.com"))
            self.assertIsNone(tarayici.pencere_ac("https://gemini.google.com/app"))
            self.assertEqual(s.gelenler[-1]["method"], "Target.createTarget")
            tarayici.pencere_sinirlari("3", 0, 0, 100, 100)
        self.assertFalse(tarayici.calisiyor_mu())  # yama bitti: bu süreçte tarayıcı yok
        self.assertIsNone(tarayici.sayfa("chatgpt.com"))
        self.assertIsNone(tarayici.hedef("chatgpt.com"))
        with self.assertRaises(cdp.CdpHatasi):
            tarayici.pencere_sinirlari("3", 0, 0, 100, 100)

    def test_kapanmis_boru_calismiyor_sayilir(self):
        s = self.kur(self.davranis)
        s.yazmayi_kapat()
        with mock.patch.object(tarayici, "_boru", s.boru):
            self.assertTrue(self._bekle(lambda: not tarayici.calisiyor_mu()))
            self.assertIsNone(tarayici.sayfa("chatgpt.com"))

    def _bekle(self, kosul, sure=2):
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            if kosul():
                return True
            time.sleep(0.02)
        return False


class TarayiciBaslatmaTesti(unittest.TestCase):
    """tarayici.baslat: Edge'in kendisi yerine sahte boru kullanılır."""

    def setUp(self):
        yama = mock.patch.object(tarayici, "_boru", None)
        yama.start()
        self.addCleanup(yama.stop)

    def test_edge_yoksa_varsayilan_tarayici_ve_uyari(self):
        with mock.patch.object(tarayici, "EDGE_YOLLARI", [r"C:\yok\msedge.exe"]), \
                mock.patch.object(tarayici.webbrowser, "open") as ac:
            uyari = tarayici.baslat("http://127.0.0.1:1/")
        ac.assert_called_once_with("http://127.0.0.1:1/")
        self.assertIn("Edge bulunamadı", uyari)

    def baslatici(self, davranis, komutlar):
        def boruyla_baslat(komut):
            komutlar.append(komut)
            s = SahteTarayici(davranis)
            self.addCleanup(s.boru.kapat)
            self.addCleanup(s.yazmayi_kapat)
            self.sahte = s
            return s.boru
        return boruyla_baslat

    def test_boruyla_baslar_port_acmaz(self):
        komutlar = []
        with mock.patch.object(tarayici, "_edge_yolu", return_value=r"C:\edge\msedge.exe"), \
                mock.patch.object(tarayici.cdp, "boruyla_baslat",
                                  self.baslatici(lambda i, s: [{"id": i["id"], "result": {"product": "Edg"}}], komutlar)):
            self.assertIsNone(tarayici.baslat("http://127.0.0.1:8766/ac/AcilisKodu_0123456789abcdef"))
            self.assertTrue(tarayici.calisiyor_mu())
        komut = komutlar[0]
        self.assertEqual(komut[0], r"C:\edge\msedge.exe")
        self.assertIn(f"--user-data-dir={tarayici.PROFIL}", komut)
        self.assertEqual(komut[-1], "--app=http://127.0.0.1:8766/ac/AcilisKodu_0123456789abcdef")
        self.assertFalse(any(("remote-debugging-" + "port") in a or ("remote-allow-" + "origins") in a for a in komut))
        self.assertEqual(self.sahte.gelenler[0]["method"], "Browser.getVersion")

    def test_site_penceresi_uygulama_kipinde_degil(self):
        komutlar = []
        with mock.patch.object(tarayici, "_edge_yolu", return_value=r"C:\edge\msedge.exe"), \
                mock.patch.object(tarayici.cdp, "boruyla_baslat",
                                  self.baslatici(lambda i, s: [{"id": i["id"], "result": {}}], komutlar)):
            self.assertIsNone(tarayici.pencere_ac("https://chatgpt.com/"))
        self.assertEqual(komutlar[0][-1], "https://chatgpt.com/")

    def test_profil_baska_edge_tarafindan_kullaniliyorsa_turkce_hata(self):
        def davranis(istek, s):
            s.yazmayi_kapat()  # süreç açılışı eski Edge'e devredip çıktı: boru EOF
            return []
        with mock.patch.object(tarayici, "_edge_yolu", return_value=r"C:\edge\msedge.exe"), \
                mock.patch.object(tarayici.cdp, "boruyla_baslat", self.baslatici(davranis, [])):
            with self.assertRaises(tarayici.TarayiciHatasi) as h:
                tarayici.baslat("http://127.0.0.1:1/")
            self.assertEqual(str(h.exception), tarayici.PROFIL_ACIK_MESAJI)
            self.assertIn("açık bir Edge penceresi var", tarayici.pencere_ac("https://chatgpt.com/"))
            self.assertIn("açık bir Edge penceresi var", tarayici.uygulama_penceresi_ac("http://127.0.0.1:1/"))
        self.assertFalse(tarayici.calisiyor_mu())

    def test_calisirken_uygulama_penceresi_devredilir(self):
        s = SahteTarayici(lambda i, s: [{"id": i["id"], "result": {}}])
        self.addCleanup(s.boru.kapat)
        self.addCleanup(s.yazmayi_kapat)
        with mock.patch.object(tarayici, "_boru", s.boru), \
                mock.patch.object(tarayici, "_edge_yolu", return_value=r"C:\edge\msedge.exe"), \
                mock.patch.object(tarayici.subprocess, "Popen") as popen, \
                mock.patch.object(tarayici.cdp, "boruyla_baslat") as yeni_boru:
            self.assertIsNone(tarayici.uygulama_penceresi_ac("http://127.0.0.1:8766/ac/AcilisKodu_0123456789abcdef"))
        yeni_boru.assert_not_called()  # ikinci denetim bağlantısı açılmaz
        komut = popen.call_args.args[0]
        self.assertEqual(komut, [r"C:\edge\msedge.exe", "--app=http://127.0.0.1:8766/ac/AcilisKodu_0123456789abcdef",
                                 f"--user-data-dir={tarayici.PROFIL}"])

    def test_belirtecli_adres_uygulama_kipinde_reddedilir(self):
        # Komut satırı Win32_Process ile her yerel süreçten okunabilir: #t= / ?t= biçimli adres hiç başlatılmaz.
        with mock.patch.object(tarayici, "_edge_yolu", return_value=r"C:\edge\msedge.exe"), \
                mock.patch.object(tarayici.subprocess, "Popen") as popen, \
                mock.patch.object(tarayici.cdp, "boruyla_baslat") as boru:
            for adres in ("http://127.0.0.1:8766/#t=gizli", "http://127.0.0.1:8766/?t=gizli", "http://127.0.0.1:1/x#a&t=1"):
                with self.subTest(adres=adres):
                    with self.assertRaises(tarayici.TarayiciHatasi):
                        tarayici.baslat(adres)
                    self.assertIn("belirteci", tarayici.uygulama_penceresi_ac(adres))
        popen.assert_not_called()
        boru.assert_not_called()

    def test_komut_listesinde_belirtec_yok(self):
        import masaustu_sunucu as ms
        adres = ms.acilis_adresi(8766)
        for komut in (tarayici.edge_komutu(r"C:\edge\msedge.exe", adres), tarayici.devret_komutu(r"C:\edge\msedge.exe", adres)):
            birlesik = " ".join(komut)
            self.assertNotIn(ms.BELIRTEC, birlesik)
            self.assertNotIn("t=", birlesik)
            self.assertIn("/ac/", birlesik)

    def test_kapat_browser_close_gonderir(self):
        s = SahteTarayici(lambda i, s: [{"id": i["id"], "result": {}}])
        self.addCleanup(s.yazmayi_kapat)
        tarayici._boru = s.boru
        tarayici.kapat()
        self.assertIsNone(tarayici._boru)
        self.assertEqual([g["method"] for g in s.gelenler], ["Browser.close"])
        self.assertTrue(s.eof_goruldu.wait(2))
        tarayici.kapat()  # ikinci kez sessiz


# ---------------------------------------------------------------- gerçek Edge ile bütünleşme

def _edge_var_mi():
    return sys.platform == "win32" and any(Path(y).exists() for y in tarayici.EDGE_YOLLARI)


def _profil_sureclerini_kapat(profil):
    """Komut satırında geçici profil klasörünün adı geçen Edge süreçlerini durdurur (başka Edge'lere dokunmaz)."""
    ad = Path(profil).name
    komut = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains('%s') } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" % ad)
    subprocess.run(["powershell", "-NoProfile", "-Command", komut], capture_output=True, timeout=60)


def _profil_surec_kimlikleri(profil):
    """Komut satırında profil klasörünün adı geçen süreçlerin kimlikleri."""
    ad = Path(profil).name
    komut = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains('%s') } | "
             "ForEach-Object { $_.ProcessId }" % ad)
    cikti = subprocess.run(["powershell", "-NoProfile", "-Command", komut], capture_output=True, text=True, timeout=60)
    return {int(x) for x in cikti.stdout.split() if x.strip().isdigit()}


def _dinlenen_portlar(kimlikler):
    """Verilen süreçlerin TCP LISTENING portları (netstat -ano)."""
    cikti = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=60).stdout
    portlar = []
    for satir in cikti.splitlines():
        p = satir.split()
        if len(p) >= 5 and p[3].upper() == "LISTENING" and p[4].isdigit() and int(p[4]) in kimlikler:
            portlar.append(p[1])
    return portlar


@unittest.skipUnless(_edge_var_mi(), "Microsoft Edge bulunamadı, bütünleşme testi atlandı")
class EdgeButunlesmeTesti(unittest.TestCase):
    def test_boruyla_baslat_degerlendir_ve_port_yok(self):
        profil = tempfile.mkdtemp(prefix="yzcdp_")
        self.addCleanup(shutil.rmtree, profil, True)
        self.addCleanup(_profil_sureclerini_kapat, profil)
        self.addCleanup(tarayici.kapat)
        with mock.patch.object(tarayici, "PROFIL", Path(profil)), mock.patch.object(tarayici, "_boru", None):
            self.assertIsNone(tarayici.baslat("about:blank", uygulama=False))
            self.assertTrue(tarayici.calisiyor_mu())
            b = tarayici.baglanti()
            self.assertIn("Edg", b.komut("Browser.getVersion")["product"])
            # Yeni pencere boru üzerinden açılır; about:blank http(s) olmadığından adres eşleştirmesiyle bulunmaz,
            # hedef doğrudan Target.getTargets listesinden alınır.
            hedef_id = cdp.yeni_pencere(b, "about:blank")
            self.assertIsNone(tarayici.sayfa("about:blank"))
            with cdp.sekmeye_baglan(b, hedef_id) as sayfa:
                self.assertEqual(sayfa.degerlendir("1+41"), 42)
            self.assertNotIn(sayfa.oturum_id, b.oturumlar)  # kapatınca oturumdan ayrıldı
            sinir = tarayici.pencere_sinirlari(hedef_id, 50, 60, 700, 500)
            for gercek, beklenen in zip((sinir["left"], sinir["top"], sinir["width"], sinir["height"]), (50, 60, 700, 500)):
                self.assertAlmostEqual(gercek, beklenen, delta=2, msg=str(sinir))  # DPI ölçeğinde yuvarlama
            # Hiçbir Edge süreci TCP portu dinlemiyor (CDP yalnızca boruda).
            kimlikler = _profil_surec_kimlikleri(profil)
            self.assertIn(b.surec.pid, kimlikler)
            self.assertEqual(_dinlenen_portlar(kimlikler), [])
            # Aynı profille ikinci bir boru örneği açılışı eskisine devreder: Türkçe hata.
            ilk = tarayici._boru
            tarayici._boru = None
            try:
                with self.assertRaises(tarayici.TarayiciHatasi) as h:
                    tarayici.baslat("about:blank", uygulama=False)
                self.assertEqual(str(h.exception), tarayici.PROFIL_ACIK_MESAJI)
            finally:
                tarayici._boru = ilk
            self.assertTrue(tarayici.calisiyor_mu(), "ilk tarayıcının borusu etkilenmemeli")
            surec = b.surec
            tarayici.kapat()
            self.assertEqual(surec.wait(15), 0, "Browser.close ile Edge kapanmalı")


if __name__ == "__main__":
    unittest.main()
