"""Kod denetim testleri: kaynak dosyalarında tehlikeli kalıplar (innerHTML, çerez erişimi, sızan anahtar) olmasın.

Bu testler kodu çalıştırmaz, yalnızca metin olarak tarar. Bir denetim yanlışlıkla gevşetilirse ya da yeni
bir kalıp eklenirse testin kırılması beklenir.
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import re
import sys
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
import siteler  # noqa: E402

ARAYUZ_DOSYALARI = (KOK / "arayuz-masaustu" / "uygulama.js", KOK / "arayuz" / "uygulama.js")
ATLANAN_KLASORLER = {".git", "__pycache__", "node_modules", ".tarayici-profili", ".claude", "veri"}

# innerHTML'e atama (=, +=, ...); karşılaştırma (==, ===) ve okuma sayılmaz.
INNERHTML_ATAMA = re.compile(r"\.innerHTML\s*(?P<islem>[-+*/%|&^]?=)(?!=)(?P<sag>[^\n]*)")
# Tek izinli biçim: kapsayıcıyı boşaltmak.
INNERHTML_BOSALTMA = re.compile(r"""^\s*(?:""|'')\s*;?\s*(?://.*)?$""")
# Başka HTML enjeksiyon yolları hiç kullanılmamalı.
TEHLIKELI_HTML = re.compile(r"\.outerHTML\s*=(?!=)|\.insertAdjacentHTML\s*\(|document\.write(?:ln)?\s*\(")

# Anahtar/belirteç kalıpları: 20+ karakterlik uzun gövde (örnek metinler ve "sk-" öneki tek başına sorun değil).
BELIRTEC_KALIBI = re.compile(r"(?<![A-Za-z0-9_])(?:sk-ant-|sk-|AIza|ghp_)[A-Za-z0-9_\-]{20,}")

SITE_JS_YASAKLARI = (
    ("Network.", re.compile(r"Network\.")),
    ("Storage.", re.compile(r"Storage\.")),
    ("cookie", re.compile(r"cookie", re.I)),
    ("localStorage", re.compile(r"localStorage")),
    ("sessionStorage", re.compile(r"sessionStorage")),
    ("password", re.compile(r"password", re.I)),
)


def innerhtml_sorunlari(metin):
    """Boşaltma (= "" / = '') dışındaki her innerHTML atamasını (satır no, satır) olarak döndürür."""
    sorunlar = []
    for no, satir in enumerate(metin.splitlines(), 1):
        for e in INNERHTML_ATAMA.finditer(satir):
            if e.group("islem") != "=" or not INNERHTML_BOSALTMA.match(e.group("sag")):
                sorunlar.append((no, satir.strip()))
    return sorunlar


def kaynak_dosyalari():
    """Projedeki .py ve .js dosyaları (tarayıcı profili, git ve önbellek klasörleri hariç)."""
    for yol in sorted(KOK.rglob("*")):
        if yol.suffix in (".py", ".js") and yol.is_file() and not (set(yol.relative_to(KOK).parts) & ATLANAN_KLASORLER):
            yield yol


class InnerHtmlDenetimiTesti(unittest.TestCase):
    def test_denetleyici_kendi_kendine(self):
        iyi = 'a.innerHTML = "";\nb.innerHTML = \'\';\nc.innerHTML="" ;\nif (x.innerHTML === y) {}\nlet z = e.innerHTML;'
        self.assertEqual(innerhtml_sorunlari(iyi), [])
        for kotu in ('a.innerHTML = veri;', 'a.innerHTML = "<b>" + x;', 'a.innerHTML += "";', "a.innerHTML = `${x}`;",
                     'a.innerHTML = "" + x;', "a.innerHTML = '<i>';"):
            with self.subTest(kod=kotu):
                self.assertEqual(len(innerhtml_sorunlari(kotu)), 1)

    def test_arayuz_dosyalarinda_innerhtml_yalniz_bosaltma(self):
        for yol in ARAYUZ_DOSYALARI:
            with self.subTest(dosya=str(yol.relative_to(KOK))):
                self.assertTrue(yol.is_file(), f"{yol} yok")
                self.assertEqual(innerhtml_sorunlari(yol.read_text("utf-8")), [])

    def test_baska_html_enjeksiyon_yolu_yok(self):
        for yol in ARAYUZ_DOSYALARI:
            with self.subTest(dosya=str(yol.relative_to(KOK))):
                self.assertIsNone(TEHLIKELI_HTML.search(yol.read_text("utf-8")))


class SiteJsDenetimiTesti(unittest.TestCase):
    def parcalar(self):
        for kimlik, kayit in siteler.SITELER.items():
            for anahtar, parca in kayit["js"].items():
                yield f"{kimlik}/{anahtar}", parca
        for kimlik in siteler.SITELER:  # kenar çubuğunu açan sürüm de aynı kurallara uymalı
            yield f"{kimlik}/sohbet_listesi(kenar_ac)", siteler.js_parca(kimlik, "sohbet_listesi", kenar_ac=True)

    def test_yasakli_sozcukler_yok(self):
        sayac = 0
        for ad, parca in self.parcalar():
            sayac += 1
            for etiket, kalip in SITE_JS_YASAKLARI:
                with self.subTest(parca=ad, yasak=etiket):
                    self.assertIsNone(kalip.search(parca), f"{ad}: {etiket} geçiyor")
        self.assertGreaterEqual(sayac, 3 * len(siteler.JS_ANAHTARLARI))

    def test_yasakli_kalip_yakalanir(self):
        for etiket, ornek in (("Network.", "Network.getAllCookies"), ("Storage.", "Storage.getCookies"),
                              ("cookie", "document.Cookie"), ("localStorage", "window.localStorage"),
                              ("sessionStorage", "sessionStorage.x"), ("password", "input[type=PassWord]")):
            kalip = dict(SITE_JS_YASAKLARI)[etiket]
            self.assertIsNotNone(kalip.search(ornek), etiket)


class TarayiciBayraklariTesti(unittest.TestCase):
    def test_remote_allow_origins_yok(self):
        metin = (KOK / "tarayici.py").read_text("utf-8")
        self.assertNotIn("remote-allow-origins", metin)

    def test_baska_kaynakta_da_yok(self):
        for yol in kaynak_dosyalari():
            if yol.name == "test_guvenlik_kod.py":
                continue
            with self.subTest(dosya=str(yol.relative_to(KOK))):
                self.assertNotIn("remote-allow-origins", yol.read_text("utf-8", errors="replace"))

    def test_hata_ayiklama_portu_hicbir_yerde_yok(self):
        # CDP yalnızca boru (--remote-debugging-pipe) üzerinden: TCP denetim portu açan bayrak hiçbir dosyada olmamalı.
        yasak = "remote-debugging-" + "port"
        dosyalar = list(kaynak_dosyalari()) + [KOK / "BENIOKU.md", KOK / "baslat.bat", KOK / "baslat-api.bat"]
        for yol in dosyalar:
            with self.subTest(dosya=str(yol.relative_to(KOK))):
                self.assertNotIn(yasak, yol.read_text("utf-8", errors="replace"))
        self.assertIn("--remote-debugging-pipe", (KOK / "cdp.py").read_text("utf-8"))


class SizanAnahtarDenetimiTesti(unittest.TestCase):
    def test_kalip_kendi_kendine(self):
        for kotu in ("sk-" + "a" * 20, "sk-ant-" + "B1_-" * 6, "AIza" + "x" * 35, "ghp_" + "9" * 36,
                     'anahtar = "sk-proj-' + "z" * 30 + '"'):
            with self.subTest(ornek=kotu[:10]):
                self.assertIsNotNone(BELIRTEC_KALIBI.search(kotu))
        for iyi in ("sk-", "sk-kisa", "ask-" + "a" * 30, "AIza kisa", "ghp_ ornek", "task-" + "a" * 30, "sk-ant-..."):
            with self.subTest(ornek=iyi):
                self.assertIsNone(BELIRTEC_KALIBI.search(iyi))

    def test_kaynak_dosyalarinda_belirtec_yok(self):
        dosyalar = list(kaynak_dosyalari())
        self.assertGreater(len(dosyalar), 10)  # tarama gerçekten dosya buldu
        for yol in dosyalar:
            with self.subTest(dosya=str(yol.relative_to(KOK))):
                eslesme = BELIRTEC_KALIBI.search(yol.read_text("utf-8", errors="replace"))
                self.assertIsNone(eslesme, "anahtar benzeri metin: " + (eslesme.group(0)[:8] + "..." if eslesme else ""))


if __name__ == "__main__":
    unittest.main()
