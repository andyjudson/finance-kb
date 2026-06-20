"""Read/write markdown + YAML frontmatter with canonical field ordering."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter as fm
import yaml

# Canonical field order for all sources. Fields absent from a given document
# are simply omitted; extra fields go at the end.
_FIELD_ORDER = [
    "source_url",
    "source",
    "slug",
    "title",
    "fetched_at",
    "internal_links",
    "images_dropped",
    "parse_warnings",
    "parser_version",
]


class _OrderedDumper(yaml.Dumper):
    """YAML dumper that preserves dict insertion order."""
    pass


def _represent_dict_ordered(dumper: yaml.Dumper, data: dict) -> yaml.Node:
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())


_OrderedDumper.add_representer(dict, _represent_dict_ordered)


def _ordered_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in _FIELD_ORDER:
        if key in meta:
            ordered[key] = meta[key]
    for key, val in meta.items():
        if key not in ordered:
            ordered[key] = val
    return ordered


def _dumps(body: str, metadata: dict[str, Any]) -> str:
    """Serialise body + metadata to frontmatter markdown string."""
    ordered = _ordered_metadata(metadata)
    yaml_str = yaml.dump(
        ordered,
        Dumper=_OrderedDumper,
        allow_unicode=True,
        default_flow_style=False,
    )
    return f"---\n{yaml_str}---\n\n{body}\n"


def write(path: Path, body: str, metadata: dict[str, Any]) -> None:
    """Write *body* with *metadata* as YAML frontmatter to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dumps(body, metadata), encoding="utf-8")


def read(path: Path) -> tuple[str, dict[str, Any]]:
    """Return (body, metadata) from a frontmatter markdown file."""
    post = fm.load(str(path))
    return post.content, dict(post.metadata)
