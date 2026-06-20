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
