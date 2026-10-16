#!/usr/bin/env python3
"""Proje kökündeki sürümü `surumler/<SURUM>/` içine paketleyip kurar (ilk kurulum / yerel güncelleme yolu).

Adımlar: kökte manifest.json üretilir → guncelleme.guncelle(kök, kök): manifestteki dosyalar surumler/<SURUM>/
içine kopyalanır, doğrulanır, duman testinden geçer, guncel.json atomik yazılır ve eski sürümlerin YALNIZCA kendi
manifestlerindeki dosyaları silinir. Kökteki (git) dosyalara ve kullanıcı verisine hiç dokunulmaz.
Başarısız olursa eski sürüm ve guncel.json aynen kalır.

Aynı SURUM ile içerik değiştiyse kurulum reddedilir: önce surum.py içindeki SURUM'u artır.

Kullanım:  python araclar\surum_paketle.py
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
import guncelleme  # noqa: E402


def main(argumanlar=None):
    kok = Path(argumanlar[0]) if argumanlar else KOK
    manifest = guncelleme.manifest_uret(kok)
    guncelleme.manifest_yaz(kok, manifest)
    print(f"Manifest üretildi: sürüm {manifest['surum']}, {len(manifest['dosyalar'])} dosya")
    try:
        sonuc = guncelleme.guncelle(kok, kok)
    except guncelleme.GuncellemeHatasi as h:
        print(f"Kurulum yapılmadı, eski sürüm yerinde: {h}")
        return 1
    print(f"Kuruldu: {sonuc['yol']} (kopyalandı: {'evet' if sonuc['kopyalandi'] else 'zaten vardı'})")
    print(f"Eski sürümlerden silinen: {len(sonuc['silinen'])} dosya; atlanan: {len(sonuc['atlanan'])}")
    for a in sonuc["atlanan"]:
        print(f"  atlandı: {a['yol']} ({a['neden']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
