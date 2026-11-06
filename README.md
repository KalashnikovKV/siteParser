# Поиск ПК на Skelbiu с запасом апгрейда

Скрипт качает объявления с [skelbiu.lt](https://ru.skelbiu.lt/skelbimai/kompiuterija/kompiuteriai/), раскладывает комплектующие и оставляет те машины, где **материнская плата ещё живая**, а текущие CPU/GPU/RAM далеки от её потолка.

Качаем **всю** категорию `/kompiuteriai/` (ноутбуки, стационарные, серверы). Поиск, фильтры и оценка апгрейда идут уже по локальной SQLite — без повторных запросов на сайт.

## Алгоритм

Идея: потенциал апгрейда = потолок платы минус то, что уже стоит.

```
fetch: вся /kompiuteriai/ → SQLite + история цен
        ↓
analyze / UI: поиск и логика только по локальной БД
        ↓
разбор частей → сокет/чипсет → оценка 4 блоками
```

1. **Сначала загрузка всей категории.** `fetch` только качает. Поиск и апгрейд — отдельный шаг по БД.
2. **Индекс важнее карточек.** Сначала список, потом детали точечно.
3. **Плата задаёт потолок.** CPU/чипсет → сокет (AM5, AM4, LGA1700…). Живая платформа даёт до 40 баллов.
4. **Запас (до 35).** Насколько текущий камень слабее потолка сокета.
5. **Расширяемость (до 15).** Мало RAM, нормальный БП, не урезанный чипсет.
6. **Цена (до 10).** Если в карточке одна сумма, а в тексте «Kaina: … €» другая — берём текст.
7. **Отсев.** Ноутбуки, мёртвые сокеты, объявления без платы и CPU.

Порог «есть потенциал» — сумма **≥ 40**.

Локальная модель (Ollama, по умолчанию `qwen3.5:4b`) ставит `брать` / `смотреть` / `пропуск`. Нужна Ollama на `127.0.0.1:11434`. Выключить: `SKELBIU_ADVISOR=off`.

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

Первый заход часто упирается в Cloudflare. Один раз откройте окно и подтвердите, что вы не робот — профиль сохранится в `data/browser_profile/`:

```bash
python -m skelbiu_pc fetch --headed --max-pages 2 --limit-details 20
python -m skelbiu_pc analyze
python -m skelbiu_pc advise --limit 80
python -m skelbiu_pc serve
```

UI: http://127.0.0.1:8765/  (после `npm run build` в `web/`)

Фронт в режиме разработки:

```bash
cd web && npm install && npm run dev
```

UI: http://127.0.0.1:5173  API: http://127.0.0.1:8765

По умолчанию API слушает **только localhost**. Чтобы открыть из LAN: `SKELBIU_HOST=0.0.0.0 python -m skelbiu_pc serve`.

```bash
python -m skelbiu_pc report --min-score 40 --top 30
python -m skelbiu_pc history 100001
python -m pytest
```

База: `data/skelbiu.db`. Каталоги железа: `skelbiu_pc/catalogs/*.json`.

## Docker

```bash
docker compose up -d --build
```

UI: http://127.0.0.1:8765/  
Образ с Chromium: кнопки «докачать описания» / fetch работают из UI.

Только индекс без UI:

```bash
docker compose --profile scrape run --rm scrape
```
