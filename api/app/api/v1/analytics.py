from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.responses import Response

from app.api.v1.schemas import AnalyticsResponse, ReportRequest, SearchResponse
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
async def accreditation_upload(request: Request, prodi_id: str = Form(...), file: UploadFile = File(...), api: AnalyticsService = Depends(service)):
    user = _auth_user(request, api)
    from app.services.accreditation_upload import MAX_UPLOAD_BYTES, UploadError, save_upload
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 25 MB")
    try:
        return save_upload(api.engine, Path(settings.accreditation_upload_dir), prodi_id, file.filename or "file", file.content_type, data, user["email"])
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Upload gagal disimpan") from exc


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



@router.post("/reports")
def report(payload: ReportRequest, api: AnalyticsService = Depends(service)):
    try:
        params = FilterParams(
            year_from=payload.year_from,
            year_to=payload.year_to,
            pillars=tuple(payload.pillars),
            topics=tuple(payload.topics),
            sdgs=tuple(payload.sdgs),
            units=tuple(payload.units),
        )
        result = api.impact(params, payload.mode) if payload.mode != "sdgs" else api.sdgs(params)
        from app.services.report import build_report
        content = build_report(payload.mode, result)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="Laporan_UGM_Analytics_{payload.mode}.docx"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Report generation is unavailable") from exc


@router.get("/refresh-status")
def refresh_status(api: AnalyticsService = Depends(service)):
    return {"status": "not_started", "updated_at": api._last_update(), "trigger_available": False}
