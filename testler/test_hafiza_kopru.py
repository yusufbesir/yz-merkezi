"""hafiza_kopru.py testleri: geçici kasa (YZ_KASA) ve sahte `araclar/hafiza.py` ile; gerçek kasaya dokunmaz."""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _ortam  # noqa: E402,F401  (gerçek ayar dosyalarını ve gerçek kasayı korur; sunucu modülünden önce)
import hafiza_kopru as hk  # noqa: E402
import masaustu_sunucu as ms  # noqa: E402
import siteler  # noqa: E402

# Sahte hafiza.py: argv'yi ve çalışma klasörünü argv.json'a yazar, sorgudaki anahtar sözcüğe göre davranır.
SAHTE_ARAC = r'''
import json, os, sys, time
a = sys.argv[1:]
with open("argv.json", "w", encoding="utf-8") as f:
    json.dump({"argv": a, "cwd": os.getcwd()}, f)
q = a[-1]
def yaz(veri):
    sys.stdout.buffer.write(json.dumps(veri, ensure_ascii=False).encode("utf-8"))
if "UZUN-BEKLE" in q:
    time.sleep(30)
if "HATA-KODU" in q:
    yaz({"error": "kasa bozuk"}); sys.exit(1)
if "BOZUK-CIKTI" in q:
    sys.stdout.write("bu json degil"); sys.exit(0)
if "BOS-BAGLAM" in q:
    yaz({"memory_ids": [], "text": "", "mode": "local", "fallback_reason": None}); sys.exit(0)
yaz({"memory_ids": ["m1", "m2"], "mode": "local", "fallback_reason": None,
     "text": "- Yusuf Türkçe yanıt ister.\n- sk-ABCDEF1234567890 anahtarı\n- Parola: 12345\n- ŞİFRE bilgisi\n"
             "- AIzaSyEXAMPLE\n- ghp_abcdef\n-----BEGIN PRIVATE KEY-----\n- Kısa ve net cevap sever."})
'''

BEKLENEN_BAGLAM = "- Yusuf Türkçe yanıt ister.\n- Kısa ve net cevap sever."


def gecici_kasa(arac=SAHTE_ARAC, hafiza_py=True):
    """Geçici bir kasa kurar; (kasa yolu, temizlik) döner."""
    kasa = Path(tempfile.mkdtemp(prefix="yzkasa_"))
    if hafiza_py:
        (kasa / "araclar").mkdir()
        (kasa / "araclar" / "hafiza.py").write_text(arac, encoding="utf-8")
    return kasa


class KasaTestiTaban(unittest.TestCase):
    def kasa_kur(self, **kw):
        kasa = gecici_kasa(**kw)
        self.addCleanup(shutil.rmtree, kasa, True)
        ozet_klasoru = Path(tempfile.mkdtemp(prefix="yzozet_"))   # hafiza.py güven özeti: her test kendi dosyası
        self.addCleanup(shutil.rmtree, ozet_klasoru, True)
        self.ozet_dosyasi = ozet_klasoru / "hafiza-py.sha256"
        yama = mock.patch.dict(os.environ, {"YZ_KASA": str(kasa), "YZ_HAFIZA_HASH": str(self.ozet_dosyasi)})
        yama.start()
        self.addCleanup(yama.stop)
        hk._durumu_yaz(None, None)
        return kasa


class BaglamGetirTesti(KasaTestiTaban):
    def test_komut_satiri_ve_calisma_klasoru(self):
        kasa = self.kasa_kur()
        sonuc = hk.baglam_getir("Hangi dili tercih ederim?")
        kayit = json.loads((kasa / "argv.json").read_text("utf-8"))
        arg = kayit["argv"]
        self.assertEqual(arg, ["--vault", ".", "context", "--limit", "5", "--char-budget", "1200", "--local", "--",
                               "Hangi dili tercih ederim?"])
        self.assertEqual(Path(kayit["cwd"]).resolve(), kasa.resolve())
        self.assertEqual((sonuc["mod"], sonuc["sebep"], sonuc["kimlikler"]), ("local", None, ["m1", "m2"]))

    def test_sir_satirlari_atilir(self):
        self.kasa_kur()
        sonuc = hk.baglam_getir("kişisel tercihlerim")
        self.assertEqual(sonuc["metin"], BEKLENEN_BAGLAM)
        self.assertEqual(sonuc["atilan"], 6)
        for yasak in ("sk-", "AIza", "ghp_", "BEGIN", "arola", "İFRE"):
            self.assertNotIn(yasak, sonuc["metin"])

    def test_sirli_satir_suzgeci(self):
        temiz, atilan = hk.sirli_satirlari_at("normal\nmy password is x\nŞifre: 1\nşifre 2\nSIFRE 3\nbask-et\nson")
        self.assertEqual(temiz, "normal\nbask-et\nson")  # "bask-et" içindeki "sk-" bir anahtar öneki değildir
        self.assertEqual(atilan, 4)

    def test_baglam_ekle_bicimi(self):
        self.kasa_kur()
        gonderilecek, baglam = hk.baglam_ekle("Merhaba\nikinci satır")
        self.assertEqual(gonderilecek, "Bağlam (kişisel notlarımdan, yalnızca gerekiyorsa kullan):\n"
                                       + BEKLENEN_BAGLAM + "\n\n---\nMerhaba\nikinci satır")
        self.assertEqual(baglam, {"metin": BEKLENEN_BAGLAM, "mod": "local", "karakter": len(BEKLENEN_BAGLAM),
                                  "kimlikler": ["m1", "m2"]})

    def test_bos_baglamda_hicbir_sey_eklenmez(self):
        self.kasa_kur()
        self.assertEqual(hk.baglam_ekle("BOS-BAGLAM sorusu"), ("BOS-BAGLAM sorusu", None))
        self.assertEqual(hk.durum()["son_mod"], "local")

    def test_zaman_asimi(self):
        self.kasa_kur()
        sonuc = hk.baglam_getir("UZUN-BEKLE", zaman_asimi=1)
        self.assertEqual(sonuc["metin"], "")
        self.assertIn("1 saniyede yanıt vermedi", sonuc["sebep"])
        self.assertIn("saniyede", hk.durum()["son_hata"])

    def test_arac_hatasi_ve_bozuk_cikti_bos_doner(self):
        self.kasa_kur()
        hata = hk.baglam_getir("HATA-KODU")
        self.assertEqual(hata["metin"], "")
        self.assertIn("hata bildirdi", hata["sebep"])
        bozuk = hk.baglam_getir("BOZUK-CIKTI")
        self.assertEqual(bozuk["metin"], "")
        self.assertIn("okunamadı", bozuk["sebep"])
        self.assertEqual(hk.baglam_ekle("HATA-KODU"), ("HATA-KODU", None))

    def test_kasa_ya_da_arac_yoksa(self):
        yok = Path(tempfile.gettempdir()) / "yzkasa_olmayan_klasor"
        with mock.patch.dict(os.environ, {"YZ_KASA": str(yok)}):
            sonuc = hk.baglam_getir("soru")
            self.assertEqual(sonuc["metin"], "")
            self.assertIn("kasası bulunamadı", sonuc["sebep"])
            self.assertEqual(hk.durum()["kasa_var"], False)
        self.kasa_kur(hafiza_py=False)
        sonuc = hk.baglam_getir("soru")
        self.assertIn("aracı bulunamadı", sonuc["sebep"])
        d = hk.durum()
        self.assertEqual((d["kasa_var"], d["hafiza_py_var"]), (True, False))

    def test_bos_soru_calistirmaz(self):
        kasa = self.kasa_kur()
        self.assertEqual(hk.baglam_ekle("   \n "), ("   \n ", None))
        self.assertFalse((kasa / "argv.json").exists())

    def test_uzun_soru_kisaltilir_ve_tireyle_baslayan_soru_secenek_sayilmaz(self):
        kasa = self.kasa_kur()
        hk.baglam_getir("--help " + "x" * 5000)
        arg = json.loads((kasa / "argv.json").read_text("utf-8"))["argv"]
        self.assertLessEqual(len(arg[-1]), hk.SORGU_EN_FAZLA)
        self.assertEqual(arg[-2], "--")
        self.assertTrue(arg[-1].startswith("--help"))

    def test_baslatilamayan_yorumlayici_atlanir_siradaki_denenir(self):
        self.kasa_kur()
        with mock.patch.object(hk, "_python_komutlari", return_value=[["yok-python-xyz"], [sys.executable]]):
            sonuc = hk.baglam_getir("soru")
        self.assertEqual(sonuc["metin"], BEKLENEN_BAGLAM)
        with mock.patch.object(hk, "_python_komutlari", return_value=[["yok-python-xyz"]]):
            sonuc = hk.baglam_getir("soru")
        self.assertEqual(sonuc["metin"], "")
        self.assertIn("başlatılamadı", sonuc["sebep"])


class AdayYazTesti(KasaTestiTaban):
    AN = datetime(2026, 10, 11, 14, 5, 9)

    def yol(self, kasa):
        return kasa / "gelen-kutusu" / "yz-merkezi" / "2026-10-11.md"

    def test_dosya_bicimi(self):
        kasa = self.kasa_kur()
        soru, yanit = "s" * 300, "y" * 900
        sonuc = hk.aday_yaz("ChatGPT", soru, yanit, zaman=self.AN)
        self.assertEqual((sonuc["yazildi"], sonuc["sebep"]), (True, None))
        metin = self.yol(kasa).read_text("utf-8")
        self.assertEqual(Path(sonuc["yol"]), self.yol(kasa))
        self.assertTrue(metin.startswith("---\nkaynak: yz-merkezi\n"))
        self.assertIn("\n---\n", metin[3:])
        satirlar = {s.split(": ", 1)[0]: s.split(": ", 1)[1] for s in metin.splitlines() if s.startswith("- ")}
        self.assertEqual(satirlar["- zaman"], "2026-10-11T14:05:09")
        self.assertEqual(satirlar["- site"], "ChatGPT")
        self.assertEqual(len(satirlar["- soru"]), 200)
        self.assertTrue(satirlar["- soru"].endswith("…"))
        self.assertEqual(len(satirlar["- yanıt"]), 600)
        self.assertTrue(satirlar["- yanıt"].endswith("…"))
        self.assertRegex(satirlar["- kimlik"], r"^[0-9a-f]{12}$")
        self.assertIn("## 14:05 · ChatGPT", metin)

    def test_kisa_metin_kesilmez_ve_tek_satir_olur(self):
        kasa = self.kasa_kur()
        hk.aday_yaz("Claude", "Merhaba\n\n  dünya", "Satır bir\nsatır   iki", zaman=self.AN)
        metin = self.yol(kasa).read_text("utf-8")
        self.assertIn("- soru: Merhaba dünya\n", metin)
        self.assertIn("- yanıt: Satır bir satır iki\n", metin)

    def test_ekleme_oncekini_degistirmez_ve_tekrar_yazilmaz(self):
        kasa = self.kasa_kur()
        hk.aday_yaz("ChatGPT", "bir", "yanıt bir", zaman=self.AN)
        ilk = self.yol(kasa).read_bytes()
        tekrar = hk.aday_yaz("ChatGPT", "bir", "yanıt bir", zaman=self.AN)
        self.assertEqual((tekrar["yazildi"], tekrar["sebep"]), (False, "Bu kayıt zaten yazılmış."))
        self.assertEqual(self.yol(kasa).read_bytes(), ilk)
        hk.aday_yaz("Gemini", "bir", "yanıt iki", zaman=self.AN.replace(minute=6))
        yeni = self.yol(kasa).read_bytes()
        self.assertTrue(yeni.startswith(ilk), "var olan içerik değişmemeli, yalnız sona eklenmeli")
        self.assertEqual(yeni.decode("utf-8").count("kaynak: yz-merkezi"), 1)
        self.assertEqual(yeni.decode("utf-8").count("## "), 2)

    def test_var_olan_dosyanin_uzerine_yazilmaz(self):
        kasa = self.kasa_kur()
        self.yol(kasa).parent.mkdir(parents=True)
        self.yol(kasa).write_text("Benim notum\n", encoding="utf-8")
        hk.aday_yaz("ChatGPT", "soru", "yanıt", zaman=self.AN)
        metin = self.yol(kasa).read_text("utf-8")
        self.assertTrue(metin.startswith("Benim notum\n## 14:05"))

    def test_sir_iceren_kayit_yazilmaz(self):
        kasa = self.kasa_kur()
        for soru, yanit in [("parolam 1234", "tamam"), ("normal", "anahtar: sk-ABCDEF123"), ("normal", "Şifre: 9")]:
            sonuc = hk.aday_yaz("ChatGPT", soru, yanit, zaman=self.AN)
            self.assertFalse(sonuc["yazildi"])
            self.assertIn("Sır benzeri", sonuc["sebep"])
        self.assertFalse((kasa / "gelen-kutusu").exists())

    def test_bos_ya_da_kasasiz_yazilmaz(self):
        kasa = self.kasa_kur()
        self.assertFalse(hk.aday_yaz("ChatGPT", "", "yanıt")["yazildi"])
        self.assertFalse(hk.aday_yaz("ChatGPT", "soru", "  ")["yazildi"])
        self.assertFalse((kasa / "gelen-kutusu").exists())
        with mock.patch.dict(os.environ, {"YZ_KASA": str(kasa / "yok")}):
            sonuc = hk.aday_yaz("ChatGPT", "soru", "yanıt")
            self.assertFalse(sonuc["yazildi"])
            self.assertFalse((kasa / "yok").exists(), "olmayan kasa oluşturulmamalı")

    def test_obsidian_baglanti_ve_etiket_etkisizlestirilir(self):
        kasa = self.kasa_kur()
        hk.aday_yaz("ChatGPT", "bak [[Ana Sayfa]] #etiket", "şu [[not]] ve #baska", zaman=self.AN)
        metin = self.yol(kasa).read_text("utf-8")
        self.assertNotIn("[[", metin)
        self.assertNotIn("]]", metin)
        self.assertNotIn(" #etiket", metin)
        self.assertIn("\\#etiket", metin)

    def test_kasada_baska_hicbir_dosya_degismez(self):
        kasa = self.kasa_kur()
        (kasa / "notlar").mkdir()
        (kasa / "notlar" / "a.md").write_text("not", encoding="utf-8")
        once = {p: p.read_bytes() for p in kasa.rglob("*") if p.is_file()}
        hk.aday_yaz("ChatGPT", "soru", "yanıt", zaman=self.AN)
        hk.baglam_getir("kişisel tercihlerim")
        sonra = {p: p.read_bytes() for p in kasa.rglob("*") if p.is_file()}
        yeni = set(sonra) - set(once)
        self.assertEqual({p.relative_to(kasa).as_posix() for p in yeni}, {"gelen-kutusu/yz-merkezi/"
                                                                         + self.AN.strftime("%Y-%m-%d") + ".md"}
                         | ({"argv.json"} if "argv.json" not in {p.name for p in once} else set()))
        for p, icerik in once.items():
            if p.name != "argv.json":
                self.assertEqual(sonra[p], icerik, p)

    def test_istisna_firlatmaz(self):
        self.kasa_kur()
        with mock.patch.object(hk, "_aday_yaz", side_effect=PermissionError("x")):
            sonuc = hk.aday_yaz("ChatGPT", "soru", "yanıt")
        self.assertFalse(sonuc["yazildi"])
        self.assertIn("PermissionError", hk.durum()["son_hata"])


class DurumTesti(KasaTestiTaban):
    def test_anahtarlar_ve_degerler(self):
        kasa = self.kasa_kur()
        d = hk.durum()
        self.assertEqual(set(d), {"kasa_var", "hafiza_py_var", "son_mod", "son_hata", "kasa", "hash_degisti",
                                  "hash_uyarisi"})
        self.assertEqual((d["hash_degisti"], d["hash_uyarisi"]), (False, None))
        self.assertEqual((d["kasa_var"], d["hafiza_py_var"], d["kasa"]), (True, True, str(kasa)))

    def test_varsayilan_kasa_ortam_degiskeni_yoksa(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("YZ_KASA", None)
            self.assertEqual(str(hk.kasa_yolu()), r"D:\YusufII\HAFIZAM1\kasa")


class HafizaSunucuTabani(KasaTestiTaban):
    """/api/gonder ve /api/yanit-kaydet: gönderilen metnin başına bağlam eklenir; geçmiş ve aday kaydı doğru tutulur."""

    def setUp(self):
        klasor = Path(tempfile.mkdtemp(prefix="yzhafiza_"))
        self.addCleanup(shutil.rmtree, klasor, True)
        yama = mock.patch.object(ms, "AYAR_DOSYASI", klasor / "ayar.json")
        yama.start()
        self.addCleanup(yama.stop)
        ms.is_kilidi = threading.Lock()
        self.kasa = self.kasa_kur()
        self.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), ms.Isleyici)
        threading.Thread(target=self.sunucu.serve_forever, daemon=True).start()
        self.addCleanup(self.sunucu.server_close)
        self.addCleanup(self.sunucu.shutdown)
        # Bu sınıfın eski testleri otomatik bağlam yolunu sınar; onaylı yol BaglamOnayiGonderTesti'nde.
        ms.ayarlari_yaz({"secili": {"site:gemini": False, "site:claude": False}, "ayarlar": {"hafiza_onay": False}})

    def istek(self, yol, veri=None):
        govde = None if veri is None else json.dumps(veri).encode()
        basliklar = {"X-YZ-Token": ms.BELIRTEC}
        if govde is not None:
            basliklar["Content-Type"] = "application/json"
        talep = urllib.request.Request(f"http://127.0.0.1:{self.sunucu.server_port}{yol}", govde, basliklar)
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(talep, timeout=30) as y:
            return json.load(y)

    @staticmethod
    def sahte_sekme():
        """ChatGPT sekmesi taklidi: yazı kutusu, yazi_ekle ile eklenenleri aynen gösterir."""
        b = mock.MagicMock()
        konum = {"href": siteler.SITELER["chatgpt"]["yeni_sohbet_adresi"]}
        b.git.side_effect = lambda url: konum.update(href=url)
        sjs = siteler.SITELER["chatgpt"]["js"]

        def degerlendir(js, zaman=30):
            if js == sjs["kutu_metni"]:
                return "".join(c.args[0] for c in b.yazi_ekle.call_args_list)
            if js == "location.href":
                return konum["href"]
            return {
                sjs["giris_var_mi"]: {"giris": True, "sebep": "x"},
                sjs["yazi_kutusunu_bul"]: {"tamam": True, "tur": "contenteditable", "sebep": ""},
                sjs["kutu_hazir_mi"]: {"hazir": True},
                sjs["mesajlar"]: {"baslik": "", "mesajlar": []},
                sjs["gonder"]: {"tamam": True, "yontem": "dugme", "sebep": ""},
            }[js]
        b.degerlendir.side_effect = degerlendir
        return b

    def gonder(self, metin, **ek):
        """Gerçek gonder() yoluyla gönderir; sitenin kutusuna yazılan metni de döndürür."""
        b = self.sahte_sekme()
        with mock.patch.object(ms, "site_sayfasi", return_value=b), mock.patch.object(ms.time, "sleep"), \
                mock.patch.object(ms, "kendi_pencere", return_value=None):
            v = self.istek("/api/gonder", dict(metin=metin, **ek))
        return v, "".join(c.args[0] for c in b.yazi_ekle.call_args_list)


class SunucuEntegrasyonTesti(HafizaSunucuTabani):
    """Otomatik bağlam yolu (hafiza_onay kapalı)."""

    def test_gonderilen_metnin_basina_baglam_eklenir(self):
        v, yazilan = self.gonder("Hangi dili severim?")
        self.assertEqual(yazilan, "Bağlam (kişisel notlarımdan, yalnızca gerekiyorsa kullan):\n"
                                  + "\n".join(BEKLENEN_BAGLAM.split("\n")) + "\n\n---\nHangi dili severim?")
        self.assertTrue(yazilan.startswith("Bağlam (kişisel notlarımdan"))
        self.assertEqual(v["gonderilen"], ["ChatGPT"])
        # Geçmişte ham mesaj ve bağlam ayrı alanlarda
        mesaj = v["sohbetler"][0]["mesajlar"][0]
        self.assertEqual(mesaj["metin"], "Hangi dili severim?")
        self.assertEqual(mesaj["baglam"]["metin"], BEKLENEN_BAGLAM)
        self.assertEqual(mesaj["baglam"]["karakter"], len(BEKLENEN_BAGLAM))
        self.assertEqual(v["baglam"], mesaj["baglam"])
        self.assertEqual(v["sohbetler"][0]["baslik"], "Hangi dili severim?")

    def test_baglam_bossa_ya_da_arac_hataliysa_mesaj_aynen_gider(self):
        for soru in ("BOS-BAGLAM mesajı", "HATA-KODU mesajı"):
            v, yazilan = self.gonder(soru)
            self.assertEqual(yazilan, soru)
            self.assertEqual(v["gonderilen"], ["ChatGPT"])
            self.assertIsNone(v["baglam"])
            self.assertNotIn("baglam", v["sohbetler"][0]["mesajlar"][-1])
            ms.is_kilidi = threading.Lock()

    def test_ayar_kapaliyken_baglam_eklenmez_ve_arac_calismaz(self):
        self.istek("/api/ayar", {"hafiza_ekle": False})
        v, yazilan = self.gonder("Merhaba")
        self.assertEqual(yazilan, "Merhaba")
        self.assertIsNone(v["baglam"])
        self.assertFalse((self.kasa / "argv.json").exists())

    def test_ayar_dogrulanir(self):
        with self.assertRaises(urllib.error.HTTPError) as h:
            self.istek("/api/ayar", {"hafiza_ekle": "evet"})
        self.assertEqual(h.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError):
            self.istek("/api/ayar", {"hafiza_aday": 1})
        self.istek("/api/ayar", {"hafiza_ekle": False, "hafiza_aday": False})
        a = ms.ayarlari_oku()["ayarlar"]
        self.assertEqual((a["hafiza_ekle"], a["hafiza_aday"]), (False, False))

    def test_varsayilan_ayarlar_acik(self):
        a = ms.ayarlari_oku()["ayarlar"]
        self.assertEqual((a["hafiza_ekle"], a["hafiza_aday"]), (True, True))
        self.assertIs(ms.VARSAYILAN_AYARLAR["hafiza_onay"], True)

    def test_yanit_kaydedilince_aday_yazilir_ham_soruyla(self):
        v, _ = self.gonder("Hangi dili severim?")
        with mock.patch.object(ms, "site_konumu", return_value=None):
            self.istek("/api/yanit-kaydet", {"sohbet": v["sohbet"], "mesaj_sira": 0, "site": "chatgpt",
                                             "metin": "Türkçe seversin."})
        dosya = self.kasa / "gelen-kutusu" / "yz-merkezi" / (datetime.now().strftime("%Y-%m-%d") + ".md")
        metin = dosya.read_text("utf-8")
        self.assertIn("kaynak: yz-merkezi", metin)
        self.assertIn("- soru: Hangi dili severim?\n", metin)
        self.assertNotIn("Bağlam (kişisel", metin)  # eklenen bağlam adaya karışmaz
        self.assertIn("- yanıt: Türkçe seversin.\n", metin)
        self.assertIn("- site: chatgpt\n", metin)

    def test_aday_ayari_kapaliysa_yazilmaz(self):
        self.istek("/api/ayar", {"hafiza_aday": False})
        v, _ = self.gonder("Merhaba")
        with mock.patch.object(ms, "site_konumu", return_value=None):
            self.istek("/api/yanit-kaydet", {"sohbet": v["sohbet"], "mesaj_sira": 0, "site": "chatgpt", "metin": "Selam"})
        self.assertFalse((self.kasa / "gelen-kutusu").exists())

    def test_hafiza_durum_ucu(self):
        d = self.istek("/api/hafiza-durum")
        self.assertEqual((d["kasa_var"], d["hafiza_py_var"], d["kasa"]), (True, True, str(self.kasa)))
        self.assertIsNone(d["son_mod"])
        self.gonder("Merhaba")
        self.assertEqual(self.istek("/api/hafiza-durum")["son_mod"], "local")
        # belirteçsiz istek reddedilir
        talep = urllib.request.Request(f"http://127.0.0.1:{self.sunucu.server_port}/api/hafiza-durum")
        with self.assertRaises(urllib.error.HTTPError) as h:
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(talep, timeout=10)
        self.assertEqual(h.exception.code, 403)


class ToctouTesti(KasaTestiTaban):
    """Denetlenen baytlar çalıştırılan baytlardır: hash denetiminden sonra dosya değişse bile ilk okunan kod çalışır."""

    def test_denetimden_sonra_degisen_dosya_calistirilmaz(self):
        kasa = self.kasa_kur()
        hk.baglam_getir("Hangi dil?")                  # özet kaydedilir
        yol = kasa / "araclar" / "hafiza.py"
        (kasa / "argv.json").unlink()
        gercek = hk._calistir

        def degistirerek_calistir(kasa_, sorgu, limit, butce, zaman_asimi, kod):
            # denetim geçti; çalıştırmadan hemen önce saldırgan dosyayı değiştirir
            yol.write_text("open('kotu.txt', 'w').write('calisti')\n", encoding="utf-8")
            return gercek(kasa_, sorgu, limit, butce, zaman_asimi, kod)

        with mock.patch.object(hk, "_calistir", degistirerek_calistir):
            sonuc = hk.baglam_getir("Hangi dil?")
        self.assertEqual(sonuc["metin"], BEKLENEN_BAGLAM)          # ilk okunan (denetlenen) kod çalıştı
        self.assertFalse((kasa / "kotu.txt").exists(), "sonradan yazılan sahte kod çalıştırılmamalı")

    def test_file_ve_argv_dosyadan_calistirilmis_gibi(self):
        kasa = self.kasa_kur(arac=SAHTE_ARAC.replace('q = a[-1]', 'q = a[-1]\nopen("kimlik.json","w").write(json.dumps('
                                                      '{"file": __file__, "name": __name__, "arg0": sys.argv[0], "yol0": sys.path[0]}))'))
        hk.baglam_getir("soru")
        k = json.loads((kasa / "kimlik.json").read_text("utf-8"))
        arac = str(kasa / "araclar" / "hafiza.py")
        self.assertEqual((k["file"], k["name"], k["arg0"], k["yol0"]), (arac, "__main__", arac, str(kasa / "araclar")))


class HashDenetimiTesti(KasaTestiTaban):
    """hafiza.py bütünlüğü: ilk başarılı çalıştırmada özet yazılır; değişirse araç çalıştırılmaz; onaydan sonra çalışır."""

    def test_ilk_basarili_calistirmada_ozet_yazilir(self):
        kasa = self.kasa_kur()
        self.assertFalse(self.ozet_dosyasi.exists())
        self.assertEqual(hk.baglam_getir("Hangi dil?")["metin"], BEKLENEN_BAGLAM)
        import hashlib
        beklenen = hashlib.sha256((kasa / "araclar" / "hafiza.py").read_bytes()).hexdigest()
        self.assertEqual(self.ozet_dosyasi.read_text("utf-8").strip(), beklenen)

    def test_hatali_ilk_calistirmada_ozet_yazilmaz(self):
        self.kasa_kur()
        hk.baglam_getir("HATA-KODU")
        self.assertFalse(self.ozet_dosyasi.exists())

    def test_degisirse_calistirilmaz_onaydan_sonra_calisir(self):
        kasa = self.kasa_kur()
        hk.baglam_getir("Hangi dil?")
        (kasa / "argv.json").unlink()
        (kasa / "araclar" / "hafiza.py").write_text(SAHTE_ARAC + "\n# kötü niyetli değişiklik\n", encoding="utf-8")
        sonuc = hk.baglam_getir("Hangi dil?")
        self.assertEqual(sonuc["metin"], "")
        self.assertIn("hafiza.py değişmiş", sonuc["sebep"])
        self.assertFalse((kasa / "argv.json").exists(), "değişmiş araç çalıştırılmamalı")
        d = hk.durum()
        self.assertTrue(d["hash_degisti"])
        self.assertIn("Ayarlar → Hafıza", d["hash_uyarisi"])
        self.assertEqual(hk.baglam_ekle("Hangi dil?"), ("Hangi dil?", None))
        # kullanıcı onaylar: yeni özet kabul edilir, araç yeniden çalışır
        self.assertTrue(hk.hash_onayla()["tamam"])
        self.assertFalse(hk.durum()["hash_degisti"])
        self.assertEqual(hk.baglam_getir("Hangi dil?")["metin"], BEKLENEN_BAGLAM)
        self.assertTrue((kasa / "argv.json").exists())

    def test_onay_araci_yoksa_basarisiz(self):
        self.kasa_kur(hafiza_py=False)
        self.assertFalse(hk.hash_onayla()["tamam"])
        self.assertFalse(self.ozet_dosyasi.exists())

    def test_bozuk_ozet_dosyasi_ilk_gorus_sayilir(self):
        self.kasa_kur()
        self.ozet_dosyasi.write_text("bozuk", encoding="utf-8")
        self.assertEqual(hk.baglam_getir("Hangi dil?")["metin"], BEKLENEN_BAGLAM)
        self.assertRegex(self.ozet_dosyasi.read_text("utf-8").strip(), r"^[0-9a-f]{64}$")

    def test_varsayilan_ozet_yolu_veri_klasorunde(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("YZ_HAFIZA_HASH", None)
            self.assertEqual(hk.hash_dosyasi(), ms.guvenlik.veri_klasoru() / "hafiza-py.sha256")


class HashOnayHttpTesti(HafizaSunucuTabani):
    """/api/hafiza-durum uyarısı ve /api/hafiza-onayla (belirteçli)."""

    def test_hafiza_onayla_ucu(self):
        hk.baglam_getir("Hangi dil?")
        (self.kasa / "araclar" / "hafiza.py").write_text(SAHTE_ARAC + "\n# yeni sürüm\n", encoding="utf-8")
        d = self.istek("/api/hafiza-durum")
        self.assertTrue(d["hash_degisti"])
        v, yazilan = self.gonder("Hangi dili severim?")
        self.assertEqual(yazilan, "Hangi dili severim?", "değişmiş araç çalışmaz; mesaj bağlamsız gider")
        ms.is_kilidi = threading.Lock()
        # belirteçsiz onay reddedilir
        talep = urllib.request.Request(f"http://127.0.0.1:{self.sunucu.server_port}/api/hafiza-onayla", b"{}",
                                       {"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as h:
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(talep, timeout=10)
        self.assertEqual(h.exception.code, 403)
        self.assertTrue(self.istek("/api/hafiza-durum")["hash_degisti"])
        v = self.istek("/api/hafiza-onayla", {})
        self.assertTrue(v["tamam"])
        self.assertFalse(v["durum"]["hash_degisti"])
        _, yazilan = self.gonder("Hangi dili severim?")
        self.assertTrue(yazilan.startswith("Bağlam (kişisel notlarımdan"))


class BaglamOnayiGonderTesti(HafizaSunucuTabani):
    """Gelişmiş kip /api/gonder: bağlam sitelere gitmeden önce gösterilir (hafiza_onay varsayılan AÇIK)."""

    def setUp(self):
        super().setUp()
        ms.ayarlari_yaz({"secili": {"site:gemini": False, "site:claude": False}})   # varsayılan: onay açık
        ms._BAGLAM_ONAYLARI.clear()

    def test_baglam_onayi_istenir_gonderim_ve_kayit_yok(self):
        v, yazilan = self.gonder("Hangi dili severim?")
        self.assertEqual((v["tur"], v["baglam_onay"]), ("baglam_onay", True))
        self.assertEqual((v["baglam"], v["karakter"]), (BEKLENEN_BAGLAM, len(BEKLENEN_BAGLAM)))
        self.assertTrue(v["baglam_kimligi"])
        self.assertEqual(yazilan, "", "onay gelmeden siteye hiçbir şey yazılmaz")
        self.assertEqual(ms.ayarlari_oku()["sohbetler"], [], "kayıt da yapılmaz")
        return v

    def test_ekle_karari_gosterilen_baglami_ekler(self):
        v = self.test_baglam_onayi_istenir_gonderim_ve_kayit_yok()
        v2, yazilan = self.gonder("Hangi dili severim?", baglam_karari="ekle", baglam_kimligi=v["baglam_kimligi"])
        self.assertEqual(v2["gonderilen"], ["ChatGPT"])
        self.assertTrue(yazilan.startswith("Bağlam (kişisel notlarımdan"))
        self.assertTrue(yazilan.endswith("---\nHangi dili severim?"))
        self.assertEqual(v2["sohbetler"][0]["mesajlar"][0]["baglam"]["metin"], BEKLENEN_BAGLAM)
        ms.is_kilidi = threading.Lock()
        # aynı kimlik ikinci kez kullanılamaz: yeniden onay istenir
        v3, yazilan = self.gonder("Hangi dili severim?", baglam_karari="ekle", baglam_kimligi=v["baglam_kimligi"])
        self.assertTrue(v3.get("baglam_onay"))
        self.assertEqual(yazilan, "")

    def test_ekleme_karari_baglamsiz_gonderir_ve_araci_calistirmaz(self):
        v, yazilan = self.gonder("Merhaba", baglam_karari="ekleme")
        self.assertEqual((yazilan, v["baglam"]), ("Merhaba", None))
        self.assertFalse((self.kasa / "argv.json").exists())

    def test_baska_mesaja_kimlik_gecmez(self):
        v, _ = self.gonder("Hangi dili severim?")
        v2, yazilan = self.gonder("Başka bir soru", baglam_karari="ekle", baglam_kimligi=v["baglam_kimligi"])
        self.assertTrue(v2.get("baglam_onay"), "onay o mesaja özgü; başka metinde yeniden sorulur")
        self.assertEqual(yazilan, "")

    def test_bos_baglamda_onay_istenmez(self):
        v, yazilan = self.gonder("BOS-BAGLAM mesajı")
        self.assertEqual((yazilan, v["gonderilen"]), ("BOS-BAGLAM mesajı", ["ChatGPT"]))

    def test_gecersiz_karar_400(self):
        for ek in ({"baglam_karari": "evet"}, {"baglam_karari": "ekle", "baglam_kimligi": "../x"}):
            with self.subTest(ek=ek), self.assertRaises(urllib.error.HTTPError) as h:
                self.gonder("Merhaba", **ek)
            self.assertEqual(h.exception.code, 400)

    def test_ayar_kapaliysa_eski_otomatik_davranis(self):
        self.istek("/api/ayar", {"hafiza_onay": False})
        v, yazilan = self.gonder("Hangi dili severim?")
        self.assertTrue(yazilan.startswith("Bağlam (kişisel notlarımdan"))
        with self.assertRaises(urllib.error.HTTPError):
            self.istek("/api/ayar", {"hafiza_onay": "hayır"})


if __name__ == "__main__":
    unittest.main()
