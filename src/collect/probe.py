from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from src.collect.dart_client import DEFAULT_REPORT_KEYWORDS, DartClient, LIST_ENDPOINT
from src.models import ReportSection


VIEWER_PATTERN = re.compile(
    r'viewDoc\("(?P<rcpNo>\d+)",\s*"(?P<dcmNo>\d+)",\s*"(?P<eleId>\d+)",\s*"(?P<offset>\d+)",\s*"(?P<length>\d+)",\s*"(?P<dtd>[^"]+)"'
)
RAW_DART_DIR = Path("data/raw/dart")


@dataclass(slots=True)
class ProbeMatch:
    receipt_no: str
    corp_name: str
    report_name: str
    filer_name: str
    page_keyword_hit: bool
    viewer_keyword_hit: bool
    viewer_excerpt: str | None
    viewer_url: str | None


@dataclass(slots=True)
class ReportInspection:
    page_keyword_hit: bool
    viewer_keyword_hit: bool
    viewer_excerpt: str | None
    viewer_url: str | None


def probe_filings_by_date(
    client: DartClient,
    date_value: str,
    keyword: str,
    report_keywords: list[str] | None = None,
) -> dict[str, Any]:
    report_keywords = report_keywords or DEFAULT_REPORT_KEYWORDS
    raw_items = _list_daily_filings(client, date_value)
    candidates = []
    for item in raw_items:
        report_name = item.get("report_nm", "")
        if not any(token in report_name for token in report_keywords):
            continue
        candidates.append(item)

    matches: list[ProbeMatch] = []
    errors: list[dict[str, str]] = []
    for item in candidates:
        report_name = item.get("report_nm", "")
        try:
            inspection = inspect_report_for_keyword(client, item["rcept_no"], keyword)
            if inspection.page_keyword_hit or inspection.viewer_keyword_hit:
                matches.append(
                    ProbeMatch(
                        receipt_no=item["rcept_no"],
                        corp_name=item.get("corp_name", ""),
                        report_name=report_name,
                        filer_name=item.get("flr_nm", ""),
                        page_keyword_hit=inspection.page_keyword_hit,
                        viewer_keyword_hit=inspection.viewer_keyword_hit,
                        viewer_excerpt=inspection.viewer_excerpt,
                        viewer_url=inspection.viewer_url,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "receipt_no": item["rcept_no"],
                    "corp_name": item.get("corp_name", ""),
                    "report_name": report_name,
                    "error": str(exc),
                }
            )

    return {
        "date": date_value,
        "keyword": keyword,
        "candidate_count": len(candidates),
        "match_count": len(matches),
        "error_count": len(errors),
        "matches": [asdict(match) for match in matches],
        "errors": errors,
    }


def inspect_report_for_keyword(
    client: DartClient,
    receipt_no: str,
    keyword: str,
    scan_all_sections: bool = True,
) -> ReportInspection:
    main_url = _main_url(receipt_no)
    main_html = _fetch_text_with_cache(client, main_url, receipt_no, "main.html")
    page_hit = keyword in main_html
    viewer_url = None
    viewer_hit = False
    viewer_excerpt = None
    descriptors = _extract_viewer_descriptors(main_html)
    if not scan_all_sections:
        descriptors = descriptors[:1]
    for descriptor in descriptors:
        viewer_url = _viewer_url(descriptor)
        viewer_html = _fetch_text_with_cache(client, viewer_url, receipt_no, _viewer_cache_name(descriptor))
        if keyword in viewer_html:
            viewer_hit = True
            viewer_excerpt = _extract_excerpt(viewer_html, keyword)
            break
    return ReportInspection(
        page_keyword_hit=page_hit,
        viewer_keyword_hit=viewer_hit,
        viewer_excerpt=viewer_excerpt,
        viewer_url=viewer_url,
    )


def fetch_viewer_sections(client: DartClient, receipt_no: str) -> list[ReportSection]:
    main_html = _fetch_text_with_cache(client, _main_url(receipt_no), receipt_no, "main.html")
    sections: list[ReportSection] = []
    for descriptor in _extract_viewer_descriptors(main_html):
        viewer_url = _viewer_url(descriptor)
        viewer_html = _fetch_text_with_cache(client, viewer_url, receipt_no, _viewer_cache_name(descriptor))
        sections.append(
            ReportSection(
                title=descriptor.get("text", ""),
                url=viewer_url,
                html=viewer_html,
            )
        )
    return sections


def _list_daily_filings(client: DartClient, date_value: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_no = 1
    while True:
        payload = client.get_json(
            LIST_ENDPOINT,
            {
                "crtfc_key": client.api_key,
                "bgn_de": date_value.replace("-", ""),
                "end_de": date_value.replace("-", ""),
                "page_no": page_no,
                "page_count": 100,
            },
        )
        if payload.get("status") != "000":
            raise RuntimeError(f"DART list.json failed: {payload.get('status')} {payload.get('message')}")
        items.extend(payload.get("list", []))
        total_pages = int(payload.get("total_page", 1) or 1)
        if page_no >= total_pages:
            break
        page_no += 1
    return items


def _main_url(receipt_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"


def _extract_viewer_descriptors(main_html: str) -> list[dict[str, str]]:
    descriptors: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for block in re.findall(r"var node1 = \{\};(.*?)treeData\.push\(node1\);", main_html, flags=re.DOTALL):
        values = dict(re.findall(r"node1\['(?P<key>[^']+)'\]\s*=\s*\"(?P<value>[^\"]*)\"", block))
        if not {"rcpNo", "dcmNo", "eleId", "offset", "length", "dtd"} <= set(values):
            continue
        key = (values["rcpNo"], values["dcmNo"], values["eleId"], values["offset"], values["length"], values["dtd"])
        if key in seen:
            continue
        seen.add(key)
        descriptors.append(values)
    if descriptors:
        return descriptors

    for match in VIEWER_PATTERN.finditer(main_html):
        values = match.groupdict()
        key = (values["rcpNo"], values["dcmNo"], values["eleId"], values["offset"], values["length"], values["dtd"])
        if key in seen:
            continue
        seen.add(key)
        descriptors.append(values)
    return descriptors


def _viewer_url(values: dict[str, str]) -> str:
    return (
        "https://dart.fss.or.kr/report/viewer.do?"
        + urlencode(
            {
                "rcpNo": values["rcpNo"],
                "dcmNo": values["dcmNo"],
                "eleId": values["eleId"],
                "offset": values["offset"],
                "length": values["length"],
                "dtd": values["dtd"],
            }
        )
    )


def _viewer_cache_name(values: dict[str, str]) -> str:
    ele_id = re.sub(r"[^0-9A-Za-z_-]+", "_", values.get("eleId", "unknown"))
    return f"viewer_{ele_id}.html"


def _fetch_text_with_cache(client: DartClient, url: str, receipt_no: str, filename: str) -> str:
    cache_path = RAW_DART_DIR / receipt_no / filename
    try:
        text = client.fetch_text(url)
    except Exception:
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")
        raise
    if isinstance(client, DartClient):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
    return text


def _extract_excerpt(text: str, keyword: str, radius: int = 120) -> str:
    index = text.find(keyword)
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(text), index + len(keyword) + radius)
    return text[start:end]
