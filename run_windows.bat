@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 app.py
    ) else (
        python app.py
    )
)
if errorlevel 1 (
    echo.
    echo اجرای برنامه با خطا مواجه شد. برای نصب وابستگی‌ها install_windows.ps1 را اجرا کنید.
)
pause
