"""Sahte motor betiklerinin ortak yardımcıları (testler için; gerçek CLI'ların çıktı biçimini taklit eder).

Davranış istemdeki anahtar sözcükle seçilir:
    HATA    → motorun kendi hata olayı + çıkış kodu 1
    COKME   → stderr'e Türkçe hata yazıp tamamlanmadan çıkış (kod 3)
    SESSIZ  → hiçbir şey yazmadan bekler (ilk bayt zaman aşımı)
    YAVAS   → başlangıçtan sonra yarım saniyede bir parça yazar (iptal / toplam zaman aşımı)
    (diğer) → Türkçe karakterli üç parça ve başarılı bitiş

SAHTE_ARGV_DOSYASI tanımlıysa argv ve standart girdi JSON olarak oraya yazılır (testler bayrakları denetler).
SAHTE_GIRIS = "0" ise giriş durumu "yok" döner.
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import json
import os
import sys
import time
import uuid

PARCALAR = ["Merhaba ", "dünya — ", "ğüşıöç İ"]


def hazirla():
    for akis in (sys.stdout, sys.stderr):
        akis.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")


def girdi_oku():
    metin = sys.stdin.read()
    dosya = os.environ.get("SAHTE_ARGV_DOSYASI")
    if dosya:
        with open(dosya, "w", encoding="utf-8") as f:
            json.dump({"argv": sys.argv[1:], "girdi": metin}, f, ensure_ascii=False)
    return metin


def yaz(veri):
    sys.stdout.write(json.dumps(veri, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def giris_var():
    return os.environ.get("SAHTE_GIRIS", "1") != "0"


def deger(argv, bayrak):
    if bayrak in argv:
        i = argv.index(bayrak)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def yeni_kimlik():
    return str(uuid.uuid4())


def senaryo(istem):
    for anahtar in ("HATA", "COKME", "SESSIZ", "YAVAS"):
        if anahtar in istem:
            return anahtar
    return "normal"


def cokme():
    sys.stderr.write("ölümcül hata: sahte motor çöktü\n")
    sys.stderr.flush()
    sys.exit(3)


def sessiz():
    time.sleep(60)
    sys.exit(0)
