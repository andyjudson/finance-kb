from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from ingest.errors import CircuitBreakerOpen

app = typer.Typer(help="Finance KB ingestion pipeline")


@app.callback()
def main() -> None:
    """Finance KB ingestion pipeline."""


@app.command()
def info() -> None:
    """Print project info."""
    typer.echo("finance-kb ingest CLI — ready")


@app.command("investor-gov")
def investor_gov(
    refresh: Annotated[bool, typer.Option("--refresh", help="Re-fetch even if cached")] = False,
    limit: Annotated[Optional[int], typer.Option("--limit", help="Process only first N slugs")] = None,
    terms_file: Annotated[
        Optional[Path], typer.Option("--terms-file", help="Path to investor-gov-terms.md")
    ] = None,
) -> None:
    """Fetch and parse Investor.gov glossary terms."""
    from ingest.sources import investor_gov as ig

    slugs = ig.load_slugs_from_file(terms_file)
    if limit is not None:
        slugs = slugs[:limit]

    typer.echo(f"Investor.gov: processing {len(slugs)} term(s)...")

    try:
        result = ig.run(slugs, refresh=refresh)
    except CircuitBreakerOpen as exc:
        typer.echo(f"\nABORTED — {exc}", err=True)
        raise typer.Exit(1)

    _print_summary(result, manifest_path="data/processed/investor_gov/manifest.jsonl")


@app.command()
def investopedia(
    source_dir: Annotated[
        Path,
        typer.Option("--source-dir", help="Directory of saved .html files"),
    ] = Path.home() / "Downloads" / "investopedia",
    limit: Annotated[Optional[int], typer.Option("--limit", help="Process only first N files")] = None,
) -> None:
    """Parse locally-saved Investopedia HTML files (no network access)."""
    from ingest.sources import investopedia as inv

    if not source_dir.exists():
        typer.echo(f"Error: source-dir not found: {source_dir}", err=True)
        raise typer.Exit(1)

    html_files = sorted(source_dir.glob("*.html"))
    n = len(html_files) if limit is None else min(limit, len(html_files))
    typer.echo(f"Investopedia: processing {n} file(s) from {source_dir} ...")

    result = inv.run(source_dir, limit=limit)
    _print_summary(result, manifest_path="data/processed/investopedia/manifest.jsonl")


@app.command()
def boe(
    refresh: Annotated[bool, typer.Option("--refresh", help="Re-fetch even if cached")] = False,
    limit: Annotated[Optional[int], typer.Option("--limit", help="Process only first N URLs")] = None,
    skip_discovery: Annotated[bool, typer.Option("--skip-discovery", help="Use only cached raw HTML")] = False,
) -> None:
    """Crawl and parse the BoE Knowledge Bank explainer articles."""
    from ingest.errors import CircuitBreakerOpen
    from ingest.sources import boe as boe_mod
    from ingest import http as http_mod

    if skip_discovery:
        raw_dir = boe_mod._RAW_DIR
        urls = sorted(
            f"https://www.bankofengland.co.uk/explainers/{p.stem}"
            for p in raw_dir.glob("*.html")
        ) if raw_dir.exists() else []
        typer.echo(f"BoE (offline): {len(urls)} cached articles")
    else:
        typer.echo("BoE: discovering articles (two-pass crawl)...")
        cb = http_mod.CircuitBreaker()
        try:
            urls = boe_mod.discover_urls(cb)
        except CircuitBreakerOpen as exc:
            typer.echo(f"\nABORTED during discovery — {exc}", err=True)
            raise typer.Exit(1)
        typer.echo(f"BoE: discovered {len(urls)} unique article URLs")

    if limit is not None:
        urls = urls[:limit]
        typer.echo(f"BoE: processing first {len(urls)} (--limit)")

    try:
        result = boe_mod.run(urls, refresh=refresh)
    except CircuitBreakerOpen as exc:
        typer.echo(f"\nABORTED — {exc}", err=True)
        raise typer.Exit(1)

    _print_summary(result, manifest_path="data/processed/boe/manifest.jsonl")


@app.command("boe-glossary")
def boe_glossary(
    refresh: Annotated[bool, typer.Option("--refresh", help="Re-fetch even if cached")] = False,
    limit: Annotated[Optional[int], typer.Option("--limit", help="Process only first N terms")] = None,
) -> None:
    """Fetch and parse the BoE A-Z glossary (~570 abbreviation terms)."""
    from ingest.sources import boe_glossary as bg

    typer.echo("BoE Glossary: fetching and parsing...")
    result = bg.run(refresh=refresh, limit=limit)
    _print_summary(result, manifest_path="data/processed/boe_glossary/manifest.jsonl")


@app.command()
def chunk(
    source: Annotated[
        str,
        typer.Option(
            "--source",
            help="Source to chunk: investor-gov | investopedia | boe | boe-glossary | all",
        ),
    ] = "all",
    limit: Annotated[Optional[int], typer.Option("--limit", help="Process only first N docs per source")] = None,
) -> None:
    """Chunk processed markdown files into JSONL ready for embedding."""
    import json
    from ingest import chunker, frontmatter_io

    _SOURCE_MAP = {
        "investor-gov":  ("investor_gov",  Path("data/processed/investor_gov")),
        "investopedia":  ("investopedia",  Path("data/processed/investopedia")),
        "boe":           ("boe",           Path("data/processed/boe")),
        "boe-glossary":  ("boe_glossary",  Path("data/processed/boe_glossary")),
    }

    targets = list(_SOURCE_MAP.items()) if source == "all" else [
        (source, _SOURCE_MAP[source]) if source in _SOURCE_MAP
        else _bail(f"Unknown source '{source}'. Choose from: {', '.join(_SOURCE_MAP)} or all")
    ]

    chunks_dir = Path("data/chunks")
    chunks_dir.mkdir(parents=True, exist_ok=True)

    grand_total = 0
    for cli_name, (src_key, processed_dir) in targets:
        if not processed_dir.exists():
            typer.echo(f"  {cli_name}: processed dir not found — skipping ({processed_dir})")
            continue

        doc_files = sorted(f for f in processed_dir.glob("*.md") if f.name != "manifest.jsonl")
        if limit is not None:
            doc_files = doc_files[:limit]

        out_path = chunks_dir / f"{src_key}.jsonl"
        doc_count = 0
        chunk_count = 0
        token_counts: list[int] = []

        with out_path.open("w", encoding="utf-8") as fh:
            for doc_file in doc_files:
                body, metadata = frontmatter_io.read(doc_file)
                if not body.strip():
                    continue
                doc_chunks = chunker.chunk_document(body, metadata)
                for c in doc_chunks:
                    fh.write(json.dumps(c, ensure_ascii=False) + "\n")
                    token_counts.append(c["token_count"])
                chunk_count += len(doc_chunks)
                doc_count += 1

        if token_counts:
            token_counts.sort()
            n = len(token_counts)
            p50 = token_counts[n // 2]
            p90 = token_counts[n * 9 // 10]
            typer.echo(
                f"  {cli_name}: {doc_count} docs → {chunk_count} chunks  "
                f"(tokens: min={token_counts[0]} p50={p50} p90={p90} max={token_counts[-1]})"
            )
        else:
            typer.echo(f"  {cli_name}: 0 docs processed")
        grand_total += chunk_count

    typer.echo(f"\nTotal chunks: {grand_total}  →  data/chunks/")


def _bail(msg: str):
    typer.echo(f"Error: {msg}", err=True)
    raise typer.Exit(1)


def _print_summary(result: dict, manifest_path: str) -> None:
    counts = result["counts"]
    errors = result["errors_by_category"]

    typer.echo(
        f"\nDone — attempted: {counts['attempted']}, "
        f"ok: {counts['ok']}, "
        f"error: {counts['error']}"
    )

    if errors:
        typer.echo("\nFailures by category:")
        for cat, slugs in sorted(errors.items()):
            typer.echo(f"  [{cat}] {', '.join(slugs)}")

    typer.echo(f"\nManifest: {manifest_path}")


if __name__ == "__main__":
    app()
