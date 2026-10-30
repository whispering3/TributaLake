from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from fiscal_model import Finding, FindingSeverity
from nfelib.nfe.bindings.v4_0.nfe_v4_00 import Nfe
from nfelib.nfe.bindings.v4_0.proc_nfe_v4_00 import NfeProc


def validate_nfe_schema(path: str | Path) -> list[Finding]:
    """Valida NF-e/NFC-e v4.00 com os XSDs distribuídos pela nfelib."""
    source = Path(path)
    try:
        document = _load_binding(source)
        errors = document.validate_xml()
    except Exception as error:
        return [_schema_finding(str(error))]

    return [_schema_finding(str(error)) for error in errors]


def _load_binding(path: Path) -> Any:
    root = ElementTree.parse(path).getroot()
    local_name = root.tag.rsplit("}", maxsplit=1)[-1]
    binding = NfeProc if local_name == "nfeProc" else Nfe
    return binding.from_path(str(path))


def _schema_finding(message: str) -> Finding:
    return Finding(
        code="V-XML-003",
        severity=FindingSeverity.ERROR,
        message=f"XML incompatível com o XSD da NF-e v4.00: {message}",
    )
