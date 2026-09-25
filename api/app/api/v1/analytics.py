from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
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
        return _account_service(api).admin_action(
            user, action, target_id, None if value is None else bool(value))
    except AksiDitolak as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/accreditation/uploads")
async def accreditation_upload(request: Request, laporan_id: int = Form(...), file: UploadFile = File(...), api: AnalyticsService = Depends(service)):
    user = _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, laporan_id)
    from app.services.accreditation_upload import MAX_UPLOAD_BYTES, UploadError, save_upload
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 25 MB")
    try:
        return save_upload(api.engine, Path(settings.accreditation_upload_dir), laporan, file.filename or "file", file.content_type, data, user["email"])
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Upload gagal disimpan") from exc


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
    return _laporan_call(_laporan_svc(api).buat_laporan, str(payload.get("prodi_id", "")), str(payload.get("dokumen", "")),
                         payload.get("tahun"), str(payload.get("nama") or ""), _token(request), user["email"])


@router.post("/accreditation/laporan/{laporan_id}/hapus")
def accreditation_laporan_delete(laporan_id: int, request: Request, api: AnalyticsService = Depends(service)):
    """Hapus laporan beserta isian, file, dan riwayat Word-nya; PIN prodi harus sudah dibuka di sesi ini."""
    _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, laporan_id)
    return _workspace_call(_workspace(api).hapus_laporan, laporan)


@router.post("/accreditation/prodi/{prodi_id}/kunci")
def accreditation_kunci_buat(prodi_id: str, payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Buat password pertama prodi (hanya bila belum ada)."""
    user = _auth_user(request, api)
    return _laporan_call(_laporan_svc(api).buat_kunci, prodi_id, str(payload.get("password", "")), _token(request), user["email"])


@router.post("/accreditation/prodi/{prodi_id}/buka")
def accreditation_kunci_buka(prodi_id: str, payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Masukkan password prodi; berlaku sampai logout / sesi login berakhir."""
    user = _auth_user(request, api)
    return _laporan_call(_laporan_svc(api).buka, prodi_id, str(payload.get("password", "")), _token(request), user["email"])


@router.post("/accreditation/prodi/{prodi_id}/reset")
def accreditation_kunci_reset(prodi_id: str, payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Ajukan password prodi baru; berlaku setelah disetujui admin."""
    user = _auth_user(request, api)
    return _laporan_call(_laporan_svc(api).ajukan_reset, prodi_id, str(payload.get("password_baru", "")),
                         str(payload.get("alasan") or ""), user)


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
    return _laporan_call(_laporan_svc(api).putuskan_reset, reset_id, bool(payload.get("setujui")), user)


@router.get("/accreditation/workspace")
def accreditation_workspace(request: Request, laporan_id: int = Query(...), api: AnalyticsService = Depends(service)):
    """Semua item LED/LKPS satu laporan + isian, riwayat ekstraksi, file, dan riwayat Word."""
    _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, laporan_id)
    return _workspace_call(_workspace(api).workspace, laporan)


@router.post("/accreditation/workspace/items/{item_id}")
def accreditation_save_item(item_id: str, payload: dict[str, Any], request: Request,
                            api: AnalyticsService = Depends(service)):
    """Simpan isian satu item (ganti seluruh sel item itu) di laporan."""
    user = _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, payload.get("laporan_id"))
    return _workspace_call(_workspace(api).save_item, laporan, item_id, payload.get("rows"), user["email"])


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
    _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, payload.get("laporan_id"))
    return _workspace_call(_workspace(api).start_extraction, laporan)


@router.post("/accreditation/generate")
def accreditation_generate(payload: dict[str, Any], request: Request, api: AnalyticsService = Depends(service)):
    """Generate Word satu laporan; tercatat di riwayat laporan (dan riwayat akun pembuatnya)."""
    user = _auth_user(request, api)
    laporan = _laporan_terbuka(request, api, payload.get("laporan_id"))
    content, filename = _workspace_call(_workspace(api).generate, laporan, user["email"])
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
        return tandai(api.engine, _frames(api), str(payload.get("url", "")), payload.get("topiks"), user["email"])
    except TagError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    kunci = f"{payload.model_dump_json()}|{StoryService(api.engine).frames().data_as_of}"
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


@router.post("/reports")
def report(payload: ReportRequest, api: AnalyticsService = Depends(service)):
    """Unduh laporan dampak (.docx) untuk filter aktif."""
    from app.services.laporan_dampak import render_docx
    try:
        content = render_docx(_laporan(payload, api))
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
