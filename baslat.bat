@echo off
cd /d "%~dp0"
rem guncel.json varsa etkin surum (surumler\SURUM) baslatilir; yoksa bu klasor calistirilir.
if exist "guncel.json" (
  start "" pythonw guncelleme.py --baslat
) else (
  start "" pythonw masaustu_sunucu.py
)
