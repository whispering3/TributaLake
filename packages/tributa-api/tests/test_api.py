from pathlib import Path

from fastapi.testclient import TestClient
from tributa_api import create_app
from tributa_api.settings import Settings


def test_portal_and_health_are_available(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    assert client.get("/").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"


def test_ingests_sped_and_exposes_dashboard(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    response = client.post(
        "/api/ingestions/sped",
        files={"upload": ("efd.txt", _valid_sped(), "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["records_written"] == 1
    assert client.get("/api/dashboard").json() == {
        "files": 1,
        "published": 1,
        "findings": 0,
    }
    assert client.get("/api/ingestions").json()[0]["source_name"].endswith("-efd.txt")


def test_rejects_unsupported_upload(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    response = client.post(
        "/api/ingestions/sped",
        files={"upload": ("efd.xml", b"<xml />", "application/xml")},
    )

    assert response.status_code == 415


def test_rejects_invalid_tenant_identifier(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    response = client.get("/api/dashboard", headers={"X-Tributa-Tenant": "../other"})

    assert response.status_code == 400


def _settings(root: Path) -> Settings:
    return Settings(
        store_path=root / "lake",
        spec_path=Path(__file__).parents[2]
        / "fiscal-spec"
        / "specs"
        / "candidates"
        / "efd_contribuicoes_0000_v1_35.yaml",
        upload_path=root / "incoming",
        development_tenant="demo",
    )


def _valid_sped() -> bytes:
    return b"|0000|016|0|0||01012026|31012026|Empresa Teste|12345678000199|SP|\n"
