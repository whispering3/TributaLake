from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fiscal_spec.models import LayoutSpec


def load_spec(path: str | Path) -> LayoutSpec:
    source = Path(path)
    with source.open(encoding="utf-8") as stream:
        content: Any = yaml.safe_load(stream)
    if not isinstance(content, dict):
        raise ValueError("A raiz da spec deve ser um mapa YAML.")
    return LayoutSpec.from_mapping(content)
