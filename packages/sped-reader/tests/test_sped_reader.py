from pathlib import Path

from sped_reader import SpedReader


def test_streams_records_and_routes_malformed_line_to_findings(tmp_path: Path) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("|0000|016|0|01012026|31012026|\ninvalid\n|C100|0|\n", encoding="utf-8")

    records = list(SpedReader().stream(source))

    assert records[0].record is not None
    assert records[0].record.record_code == "0000"
    assert records[1].record is None
    assert records[1].findings[0].code == "V-STR-001"
    assert records[2].record is not None


def test_detects_cp1252_without_loading_the_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.txt"
    source.write_bytes("|0000|016|RAZÃO|\n".encode("cp1252"))

    encoding = SpedReader().inspect(source)

    assert encoding.name == "cp1252"
