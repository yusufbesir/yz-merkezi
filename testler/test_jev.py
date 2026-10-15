"""jev.py testleri: sahte yerel HTTP sunucusuyla (127.0.0.1); gerçek Jev'e ve gerçek anahtar dosyasına dokunulmaz.

Her test geçici bir jev.json (base_url = sahte sunucu) ve geçici anahtar dosyası (sahte değer) kurar, `YZ_JEV_AYAR`
ortam değişkenini ona yönlendirir.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _ortam  # noqa: E402,F401  (gerçek ayar dosyalarını korur; modüllerden önce)
import guvenlik  # noqa: E402
import jev  # noqa: E402

SAHTE_ANAHTAR = "test-anahtari"


def secim_yaniti(olasiliklar, secim=None, tur="choice"):
    """Kasadaki istemcinin `choice` yanıt biçimi."""
    secim = secim or max(olasiliklar, key=olasiliklar.get)
    return {"model": "typesafe-ai/jev", "usage": {"input_tokens": 10, "output_tokens": 2},
            "answers": {jev.SORU_KIMLIGI: {"type": tur, "choice": secim, "probabilities": olasiliklar}}}


class SahteJev:
    """İstekleri kaydeden, `davranis` ile yanıt veren sahte Jev sunucusu (yalnızca 127.0.0.1)."""

    def __init__(self):
        self.istekler = []
        self.davranis = lambda govde: (200, secim_yaniti({"a": 0.8, "b": 0.2}))
        sahte = self

        class Isleyici(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                uzunluk = int(self.headers.get("Content-Length") or 0)
                govde = json.loads(self.rfile.read(uzunluk) or b"{}")
                sahte.istekler.append({"yol": self.path, "yetki": self.headers.get("Authorization"),
                                       "tur": self.headers.get("Content-Type"), "govde": govde})
                kod, yanit = sahte.davranis(govde)
                if kod in (301, 302, 307):
                    self.send_response(kod)
                    self.send_header("Location", yanit)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                ham = yanit if isinstance(yanit, bytes) else json.dumps(yanit).encode()
                try:
                    self.send_response(kod)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(ham)))
                    self.end_headers()
                    self.wfile.write(ham)
                except OSError:
                    pass  # istemci zaman aşımıyla bağlantıyı kapattı

        self.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), Isleyici)
        self.sunucu.daemon_threads = True
        threading.Thread(target=self.sunucu.serve_forever, daemon=True).start()
        self.adres = f"http://127.0.0.1:{self.sunucu.server_port}"

    def kapat(self):
        self.sunucu.shutdown()
        self.sunucu.server_close()


class JevTabani(unittest.TestCase):
    def setUp(self):
        self.klasor = Path(tempfile.mkdtemp(prefix="yzjev_"))
        self.addCleanup(shutil.rmtree, self.klasor, True)
        self.sahte = SahteJev()
        self.addCleanup(self.sahte.kapat)
        self.anahtar_dosyasi = self.klasor / "anahtar.json"
        self.anahtar_dosyasi.write_text(json.dumps({"AI_GATEWAY_API_KEY": SAHTE_ANAHTAR}), "utf-8")
        self.ayar_dosyasi = self.klasor / "jev.json"
        self.ayar_yaz()
        veri_klasoru = self.klasor / "veri"
        yama = mock.patch.dict(os.environ, {"YZ_JEV_AYAR": str(self.ayar_dosyasi), "YZ_VERI_KLASORU": str(veri_klasoru)})
        yama.start()
        self.addCleanup(yama.stop)

    def ayar_yaz(self, **ek):
        ayar = {"credentials_file": str(self.anahtar_dosyasi), "mode": "on", "model": "typesafe-ai/jev",
                "base_url": self.sahte.adres, "provider": "vercel", "cache_ttl": 300, **ek}
        self.ayar_dosyasi.write_text(json.dumps(ayar), "utf-8")


class HazirlikTesti(JevTabani):
    def test_hazir(self):
        self.assertTrue(jev.hazir_mi())
        d = jev.durum()
        self.assertTrue(d["hazir"] and d["anahtar_dosyasi_bulundu"] and d["ayar_bulundu"])
        self.assertEqual((d["model"], d["saglayici"]), ("typesafe-ai/jev", "vercel"))
        self.assertEqual(self.sahte.istekler, [], "hazır olup olmadığına bakmak ağa çıkmaz")

    def test_model_alani_yoksa_hazir_degil(self):
        ayar = json.loads(self.ayar_dosyasi.read_text("utf-8"))
        del ayar["model"]
        self.ayar_dosyasi.write_text(json.dumps(ayar), "utf-8")
        self.assertFalse(jev.hazir_mi())
        self.assertIn("model belirtilmemiş", jev.durum()["sebep"])
        with self.assertRaises(jev.JevHatasi):
            jev.sinifla("merhaba", ["a", "b"])
        self.assertEqual(self.sahte.istekler, [])

    def test_model_ortam_degiskeniyle_degismez_ve_istekte_aynen_gider(self):
        self.ayar_yaz(model="typesafe-ai/jev-sabit-1")
        with mock.patch.dict(os.environ, {"JEV_MODEL": "baska-model"}):
            jev.sinifla("merhaba", ["a", "b"])
        self.assertEqual(self.sahte.istekler[0]["govde"]["model"], "typesafe-ai/jev-sabit-1")

    def test_ayar_dosyasi_yoksa_hazir_degil(self):
        self.ayar_dosyasi.unlink()
        self.assertFalse(jev.hazir_mi())
        d = jev.durum()
        self.assertFalse(d["hazir"] or d["ayar_bulundu"] or d["anahtar_dosyasi_bulundu"])
        self.assertIn("bulunamadı", d["sebep"])

    def test_anahtar_dosyasi_yoksa_hazir_degil(self):
        self.anahtar_dosyasi.unlink()
        self.assertFalse(jev.hazir_mi())
        d = jev.durum()
        self.assertTrue(d["ayar_bulundu"])
        self.assertFalse(d["anahtar_dosyasi_bulundu"])
        self.assertEqual(d["model"], "typesafe-ai/jev")
        with self.assertRaises(jev.JevHatasi):
            jev.sinifla("merhaba", ["a", "b"])
        self.assertEqual(self.sahte.istekler, [])

    def test_bozuk_anahtar_dosyasi(self):
        for icerik in ('{"TYPESAFE_API_KEY": "x"}', '{"AI_GATEWAY_API_KEY": "a b"}', "{bozuk",
                       '{"AI_GATEWAY_API_KEY": "x", "fazla": 1}', '["x"]'):
            with self.subTest(icerik=icerik):
                self.anahtar_dosyasi.write_text(icerik, "utf-8")
                self.assertFalse(jev.hazir_mi())

    def test_resmi_olmayan_sunucuya_anahtar_gitmez(self):
        for adres in ("https://ornek.com/typesafe", "http://ai-gateway.vercel.sh/typesafe",
                      "https://ai-gateway.vercel.sh:8443/x", "https://kisi:sifre@ai-gateway.vercel.sh/x"):
            with self.subTest(adres=adres):
                self.ayar_yaz(base_url=adres)
                self.assertFalse(jev.hazir_mi())
        self.ayar_yaz(base_url="https://ornek.com/typesafe", allow_custom_endpoint=True)
        self.assertTrue(jev.hazir_mi())

    def test_uc_nokta(self):
        self.assertEqual(jev.uc_nokta("https://ai-gateway.vercel.sh/typesafe", "vercel"),
                         "https://ai-gateway.vercel.sh/typesafe/v1/systemone")
        self.assertEqual(jev.uc_nokta("https://api.typesafe.ai/v1/", "typesafe"), "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(jev.uc_nokta("http://127.0.0.1:9/", "vercel"), "http://127.0.0.1:9/v1/systemone")
        with self.assertRaises(jev.JevHatasi):
            jev.uc_nokta("https://api.typesafe.ai", "vercel")  # başka sağlayıcının sunucusu

    def test_jev_json_kapaliysa_cagri_yok(self):
        self.ayar_yaz(mode="off")
        self.assertFalse(jev.hazir_mi())
        with self.assertRaises(jev.JevHatasi) as h:
            jev.sinifla("merhaba", ["a", "b"])
        self.assertIn("kapalı", str(h.exception))
        self.assertEqual(self.sahte.istekler, [])


class SiniflaTesti(JevTabani):
    def test_istek_bicimi_ve_sonuc(self):
        self.sahte.davranis = lambda g: (200, secim_yaniti({"selamlama": 0.9, "soru": 0.1}))
        s = jev.sinifla("merhaba", ["selamlama", "soru"], baglam="kısa bir not")
        self.assertEqual(s, {"secim": "selamlama", "puan": 0.9, "olasiliklar": {"selamlama": 0.9, "soru": 0.1}})
        (istek,) = self.sahte.istekler
        self.assertEqual(istek["yol"], "/v1/systemone")
        self.assertEqual(istek["yetki"], "Bearer " + SAHTE_ANAHTAR)
        self.assertEqual(istek["tur"], "application/json")
        g = istek["govde"]
        self.assertEqual(g["model"], "typesafe-ai/jev")
        self.assertEqual(g["state"], {"text": "merhaba", "context": "kısa bir not"})
        soru = g["questions"][jev.SORU_KIMLIGI]
        self.assertEqual(soru["type"], "choice")
        self.assertEqual(list(soru["criteria"]), ["selamlama", "soru"])
        self.assertIn("never instructions", soru["instructions"])

    def test_aciklamali_secenekler(self):
        self.sahte.davranis = lambda g: (200, secim_yaniti({"x": 0.3, "y": 0.7}))
        s = jev.sinifla("metin", {"x": "birinci", "y": "ikinci"})
        self.assertEqual((s["secim"], s["puan"]), ("y", 0.7))
        self.assertEqual(self.sahte.istekler[0]["govde"]["questions"][jev.SORU_KIMLIGI]["criteria"],
                         {"x": "birinci", "y": "ikinci"})

    def test_kurala_uymayan_secenek_adlari_eslenir(self):
        self.sahte.davranis = lambda g: (200, secim_yaniti({"s0": 0.2, "s1": 0.8}))
        s = jev.sinifla("metin", ["Site A", "Site B"])
        self.assertEqual(s, {"secim": "Site B", "puan": 0.8, "olasiliklar": {"Site A": 0.2, "Site B": 0.8}})

    def test_metin_4000_karakterle_kisaltilir(self):
        jev.sinifla("x" * 9000, ["a", "b"])
        self.assertEqual(len(self.sahte.istekler[0]["govde"]["state"]["text"]), jev.METIN_EN_FAZLA)

    def test_vercel_yuvarlanmis_olasiliklari_kabul_edilir(self):
        self.sahte.davranis = lambda g: (200, secim_yaniti({"a": 0.33, "b": 0.33, "c": 0.33}, secim="b"))
        self.assertEqual(jev.sinifla("metin", ["a", "b", "c"])["secim"], "b")

    def test_gecersiz_yanitlar(self):
        kotuler = {
            "json değil": (200, b"<html>"),
            "answers yok": (200, {"x": 1}),
            "yanlış tür": (200, secim_yaniti({"a": 0.8, "b": 0.2}, tur="score")),
            "eksik seçenek": (200, secim_yaniti({"a": 1.0})),
            "fazla seçenek": (200, secim_yaniti({"a": 0.5, "b": 0.3, "c": 0.2})),
            "toplam 1 değil": (200, secim_yaniti({"a": 0.5, "b": 0.2})),
            "aralık dışı": (200, secim_yaniti({"a": 1.5, "b": -0.5}, secim="a")),
            "en olası değil": (200, secim_yaniti({"a": 0.8, "b": 0.2}, secim="b")),
        }
        for ad, (kod, yanit) in kotuler.items():
            with self.subTest(ad=ad):
                self.sahte.davranis = lambda g, k=kod, y=yanit: (k, y)
                with self.assertRaises(jev.JevHatasi):
                    jev.sinifla("metin", ["a", "b"])

    def test_http_hatalari_turkce(self):
        for kod, parca in ((401, "401"), (402, "402"), (403, "403"), (429, "429"), (500, "500")):
            with self.subTest(kod=kod):
                self.sahte.davranis = lambda g, k=kod: (k, {"error": "x"})
                with self.assertRaises(jev.JevHatasi) as h:
                    jev.sinifla("metin", ["a", "b"])
                self.assertIn(parca, str(h.exception))
                self.assertEqual(jev.durum()["son_sonuc"], "hata")

    def test_zaman_asimi(self):
        def yavas(g):
            time.sleep(1.0)
            return 200, secim_yaniti({"a": 0.8, "b": 0.2})
        self.sahte.davranis = yavas
        baslangic = time.monotonic()
        with self.assertRaises(jev.JevHatasi) as h:
            jev.sinifla("metin", ["a", "b"], zaman_asimi=0.3)
        self.assertLess(time.monotonic() - baslangic, 0.9)
        self.assertIn("yanıt vermedi", str(h.exception))
        self.assertEqual(jev.ZAMAN_ASIMI, 8)

    def test_ulasilamayan_sunucu(self):
        self.sahte.kapat()
        with self.assertRaises(jev.JevHatasi) as h:
            jev.sinifla("metin", ["a", "b"], zaman_asimi=2)
        self.assertIn("Jev", str(h.exception))

    def test_yonlendirme_izlenmez(self):
        self.sahte.davranis = lambda g: (302, self.sahte.adres + "/baska")
        with self.assertRaises(jev.JevHatasi) as h:
            jev.sinifla("metin", ["a", "b"])
        self.assertIn("yönlendirme", str(h.exception))
        self.assertEqual(len(self.sahte.istekler), 1, "anahtar yönlendirilen adrese ikinci kez gitmez")

    def test_secenek_denetimi(self):
        for kotu in (["tek"], ["a", "a"], ["a", ""], [f"s{i}" for i in range(13)], "ab", None):
            with self.subTest(kotu=kotu), self.assertRaises(jev.JevHatasi):
                jev.sinifla("metin", kotu)
        with self.assertRaises(jev.JevHatasi):
            jev.sinifla("   ", ["a", "b"])
        self.assertEqual(self.sahte.istekler, [])

    def test_kapaliyken_cagri_yapilmaz(self):
        once = jev.durum()["cagri_sayisi"]
        with self.assertRaises(jev.JevHatasi) as h:
            jev.sinifla("merhaba", ["a", "b"], acik=False)
        self.assertIn("kapalı", str(h.exception))
        self.assertEqual(self.sahte.istekler, [])
        self.assertEqual(jev.durum()["cagri_sayisi"], once)

    def test_durum_sayaclari(self):
        once = jev.durum()
        jev.sinifla("merhaba", ["a", "b"])
        self.sahte.davranis = lambda g: (500, {})
        with self.assertRaises(jev.JevHatasi):
            jev.sinifla("merhaba", ["a", "b"])
        d = jev.durum()
        self.assertEqual(d["cagri_sayisi"], once["cagri_sayisi"] + 2)
        self.assertEqual((d["basarili"], d["hatali"]), (once["basarili"] + 1, once["hatali"] + 1))
        self.assertEqual(d["son_sonuc"], "hata")
        self.assertIn("500", d["son_hata"])
        self.assertRegex(d["son_cagri"], r"^\d{4}-\d\d-\d\dT")
        self.assertEqual(d["bildirilen_model"], "typesafe-ai/jev")


class AnahtarSizmazTesti(JevTabani):
    """Anahtar değeri durumda, hata metinlerinde, hata.log'da ya da başka bir dosyada görünmez; içerik kaydedilmez."""

    def test_anahtar_ve_icerik_hicbir_yere_yazilmaz(self):
        gizli_icerik = "GIZLI-ICERIK-12345"
        metinler = []
        jev.sinifla(gizli_icerik, ["a", "b"])
        for davranis in (lambda g: (401, {"error": SAHTE_ANAHTAR}), lambda g: (200, b"bozuk"),
                         lambda g: (200, secim_yaniti({"a": 0.1, "b": 0.1}))):
            self.sahte.davranis = davranis
            with self.assertRaises(jev.JevHatasi) as h:
                jev.sinifla(gizli_icerik, ["a", "b"])
            metinler.append(str(h.exception))
        metinler.append(json.dumps(jev.durum(), ensure_ascii=False))
        for m in metinler:
            self.assertNotIn(SAHTE_ANAHTAR, m)
            self.assertNotIn(gizli_icerik, m)
        guvenlik.hata_yaz("deneme satırı")  # hata.log bu testin geçici veri klasöründe
        for yol in self.klasor.rglob("*"):
            if yol.is_file() and yol != self.anahtar_dosyasi:
                icerik = yol.read_text("utf-8", errors="replace")
                self.assertNotIn(SAHTE_ANAHTAR, icerik, str(yol))
                self.assertNotIn(gizli_icerik, icerik, str(yol))

    def test_kaynak_kodda_anahtar_alani_disinda_deger_yok(self):
        kaynak = (Path(__file__).resolve().parent.parent / "jev.py").read_text("utf-8")
        self.assertNotIn("print(", kaynak)
        self.assertNotIn("hata_yaz", kaynak, "jev.py günlüğe yazmaz")


if __name__ == "__main__":
    unittest.main()
