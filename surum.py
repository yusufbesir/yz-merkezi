"""Uygulamanın sürüm bilgisi (semver). Güncelleme düzeni (guncelleme.py) ve /api/kimlik bunu kullanır.

Yeni bir sürüm paketlenmeden önce SURUM artırılır; aynı sürüm numarasıyla farklı içerik kurulamaz.
Yalnızca standart kütüphane; içe aktarılırken yan etkisi yoktur.
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

UYGULAMA = "yz-merkezi"
SURUM = "1.1.0"


def kimlik():
    """`/api/kimlik` yanıtı: uygulama adı ve sürümü (belirteçsiz uç; gizli bilgi içermez)."""
    return {"uygulama": UYGULAMA, "surum": SURUM}
