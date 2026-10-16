# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

# Masaüstünde "Yapay Zeka Merkezi.lnk" kısayolu oluşturur (hedef: pythonw.exe masaustu_sunucu.py;
# guncel.json varsa pythonw.exe guncelleme.py --baslat: etkin sürüm (surumler\<surum>) başlatılır).
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
if (Test-Path (Join-Path $proje 'guncel.json')) { $kisayol.Arguments = 'guncelleme.py --baslat' } else { $kisayol.Arguments = 'masaustu_sunucu.py' }
$kisayol.WorkingDirectory = $proje
$kisayol.IconLocation = "$simge,0"
$kisayol.Description = 'Yapay Zeka Merkezi'
$kisayol.Save()
Write-Host "Kısayol oluşturuldu: $yol"
