FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SKELBIU_HOST=0.0.0.0 \
    SKELBIU_PORT=8765 \
    SKELBIU_SOURCE=skelbiu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium
COPY skelbiu_pc ./skelbiu_pc
COPY pytest.ini ./
COPY --from=web /web/dist ./web/dist
EXPOSE 8765
VOLUME /app/data
CMD ["python", "-m", "skelbiu_pc", "serve", "--host", "0.0.0.0", "--port", "8765"]
