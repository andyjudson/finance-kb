import typer

app = typer.Typer(help="Finance KB ingestion pipeline")


@app.callback()
def main() -> None:
    """Finance KB ingestion pipeline."""


@app.command()
def info() -> None:
    """Print project info."""
    typer.echo("finance-kb ingest CLI — ready")


if __name__ == "__main__":
    app()
