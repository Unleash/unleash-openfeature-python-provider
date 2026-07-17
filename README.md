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

## Test Harness

This repository includes the OpenFeature provider verifier as a git submodule.
After cloning, initialize it before running the full test suite:

```bash
git submodule update --init --recursive
```

If the verifier submodule is intentionally updated, refresh it and commit the
new submodule pointer:

```bash
git submodule update --remote --merge verifier
git status
```

## Use

```python
from openfeature import api
from openfeature.evaluation_context import EvaluationContext

from unleash_openfeature_python_provider import UnleashFlagProvider

# The provider builds and owns the Unleash client. Pass the same options you
provider = UnleashFlagProvider(
    url="https://app.unleash-hosted.com/demo/api",
    app_name="my-app",
    custom_headers={"Authorization": "<client-api-key>"},
)

api.set_provider_and_wait(provider)

client = api.get_client()
enabled = client.get_boolean_value(
    "my-feature",
    False,
    EvaluationContext(targeting_key="user-123"),
)
```

## Example

```bash
uv run python examples/boolean_flag.py \
  --url https://app.unleash-hosted.com/demo/api \
  --api-key "$UNLEASH_API_KEY" \
  --flag-key my-feature \
  --targeting-key user-123
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
