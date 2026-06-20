# Step 001 — Bare scaffold

Read `CLAUDE.md` for project context before starting.

## Goal

Working uv-managed Python project with a runnable Typer CLI stub. End state:

```
$ uv run ingest --help
```

…shows a Typer help screen with one `info` command.

This step validates the whole skeleton end-to-end before we add any real logic.

## Directory structure to create

```
finance-kb/
├── pyproject.toml
├── .python-version
├── .gitignore
├── .env.example
├── README.md
├── CLAUDE.md                    # already exists
│
├── ingest/
│   ├── __init__.py
│   ├── cli.py
│   └── sources/
│       └── __init__.py
│
├── api/
│   └── __init__.py              # placeholder only
│
├── data/
│   ├── raw/.gitkeep
│   ├── processed/.gitkeep
│   └── index/.gitkeep
│
└── docs/
    ├── sources.md               # template
    └── learnings.md             # template
```

## File contents

### `pyproject.toml`

```toml
[project]
name = "finance-kb"
version = "0.1.0"
description = "Personal knowledge base for EU/UK capital reporting"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.12",
    "anthropic>=0.40",
    "python-dotenv>=1.0",
]

[project.scripts]
ingest = "ingest.cli:app"

[dependency-groups]
dev = ["ruff>=0.6", "pytest>=8.0"]
```

### `.python-version`

```
3.12
```

### `ingest/cli.py`

```python
import typer

app = typer.Typer(help="Finance KB ingestion pipeline")


@app.command()
def info() -> None:
    """Print project info."""
    typer.echo("finance-kb ingest CLI — ready")


if __name__ == "__main__":
    app()
```

### `.gitignore`

```
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/

# Env
.env

# Data (never commit downloaded docs or vector index)
data/raw/*
data/processed/*
data/index/*
!data/**/.gitkeep

# Node (for later)
node_modules/
.next/

# IDE
.vscode/
.idea/
.DS_Store
```

### `.env.example`

```
ANTHROPIC_API_KEY=
# Embedding provider key will go here once chosen
```

### `README.md`

Real README (not placeholder). Sections:

- **What this is** — one paragraph derived from `CLAUDE.md`.
- **Architecture** — short version of the three-piece split.
- **Setup** — `uv sync`, copy `.env.example` to `.env`, fill in keys.
- **Current phase** — Phase 0, Step 001 (scaffold).

### `docs/sources.md`

Template only. Markdown table with columns: source name, URL, jurisdiction, doc type (regulation / guideline / glossary / primer), date retrieved, version, notes. One example row in italics so the format is clear. No real sources yet.

### `docs/learnings.md`

Empty template. Heading + one-line description: "Capital reporting concepts, terminology, and surprises encountered while building this project." No content yet.

### `ingest/__init__.py`, `ingest/sources/__init__.py`, `api/__init__.py`

Empty files.

### `data/**/.gitkeep`

Empty files to preserve directory structure in git.

## Verification checklist

After implementation, run these four checks and confirm each passes:

1. `uv sync` — installs cleanly, creates `.venv`, no errors.
2. `uv run ingest --help` — shows Typer help with the `info` command listed.
3. `uv run ingest info` — prints `finance-kb ingest CLI — ready`.
4. `git status` (after `git init` if not done) — shows only the files intended for commit. No `__pycache__`, no `.venv`, no data files.

## Constraints

- Do **not** add dependencies beyond what's listed in `pyproject.toml` above.
- Do **not** add logic beyond the CLI stub. No real ingestion code yet.
- Do **not** create the `web/` directory yet — deferred until the API exists.
- Do **not** write tests yet — there's no logic to test.
- Do **not** create `sources/eba.py`, `sources/pra.py`, etc. yet — those come in Step 3.

## When done

Report back with:
- Confirmation that all four checks pass.
- Output of `uv run ingest info` and `uv run ingest --help`.
- Tree of created files (`tree -L 3 -a -I '.venv|__pycache__|.git'` or equivalent).
