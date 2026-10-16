"""Chrome DevTools Protocol (CDP) için küçük istemci: Edge'i ağ portu açmadan, anonim BORULAR üzerinden denetler.

Edge `--remote-debugging-pipe --remote-debugging-io-pipes=<okuma>,<yazma>` ile başlatılır: tarayıcı, komutları
kendisine verilen okuma borusundan alır, yanıt ve olayları yazma borusuna yazar. Mesajlar `\\0` ile ayrılmış
JSON metinleridir. Hiçbir TCP portu dinlenmez; bu yüzden aynı bilgisayardaki başka bir süreç (ya da web sayfası)
tarayıcıya bağlanıp çerezleri okuyamaz. Borunun ucu yalnızca uygulamayı başlatan süreçtedir.

- `BoruBaglantisi`: tarayıcı düzeyindeki tek bağlantı. Tek okuyucu thread gelen mesajları toplar, komutlar
  kimlik (id) ile eşlenir, sekme oturumlarına giden komutlar `sessionId` taşır (Target.attachToTarget, flatten).
- `Oturum`: tek bir sekmeye bağlı oturum; degerlendir/git/yazi_ekle/tus/one_getir/kapat sunar.
- `boruyla_baslat`: Edge'i borularla başlatır (yalnızca Windows).

Yalnızca Python standart kütüphanesi kullanılır.
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import collections
import json
import os
import subprocess
import threading
import time

import siteler

EN_BUYUK_YUK = 256 * 1024 * 1024  # bozuk/sonsuz bir mesaj belleği doldurmasın
OLAY_SINIRI = 200                 # saklanan en son olay sayısı
OKUMA_PARCASI = 65536


class CdpHatasi(Exception):
    """Kullanıcıya Türkçe gösterilecek tarayıcı denetimi hatası."""


# ---------------------------------------------------------------- sayfa komutları (ortak)

class _SayfaKomutlari:
    """`komut(yontem, zaman=..., **params)` sağlayan sınıflara sekme düzeyi kolaylık fonksiyonları ekler."""

    def degerlendir(self, js, zaman=30):
        """Sayfada JavaScript çalıştırır (Promise beklenir) ve değeri döndürür."""
        sonuc = self.komut("Runtime.evaluate", zaman=zaman, expression=js, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in sonuc:
            ayrinti = sonuc["exceptionDetails"]
            metin = ayrinti.get("exception", {}).get("description") or ayrinti.get("text", "bilinmeyen hata")
            raise CdpHatasi(f"Sayfadaki JavaScript hata verdi: {metin}")
        return sonuc.get("result", {}).get("value")

    def git(self, url):
        """Sayfayı adrese yönlendirir ve yüklenmesi için kısa bekler."""
        sonuc = self.komut("Page.navigate", url=url)
        if sonuc.get("errorText"):
            raise CdpHatasi(f"Sayfa açılamadı ({url}): {sonuc['errorText']}")
        time.sleep(0.5)
        return sonuc

    def yazi_ekle(self, metin):
        """Odaktaki alana yazı ekler (yapıştırma gibi, tuş basmadan)."""
        self.komut("Input.insertText", text=metin)

    def tus(self, key, code, windowsVirtualKeyCode, text=None):
        """Bir tuşa basıp bırakır. Enter için: tus("Enter", "Enter", 13, "\\r")."""
        ortak = {"key": key, "code": code, "windowsVirtualKeyCode": windowsVirtualKeyCode}
        asagi = dict(ortak, type="keyDown", **({"text": text} if text else {}))
        self.komut("Input.dispatchKeyEvent", **asagi)
        self.komut("Input.dispatchKeyEvent", type="keyUp", **ortak)

    def one_getir(self):
        """Sekmeyi/pencereyi öne getirir."""
        self.komut("Page.bringToFront")


# ---------------------------------------------------------------- boru bağlantısı

class BoruBaglantisi:
    """Tarayıcı düzeyinde CDP bağlantısı: iki anonim boru üzerinden `\\0` ile ayrılmış JSON mesajları.

    okuma_fd: tarayıcının YAZDIĞI borunun bizdeki ucu; yazma_fd: tarayıcının OKUDUĞU borunun bizdeki ucu.
    Birden fazla thread aynı anda komut gönderebilir; yanıtlar kimlik (id) ile eşlenir.
    """

    def __init__(self, okuma_fd, yazma_fd, surec=None):
        self._okuma_fd, self._yazma_fd = okuma_fd, yazma_fd
        self.surec = surec                     # bizim başlattığımız tarayıcı süreci (varsa)
        self._yazma_kilidi = threading.Lock()
        self._kosul = threading.Condition()
        self._sonraki_id = 0
        self._bekleyen = {}                    # id -> None (bekleniyor) | yanıt mesajı
        self._kapali = False
        self._yazma_kapali = False
        self.kapanma_sebebi = ""
        self.olaylar = collections.deque(maxlen=OLAY_SINIRI)
        self.oturumlar = {}                    # sessionId -> targetId (Target.attachedToTarget/detachedFromTarget)
        self._okuyucu = threading.Thread(target=self._oku, name="cdp-boru-okuyucu", daemon=True)
        self._okuyucu.start()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.kapat()

    # ------------------------------------------------------------ durum

    @property
    def kapali(self):
        return self._kapali

    def canli_mi(self):
        """Boru açık ve (biliniyorsa) tarayıcı süreci çalışıyor mu?"""
        if self._kapali:
            return False
        return self.surec is None or self.surec.poll() is None

    # ------------------------------------------------------------ okuma

    def _oku(self):
        """Tek okuyucu: `\\0` ile ayrılmış mesajları ayırır; boru kapanınca bekleyen tüm komutları uyandırır."""
        tampon = bytearray()
        sebep = "Tarayıcı bağlantıyı kapattı."
        try:
            while True:
                parca = os.read(self._okuma_fd, OKUMA_PARCASI)
                if not parca:
                    break
                tampon += parca
                while True:
                    i = tampon.find(b"\0")
                    if i < 0:
                        break
                    ham = bytes(tampon[:i])
                    del tampon[:i + 1]
                    self._isle(ham)
                if len(tampon) > EN_BUYUK_YUK:
                    sebep = f"Tarayıcıdan gelen veri çok büyük ({len(tampon)} bayt), bağlantı kesildi."
                    break
        except OSError as h:
            sebep = f"Tarayıcı bağlantısı koptu: {h}"
        finally:
            self._kapandi(sebep)
            try:
                os.close(self._okuma_fd)
            except OSError:
                pass

    def _isle(self, ham):
        try:
            mesaj = json.loads(ham.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return  # bozuk tek mesaj bağlantıyı düşürmesin
        if not isinstance(mesaj, dict):
            return
        if "id" in mesaj:
            with self._kosul:
                if mesaj["id"] in self._bekleyen:  # zaman aşımına uğramış komutun geç yanıtı atılır
                    self._bekleyen[mesaj["id"]] = mesaj
                    self._kosul.notify_all()
            return
        yontem = mesaj.get("method")
        if not isinstance(yontem, str):
            return
        params = mesaj.get("params") if isinstance(mesaj.get("params"), dict) else {}
        with self._kosul:
            if yontem == "Target.attachedToTarget" and params.get("sessionId"):
                self.oturumlar[params["sessionId"]] = (params.get("targetInfo") or {}).get("targetId", "")
            elif yontem == "Target.detachedFromTarget" and params.get("sessionId"):
                self.oturumlar.pop(params["sessionId"], None)
            self.olaylar.append(mesaj)

    def _kapandi(self, sebep):
        with self._kosul:
            if not self._kapali:
                self._kapali = True
                self.kapanma_sebebi = sebep
            self._kosul.notify_all()

    # ------------------------------------------------------------ yazma

    def _yaz(self, veri):
        with self._yazma_kilidi:
            if self._yazma_kapali:
                raise CdpHatasi("Tarayıcı bağlantısı kapalı.")
            try:
                gorunum = memoryview(veri)
                while gorunum:
                    yazilan = os.write(self._yazma_fd, gorunum)
                    gorunum = gorunum[yazilan:]
            except OSError as h:
                self._kapandi(f"Tarayıcıya veri gönderilemedi: {h}")
                raise CdpHatasi(f"Tarayıcıya veri gönderilemedi: {h}") from h

    def komut(self, yontem, sessionId=None, zaman=30, parametreler=None, **params):
        """CDP komutu gönderir, aynı kimlikli yanıtı bekler ve `result` değerini döndürür.

        sessionId verilirse komut o sekme oturumuna gider. Parametre adı "sessionId" olan komutlar
        (ör. Target.detachFromTarget) parametreyi `parametreler={"sessionId": ...}` ile verir.
        """
        if parametreler:
            params = dict(parametreler, **params)
        with self._kosul:
            if self._kapali:
                raise CdpHatasi(self.kapanma_sebebi or "Tarayıcı bağlantısı kapalı.")
            self._sonraki_id += 1
            kimlik = self._sonraki_id
            self._bekleyen[kimlik] = None
        mesaj = {"id": kimlik, "method": yontem, "params": params}
        if sessionId:
            mesaj["sessionId"] = sessionId
        try:
            # json.dumps denetim karakterlerini (\u0000 dahil) kaçışlar: ayraç baytı mesajın içinde geçemez.
            self._yaz(json.dumps(mesaj).encode("utf-8") + b"\0")
            bitis = time.monotonic() + zaman
            with self._kosul:
                while self._bekleyen.get(kimlik) is None:
                    if self._kapali:
                        raise CdpHatasi(self.kapanma_sebebi or "Tarayıcı bağlantısı kapalı.")
                    kalan = bitis - time.monotonic()
                    if kalan <= 0:
                        raise CdpHatasi(f"Tarayıcıdan yanıt gelmedi (zaman aşımı: {yontem}).")
                    self._kosul.wait(kalan)
                yanit = self._bekleyen[kimlik]
        finally:
            with self._kosul:
                self._bekleyen.pop(kimlik, None)
        if "error" in yanit:
            e = yanit["error"] if isinstance(yanit["error"], dict) else {"message": str(yanit["error"])}
            raise CdpHatasi(f"{yontem} komutu hata verdi: {e.get('message', e)} (kod {e.get('code', '?')})")
        sonuc = yanit.get("result", {})
        return sonuc if isinstance(sonuc, dict) else {}

    # ------------------------------------------------------------ kapatma

    def kapat(self, tarayiciyi_kapat=False, bekleme=5):
        """Bağlantıyı kapatır (hata vermez). tarayiciyi_kapat=True ise önce Browser.close gönderilir.

        Bizim yazma ucumuz kapanınca tarayıcı da kendiliğinden kapanır (boru bağlantısının doğası).
        Okuma ucu, okuyucu thread sonu (EOF) görünce kendisi kapatılır.
        """
        if tarayiciyi_kapat and not self._kapali:
            try:
                self.komut("Browser.close", zaman=bekleme)
            except CdpHatasi:
                pass
        with self._yazma_kilidi:
            if not self._yazma_kapali:
                self._yazma_kapali = True
                try:
                    os.close(self._yazma_fd)
                except OSError:
                    pass
        self._kapandi("Tarayıcı bağlantısı kapatıldı.")
        if self.surec is not None and bekleme:
            try:
                self.surec.wait(bekleme)
            except subprocess.TimeoutExpired:
                pass


class Oturum(_SayfaKomutlari):
    """Tek bir sekmeye (hedefe) bağlı CDP oturumu; komutlar ortak boru üzerinden `sessionId` ile gider."""

    def __init__(self, boru, hedef_id, oturum_id):
        self.boru, self.hedef_id, self.oturum_id = boru, hedef_id, oturum_id
        self._kapali = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.kapat()

    def komut(self, yontem, *, zaman=30, **params):
        if self._kapali:
            raise CdpHatasi("Sekme bağlantısı kapalı.")
        return self.boru.komut(yontem, sessionId=self.oturum_id, zaman=zaman, parametreler=params)

    def kapat(self):
        """Oturumdan ayrılır (Target.detachFromTarget); sekme açık kalır. Hata vermez."""
        if self._kapali:
            return
        self._kapali = True
        try:
            self.boru.komut("Target.detachFromTarget", zaman=5, parametreler={"sessionId": self.oturum_id})
        except CdpHatasi:
            pass


# ---------------------------------------------------------------- tarayıcı düzeyi yardımcılar

def hedefler(boru):
    """Açık hedeflerin listesi: [{"id", "type", "url", "title"}] (Target.getTargets)."""
    liste = boru.komut("Target.getTargets").get("targetInfos", [])
    return [{"id": h.get("targetId", ""), "type": h.get("type", ""), "url": h.get("url", ""),
             "title": h.get("title", "")} for h in liste if isinstance(h, dict)]


def pencere_bul(boru, parca):
    """Adresi parçayla eşleşen ilk "page" hedefi; yoksa None.

    parca: "alanadi[:port][/yol-oneki]" (ör. "chatgpt.com", "127.0.0.1:8799/test"). Eşleşme alt dize
    değil, alan adı sınırında yapılır (bkz. siteler.adres_eslesir_mi): "chatgpt.com.kotu.net" eşleşmez.
    """
    return next((h for h in hedefler(boru)
                 if h["type"] == "page" and siteler.adres_eslesir_mi(h["url"], parca)), None)


def sekmeye_baglan(boru, hedef_id):
    """Hedefe (sekmeye) düz (flatten) oturumla bağlanır; `Oturum` döndürür."""
    oturum_id = boru.komut("Target.attachToTarget", targetId=hedef_id, flatten=True).get("sessionId")
    if not oturum_id:
        raise CdpHatasi("Sekmeye bağlanılamadı (oturum kimliği gelmedi).")
    return Oturum(boru, hedef_id, oturum_id)


def yeni_pencere(boru, url):
    """Yeni bir ÜST DÜZEY pencere açar ve hedef kimliğini (targetId) döndürür."""
    return boru.komut("Target.createTarget", url=url, newWindow=True)["targetId"]


def pencere_sinirlari(boru, hedef_id, sol, ust, genislik, yukseklik):
    """Hedefin (sekmenin) bulunduğu tarayıcı penceresini verilen konuma/boyuta getirir.

    Browser.getWindowForTarget → Browser.setWindowBounds çağrılır; pencere simge/ekranı kaplama
    durumundaysa önce normale döndürülür. Değerler tarayıcının kullandığı mantıksal (DIP) pikseldir.
    Yeni sınırlar sözlük olarak döner.
    """
    pencere = boru.komut("Browser.getWindowForTarget", targetId=hedef_id)
    if pencere.get("bounds", {}).get("windowState", "normal") != "normal":
        boru.komut("Browser.setWindowBounds", windowId=pencere["windowId"], bounds={"windowState": "normal"})
    boru.komut("Browser.setWindowBounds", windowId=pencere["windowId"],
               bounds={"left": int(sol), "top": int(ust), "width": int(genislik), "height": int(yukseklik),
                       "windowState": "normal"})
    return boru.komut("Browser.getWindowForTarget", targetId=hedef_id).get("bounds", {})


# ---------------------------------------------------------------- başlatma

def boruyla_baslat(komut):
    """Tarayıcıyı CDP borularıyla başlatır ve `BoruBaglantisi` döndürür (yalnızca Windows).

    komut: [exe, argümanlar...]; boru bayrakları exe'den hemen sonra eklenir. Tarayıcıya YALNIZCA iki boru
    ucu kalıtılır (STARTUPINFO handle_list); bizdeki karşı uçlar süreç başlar başlamaz kapatılır, böylece
    tarayıcı kapanınca okuyucu EOF görür. `--remote-debugging-io-pipes` sırası tarayıcının bakış açısındandır:
    önce tarayıcının OKUDUĞU, sonra YAZDIĞI uç.
    """
    import msvcrt  # yalnızca Windows

    tarayici_okur, biz_yazariz = os.pipe()
    biz_okuruz, tarayici_yazar = os.pipe()
    surec = None
    try:
        h_okur = msvcrt.get_osfhandle(tarayici_okur)
        h_yazar = msvcrt.get_osfhandle(tarayici_yazar)
        os.set_handle_inheritable(h_okur, True)
        os.set_handle_inheritable(h_yazar, True)
        bilgi = subprocess.STARTUPINFO()
        bilgi.lpAttributeList = {"handle_list": [h_okur, h_yazar]}
        tam = [komut[0], "--remote-debugging-pipe", f"--remote-debugging-io-pipes={h_okur},{h_yazar}", *komut[1:]]
        surec = subprocess.Popen(tam, startupinfo=bilgi, close_fds=True)
    except OSError as h:
        for fd in (biz_yazariz, biz_okuruz):
            os.close(fd)
        raise CdpHatasi(f"Tarayıcı başlatılamadı: {h}") from h
    finally:
        for fd in (tarayici_okur, tarayici_yazar):
            try:
                os.close(fd)
            except OSError:
                pass
    return BoruBaglantisi(biz_okuruz, biz_yazariz, surec)
