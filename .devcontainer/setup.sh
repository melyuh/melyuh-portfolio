#!/usr/bin/env bash
set -euo pipefail

echo "==> uv sync"
uv sync

echo "==> pnpm install"
pnpm install

echo "==> pre-commit install"
uv run pre-commit install

echo "==> setup complete"
