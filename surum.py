"""Uygulamanın sürüm bilgisi (semver). Güncelleme düzeni (guncelleme.py) ve /api/kimlik bunu kullanır.

Yeni bir sürüm paketlenmeden önce SURUM artırılır; aynı sürüm numarasıyla farklı içerik kurulamaz.
Yalnızca standart kütüphane; içe aktarılırken yan etkisi yoktur.
"""
UYGULAMA = "yz-merkezi"
SURUM = "1.1.0"


def kimlik():
    """`/api/kimlik` yanıtı: uygulama adı ve sürümü (belirteçsiz uç; gizli bilgi içermez)."""
    return {"uygulama": UYGULAMA, "surum": SURUM}
