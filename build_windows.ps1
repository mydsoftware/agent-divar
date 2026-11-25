# ساخت نسخه اجرایی مستقل Agent Divar برای ویندوز
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = (Get-Content (Join-Path $ProjectRoot "VERSION") -Raw).Trim()
if ($Version -notmatch "^\d+\.\d+\.\d+$") { throw "نسخه VERSION معتبر نیست." }
Set-Location $ProjectRoot
Write-Host "نصب وابستگی‌های برنامه و بسته‌ساز..." -ForegroundColor Cyan
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "نصب وابستگی‌های برنامه ناموفق بود." }
python -m pip install "pyinstaller>=6.10,<7"
if ($LASTEXITCODE -ne 0) { throw "نصب PyInstaller ناموفق بود." }
$BrowserCache = Join-Path $ProjectRoot ".playwright-browsers"
$env:PLAYWRIGHT_BROWSERS_PATH = $BrowserCache
Write-Host "دریافت Chromium..." -ForegroundColor Cyan
python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "دریافت Chromium ناموفق بود." }
Write-Host "ساخت نسخه اجرایی..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm AgentDivar.spec
if ($LASTEXITCODE -ne 0) { throw "ساخت EXE ناموفق بود." }
$Output = Join-Path $ProjectRoot "dist\AgentDivar"
$BundledBrowsers = Join-Path $Output "ms-playwright"
if (Test-Path $BundledBrowsers) { Remove-Item $BundledBrowsers -Recurse -Force }
Copy-Item $BrowserCache $BundledBrowsers -Recurse
$Executable = Join-Path $Output "AgentDivar.exe"
if (-not (Test-Path $Executable)) { throw "فایل AgentDivar.exe ساخته نشده است." }
Write-Host "اجرای آزمون دود نسخه اجرایی..." -ForegroundColor Cyan
& $Executable --self-test
if ($LASTEXITCODE -ne 0) { throw "آزمون دود نسخه اجرایی ناموفق بود." }
Write-Host "ساخت بسته Portable..." -ForegroundColor Cyan
$PortableZip = Join-Path $ProjectRoot "dist\AgentDivar-Portable-$Version-x64.zip"
if (Test-Path $PortableZip) { Remove-Item $PortableZip -Force }
Compress-Archive -Path (Join-Path $Output "*") -DestinationPath $PortableZip -CompressionLevel Optimal
$IsccCandidates = @(
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
) | Where-Object { $_ -and (Test-Path $_) }
if (-not $IsccCandidates) { throw "Inno Setup 6 پیدا نشد؛ برای ساخت نصب‌کننده آن را نصب کنید." }
$Iscc = $IsccCandidates[0]
$InstallerScript = Join-Path $ProjectRoot "installer\AgentDivar.iss"
& $Iscc "/DMyAppVersion=$Version" $InstallerScript
if ($LASTEXITCODE -ne 0) { throw "ساخت نصب‌کننده Inno Setup ناموفق بود." }
$Setup = Join-Path $ProjectRoot "dist\AgentDivar-Setup-$Version-x64.exe"
if (-not (Test-Path $Setup)) { throw "فایل نصب‌کننده ساخته نشده است." }
Write-Host "ساخت EXE، Portable و نصب‌کننده موفق بود." -ForegroundColor Green
Write-Host "پوشه برنامه: $Output"
Write-Host "بسته Portable: $PortableZip"
Write-Host "نصب‌کننده: $Setup"
