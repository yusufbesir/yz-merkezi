#!/usr/bin/env python3
"""Proje kökündeki uygulama dosyalarının manifest.json dosyasını üretir (güncelleme doğrulaması için).

Yalnızca uygulama dosyaları girer: kökteki .py/.json/.bat/.ps1/.md ile arayuz/, arayuz-masaustu/, motorlar/,
araclar/ klasörleri. Veri ve ayar dosyaları (ayarlar*.json, masaustu-ayarlar*.json, *.log, tarayıcı profili,
veri, kasa), .git, testler/, __pycache__ ve surumler/ HARİÇ tutulur (bkz. guncelleme.KORUNAN_KALIPLAR).

Kullanım:  python araclar\manifest_uret.py [KLASOR]     (varsayılan: proje kökü)
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
    a = sys.argv[1:] if argumanlar is None else argumanlar
    klasor = Path(a[0]) if a else KOK
    manifest = guncelleme.manifest_uret(klasor)
    guncelleme.manifest_yaz(klasor, manifest)
    print(f"manifest.json yazıldı: {klasor / guncelleme.MANIFEST} (sürüm {manifest['surum']}, "
          f"{len(manifest['dosyalar'])} dosya)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
