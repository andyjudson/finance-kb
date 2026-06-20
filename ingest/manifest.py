"""Append-only JSONL manifest writer and reader."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append(path: Path, record: dict[str, Any]) -> None:
    """Append one JSON record to *path* (creates file and parents if needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_all(path: Path) -> list[dict[str, Any]]:
    """Return all records from *path*; empty list if file doesn't exist."""
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def already_processed(manifest_path: Path, slug: str) -> bool:
    """True if *slug* appears with status 'ok' in the manifest."""
    for record in read_all(manifest_path):
        if record.get("slug") == slug and record.get("status") == "ok":
            return True
    return False
