from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DetectedEncoding:
    name: str
    has_bom: bool


def detect_encoding(path: str | Path) -> DetectedEncoding:
    """Detecta a codificação sem carregar o arquivo SPED inteiro em memória."""
    source = Path(path)
    with source.open("rb") as stream:
        prefix = stream.read(3)
    if prefix.startswith(b"\xef\xbb\xbf"):
        return DetectedEncoding("utf-8-sig", True)
    for encoding in ("utf-8", "cp1252", "latin-1"):
        if _can_decode(source, encoding):
            return DetectedEncoding(encoding, False)
    raise ValueError("Não foi possível identificar uma codificação suportada para o arquivo SPED.")


def _can_decode(path: Path, encoding: str) -> bool:
    try:
        with path.open("r", encoding=encoding, newline="") as stream:
            while stream.read(1024 * 1024):
                pass
    except UnicodeDecodeError:
        return False
    return True
