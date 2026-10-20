"""Network IO is explicit, bounded and never runs at module import."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DataError(ValueError):
    """An input violates a documented data contract."""


def download(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        request = Request(url, headers={"User-Agent": "CaliforniaHousingAtlas/0.1 (research)"})
        with urlopen(request, timeout=90) as response:
            payload = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise DataError(f"Download failed for {url}: {exc}. Existing cache was not changed.") from exc
    if not payload:
        raise DataError(f"Empty response: {url}")
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(target)
    return target


def provenance(paths: list[Path], urls: list[str], target: Path) -> None:
    target.write_text(
        json.dumps(
            {
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "sources": urls,
                "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            },
            indent=2,
        )
        + "\n"
    )
