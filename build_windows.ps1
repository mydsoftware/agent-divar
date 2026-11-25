# ساخت نسخه اجرایی مستقل Agent Divar برای ویندوز
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
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
Write-Host "ساخت نسخه اجرایی و آزمون دود موفق بود." -ForegroundColor Green
Write-Host "مسیر خروجی: $Output"
