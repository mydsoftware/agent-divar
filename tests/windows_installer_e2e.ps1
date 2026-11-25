# آزمون نصب، ارتقا، اجرای بی‌پنجره و حذف نصب Agent Divar
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content (Join-Path $ProjectRoot "VERSION") -Raw).Trim()
$Setup = Join-Path $ProjectRoot "dist\AgentDivar-Setup-$Version-x64.exe"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\AgentDivar"
$DataDir = Join-Path $env:LOCALAPPDATA "AgentDivar\data"
$StartMenuLink = Join-Path ([Environment]::GetFolderPath("Programs")) "Agent Divar\Agent Divar.lnk"
$DesktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "Agent Divar.lnk"
$LogDir = Join-Path $ProjectRoot "artifacts\windows-e2e"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Start-Transcript -Path (Join-Path $LogDir "installer-e2e.log") -Force
try {
    if (-not (Test-Path $Setup)) { throw "فایل نصب‌کننده پیدا نشد: $Setup" }
    Write-Host "مرحله ۱: نصب تمیز"
    $p = Start-Process -FilePath $Setup -ArgumentList @("/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/CURRENTUSER","/TASKS=desktopicon") -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "نصب‌کننده با کد $($p.ExitCode) خارج شد." }
    $Exe = Join-Path $InstallDir "AgentDivar.exe"
    if (-not (Test-Path $Exe)) { throw "فایل اجرایی در مسیر نصب وجود ندارد." }
    if (-not (Test-Path $StartMenuLink)) { throw "میانبر منوی شروع ساخته نشده است: $StartMenuLink" }
    if (-not (Test-Path $DesktopLink)) { throw "میانبر دسکتاپ ساخته نشده است: $DesktopLink" }
    Write-Host "مرحله ۲: اجرای آزمون دود EXE نصب‌شده"
    & $Exe --self-test
    if ($LASTEXITCODE -ne 0) { throw "آزمون دود EXE نصب‌شده ناموفق بود." }
    Write-Host "مرحله ۳: ساخت داده آزمایشی و شبیه‌سازی ارتقا"
    New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "property-media") | Out-Null
    $marker = Join-Path $DataDir "e2e-user-data-marker.txt"
    Set-Content -Path $marker -Value "keep-user-data-$Version" -Encoding UTF8
    Set-Content -Path (Join-Path $DataDir "settings.json") -Value '{"theme":"clam","font_size":12,"export_directory":"","diagnostics_enabled":true}' -Encoding UTF8
    Set-Content -Path (Join-Path $DataDir "property-media\e2e-media.txt") -Value "media-preservation-check" -Encoding UTF8
    $p = Start-Process -FilePath $Setup -ArgumentList @("/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/CURRENTUSER","/TASKS=desktopicon") -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "نصب مجدد/ارتقا با کد $($p.ExitCode) شکست خورد." }
    foreach ($path in @($marker,(Join-Path $DataDir "settings.json"),(Join-Path $DataDir "property-media\e2e-media.txt"))) {
        if (-not (Test-Path $path)) { throw "داده کاربر در جریان ارتقا از بین رفته است: $path" }
    }
    & $Exe --self-test
    if ($LASTEXITCODE -ne 0) { throw "آزمون دود پس از ارتقا ناموفق بود." }
    Write-Host "مرحله ۴: حذف نصب و بررسی حفظ داده‌ها"
    $Uninstaller = Join-Path $InstallDir "unins000.exe"
    if (-not (Test-Path $Uninstaller)) { throw "فایل حذف نصب پیدا نشد." }
    $p = Start-Process -FilePath $Uninstaller -ArgumentList @("/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART") -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "حذف نصب با کد $($p.ExitCode) شکست خورد." }
    if (Test-Path $Exe) { throw "فایل اجرایی پس از حذف نصب باقی مانده است." }
    if (-not (Test-Path $marker)) { throw "حذف نصب داده‌های کاربر را پاک کرده است." }
    if (-not (Test-Path (Join-Path $DataDir "property-media\e2e-media.txt"))) { throw "رسانه کاربر پس از حذف نصب باقی نمانده است." }
    Write-Host "آزمون نصب، ارتقا، اجرا و حذف نصب موفق بود." -ForegroundColor Green
}
finally {
    Stop-Transcript
}
