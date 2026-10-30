from pathlib import Path

from fiscal_spec import load_spec


def test_loads_efd_contribuicoes_candidate_spec() -> None:
    root = Path(__file__).parents[1]
    source = root / "specs" / "candidates" / "efd_contribuicoes_0000_v1_35.yaml"

    spec = load_spec(source)

    assert spec.module == "efd_contrib"
    assert spec.records["0000"].fields[5].name == "DT_INI"
