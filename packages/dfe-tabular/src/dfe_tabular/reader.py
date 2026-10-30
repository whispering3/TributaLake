from __future__ import annotations

from pathlib import Path

import pyarrow as pa
from fiscal_model import Finding, IngestionReport
from fiscal_store import Store

from dfe_tabular.nfe import parse_nfe
from dfe_tabular.schema_validation import validate_nfe_schema

_HEADER_SCHEMA = pa.schema(
    [
        pa.field("document_key", pa.string(), nullable=False),
        pa.field("model", pa.string()),
        pa.field("series", pa.string()),
        pa.field("number", pa.string()),
        pa.field("issued_at", pa.date32(), nullable=False),
        pa.field("issuer_tax_id", pa.string()),
        pa.field("issuer_state", pa.string()),
        pa.field("recipient_tax_id", pa.string()),
        pa.field("recipient_state", pa.string()),
        pa.field("total_value", pa.decimal128(18, 2)),
        pa.field("layout_version", pa.string()),
        pa.field("_tenant_id", pa.string(), nullable=False),
        pa.field("_file_id", pa.string(), nullable=False),
    ]
)

_ITEM_SCHEMA = pa.schema(
    [
        pa.field("document_key", pa.string(), nullable=False),
        pa.field("item_number", pa.int32(), nullable=False),
        pa.field("product_code", pa.string()),
        pa.field("description", pa.string()),
        pa.field("ncm", pa.string()),
        pa.field("cfop", pa.string()),
        pa.field("quantity", pa.decimal128(18, 4)),
        pa.field("unit_value", pa.decimal128(18, 10)),
        pa.field("total_value", pa.decimal128(18, 2)),
        pa.field("_tenant_id", pa.string(), nullable=False),
        pa.field("_file_id", pa.string(), nullable=False),
    ]
)


class DfeReader:
    """Ingere NF-e de forma idempotente e preserva achados de validação."""

    def ingest_file(self, path: str | Path, *, tenant: str, store: Store) -> IngestionReport:
        source = Path(path)
        fingerprint = store.fingerprint(source)
        if store.has_file(fingerprint.sha256, tenant):
            return IngestionReport(fingerprint.sha256, tenant, "already_processed")

        store.register_file(
            fingerprint=fingerprint,
            tenant_id=tenant,
            source_name=source.name,
            document_type="nfe",
        )
        try:
            document = parse_nfe(source)
            schema_findings = validate_nfe_schema(source)
            header = {**document.header, "_tenant_id": tenant, "_file_id": fingerprint.sha256}
            items = [
                {**item, "_tenant_id": tenant, "_file_id": fingerprint.sha256}
                for item in document.items
            ]
            store.publish_rows(
                layer="bronze",
                table_name="nfe_header",
                tenant_id=tenant,
                competencia=document.competence,
                file_id=fingerprint.sha256,
                rows=[header],
                schema=_HEADER_SCHEMA,
            )
            if items:
                store.publish_rows(
                    layer="bronze",
                    table_name="nfe_item",
                    tenant_id=tenant,
                    competencia=document.competence,
                    file_id=fingerprint.sha256,
                    rows=items,
                    schema=_ITEM_SCHEMA,
                )
            store.mark_published(fingerprint.sha256, tenant)
            return IngestionReport(
                fingerprint.sha256,
                tenant,
                "published",
                records_written=1 + len(items),
                findings=[*document.findings, *schema_findings],
            )
        except Exception:
            store.mark_failed(fingerprint.sha256, tenant)
            raise

    def ingest_dir(self, path: str | Path, *, tenant: str, store: Store) -> list[IngestionReport]:
        directory = Path(path)
        files = directory.rglob("*.xml")
        return [self.ingest_file(file, tenant=tenant, store=store) for file in files]


def findings_to_rows(findings: list[Finding]) -> list[dict[str, str | None]]:
    return [
        {
            "code": finding.code,
            "severity": finding.severity.value,
            "message": finding.message,
            "field": finding.field,
            "observed": finding.observed,
        }
        for finding in findings
    ]
