@echo off
rem Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
rem Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
rem ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
rem Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.
cd /d "%~dp0"
rem guncel.json varsa etkin surum (surumler\SURUM) baslatilir; yoksa bu klasor calistirilir.
if exist "guncel.json" (
  start "" pythonw guncelleme.py --baslat
) else (
  start "" pythonw masaustu_sunucu.py
)
