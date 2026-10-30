from pathlib import Path

from dfe_tabular.schema_validation import validate_nfe_schema


def test_reports_malformed_nfe_schema_without_raising(tmp_path: Path) -> None:
    source = tmp_path / "invalid.xml"
    source.write_text("<NFe />", encoding="utf-8")

    findings = validate_nfe_schema(source)

    assert findings
    assert all(finding.code == "V-XML-003" for finding in findings)
