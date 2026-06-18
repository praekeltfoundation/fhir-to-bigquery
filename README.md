# fhir-to-bigquery

Stateless Python ETL tool for streaming FHIR Bulk Data Export (`$export`) payloads into BigQuery.

Implementation details live in [DESIGN.md](DESIGN.md). Current repo stage: CI and packaging scaffold only.

## Development

Requires Python from [.python-version](.python-version) and `uv`.

```bash
uv sync --all-groups
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

## Docker

The image uses a multi-stage build. `uv` and build tooling stay in the builder stage;
the runtime image contains the virtual environment and runs the installed console script
from `/app/.venv/bin`.

Build locally:

```bash
docker build -t fhir-to-bigquery .
docker run --rm fhir-to-bigquery
```

## CI

GitHub Actions workflows live in [.github/workflows](.github/workflows).

Workflows:

- `Checks`: installs deps with `uv`, checks formatting with `ruff`, lints with `ruff`, type-checks with `ty`, runs unit tests with `pytest`.
- `Docker`: on pushes and `v*` tags, builds image and publishes to GitHub Container Registry (`ghcr.io/<owner>/<repo>`).

Workflow actions use the latest tagged versions and are pinned to full commit hashes with source tag comments.

Image tags:

- Branch/commit pushes: long commit SHA tag.
- Git tag pushes matching `v*`: Git tag name.

Image labels include:

- `org.opencontainers.image.revision`: commit SHA.
- `org.opencontainers.image.version`: Git tag when present, else commit SHA.
