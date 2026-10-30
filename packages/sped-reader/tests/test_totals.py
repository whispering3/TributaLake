from sped_reader.records import ParsedSpedLine
from sped_reader.totals import SpedTotals


def test_accepts_matching_9900_and_9999_totals() -> None:
    totals = SpedTotals()
    records = (
        _record(1, "0000", ()),
        _record(2, "9900", ("0000", "1")),
        _record(3, "9900", ("9900", "3")),
        _record(4, "9900", ("9999", "1")),
        _record(5, "9999", ("5",)),
    )
    for record in records:
        totals.add(record)

    assert not totals.findings()


def test_reports_mismatched_record_and_file_totals() -> None:
    totals = SpedTotals()
    for record in (
        _record(1, "0000", ()),
        _record(2, "9900", ("0000", "2")),
        _record(3, "9999", ("9",)),
    ):
        totals.add(record)

    findings = totals.findings()

    assert {finding.code for finding in findings} == {"V-STR-005", "V-STR-006"}


def _record(line_no: int, code: str, fields: tuple[str, ...]) -> ParsedSpedLine:
    return ParsedSpedLine(line_no, f"|{code}|", code, fields)
