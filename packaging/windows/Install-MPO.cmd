@echo off
rem Nakładka dla nietechnicznych użytkowników: podwójny klik = instalacja.
rem (uruchamia install.ps1 z pominięciem polityki wykonywania skryptów)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
