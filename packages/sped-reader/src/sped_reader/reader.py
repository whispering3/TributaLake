from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pyarrow as pa
from fiscal_model import Finding, FindingSeverity, IngestionReport
from fiscal_spec import LayoutSpec
from fiscal_store import ParquetBatchWriter, Store

from sped_reader.encoding import DetectedEncoding, detect_encoding
from sped_reader.records import RecordParseResult, parse_sped_line
from sped_reader.totals import SpedTotals
from sped_reader.typing import TypedSpedRecord, type_record


class SpedReader:
    """Leitor incremental da camada estrutural comum aos arquivos SPED."""

    def inspect(self, path: str | Path) -> DetectedEncoding:
        return detect_encoding(path)

    def stream(self, path: str | Path) -> Iterator[RecordParseResult]:
        source = Path(path)
        encoding = detect_encoding(source)
        with source.open("r", encoding=encoding.name, newline="") as stream:
            for line_no, raw in enumerate(stream, start=1):
                yield parse_sped_line(raw, line_no)

    def ingest(
        self,
        path: str | Path,
        *,
        tenant: str,
        store: Store,
        spec: LayoutSpec,
        mode: str = "tolerant",
    ) -> IngestionReport:
        if mode not in {"tolerant", "strict"}:
            raise ValueError("mode deve ser tolerant ou strict.")
        source = Path(path)
        fingerprint = store.fingerprint(source)
        if store.has_file(fingerprint.sha256, tenant):
            return IngestionReport(fingerprint.sha256, tenant, "already_processed")

        records = self.stream(source)
        first_result = next(records, None)
        competence = _competence_from_header(first_result, spec)
        store.register_file(
            fingerprint=fingerprint,
            tenant_id=tenant,
            source_name=source.name,
            document_type=spec.module,
        )
        report = IngestionReport(fingerprint.sha256, tenant, "published")
        writer = store.open_batch_writer(
            layer="bronze",
            tenant_id=tenant,
            competencia=competence,
            file_id=fingerprint.sha256,
        )
        active_parent_lines: dict[str, int] = {}
        totals = SpedTotals()
        try:
            for result in _prepend(first_result, records):
                totals.add(result.record)
                self._persist_result(
                    result,
                    spec,
                    writer,
                    report,
                    tenant,
                    fingerprint.sha256,
                    active_parent_lines,
                    mode,
                )
            self._persist_total_findings(
                totals.findings(), writer, report, fingerprint.sha256, tenant, mode
            )
            writer.publish()
            store.mark_published(fingerprint.sha256, tenant)
            return report
        except Exception:
            writer.discard()
            store.mark_failed(fingerprint.sha256, tenant)
            raise

    def _persist_total_findings(
        self,
        findings: tuple[Finding, ...],
        writer: ParquetBatchWriter,
        report: IngestionReport,
        file_id: str,
        tenant: str,
        mode: str,
    ) -> None:
        if not findings:
            return
        self._write_findings(findings, writer, file_id, tenant)
        report.findings.extend(findings)
        if mode == "strict":
            raise ValueError("Totalizador SPED inconsistente no modo estrito.")

    def _persist_result(
        self,
        result: RecordParseResult,
        spec: LayoutSpec,
        writer: ParquetBatchWriter,
        report: IngestionReport,
        tenant: str,
        file_id: str,
        active_parent_lines: dict[str, int],
        mode: str,
    ) -> None:
        if result.record is None:
            self._quarantine(
                result.findings, result.raw, None, writer, report, file_id, tenant, mode
            )
            return
        definition = spec.records.get(result.record.record_code)
        if definition is None:
            finding = Finding(
                code="V-STR-002",
                severity=FindingSeverity.ERROR,
                message="Registro inexistente para a versão do leiaute.",
                record=result.record.record_code,
                line_no=result.record.line_no,
            )
            self._quarantine(
                (finding,),
                result.record.raw,
                result.record.line_no,
                writer,
                report,
                file_id,
                tenant,
                mode,
            )
            return
        typed, findings = type_record(result.record, definition)
        if typed is None:
            self._quarantine(
                findings,
                result.record.raw,
                result.record.line_no,
                writer,
                report,
                file_id,
                tenant,
                mode,
            )
            return
        self._write_findings(findings, writer, file_id, tenant)
        report.findings.extend(findings)
        parent_line = active_parent_lines.get(definition.parent) if definition.parent else None
        row = {
            **typed.values,
            "_tenant_id": tenant,
            "_file_id": file_id,
            "_line_no": typed.source.line_no,
            "_parent_line_no": parent_line,
            "_layout_version": spec.layout_version,
            "_parser_version": "0.1.0",
        }
        writer.append(
            f"sped_{spec.module}_{definition.code.lower()}", row, _record_schema(typed, spec)
        )
        active_parent_lines[definition.code] = typed.source.line_no
        report.records_written += 1

    def _quarantine(
        self,
        findings: tuple[Finding, ...],
        raw: str,
        line_no: int | None,
        writer: ParquetBatchWriter,
        report: IngestionReport,
        file_id: str,
        tenant: str,
        mode: str,
    ) -> None:
        self._write_findings(findings, writer, file_id, tenant)
        report.findings.extend(findings)
        if mode == "strict":
            raise ValueError("Erro estrutural ou de tipagem no modo estrito.")
        first = findings[0]
        writer.append(
            "sped_quarantine",
            {
                "file_id": file_id,
                "tenant_id": tenant,
                "line_no": line_no,
                "raw": raw,
                "code": first.code,
                "message": first.message,
            },
            _quarantine_schema(),
        )
        report.records_quarantined += 1

    def _write_findings(
        self, findings: tuple[Finding, ...], writer: ParquetBatchWriter, file_id: str, tenant: str
    ) -> None:
        for finding in findings:
            writer.append(
                "sped_finding",
                {
                    "file_id": file_id,
                    "tenant_id": tenant,
                    "line_no": finding.line_no,
                    "record": finding.record,
                    "field": finding.field,
                    "code": finding.code,
                    "severity": finding.severity.value,
                    "message": finding.message,
                },
                _finding_schema(),
            )


def _prepend(
    first: RecordParseResult | None, remainder: Iterator[RecordParseResult]
) -> Iterator[RecordParseResult]:
    if first is not None:
        yield first
    yield from remainder


def _competence_from_header(result: RecordParseResult | None, spec: LayoutSpec) -> date:
    if result is None or result.record is None or result.record.record_code != "0000":
        raise ValueError("O arquivo SPED deve iniciar com o registro 0000.")
    definition = spec.records.get("0000")
    if definition is None:
        raise ValueError("A spec deve definir o registro 0000.")
    typed, findings = type_record(result.record, definition)
    if typed is None or findings:
        raise ValueError("O registro 0000 não possui uma competência válida.")
    value = typed.values.get("dt_ini")
    if not isinstance(value, date):
        raise ValueError("A spec do registro 0000 deve declarar DT_INI como data.")
    return date(value.year, value.month, 1)


def _record_schema(record: TypedSpedRecord, spec: LayoutSpec) -> pa.Schema:
    definition = spec.records[record.source.record_code]
    fields = [
        _arrow_field(field.name.lower(), field.field_type, field.precision, field.scale)
        for field in definition.fields
    ]
    fields.extend(
        [
            pa.field("_tenant_id", pa.string(), nullable=False),
            pa.field("_file_id", pa.string(), nullable=False),
            pa.field("_line_no", pa.int64(), nullable=False),
            pa.field("_parent_line_no", pa.int64()),
            pa.field("_layout_version", pa.string(), nullable=False),
            pa.field("_parser_version", pa.string(), nullable=False),
        ]
    )
    return pa.schema(fields)


def _arrow_field(name: str, field_type: str, precision: int | None, scale: int | None) -> pa.Field:
    types = {"str": pa.string(), "enum": pa.string(), "int": pa.int64(), "date": pa.date32()}
    data_type = (
        pa.decimal128(precision or 18, scale or 2) if field_type == "decimal" else types[field_type]
    )
    return pa.field(name, data_type)


def _quarantine_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("file_id", pa.string()),
            pa.field("tenant_id", pa.string()),
            pa.field("line_no", pa.int64()),
            pa.field("raw", pa.string()),
            pa.field("code", pa.string()),
            pa.field("message", pa.string()),
        ]
    )


def _finding_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("file_id", pa.string()),
            pa.field("tenant_id", pa.string()),
            pa.field("line_no", pa.int64()),
            pa.field("record", pa.string()),
            pa.field("field", pa.string()),
            pa.field("code", pa.string()),
            pa.field("severity", pa.string()),
            pa.field("message", pa.string()),
        ]
    )
