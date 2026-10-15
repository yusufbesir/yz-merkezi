"""Yapay zeka komut satırı motorlarının ortak tabanı.

Her motor (Claude Code, Codex CLI, Gemini CLI) kullanıcının KENDİ hesabıyla, arka planda ve pencere açmadan
(Windows'ta CREATE_NO_WINDOW) bir alt süreç olarak çalıştırılır; çıktısı satır satır okunup olay sözlükleri
hâlinde akıtılır:

    {"tur": "baslangic", "oturum": id|None}
    {"tur": "durum", "metin": "düşünüyor…"}
    {"tur": "parca", "metin": str}
    {"tur": "bitti", "oturum": id|None, "metin": tam_yanit, "model": str|None, "sure": float}
    {"tur": "hata", "mesaj": Türkçe açıklama}          (iptalde ayrıca "iptal": True)

- Yürütülebilir dosya yolu `YZ_MOTOR_<ID>_EXE` ortam değişkeniyle değiştirilebilir (testler sahte betik verir;
  `.py` uzantılı yol bu Python yorumlayıcısıyla, `.js` uzantılı yol node ile çalıştırılır).
- İstem komut satırına değil standart girdiye yazılır (uzun geçmiş ve özel karakterler güvenle geçer).
- Zaman aşımı: ilk çıktı satırı için 60 sn, toplam 600 sn. `iptal` (threading.Event) kurulunca süreç ağacı durdurulur.
- Çalışma klasörü varsayılanı `%LOCALAPPDATA%\\YZMerkezi\\calisma` (guvenlik.veri_yolu; `YZ_MOTOR_CALISMA` ile değişir).

Yalnızca standart kütüphane.
"""
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

_KOK = Path(__file__).resolve().parent.parent
if str(_KOK) not in sys.path:
    sys.path.insert(0, str(_KOK))
import guvenlik  # noqa: E402

ILK_BAYT_ZAMAN_ASIMI = 60     # sn: ilk çıktı satırı gelmezse süreç durdurulur
TOPLAM_ZAMAN_ASIMI = 600      # sn: bir yanıtın en uzun süresi
ONBELLEK_SURESI = 60          # sn: hazir_mi() sonucunun önbellekte kalma süresi
YARDIMCI_ZAMAN_ASIMI = 20     # sn: --version / giriş durumu komutları
STDERR_SINIRI = 20_000        # karakter: toplanan hata çıktısının üst sınırı
STDERR_OZETI = 300            # karakter: hata mesajına eklenen kısım
DUSUNUYOR = "düşünüyor…"


class MotorHatasi(Exception):
    """Motorla ilgili, kullanıcıya Türkçe gösterilebilecek hata."""


def pencere_bayraklari():
    """Windows'ta alt süreç için konsol penceresi açılmasın."""
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def calisma_klasoru_varsayilan():
    """Motorların çalışma klasörü: %LOCALAPPDATA%\\YZMerkezi\\calisma (yoksa oluşturulur)."""
    yol = guvenlik.veri_yolu("YZ_MOTOR_CALISMA", "calisma")
    yol.mkdir(parents=True, exist_ok=True)
    return yol


def sureci_durdur(surec):
    """Süreci (Windows'ta alt süreçleriyle birlikte) durdurur; hata fırlatmaz."""
    if surec is None or surec.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(surec.pid)], capture_output=True,
                           timeout=10, **pencere_bayraklari())
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        if surec.poll() is None:
            surec.terminate()
            surec.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        try:
            surec.kill()
        except OSError:
            pass


class Motor:
    """Bir yapay zeka komut satırı motoru.

    Alt sınıflar `_exe_bul`, `_giris_denetle`, `_komut` ve `_satir_isle` yöntemlerini doldurur.
    """

    id = ""
    ad = ""
    renk = ""
    VARSAYILAN_MODELLER = []   # [{"id","ad","sinif"}]; CLI'dan alınamazsa kullanılır
    GIRIS_YARDIMI = ""        # giriş yoksa gösterilecek Türkçe yönerge

    def __init__(self):
        self.ilk_bayt_zaman_asimi = ILK_BAYT_ZAMAN_ASIMI
        self.toplam_zaman_asimi = TOPLAM_ZAMAN_ASIMI
        self._onbellek = None      # (zaman, sonuç)
        self._kilit = threading.Lock()

    # ------------------------------------------------------------ yol bulma

    def ortam_degiskeni(self):
        return f"YZ_MOTOR_{self.id.upper()}_EXE"

    def exe(self):
        """Yürütülebilir dosyanın yolu (str) ya da bulunamazsa None."""
        ozel = os.environ.get(self.ortam_degiskeni())
        if ozel:
            return ozel if Path(ozel).is_file() else None
        yol = self._exe_bul()
        return str(yol) if yol and Path(yol).is_file() else None

    def _exe_bul(self):
        return shutil.which(self.id)

    def komut_onu(self):
        """Komutun başı (liste). `.py` → bu Python, `.js` → node. Bulunamazsa MotorHatasi."""
        yol = self.exe()
        if not yol:
            raise MotorHatasi(f"{self.ad} bulunamadı. {self.kurulum_yardimi()}".strip())
        uzanti = Path(yol).suffix.lower()
        if uzanti == ".py":
            return [sys.executable, yol]
        if uzanti == ".js":
            node = self._node_bul(yol)
            if not node:
                raise MotorHatasi("Node.js bulunamadı (node.exe).")
            return [node, yol]
        if uzanti in (".cmd", ".bat"):
            # Toplu iş dosyalarına (cmd.exe) kullanıcı metni geçirilmez; motor kendi .js girişini vermelidir.
            raise MotorHatasi(f"{self.ad} için .cmd/.bat yolu kullanılamaz: {yol}")
        return [yol]

    @staticmethod
    def _node_bul(betik):
        for ata in Path(betik).resolve().parents:
            aday = ata / ("node.exe" if os.name == "nt" else "node")
            if aday.is_file():
                return str(aday)
        return shutil.which("node")

    def kurulum_yardimi(self):
        return ""

    # ------------------------------------------------------------ alt süreç yardımcıları

    def _ortam(self):
        """Alt süreç ortamı (alt sınıflar ekleme/çıkarma yapabilir)."""
        return dict(os.environ)

    def _yardimci_calistir(self, argumanlar, zaman_asimi=YARDIMCI_ZAMAN_ASIMI):
        """Kısa bir yardımcı komut çalıştırır: (çıkış kodu, stdout, stderr). Hata/zaman aşımında (None, "", sebep)."""
        try:
            sonuc = subprocess.run(self.komut_onu() + list(argumanlar), capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=zaman_asimi,
                                   stdin=subprocess.DEVNULL, env=self._ortam(),
                                   cwd=str(calisma_klasoru_varsayilan()), **pencere_bayraklari())
        except subprocess.TimeoutExpired:
            return None, "", "zaman aşımı"
        except (OSError, MotorHatasi) as hata:
            return None, "", str(hata)
        return sonuc.returncode, sonuc.stdout or "", sonuc.stderr or ""

    def surum(self):
        kod, cikti, _ = self._yardimci_calistir(["--version"])
        if kod != 0:
            return None
        satir = (cikti.strip().splitlines() or [""])[0].strip()
        return satir or None

    # ------------------------------------------------------------ hazırlık

    def hazir_mi(self, yenile=False):
        """{"hazir": bool, "sebep": Türkçe, "surum": str|None, "giris": bool|None}; 60 sn önbellekli."""
        with self._kilit:
            if not yenile and self._onbellek and time.monotonic() - self._onbellek[0] < ONBELLEK_SURESI:
                return dict(self._onbellek[1])
        sonuc = self._hazirlik_hesapla()
        with self._kilit:
            self._onbellek = (time.monotonic(), sonuc)
        return dict(sonuc)

    def _hazirlik_hesapla(self):
        if not self.exe():
            return {"hazir": False, "sebep": f"{self.ad} kurulu değil. {self.kurulum_yardimi()}".strip(),
                    "surum": None, "giris": None}
        surum = self.surum()
        if surum is None:
            return {"hazir": False, "sebep": f"{self.ad} çalıştırılamadı (--version başarısız).",
                    "surum": None, "giris": None}
        giris = self._giris_denetle()
        if giris is False:
            return {"hazir": False, "sebep": self.GIRIS_YARDIMI, "surum": surum, "giris": False}
        sebep = "Hazır." if giris else "Hazır (giriş durumu doğrulanamadı)."
        return {"hazir": True, "sebep": sebep, "surum": surum, "giris": giris}

    def _giris_denetle(self):
        """True/False ya da bilinmiyorsa None."""
        return None

    def modeller(self):
        """[{"id","ad","sinif": "hizli"|"dengeli"|"guclu"}]."""
        return [dict(m) for m in self.VARSAYILAN_MODELLER]

    # ------------------------------------------------------------ soru sorma

    def _komut(self, istem, oturum, model, sistem):
        """(argüman listesi — komut önü hariç, standart girdi metni) döndürür."""
        raise NotImplementedError

    def _satir_isle(self, veri, durum):
        """Ayrıştırılmış bir JSON olayını işler; olay sözlükleri listesi döndürür.

        `durum` sözlüğü: oturum, model, parcalar (liste), tam_metin (None|str), bitti (bool), hata (None|str);
        isteğe bağlı `son_hata`: yalnızca süreç bitişsiz sonlanırsa gösterilecek son uyarı.
        Alt sınıf `{"tur": "baslangic"}`, `{"tur": "parca", ...}`, `{"tur": "durum", ...}` döndürebilir;
        bitiş ve hata `durum` üzerinden bildirilir.
        """
        raise NotImplementedError

    @staticmethod
    def _sistemli_istem(istem, sistem):
        """Sistem istemi bayrağı olmayan motorlar için talimatı istemin başına ekler."""
        if not sistem:
            return istem
        return f"[Talimat]\n{sistem}\n[/Talimat]\n\n{istem}"

    def sor(self, istem, *, oturum=None, model=None, sistem=None, calisma_klasoru=None, iptal=None):
        """İstemi motora gönderir; olay sözlükleri üreten bir generator döndürür (bkz. modül belgesi)."""
        baslama = time.monotonic()
        try:
            on = self.komut_onu()
            argumanlar, girdi = self._komut(str(istem or ""), oturum, model, sistem)
            klasor = Path(calisma_klasoru) if calisma_klasoru else calisma_klasoru_varsayilan()
            klasor.mkdir(parents=True, exist_ok=True)
            surec = subprocess.Popen(on + argumanlar, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                     cwd=str(klasor), env=self._ortam(), **pencere_bayraklari())
        except (MotorHatasi, OSError, ValueError) as hata:
            yield {"tur": "hata", "mesaj": f"{self.ad} başlatılamadı: {hata}"}
            return

        kuyruk = queue.Queue()
        hata_parcalari = []

        def girdi_yaz():
            try:
                surec.stdin.write(girdi or "")
                surec.stdin.close()
            except (OSError, ValueError):
                pass

        def cikti_oku():
            try:
                for satir in iter(surec.stdout.readline, ""):
                    kuyruk.put(satir)
            except (OSError, ValueError):
                pass
            kuyruk.put(None)

        def hata_oku():
            toplam = 0
            try:
                for satir in iter(surec.stderr.readline, ""):
                    if toplam < STDERR_SINIRI:
                        hata_parcalari.append(satir)
                        toplam += len(satir)
            except (OSError, ValueError):
                pass

        for hedef in (girdi_yaz, cikti_oku, hata_oku):
            threading.Thread(target=hedef, daemon=True).start()

        durum = {"oturum": oturum, "model": model, "parcalar": [], "tam_metin": None, "bitti": False,
                 "hata": None}
        baslangic_gitti = False
        ilk_satir_geldi = False

        def baslangic():
            return {"tur": "baslangic", "oturum": durum["oturum"]}

        try:
            yield {"tur": "durum", "metin": DUSUNUYOR}
            son_durum = DUSUNUYOR
            while True:
                if iptal is not None and iptal.is_set():
                    sureci_durdur(surec)
                    yield {"tur": "hata", "mesaj": "İptal edildi.", "iptal": True}
                    return
                gecen = time.monotonic() - baslama
                if not ilk_satir_geldi and gecen > self.ilk_bayt_zaman_asimi:
                    sureci_durdur(surec)
                    yield {"tur": "hata", "mesaj": f"{self.ad} {self.ilk_bayt_zaman_asimi:g} sn içinde yanıt "
                                                   f"vermeye başlamadı (zaman aşımı)."}
                    return
                if gecen > self.toplam_zaman_asimi:
                    sureci_durdur(surec)
                    yield {"tur": "hata", "mesaj": f"{self.ad} yanıtı {self.toplam_zaman_asimi:g} sn içinde "
                                                   f"bitmedi (zaman aşımı)."}
                    return
                try:
                    satir = kuyruk.get(timeout=0.1)
                except queue.Empty:
                    continue
                if satir is None:
                    break
                ilk_satir_geldi = True
                satir = satir.strip()
                if not satir:
                    continue
                try:
                    veri = json.loads(satir)
                except ValueError:
                    continue   # JSON olmayan satırlar (uyarılar vb.) atlanır
                if not isinstance(veri, dict):
                    continue
                for olay in self._satir_isle(veri, durum) or []:
                    tur = olay.get("tur")
                    if tur == "baslangic":
                        if not baslangic_gitti:
                            baslangic_gitti = True
                            yield baslangic()
                    elif tur == "durum":
                        if olay.get("metin") != son_durum:
                            son_durum = olay.get("metin")
                            yield olay
                    elif tur == "parca" and olay.get("metin"):
                        if not baslangic_gitti:
                            baslangic_gitti = True
                            yield baslangic()
                        son_durum = None
                        yield olay
                if durum["hata"] or durum["bitti"]:
                    break

            # Süreç bitti ya da motor bitiş/hata bildirdi
            try:
                surec.wait(timeout=10)
            except subprocess.TimeoutExpired:
                sureci_durdur(surec)
            if durum["hata"]:
                yield {"tur": "hata", "mesaj": f"{self.ad}: {durum['hata']}"}
                return
            if not durum["bitti"] and durum.get("son_hata"):
                yield {"tur": "hata", "mesaj": f"{self.ad}: {durum['son_hata']}"}
                return
            if not durum["bitti"]:
                kod = surec.returncode
                time.sleep(0.05)   # stderr okuyucusu son satırları toplasın
                ozet = "".join(hata_parcalari).strip()[:STDERR_OZETI]
                yield {"tur": "hata", "mesaj": self._hata_yorumla(kod, ozet)}
                return
            if not baslangic_gitti:
                yield baslangic()
            tam = durum["tam_metin"] if durum["tam_metin"] is not None else "".join(durum["parcalar"])
            yield {"tur": "bitti", "oturum": durum["oturum"], "metin": tam, "model": durum["model"],
                   "sure": round(time.monotonic() - baslama, 3)}
        finally:
            sureci_durdur(surec)
            for akis in (surec.stdout, surec.stderr):
                try:
                    akis.close()
                except (OSError, ValueError):
                    pass

    def _hata_yorumla(self, kod, stderr_ozeti):
        """Yanıt tamamlanmadan biten süreç için Türkçe hata mesajı (alt sınıflar bilinen kodları açıklar)."""
        mesaj = f"{self.ad} yanıtı tamamlamadan sonlandı (çıkış kodu {kod})."
        if stderr_ozeti:
            mesaj += f" Ayrıntı: {stderr_ozeti}"
        return mesaj
