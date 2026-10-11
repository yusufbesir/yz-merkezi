# Masaüstünde "Yapay Zeka Merkezi.lnk" kısayolu oluşturur (hedef: pythonw.exe masaustu_sunucu.py).
# Kullanım: sağ tık > "PowerShell ile Çalıştır" ya da  powershell -ExecutionPolicy Bypass -File kisayol-olustur.ps1
$ErrorActionPreference = 'Stop'
$proje = $PSScriptRoot
$komut = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if (-not $komut) { throw "pythonw.exe bulunamadı. Python'u PATH'e ekleyerek kur." }
$simge = Join-Path $proje 'arayuz-masaustu\simge.ico'
if (-not (Test-Path $simge)) { throw "Simge bulunamadı: $simge (önce python araclar\simge_uret.py çalıştır)." }
$masaustu = [Environment]::GetFolderPath('Desktop')
$yol = Join-Path $masaustu 'Yapay Zeka Merkezi.lnk'
$kabuk = New-Object -ComObject WScript.Shell
$kisayol = $kabuk.CreateShortcut($yol)
$kisayol.TargetPath = $komut.Source
$kisayol.Arguments = 'masaustu_sunucu.py'
$kisayol.WorkingDirectory = $proje
$kisayol.IconLocation = "$simge,0"
$kisayol.Description = 'Yapay Zeka Merkezi'
$kisayol.Save()
Write-Host "Kısayol oluşturuldu: $yol"
