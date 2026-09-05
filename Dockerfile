FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-bookworm AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SKELBIU_HOST=127.0.0.1 \
    SKELBIU_PORT=8765 \
    SKELBIU_SOURCE=skelbiu
COPY pyproject.toml README.md ./
COPY skelbiu_pc ./skelbiu_pc
RUN pip install --no-cache-dir .
COPY --from=web /web/dist ./web/dist
VOLUME /app/data

FROM runtime AS serve
EXPOSE 8765
CMD ["python", "-m", "skelbiu_pc", "serve"]

FROM runtime AS scrape
RUN playwright install --with-deps chromium
CMD ["python", "-m", "skelbiu_pc", "fetch", "--skip-details"]
