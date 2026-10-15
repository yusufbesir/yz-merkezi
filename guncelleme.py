#!/usr/bin/env python3
"""Sürüm kurma ve eski sürüm dosyalarını kendi kendine temizleme (yalnızca standart kütüphane).

Kural (Yusuf): yeni sürüm kurulunca eski sürümden kalan dosyaları uygulama kendisi siler; kullanıcı verisi asla.

Kurulum düzeni:
    <kurulum_koku>/surumler/<surum>/      her sürüm kendi klasöründe, kendi manifest.json dosyasıyla
    <kurulum_koku>/guncel.json             {"surum": "1.1.0", "yol": "surumler/1.1.0"} (etkin sürüm işaretçisi)

Sınırlar:
- Yalnızca `surumler/<eski>/` altındaki, O KLASÖRÜN manifest.json dosyasında yazan dosyalar (ve onların Python
  önbelleği) silinir. Manifest dışı dosyaya, manifesti olmayan sürüm klasörüne, kurulum kökünün kendisine dokunulmaz.
- Gerçek yol denetlenir: symlink/junction (reparse point) asla izlenmez; yolda biri varsa atlanır ve raporlanır.
- KORUNAN_KALIPLAR (ayarlar, günlükler, tarayıcı profili, veri, kasa ...) ve veri klasörü her durumda silinmez.
- Önce yeni sürüm kopyalanır, DOĞRULANIR (sha256, eksik/fazla dosya) ve duman testinden geçer; ancak sonra işaretçi
  atomik yazılır ve eski sürümler temizlenir. Başarısız güncellemede yalnızca bu işlemin kopyaladığı dosyalar geri
  alınır; eski sürüm ve işaretçi aynen kalır.
- `.git` bulunan kök "geliştirme kurulumu"dur: kökteki dosyalar hiçbir zaman silinmez (yalnızca `surumler/` işlenir).

Her adım `%LOCALAPPDATA%\\YZMerkezi\\guncelleme.log` dosyasına yazılır (YZ_GUNCELLEME_LOG ile değiştirilebilir).

Komut satırı:
    python guncelleme.py --yol                etkin sürüm klasörünü yazar (baslat.bat kullanır)
    python guncelleme.py --baslat             etkin sürümde masaustu_sunucu.py'yi pythonw ile başlatır
    python guncelleme.py --guncelle KLASOR    KLASOR'daki sürümü bu köke kurar
    python guncelleme.py --temizle            eski sürümleri temizler
    python guncelleme.py --durum              durum özetini JSON olarak yazar
"""
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

import guvenlik

KOK = Path(__file__).resolve().parent
SURUMLER = "surumler"
ISARETCI = "guncel.json"
MANIFEST = "manifest.json"
GUNLUK_SINIRI = 1_000_000          # bayt: guncelleme.log bu boyu aşınca yedeğe alınır
DUMAN_ZAMAN_ASIMI = 90             # sn
DUMAN_MODULLERI = ("masaustu_sunucu", "motorlar", "surum")
SEMVER = re.compile(r"^(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})$")
FILE_ATTRIBUTE_REPARSE_POINT = 0x400

# Hangi yolda olursa olsun (herhangi bir parçası eşleşirse) asla silinmez ve manifeste girmez.
KORUNAN_KALIPLAR = (
    "ayarlar*.json", "masaustu-ayarlar*.json", "*.bozuk-*.json", "*.log", "*.log.*", "*.tmp",
    ".tarayici-profili*", "tarayici-profili*", "veri", "kasa", "belirtec", ISARETCI, SURUMLER, ".git",
)

# Manifeste giren uygulama dosyaları: kökteki bu uzantılar + bu klasörlerin tamamı.
KOK_UZANTILARI = (".py", ".json", ".bat", ".ps1", ".md")
UYGULAMA_KLASORLERI = ("arayuz", "arayuz-masaustu", "motorlar", "araclar")
MANIFEST_DISI_KLASORLER = {".git", "testler", "__pycache__", ".claude", SURUMLER, "node_modules"}


class GuncellemeHatasi(Exception):
    """Güncelleme yapılmadı; eski sürüm ve işaretçi değişmedi."""


# ---------------------------------------------------------------- günlük

def gunluk_dosyasi():
    return guvenlik.veri_yolu("YZ_GUNCELLEME_LOG", "guncelleme.log")


def gunluk_yaz(satir):
    """guncelleme.log dosyasına tek satır ekler (yazılamıyorsa hata.log'a not düşer, işlemi durdurmaz)."""
    try:
        yol = gunluk_dosyasi()
        yol.parent.mkdir(parents=True, exist_ok=True)
        if yol.exists() and yol.stat().st_size > GUNLUK_SINIRI:
            os.replace(yol, yol.with_name(yol.name + ".eski"))
        with open(yol, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {satir}\n")
    except OSError as h:
        guvenlik.hata_yaz(f"guncelleme.log yazılamadı: {h}")


def gunluk_son(adet=20):
    try:
        satirlar = gunluk_dosyasi().read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return satirlar[-adet:]


# ---------------------------------------------------------------- yol denetimleri

def reparse_mi(yol):
    """Yol bir symlink ya da junction (Windows reparse point) mi? Yoksa False."""
    try:
        st = os.lstat(yol)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def _altinda_mi(yol, taban):
    """`yol`, `taban` klasörünün İÇİNDE mi (ikisi de gerçek yol olmalı; eşitlik sayılmaz)."""
    try:
        return os.path.commonpath([os.path.normcase(yol), os.path.normcase(taban)]) == os.path.normcase(taban) \
            and os.path.normcase(yol) != os.path.normcase(taban)
    except ValueError:  # farklı sürücüler
        return False


def yol_parcalari(yol):
    """Manifest yolunu güvenli parçalara ayırır; mutlak, sürücülü, `..`/`.` içeren ya da boş yol için ValueError."""
    if not isinstance(yol, str) or not yol.strip():
        raise ValueError("boş yol")
    duz = yol.replace("\\", "/")
    if duz.startswith("/") or ":" in duz or "\0" in duz:
        raise ValueError(f"mutlak ya da sürücülü yol: {yol}")
    parcalar = duz.split("/")
    for p in parcalar:
        if p in ("", ".", "..") or p != p.strip() or p.endswith("."):
            raise ValueError(f"geçersiz yol parçası: {yol}")
    return tuple(parcalar)


def korunan_mu(parcalar):
    """Yolun herhangi bir parçası KORUNAN_KALIPLAR ile eşleşiyor mu (büyük/küçük harf duyarsız)?"""
    for p in parcalar:
        ad = p.lower()
        if any(fnmatch.fnmatchcase(ad, k.lower()) for k in KORUNAN_KALIPLAR):
            return True
    return False


def _zincirde_reparse(taban, parcalar):
    """taban/p1, taban/p1/p2, ... içinde ilk reparse point'i döndürür (yoksa None)."""
    yol = Path(taban)
    for p in parcalar:
        yol = yol / p
        if reparse_mi(yol):
            return yol
    return None


def _veri_klasorunde_mi(gercek):
    try:
        veri = os.path.realpath(guvenlik.veri_klasoru())
    except OSError:
        return False
    return _altinda_mi(gercek, veri) or os.path.normcase(gercek) == os.path.normcase(veri)


def sha256(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def gelistirme_kurulumu_mu(kok):
    """`.git` bulunan kök geliştirme kurulumudur: kökteki dosyalar asla silinmez."""
    return os.path.lexists(Path(kok) / ".git")


# ---------------------------------------------------------------- manifest

def _uygulama_dosyalari(kok):
    """Manifeste girecek göreli yollar (yalnızca uygulama dosyaları; veri, testler, .git, önbellek hariç)."""
    kok = Path(kok)
    for oge in sorted(kok.iterdir(), key=lambda p: p.name.lower()):
        if oge.is_file() and not reparse_mi(oge) and oge.suffix.lower() in KOK_UZANTILARI \
                and oge.name not in (MANIFEST, ISARETCI) and not korunan_mu((oge.name,)):
            yield oge.name
    for klasor in UYGULAMA_KLASORLERI:
        taban = kok / klasor
        if not taban.is_dir() or reparse_mi(taban):
            continue
        for ust, klasorler, dosyalar in os.walk(taban):
            klasorler[:] = sorted(k for k in klasorler
                                  if k not in MANIFEST_DISI_KLASORLER and not korunan_mu((k,))
                                  and not reparse_mi(Path(ust) / k))
            for ad in sorted(dosyalar):
                tam = Path(ust) / ad
                goreli = tam.relative_to(kok).as_posix()
                if ad.endswith((".pyc", ".pyo")) or reparse_mi(tam) or korunan_mu(PurePosixPath(goreli).parts):
                    continue
                yield goreli


def manifest_uret(kok, surum=None):
    """`kok` klasöründeki uygulama dosyalarının manifestini (sözlük) üretir."""
    if surum is None:
        import surum as _surum
        surum = _surum.SURUM
    if not SEMVER.match(str(surum)):
        raise ValueError(f"Sürüm semver değil: {surum}")
    kok = Path(kok)
    dosyalar = []
    for goreli in _uygulama_dosyalari(kok):
        tam = kok / goreli
        dosyalar.append({"yol": goreli, "sha256": sha256(tam), "boyut": tam.stat().st_size})
    return {"surum": surum, "olusturma": datetime.now().isoformat(timespec="seconds"), "dosyalar": dosyalar}


def manifest_yaz(klasor, manifest):
    guvenlik.json_yaz(Path(klasor) / MANIFEST, manifest)


def manifest_oku(klasor):
    """Klasörün manifestini okur ve şemasını denetler; sorun varsa ValueError."""
    yol = Path(klasor) / MANIFEST
    if reparse_mi(yol):
        raise ValueError("manifest.json bir bağlantı (reparse point)")
    try:
        veri = json.loads(yol.read_text("utf-8"))
    except FileNotFoundError:
        raise ValueError("manifest.json yok") from None
    except (OSError, ValueError) as h:
        raise ValueError(f"manifest.json okunamadı: {h}") from None
    if not isinstance(veri, dict) or not SEMVER.match(str(veri.get("surum", ""))):
        raise ValueError("manifestte geçerli semver 'surum' yok")
    dosyalar = veri.get("dosyalar")
    if not isinstance(dosyalar, list):
        raise ValueError("manifestte 'dosyalar' listesi yok")
    gorulen = set()
    for g in dosyalar:
        if not isinstance(g, dict) or not isinstance(g.get("sha256"), str) or not isinstance(g.get("boyut"), int):
            raise ValueError("manifest girdisi eksik (yol, sha256, boyut)")
        parcalar = yol_parcalari(g.get("yol"))
        if korunan_mu(parcalar):
            raise ValueError(f"manifest korunan bir yolu içeriyor: {g['yol']}")
        if parcalar[-1].lower() == MANIFEST and len(parcalar) == 1:
            raise ValueError("manifest kendini listeleyemez")
        anahtar = "/".join(parcalar).lower()
        if anahtar in gorulen:
            raise ValueError(f"manifestte yinelenen yol: {g['yol']}")
        gorulen.add(anahtar)
    return veri


# ---------------------------------------------------------------- doğrulama

def kaynak_dogrula(klasor):
    """Sürüm klasörünü manifestine göre doğrular: her dosya var, boyut ve sha256 eşleşiyor, fazla dosya yok,
    hiçbir yerde symlink/junction yok. {"gecerli": bool, "surum": str|None, "sorunlar": [...]} döndürür."""
    klasor = Path(klasor)
    sorunlar = []
    try:
        manifest = manifest_oku(klasor)
    except ValueError as h:
        return {"gecerli": False, "surum": None, "sorunlar": [str(h)]}
    if reparse_mi(klasor):
        return {"gecerli": False, "surum": manifest["surum"], "sorunlar": ["sürüm klasörü bir bağlantı"]}
    beklenen = {}
    for g in manifest["dosyalar"]:
        parcalar = yol_parcalari(g["yol"])
        beklenen["/".join(parcalar).lower()] = g
        tam = klasor.joinpath(*parcalar)
        baglanti = _zincirde_reparse(klasor, parcalar)
        if baglanti is not None:
            sorunlar.append(f"bağlantı (reparse point): {g['yol']}")
            continue
        if not tam.is_file():
            sorunlar.append(f"eksik dosya: {g['yol']}")
            continue
        if tam.stat().st_size != g["boyut"] or sha256(tam) != g["sha256"].lower():
            sorunlar.append(f"içerik uyuşmuyor: {g['yol']}")
    for ust, klasorler, dosyalar in os.walk(klasor):
        for k in list(klasorler):
            if reparse_mi(Path(ust) / k):
                sorunlar.append(f"bağlantı (reparse point): {(Path(ust) / k).relative_to(klasor).as_posix()}")
                klasorler.remove(k)
            elif k == "__pycache__":
                klasorler.remove(k)  # Python'un kendi ürettiği önbellek: fazla dosya sayılmaz
        for ad in dosyalar:
            goreli = (Path(ust) / ad).relative_to(klasor).as_posix()
            if goreli.lower() == MANIFEST:
                continue
            if goreli.lower() not in beklenen:
                sorunlar.append(f"manifestte olmayan fazla dosya: {goreli}")
    return {"gecerli": not sorunlar, "surum": manifest["surum"], "sorunlar": sorunlar}


def duman_testi(klasor, moduller=DUMAN_MODULLERI, zaman_asimi=DUMAN_ZAMAN_ASIMI):
    """Ayrı bir süreçte yeni sürümün ana modüllerini içe aktarır (önbellek yazmadan). (başarılı mı, ileti)"""
    klasor = os.path.realpath(klasor)
    kod = ("import sys; sys.path.insert(0, sys.argv[1]); import importlib; "
           "[importlib.import_module(m) for m in sys.argv[2:]]; print('tamam')")
    ortam = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    ortam.pop("PYTHONPATH", None)
    try:
        sonuc = subprocess.run([sys.executable, "-B", "-c", kod, klasor, *moduller], cwd=klasor, env=ortam,
                               capture_output=True, timeout=zaman_asimi, stdin=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as h:
        return False, f"duman testi çalıştırılamadı: {h}"
    if sonuc.returncode != 0:
        hata = sonuc.stderr.decode("utf-8", errors="replace").strip().splitlines()
        return False, "duman testi başarısız: " + (hata[-1] if hata else f"çıkış kodu {sonuc.returncode}")
    return True, "duman testi geçti"


# ---------------------------------------------------------------- işaretçi

def isaretci_oku(kurulum_koku):
    """guncel.json geçerliyse {"surum", "yol"} döndürür; yoksa ya da güvenilmezse None."""
    kok = Path(kurulum_koku)
    yol = kok / ISARETCI
    if not yol.is_file() or reparse_mi(yol):
        return None
    try:
        veri = json.loads(yol.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(veri, dict):
        return None
    surum = str(veri.get("surum", ""))
    if not SEMVER.match(surum) or veri.get("yol") != f"{SURUMLER}/{surum}":
        return None
    return {"surum": surum, "yol": veri["yol"]}


def isaretci_yaz(kurulum_koku, surum):
    guvenlik.json_yaz(Path(kurulum_koku) / ISARETCI, {"surum": surum, "yol": f"{SURUMLER}/{surum}"})


def etkin_klasor(kurulum_koku=KOK):
    """Çalıştırılacak klasör: geçerli işaretçinin gösterdiği sürüm, yoksa kök."""
    kok = Path(kurulum_koku)
    isaret = isaretci_oku(kok)
    if isaret:
        hedef = kok / SURUMLER / isaret["surum"]
        if not reparse_mi(kok / SURUMLER) and not reparse_mi(hedef) and (hedef / "masaustu_sunucu.py").is_file():
            return hedef
    return kok


def kurulum_koku_bul(klasor):
    """Çalışan kod `<kok>/surumler/<surum>/` içindeyse <kok>, değilse klasörün kendisi."""
    klasor = Path(klasor).resolve()
    if klasor.parent.name == SURUMLER and SEMVER.match(klasor.name):
        return klasor.parent.parent
    return klasor


# ---------------------------------------------------------------- güncelleme

def _geri_al(hedef, kopyalanan, olusan_klasorler):
    """Yalnızca bu işlemin kopyaladığı dosyaları ve açtığı (boş kalan) klasörleri kaldırır."""
    for dosya in reversed(kopyalanan):
        try:
            if os.path.lexists(dosya) and not reparse_mi(dosya) and Path(dosya).is_file():
                os.unlink(dosya)
        except OSError as h:
            gunluk_yaz(f"GERİ ALMA: silinemedi {dosya}: {h}")
    for k in sorted(olusan_klasorler, key=lambda p: len(Path(p).parts), reverse=True):
        try:
            if not reparse_mi(k) and Path(k).is_dir() and not any(Path(k).iterdir()):
                os.rmdir(k)
        except OSError:
            pass
    gunluk_yaz(f"GERİ ALINDI: {hedef} ({len(kopyalanan)} dosya kaldırıldı)")


def guncelle(kurulum_koku, yeni_surum_klasoru):
    """Yeni sürümü `surumler/<surum>/` içine kurar, doğrular, işaretçiyi değiştirir, eski sürümleri temizler.

    Başarısızlıkta GuncellemeHatasi; eski sürüm ve guncel.json değişmez. Başarıda
    {"surum", "yol", "kopyalandi", "silinen", "atlanan"} döndürür.
    """
    kok = Path(os.path.realpath(kurulum_koku))
    kaynak = Path(yeni_surum_klasoru)
    gunluk_yaz(f"GÜNCELLEME BAŞLADI: kök={kok} kaynak={kaynak}")
    try:
        manifest = manifest_oku(kaynak)
    except ValueError as h:
        gunluk_yaz(f"GÜNCELLEME REDDEDİLDİ: kaynak manifesti geçersiz: {h}")
        raise GuncellemeHatasi(f"Kaynak manifesti geçersiz: {h}") from None
    surum = manifest["surum"]
    surumler = kok / SURUMLER
    if reparse_mi(surumler):
        gunluk_yaz("GÜNCELLEME REDDEDİLDİ: surumler/ bir bağlantı (reparse point)")
        raise GuncellemeHatasi("surumler/ klasörü bir bağlantı; güncelleme yapılmadı.")
    hedef = surumler / surum
    if reparse_mi(hedef):
        gunluk_yaz(f"GÜNCELLEME REDDEDİLDİ: {hedef} bir bağlantı")
        raise GuncellemeHatasi("Hedef sürüm klasörü bir bağlantı; güncelleme yapılmadı.")

    kopyalanan, olusan = [], []
    kopyalandi = False
    if hedef.exists():
        gunluk_yaz(f"Sürüm klasörü zaten var, kopyalama atlandı: {hedef}")
    else:
        kopyalandi = True
        try:
            if not surumler.exists():
                surumler.mkdir(parents=True)
                olusan.append(surumler)
            hedef.mkdir()
            olusan.append(hedef)
            for g in manifest["dosyalar"]:
                parcalar = yol_parcalari(g["yol"])
                kaynak_dosya = kaynak.joinpath(*parcalar)
                if _zincirde_reparse(kaynak, parcalar) is not None or not kaynak_dosya.is_file():
                    raise GuncellemeHatasi(f"Kaynakta dosya yok ya da bağlantı: {g['yol']}")
                hedef_dosya = hedef.joinpath(*parcalar)
                ust = hedef_dosya.parent
                eksik = []
                while not ust.exists():
                    eksik.append(ust)
                    ust = ust.parent
                for k in reversed(eksik):
                    k.mkdir()
                    olusan.append(k)
                kopyalanan.append(hedef_dosya)
                shutil.copy2(kaynak_dosya, hedef_dosya)
            kopyalanan.append(hedef / MANIFEST)
            manifest_yaz(hedef, manifest)
            gunluk_yaz(f"Kopyalandı: {len(manifest['dosyalar'])} dosya -> {hedef}")
        except (OSError, GuncellemeHatasi) as h:
            _geri_al(hedef, kopyalanan, olusan)
            gunluk_yaz(f"GÜNCELLEME BAŞARISIZ (kopyalama): {h}")
            raise GuncellemeHatasi(f"Kopyalama başarısız: {h}") from None

    dogrulama = kaynak_dogrula(hedef)
    if not dogrulama["gecerli"] or dogrulama["surum"] != surum:
        if kopyalandi:
            _geri_al(hedef, kopyalanan, olusan)
        sorun = "; ".join(dogrulama["sorunlar"][:5]) or "sürüm uyuşmuyor"
        gunluk_yaz(f"GÜNCELLEME BAŞARISIZ (doğrulama): {sorun}")
        raise GuncellemeHatasi(f"Yeni sürüm doğrulanamadı: {sorun}")
    gunluk_yaz(f"Doğrulandı: {surum}")
    tamam, ileti = duman_testi(hedef)
    if not tamam:
        if kopyalandi:
            _geri_al(hedef, kopyalanan, olusan)
        gunluk_yaz(f"GÜNCELLEME BAŞARISIZ (duman testi): {ileti}")
        raise GuncellemeHatasi(f"Yeni sürüm duman testinden geçemedi: {ileti}")
    gunluk_yaz(f"Duman testi geçti: {surum}")

    try:
        isaretci_yaz(kok, surum)
    except OSError as h:
        if kopyalandi:
            _geri_al(hedef, kopyalanan, olusan)
        gunluk_yaz(f"GÜNCELLEME BAŞARISIZ (işaretçi yazılamadı): {h}")
        raise GuncellemeHatasi(f"guncel.json yazılamadı: {h}") from None
    gunluk_yaz(f"İşaretçi güncellendi: guncel.json -> {SURUMLER}/{surum}")

    temizlik = eski_surumleri_temizle(kok, korunan=surum)
    gunluk_yaz(f"GÜNCELLEME TAMAMLANDI: {surum} (silinen {len(temizlik['silinen'])}, "
               f"atlanan {len(temizlik['atlanan'])})")
    return {"surum": surum, "yol": str(hedef), "kopyalandi": kopyalandi,
            "silinen": temizlik["silinen"], "atlanan": temizlik["atlanan"]}


# ---------------------------------------------------------------- temizlik

def _sil(yol, sonuc, neden="manifest"):
    try:
        os.unlink(yol)
    except OSError as h:
        sonuc["atlanan"].append({"yol": str(yol), "neden": f"silinemedi: {h}"})
        gunluk_yaz(f"ATLANDI (silinemedi): {yol}: {h}")
        return False
    sonuc["silinen"].append(str(yol))
    gunluk_yaz(f"SİLİNDİ ({neden}): {yol}")
    return True


def _atla(sonuc, yol, neden):
    sonuc["atlanan"].append({"yol": str(yol), "neden": neden})
    gunluk_yaz(f"ATLANDI ({neden}): {yol}")


def _bos_klasorleri_kaldir(klasor, sonuc):
    """Sürüm klasörünün içindeki boş klasörleri (en derinden) ve boş kalırsa klasörün kendisini kaldırır.
    Bağlantılara (reparse point) girilmez ve dokunulmaz."""
    klasorler = []
    for ust, alt, _dosyalar in os.walk(klasor):
        for k in list(alt):
            if reparse_mi(Path(ust) / k):
                alt.remove(k)
            else:
                klasorler.append(Path(ust) / k)
    for k in sorted(klasorler, key=lambda p: len(p.parts), reverse=True) + [Path(klasor)]:
        try:
            if not reparse_mi(k) and k.is_dir() and not any(k.iterdir()):
                os.rmdir(k)
                gunluk_yaz(f"Boş klasör kaldırıldı: {k}")
        except OSError:
            pass


def _surum_klasorunu_temizle(d, sonuc):
    try:
        manifest = manifest_oku(d)
    except ValueError as h:
        _atla(sonuc, d, f"manifest geçersiz ya da yok, dokunulmadı: {h}")
        return
    if manifest["surum"] != d.name:
        _atla(sonuc, d, f"manifest sürümü ({manifest['surum']}) klasör adıyla uyuşmuyor, dokunulmadı")
        return
    d_gercek = os.path.realpath(d)
    hepsi = True
    for g in manifest["dosyalar"]:
        parcalar = yol_parcalari(g["yol"])  # manifest_oku zaten doğruladı
        tam = d.joinpath(*parcalar)
        baglanti = _zincirde_reparse(d, parcalar)
        if baglanti is not None:
            _atla(sonuc, baglanti, "bağlantı (symlink/junction), izlenmedi")
            hepsi = False
            continue
        if not os.path.lexists(tam):
            continue
        gercek = os.path.realpath(tam)
        if not _altinda_mi(gercek, d_gercek) or _veri_klasorunde_mi(gercek):
            _atla(sonuc, tam, "gerçek yol sürüm klasörünün dışında")
            hepsi = False
            continue
        if not os.path.isfile(tam):
            _atla(sonuc, tam, "dosya değil")
            hepsi = False
            continue
        if not _sil(tam, sonuc):
            hepsi = False
            continue
        if parcalar[-1].lower().endswith(".py"):  # bu dosyanın Python önbelleği (uygulamanın kendi ürettiği)
            onbellek = tam.parent / "__pycache__"
            if onbellek.is_dir() and not reparse_mi(onbellek):
                kok_ad = tam.stem.lower() + "."
                for pyc in onbellek.iterdir():
                    ad = pyc.name.lower()
                    if ad.startswith(kok_ad) and ad.endswith(".pyc") and ad.count(".") == 2 \
                            and not reparse_mi(pyc) and pyc.is_file():
                        _sil(pyc, sonuc, "önbellek")
    if hepsi:
        _sil(d / MANIFEST, sonuc)
    else:
        gunluk_yaz(f"{d}: bazı dosyalar silinemedi; manifest.json sonraki temizlik için bırakıldı")
    _bos_klasorleri_kaldir(d, sonuc)


def eski_surumleri_temizle(kurulum_koku, korunan=None):
    """`surumler/` altındaki korunan dışı sürümlerden yalnızca kendi manifestlerindeki dosyaları siler.

    `korunan` ve guncel.json'un gösterdiği sürüme dokunulmaz. {"silinen": [...], "atlanan": [{yol, neden}]}.
    """
    kok = Path(os.path.realpath(kurulum_koku))
    sonuc = {"silinen": [], "atlanan": []}
    gunluk_yaz(f"TEMİZLİK BAŞLADI: kök={kok} korunan={korunan}"
               + (" (geliştirme kurulumu: kökteki dosyalara dokunulmaz)" if gelistirme_kurulumu_mu(kok) else ""))
    surumler = kok / SURUMLER
    if not os.path.lexists(surumler):
        gunluk_yaz("TEMİZLİK: surumler/ yok, yapılacak bir şey yok")
        return sonuc
    if reparse_mi(surumler) or not surumler.is_dir():
        _atla(sonuc, surumler, "surumler/ bir bağlantı ya da klasör değil")
        return sonuc
    if not _altinda_mi(os.path.realpath(surumler), str(kok)):
        _atla(sonuc, surumler, "surumler/ gerçek yolu kurulum kökünün dışında")
        return sonuc
    koru = {korunan} if korunan else set()
    isaret = isaretci_oku(kok)
    if isaret:
        koru.add(isaret["surum"])
    for d in sorted(surumler.iterdir(), key=lambda p: p.name):
        if d.name in koru:
            continue
        if reparse_mi(d):
            _atla(sonuc, d, "bağlantı (symlink/junction), izlenmedi")
            continue
        if not d.is_dir():
            continue
        if not SEMVER.match(d.name):
            _atla(sonuc, d, "sürüm klasörü adı semver değil, dokunulmadı")
            continue
        if os.path.lexists(d / ".git"):
            _atla(sonuc, d, "geliştirme kurulumu (.git), dokunulmadı")
            continue
        if korunan_mu((d.name,)):
            _atla(sonuc, d, "korunan ad")
            continue
        _surum_klasorunu_temizle(d, sonuc)
    gunluk_yaz(f"TEMİZLİK BİTTİ: silinen {len(sonuc['silinen'])}, atlanan {len(sonuc['atlanan'])}")
    return sonuc


# ---------------------------------------------------------------- durum

def durum(calisan_klasor=KOK):
    """Uygulama içi gösterim için: çalışan sürüm, kurulum düzeni, işaretçi, günlüğün son 20 satırı."""
    import surum as _surum
    kok = kurulum_koku_bul(calisan_klasor)
    surumler = kok / SURUMLER
    kurulu = []
    if surumler.is_dir() and not reparse_mi(surumler):
        kurulu = sorted(d.name for d in surumler.iterdir() if d.is_dir() and SEMVER.match(d.name))
    return {"surum": _surum.SURUM, "calisan_klasor": str(Path(calisan_klasor).resolve()), "kurulum_koku": str(kok),
            "gelistirme_kurulumu": gelistirme_kurulumu_mu(kok), "guncel": isaretci_oku(kok),
            "kurulu_surumler": kurulu, "gunluk": gunluk_son(20)}


def _baslat(ek_argumanlar):
    hedef = etkin_klasor(KOK)
    yorumlayici = Path(sys.executable)
    pencere_siz = yorumlayici.with_name("pythonw.exe")
    if pencere_siz.is_file():
        yorumlayici = pencere_siz
    gunluk_yaz(f"Başlatılıyor: {hedef}")
    subprocess.Popen([str(yorumlayici), "masaustu_sunucu.py", *ek_argumanlar], cwd=str(hedef),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0), close_fds=True)


def main(argumanlar=None):
    a = list(sys.argv[1:] if argumanlar is None else argumanlar)
    if not a or a[0] in ("-h", "--yardim", "--help"):
        print(__doc__)
        return 0
    komut = a[0]
    if komut == "--yol":
        print(etkin_klasor(KOK))
        return 0
    if komut == "--baslat":
        _baslat(a[1:])
        return 0
    if komut == "--durum":
        print(json.dumps(durum(), ensure_ascii=False, indent=2))
        return 0
    if komut == "--temizle":
        print(json.dumps(eski_surumleri_temizle(KOK, korunan=(isaretci_oku(KOK) or {}).get("surum")),
                         ensure_ascii=False, indent=2))
        return 0
    if komut == "--guncelle" and len(a) == 2:
        try:
            print(json.dumps(guncelle(KOK, a[1]), ensure_ascii=False, indent=2))
        except GuncellemeHatasi as h:
            print(f"Güncelleme yapılmadı, eski sürüm yerinde: {h}")
            return 1
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
