from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    store_path: Path
    spec_path: Path
    upload_path: Path
    development_tenant: str | None
    max_upload_bytes: int = 100 * 1024 * 1024

    @classmethod
    def development(cls, root: Path) -> Settings:
        return cls(
            store_path=root / "data",
            spec_path=root
            / "packages"
            / "fiscal-spec"
            / "specs"
            / "candidates"
            / "efd_contribuicoes_0000_v1_35.yaml",
            upload_path=root / "data" / "incoming",
            development_tenant="demo",
        )
