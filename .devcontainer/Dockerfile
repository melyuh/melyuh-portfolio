FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Astral公式イメージから uv と uvx のバイナリだけを純粋にコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# weasyprint (PDF生成) と cffi のビルドに必要なシステムライブラリ
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*