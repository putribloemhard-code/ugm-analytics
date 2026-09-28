from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.responses import Response

from app.api.v1.schemas import AnalyticsResponse, ReportRequest, SearchResponse
from app.config import settings
from app.db import get_engine
from app.domain.models import FilterParams
from app.domain.search import parse_search
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def service() -> AnalyticsService:
    try:
        return AnalyticsService(get_engine())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def parse_list(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_int_list(value: str | None) -> tuple[int, ...]:
    values = parse_list(value)
    try:
        numbers = tuple(int(value) for value in values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="SDG values must be integers") from exc
    if any(value < 1 or value > 17 for value in numbers):
        raise HTTPException(status_code=422, detail="SDG values must be between 1 and 17")
    return numbers


def filters(
    year_from: str | None = Query(default=None),
    year_to: str | None = Query(default=None),
    pillars: str | None = Query(default=None),
    topics: str | None = Query(default=None),
    sdgs: str | None = Query(default=None),
    units: str | None = Query(default=None),
) -> FilterParams:
    if year_from and (len(year_from) != 4 or not year_from.isdigit()):
        raise HTTPException(status_code=422, detail="year_from must be a four-digit year")
    if year_to and (len(year_to) != 4 or not year_to.isdigit()):
        raise HTTPException(status_code=422, detail="year_to must be a four-digit year")
    if year_from and year_to and year_from > year_to:
        raise HTTPException(status_code=422, detail="year_from cannot be after year_to")
    return FilterParams(
        year_from=year_from,
        year_to=year_to,
        pillars=parse_list(pillars),
        topics=parse_list(topics),
        sdgs=parse_int_list(sdgs),
        units=parse_list(units),
    )


@router.get("/metadata")
def metadata(api: AnalyticsService = Depends(service)):
    return api.metadata()


@router.get("/accreditation")
def accreditation(api: AnalyticsService = Depends(service)):
    try:
        from app.services.accreditation import AccreditationService
        acc = AccreditationService(api.engine)
        return acc.full_read_model()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Accreditation data is unavailable") from exc


def _auth_user(request: Request, api: AnalyticsService):
    from app.services.accreditation_auth import user_from_token, COOKIE_NAME
    user = user_from_token(api.engine, request.cookies.get(COOKIE_NAME))
    if not user:
        raise HTTPException(status_code=401, detail="Login akreditasi diperlukan")
    return user


@router.post("/accreditation/auth/register")
def accreditation_register(payload: dict[str, str], api: AnalyticsService = Depends(service)):
    from app.services.accreditation_auth import register
    ok, message = register(api.engine, payload.get("email", ""), payload.get("name", ""), payload.get("password", ""))
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


@router.post("/accreditation/auth/login")
def accreditation_login(payload: dict[str, str], api: AnalyticsService = Depends(service)):
    from app.services.accreditation_auth import COOKIE_NAME, login
    user, message, token = login(api.engine, payload.get("email", ""), payload.get("password", ""))
    if not user or not token:
        raise HTTPException(status_code=401, detail=message or "Login gagal")
    response = JSONResponse({"user": user})
    response.set_cookie(COOKIE_NAME, token, max_age=43200, httponly=True, samesite="strict", secure=False, path="/")
    return response


@router.get("/accreditation/auth/me")
def accreditation_me(request: Request, api: AnalyticsService = Depends(service)):
    return {"user": _auth_user(request, api)}


@router.post("/accreditation/auth/logout")
def accreditation_logout(request: Request, api: AnalyticsService = Depends(service)):
    from app.services.accreditation_auth import COOKIE_NAME, logout
    logout(api.engine, request.cookies.get(COOKIE_NAME))
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


def _dampak_auth_user(request: Request, api: AnalyticsService):
    from app.services.dampak_auth import user_from_token, COOKIE_NAME
    user = user_from_token(api.engine, request.cookies.get(COOKIE_NAME))
    if not user:
        raise HTTPException(status_code=401, detail="Login Analisis Dampak diperlukan")
    return user


@router.post("/dampak/auth/register")
def dampak_register(payload: dict[str, str], api: AnalyticsService = Depends(service)):
    from app.services.dampak_auth import ensure_schema, register
    ensure_schema(api.engine)
    ok, message = register(api.engine, payload.get("email", ""), payload.get("name", ""), payload.get("password", ""))
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


@router.post("/dampak/auth/login")
def dampak_login(payload: dict[str, str], api: AnalyticsService = Depends(service)):
    from app.services.dampak_auth import COOKIE_NAME, ensure_schema, login
    ensure_schema(api.engine)
    user, message, token = login(api.engine, payload.get("email", ""), payload.get("password", ""))
    if not user or not token:
        raise HTTPException(status_code=401, detail=message or "Login gagal")
    response = JSONResponse({"user": user})
    response.set_cookie(COOKIE_NAME, token, max_age=43200, httponly=True, samesite="strict", secure=False, path="/")
    return response


@router.get("/dampak/auth/me")
def dampak_me(request: Request, api: AnalyticsService = Depends(service)):
    return {"user": _dampak_auth_user(request, api)}


@router.post("/dampak/auth/logout")
def dampak_logout(request: Request, api: AnalyticsService = Depends(service)):
    from app.services.dampak_auth import COOKIE_NAME, logout
    logout(api.engine, request.cookies.get(COOKIE_NAME))
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


# ------------------------------------------------------------------ masuk dengan Google (dua portal)
@router.get("/auth/google/status")
def google_status():
    from app.services.google_login import aktif
    return {"aktif": aktif()}


def _google_gagal(request: Request, portal: str, pesan: str) -> RedirectResponse:
    from urllib.parse import quote
    from app.services.google_login import PORTAL, STATE_COOKIE
    path = PORTAL.get(portal, PORTAL["akreditasi"])["path"]
    response = RedirectResponse(f"{_base_url(request)}{path}?google_error={quote(pesan)}", status_code=303)
    response.delete_cookie(STATE_COOKIE, path="/")
    response.delete_cookie(STATE_COOKIE + "_next", path="/")
    return response


@router.get("/auth/google/start")
def google_start(request: Request, portal: str = Query(..., max_length=16), next: str = Query("", max_length=512)):
    from app.services.google_login import STATE_AGE, STATE_COOKIE, GoogleLoginError, mulai, redirect_uri, tujuan_aman
    try:
        url, state = mulai(portal, redirect_uri(_base_url(request)))
    except GoogleLoginError as exc:
        return _google_gagal(request, portal, str(exc))
    response = RedirectResponse(url, status_code=303)
    # SameSite=Lax: cookie ini harus ikut terkirim saat Google mengarahkan browser kembali ke callback.
    response.set_cookie(STATE_COOKIE, state, max_age=STATE_AGE, httponly=True, samesite="lax",
                        secure=_base_url(request).startswith("https://"), path="/")
    if tujuan_aman(portal, next):
        response.set_cookie(STATE_COOKIE + "_next", next, max_age=STATE_AGE, httponly=True, samesite="lax",
                            secure=_base_url(request).startswith("https://"), path="/")
    return response


@router.get("/auth/google/callback")
def google_callback(request: Request, code: str = Query("", max_length=2048), state: str = Query("", max_length=256),
                    error: str = Query("", max_length=256), api: AnalyticsService = Depends(service)):
    from app.services import accreditation_auth, dampak_auth
    from app.services.google_login import PORTAL, STATE_COOKIE, GoogleLoginError, baca_cookie, redirect_uri, selesaikan, tujuan_aman
    cookie = baca_cookie(request.cookies.get(STATE_COOKIE))
    portal = cookie["portal"] if cookie else "akreditasi"
    if error:
        return _google_gagal(request, portal, "Login Google dibatalkan." if error == "access_denied" else "Google menolak permintaan login.")
    try:
        if portal == "dampak":
            dampak_auth.ensure_schema(api.engine)
        portal, _user, token = selesaikan(api.engine, code, state, cookie, redirect_uri(_base_url(request)))
    except GoogleLoginError as exc:
        return _google_gagal(request, portal, str(exc))
    except Exception:  # noqa: BLE001 -- jaringan ke Google putus dsb.; detailnya di log, bukan di URL
        logging.getLogger(__name__).exception("login Google gagal")
        return _google_gagal(request, portal, "Login Google gagal karena gangguan koneksi. Coba lagi.")
    nama_cookie = dampak_auth.COOKIE_NAME if portal == "dampak" else accreditation_auth.COOKIE_NAME
    tujuan = request.cookies.get(STATE_COOKIE + "_next", "")
    tujuan = tujuan if tujuan_aman(portal, tujuan) else PORTAL[portal]["path"]
    response = RedirectResponse(f"{_base_url(request)}{tujuan}", status_code=303)
    response.set_cookie(nama_cookie, token, max_age=43200, httponly=True, samesite="strict", secure=False, path="/")
    response.delete_cookie(STATE_COOKIE, path="/")
    response.delete_cookie(STATE_COOKIE + "_next", path="/")
    return response


# ------------------------------------------------------------------ lupa password (dua portal)
def _base_url(request: Request) -> str:
    """Alamat web untuk tautan reset: APP_BASE_URL (server) atau alamat yang dipakai browser (lokal)."""
    import os
    dasar = os.environ.get("APP_BASE_URL")
    if dasar:
        return dasar
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{request.headers.get('x-forwarded-host') or request.headers.get('host') or request.url.netloc}"


def _reset_call(fn, *args):
    from app.services.reset_password import ResetError
    try:
        return fn(*args)
    except ResetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/auth/lupa-password")
def lupa_password(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Kirim tautan reset ke email akun (Akreditasi atau Dampak). Jawaban sama walau email tidak terdaftar."""
    from app.services.reset_password import minta_reset
    return _reset_call(minta_reset, api.engine, str(payload.get("portal", "")), str(payload.get("email", "")), _base_url(request))


@router.get("/auth/reset-password")
def cek_reset_password(portal: str = Query(..., max_length=16), token: str = Query(..., max_length=128),
                       api: AnalyticsService = Depends(service)):
    """Cek tautan reset masih berlaku (untuk menampilkan email pemilik di halaman password baru)."""
    from app.services.reset_password import cek
    return _reset_call(cek, api.engine, portal, token)


@router.post("/auth/reset-password")
def simpan_reset_password(payload: dict[str, Any], api: AnalyticsService = Depends(service)):
    """Simpan password baru dari tautan reset; tautan sekali pakai dan semua sesi akun diakhiri."""
    from app.services.reset_password import reset
    return _reset_call(reset, api.engine, str(payload.get("portal", "")), str(payload.get("token", "")),
                       str(payload.get("password", "")))


@router.post("/accreditation/admin/users/{target_id}/reset-link")
def accreditation_admin_reset_link(target_id: int, request: Request, api: AnalyticsService = Depends(service)):
    """Admin Akreditasi membuat tautan reset untuk sebuah akun (jalur cadangan tanpa server email)."""
    user = _auth_user(request, api)
    from app.services.reset_password import buat_tautan_admin
    hasil = _reset_call(buat_tautan_admin, api.engine, "akreditasi", user, target_id, _base_url(request))
    _catat(api, "akreditasi", user, "tautan_reset", f"Membuat tautan reset password untuk {hasil['email']}")
    return hasil


def _catat(api: AnalyticsService, portal: str, user: dict[str, Any], aksi: str, keterangan: str,
           laporan_id: int | None = None) -> None:
    """Catat aktivitas yang sudah berhasil (lihat services/aktivitas.py); tidak pernah menggagalkan aksi."""
    from app.services.aktivitas import catat
    catat(api.engine, portal, user, aksi, keterangan, laporan_id)


def _nama_item(item_id: str) -> str:
    try:
        from app.services.accreditation_workspace import _registry
        return str(_registry().KEBUTUHAN_DATA.get(item_id, {}).get("nama") or item_id)
    except Exception:  # noqa: BLE001 -- nama hanya untuk teks log
        return item_id


def _admin_saja(user: dict[str, Any]) -> None:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Hanya admin.")


@router.get("/accreditation/admin/aktivitas")
def accreditation_admin_aktivitas(request: Request, api: AnalyticsService = Depends(service)):
    """Aktivitas terbaru portal Akreditasi (admin)."""
    user = _auth_user(request, api)
    _admin_saja(user)
    from app.services.aktivitas import daftar
    return {"aktivitas": daftar(api.engine, "akreditasi", limit=100)}


@router.get("/dampak/admin/aktivitas")
def dampak_admin_aktivitas(request: Request, api: AnalyticsService = Depends(service)):
    """Aktivitas terbaru portal Analisis Dampak (admin Dampak)."""
    user = _dampak_auth_user(request, api)
    _admin_saja(user)
    from app.services.aktivitas import daftar
    return {"aktivitas": daftar(api.engine, "dampak", limit=100)}


@router.post("/accreditation/admin/email-uji")
def accreditation_admin_email_uji(request: Request, api: AnalyticsService = Depends(service)):
    """Kirim email uji ke alamat admin sendiri untuk memeriksa pengaturan SMTP."""
    user = _auth_user(request, api)
    _admin_saja(user)
    from app.services.notifikasi import email_uji
    return email_uji("akreditasi", user["email"])


@router.post("/dampak/admin/email-uji")
def dampak_admin_email_uji(request: Request, api: AnalyticsService = Depends(service)):
    """Kirim email uji ke alamat admin Dampak sendiri."""
    user = _dampak_auth_user(request, api)
    _admin_saja(user)
    from app.services.notifikasi import email_uji
    return email_uji("dampak", user["email"])


def _dampak_admin_call(fn, *args):
    from app.services.accreditation_account import AksiDitolak
    try:
        return fn(*args)
    except AksiDitolak as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/dampak/admin/users")
def dampak_admin_users(request: Request, api: AnalyticsService = Depends(service)):
    """Daftar akun Analisis Dampak; hanya admin Dampak."""
    user = _dampak_auth_user(request, api)
    from app.services.dampak_account import DampakAccountService
    return _dampak_admin_call(DampakAccountService(api.engine).admin_overview, user)


@router.post("/dampak/admin/users/{target_id}/action")
def dampak_admin_action(target_id: int, payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Blokir/buka blokir, beri/cabut admin, atau hapus akun Analisis Dampak."""
    user = _dampak_auth_user(request, api)
    from app.services.dampak_account import DampakAccountService
    value = payload.get("value")
    hasil = _dampak_admin_call(DampakAccountService(api.engine).admin_action, user, str(payload.get("action", "")),
                               target_id, None if value is None else bool(value))
    _catat(api, "dampak", user, "admin_akun", str(hasil.get("message") or f"Aksi admin pada akun #{target_id}"))
    return hasil


@router.post("/dampak/admin/users/{target_id}/reset-link")
def dampak_admin_reset_link(target_id: int, request: Request, api: AnalyticsService = Depends(service)):
    """Admin Dampak membuat tautan reset untuk sebuah akun Dampak."""
    user = _dampak_auth_user(request, api)
    from app.services.reset_password import buat_tautan_admin
    hasil = _reset_call(buat_tautan_admin, api.engine, "dampak", user, target_id, _base_url(request))
    _catat(api, "dampak", user, "tautan_reset", f"Membuat tautan reset password untuk {hasil['email']}")
    return hasil


def _account_service(api: AnalyticsService):
    from app.services.accreditation_account import AccreditationAccountService
    return AccreditationAccountService(api.engine)


@router.get("/accreditation/profile")
def accreditation_profile(request: Request, api: AnalyticsService = Depends(service)):
    """Profil akun sendiri + pekerjaan berjalan + riwayat laporan (padanan page_profil.py)."""
    user = _auth_user(request, api)
    return _account_service(api).profile(user)


@router.get("/accreditation/admin/users")
def accreditation_admin_users(request: Request, api: AnalyticsService = Depends(service)):
    """Daftar seluruh akun + ringkasan; hanya admin (padanan page_admin.py)."""
    user = _auth_user(request, api)
    from app.services.accreditation_account import AksiDitolak
    try:
        return _account_service(api).admin_overview(user)
    except AksiDitolak as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/accreditation/admin/users/{target_id}/action")
def accreditation_admin_action(target_id: int, payload: dict[str, Any], request: Request,
                              api: AnalyticsService = Depends(service)):
    """Blokir/buka blokir, beri/cabut admin, atau hapus akun. Cek ulang di service, bukan di UI."""
    user = _auth_user(request, api)
    from app.services.accreditation_account import AksiDitolak
    action = str(payload.get("action", ""))
    value = payload.get("value")
    try:
        hasil = _account_service(api).admin_action(
            user, action, target_id, None if value is None else bool(value))
    except AksiDitolak as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    _catat(api, "akreditasi", user, "admin_akun", str(hasil.get("message") or f"Aksi admin pada akun #{target_id}"))
    return hasil


@router.post("/accreditation/uploads")
async def accreditation_upload(request: Request, laporan_id: int = Form(...), file: UploadFile = File(...), api: AnalyticsService = Depends(service)):
    user = _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, laporan_id)
    from app.services.accreditation_upload import MAX_UPLOAD_BYTES, UploadError, save_upload
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 25 MB")
    try:
        hasil = save_upload(api.engine, Path(settings.accreditation_upload_dir), laporan, file.filename or "file", file.content_type, data, user["email"])
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Upload gagal disimpan") from exc
    _catat(api, "akreditasi", user, "unggah", f"Mengunggah {file.filename or 'file'}", int(laporan["id"]))
    return hasil


def _workspace(api: AnalyticsService):
    from app.services.accreditation_workspace import AccreditationWorkspaceService
    return AccreditationWorkspaceService(
        api.engine,
        upload_root=Path(settings.accreditation_upload_dir),
        generated_root=Path(settings.accreditation_generated_dir),
    )


def _workspace_call(fn, *args, **kwargs):
    """Terjemahkan galat ruang kerja ke status HTTP yang bisa dibaca UI."""
    from app.services.accreditation_workspace import NotFound, WorkspaceError
    try:
        return fn(*args, **kwargs)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _docx(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _laporan_svc(api: AnalyticsService):
    from app.services.accreditation_laporan import LaporanService
    return LaporanService(api.engine)


def _laporan_call(fn, *args, **kwargs):
    """Terjemahkan galat laporan/kunci prodi ke status HTTP."""
    from app.services.accreditation_laporan import AksesDitolak, LaporanError, TidakDitemukan
    try:
        return fn(*args, **kwargs)
    except TidakDitemukan as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AksesDitolak as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LaporanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _token(request: Request) -> str | None:
    from app.services.accreditation_auth import COOKIE_NAME
    return request.cookies.get(COOKIE_NAME)


def _laporan_terbuka(request: Request, api: AnalyticsService, laporan_id: Any) -> dict[str, Any]:
    """Laporan yang password prodinya sudah dimasukkan di sesi login ini; 403 bila belum."""
    return _laporan_call(_laporan_svc(api).laporan, laporan_id, _token(request))


@router.get("/accreditation/laporan")
def accreditation_laporan_list(request: Request, prodi_id: str = Query(..., max_length=64),
                               dokumen: str = Query(default="LED", pattern="^(LED|LKPS)$"),
                               api: AnalyticsService = Depends(service)):
    """Riwayat laporan satu prodi + dokumen (terlihat semua akun) dan status kunci prodi di sesi ini."""
    user = _auth_user(request, api)
    return _laporan_call(_laporan_svc(api).daftar, prodi_id, dokumen, _token(request), user["email"])


@router.post("/accreditation/laporan")
def accreditation_laporan_create(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Buat laporan baru (prodi + dokumen + tahun); password prodi harus sudah dibuka di sesi ini."""
    user = _auth_user(request, api)
    hasil = _laporan_call(_laporan_svc(api).buat_laporan, str(payload.get("prodi_id", "")), str(payload.get("dokumen", "")),
                          payload.get("tahun"), str(payload.get("nama") or ""), _token(request), user["email"])
    _catat(api, "akreditasi", user, "buat_laporan", f"Membuat laporan {hasil.get('nama')} ({payload.get('prodi_id')})",
           int(hasil["id"]))
    return hasil


@router.post("/accreditation/laporan/{laporan_id}/hapus")
def accreditation_laporan_delete(laporan_id: int, request: Request, api: AnalyticsService = Depends(service)):
    """Hapus laporan beserta isian, file, dan riwayat Word-nya; PIN prodi harus sudah dibuka di sesi ini."""
    user = _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, laporan_id)
    hasil = _workspace_call(_workspace(api).hapus_laporan, laporan)
    _catat(api, "akreditasi", user, "hapus_laporan", str(hasil.get("message") or f"Menghapus laporan #{laporan_id}"))
    return hasil


@router.post("/accreditation/prodi/{prodi_id}/kunci")
def accreditation_kunci_buat(prodi_id: str, payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Buat password pertama prodi (hanya bila belum ada)."""
    user = _auth_user(request, api)
    hasil = _laporan_call(_laporan_svc(api).buat_kunci, prodi_id, str(payload.get("password", "")), _token(request), user["email"])
    _catat(api, "akreditasi", user, "buat_pin", f"Membuat PIN prodi {prodi_id}")
    return hasil


@router.post("/accreditation/prodi/{prodi_id}/buka")
def accreditation_kunci_buka(prodi_id: str, payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Masukkan password prodi; berlaku sampai logout / sesi login berakhir."""
    user = _auth_user(request, api)
    return _laporan_call(_laporan_svc(api).buka, prodi_id, str(payload.get("password", "")), _token(request), user["email"])


@router.post("/accreditation/prodi/{prodi_id}/reset")
def accreditation_kunci_reset(prodi_id: str, payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Ajukan password prodi baru; berlaku setelah disetujui admin."""
    user = _auth_user(request, api)
    hasil = _laporan_call(_laporan_svc(api).ajukan_reset, prodi_id, str(payload.get("password_baru", "")),
                          str(payload.get("alasan") or ""), user)
    _catat(api, "akreditasi", user, "ajukan_reset_pin", f"Mengajukan reset PIN prodi {prodi_id}")
    from app.services.notifikasi import kabari_admin
    kabari_admin(api.engine, "akreditasi", f"Pengajuan reset PIN prodi {prodi_id}",
                 f"{user.get('nama') or user['email']} ({user['email']}) mengajukan PIN baru untuk prodi {prodi_id}.\n"
                 f"Alasan: {str(payload.get('alasan') or '-').strip()[:300]}\n\n"
                 f"Setujui atau tolak di halaman Admin: {_base_url(request)}/admin\n")
    return hasil


@router.get("/accreditation/admin/reset")
def accreditation_admin_reset_list(request: Request, api: AnalyticsService = Depends(service)):
    """Pengajuan reset password prodi (admin)."""
    user = _auth_user(request, api)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Hanya admin.")
    return {"pengajuan": _laporan_svc(api).daftar_reset()}


@router.post("/accreditation/admin/reset/{reset_id}")
def accreditation_admin_reset_decide(reset_id: int, payload: dict[str, Any], request: Request,
                                     api: AnalyticsService = Depends(service)):
    """Setujui / tolak pengajuan reset password prodi (admin)."""
    user = _auth_user(request, api)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Hanya admin.")
    hasil = _laporan_call(_laporan_svc(api).putuskan_reset, reset_id, bool(payload.get("setujui")), user)
    _catat(api, "akreditasi", user, "putuskan_reset_pin",
           f"{'Menyetujui' if payload.get('setujui') else 'Menolak'} pengajuan reset PIN #{reset_id}")
    return hasil


@router.get("/accreditation/workspace")
def accreditation_workspace(request: Request, laporan_id: int = Query(...), api: AnalyticsService = Depends(service)):
    """Semua item LED/LKPS satu laporan + isian, riwayat ekstraksi, file, dan riwayat Word."""
    _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, laporan_id)
    return _workspace_call(_workspace(api).workspace, laporan)


@router.get("/accreditation/laporan/{laporan_id}/aktivitas")
def accreditation_laporan_aktivitas(laporan_id: int, request: Request, api: AnalyticsService = Depends(service)):
    """Riwayat perubahan satu laporan: siapa mengubah apa dan kapan (butuh PIN prodi di sesi ini)."""
    _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, laporan_id)
    from app.services.aktivitas import daftar
    return {"aktivitas": daftar(api.engine, "akreditasi", laporan_id=int(laporan["id"]), limit=100)}


@router.post("/accreditation/workspace/items/{item_id}")
def accreditation_save_item(item_id: str, payload: dict[str, Any], request: Request,
                            api: AnalyticsService = Depends(service)):
    """Simpan isian satu item (ganti seluruh sel item itu) di laporan."""
    user = _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, payload.get("laporan_id"))
    hasil = _workspace_call(_workspace(api).save_item, laporan, item_id, payload.get("rows"), user["email"])
    _catat(api, "akreditasi", user, "ubah_isian", f"Mengubah isian: {_nama_item(item_id)}", int(laporan["id"]))
    return hasil


@router.post("/accreditation/workspace/final")
def accreditation_item_final(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Tandai / batalkan status final bagian laporan saat review dokumen (satu item atau daftar item)."""
    user = _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, payload.get("laporan_id"))
    hasil = _workspace_call(_workspace(api).set_final, laporan, payload.get("item_ids"),
                            bool(payload.get("final", True)), user["email"])
    ids = payload.get("item_ids")
    apa = _nama_item(ids) if isinstance(ids, str) else (_nama_item(ids[0]) if isinstance(ids, list) and len(ids) == 1 else None)
    _catat(api, "akreditasi", user, "final", f"{'Menandai final' if payload.get('final', True) else 'Mengembalikan ke draft'}: {apa}"
           if apa else str(hasil.get("message")), int(laporan["id"]))
    return hasil


@router.post("/accreditation/programs")
def accreditation_add_program(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Tambah program studi baru di bawah satu fakultas (padanan "+ Tambah prodi baru")."""
    _auth_user(request, api)
    return _workspace_call(_workspace(api).add_program, payload.get("fakultas_id"),
                           str(payload.get("nama", "")), str(payload.get("jenjang", "")))


@router.post("/accreditation/extractions")
def accreditation_extract(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Mulai ekstraksi AI di latar belakang untuk file laporan yang belum/gagal diekstrak; hasilnya langsung
    diterapkan ke data laporan tanpa menimpa isian yang ada. UI memantau lewat workspace."""
    user = _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, payload.get("laporan_id"))
    hasil = _workspace_call(_workspace(api).start_extraction, laporan)
    if hasil.get("dimulai"):
        _catat(api, "akreditasi", user, "ekstraksi", f"Memulai ekstraksi AI untuk {hasil['dimulai']} file", int(laporan["id"]))
    return hasil


@router.post("/accreditation/generate")
def accreditation_generate(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Generate Word satu laporan; tercatat di riwayat laporan (dan riwayat akun pembuatnya)."""
    user = _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, payload.get("laporan_id"))
    content, filename = _workspace_call(_workspace(api).generate, laporan, user["email"])
    _catat(api, "akreditasi", user, "unduh_word", f"Mengunduh Word {filename}", int(laporan["id"]))
    return _docx(content, filename)


@router.get("/accreditation/laporan/{laporan_id}/riwayat/{riwayat_id}/file")
def accreditation_laporan_file(laporan_id: int, riwayat_id: int, request: Request, api: AnalyticsService = Depends(service)):
    """Unduh Word dari riwayat laporan (semua staf yang sudah membuka laporan ini)."""
    _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, laporan_id)
    content, filename = _workspace_call(_workspace(api).laporan_file, laporan, riwayat_id)
    return _docx(content, filename)


@router.get("/accreditation/history/{riwayat_id}/file")
def accreditation_history_file(riwayat_id: int, request: Request, api: AnalyticsService = Depends(service)):
    """Unduh ulang laporan dari riwayat milik sendiri (halaman Profil)."""
    user = _auth_user(request, api)
    content, filename = _workspace_call(_workspace(api).history_file, riwayat_id, user["email"])
    return _docx(content, filename)


@router.get("/home-summary")
def home_summary(api: AnalyticsService = Depends(service)):
    return api.home_summary()


@router.get("/search", response_model=SearchResponse)
def search(q: str = Query(default="")):
    result = parse_search(q)
    return {
        "query": result.query,
        "page": result.page,
        "pillars": result.pillars,
        "topics": result.topics,
        "sdgs": result.sdgs,
        "years": list(result.years) if result.years else None,
        "matched": result.matched,
        "explanation": result.explanation,
    }


@router.get("/impact", response_model=AnalyticsResponse)
def impact(
    mode: str = Query(default="impact", pattern="^(impact|impact-sdgs)$"),
    params: FilterParams = Depends(filters),
    api: AnalyticsService = Depends(service),
):
    try:
        return api.impact(params, mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Analytics data is unavailable") from exc


@router.get("/sdgs", response_model=AnalyticsResponse)
def sdgs(params: FilterParams = Depends(filters), api: AnalyticsService = Depends(service)):
    try:
        return api.sdgs(params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="SDG data is unavailable") from exc


@router.get("/story")
def story(
    mode: str = Query(default="impact", pattern="^(impact|impact-sdgs|sdgs)$"),
    pillar: str | None = Query(default=None, pattern="^(Lingkungan|Ekonomi|Sosial)$"),
    topic: str | None = Query(default=None),
    params: FilterParams = Depends(filters),
    api: AnalyticsService = Depends(service),
):
    """Seluruh chart + insight dashboard Streamlit lama dalam satu respons generik (lihat services/story.py)."""
    from app.domain.source import kepmen
    from app.services.story import StoryService

    if topic and topic not in kepmen().TOPIK_KEPMEN_ALL:
        raise HTTPException(status_code=422, detail="Unknown topic id")
    try:
        return StoryService(api.engine).story(params, mode, pillar, topic)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logging.getLogger(__name__).exception("story endpoint failed")
        raise HTTPException(status_code=503, detail="Story data is unavailable") from exc


@router.get("/sources")
def sources(api: AnalyticsService = Depends(service)):
    """Bagian "Sumber": asal data berita & mata kuliah, jumlah diambil vs memuat dampak, per pilar."""
    from app.services.sources import ringkasan_sumber
    from app.services.story import StoryService
    try:
        return ringkasan_sumber(StoryService(api.engine).frames())
    except Exception as exc:
        logging.getLogger(__name__).exception("sources endpoint failed")
        raise HTTPException(status_code=503, detail="Ringkasan sumber data belum tersedia") from exc


@router.get("/sources/news")
def sources_news(page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=50),
                 q: str = Query(default="", max_length=100), pilar: str = Query(default=""),
                 api: AnalyticsService = Depends(service)):
    """Daftar berita yang memuat konten dampak (satu baris per berita, tautan ke artikel asli)."""
    from app.services.sources import berita_berdampak
    from app.services.story import StoryService
    try:
        return berita_berdampak(StoryService(api.engine).frames(), page, page_size, q, pilar)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logging.getLogger(__name__).exception("sources/news endpoint failed")
        raise HTTPException(status_code=503, detail="Daftar berita belum tersedia") from exc


def _frames(api: AnalyticsService):
    from app.services.story import StoryService
    return StoryService(api.engine).frames()


@router.get("/sdg-manual/untagged")
def sdg_untagged(page: int = Query(default=1, ge=1), page_size: int = Query(default=5, ge=1, le=50),
                 q: str = Query(default="", max_length=100),
                 year_from: str | None = Query(default=None, pattern=r"^\d{4}$"),
                 year_to: str | None = Query(default=None, pattern=r"^\d{4}$"),
                 units: str | None = Query(default=None), api: AnalyticsService = Depends(service)):
    """Berita tanpa tanda SDG (cek manual), terbaru lebih dulu."""
    from app.services.sdg_manual import TagError, belum_bertanda
    try:
        return belum_bertanda(_frames(api), page, page_size, q, year_from, year_to, parse_list(units))
    except TagError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sdg-manual")
def sdg_tag(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Tandai SDG sebuah berita secara manual (butuh login Analisis Dampak); tersimpan di berita_sdg_manual."""
    user = _dampak_auth_user(request, api)
    from app.services.sdg_manual import TagError, tandai
    try:
        return tandai(api.engine, _frames(api), str(payload.get("url", "")), payload.get("sdgs"), user["email"])
    except TagError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sdg-manual/delete")
def sdg_untag(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Batalkan tag SDG manual sebuah berita (butuh login Analisis Dampak)."""
    _dampak_auth_user(request, api)
    from app.services.sdg_manual import TagError, batalkan
    try:
        return batalkan(api.engine, _frames(api), str(payload.get("url", "")))
    except TagError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tema-manual/untagged")
def tema_untagged(page: int = Query(default=1, ge=1), page_size: int = Query(default=5, ge=1, le=50),
                  q: str = Query(default="", max_length=100),
                  year_from: str | None = Query(default=None, pattern=r"^\d{4}$"),
                  year_to: str | None = Query(default=None, pattern=r"^\d{4}$"),
                  units: str | None = Query(default=None), api: AnalyticsService = Depends(service)):
    """Berita tanpa tema Kepmen (cek manual), terbaru lebih dulu."""
    from app.services.tema_manual import TagError, tanpa_tema
    try:
        return tanpa_tema(_frames(api), page, page_size, q, year_from, year_to, parse_list(units))
    except TagError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/tema-manual")
def tema_tag(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Tandai tema Kepmen sebuah berita secara manual (butuh login Analisis Dampak); tersimpan di berita_tema_manual."""
    user = _dampak_auth_user(request, api)
    from app.services.tema_manual import TagError, tandai
    try:
        hasil = tandai(api.engine, _frames(api), str(payload.get("url", "")), payload.get("topiks"), user["email"])
    except TagError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _catat(api, "dampak", user, "tag_tema", f"Menandai tema berita {str(payload.get('url', ''))[:300]}")
    return hasil


@router.post("/tema-manual/delete")
def tema_untag(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Batalkan tag tema manual sebuah berita (butuh login Analisis Dampak)."""
    _dampak_auth_user(request, api)
    from app.services.tema_manual import TagError, batalkan
    try:
        return batalkan(api.engine, _frames(api), str(payload.get("url", "")))
    except TagError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/news")
def news(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    mode: str = Query(default="impact", pattern="^(impact|impact-sdgs|sdgs)$"),
    year_from: str | None = Query(default=None, pattern=r"^\d{4}$"),
    year_to: str | None = Query(default=None, pattern=r"^\d{4}$"),
    pillars: str | None = Query(default=None),
    topics: str | None = Query(default=None),
    sdgs: str | None = Query(default=None),
    units: str | None = Query(default=None),
    api: AnalyticsService = Depends(service),
):
    try:
        from app.services.news import NewsService
        return NewsService(api.engine).list_news(
            page=page, page_size=page_size, mode=mode,
            year_from=year_from, year_to=year_to,
            pillars=parse_list(pillars), topics=parse_list(topics),
            sdgs=parse_int_list(sdgs), units=parse_list(units),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="News data is unavailable") from exc



# Laporan terakhir per filter: tombol "Unduh Word" di pratinjau memakai hasil yang sama dengan yang
# baru dilihat (tanpa menggambar ulang puluhan grafik). Kunci ikut data_as_of supaya data baru tidak basi.
_LAPORAN_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LAPORAN_TTL = 300
_LAPORAN_MAKS = 4


def _laporan(payload: ReportRequest, api: AnalyticsService) -> dict[str, Any]:
    from app.services.story import StoryService
    # Suntingan tidak ikut kunci: unduhan memakai laporan yang sama dengan pratinjau, lalu disunting.
    kunci = f"{payload.model_dump_json(exclude={'suntingan'})}|{StoryService(api.engine).frames().data_as_of}"
    sekarang = time.monotonic()
    hit = _LAPORAN_CACHE.get(kunci)
    if hit and sekarang - hit[0] < _LAPORAN_TTL:
        return hit[1]
    hasil = _susun_laporan(payload, api)
    _LAPORAN_CACHE[kunci] = (sekarang, hasil)
    for lama in sorted(_LAPORAN_CACHE, key=lambda k: _LAPORAN_CACHE[k][0])[:-_LAPORAN_MAKS]:
        _LAPORAN_CACHE.pop(lama, None)
    return hasil


def _susun_laporan(payload: ReportRequest, api: AnalyticsService) -> dict[str, Any]:
    """Model laporan dampak (kerangka LAPORAN DAMPAK UGM 2025) untuk filter aktif."""
    from app.domain.source import kepmen
    from app.services.laporan_dampak import build_laporan
    from app.services.sources import ringkasan_sumber
    from app.services.story import StoryService

    params = FilterParams(
        year_from=payload.year_from,
        year_to=payload.year_to,
        pillars=tuple(payload.pillars),
        topics=tuple(payload.topics),
        sdgs=tuple(payload.sdgs),
        units=tuple(payload.units),
    )
    service_ = StoryService(api.engine)
    story_ = service_.story(params, payload.mode, None, None)
    try:
        sumber = ringkasan_sumber(service_.frames())
    except Exception:  # ringkasan sumber hanya pelengkap BAB I; laporan tetap dibuat tanpanya
        logging.getLogger(__name__).warning("ringkasan sumber tidak tersedia untuk laporan", exc_info=True)
        sumber = None
    return build_laporan(story_, sumber, kepmen().LABEL_TOPIC_ALL)


@router.post("/reports/preview")
def report_preview(payload: ReportRequest, api: AnalyticsService = Depends(service)):
    """Pratinjau laporan: blok dokumen yang sama persis dengan isi file Word."""
    try:
        return _laporan(payload, api)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logging.getLogger(__name__).exception("report preview failed")
        raise HTTPException(status_code=503, detail="Pratinjau laporan belum dapat dibuat") from exc


def _filter_laporan(payload: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.schemas import ReportRequest
    try:
        req = ReportRequest(**{k: v for k, v in (payload or {}).items() if k != "suntingan"})
    except Exception as exc:  # noqa: BLE001 -- filter tidak valid = 422 seperti /reports
        raise HTTPException(status_code=422, detail="Filter laporan tidak valid.") from exc
    return req.model_dump(exclude={"suntingan"})


@router.post("/reports/draf/ambil")
def report_draf_ambil(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Draf suntingan pratinjau milik akun ini untuk filter laporan yang sama."""
    user = _dampak_auth_user(request, api)
    from app.services.laporan_draf import ambil
    return ambil(api.engine, int(user["id"]), _filter_laporan(payload.get("filter") or {}))


@router.post("/reports/draf")
def report_draf_simpan(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Simpan draf suntingan (otomatis dari pratinjau); suntingan kosong = draf dihapus."""
    user = _dampak_auth_user(request, api)
    from app.services.laporan_draf import DrafError, simpan
    try:
        return simpan(api.engine, int(user["id"]), _filter_laporan(payload.get("filter") or {}), payload.get("suntingan") or {})
    except DrafError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reports")
def report(payload: ReportRequest, api: AnalyticsService = Depends(service)):
    """Unduh laporan dampak (.docx) untuk filter aktif, dengan suntingan narasi dari pratinjau (bila ada)."""
    from app.services.laporan_dampak import render_docx, terapkan_suntingan
    try:
        content = render_docx(terapkan_suntingan(_laporan(payload, api), payload.suntingan))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logging.getLogger(__name__).exception("report generation failed")
        raise HTTPException(status_code=503, detail="Laporan belum dapat dibuat") from exc
    nama = {"impact": "Dampak", "impact-sdgs": "Dampak_SDGs", "sdgs": "SDGs"}[payload.mode]
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="Laporan_{nama}_UGM.docx"'},
    )


_last_seen_update_log: float | None = None


@router.get("/refresh-status")
def refresh_status(api: AnalyticsService = Depends(service)):
    """Status update data berita (pipeline update_mingguan.py) + tail log-nya."""
    global _last_seen_update_log
    from app.services import refresh
    result = refresh.status(api._last_update())
    # Update baru selesai -> buang cache frame /story sekali supaya berita baru langsung tampil.
    if result["status"] == "finished" and refresh.LOG.exists():
        mtime = refresh.LOG.stat().st_mtime
        if _last_seen_update_log is not None and mtime != _last_seen_update_log:
            from app.services.story import StoryService
            StoryService.clear_cache()
        _last_seen_update_log = mtime
    return result


@router.post("/refresh")
def refresh_start(request: Request, api: AnalyticsService = Depends(service)):
    """Mulai update data berita di latar belakang -- khusus admin (padanan tombol Streamlit lama)."""
    user = _auth_user(request, api)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Hanya admin yang bisa memulai update data.")
    from app.services import refresh
    try:
        return refresh.start()
    except refresh.RefreshError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
