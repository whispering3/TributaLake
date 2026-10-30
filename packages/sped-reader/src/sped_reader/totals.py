from __future__ import annotations

from collections import Counter

from fiscal_model import Finding, FindingSeverity

from sped_reader.records import ParsedSpedLine


class SpedTotals:
    """Acumula contagens e valida os totalizadores finais do arquivo SPED."""

    def __init__(self) -> None:
        self._record_counts: Counter[str] = Counter()
        self._declared_record_counts: dict[str, tuple[int, int]] = {}
        self._declared_line_count: tuple[int, int] | None = None
        self._line_count = 0

    def add(self, record: ParsedSpedLine | None) -> None:
        self._line_count += 1
        if record is None:
            return
        self._record_counts[record.record_code] += 1
        if record.record_code == "9900":
            self._add_9900(record)
        elif record.record_code == "9999":
            self._add_9999(record)

    def findings(self) -> tuple[Finding, ...]:
        findings = self._record_count_findings()
        if self._declared_line_count is not None:
            declared, line_no = self._declared_line_count
            if declared != self._line_count:
                findings.append(
                    _finding(
                        "V-STR-006",
                        line_no,
                        "Total do registro 9999 difere da quantidade de linhas do arquivo.",
                        str(declared),
                        str(self._line_count),
                    )
                )
        return tuple(findings)

    def _add_9900(self, record: ParsedSpedLine) -> None:
        if len(record.fields) < 2:
            return
        try:
            self._declared_record_counts[record.fields[0]] = (int(record.fields[1]), record.line_no)
        except ValueError:
            return

    def _add_9999(self, record: ParsedSpedLine) -> None:
        if not record.fields:
            return
        try:
            self._declared_line_count = (int(record.fields[0]), record.line_no)
        except ValueError:
            return

    def _record_count_findings(self) -> list[Finding]:
        findings: list[Finding] = []
        for record_code, (declared, line_no) in self._declared_record_counts.items():
            observed = self._record_counts[record_code]
            if declared != observed:
                findings.append(
                    _finding(
                        "V-STR-005",
                        line_no,
                        "Contagem declarada no registro 9900 difere da contagem observada.",
                        str(declared),
                        str(observed),
                    )
                )
        return findings


def _finding(code: str, line_no: int, message: str, expected: str, observed: str) -> Finding:
    return Finding(
        code=code,
        severity=FindingSeverity.ERROR,
        message=message,
        record="9900" if code == "V-STR-005" else "9999",
        line_no=line_no,
        observed=observed,
        expected=expected,
    )
