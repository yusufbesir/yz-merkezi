"""Test ortamı korumaları: testler gerçek ayar dosyalarına, tarayıcı profiline ve kullanıcı klasörüne dokunmasın.

Sunucu modülleri bu ortam değişkenlerini İÇE AKTARILIRKEN okur; bu yüzden test dosyaları sunucu modüllerinden
ÖNCE `import _ortam` (paket olarak yüklenirse `testler/__init__.py`) çalıştırır. Ortamda gerçek bir yol tanımlı
olsa bile testlerde her zaman geçici yollar kullanılır (koşulsuz atama).
"""
import atexit
import os
import shutil
import tempfile
from pathlib import Path

GECICI_KLASOR = Path(tempfile.mkdtemp(prefix="yztest_"))
atexit.register(shutil.rmtree, GECICI_KLASOR, ignore_errors=True)

for _ad, _yol in (("YZ_MASAUSTU_AYAR", "masaustu-ayarlar.json"),
                  ("YZ_AYAR_DOSYASI", "ayarlar.json"),
                  ("YZ_TARAYICI_PROFILI", "tarayici-profili"),
                  ("YZ_VERI_KLASORU", "veri")):  # belirtec ve hata.log
    os.environ[_ad] = str(GECICI_KLASOR / _yol)

# Hafıza OS kasası: testler gerçek kasaya (D:\YusufII\HAFIZAM1\kasa) ne okumak ne yazmak için dokunmasın.
# Bu klasör bilerek oluşturulmaz; hafiza_kopru testleri kendi geçici kasalarını YZ_KASA ile kurar.
os.environ["YZ_KASA"] = str(GECICI_KLASOR / "kasa-yok")

# Jev (jev.py): testler gerçek komuta/jev.json'a ve gerçek anahtar dosyasına dokunmasın, gerçek Jev'e istek gitmesin.
# Bu dosya bilerek oluşturulmaz (Jev "hazır değil" → kural tabanlı yol); test_jev.py kendi geçici ayarını kurar.
# setdefault değil: ortamda gerçek bir yol tanımlı olsa bile testlerde her zaman geçici yol kullanılır.
os.environ["YZ_JEV_AYAR"] = str(GECICI_KLASOR / "jev-yok" / "jev.json")
