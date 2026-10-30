from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

from fiscal_model import Finding, FindingSeverity, validate_access_key


@dataclass(frozen=True, slots=True)
class NfeDocument:
    key: str
    competence: date
    header: dict[str, object]
    items: list[dict[str, object]]
    findings: list[Finding]


def parse_nfe(path: str | Path) -> NfeDocument:
    root = ElementTree.parse(path).getroot()
    inf_nfe = _find_first(root, "infNFe")
    if inf_nfe is None:
        raise ValueError("XML não contém o grupo infNFe de uma NF-e/NFC-e.")

    key = inf_nfe.attrib.get("Id", "").removeprefix("NFe")
    validation = validate_access_key(key)
    findings = [] if validation.is_valid else [_invalid_key_finding(key)]

    ide = _required_child(inf_nfe, "ide")
    emit = _required_child(inf_nfe, "emit")
    dest = _find_child(inf_nfe, "dest")
    total = _find_child(_required_child(inf_nfe, "total"), "ICMSTot")
    issued_at = _parse_issue_date(_text(ide, "dhEmi") or _text(ide, "dEmi"))
    if issued_at is None:
        raise ValueError("XML NF-e sem data de emissão válida.")

    header: dict[str, object] = {
        "document_key": key,
        "model": _text(ide, "mod"),
        "series": _text(ide, "serie"),
        "number": _text(ide, "nNF"),
        "issued_at": issued_at,
        "issuer_tax_id": _text(emit, "CNPJ") or _text(emit, "CPF"),
        "issuer_state": _text(_find_child(emit, "enderEmit"), "UF"),
        "recipient_tax_id": _text(dest, "CNPJ") or _text(dest, "CPF"),
        "recipient_state": _text(_find_child(dest, "enderDest"), "UF"),
        "total_value": _decimal(_text(total, "vNF")),
        "layout_version": inf_nfe.attrib.get("versao"),
    }
    competence = date(issued_at.year, issued_at.month, 1)
    return NfeDocument(key, competence, header, _items(inf_nfe, key), findings)


def _items(inf_nfe: ElementTree.Element, key: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for detail in _children(inf_nfe, "det"):
        product = _required_child(detail, "prod")
        items.append(
            {
                "document_key": key,
                "item_number": int(detail.attrib["nItem"]),
                "product_code": _text(product, "cProd"),
                "description": _text(product, "xProd"),
                "ncm": _text(product, "NCM"),
                "cfop": _text(product, "CFOP"),
                "quantity": _decimal(_text(product, "qCom")),
                "unit_value": _decimal(_text(product, "vUnCom")),
                "total_value": _decimal(_text(product, "vProd")),
            }
        )
    return items


def _invalid_key_finding(key: str) -> Finding:
    return Finding(
        code="V-KEY-001",
        severity=FindingSeverity.ERROR,
        message="A chave de acesso da NF-e é inválida.",
        field="document_key",
        observed=key,
    )


def _parse_issue_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Valor decimal inválido no XML: {value}") from error


def _local_name(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", maxsplit=1)[-1]


def _find_child(element: ElementTree.Element | None, name: str) -> ElementTree.Element | None:
    if element is None:
        return None
    return next((child for child in element if _local_name(child) == name), None)


def _find_first(element: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((node for node in element.iter() if _local_name(node) == name), None)


def _children(element: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in element if _local_name(child) == name]


def _required_child(element: ElementTree.Element, name: str) -> ElementTree.Element:
    child = _find_child(element, name)
    if child is None:
        raise ValueError(f"XML NF-e sem o grupo obrigatório {name}.")
    return child


def _text(element: ElementTree.Element | None, name: str) -> str | None:
    child = _find_child(element, name)
    return child.text.strip() if child is not None and child.text else None
