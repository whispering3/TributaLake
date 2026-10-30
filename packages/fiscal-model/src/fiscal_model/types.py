from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: FindingSeverity
    message: str
    record: str | None = None
    field: str | None = None
    line_no: int | None = None
    observed: str | None = None
    expected: str | None = None


@dataclass(frozen=True, slots=True)
class Lineage:
    tenant_id: str
    file_id: str
    line_no: int | None
    parent_line_no: int | None
    layout_version: str | None
    parser_version: str
    competencia: date | None


@dataclass(frozen=True, slots=True)
class FileFingerprint:
    sha256: str
    size_bytes: int


@dataclass(slots=True)
class IngestionReport:
    file_id: str
    tenant_id: str
    status: str
    records_written: int = 0
    records_quarantined: int = 0
    findings: list[Finding] = field(default_factory=list)

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)

    def summary(self) -> dict[str, int | str]:
        return {
            "file_id": self.file_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "records_written": self.records_written,
            "records_quarantined": self.records_quarantined,
            "findings": len(self.findings),
        }
