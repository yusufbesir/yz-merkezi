"""Yapay Zeka Merkezi simgesini üretir: SVG -> PNG (Edge headless) -> ICO (saf Python, ek paket yok).

Kullanım:  python araclar/simge_uret.py

Girdi : arayuz-masaustu/simge.svg (büyük), arayuz-masaustu/simge-kucuk.svg (16-32 px için sadeleştirilmiş)
Çıktı : arayuz-masaustu/simge-256.png, arayuz-masaustu/simge.ico (16, 24, 32, 48, 64, 128, 256 px, PNG girdili)
Geçici dosyalar ve Edge profili sistem geçici klasöründe açılır ve bitince silinir.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
ARAYUZ = KOK / "arayuz-masaustu"
BOYUTLAR = (16, 24, 32, 48, 64, 128, 256)
KUCUK_SINIR = 32  # bu boyuta kadar (dahil) sadeleştirilmiş SVG kullanılır
EDGE_ZAMAN_ASIMI = 15  # saniye (normalde bir çekim ~1 sn sürer)
EDGE_DENEME = 5
PNG_IMZA = b"\x89PNG\r\n\x1a\n"


def edge_bul():
    adaylar = [os.environ.get("YZ_EDGE", "")]
    for ortam in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        taban = os.environ.get(ortam)
        if taban:
            adaylar.append(str(Path(taban) / "Microsoft" / "Edge" / "Application" / "msedge.exe"))
    for aday in adaylar:
        if aday and Path(aday).is_file():
            return aday
    raise SystemExit("msedge.exe bulunamadı (YZ_EDGE ortam değişkeniyle yolunu verebilirsin).")


def png_boyutu(veri):
    """PNG IHDR'dan (genişlik, yükseklik) okur."""
    if veri[:8] != PNG_IMZA or veri[12:16] != b"IHDR":
        raise ValueError("Geçerli bir PNG değil.")
    return struct.unpack(">II", veri[16:24])


def edge_cek(edge, html, boyut, hedef, profil):
    """Tek bir headless Edge çekimi; takılırsa (zaman aşımı) süreç ağacını kapatır. Başarılıysa True."""
    komut = [edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
             f"--user-data-dir={profil}", f"--screenshot={hedef}",
             f"--window-size={boyut},{boyut}", html.as_uri()]
    hedef.unlink(missing_ok=True)
    # stdin kapalı olmazsa Edge bazen takılır
    surec = subprocess.Popen(komut, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        surec.wait(timeout=EDGE_ZAMAN_ASIMI)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # yalnızca bu çekimin başlattığı süreç ağacı kapatılır (kullanıcının Edge'ine dokunulmaz)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(surec.pid)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    try:
        return hedef.is_file() and png_boyutu(hedef.read_bytes()) == (boyut, boyut)
    except ValueError:
        return False


def svg_png(edge, svg, boyut, hedef, gecici):
    html = gecici / f"sarmal-{boyut}.html"
    html.write_text(
        '<!doctype html><html><body style="margin:0;background:transparent">'
        f'<img src="{svg.as_uri()}" style="width:{boyut}px;height:{boyut}px;display:block"></body></html>',
        encoding="utf-8")
    for deneme in range(1, EDGE_DENEME + 1):  # headless Edge ara sıra takılır: temiz profille yeniden dene
        if edge_cek(edge, html, boyut, hedef, gecici / f"edge-profil-{boyut}-{deneme}"):
            return
    raise SystemExit(f"{boyut} px PNG üretilemedi.")


def ico_yaz(png_listesi, hedef):
    """png_listesi: [(boyut, png_baytlari)]. Her girdi PNG baytlarını doğrudan içerir."""
    baslik = struct.pack("<HHH", 0, 1, len(png_listesi))
    ofset = 6 + 16 * len(png_listesi)
    girdiler, govde = b"", b""
    for boyut, veri in png_listesi:
        b = 0 if boyut >= 256 else boyut  # 256 px için genişlik/yükseklik baytı 0
        girdiler += struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(veri), ofset + len(govde))
        govde += veri
    hedef.write_bytes(baslik + girdiler + govde)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    edge = edge_bul()
    gecici = Path(tempfile.mkdtemp(prefix="yz-simge-"))
    try:
        png_listesi = []
        for boyut in BOYUTLAR:
            svg = ARAYUZ / ("simge-kucuk.svg" if boyut <= KUCUK_SINIR else "simge.svg")
            png = gecici / f"simge-{boyut}.png"
            svg_png(edge, svg, boyut, png, gecici)
            png_listesi.append((boyut, png.read_bytes()))
            print(f"{boyut:>3} px  <- {svg.name}")
        (ARAYUZ / "simge-256.png").write_bytes(dict(png_listesi)[256])
        ico_yaz(png_listesi, ARAYUZ / "simge.ico")
        print("Yazıldı:", ARAYUZ / "simge-256.png", "ve", ARAYUZ / "simge.ico")
    finally:
        for _ in range(5):  # Edge profil dosyalarını bırakana kadar kısa süre bekle
            shutil.rmtree(gecici, ignore_errors=True)
            if not gecici.exists():
                break
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
