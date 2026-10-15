#!/usr/bin/env python3
"""Yapay Zeka Merkezi: GPT, Gemini, Claude ve yerel modelleri tek ekrandan kullanmak için yerel sunucu.

Yalnızca Python standart kütüphanesini kullanır, ek paket kurmak gerekmez.
Sunucu sadece bu bilgisayardan (127.0.0.1) erişilebilir; API anahtarları
ayarlar.json dosyasında ya da ortam değişkenlerinde durur ve tarayıcıya gönderilmez.
"""
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import guvenlik

KOK = Path(__file__).resolve().parent
ARAYUZ = KOK / "arayuz"
KAYIT_DOSYASI = KOK / "saglayicilar.json"
AYAR_DOSYASI = guvenlik.veri_yolu("YZ_AYAR_DOSYASI", "ayarlar.json")  # varsayılan: %LOCALAPPDATA%\YZMerkezi
ESKI_AYAR_DOSYASI = KOK / "ayarlar.json"  # eski sürümlerin yeri (ilk açılışta taşınır)
PORT = int(os.environ.get("YZ_PORT", "8765"))
EN_FAZLA_TOKEN = 8192

# Bilinen yerel model sunucularının OpenAI uyumlu adresleri.
YEREL_ADAYLAR = [
    ("ollama", "Ollama", "http://127.0.0.1:11434/v1"),
    ("lmstudio", "LM Studio", "http://127.0.0.1:1234/v1"),
    ("jan", "Jan", "http://127.0.0.1:1337/v1"),
    ("llamacpp", "llama.cpp / LocalAI", "http://127.0.0.1:8080/v1"),
    ("vllm", "vLLM", "http://127.0.0.1:8000/v1"),
    ("tgwui", "Text Generation WebUI", "http://127.0.0.1:5000/v1"),
    ("gpt4all", "GPT4All", "http://127.0.0.1:4891/v1"),
]

# OpenAI'nin model listesinde sohbet dışı (ses, görsel, gömme) modelleri ayıklar.
OPENAI_SOHBET_DISI = re.compile(
    r"embed|whisper|tts|dall-e|moderation|davinci|babbage|transcribe|realtime|audio|image|search|computer-use|sora"
)

AYAR_KILIDI = threading.Lock()
bulunan_yereller = {}
# İstek belirteci: açılışta bir kez üretilir, yalnızca bellekte durur; arayüz adreste (#t=) alır.
BELIRTEC = guvenlik.yeni_belirtec()


class SaglayiciHatasi(Exception):
    """Kullanıcıya Türkçe gösterilecek, sağlayıcı kaynaklı hata."""


# ---------------------------------------------------------------- ayarlar

def ayarlari_oku():
    """Ayar dosyasını okur. Bozuksa (JSON değilse) silinmez: `<ad>.bozuk-<zaman>.json` olarak saklanır."""
    veri, uyari = guvenlik.json_oku(AYAR_DOSYASI)
    if uyari:
        print(uyari)
    return veri


def ayarlari_yaz(ayar):
    """Yazmadan önce `anahtarlar` değerlerini DPAPI ile şifreler (düz metin geçişi); DPAPI yoksa hata verir."""
    anahtarlar = ayar.get("anahtarlar")
    if isinstance(anahtarlar, dict):
        ayar = dict(ayar, anahtarlar={
            k: (v if guvenlik.dpapi_sifreli_mi(v) else guvenlik.dpapi_sifrele(v))
            for k, v in anahtarlar.items() if isinstance(v, str) and v})
    guvenlik.json_yaz(AYAR_DOSYASI, ayar)


def tum_saglayicilar():
    hazir = json.loads(KAYIT_DOSYASI.read_text("utf-8"))
    ozel = ayarlari_oku().get("ozel_saglayicilar", [])
    return (
        [dict(s, kaynak="hazir") for s in hazir]
        + [dict(s, kaynak="ozel") for s in ozel]
        + [dict(s, kaynak="yerel") for s in bulunan_yereller.values()]
    )


def saglayici_bul(sid):
    return next((s for s in tum_saglayicilar() if s["id"] == sid), None)


def anahtar_al(s):
    """Önce ayarlar.json, sonra ortam değişkeni. (anahtar, kaynak) döner."""
    dosyadaki = ayarlari_oku().get("anahtarlar", {}).get(s["id"])
    if dosyadaki:
        if not guvenlik.dpapi_sifreli_mi(dosyadaki):
            return dosyadaki, "dosya"  # eski düz metin kaydı: kabul edilir, ilk yazımda şifrelenir
        try:
            return guvenlik.dpapi_coz(dosyadaki), "dosya"
        except ValueError as h:
            guvenlik.hata_yaz(f"Kayıtlı API anahtarı çözülemedi ({s['id']}): {h}")
            return "", None
    ortamdaki = os.environ.get(s.get("anahtar_ortam") or "")
    if ortamdaki:
        return ortamdaki, "ortam"
    return "", None


def saglayici_listesi():
    liste = []
    for s in tum_saglayicilar():
        _, kaynak = anahtar_al(s)
        liste.append({
            "id": s["id"],
            "ad": s["ad"],
            "tur": s["tur"],
            "adres": s["adres"],
            "renk": s.get("renk", "#888888"),
            "kaynak": s["kaynak"],
            "nereden": s.get("nereden", ""),
            "anahtar_ortam": s.get("anahtar_ortam", ""),
            "anahtar_gerekli": bool(s.get("anahtar_gerekli")),
            "anahtar_kaynagi": kaynak,
            "model_sayisi": s.get("model_sayisi"),
        })
    return liste


# ---------------------------------------------------------------- HTTP yardımcıları

def http_hatasi(e):
    try:
        govde = e.read().decode("utf-8", "replace")
    except OSError:
        govde = ""
    mesaj = govde
    try:
        veri = json.loads(govde)
        if isinstance(veri, list) and veri:
            veri = veri[0]
        hata = veri.get("error", veri) if isinstance(veri, dict) else veri
        mesaj = hata.get("message", str(hata)) if isinstance(hata, dict) else str(hata)
    except ValueError:
        pass
    aciklama = {
        400: "İstek geçersiz",
        401: "API anahtarı geçersiz veya eksik",
        402: "Hesapta yeterli bakiye yok",
        403: "Bu işlem için yetki yok",
        404: "Model ya da adres bulunamadı",
        429: "Kota veya hız sınırı aşıldı",
        500: "Sağlayıcı sunucusunda hata oluştu",
        503: "Sağlayıcı şu an hizmet veremiyor",
    }.get(e.code, "Sağlayıcı hata döndürdü")
    return SaglayiciHatasi(f"{aciklama} (HTTP {e.code}): {mesaj.strip()[:400]}")


def istek(url, veri=None, basliklar=None, zaman=60):
    tum_basliklar = {"Content-Type": "application/json", "User-Agent": "YapayZekaMerkezi/1.0"}
    tum_basliklar.update(basliklar or {})
    govde = json.dumps(veri).encode("utf-8") if veri is not None else None
    talep = urllib.request.Request(url, data=govde, headers=tum_basliklar, method="POST" if govde else "GET")
    try:
        return urllib.request.urlopen(talep, timeout=zaman)
    except urllib.error.HTTPError as e:
        raise http_hatasi(e) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        sebep = getattr(e, "reason", e)
        raise SaglayiciHatasi(f"Sağlayıcıya bağlanılamadı: {sebep}") from None


def sse_olaylari(yanit):
    """Sunucu olay akışındaki (SSE) her 'data:' satırını JSON olarak verir."""
    for ham in yanit:
        satir = ham.decode("utf-8", "replace").strip()
        if not satir.startswith("data:"):
            continue
        veri = satir[5:].strip()
        if veri == "[DONE]":
            return
        if veri:
            yield json.loads(veri)


def anahtar_gerekli(s):
    anahtar, _ = anahtar_al(s)
    if not anahtar and s.get("anahtar_gerekli"):
        raise SaglayiciHatasi(f"{s['ad']} için API anahtarı girilmemiş. Ayarlar penceresinden ekleyin.")
    return anahtar


# ---------------------------------------------------------------- OpenAI uyumlu (GPT, Ollama, LM Studio, Grok, DeepSeek...)

def openai_basliklar(anahtar):
    return {"Authorization": f"Bearer {anahtar}"} if anahtar else {}


def openai_modeller(s):
    anahtar = anahtar_gerekli(s)
    with istek(s["adres"].rstrip("/") + "/models", basliklar=openai_basliklar(anahtar), zaman=20) as y:
        veri = json.load(y)
    modeller = veri.get("data", veri.get("models", []))
    if s["id"] == "openai":
        modeller = [m for m in modeller if not OPENAI_SOHBET_DISI.search(m["id"])]
    modeller.sort(key=lambda m: (-(m.get("created") or 0), m["id"]))
    return [{"id": m["id"], "ad": m.get("name") or m["id"]} for m in modeller]


def openai_sohbet(s, model, mesajlar, sistem):
    anahtar = anahtar_gerekli(s)
    roller = {"kullanici": "user", "asistan": "assistant"}
    mesaj_listesi = [{"role": "system", "content": sistem}] if sistem else []
    mesaj_listesi += [{"role": roller[m["rol"]], "content": m["icerik"]} for m in mesajlar]
    govde = {"model": model, "messages": mesaj_listesi, "stream": True}
    with istek(s["adres"].rstrip("/") + "/chat/completions", govde, openai_basliklar(anahtar), zaman=600) as y:
        for olay in sse_olaylari(y):
            if "error" in olay:
                raise SaglayiciHatasi(str(olay["error"].get("message", olay["error"])))
            secenekler = olay.get("choices") or [{}]
            parca = (secenekler[0].get("delta") or {}).get("content")
            if parca:
                yield parca


# ---------------------------------------------------------------- Anthropic (Claude)

def anthropic_basliklar(anahtar):
    return {"x-api-key": anahtar, "anthropic-version": "2023-06-01"}


def anthropic_modeller(s):
    anahtar = anahtar_gerekli(s)
    with istek(s["adres"].rstrip("/") + "/models?limit=1000", basliklar=anthropic_basliklar(anahtar), zaman=20) as y:
        veri = json.load(y)
    return [{"id": m["id"], "ad": m.get("display_name") or m["id"]} for m in veri.get("data", [])]


def anthropic_sohbet(s, model, mesajlar, sistem):
    anahtar = anahtar_gerekli(s)
    roller = {"kullanici": "user", "asistan": "assistant"}
    govde = {
        "model": model,
        "max_tokens": EN_FAZLA_TOKEN,
        "messages": [{"role": roller[m["rol"]], "content": m["icerik"]} for m in mesajlar],
        "stream": True,
    }
    if sistem:
        govde["system"] = sistem
    with istek(s["adres"].rstrip("/") + "/messages", govde, anthropic_basliklar(anahtar), zaman=600) as y:
        for olay in sse_olaylari(y):
            if olay.get("type") == "error":
                raise SaglayiciHatasi(olay.get("error", {}).get("message", "Claude hata döndürdü"))
            if olay.get("type") == "content_block_delta" and olay["delta"].get("type") == "text_delta":
                yield olay["delta"]["text"]


# ---------------------------------------------------------------- Google Gemini

def gemini_modeller(s):
    anahtar = anahtar_gerekli(s)
    url = s["adres"].rstrip("/") + "/models?pageSize=1000"
    with istek(url, basliklar={"x-goog-api-key": anahtar}, zaman=20) as y:
        veri = json.load(y)
    return [
        {"id": m["name"].removeprefix("models/"), "ad": m.get("displayName") or m["name"]}
        for m in veri.get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]


def gemini_sohbet(s, model, mesajlar, sistem):
    anahtar = anahtar_gerekli(s)
    roller = {"kullanici": "user", "asistan": "model"}
    govde = {"contents": [{"role": roller[m["rol"]], "parts": [{"text": m["icerik"]}]} for m in mesajlar]}
    if sistem:
        govde["systemInstruction"] = {"parts": [{"text": sistem}]}
    url = f"{s['adres'].rstrip('/')}/models/{quote(model, safe='-._')}:streamGenerateContent?alt=sse"
    with istek(url, govde, {"x-goog-api-key": anahtar}, zaman=600) as y:
        for olay in sse_olaylari(y):
            for aday in olay.get("candidates", []):
                for parca in aday.get("content", {}).get("parts", []):
                    if parca.get("text") and not parca.get("thought"):
                        yield parca["text"]


ADAPTORLER = {
    "openai": (openai_modeller, openai_sohbet),
    "anthropic": (anthropic_modeller, anthropic_sohbet),
    "gemini": (gemini_modeller, gemini_sohbet),
}


def modelleri_getir(s):
    return ADAPTORLER[s["tur"]][0](s)


def sohbet_et(s, model, mesajlar, sistem):
    return ADAPTORLER[s["tur"]][1](s, model, mesajlar, sistem)


# ---------------------------------------------------------------- yerel tarama

def yerel_yokla(aday):
    sid, ad, adres = aday
    try:
        with urllib.request.urlopen(adres + "/models", timeout=1.5) as y:
            veri = json.load(y)
        sayi = len(veri.get("data", veri.get("models", [])))
        return {"id": sid, "ad": ad, "tur": "openai", "adres": adres, "renk": "#22a06b",
                "anahtar_gerekli": False, "model_sayisi": sayi}
    except (OSError, ValueError):
        return None


def yerelleri_tara():
    with ThreadPoolExecutor(len(YEREL_ADAYLAR)) as havuz:
        sonuclar = [s for s in havuz.map(yerel_yokla, YEREL_ADAYLAR) if s]
    bulunan_yereller.clear()
    bulunan_yereller.update({s["id"]: s for s in sonuclar})
    return sonuclar


# ---------------------------------------------------------------- HTTP sunucusu

ICERIK_TURLERI = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                  ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".png": "image/png"}


def guvenlik_adres_uygun(adres):
    """Loopback dışındaki sağlayıcı adresleri https olmalı (anahtar açık metin gitmesin)."""
    try:
        parca = urlparse(adres)
        sunucu_adi = parca.hostname
    except ValueError:
        return False
    if not sunucu_adi or parca.scheme not in ("http", "https"):
        return False
    return parca.scheme == "https" or sunucu_adi in ("localhost", "127.0.0.1", "::1")


class Isleyici(guvenlik.GuvenlikKarisimi, BaseHTTPRequestHandler):
    def log_message(self, bicim, *args):
        pass

    def _beklenen_belirtec(self):
        return BELIRTEC

    def _api_izni_yok(self, yol, govde_var=False):
        """/api/* isteği belirteçsiz ya da yanlış belirteçliyse 403 yanıtlar (True döner). /api/kimlik hariç."""
        if not yol.startswith("/api/") or yol == "/api/kimlik":
            return False
        if self._belirtec_dogru_mu():
            return False
        if govde_var:
            self._govdeyi_at()
        self._json({"hata": "Oturum belirteci eksik ya da geçersiz. Uygulamayı baslat-api.bat ile yeniden açın."}, 403)
        return True

    def _guvenli_mi(self):
        # Başka sitelerin tarayıcı üzerinden bu sunucuya istek atmasını engeller.
        izinli = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host", "") not in izinli:
            return False
        koken = self.headers.get("Origin")
        return not koken or koken in {f"http://{h}" for h in izinli}

    def _json(self, veri, kod=200):
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def do_GET(self):
        if not self._guvenli_mi():
            return self._json({"hata": "İzin verilmeyen istek."}, 403)
        yol = urlparse(self.path)
        if self._api_izni_yok(yol.path):
            return
        if yol.path == "/api/kimlik":
            return self._json(guvenlik.KIMLIK)
        if yol.path == "/api/saglayicilar":
            return self._json(saglayici_listesi())
        if yol.path == "/api/modeller":
            sid = parse_qs(yol.query).get("id", [""])[0]
            s = saglayici_bul(sid)
            if not s:
                return self._json({"hata": "Sağlayıcı bulunamadı."}, 404)
            try:
                return self._json({"modeller": modelleri_getir(s)})
            except SaglayiciHatasi as h:
                return self._json({"hata": str(h)}, 502)
        return self._dosya(yol.path)

    def do_POST(self):
        if not self._guvenli_mi():
            self._govdeyi_at()
            return self._json({"hata": "İzin verilmeyen istek."}, 403)
        yol = urlparse(self.path).path
        if self._api_izni_yok(yol, govde_var=True):
            return
        try:
            g = self._govde()
        except guvenlik.IstekHatasi as h:
            return self._json({"hata": h.mesaj}, h.kod)
        try:
            if yol == "/api/sohbet":
                return self._sohbet(g)
            if yol == "/api/tara":
                return self._json({"bulunanlar": yerelleri_tara()})
            if yol == "/api/anahtar":
                return self._anahtar(g)
            if yol == "/api/saglayici-ekle":
                return self._saglayici_ekle(g)
            if yol == "/api/saglayici-sil":
                return self._saglayici_sil(g)
        except Exception as h:  # noqa: BLE001
            return self._json({"hata": guvenlik.beklenmeyen_hata(yol, h)}, 500)
        return self._json({"hata": "Bilinmeyen adres."}, 404)

    def _dosya(self, yol):
        hedef = (ARAYUZ / ("index.html" if yol in ("", "/") else yol.lstrip("/"))).resolve()
        if ARAYUZ.resolve() not in hedef.parents or not hedef.is_file():
            return self._json({"hata": "Sayfa bulunamadı."}, 404)
        govde = hedef.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ICERIK_TURLERI.get(hedef.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(govde)

    def _sohbet(self, g):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def yaz(olay):
            self.wfile.write((json.dumps(olay, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()

        akis = None
        try:
            s = saglayici_bul(g.get("saglayici", ""))
            if not s:
                raise SaglayiciHatasi("Sağlayıcı bulunamadı. Yerel bir servisse yeniden tarayın.")
            if not g.get("model"):
                raise SaglayiciHatasi("Model seçilmedi.")
            mesajlar = [m for m in g.get("mesajlar", []) if m.get("rol") in ("kullanici", "asistan")]
            if not mesajlar:
                raise SaglayiciHatasi("Gönderilecek mesaj yok.")
            akis = sohbet_et(s, g["model"], mesajlar, (g.get("sistem") or "").strip())
            for parca in akis:
                yaz({"t": parca})
            yaz({"bitti": True})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Kullanıcı "Durdur"a bastı; tarayıcı bağlantıyı kapattı.
        except Exception as h:  # noqa: BLE001 - her hata kullanıcıya Türkçe iletilmeli
            mesaj = str(h) if isinstance(h, SaglayiciHatasi) else guvenlik.beklenmeyen_hata("/api/sohbet", h)
            try:
                yaz({"hata": mesaj})
            except OSError:
                pass
        finally:
            if akis is not None:
                akis.close()

    def _anahtar(self, g):
        s = saglayici_bul(g.get("id", ""))
        if not s:
            return self._json({"hata": "Sağlayıcı bulunamadı."}, 404)
        with AYAR_KILIDI:
            ayar = ayarlari_oku()
            anahtarlar = ayar.setdefault("anahtarlar", {})
            yeni = (g.get("anahtar") or "").strip()
            if yeni:
                anahtarlar[s["id"]] = yeni
            else:
                anahtarlar.pop(s["id"], None)
            ayarlari_yaz(ayar)
        return self._json({"tamam": True})

    def _saglayici_ekle(self, g):
        ad = (g.get("ad") or "").strip()
        adres = (g.get("adres") or "").strip().rstrip("/")
        tur = g.get("tur", "openai")
        if not ad or not adres.startswith(("http://", "https://")) or tur not in ADAPTORLER:
            return self._json({"hata": "Ad, http(s) ile başlayan adres ve geçerli bir tür gerekli."}, 400)
        if not guvenlik_adres_uygun(adres):
            return self._json({"hata": "Yerel (localhost/127.0.0.1) olmayan adresler için https gerekli."}, 400)
        sid = "ozel-" + (re.sub(r"[^a-z0-9]+", "-", ad.lower()).strip("-") or "saglayici")
        with AYAR_KILIDI:
            ayar = ayarlari_oku()
            eski = next((o for o in ayar.get("ozel_saglayicilar", []) if o["id"] == sid), None)
            ozeller = [o for o in ayar.get("ozel_saglayicilar", []) if o["id"] != sid]
            anahtar = (g.get("anahtar") or "").strip()
            if eski and eski.get("adres") != adres:  # adres değişti: eski anahtar yeni adrese taşınmaz
                ayar.get("anahtarlar", {}).pop(sid, None)
            ozeller.append({"id": sid, "ad": ad, "tur": tur, "adres": adres,
                            "anahtar_gerekli": bool(anahtar), "renk": "#9b59b6"})
            ayar["ozel_saglayicilar"] = ozeller
            if anahtar:
                ayar.setdefault("anahtarlar", {})[sid] = anahtar
            ayarlari_yaz(ayar)
        return self._json({"tamam": True, "id": sid})

    def _saglayici_sil(self, g):
        sid = g.get("id", "")
        with AYAR_KILIDI:
            ayar = ayarlari_oku()
            ayar["ozel_saglayicilar"] = [o for o in ayar.get("ozel_saglayicilar", []) if o["id"] != sid]
            ayar.get("anahtarlar", {}).pop(sid, None)
            ayarlari_yaz(ayar)
        return self._json({"tamam": True})


class Sunucu(ThreadingHTTPServer):
    # Windows'ta SO_REUSEADDR, aynı porta ikinci bir dinleyicinin bağlanmasına izin verir (port gaspı):
    # kapatıyoruz, böylece port meşgulse bağlanma hata verir.
    allow_reuse_address = False
    daemon_threads = True


def main():
    global AYAR_DOSYASI
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        sunucu = Sunucu(("127.0.0.1", PORT), Isleyici)
    except OSError:
        print(f"{PORT} numaralı port kullanımda. Uygulama zaten açık olabilir: http://127.0.0.1:{PORT}")
        sys.exit(1)
    if not os.environ.get("YZ_AYAR_DOSYASI"):  # proje klasöründeki eski ayarlar.json bir kez veri klasörüne taşınır
        AYAR_DOSYASI = guvenlik.eski_veriyi_tasi(ESKI_AYAR_DOSYASI, AYAR_DOSYASI)
    threading.Thread(target=yerelleri_tara, daemon=True).start()
    adres = f"http://127.0.0.1:{PORT}"
    # Belirteç adresin parçasında (#t=) gider; parça sunucuya gönderilmez, arayüz okuyup adresten siler.
    belirtecli = f"{adres}/#t={BELIRTEC}"
    print(f"Yapay Zeka Merkezi çalışıyor: {adres}")
    print("Kapatmak için bu pencerede Ctrl+C tuşlarına basın.")
    if "--tarayici-acma" not in sys.argv:
        webbrowser.open(belirtecli)
    else:
        print(f"Tarayıcıda şu adresi aç (oturum belirteci içerir, kimseyle paylaşma): {belirtecli}")
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatıldı.")


if __name__ == "__main__":
    main()
