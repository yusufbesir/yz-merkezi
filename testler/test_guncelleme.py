"""Güncelleme ve eski sürüm temizliği testleri (guncelleme.py).

Her şey geçici klasörlerde olur: gerçek %LOCALAPPDATA%\\YZMerkezi, kasa ve proje kökündeki dosyalar ne silinir ne
yazılır. Proje kökü yalnızca OKUNUR (manifest üretimi ve gerçek uygulamanın duman testi için geçici kopya).
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(KOK))
import _ortam  # noqa: E402,F401  (gerçek ayar dosyalarını korur; sunucu modüllerinden önce)
import guncelleme as gn  # noqa: E402
import guvenlik  # noqa: E402
import surum  # noqa: E402

SAGLAM = {
    "masaustu_sunucu.py": "import surum\nDEGER = 1\n",
    "surum.py": "SURUM = '{surum}'\n",
    "motorlar/__init__.py": "from . import taban\n",
    "motorlar/taban.py": "X = '{surum}'\n",
    "arayuz-masaustu/index.html": "<html>{surum}</html>\n",
    "baslat.bat": "@echo off\n",
}


def junction_olustur(hedef, baglanti):
    """Windows junction (yönetici izni gerekmez). Olmazsa SkipTest."""
    try:
        import _winapi
        _winapi.CreateJunction(str(hedef), str(baglanti))
    except (ImportError, AttributeError, OSError) as h:
        raise unittest.SkipTest(f"junction oluşturulamadı: {h}")


class Taban(unittest.TestCase):
    def setUp(self):
        self.gecici = Path(os.path.realpath(tempfile.mkdtemp(prefix="yzguncel_")))  # 8.3 kısa adları aç
        self.kok = self.gecici / "kurulum"
        self.kok.mkdir()
        self._eski_log = os.environ.get("YZ_GUNCELLEME_LOG")
        os.environ["YZ_GUNCELLEME_LOG"] = str(self.gecici / "veri" / "guncelleme.log")
        self.baglantilar = []

    def tearDown(self):
        for b in self.baglantilar:  # bağlantının kendisini kaldır, hedefine dokunma
            try:
                if os.path.isdir(b):
                    os.rmdir(b)
                else:
                    os.unlink(b)
            except OSError:
                pass
        if self._eski_log is None:
            os.environ.pop("YZ_GUNCELLEME_LOG", None)
        else:
            os.environ["YZ_GUNCELLEME_LOG"] = self._eski_log
        shutil.rmtree(self.gecici, ignore_errors=True)

    def kaynak(self, surum_no, dosyalar=None, ad=None):
        """Geçici kaynak klasöründe bir sürüm (dosyalar + manifest.json) hazırlar."""
        klasor = self.gecici / (ad or f"kaynak-{surum_no}")
        klasor.mkdir()
        for yol, icerik in (dosyalar or SAGLAM).items():
            tam = klasor / yol
            tam.parent.mkdir(parents=True, exist_ok=True)
            tam.write_text(icerik.replace("{surum}", surum_no), "utf-8")
        gn.manifest_yaz(klasor, gn.manifest_uret(klasor, surum_no))
        return klasor

    def kur(self, surum_no, **k):
        return gn.guncelle(self.kok, self.kaynak(surum_no, **k))

    def isaretci(self):
        return json.loads((self.kok / "guncel.json").read_text("utf-8"))

    def agac(self, klasor):
        return sorted(p.relative_to(klasor).as_posix() for p in Path(klasor).rglob("*") if p.is_file())


class SurumKimlikTesti(unittest.TestCase):
    def test_semver_ve_kimlik(self):
        self.assertRegex(surum.SURUM, gn.SEMVER)
        self.assertEqual(surum.kimlik(), {"uygulama": "yz-merkezi", "surum": surum.SURUM})
        self.assertEqual(guvenlik.KIMLIK, surum.kimlik())


class BasariliGuncellemeTesti(Taban):
    def test_eski_surum_manifest_dosyalari_silinir_digerleri_kalir(self):
        self.kur("1.0.0")
        eski = self.kok / "surumler" / "1.0.0"
        self.assertEqual(self.isaretci(), {"surum": "1.0.0", "yol": "surumler/1.0.0"})
        # eski sürümün içinde manifest dışı ve korunan kalıplı dosyalar + Python önbelleği
        (eski / "kullanici-notu.txt").write_text("benim", "utf-8")
        (eski / "ayarlar.json").write_text("{}", "utf-8")
        (eski / "masaustu-ayarlar.json").write_text("{}", "utf-8")
        (eski / "hata.log").write_text("x", "utf-8")
        (eski / ".tarayici-profili").mkdir()
        (eski / ".tarayici-profili" / "Cookies").write_text("c", "utf-8")
        (eski / "__pycache__").mkdir()
        (eski / "__pycache__" / "masaustu_sunucu.cpython-312.pyc").write_bytes(b"\0")
        (eski / "__pycache__" / "baska.cpython-312.pyc").write_bytes(b"\0")  # kaynağı manifestte yok
        kok_veri = self.kok / "ayarlar.json"
        kok_veri.write_text("{}", "utf-8")

        sonuc = self.kur("1.1.0")
        self.assertEqual(self.isaretci(), {"surum": "1.1.0", "yol": "surumler/1.1.0"})
        for yol in SAGLAM:
            self.assertFalse((eski / yol).exists(), yol)
        self.assertFalse((eski / "manifest.json").exists())
        self.assertFalse((eski / "motorlar").exists())  # boş kalan klasör kaldırıldı
        self.assertFalse((eski / "__pycache__" / "masaustu_sunucu.cpython-312.pyc").exists())
        self.assertEqual(self.agac(eski), sorted([
            "kullanici-notu.txt", "ayarlar.json", "masaustu-ayarlar.json", "hata.log",
            ".tarayici-profili/Cookies", "__pycache__/baska.cpython-312.pyc"]))
        self.assertTrue(kok_veri.exists())
        self.assertTrue(gn.kaynak_dogrula(self.kok / "surumler" / "1.1.0")["gecerli"])
        self.assertTrue(sonuc["kopyalandi"])
        self.assertIn(str(eski / "masaustu_sunucu.py"), sonuc["silinen"])

    def test_tamamen_temizlenen_eski_surum_klasoru_kalkar(self):
        self.kur("1.0.0")
        self.kur("1.1.0")
        self.assertFalse((self.kok / "surumler" / "1.0.0").exists())
        self.assertEqual(sorted(p.name for p in (self.kok / "surumler").iterdir()), ["1.1.0"])

    def test_gunluk_yazilir(self):
        self.kur("1.0.0")
        self.kur("1.1.0")
        metin = gn.gunluk_dosyasi().read_text("utf-8")
        self.assertEqual(gn.gunluk_dosyasi(), self.gecici / "veri" / "guncelleme.log")
        for parca in ("GÜNCELLEME BAŞLADI", "Doğrulandı: 1.1.0", "Duman testi geçti", "İşaretçi güncellendi",
                      "SİLİNDİ (manifest)", "GÜNCELLEME TAMAMLANDI: 1.1.0"):
            self.assertIn(parca, metin)
        self.assertLessEqual(len(gn.gunluk_son(20)), 20)

    def test_ayni_surum_zaten_kuruluysa_kopyalama_atlanir(self):
        self.kur("1.0.0")
        sonuc = gn.guncelle(self.kok, self.kok / "surumler" / "1.0.0")
        self.assertFalse(sonuc["kopyalandi"])
        self.assertEqual(sonuc["silinen"], [])

    def test_manifesti_olmayan_surum_klasorune_dokunulmaz(self):
        yabanci = self.kok / "surumler" / "0.9.0"
        yabanci.mkdir(parents=True)
        (yabanci / "masaustu_sunucu.py").write_text("x", "utf-8")
        self.kur("1.0.0")
        self.assertTrue((yabanci / "masaustu_sunucu.py").exists())

    def test_durum(self):
        self.kur("1.0.0")
        d = gn.durum(self.kok / "surumler" / "1.0.0")
        self.assertEqual(d["surum"], surum.SURUM)
        self.assertEqual(Path(d["kurulum_koku"]).resolve(), self.kok.resolve())
        self.assertEqual(d["guncel"], {"surum": "1.0.0", "yol": "surumler/1.0.0"})
        self.assertEqual(d["kurulu_surumler"], ["1.0.0"])
        self.assertTrue(d["gunluk"])
        self.assertEqual(gn.etkin_klasor(self.kok), self.kok / "surumler" / "1.0.0")


class BasarisizGuncellemeTesti(Taban):
    def onceki_durum(self):
        self.kur("1.0.0")
        return self.agac(self.kok), (self.kok / "guncel.json").read_bytes()

    def test_hash_uyusmazligi(self):
        agac, isaret = self.onceki_durum()
        kaynak = self.kaynak("2.0.0")
        m = json.loads((kaynak / "manifest.json").read_text("utf-8"))
        m["dosyalar"][0]["sha256"] = "0" * 64
        gn.manifest_yaz(kaynak, m)
        with self.assertRaises(gn.GuncellemeHatasi):
            gn.guncelle(self.kok, kaynak)
        self.assertFalse((self.kok / "surumler" / "2.0.0").exists())
        self.assertEqual(self.agac(self.kok), agac)
        self.assertEqual((self.kok / "guncel.json").read_bytes(), isaret)

    def test_eksik_dosya(self):
        agac, isaret = self.onceki_durum()
        kaynak = self.kaynak("2.0.0")
        (kaynak / "motorlar" / "taban.py").unlink()
        with self.assertRaises(gn.GuncellemeHatasi):
            gn.guncelle(self.kok, kaynak)
        self.assertFalse((self.kok / "surumler" / "2.0.0").exists())
        self.assertEqual(self.agac(self.kok), agac)
        self.assertEqual((self.kok / "guncel.json").read_bytes(), isaret)

    def test_duman_testi_basarisiz(self):
        agac, isaret = self.onceki_durum()
        bozuk = dict(SAGLAM, **{"masaustu_sunucu.py": "raise RuntimeError('bozuk surum')\n"})
        with self.assertRaises(gn.GuncellemeHatasi) as bag:
            self.kur("2.0.0", dosyalar=bozuk)
        self.assertIn("duman", str(bag.exception))
        self.assertFalse((self.kok / "surumler" / "2.0.0").exists())
        self.assertEqual(self.agac(self.kok), agac)
        self.assertEqual((self.kok / "guncel.json").read_bytes(), isaret)
        self.assertIn("GERİ ALINDI", gn.gunluk_dosyasi().read_text("utf-8"))

    def test_zaten_var_olan_bozuk_klasor_silinmez(self):
        agac, isaret = self.onceki_durum()
        kaynak = self.kaynak("2.0.0")
        hedef = self.kok / "surumler" / "2.0.0"
        hedef.mkdir()
        (hedef / "yabanci.txt").write_text("x", "utf-8")
        with self.assertRaises(gn.GuncellemeHatasi):
            gn.guncelle(self.kok, kaynak)
        self.assertTrue((hedef / "yabanci.txt").exists())
        self.assertEqual((self.kok / "guncel.json").read_bytes(), isaret)

    def test_kaynak_dogrula_fazla_ve_eksik(self):
        self.kur("1.0.0")
        k = self.kok / "surumler" / "1.0.0"
        self.assertTrue(gn.kaynak_dogrula(k)["gecerli"])
        (k / "fazla.txt").write_text("x", "utf-8")
        d = gn.kaynak_dogrula(k)
        self.assertFalse(d["gecerli"])
        self.assertTrue(any("fazla" in s for s in d["sorunlar"]))
        (k / "fazla.txt").unlink()
        (k / "baslat.bat").unlink()
        self.assertTrue(any("eksik" in s for s in gn.kaynak_dogrula(k)["sorunlar"]))


class BaglantiVeYolTesti(Taban):
    def test_junction_izlenmez_dis_hedef_silinmez(self):
        self.kur("1.0.0")
        eski = self.kok / "surumler" / "1.0.0"
        dis = self.gecici / "disarisi"
        dis.mkdir()
        (dis / "taban.py").write_text("DEĞERLİ", "utf-8")
        (dis / "__init__.py").write_text("DEĞERLİ", "utf-8")
        shutil.rmtree(eski / "motorlar")
        junction_olustur(dis, eski / "motorlar")
        self.baglantilar.append(eski / "motorlar")
        self.assertTrue(gn.reparse_mi(eski / "motorlar"))
        sonuc = self.kur("1.1.0")
        self.assertEqual((dis / "taban.py").read_text("utf-8"), "DEĞERLİ")
        self.assertEqual((dis / "__init__.py").read_text("utf-8"), "DEĞERLİ")
        self.assertTrue(any("bağlantı" in a["neden"] and a["yol"].endswith("motorlar") for a in sonuc["atlanan"]))
        self.assertTrue(os.path.lexists(eski / "motorlar"))  # bağlantının kendisi de bırakıldı
        self.assertFalse((eski / "masaustu_sunucu.py").exists())  # bağlantı dışındaki dosyalar temizlendi
        self.assertTrue((eski / "manifest.json").exists())  # tamamı silinemedi: manifest korunur

    def test_junction_surum_klasorunun_kendisi(self):
        dis = self.kaynak("0.5.0", ad="dis-surum")  # manifestli, gerçek bir sürüm gibi duran dış klasör
        (self.kok / "surumler").mkdir()
        junction_olustur(dis, self.kok / "surumler" / "0.5.0")
        self.baglantilar.append(self.kok / "surumler" / "0.5.0")
        self.kur("1.0.0")
        self.assertEqual(self.agac(dis), sorted(list(SAGLAM) + ["manifest.json"]))

    def test_symlink_izlenmez(self):
        self.kur("1.0.0")
        eski = self.kok / "surumler" / "1.0.0"
        dis = self.gecici / "dis-dosya.txt"
        dis.write_text("DEĞERLİ", "utf-8")
        (eski / "baslat.bat").unlink()
        try:
            os.symlink(dis, eski / "baslat.bat")
        except (OSError, NotImplementedError) as h:
            self.skipTest(f"symlink izni yok: {h}")
        self.baglantilar.append(eski / "baslat.bat")
        sonuc = self.kur("1.1.0")
        self.assertEqual(dis.read_text("utf-8"), "DEĞERLİ")
        self.assertTrue(any(a["yol"].endswith("baslat.bat") for a in sonuc["atlanan"]))

    def test_kok_disina_isaret_eden_manifest_reddedilir(self):
        self.kur("1.0.0")
        eski = self.kok / "surumler" / "1.0.0"
        disari = self.kok / "surumler" / "disari.txt"
        disari.write_text("DEĞERLİ", "utf-8")
        cok_disari = self.gecici / "kok-disi.txt"
        cok_disari.write_text("DEĞERLİ", "utf-8")
        m = json.loads((eski / "manifest.json").read_text("utf-8"))
        m["dosyalar"].append({"yol": "..\\disari.txt", "sha256": "0" * 64, "boyut": 1})
        m["dosyalar"].append({"yol": "../../../kok-disi.txt", "sha256": "0" * 64, "boyut": 1})
        gn.manifest_yaz(eski, m)
        sonuc = self.kur("1.1.0")
        self.assertTrue(disari.exists())
        self.assertTrue(cok_disari.exists())
        self.assertTrue((eski / "masaustu_sunucu.py").exists())  # geçersiz manifest: sürüme hiç dokunulmadı
        self.assertTrue(any("manifest geçersiz" in a["neden"] for a in sonuc["atlanan"]))

    def test_yol_parcalari(self):
        for kotu in ("..\\a", "../a", "a/../b", "/a", "C:\\a", "C:a", "", "a//b", "a/./b", "a/b."):
            with self.subTest(yol=kotu):
                with self.assertRaises(ValueError):
                    gn.yol_parcalari(kotu)
        self.assertEqual(gn.yol_parcalari("motorlar\\taban.py"), ("motorlar", "taban.py"))

    def test_korunan_kalipli_manifest_reddedilir(self):
        self.kur("1.0.0")
        eski = self.kok / "surumler" / "1.0.0"
        (eski / "masaustu-ayarlar.json").write_text("{}", "utf-8")
        (eski / "veri").mkdir()
        (eski / "veri" / "sohbet.json").write_text("{}", "utf-8")
        m = json.loads((eski / "manifest.json").read_text("utf-8"))
        m["dosyalar"].append({"yol": "masaustu-ayarlar.json", "sha256": "0" * 64, "boyut": 2})
        m["dosyalar"].append({"yol": "veri/sohbet.json", "sha256": "0" * 64, "boyut": 2})
        gn.manifest_yaz(eski, m)
        sonuc = self.kur("1.1.0")
        self.assertTrue((eski / "masaustu-ayarlar.json").exists())
        self.assertTrue((eski / "veri" / "sohbet.json").exists())
        self.assertTrue(any("korunan" in a["neden"] for a in sonuc["atlanan"]))
        for ad in ("ayarlar.json", "masaustu-ayarlar-yedek.json", "a.log", ".tarayici-profili", "kasa", "veri"):
            self.assertTrue(gn.korunan_mu(("x", ad)), ad)


class GelistirmeKurulumuTesti(Taban):
    def test_git_olan_kokte_kok_dosyalari_silinmez(self):
        for yol, icerik in SAGLAM.items():
            tam = self.kok / yol
            tam.parent.mkdir(parents=True, exist_ok=True)
            tam.write_text(icerik.replace("{surum}", "1.0.0"), "utf-8")
        (self.kok / ".git").mkdir()
        (self.kok / ".git" / "HEAD").write_text("ref", "utf-8")
        gn.manifest_yaz(self.kok, gn.manifest_uret(self.kok, "1.0.0"))
        self.assertTrue(gn.gelistirme_kurulumu_mu(self.kok))
        gn.guncelle(self.kok, self.kok)  # surum_paketle'nin yolu: kökten surumler/1.0.0'a
        (self.kok / "surum.py").write_text("SURUM = '1.1.0'\n", "utf-8")
        gn.manifest_yaz(self.kok, gn.manifest_uret(self.kok, "1.1.0"))
        kok_oncesi = {p: (self.kok / p).read_bytes() for p in list(SAGLAM) + ["manifest.json", ".git/HEAD"]}
        gn.guncelle(self.kok, self.kok)
        gn.eski_surumleri_temizle(self.kok, korunan="1.1.0")
        for p, icerik in kok_oncesi.items():
            self.assertEqual((self.kok / p).read_bytes(), icerik, p)
        self.assertFalse((self.kok / "surumler" / "1.0.0").exists())
        self.assertIn("geliştirme kurulumu", gn.gunluk_dosyasi().read_text("utf-8"))

    def test_git_olan_surum_klasorune_dokunulmaz(self):
        self.kur("1.0.0")
        eski = self.kok / "surumler" / "1.0.0"
        (eski / ".git").mkdir()
        sonuc = self.kur("1.1.0")
        self.assertTrue((eski / "masaustu_sunucu.py").exists())
        self.assertTrue(any(".git" in a["neden"] for a in sonuc["atlanan"]))


class ManifestTesti(Taban):
    def test_veri_dosyalari_dislanir(self):
        k = self.gecici / "proje"
        for yol in ("masaustu_sunucu.py", "surum.py", "uygulamalar.json", "baslat.bat", "kisayol-olustur.ps1",
                    "BENIOKU.md", "motorlar/taban.py", "araclar/manifest_uret.py", "arayuz-masaustu/stil.css",
                    # dışlanması gerekenler:
                    "ayarlar.json", "ayarlar.tmp", "masaustu-ayarlar.json", "masaustu-ayarlar.bozuk-1.json",
                    "hata.log", "guncel.json", ".tarayici-profili/Default/Cookies", "testler/test_a.py",
                    ".git/config", "__pycache__/a.cpython-312.pyc", "motorlar/__pycache__/taban.cpython-312.pyc",
                    "veri/a.json", "kasa/not.md", "surumler/1.0.0/a.py", ".claude/devam.md",
                    "motorlar/hata.log", "arayuz-masaustu/ayarlar.json"):
            tam = k / yol
            tam.parent.mkdir(parents=True, exist_ok=True)
            tam.write_text("x", "utf-8")
        yollar = [d["yol"] for d in gn.manifest_uret(k, "1.0.0")["dosyalar"]]
        self.assertEqual(sorted(yollar), sorted([
            "masaustu_sunucu.py", "surum.py", "uygulamalar.json", "baslat.bat", "kisayol-olustur.ps1", "BENIOKU.md",
            "motorlar/taban.py", "araclar/manifest_uret.py", "arayuz-masaustu/stil.css"]))

    def test_gercek_proje_manifesti(self):
        m = gn.manifest_uret(KOK)  # yalnızca okur; manifest.json yazmaz
        yollar = {d["yol"] for d in m["dosyalar"]}
        self.assertEqual(m["surum"], surum.SURUM)
        for gerekli in ("masaustu_sunucu.py", "guncelleme.py", "surum.py", "guvenlik.py", "motorlar/__init__.py",
                        "arayuz-masaustu/index.html", "araclar/surum_paketle.py", "baslat.bat"):
            self.assertIn(gerekli, yollar)
        for y in yollar:
            parcalar = tuple(y.split("/"))
            self.assertFalse(gn.korunan_mu(parcalar), y)
            self.assertNotIn(parcalar[0], ("testler", ".git", ".claude", "surumler"), y)
            self.assertNotIn("__pycache__", parcalar, y)
            self.assertNotEqual(y, "manifest.json")
        for d in m["dosyalar"]:
            self.assertRegex(d["sha256"], r"^[0-9a-f]{64}$")


class GercekUygulamaDumanTesti(Taban):
    def test_gercek_uygulama_kurulur_ve_duman_testinden_gecer(self):
        manifest = gn.manifest_uret(KOK)
        kaynak = self.gecici / "gercek-kaynak"
        for d in manifest["dosyalar"]:
            hedef = kaynak / d["yol"]
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(KOK / d["yol"], hedef)
        gn.manifest_yaz(kaynak, manifest)
        sonuc = gn.guncelle(self.kok, kaynak)
        self.assertEqual(sonuc["surum"], surum.SURUM)
        kurulu = self.kok / "surumler" / surum.SURUM
        self.assertTrue(gn.kaynak_dogrula(kurulu)["gecerli"])
        self.assertFalse((kurulu / "__pycache__").exists())  # duman testi önbellek yazmaz
        self.assertEqual(gn.etkin_klasor(self.kok), kurulu)


class GuncellemeDurumUcuTesti(unittest.TestCase):
    """GET /api/guncelleme-durum (belirteç ister) ve /api/kimlik sürümü."""

    def setUp(self):
        import threading
        from http.server import ThreadingHTTPServer
        import masaustu_sunucu as ms
        self.ms = ms
        self.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), ms.Isleyici)
        threading.Thread(target=self.sunucu.serve_forever, daemon=True).start()
        self.addCleanup(self.sunucu.server_close)
        self.addCleanup(self.sunucu.shutdown)

    def istek(self, yol, belirtec=True):
        import urllib.error
        import urllib.request
        basliklar = {"X-YZ-Token": self.ms.BELIRTEC} if belirtec else {}
        talep = urllib.request.Request(f"http://127.0.0.1:{self.sunucu.server_port}{yol}", headers=basliklar)
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with acici.open(talep, timeout=10) as y:
                return y.status, json.load(y)
        except urllib.error.HTTPError as h:
            return h.code, json.loads(h.read().decode("utf-8"))

    def test_durum_ucu(self):
        kod, v = self.istek("/api/guncelleme-durum")
        self.assertEqual(kod, 200)
        self.assertEqual(v["surum"], surum.SURUM)
        for alan in ("calisan_klasor", "kurulum_koku", "gelistirme_kurulumu", "guncel", "kurulu_surumler", "gunluk"):
            self.assertIn(alan, v)
        self.assertLessEqual(len(v["gunluk"]), 20)
        self.assertEqual(self.istek("/api/guncelleme-durum", belirtec=False)[0], 403)

    def test_kimlik_surumu(self):
        kod, v = self.istek("/api/kimlik", belirtec=False)
        self.assertEqual((kod, v), (200, {"uygulama": "yz-merkezi", "surum": surum.SURUM}))


if __name__ == "__main__":
    unittest.main()
