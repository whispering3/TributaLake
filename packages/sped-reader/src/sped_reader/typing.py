from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fiscal_model import Finding, FindingSeverity
from fiscal_spec import RecordSpec

from sped_reader.records import ParsedSpedLine


@dataclass(frozen=True, slots=True)
class TypedSpedRecord:
    source: ParsedSpedLine
    values: dict[str, object | None]


def type_record(
    record: ParsedSpedLine, definition: RecordSpec
) -> tuple[TypedSpedRecord | None, tuple[Finding, ...]]:
    findings: list[Finding] = []
    typed_values: dict[str, object | None] = {}
    for field in definition.fields:
        raw_value = (
            record.record_code
            if field.position == 1
            else _value_at(record.fields, field.position - 2)
        )
        parsed_value, field_findings = _parse_field(
            raw_value, field.field_type, field.required, field.values
        )
        typed_values[field.name.lower()] = parsed_value
        findings.extend(_with_location(field_findings, record, field.name))
    if any(finding.severity == FindingSeverity.ERROR for finding in findings):
        return None, tuple(findings)
    return TypedSpedRecord(record, typed_values), tuple(findings)


def _value_at(values: tuple[str, ...], index: int) -> str:
    return values[index] if 0 <= index < len(values) else ""


def _parse_field(
    raw_value: str, field_type: str, required: str, allowed_values: tuple[str, ...]
) -> tuple[object | None, tuple[Finding, ...]]:
    if not raw_value:
        if required == "O":
            return None, (_finding("V-FLD-003", "Campo obrigatório ausente."),)
        return None, ()
    try:
        value = _convert_value(raw_value, field_type)
    except (InvalidOperation, ValueError):
        return None, (_finding("V-FLD-001", "Campo incompatível com o tipo definido na spec."),)
    if allowed_values and raw_value not in allowed_values:
        return value, (_finding("V-FLD-004", "Valor fora da enumeração permitida."),)
    return value, ()


def _convert_value(raw_value: str, field_type: str) -> object:
    match field_type:
        case "str" | "enum":
            return raw_value
        case "int":
            return int(raw_value)
        case "decimal":
            return Decimal(raw_value.replace(",", "."))
        case "date":
            return datetime.strptime(raw_value, "%d%m%Y").date()
        case _:
            raise ValueError(f"Tipo de campo não suportado: {field_type}.")


def _with_location(
    findings: tuple[Finding, ...], record: ParsedSpedLine, field_name: str
) -> list[Finding]:
    return [
        Finding(
            code=finding.code,
            severity=finding.severity,
            message=finding.message,
            record=record.record_code,
            field=field_name.lower(),
            line_no=record.line_no,
            observed=record.raw,
        )
        for finding in findings
    ]


def _finding(code: str, message: str) -> Finding:
    return Finding(code=code, severity=FindingSeverity.ERROR, message=message)
