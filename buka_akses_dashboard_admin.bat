@echo off
title Buka Akses Dashboard Streamlit (Firewall)
REM ============================================================
REM  Membuka port 8766 di Windows Firewall agar dashboard
REM  Streamlit bisa dibuka dari laptop lain di jaringan yang sama.
REM  Double-click file ini -> muncul prompt UAC -> klik Yes.
REM ============================================================

REM Cek apakah sudah admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Meminta izin administrator...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Menambahkan rule firewall untuk port 8766...
netsh advfirewall firewall add rule name="Streamlit 8766" dir=in action=allow protocol=TCP localport=8766

echo.
echo Selesai. Cek hasil:
netsh advfirewall firewall show rule name="Streamlit 8766"

echo.
echo Sekarang laptop lain di jaringan yang sama bisa buka:
echo   http://10.73.1.179:8766
echo.
pause
