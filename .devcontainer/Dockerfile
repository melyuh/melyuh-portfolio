FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Astral公式イメージから uv と uvx のバイナリだけを純粋にコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# weasyprint (PDF生成) と cffi のビルドに必要なシステムライブラリ
# および Chrome headless shell (mermaid-to-svg の Puppeteer) に必要なライブラリ
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    libnspr4 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libx11-xcb1 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*