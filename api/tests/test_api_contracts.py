from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v1.analytics import service
from app.main import app


class FakeService:
    engine = object()

    def metadata(self):
        return {"years": {"min": "2020", "max": "2024"}, "pillars": ["Lingkungan", "Ekonomi", "Sosial"], "topics": [], "sdgs": [], "units": [], "updated_at": None}

    def home_summary(self):
        return {"total_berita": 2, "n_dampak": 1, "total_sitemap": 4, "cakupan_pct": 25.0, "updated_at": None}

    def impact(self, filters, mode):
        return {"mode": mode, "filters": {"year_from": "2020", "year_to": "2024"}, "data_as_of": None, "summary": {"total_news": 1}, "narrative": "Data terfilter.", "charts": {}, "tables": {}, "caveats": []}

    def sdgs(self, filters):
        return {"mode": "sdgs", "filters": {"year_from": "2020", "year_to": "2024"}, "data_as_of": None, "summary": {"total_sitemap": 1}, "narrative": "Data SDG.", "charts": {}, "tables": {}, "caveats": []}

    def _last_update(self):
        return None


app.dependency_overrides[service] = lambda: FakeService()
client = TestClient(app)


def teardown_module():
    app.dependency_overrides.clear()


def test_health_is_public():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_preserves_direct_sdg_routing():
    response = client.get("/api/v1/analytics/search", params={"q": "SDG 7 2024"})
    assert response.status_code == 200
    assert response.json()["page"] == "sdgs"
    assert response.json()["sdgs"] == [7]
    assert response.json()["years"] == ["2024", "2024"]


def test_impact_rejects_invalid_year():
    response = client.get("/api/v1/analytics/impact", params={"year_from": "2025", "year_to": "2024"})
    assert response.status_code == 422


def test_sdg_values_are_bounded():
    response = client.get("/api/v1/analytics/sdgs", params={"sdgs": "18"})
    assert response.status_code == 422


def test_read_endpoints_return_contract_shape():
    assert client.get("/api/v1/analytics/metadata").json()["years"]["min"] == "2020"
    assert client.get("/api/v1/analytics/home-summary").json()["n_dampak"] == 1
    assert client.get("/api/v1/analytics/impact", params={"mode": "impact"}).json()["mode"] == "impact"
    assert client.get("/api/v1/analytics/sdgs").json()["mode"] == "sdgs"
