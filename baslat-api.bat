@echo off
chcp 65001 >nul
rem Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
rem Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
rem ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
rem Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.
title Yapay Zeka Merkezi
cd /d "%~dp0"
python sunucu.py
if errorlevel 1 pause
