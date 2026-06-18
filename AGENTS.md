# AGENTS.md

## Project Notes

- `DESIGN.md` describes the intended FHIR-to-BigQuery ETL behavior and deployment shape.
- Use `uv` for Python environment and dependency management.

## Docker

- Keep the Docker image runnable from repository root using `Dockerfile`.
- Use a multi-stage Docker build so build tools stay out of the final runtime image.
- Put `/app/.venv/bin` on `PATH` in the runtime image and use console script names directly in `CMD`.

## CI

- Keep checks and Docker publishing in separate GitHub Actions workflows.
- Use the latest tagged version for GitHub Actions `uses:` entries, pin them to full commit hashes, and include the source tag in a comment.

## Docs

- Keep `README.md` up to date for any user-facing workflow, command, packaging, or CI change.

## Corrections

When a requested correction reveals a reusable repo convention, update this file in the same change so future agents do not need the same correction again.

## Checks

Run these before handing off changes:

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check .
uv run pytest
```
