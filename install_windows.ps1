# نصب و راه‌اندازی Agent Divar در ویندوز
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "بررسی Python..." -ForegroundColor Cyan
$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) {
    & py -3.11 --version
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11 نصب نیست. ابتدا Python 3.11 را نصب کنید." }
    $PythonCommand = "py"
} else {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Python) { throw "Python 3.11 نصب نیست." }
    & python --version
    if ($LASTEXITCODE -ne 0) { throw "اجرای Python ناموفق بود." }
    $PythonCommand = "python"
}

if (-not (Test-Path ".venv")) {
    if ($PythonCommand -eq "py") { & py -3.11 -m venv .venv }
    else { & python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw "ساخت محیط مجازی ناموفق بود." }
}
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Write-Host "نصب وابستگی‌ها..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "به‌روزرسانی pip ناموفق بود." }
& $VenvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "نصب وابستگی‌ها ناموفق بود." }
Write-Host "نصب مرورگر Chromium برای Playwright..." -ForegroundColor Cyan
& $VenvPython -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "نصب Chromium ناموفق بود." }

$Launcher = Join-Path $ProjectRoot "run_windows.bat"
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Agent Divar.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,1"
$Shortcut.Save()

Write-Host "نصب تمام شد. میانبر Agent Divar روی دسکتاپ ساخته شد." -ForegroundColor Green
Write-Host "برای اجرا، میانبر یا run_windows.bat را باز کنید."
