"""HTTP-защита локального API.

Сервер слушает localhost, но тот же браузер открывает и чужие сайты. Поэтому:
allowlist заголовка Host (DNS rebinding), свой заголовок на изменяющих запросах
(CSRF), Basic auth при выходе в LAN и строгие заголовки ответа (CSP и др.).
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import os
import secrets
from dataclasses import dataclass
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSRF_HEADER = "X-Skelbiu-Request"
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
PUBLIC_PATHS = frozenset({"/api/health"})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_SAME_ORIGIN_FETCH = frozenset({"same-origin", "none"})

_UI_CSP = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    )
)
_API_CSP = "default-src 'none'; frame-ancestors 'none'"
_COMMON_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}


def normalize_host(value: str | None) -> str | None:
    name = (value or "").strip().strip("[]").rstrip(".").lower()
    return name or None


def is_wildcard_host(host: str) -> bool:
    return normalize_host(host) in (None, "0.0.0.0", "::")


def is_loopback_host(host: str) -> bool:
    name = normalize_host(host)
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name or "").is_loopback
    except ValueError:
        return False


def host_from_header(value: str) -> str | None:
    """Имя хоста из заголовка Host; мусор (логин, путь, кривой порт) → None."""
    value = value.strip()
    if not value or any(ch in value for ch in "@/\\ \t"):
        return None
    try:
        parsed = urlsplit(f"//{value}")
        _ = parsed.port  # ValueError на нечисловом порте
    except ValueError:
        return None
    return normalize_host(parsed.hostname)


@dataclass(frozen=True)
class SecuritySettings:
    allowed_hosts: frozenset[str] = LOOPBACK_HOSTS
    username: str = "skelbiu"
    password: str | None = None

    @property
    def auth_enabled(self) -> bool:
        return bool(self.password)

    @classmethod
    def from_env(cls, bind_host: str | None = None) -> SecuritySettings:
        hosts = set(LOOPBACK_HOSTS)
        for raw in os.environ.get("SKELBIU_ALLOWED_HOSTS", "").split(","):
            name = normalize_host(raw)
            if name:
                hosts.add(name)
        if bind_host and not is_wildcard_host(bind_host):
            name = normalize_host(bind_host)
            if name:
                hosts.add(name)
        return cls(
            allowed_hosts=frozenset(hosts),
            username=os.environ.get("SKELBIU_USER") or "skelbiu",
            password=os.environ.get("SKELBIU_PASSWORD") or None,
        )


class SecurityMiddleware:
    """Проверки до приложения и защитные заголовки на каждом ответе (включая SSE)."""

    def __init__(self, app: ASGIApp, settings: SecuritySettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or "/"
        send = _with_security_headers(send, path)
        rejection = self._reject(scope, path)
        if rejection is not None:
            await rejection(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _reject(self, scope: Scope, path: str) -> JSONResponse | None:
        headers = Headers(scope=scope)
        host = host_from_header(headers.get("host", ""))
        if host is None or host not in self.settings.allowed_hosts:
            return _error(400, "Недопустимый заголовок Host")
        if (
            self.settings.auth_enabled
            and path not in PUBLIC_PATHS
            and not self._authorized(headers)
        ):
            return _error(
                401,
                "Нужен логин и пароль",
                {"WWW-Authenticate": 'Basic realm="skelbiu-pc", charset="UTF-8"'},
            )
        if scope["method"] not in _SAFE_METHODS and not self._same_origin(headers):
            return _error(403, "Запрос отклонён: он пришёл не из нашего интерфейса")
        return None

    def _authorized(self, headers: Headers) -> bool:
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "basic" or not token:
            return False
        try:
            decoded = base64.b64decode(token.strip(), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return False
        user, sep, password = decoded.partition(":")
        if not sep:
            return False
        user_ok = secrets.compare_digest(user.encode(), self.settings.username.encode())
        pass_ok = secrets.compare_digest(
            password.encode(), (self.settings.password or "").encode()
        )
        return user_ok and pass_ok

    def _same_origin(self, headers: Headers) -> bool:
        # Свой заголовок нельзя добавить к кросс-доменному запросу без CORS-preflight,
        # а CORS мы не разрешаем — значит, чужая страница сюда не дотянется.
        if headers.get(CSRF_HEADER) != "1":
            return False
        fetch_site = headers.get("sec-fetch-site")
        if fetch_site and fetch_site not in _SAME_ORIGIN_FETCH:
            return False
        origin = headers.get("origin")
        if origin:
            try:
                name = normalize_host(urlsplit(origin).hostname)
            except ValueError:
                return False
            if name is None or name not in self.settings.allowed_hosts:
                return False
        return True


def _error(status: int, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse({"detail": message}, status_code=status, headers=headers)


def _with_security_headers(send: Send, path: str) -> Send:
    is_api = path == "/api" or path.startswith("/api/")
    extra = dict(_COMMON_HEADERS)
    extra["content-security-policy"] = _API_CSP if is_api else _UI_CSP
    if is_api:
        cache = "no-store"
    elif path.startswith("/assets/"):
        cache = "public, max-age=31536000, immutable"
    else:
        cache = "no-cache"

    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = MutableHeaders(scope=message)
            for key, value in extra.items():
                if key not in headers:
                    headers[key] = value
            if "cache-control" not in headers:
                headers["cache-control"] = cache
        await send(message)

    return wrapped
