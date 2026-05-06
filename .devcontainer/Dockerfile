FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Astral公式イメージから uv と uvx のバイナリだけを純粋にコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/