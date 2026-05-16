#!/usr/bin/env bash
set -euo pipefail

echo "==> uv sync"
uv sync

echo "==> pnpm install"
pnpm install

echo "==> puppeteer: install chrome-headless-shell"
pnpm exec puppeteer browsers install chrome-headless-shell

echo "==> playwright: install chromium"
uv run playwright install chromium

echo "==> pre-commit install"
uv run pre-commit install

echo "==> setup complete"
