from datetime import date
from pathlib import Path

import pytest
from fiscal_spec import load_spec


def test_loads_yaml_spec_with_decimal_and_enum_constraints(tmp_path: Path) -> None:
    source = tmp_path / "layout.yaml"
    source.write_text(
        """
module: efd_contrib
layout_version: '016'
valid_from: 2026-01-01
records:
  C100:
    block: C
    parent: C010
    fields:
      - {n: 1, name: REG, type: str, req: O}
      - {n: 2, name: IND_OPER, type: enum, req: O, values: ['0', '1']}
      - {n: 3, name: VL_DOC, type: decimal, req: OC, precision: 18, scale: 2}
""",
        encoding="utf-8",
    )

    spec = load_spec(source)

    assert spec.valid_from == date(2026, 1, 1)
    assert spec.records["C100"].parent == "C010"
    assert spec.records["C100"].fields[2].precision == 18
    assert spec.records["C100"].fields[1].values == ("0", "1")


def test_rejects_invalid_spec_root(tmp_path: Path) -> None:
    source = tmp_path / "layout.yaml"
    source.write_text("- invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="raiz"):
        load_spec(source)
