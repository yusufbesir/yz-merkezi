#!/usr/bin/env python3
"""Yapay Zeka Merkezi (masaüstü sürümü) arka ucu.

Bilgisayarda kurulu ChatGPT, Gemini ve Claude programlarını bulur, yan yana dizer ve
arayüzden yazılan mesajı işaretli programların hepsine yapıştırıp gönderir.
Arayüz, Claude masaüstü uygulamasının düzeninde hazırlanmış bir web sayfasıdır ve
Edge'in uygulama penceresinde açılır. API anahtarı gerekmez.
"""
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pencereler as pc

KOK = Path(__file__).resolve().parent
ARAYUZ = KOK / "arayuz-masaustu"
UYGULAMA_DOSYASI = KOK / "uygulamalar.json"
AYAR_DOSYASI = Path(os.environ.get("YZ_MASAUSTU_AYAR", KOK / "masaustu-ayarlar.json"))
PORT = int(os.environ.get("YZ_MASAUSTU_PORT", "8766"))
PENCERE_BASLIGI = "Yapay Zeka Merkezi"
VARSAYILAN_KONUM = {"oran_x": 0.5, "alttan": 90}
OGRETME_SURESI = 4
EDGE_YOLLARI = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
VARSAYILAN_AYARLAR = {
    "tema": "sistem", "yazi_boyutu": "orta", "enter_bas": True, "kutuyu_temizle": True,
    "yerlesim": "sol", "ad": "Yusuf",
}

KILIT = threading.Lock()
is_kilidi = threading.Lock()  # aynı anda tek gönderme/öğretme işlemi


class IsHatasi(Exception):
    pass


# ---------------------------------------------------------------- ayarlar ve veri

def ayarlari_oku():
    try:
        veri = json.loads(AYAR_DOSYASI.read_text("utf-8"))
    except (OSError, ValueError):
        veri = {}
    veri.setdefault("ayarlar", {})
    for k, v in VARSAYILAN_AYARLAR.items():
        veri["ayarlar"].setdefault(k, v)
    veri.setdefault("konumlar", {})
    veri.setdefault("ek_uygulamalar", [])
    veri.setdefault("secili", {})
    veri.setdefault("sohbetler", [])
    return veri


def ayarlari_yaz(veri):
    gecici = AYAR_DOSYASI.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2), "utf-8")
    os.replace(gecici, AYAR_DOSYASI)


def uygulamalar(veri):
    return json.loads(UYGULAMA_DOSYASI.read_text("utf-8")) + veri["ek_uygulamalar"]


def uygulama_bul(veri, uid):
    return next((u for u in uygulamalar(veri) if u["id"] == uid), None)


def kendi_pencere():
    """Arayüzün açıldığı tarayıcı penceresi (başlığından tanınır)."""
    return pc.pencere_bul({"exe": "msedge.exe", "baslik_icerir": PENCERE_BASLIGI}, pc.pencereleri_listele()) \
        or next((p for p in pc.pencereleri_listele() if PENCERE_BASLIGI in p.baslik), None)


def durum(veri):
    acik = pc.pencereleri_listele()
    liste = []
    for u in uygulamalar(veri):
        p = pc.pencere_bul(u, acik)
        liste.append({
            "id": u["id"], "ad": u["ad"], "renk": u.get("renk", "#888"), "acik": bool(p),
            "ogretildi": u["id"] in veri["konumlar"], "secili": veri["secili"].get(u["id"], True),
            "ek": u in veri["ek_uygulamalar"], "exe": u["exe"],
        })
    return {"programlar": liste, "ayarlar": veri["ayarlar"], "sohbetler": veri["sohbetler"]}


# ---------------------------------------------------------------- işlemler

def hepsini_diz(veri):
    acik = pc.pencereleri_listele()
    hedefler = [pc.pencere_bul(u, acik) for u in uygulamalar(veri) if veri["secili"].get(u["id"], True)]
    hedefler = [h for h in hedefler if h]
    if not hedefler:
        raise IsHatasi("Dizilecek açık program yok. Önce programları açın.")
    sol, ust, sag, alt = pc.calisma_alani()
    ben = kendi_pencere()
    if veri["ayarlar"]["yerlesim"] == "alt":
        cubuk = 300
        konumlar = pc.yan_yana_konumlar((sol, ust, sag, alt), len(hedefler), cubuk)
        benim = (sol, alt - cubuk, sag - sol, cubuk)
    else:
        benim_genislik = max(400, (sag - sol) * 28 // 100)
        konumlar = pc.yan_yana_konumlar((sol + benim_genislik, ust, sag, alt), len(hedefler), 0)
        benim = (sol, ust, benim_genislik, alt - ust)
    for h, (x, y, g, yk) in zip(hedefler, konumlar):
        pc.yerlestir(h.hwnd, x, y, g, yk)
    if ben:
        pc.yerlestir(ben.hwnd, *benim)
        pc.one_getir(ben.hwnd)
    return len(hedefler)


def gonder(veri, metin, hedef_idler, enter):
    acik = pc.pencereleri_listele()
    pc.panoya_yaz(metin)
    gonderilen, sorunlar = [], []
    for uid in hedef_idler:
        u = uygulama_bul(veri, uid)
        if not u:
            continue
        p = pc.pencere_bul(u, acik)
        if not p:
            sorunlar.append({"ad": u["ad"], "sebep": "açık değil"})
            continue
        try:
            pc.yaziyi_gonder(p.hwnd, veri["konumlar"].get(uid, VARSAYILAN_KONUM), enter=enter)
            gonderilen.append(u["ad"])
        except pc.PencereHatasi as h:
            sorunlar.append({"ad": u["ad"], "sebep": str(h)})
    ben = kendi_pencere()
    if ben:
        pc.one_getir(ben.hwnd)
    return gonderilen, sorunlar


def ogret(veri, uid):
    u = uygulama_bul(veri, uid)
    p = u and pc.pencere_bul(u, pc.pencereleri_listele())
    if not p:
        raise IsHatasi("Program açık değil. Önce açın.")
    pc.one_getir(p.hwnd)
    time.sleep(OGRETME_SURESI)
    konum = pc.konum_hesapla(pc.dikdortgen(p.hwnd), pc.fare_konumu())
    ben = kendi_pencere()
    if ben:
        pc.one_getir(ben.hwnd)
    if not (0 <= konum["oran_x"] <= 1 and konum["alttan"] > 0):
        raise IsHatasi("Fare programın penceresinin dışındaydı, tekrar deneyin.")
    return konum


def sohbete_ekle(veri, sohbet_id, metin, gonderilen, sorunlar):
    sohbet = next((s for s in veri["sohbetler"] if s["id"] == sohbet_id), None)
    if not sohbet:
        sohbet = {"id": sohbet_id or datetime.now().strftime("%Y%m%d%H%M%S%f"),
                  "baslik": metin.strip().splitlines()[0][:48], "zaman": datetime.now().isoformat(timespec="minutes"),
                  "mesajlar": []}
        veri["sohbetler"].insert(0, sohbet)
    sohbet["mesajlar"].append({"metin": metin, "zaman": datetime.now().strftime("%H:%M"),
                               "gonderilen": gonderilen, "sorunlar": sorunlar})
    sohbet["guncelleme"] = datetime.now().isoformat(timespec="minutes")
    return sohbet["id"]


# ---------------------------------------------------------------- HTTP

ICERIK = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}


class Isleyici(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _guvenli(self):
        izinli = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        koken = self.headers.get("Origin")
        return self.headers.get("Host", "") in izinli and (not koken or koken in {f"http://{h}" for h in izinli})

    def _json(self, veri, kod=200):
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def _govde(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n)) if n else {}
        except ValueError:
            return {}

    def do_GET(self):
        if not self._guvenli():
            return self._json({"hata": "İzin verilmeyen istek."}, 403)
        yol = urlparse(self.path).path
        if yol == "/api/durum":
            return self._json(durum(ayarlari_oku()))
        if yol == "/api/pencereler":
            ben = kendi_pencere()
            liste = [{"baslik": p.baslik, "exe": p.exe, "yol": p.yol} for p in pc.pencereleri_listele()
                     if not ben or p.hwnd != ben.hwnd]
            return self._json({"pencereler": liste})
        hedef = (ARAYUZ / ("index.html" if yol == "/" else yol.lstrip("/"))).resolve()
        if ARAYUZ.resolve() not in hedef.parents or not hedef.is_file():
            return self._json({"hata": "Sayfa bulunamadı."}, 404)
        govde = hedef.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ICERIK.get(hedef.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(govde)

    def do_POST(self):
        if not self._guvenli():
            return self._json({"hata": "İzin verilmeyen istek."}, 403)
        yol = urlparse(self.path).path
        g = self._govde()
        try:
            with KILIT:
                veri = ayarlari_oku()
                sonuc = self._islem(yol, g, veri)
                ayarlari_yaz(veri)
            return self._json(sonuc)
        except (IsHatasi, pc.PencereHatasi) as h:
            return self._json({"hata": str(h)}, 400)
        except Exception as h:  # noqa: BLE001
            return self._json({"hata": f"Beklenmeyen hata: {h}"}, 500)

    def _islem(self, yol, g, veri):
        if yol == "/api/ayar":
            for k in VARSAYILAN_AYARLAR:
                if k in g:
                    veri["ayarlar"][k] = g[k]
            if "secili" in g:
                veri["secili"].update(g["secili"])
            return {"tamam": True}
        if yol == "/api/ac":
            u = uygulama_bul(veri, g.get("id", ""))
            if not u:
                raise IsHatasi("Program bulunamadı.")
            p = pc.pencere_bul(u, pc.pencereleri_listele())
            if p:
                pc.one_getir(p.hwnd)
                return {"tamam": True, "zaten_acik": True}
            pc.uygulamayi_ac(u)
            return {"tamam": True}
        if yol == "/api/hepsini-ac":
            acilan = []
            acik = pc.pencereleri_listele()
            for u in uygulamalar(veri):
                if veri["secili"].get(u["id"], True) and not pc.pencere_bul(u, acik):
                    pc.uygulamayi_ac(u)
                    acilan.append(u["ad"])
            return {"acilan": acilan}
        if yol == "/api/diz":
            return {"adet": hepsini_diz(veri)}
        if yol == "/api/gonder":
            metin = (g.get("metin") or "").strip()
            if not metin:
                raise IsHatasi("Mesaj boş.")
            hedefler = [u["id"] for u in uygulamalar(veri) if veri["secili"].get(u["id"], True)]
            if not hedefler:
                raise IsHatasi("En az bir program seçin.")
            if not is_kilidi.acquire(blocking=False):
                raise IsHatasi("Önceki gönderme hâlâ sürüyor.")
            try:
                gonderilen, sorunlar = gonder(veri, metin, hedefler, veri["ayarlar"]["enter_bas"])
            finally:
                is_kilidi.release()
            sid = sohbete_ekle(veri, g.get("sohbet"), metin, gonderilen, sorunlar)
            return {"gonderilen": gonderilen, "sorunlar": sorunlar, "sohbet": sid, "sohbetler": veri["sohbetler"]}
        if yol == "/api/ogret":
            if not is_kilidi.acquire(blocking=False):
                raise IsHatasi("Başka bir işlem sürüyor.")
            try:
                veri["konumlar"][g.get("id", "")] = ogret(veri, g.get("id", ""))
            finally:
                is_kilidi.release()
            return {"tamam": True}
        if yol == "/api/program-ekle":
            ad = (g.get("ad") or "").strip()
            exe = (g.get("exe") or "").strip()
            if not ad or not exe:
                raise IsHatasi("Ad ve program gerekli.")
            yeni = {"id": f"ek-{int(time.time())}", "ad": ad, "exe": exe, "renk": "#9b59b6"}
            if g.get("baslik_icerir"):
                yeni["baslik_icerir"] = g["baslik_icerir"].strip()
            elif g.get("yol"):
                yeni["yol"] = g["yol"]
            veri["ek_uygulamalar"].append(yeni)
            return {"tamam": True, "id": yeni["id"]}
        if yol == "/api/program-sil":
            veri["ek_uygulamalar"] = [u for u in veri["ek_uygulamalar"] if u["id"] != g.get("id")]
            veri["konumlar"].pop(g.get("id"), None)
            return {"tamam": True}
        if yol == "/api/sohbet-sil":
            veri["sohbetler"] = [s for s in veri["sohbetler"] if s["id"] != g.get("id")]
            return {"tamam": True, "sohbetler": veri["sohbetler"]}
        if yol == "/api/sohbet-adlandir":
            for s in veri["sohbetler"]:
                if s["id"] == g.get("id") and (g.get("baslik") or "").strip():
                    s["baslik"] = g["baslik"].strip()[:60]
            return {"tamam": True, "sohbetler": veri["sohbetler"]}
        raise IsHatasi("Bilinmeyen istek.")


def pencereyi_ac(adres):
    """Arayüzü kendi penceresinde (Edge uygulama modu) açar; Edge yoksa varsayılan tarayıcıda."""
    edge = next((y for y in EDGE_YOLLARI if Path(y).exists()), None)
    if edge:
        profil = KOK / ".tarayici-profili"
        subprocess.Popen([edge, f"--app={adres}", f"--user-data-dir={profil}", "--window-size=1100,760",
                          "--no-first-run", "--disable-features=TranslateUI"])
    else:
        webbrowser.open(adres)


def main():
    if sys.platform != "win32":
        print("Bu sürüm yalnızca Windows'ta çalışır.")
        return
    pc.dpi_farkindaligi_ac()
    try:
        sunucu = ThreadingHTTPServer(("127.0.0.1", PORT), Isleyici)
    except OSError:
        pencereyi_ac(f"http://127.0.0.1:{PORT}")  # zaten çalışıyor, sadece pencereyi aç
        return
    sunucu.daemon_threads = True
    adres = f"http://127.0.0.1:{PORT}"
    if "--pencere-acma" not in sys.argv:
        threading.Thread(target=pencereyi_ac, args=(adres,), daemon=True).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
