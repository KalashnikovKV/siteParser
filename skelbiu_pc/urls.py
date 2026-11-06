"""Внешние ссылки: в UI и в браузер скрапера попадают только обычные http(s)."""

from __future__ import annotations

from urllib.parse import urlsplit


def safe_http_url(url: str | None) -> str | None:
    """http(s)-ссылка с хостом и без логина в URL, иначе None (javascript:, data: и т. п.)."""
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    return parts.geturl()


def host_matches(url: str | None, domain: str) -> bool:
    """URL указывает на domain или его поддомен (ru.skelbiu.lt → skelbiu.lt)."""
    safe = safe_http_url(url)
    if safe is None:
        return False
    host = (urlsplit(safe).hostname or "").rstrip(".").lower()
    domain = domain.lower()
    return host == domain or host.endswith("." + domain)
