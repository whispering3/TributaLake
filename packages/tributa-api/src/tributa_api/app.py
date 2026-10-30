from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from fiscal_spec import load_spec
from fiscal_store import Store
from sped_reader import SpedReader

from tributa_api.settings import Settings

TENANT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.development(Path.cwd())
    app = FastAPI(title="TributaLake API", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.store = Store(resolved_settings.store_path)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "tributa-api"}

    @app.get("/api/dashboard")
    def dashboard(tenant: str = Depends(_tenant)) -> dict[str, int]:
        store = _store(app)
        with store.duckdb() as connection:
            files = connection.execute(
                "SELECT count(*) FROM ingest_file WHERE tenant_id = ?", [tenant]
            ).fetchone()[0]
            published = connection.execute(
                "SELECT count(*) FROM ingest_file WHERE tenant_id = ? AND status = 'published'",
                [tenant],
            ).fetchone()[0]
        return {"files": files, "published": published, "findings": _count_findings(store, tenant)}

    @app.get("/api/ingestions")
    def list_ingestions(tenant: str = Depends(_tenant)) -> list[dict[str, object]]:
        with _store(app).duckdb() as connection:
            rows = connection.execute(
                """
                SELECT file_id, source_name, document_type, size_bytes, status,
                       ingested_at, published_at
                FROM ingest_file WHERE tenant_id = ? ORDER BY ingested_at DESC
                """,
                [tenant],
            ).fetchall()
        columns = (
            "file_id",
            "source_name",
            "document_type",
            "size_bytes",
            "status",
            "ingested_at",
            "published_at",
        )
        return [dict(zip(columns, row, strict=True)) for row in rows]

    @app.get("/api/findings")
    def list_findings(tenant: str = Depends(_tenant)) -> list[dict[str, object]]:
        store = _store(app)
        if not _view_exists(store, "v_bronze_sped_finding"):
            return []
        with store.duckdb() as connection:
            rows = connection.execute(
                """
                SELECT file_id, line_no, record, field, code, severity, message
                FROM v_bronze_sped_finding
                WHERE tenant_id = ? ORDER BY line_no DESC LIMIT 100
                """,
                [tenant],
            ).fetchall()
        columns = ("file_id", "line_no", "record", "field", "code", "severity", "message")
        return [dict(zip(columns, row, strict=True)) for row in rows]

    @app.post("/api/ingestions/sped", status_code=status.HTTP_201_CREATED)
    def ingest_sped(
        upload: UploadFile = File(...), tenant: str = Depends(_tenant)
    ) -> dict[str, object]:
        source = _save_upload(upload, app.state.settings, tenant)
        report = SpedReader().ingest(
            source, tenant=tenant, store=_store(app), spec=load_spec(app.state.settings.spec_path)
        )
        return report.summary()

    @app.get("/")
    def portal() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    return app


def _tenant(request: Request) -> str:
    configured_tenant = request.app.state.settings.development_tenant
    tenant = request.headers.get("X-Tributa-Tenant", configured_tenant)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant não autenticado."
        )
    if not TENANT_PATTERN.fullmatch(tenant):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant deve conter apenas letras minúsculas, números, hífen ou sublinhado.",
        )
    return tenant


def _store(app: FastAPI) -> Store:
    return app.state.store


def _save_upload(upload: UploadFile, settings: Settings, tenant: str) -> Path:
    if not upload.filename or Path(upload.filename).suffix.lower() not in {".txt", ".sped"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Envie um arquivo SPED .txt ou .sped.",
        )
    target_directory = settings.upload_path / tenant
    target_directory.mkdir(parents=True, exist_ok=True)
    target = target_directory / f"{uuid4().hex}-{Path(upload.filename).name}"
    bytes_written = 0
    with target.open("wb") as destination:
        while chunk := upload.file.read(1024 * 1024):
            bytes_written += len(chunk)
            if bytes_written > settings.max_upload_bytes:
                break
            destination.write(chunk)
    if bytes_written > settings.max_upload_bytes:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo acima do limite permitido.",
        )
    return target


def _view_exists(store: Store, view_name: str) -> bool:
    with store.duckdb() as connection:
        row = connection.execute(
            "SELECT 1 FROM information_schema.views WHERE table_name = ?", [view_name]
        ).fetchone()
    return row is not None


def _count_findings(store: Store, tenant: str) -> int:
    if not _view_exists(store, "v_bronze_sped_finding"):
        return 0
    with store.duckdb() as connection:
        return connection.execute(
            "SELECT count(*) FROM v_bronze_sped_finding WHERE tenant_id = ?", [tenant]
        ).fetchone()[0]
