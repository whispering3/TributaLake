from __future__ import annotations

from dataclasses import dataclass

from fiscal_model import Finding, FindingSeverity


@dataclass(frozen=True, slots=True)
class ParsedSpedLine:
    line_no: int
    raw: str
    record_code: str
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecordParseResult:
    record: ParsedSpedLine | None
    findings: tuple[Finding, ...]
    raw: str


def parse_sped_line(raw: str, line_no: int) -> RecordParseResult:
    normalized = raw.rstrip("\r\n")
    if not normalized.startswith("|") or not normalized.endswith("|"):
        return RecordParseResult(None, (_malformed_line(line_no, normalized),), normalized)

    values = normalized[1:-1].split("|")
    if not values or not values[0]:
        return RecordParseResult(None, (_malformed_line(line_no, normalized),), normalized)

    return RecordParseResult(
        ParsedSpedLine(line_no, normalized, values[0], tuple(values[1:])),
        (),
        normalized,
    )


def _malformed_line(line_no: int, raw: str) -> Finding:
    return Finding(
        code="V-STR-001",
        severity=FindingSeverity.ERROR,
        message="A linha SPED deve iniciar e terminar com o caractere pipe.",
        line_no=line_no,
        observed=raw,
    )
