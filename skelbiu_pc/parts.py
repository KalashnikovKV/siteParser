"""Разбор комплектующих из заголовка, описания и атрибутов объявления."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from skelbiu_pc.platforms import CHIPSET_TO_SOCKET, CPU_TIERS, GPU_TIERS, socket_for_chipset

def looks_like_laptop(title: str | None) -> bool:
    return bool(_LAPTOP_RE.search(_lower(title or "")))


def guess_desktop(title: str | None) -> int | None:
    """1 — стационар, 0 — ноутбук, None — неясно по заголовку."""
    low = _lower(title or "")
    laptop = looks_like_laptop(title)
    desktop = any(bit in low for bit in ("stacionar", "стационар", "desktop", "tower"))
    if laptop and not desktop:
        return 0
    if desktop:
        return 1
    if laptop:
        return 0
    return None


# Для SQL-отсева: те же корни, что в _LAPTOP_RE.
LAPTOP_TITLE_BITS = (
    "nesiojam",
    "nešiojam",
    "ноутбук",
    "laptop",
    "notebook",
    "macbook",
    "thinkpad",
    "latitude",
    "elitebook",
    "ideapad",
    "zenbook",
    "vivobook",
    "inspiron",
    "pavilion",
)


_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    text = text.replace("\xa0", " ").replace("ё", "е")
    return _WS.sub(" ", text).strip()


def _lower(text: str) -> str:
    return _norm(text).lower()


@dataclass
class Parts:
    motherboard: str | None = None
    chipset: str | None = None
    socket: str | None = None
    cpu: str | None = None
    cpu_tier: float | None = None
    gpu: str | None = None
    gpu_tier: float | None = None
    ram: str | None = None
    ram_type: str | None = None
    ram_gb: int | None = None
    storage: str | None = None
    psu: str | None = None
    psu_watts: int | None = None
    case: str | None = None
    cooler: str | None = None
    is_desktop: bool = True
    is_laptop: bool = False
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


_LAPTOP_RE = re.compile(
    r"\b(notebook|laptop|nesiojam|nešiojam|ноутбук|macbook|thinkpad|"
    r"latitude|elitebook|ideapad|zenbook|vivobook|inspiron|pavilion|"
    r"mac\s*mini|imac)\b",
    re.I,
)
_DESKTOP_RE = re.compile(
    r"\b(stacionar|стационар|desktop|tower|atx|matx|itx|pc\b|системник|"
    r"корпус|motinine|материнск)\b",
    re.I,
)

_CHIPSET_RE = re.compile(
    r"\b([abzxh](?:320|350|370|390|410|430|450|460|490|520|550|560|570|"
    r"610|650e?|660|670e?|690|760|770|790|810|840|850|860|870e?|890)|"
    r"990(?:fx|x)?|970)(?:m)?\b",
    re.I,
)
_BOARD_RE = re.compile(
    r"\b((?:msi|asus|asrock|gigabyte|aorus|biostar|nzxt|suprim|"
    r"tuf|prime|rog|strix|proart|mag|mpg|tomahawk|gaming plus|"
    r"steel legend|pro rs|wifi)\b[^,;\n]{0,40}?"
    r"(?:[abzxh]\d{3}e?|[abzxh]\d{2})\w*)",
    re.I,
)
_MB_LABEL_RE = re.compile(
    r"(?:motinin[eė]\s*plok[sš]t[eė]|motherboard|\bmb\b|материнск\w*\s*плат\w*)"
    r"\s*[:\-–]?\s*([^\n,]{4,80})",
    re.I,
)

_RYZEN_RE = re.compile(
    r"\b(?:amd\s+)?ryzen\s*([3579]|threadripper)?\s*"
    r"(\d{3,4}\s*[xgfc]{0,3}(?:3d)?)",
    re.I,
)
_INTEL_RE = re.compile(
    r"\b(?:intel\s+)?(?:core\s+)?"
    r"(i[3579]\s*-?\s*\d{4,5}k?|ultra\s*[579]\s*\d{3}k?)\b",
    re.I,
)
_RYZEN_SHORT_RE = re.compile(
    r"\b(?:r[3579]|amd)\s*(\d{4}\s*[xgfc]{0,3}(?:3d)?)\b",
    re.I,
)
_X3D_RE = re.compile(r"\b(\d{4}x3d)\b", re.I)
_CPU_LABEL_RE = re.compile(
    r"(?:procesor(?:ius)?|processor|\bcpu\b|процессор)\s*[:\-–]?\s*([^\n,]{4,70})",
    re.I,
)

_GPU_RE = re.compile(
    r"\b(?:geforce\s+|nvidia\s+|radeon\s+)?"
    r"(rtx\s*/?\s*\d{4}\s*(?:ti\s*super|ti|super)?|"
    r"gtx\s*\d{3,4}\s*(?:ti|super)?|"
    r"rx\s*\d{3,4}\s*(?:xt|xtx)?|"
    r"7900\s*xtx|"
    r"arc\s*(?:b|a)\d{3})\b",
    re.I,
)
_GPU_LABEL_RE = re.compile(
    r"(?:vaizdo\s*plok[sš]t[eė]|видеокарт\w*|graphics|\bgpu\b)"
    r"\s*[:\-–]?\s*([^\n,]{3,70})",
    re.I,
)

_RAM_LABEL_RE = re.compile(
    r"(?:operatyv\w*\s*atmint\w*|оператив\w*|озу|\bram\b)"
    r"\s*[:\-–]?\s*([^\n]{3,80})",
    re.I,
)
_RAM_GB_RE = re.compile(r"\b(\d{1,3})\s*gb\b", re.I)
_RAM_TYPE_RE = re.compile(r"\b(ddr[345])\b", re.I)
_RAM_KIT_RE = re.compile(r"\b(\d{1,2})\s*[x×]\s*(\d{1,2})\s*gb\b", re.I)

_PSU_W_RE = re.compile(r"\b(\d{3,4})\s*w(?:att)?\b", re.I)
_PSU_LABEL_RE = re.compile(
    r"(?:maitinimo\s*blokas|блок\s*питани\w*|\bpsu\b|бп)\s*[:\-–]?\s*([^\n,]{3,60})",
    re.I,
)

_SSD_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?\s*(?:gb|tb)\s*(?:nvme\s*)?(?:m\.2\s*)?ssd|"
    r"(?:nvme\s*)?(?:m\.2\s*)?ssd\s*\d+(?:[.,]\d+)?\s*(?:gb|tb)|"
    r"\d+(?:[.,]\d+)?\s*(?:gb|tb)\s*(?:hdd|nvme))\b",
    re.I,
)

_CASE_LABEL_RE = re.compile(
    r"(?:korpusas|корпус|case)\s*[:\-–]?\s*([^\n,]{3,50})",
    re.I,
)
_COOLER_LABEL_RE = re.compile(
    r"(?:au[sš]intuvas|кулер|cooler|aio)\s*[:\-–]?\s*([^\n,]{3,50})",
    re.I,
)


def extract_parts(title: str, description: str = "", attributes: dict | None = None) -> Parts:
    attributes = attributes or {}
    attr_blob = " ".join(f"{k}: {v}" for k, v in attributes.items())
    blob = " \n ".join(x for x in (title, description, attr_blob) if x)
    low = _lower(blob)
    parts = Parts()

    parts.is_laptop = bool(_LAPTOP_RE.search(low))
    parts.is_desktop = bool(_DESKTOP_RE.search(low)) or not parts.is_laptop
    if parts.is_laptop and not _DESKTOP_RE.search(low):
        parts.is_desktop = False
        parts.notes.append("Похоже на ноутбук: материнка почти не апгрейдится.")

    parts.chipset = _first(_CHIPSET_RE, blob, normalize=str.upper)
    if parts.chipset and parts.chipset.endswith("E") and parts.chipset[:-1] in CHIPSET_TO_SOCKET:
        pass
    board = _first(_MB_LABEL_RE, blob) or _first(_BOARD_RE, blob)
    if board:
        parts.motherboard = _clip(board)
        if not parts.chipset:
            parts.chipset = _first(_CHIPSET_RE, board, normalize=str.upper)

    cpu = _match_cpu(blob)
    if not cpu:
        labeled = _first(_CPU_LABEL_RE, blob)
        if labeled and _match_cpu(labeled):
            cpu = labeled
    if cpu:
        parts.cpu = _clip(_clean_cpu(cpu))
        parts.cpu_tier, cpu_socket = _tier_cpu(parts.cpu)
        if cpu_socket:
            parts.socket = cpu_socket

    if not parts.socket:
        parts.socket = socket_for_chipset(parts.chipset)

    gpu = _first(_GPU_RE, blob) or _first(_GPU_LABEL_RE, blob)
    if gpu and _fake_gpu(blob, gpu):
        gpu = None
    if gpu:
        parts.gpu = _clip(gpu)
        parts.gpu_tier = _tier_gpu(parts.gpu)
        if re.search(r"\b(uhd|iris|vega\s*\d|integrated|integruot|встроен)\b", _lower(parts.gpu)):
            parts.gpu_tier = 0.4

    _fill_ram(parts, blob)
    storage = _first(_SSD_RE, blob)
    if storage:
        parts.storage = _clip(storage)

    psu = _first(_PSU_LABEL_RE, blob)
    watts = _first(_PSU_W_RE, psu or blob)
    if psu:
        parts.psu = _clip(psu)
    if watts:
        parts.psu_watts = int(watts)
        if not parts.psu:
            parts.psu = f"{parts.psu_watts}W"

    case = _first(_CASE_LABEL_RE, blob)
    if case:
        parts.case = _clip(case)
    cooler = _first(_COOLER_LABEL_RE, blob)
    if cooler:
        parts.cooler = _clip(cooler)

    parts.confidence = _confidence(parts)
    if not parts.socket and not parts.cpu and not parts.motherboard:
        parts.notes.append("Мало данных: сокет и плата не распознаны.")
    return parts


def _first(regex: re.Pattern, text: str, normalize=None) -> str | None:
    m = regex.search(text)
    if not m:
        return None
    value = m.group(1) if m.lastindex else m.group(0)
    value = _norm(value)
    return normalize(value) if normalize else value


def _fake_gpu(blob: str, gpu: str) -> bool:
    """Подпись «видеокарта» часто захватывает следующий абзац или «без GPU»."""
    if _GPU_RE.search(gpu):
        return False
    low = _lower(gpu)
    if re.search(r"(без|нет|nėra|nera|no|be)\s+(видеокарт|vaizdo|gpu|graphics)", _lower(blob)):
        return True
    if len(gpu) > 36 or re.search(r"ryzen|procesor|motinin|motherboard|\bcpu\b", low):
        return True
    return False


def _match_cpu(text: str) -> str | None:
    m = _INTEL_RE.search(text)
    if m:
        return _norm(m.group(1).replace(" ", ""))
    m = _RYZEN_RE.search(text)
    if m:
        series = m.group(1) or ""
        model = m.group(2)
        return _norm(f"Ryzen {series} {model}")
    m = _RYZEN_SHORT_RE.search(text)
    if m:
        return _norm(f"Ryzen {m.group(1)}")
    m = _X3D_RE.search(text)
    if m:
        return _norm(f"Ryzen {m.group(1)}")
    return None


def _clean_cpu(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\b(tray|box|oem|naujas|новый)\b", "", value, flags=re.I)
    return value.strip(" :-")


def _clip(value: str, limit: int = 80) -> str:
    value = _norm(value)
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _fill_ram(parts: Parts, blob: str) -> None:
    labeled = _first(_RAM_LABEL_RE, blob)
    kit = _RAM_KIT_RE.search(labeled or blob)
    if kit:
        parts.ram_gb = int(kit.group(1)) * int(kit.group(2))
        parts.ram = _clip(kit.group(0))
    else:
        # Берём наибольший реалистичный объём, игнорируя кэш CPU и SSD.
        candidates = []
        for m in _RAM_GB_RE.finditer(labeled or ""):
            candidates.append(int(m.group(1)))
        if not candidates:
            # Если подпись обрезалась, ищем объём во всём тексте рядом с RAM/DDR.
            window = blob
            for m in re.finditer(r"(?:ram|ddr[345]|озу|atmint).{0,40}(\d{1,3})\s*gb", window, re.I):
                candidates.append(int(m.group(1)))
            if not candidates:
                for m in re.finditer(r"(\d{1,3})\s*gb.{0,16}(?:ram|ddr[345])", window, re.I):
                    candidates.append(int(m.group(1)))
        gb = [x for x in candidates if x in {4, 8, 12, 16, 24, 32, 48, 64, 96, 128}]
        if gb:
            parts.ram_gb = max(gb)
            parts.ram = f"{parts.ram_gb} GB"
        elif labeled:
            parts.ram = _clip(labeled)

    ram_type = _first(_RAM_TYPE_RE, labeled or blob, normalize=str.upper)
    if ram_type:
        parts.ram_type = ram_type
    elif parts.socket == "AM5":
        parts.ram_type = "DDR5"
    elif parts.socket in {"AM4", "LGA1200", "LGA1151"}:
        parts.ram_type = "DDR4"


def _tier_cpu(name: str) -> tuple[float | None, str | None]:
    text = _lower(name)
    compact = text.replace(" ", "").replace("-", "")
    looks_intel = bool(re.search(r"i[3579]\d{4}|coreultra", compact))
    looks_amd = "ryzen" in compact or bool(re.search(r"^r[3579]\d{4}", compact))
    best: tuple[int, float, str] | None = None
    for pattern, tier, socket in CPU_TIERS:
        if looks_intel and socket.startswith(("AM", "sTR")):
            continue
        if looks_amd and socket.startswith("LGA"):
            continue
        variants = (
            (compact, pattern.replace(r"\s*", "").replace(" ", "")),
            (text, pattern),
        )
        for haystack, pat in variants:
            match = re.search(pat, haystack)
            if not match:
                continue
            length = len(match.group(0))
            if best is None or length > best[0]:
                best = (length, tier, socket)
    if best:
        return best[1], best[2]
    return None, None


def _tier_gpu(name: str) -> float | None:
    text = _lower(name).replace("/", " ")
    best: tuple[int, float] | None = None
    for pattern, tier in GPU_TIERS:
        match = re.search(pattern, text)
        if not match:
            continue
        length = len(match.group(0))
        if best is None or length > best[0]:
            best = (length, tier)
    return best[1] if best else None


def _confidence(parts: Parts) -> float:
    score = 0.0
    if parts.cpu:
        score += 0.28
    if parts.socket:
        score += 0.22
    if parts.motherboard or parts.chipset:
        score += 0.18
    if parts.gpu:
        score += 0.12
    if parts.ram_gb:
        score += 0.10
    if parts.psu_watts:
        score += 0.05
    if parts.storage:
        score += 0.05
    return round(min(score, 1.0), 2)
