"""Test ortamı korumaları: testler gerçek ayar dosyalarına, tarayıcı profiline ve kullanıcı klasörüne dokunmasın.

Sunucu modülleri bu ortam değişkenlerini İÇE AKTARILIRKEN okur; bu yüzden test dosyaları sunucu modüllerinden
ÖNCE `import _ortam` (paket olarak yüklenirse `testler/__init__.py`) çalıştırır. Değişken ortamda zaten varsa
dokunulmaz.
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
    os.environ.setdefault(_ad, str(GECICI_KLASOR / _yol))
