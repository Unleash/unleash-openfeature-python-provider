# Unleash OpenFeature Python Provider

Python project scaffold managed with [uv](https://docs.astral.sh/uv/).

## Prerequisites

- Python 3.10+
- uv

## Install

```bash
uv add unleash-openfeature-python-provider
```

For local development, sync the project environment:

```bash
uv sync --dev
```

## Use

```python
import unleash_openfeature_python_provider

print(unleash_openfeature_python_provider.__version__)
```

## Build

```bash
uv build
```

Build artifacts are written to `dist/`.

## Test

```bash
uv run pytest
```

## Lint, Format, And Type Check

```bash
uv run ruff check
uv run ruff format
uv run basedpyright
```
