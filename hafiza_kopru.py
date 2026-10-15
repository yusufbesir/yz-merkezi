"""Hafıza OS köprüsü: üç site (ChatGPT, Gemini, Claude) aynı kişisel hafızadan beslensin.

Kasa varsayılan olarak `D:\\YusufII\\HAFIZAM1\\kasa` klasörüdür (`YZ_KASA` ortam değişkeniyle değişir).

OKUMA: kasadaki `araclar/hafiza.py` aracının `context` komutu yerel bir alt süreç olarak çalıştırılır
(`--local`: Mem0 ve ağ kullanılmaz; kasa klasörü çalışma klasörüdür, zaman aşımı 10 sn). Hata ya da
zaman aşımında boş bağlam döner ve Türkçe sebep `durum()` içinde görünür; mesaj yine de gider.
Dönen metindeki sır benzeri satırlar (API anahtarı, parola, şifre ...) atılır.

BÜTÜNLÜK (ilk görüşte güven): `araclar/hafiza.py` ilk kez başarıyla çalıştırıldığında sha256 özeti
`%LOCALAPPDATA%\\YZMerkezi\\hafiza-py.sha256` dosyasına yazılır (yol `YZ_HAFIZA_HASH` ile değişir). Sonraki her
çalıştırmadan önce özet yeniden hesaplanır; değişmişse araç ÇALIŞTIRILMAZ, bağlam boş döner ve `durum()` uyarı
taşır. Denetim ile çalıştırma arasında dosya değiştirilemesin diye dosya TEK SEFERDE bayt olarak okunur; özet bu
baytlardan hesaplanır ve çalıştırılan kod da aynı baytlardır (alt sürece stdin'den verilir, bkz. `_BASLATICI`). Kullanıcı yeni sürümü Ayarlar → Hafıza'dan onaylayınca (`hash_onayla()`) yeni özet kabul edilir.

YAZMA: Hafıza OS'a (katalog, Mem0, aday kuyruğu) doğrudan yazılmaz. Kasadaki `hafiza.py candidate-add`
kuyruğu kaynak dosyada aynen bulunan, doğrulanmış kalıcı gerçekler içindir; sohbet yanıtı özetleri bu
koşulu taşımaz. Bu yüzden kasanın ham giriş klasörüne (`gelen-kutusu/yz-merkezi/YYYY-MM-DD.md`) yalnızca
EKLEME yapılır: var olan dosya ve notlar silinmez, taşınmaz, yeniden adlandırılmaz, üzerine yazılmaz.
Oradaki kayıtları inceleyip kalıcı bilgiye çevirmek kasanın kendi inceleme akışının işidir.

Yalnızca standart kütüphane.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import guvenlik

VARSAYILAN_KASA = r"D:\YusufII\HAFIZAM1\kasa"
HAFIZA_ARACI = Path("araclar") / "hafiza.py"
GELEN_KLASORU = Path("gelen-kutusu") / "yz-merkezi"
ZAMAN_ASIMI = 10          # sn: context çağrısı için üst sınır
SINIR_KAYIT = 5           # --limit
KARAKTER_BUTCESI = 1200   # --char-budget
SORGU_EN_FAZLA = 800      # karakter: komut satırına verilecek soru uzunluğu
BAGLAM_EN_FAZLA = 2500    # karakter: süzmeden sonra mesaja eklenecek bağlamın üst sınırı
SORU_OZETI = 200          # aday kaydında soru özeti
YANIT_OZETI = 600         # aday kaydında yanıt özeti
BASLIK = "Bağlam (kişisel notlarımdan, yalnızca gerekiyorsa kullan):"
AYIRAC = "\n\n---\n"

# Sır benzeri satırlar bağlamdan atılır. Önek desenleri büyük/küçük harfe duyarlıdır (yalancı eşleşmeyi azaltır),
# sözcük desenleri duyarsızdır (Türkçe İ/ı/Ş biçimleri dahil).
_SIR_DUYARLI = re.compile(r"(?<![A-Za-z0-9])sk-|AIza|ghp_|gho_|github_pat_|-----BEGIN|AKIA[0-9A-Z]|xox[bp]-")
_SIR_DUYARSIZ = re.compile(r"parola|[sş][iıİI]fre|password|passwd|api[ _-]?key", re.IGNORECASE)

_KILIT = threading.Lock()      # durum alanları
_YAZMA_KILIDI = threading.Lock()  # gelen kutusuna ekleme
_DURUM = {"son_mod": None, "son_hata": None}
HASH_UYARISI = "hafiza.py değişmiş; Ayarlar → Hafıza'dan yeni sürümü onayla"


# ---------------------------------------------------------------- yardımcılar

def kasa_yolu():
    """Hafıza kasasının klasörü (her çağrıda ortam değişkeninden okunur; testler geçici kasa kullanır)."""
    return Path(os.environ.get("YZ_KASA") or VARSAYILAN_KASA)


def _durumu_yaz(mod=None, hata=None):
    with _KILIT:
        _DURUM["son_mod"] = mod
        _DURUM["son_hata"] = hata


def _hata_yaz(hata):
    with _KILIT:
        _DURUM["son_hata"] = hata


def sir_iceriyor_mu(metin):
    return bool(_SIR_DUYARLI.search(metin or "") or _SIR_DUYARSIZ.search(metin or ""))


def sirli_satirlari_at(metin):
    """Sır benzeri satırları atar; (temiz metin, atılan satır sayısı) döner."""
    kalan, atilan = [], 0
    for satir in str(metin or "").splitlines():
        if sir_iceriyor_mu(satir):
            atilan += 1
        else:
            kalan.append(satir)
    return "\n".join(kalan).strip(), atilan


def durum():
    """/api/hafiza-durum yanıtı: {kasa_var, hafiza_py_var, son_mod, son_hata, kasa, hash_degisti, hash_uyarisi}."""
    kasa = kasa_yolu()
    with _KILIT:
        son = dict(_DURUM)
    degisti = hash_durumu()["degisti"]
    return {"kasa_var": kasa.is_dir(), "hafiza_py_var": (kasa / HAFIZA_ARACI).is_file(),
            "son_mod": son["son_mod"], "son_hata": son["son_hata"], "kasa": str(kasa),
            "hash_degisti": degisti, "hash_uyarisi": HASH_UYARISI if degisti else None}


# ---------------------------------------------------------------- hafiza.py bütünlüğü (ilk görüşte güven)

def hash_dosyasi():
    """Güvenilen hafiza.py özetinin saklandığı dosya (her çağrıda ortamdan okunur; testler geçici yol verir)."""
    return guvenlik.veri_yolu("YZ_HAFIZA_HASH", "hafiza-py.sha256")


def _arac_ozeti(kasa=None):
    """Kasadaki hafiza.py dosyasının sha256 özeti; dosya okunamazsa None."""
    yol = (kasa or kasa_yolu()) / HAFIZA_ARACI
    try:
        return hashlib.sha256(yol.read_bytes()).hexdigest()
    except OSError:
        return None


def _arac_oku(kasa=None):
    """hafiza.py baytlarını tek seferde okur; okunamazsa None. Özet ve çalıştırma AYNI baytlardan yapılır (TOCTOU yok)."""
    yol = (kasa or kasa_yolu()) / HAFIZA_ARACI
    try:
        return yol.read_bytes()
    except OSError:
        return None


def _guvenilen_ozet():
    try:
        deger = hash_dosyasi().read_text("utf-8").strip().lower()
    except OSError:
        return None
    return deger if re.fullmatch(r"[0-9a-f]{64}", deger) else None


def _ozeti_yaz(ozet):
    yol = hash_dosyasi()
    try:
        yol.parent.mkdir(parents=True, exist_ok=True)
        gecici = yol.with_name(yol.name + ".tmp")
        gecici.write_text(ozet + "\n", encoding="utf-8")
        os.replace(gecici, yol)
        return True
    except OSError as h:
        guvenlik.hata_yaz(f"hafiza.py özeti yazılamadı: {h}")
        return False


def hash_durumu():
    """{"guvenilen", "guncel", "degisti"}: kayıtlı özet yoksa (ilk görüş) degisti False."""
    guvenilen, guncel = _guvenilen_ozet(), _arac_ozeti()
    return {"guvenilen": guvenilen, "guncel": guncel,
            "degisti": bool(guvenilen and guncel and guvenilen != guncel)}


def hash_onayla():
    """Kasadaki hafiza.py'nin şimdiki özetini güvenilen özet olarak kaydeder (/api/hafiza-onayla)."""
    ozet = _arac_ozeti()
    if not ozet:
        return {"tamam": False, "sebep": "Kasada araclar/hafiza.py bulunamadı."}
    if not _ozeti_yaz(ozet):
        return {"tamam": False, "sebep": "Özet dosyası yazılamadı."}
    guvenlik.hata_yaz(f"hafiza.py yeni sürümü kullanıcı tarafından onaylandı (sha256 {ozet[:12]}…)")
    _hata_yaz(None)
    return {"tamam": True, "sha256": ozet}


# ---------------------------------------------------------------- okuma

def _python_komutlari():
    """Aracı çalıştırmayı deneyeceğimiz yorumlayıcılar (sırayla): bu süreç, python, py -3."""
    adaylar = []
    if sys.executable:
        adaylar.append([sys.executable])
    bulunan = shutil.which("python")
    if bulunan:
        adaylar.append([bulunan])
    adaylar.append(["py", "-3"])
    tekil = []
    for a in adaylar:
        if a not in tekil:
            tekil.append(a)
    return tekil


def _bos(sebep=None, mod=None):
    return {"metin": "", "mod": mod, "kimlikler": [], "sebep": sebep, "atilan": 0}


def baglam_getir(metin, limit=SINIR_KAYIT, butce=KARAKTER_BUTCESI, zaman_asimi=ZAMAN_ASIMI):
    """Sorunun hafızadaki ilgili bağlamını getirir.

    Döner: {"metin": str, "mod": str|None, "kimlikler": [...], "sebep": str|None, "atilan": int}.
    Hata ya da zaman aşımında "metin" boştur ve "sebep" Türkçe açıklama taşır; asla istisna fırlatmaz.
    """
    sorgu = " ".join(str(metin or "").split())[:SORGU_EN_FAZLA]
    kasa = kasa_yolu()
    if not sorgu:
        return _bos()
    if not kasa.is_dir():
        sonuc = _bos(f"Hafıza kasası bulunamadı: {kasa}")
    elif not (kasa / HAFIZA_ARACI).is_file():
        sonuc = _bos("Hafıza aracı bulunamadı (araclar/hafiza.py).")
    else:
        kod = _arac_oku(kasa)   # tek okuma: özet de, çalıştırılacak kod da bu baytlardır
        ozet = hashlib.sha256(kod).hexdigest() if kod is not None else None
        guvenilen = _guvenilen_ozet()
        if kod is None:
            sonuc = _bos("Hafıza aracı okunamadı (araclar/hafiza.py).")
        elif guvenilen and ozet != guvenilen:
            guvenlik.hata_yaz("hafiza.py özeti güvenilen özetle uyuşmuyor; araç çalıştırılmadı")
            sonuc = _bos(HASH_UYARISI + ".")
        else:
            sonuc = _calistir(kasa, sorgu, limit, butce, zaman_asimi, kod)
            if not guvenilen and ozet and sonuc["sebep"] is None:  # ilk başarılı çalıştırma: bu sürüme güven
                _ozeti_yaz(ozet)
    _durumu_yaz(sonuc["mod"], sonuc["sebep"])
    return sonuc


# Alt süreç başlatıcısı: hafiza.py kodunu stdin'den (denetlenen baytlar) alır; `__file__`, `sys.argv[0]` ve
# `sys.path[0]` dosyadan çalıştırılmış gibi ayarlanır. Dosya diskten yeniden okunmaz.
_BASLATICI = (
    "import sys, os\n"
    "y = sys.argv[1]; sys.argv = sys.argv[1:]\n"
    "k = sys.stdin.buffer.read()\n"
    "sys.path[0] = os.path.dirname(y)\n"
    "exec(compile(k, y, 'exec'), {'__name__': '__main__', '__file__': y, '__builtins__': __builtins__})\n"
)


def _calistir(kasa, sorgu, limit, butce, zaman_asimi, kod):
    import json
    arguman = ["-c", _BASLATICI, str(kasa / HAFIZA_ARACI), "--vault", ".", "context", "--limit", str(limit),
               "--char-budget", str(butce), "--local", "--", sorgu]
    ortam = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    ek = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    islem = None
    for komut in _python_komutlari():
        try:
            islem = subprocess.run(komut + arguman, cwd=str(kasa), capture_output=True, timeout=zaman_asimi,
                                   env=ortam, input=kod, **ek)
            break
        except subprocess.TimeoutExpired:
            return _bos(f"Hafıza aracı {zaman_asimi} saniyede yanıt vermedi; mesaj bağlamsız gitti.")
        except OSError:
            continue  # bu yorumlayıcı başlatılamadı, sıradakini dene
    if islem is None:
        return _bos("Python yorumlayıcısı başlatılamadı; hafıza aracı çalıştırılamadı.")
    cikti = islem.stdout.decode("utf-8", errors="replace").strip()
    veri = None
    for parca in (cikti, cikti[cikti.find("{"):] if "{" in cikti else ""):
        try:
            veri = json.loads(parca)
            break
        except ValueError:
            continue
    if not isinstance(veri, dict):
        return _bos("Hafıza aracının çıktısı okunamadı." if islem.returncode == 0
                    else f"Hafıza aracı hata verdi (çıkış kodu {islem.returncode}).")
    if veri.get("error") or islem.returncode != 0:
        return _bos("Hafıza aracı hata bildirdi; ayrıntı için kasada `python araclar/hafiza.py context` "
                    "komutunu elle çalıştırın.")
    ham = veri.get("text")
    temiz, atilan = sirli_satirlari_at(ham if isinstance(ham, str) else "")
    mod = veri.get("mode")
    kimlikler = [str(k) for k in veri.get("memory_ids") or [] if isinstance(k, (str, int))]
    return {"metin": temiz[:BAGLAM_EN_FAZLA].strip(), "mod": mod if isinstance(mod, str) else None,
            "kimlikler": kimlikler, "sebep": None, "atilan": atilan}


def baglam_kaydi(metin, limit=SINIR_KAYIT, butce=KARAKTER_BUTCESI):
    """Metnin hafıza bağlamı kaydı {"metin", "mod", "karakter", "kimlikler"}; bağlam boşsa ya da hata olursa None."""
    try:
        sonuc = baglam_getir(metin, limit=limit, butce=butce)
    except Exception as hata:  # noqa: BLE001  (hafıza sorunu mesajın gitmesini hiçbir koşulda engellemez)
        _durumu_yaz(None, f"Hafıza bağlamı alınamadı: {type(hata).__name__}")
        return None
    if not sonuc["metin"]:
        return None
    return {"metin": sonuc["metin"], "mod": sonuc["mod"], "karakter": len(sonuc["metin"]),
            "kimlikler": sonuc["kimlikler"]}


def baglami_birlestir(metin, kayit):
    """Bağlam kaydını gönderilecek metnin başına ekler (kayıt yoksa metin aynen döner)."""
    if not kayit or not kayit.get("metin"):
        return metin
    return f"{BASLIK}\n{kayit['metin']}{AYIRAC}{metin}"


def baglam_ekle(metin, limit=SINIR_KAYIT, butce=KARAKTER_BUTCESI):
    """Gönderilecek metnin başına hafıza bağlamını ekler (onay istenmeyen eski otomatik yol).

    Döner: (gönderilecek metin, bağlam kaydı ya da None). Bağlam boşsa metin aynen döner ve hiçbir şey eklenmez.
    Bağlam kaydı: {"metin", "mod", "karakter", "kimlikler"} (sohbet geçmişinde ham mesajdan ayrı tutulur).
    """
    kayit = baglam_kaydi(metin, limit=limit, butce=butce)
    return baglami_birlestir(metin, kayit), kayit


# ---------------------------------------------------------------- yazma (yalnızca ekleme)

def _ozet(metin, sinir):
    """Boşlukları tek satıra indirir, sınırı aşarsa … ile keser; Obsidian bağlantı/etiket sözdizimini etkisizleştirir."""
    t = " ".join(str(metin or "").split())
    if len(t) > sinir:
        t = t[:sinir - 1].rstrip() + "…"
    t = t.replace("[[", "[ [").replace("]]", "] ]")
    return re.sub(r"(^|\s)#(?=\w)", r"\1\\#", t)


def _site_adi(site):
    return re.sub(r"[^\w .-]", "", str(site or ""), flags=re.UNICODE).strip()[:40] or "site"


def aday_yaz(site, soru, yanit, zaman=None):
    """Bir soru-yanıt çiftini kasanın gelen kutusuna aday kayıt olarak EKLER.

    Dosya: <kasa>/gelen-kutusu/yz-merkezi/YYYY-MM-DD.md (yoksa frontmatter ile oluşturulur, varsa sona eklenir).
    Sır benzeri içerik taşıyan ya da aynı kimlikle zaten yazılmış kayıt atlanır. Asla istisna fırlatmaz.
    Döner: {"yazildi": bool, "sebep": str|None, "yol": str|None}.
    """
    try:
        return _aday_yaz(site, soru, yanit, zaman)
    except Exception as hata:  # noqa: BLE001  (yanıt akışını hiçbir koşulda bozmamalı)
        sebep = f"Aday kayıt yazılamadı: {type(hata).__name__}"
        _hata_yaz(sebep)
        return {"yazildi": False, "sebep": sebep, "yol": None}


def _aday_yaz(site, soru, yanit, zaman):
    kasa = kasa_yolu()
    soru, yanit = str(soru or ""), str(yanit or "")
    if not soru.strip() or not yanit.strip():
        return {"yazildi": False, "sebep": "Soru ya da yanıt boş.", "yol": None}
    if not kasa.is_dir():
        return {"yazildi": False, "sebep": f"Hafıza kasası bulunamadı: {kasa}", "yol": None}
    if sir_iceriyor_mu(soru) or sir_iceriyor_mu(yanit):
        return {"yazildi": False, "sebep": "Sır benzeri içerik var; hafızaya yazılmadı.", "yol": None}
    an = zaman or datetime.now()
    ad = _site_adi(site)
    kimlik = hashlib.sha1("\x00".join((ad, soru, yanit)).encode("utf-8")).hexdigest()[:12]
    klasor = kasa / GELEN_KLASORU
    yol = klasor / f"{an.strftime('%Y-%m-%d')}.md"
    kayit = (f"## {an.strftime('%H:%M')} · {ad}\n"
             f"- zaman: {an.isoformat(timespec='seconds')}\n"
             f"- site: {ad}\n"
             f"- soru: {_ozet(soru, SORU_OZETI)}\n"
             f"- yanıt: {_ozet(yanit, YANIT_OZETI)}\n"
             f"- kimlik: {kimlik}\n\n")
    baslangic = (f"---\nkaynak: yz-merkezi\ndurum: aday (incelenmedi)\ntarih: {an.strftime('%Y-%m-%d')}\n---\n\n"
                 f"# Yapay Zeka Merkezi adayları {an.strftime('%Y-%m-%d')}\n\n")
    with _YAZMA_KILIDI:
        klasor.mkdir(parents=True, exist_ok=True)
        if yol.exists():
            if f"- kimlik: {kimlik}\n" in yol.read_text(encoding="utf-8", errors="replace"):
                return {"yazildi": False, "sebep": "Bu kayıt zaten yazılmış.", "yol": str(yol)}
            icerik, kip = kayit, "a"
        else:
            icerik, kip = baslangic + kayit, "x"  # "x": var olan bir dosyanın üzerine asla yazma
        try:
            dosya = open(yol, kip, encoding="utf-8", newline="\n")
        except FileExistsError:  # yarış: arada başkası oluşturdu, sona ekle
            dosya, icerik = open(yol, "a", encoding="utf-8", newline="\n"), kayit
        with dosya:
            dosya.write(icerik)
    return {"yazildi": True, "sebep": None, "yol": str(yol)}
