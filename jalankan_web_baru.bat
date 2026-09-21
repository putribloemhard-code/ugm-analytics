@echo off
REM ============================================================
REM  Pratinjau LOKAL tampilan web baru (React) dengan data MySQL
REM  yang sama dengan dashboard Streamlit.
REM
REM  Membuka 2 jendela:
REM    - API  (FastAPI ke MySQL lokal dari .env)  http://127.0.0.1:8000
REM    - Web  (Vite dev server)                   http://127.0.0.1:3000
REM  Dashboard Streamlit tetap di http://localhost:8766 (jalankan
REM  seperti biasa) -- keduanya bisa dibuka berdampingan.
REM
REM  Prasyarat: MySQL menyala, .env root terisi (MYSQL_*), Node.js dan Python.
REM  Catatan: registrasi akun & upload akreditasi tidak jalan di mode ini
REM  (butuh Postgres); buat akun lewat Streamlit. Lihat web\dev_api_mysql.py.
REM  Tutup kedua jendela untuk berhenti.
REM ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Membuat lingkungan Python terpisah .venv dan memasang dependency API...
  python -m venv .venv || goto :gagal
  ".venv\Scripts\python.exe" -m pip install -r api\requirements.txt || goto :gagal
)
if not exist "web\node_modules" (
  echo [2/3] Memasang dependency web...
  pushd web
  call npm ci || (popd & goto :gagal)
  popd
)

echo [3/3] Menjalankan API dan web...
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
