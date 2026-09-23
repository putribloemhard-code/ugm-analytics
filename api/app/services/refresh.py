"""Picu & pantau update data berita (berita-dampak/scripts/update_mingguan.py) dari web.

Padanan tombol "🔄 Update Berita Terbaru" dashboard Streamlit lama: pipeline dijalankan sebagai
proses terpisah (API tidak menunggu), output ke logs_update_dashboard.txt. update_mingguan.py
sendiri menulis lock `berita-dampak/data/.update_lock` berisi PID-nya, jadi tombol ini dan cron
mingguan tidak pernah jalan bersamaan.

Pipeline butuh dependensi venv pipeline (`venv/`: requests, bs4, plotly, ...), BUKAN `.venv`
API -- interpreter diambil dari env UGM_ANALYTICS_PYTHON atau `venv/` di root repo. Kalau tidak
ada (mis. container API produksi), tombol dinonaktifkan (`trigger_available: false`).
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.source import REPO_ROOT

BERITA_DIR = REPO_ROOT / "berita-dampak"
SCRIPT = BERITA_DIR / "scripts" / "update_mingguan.py"
LOCK = BERITA_DIR / "data" / ".update_lock"
LOG = BERITA_DIR / "logs_update_dashboard.txt"
LOG_TAIL_LINES = 25


class RefreshError(RuntimeError):
    """Update tidak bisa dimulai (409/503)."""


def pipeline_python() -> Path | None:
    env = os.environ.get("UGM_ANALYTICS_PYTHON")
    candidates = [Path(env)] if env else [REPO_ROOT / "venv" / "Scripts" / "python.exe", REPO_ROOT / "venv" / "bin" / "python"]
    return next((p for p in candidates if p.is_file()), None)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # os.kill(pid, 0) di Windows justru MEMBUNUH proses -- pakai OpenProcess + GetExitCodeProcess.
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_pid() -> int | None:
    try:
        return int(LOCK.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return None


def _tail(path: Path, n: int) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [line for line in lines if line.strip()][-n:]


def status(updated_at: str | None = None) -> dict[str, Any]:
    running, stale = False, False
    if LOCK.exists():
        pid = _lock_pid()
        running = pid is not None and _pid_alive(pid)
        stale = not running
    log_time = datetime.fromtimestamp(LOG.stat().st_mtime).isoformat(timespec="seconds") if LOG.exists() else None
    tail = _tail(LOG, LOG_TAIL_LINES)
    selesai = next((line for line in reversed(tail) if line.startswith("=== SELESAI")), None)
    return {
        "status": "running" if running else ("stale_lock" if stale else ("finished" if selesai else "idle")),
        "updated_at": updated_at,
        "trigger_available": pipeline_python() is not None and SCRIPT.is_file(),
        "log_updated_at": log_time,
        "last_exit": (0 if "(exit 0)" in selesai else 1) if selesai else None,
        "log_tail": tail,
    }


def start() -> dict[str, Any]:
    python = pipeline_python()
    if python is None or not SCRIPT.is_file():
        raise RefreshError("Update tidak tersedia di server ini (venv pipeline tidak ditemukan; set UGM_ANALYTICS_PYTHON).")
    if LOCK.exists():
        pid = _lock_pid()
        if pid is not None and _pid_alive(pid):
            raise RefreshError(f"Update lain sedang berjalan (PID {pid}). Tunggu sampai selesai.")
        LOCK.unlink(missing_ok=True)  # lock yatim: proses sebelumnya mati tanpa sempat membersihkan
    log = open(LOG, "w", encoding="utf-8")  # noqa: SIM115 -- diwariskan ke proses anak
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    env = {**os.environ, "UGM_ANALYTICS_PYTHON": str(python), "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.Popen([str(python), "-u", str(SCRIPT)], cwd=str(BERITA_DIR), stdout=log,
                                stderr=subprocess.STDOUT, creationflags=flags, env=env,
                                start_new_session=sys.platform != "win32")
    finally:
        log.close()
    return {"pid": proc.pid, "message": "Update dimulai di latar belakang (±10 menit)."}
