from __future__ import annotations

import html
import re
from datetime import date, datetime


def parse_iso_date(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def today_iso() -> str:
    return date.today().isoformat()


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = clean_text(value)
    if not text or text in {"-", "--", "해당없음"}:
        return None
    text = text.replace(",", "")
    text = text.replace("주", "")
    text = text.replace("원", "")
    text = text.strip()
    scale = 1.0
    if text.endswith("%"):
        scale = 0.01
        text = text[:-1]
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text) * scale
    except ValueError:
        return None


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_-]+", "_", value.strip())
    return slug.strip("_") or "snapshot"
