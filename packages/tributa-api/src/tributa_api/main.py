from __future__ import annotations

import uvicorn

from tributa_api.app import create_app


def run() -> None:
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
