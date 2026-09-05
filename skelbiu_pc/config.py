"""Настройки пайплайна. Всегда сначала грузим свежие объявления, потом анализируем."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "skelbiu.db"
BROWSER_PROFILE = DATA_DIR / "browser_profile"
REPORTS_DIR = DATA_DIR / "reports"

# Качаем всю категорию компьютеров. Поиск и апгрейд — уже по локальной БД.
DEFAULT_LIST_URL = "https://ru.skelbiu.lt/skelbimai/kompiuterija/kompiuteriai/"
ALL_COMPUTERS_URL = DEFAULT_LIST_URL
DESKTOPS_URL = (
    "https://ru.skelbiu.lt/skelbimai/kompiuterija/kompiuteriai/"
    "stacionarus-kompiuteriai/"
)
API_HOST = os.environ.get("SKELBIU_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("SKELBIU_PORT", "8765"))
DEFAULT_SOURCE = os.environ.get("SKELBIU_SOURCE", "skelbiu")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# Вежливые паузы: быстрые, пока профиль тёплый; если Cloudflare — откат.
PAGE_DELAY_SEC = (1.6, 3.2)
DETAIL_DELAY_FAST_SEC = (0.3, 0.6)
DETAIL_DELAY_SAFE_SEC = (1.2, 2.3)
DETAIL_DELAY_SEC = DETAIL_DELAY_SAFE_SEC

# Полное описание: не вся база, а кандидаты и свежие без текста.
DETAIL_TTL_DAYS = 14
DETAIL_MIN_SCORE = float(os.environ.get("SKELBIU_DETAIL_MIN_SCORE", "30"))
NAV_TIMEOUT_MS = 45_000

# Порог, выше которого объявление считается «с потенциалом апгрейда».
MIN_UPGRADE_SCORE = 40.0

# Локальный советник (Ollama). Не качаем все 7k — только кандидаты.
ADVISOR_BACKEND = os.environ.get("SKELBIU_ADVISOR", "ollama")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")
OLLAMA_TIMEOUT_SEC = int(os.environ.get("OLLAMA_TIMEOUT", "120"))
ADVISE_DEFAULT_LIMIT = int(os.environ.get("SKELBIU_ADVISE_LIMIT", "80"))
