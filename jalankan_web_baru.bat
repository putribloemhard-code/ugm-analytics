@echo off
REM ============================================================
REM  Menjalankan UGM Analytics secara LOKAL (satu-satunya cara
REM  sejak dashboard Streamlit dihapus 2026-09-23).
REM
REM  Membuka 2 jendela:
REM    - API  (FastAPI ke MySQL lokal dari .env)  http://127.0.0.1:8000
REM    - Web  (Vite dev server)                   http://127.0.0.1:3000
REM
REM  Semua fitur jalan di mode ini: Analisis Dampak, login &
REM  registrasi, serta Akreditasi (isi data, upload, ekstraksi AI
REM  kalau OPENAI_API_KEY ada di .env, generate Word). File upload &
REM  laporan Word tersimpan di akreditasi\data\. Lihat
REM  web\dev_api_mysql.py.
REM
REM  Prasyarat: Node.js, Python, dan servis MySQL80.
REM  Tutup kedua jendela untuk berhenti.
REM ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Membuat lingkungan Python terpisah .venv...
  python -m venv .venv || goto :gagal
)
REM Selalu dicek (cepat bila sudah lengkap): .venv lama tetap dapat dependency baru.
echo [1/4] Memastikan dependency API terpasang...
".venv\Scripts\python.exe" -m pip install -q -r api\requirements.txt || goto :gagal
if not exist "web\node_modules" (
  echo [2/4] Memasang dependency web...
  pushd web
  call npm ci || (popd & goto :gagal)
  popd
)

REM ---- [3/4] Pastikan MySQL menyala. Ini penyebab paling sering halaman tampak kosong. ----
sc query MySQL80 | find "RUNNING" >nul
if not errorlevel 1 goto :mysql_siap

echo [3/4] MySQL belum menyala -- mencoba menyalakan (perlu izin admin)...
net start MySQL80 >nul 2>&1
sc query MySQL80 | find "RUNNING" >nul
if not errorlevel 1 goto :mysql_siap

echo.
echo   PERINGATAN: MySQL (servis MySQL80) belum menyala dan tidak bisa dinyalakan
echo   dari skrip ini (butuh hak Administrator).
echo.
echo   Tanpa MySQL, halaman akan terbuka tetapi isinya kosong / muncul
echo   pesan "Basis data tidak dapat dihubungi".
echo.
echo   Cara menyalakan (pilih salah satu):
echo     1. Buka "Services" (tekan Win+R, ketik services.msc, Enter),
echo        cari "MySQL80", klik kanan - Start.
echo     2. Klik kanan Command Prompt - Run as administrator, lalu jalankan:
echo          net start MySQL80
echo.
echo   Setelah MySQL menyala, jalankan ulang file ini.
echo.
pause
goto :jalankan

:mysql_siap
echo [3/4] MySQL menyala.

:jalankan
echo [4/4] Menjalankan API dan web...
start "UGM API (MySQL lokal)" /D "%~dp0" cmd /k ".venv\Scripts\python.exe web\dev_api_mysql.py"
start "UGM Web baru" /D "%~dp0web" cmd /k "npm run dev"
timeout /t 6 /nobreak >nul
start "" http://127.0.0.1:3000/
exit /b 0

:gagal
echo.
echo Gagal. Periksa pesan di atas.
pause
exit /b 1
