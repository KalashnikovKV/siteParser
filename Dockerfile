# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Зависимости ставятся по lock-файлу с хэшами и до кода: правка кода не пересобирает этот слой.
FROM python:3.15-slim-bookworm AS base
ARG APP_UID=1000
ARG APP_GID=1000
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    SKELBIU_HOST=127.0.0.1 \
    SKELBIU_PORT=8765 \
    SKELBIU_SOURCE=skelbiu
RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid app --home-dir /tmp --no-create-home \
       --shell /usr/sbin/nologin app
WORKDIR /app
COPY requirements.txt ./
RUN pip install --require-hashes -r requirements.txt

FROM base AS browsers
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Код принадлежит root и только читается; писать процесс может лишь в /app/data и /tmp.
FROM base AS serve
COPY --from=web /web/dist ./web/dist
COPY skelbiu_pc ./skelbiu_pc
RUN install -d -o app -g app /app/data
USER app
ENV HOME=/tmp
VOLUME ["/app/data"]
EXPOSE 8765
CMD ["python", "-m", "skelbiu_pc", "serve"]

FROM browsers AS scrape
COPY --from=web /web/dist ./web/dist
COPY skelbiu_pc ./skelbiu_pc
RUN install -d -o app -g app /app/data
USER app
ENV HOME=/tmp
VOLUME ["/app/data"]
EXPOSE 8765
CMD ["python", "-m", "skelbiu_pc", "fetch", "--skip-details"]
