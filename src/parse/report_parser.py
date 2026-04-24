from __future__ import annotations

import re
from html import unescape
from io import BytesIO
from typing import Sequence
from zipfile import ZipFile

from src.models import HoldingEvent, ReportRecord, ReportSection
from src.utils import clean_text, parse_iso_date, parse_number


HEADER_ALIASES = {
    "ticker": ("종목코드", "증권코드", "주식코드", "종목 코드"),
    "company_name": ("종목명", "회사명", "발행회사", "법인명"),
    "effective_date": ("변동일", "변동 일자", "보고사유발생일", "변경일"),
    "delta_shares": ("직전 보고서 대비 증감 수량", "증감수량", "변동주식수", "증감 주식수"),
    "shares_after": ("보유주식등의 수", "보유주식수", "보유 수량", "변동 후 보유주식수"),
    "ownership_after": ("보유비율", "지분율", "보유 비율"),
    "change_reason": ("변동 사유", "변동사유", "보유목적", "주요변동사유"),
}


SPECIFIC_SECURITY_REPORT_KEYWORDS = ("임원ㆍ주요주주", "특정증권")


def is_specific_security_report(report: ReportRecord) -> bool:
    return any(keyword in report.report_name for keyword in SPECIFIC_SECURITY_REPORT_KEYWORDS)


def _iter_document_texts(document_bytes: bytes) -> list[str]:
    if document_bytes.startswith(b"PK"):
        texts: list[str] = []
        with ZipFile(BytesIO(document_bytes)) as archive:
            for name in archive.namelist():
                if name.lower().endswith((".xml", ".htm", ".html", ".txt")):
                    texts.append(archive.read(name).decode("utf-8", errors="ignore"))
        return texts
    return [document_bytes.decode("utf-8", errors="ignore")]


def _strip_cell(cell: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", cell, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.IGNORECASE | re.DOTALL)
        cleaned = [_strip_cell(cell) for cell in cells]
        if any(cleaned):
            rows.append(cleaned)
    return rows


def _normalize_header(row: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, header in enumerate(row):
        normalized = clean_text(header)
        for field, aliases in HEADER_ALIASES.items():
            if any(alias in normalized for alias in aliases):
                mapping[field] = index
    return mapping


def _find_relevant_table(rows: list[list[str]]) -> tuple[dict[str, int], list[list[str]]] | None:
    for index, row in enumerate(rows):
        header_map = _normalize_header(row)
        if {"company_name", "ownership_after"} <= set(header_map):
            data_rows = rows[index + 1 :]
            return header_map, data_rows
    return None


def _extract_dates_from_text(text: str) -> list[str]:
    found = re.findall(r"(20\d{2}[./-]\d{2}[./-]\d{2}|20\d{6})", text)
    dates: list[str] = []
    for value in found:
        try:
            dates.append(parse_iso_date(value))
        except ValueError:
            continue
    return dates


def parse_report_viewer_sections(sections: Sequence[ReportSection], report: ReportRecord) -> list[HoldingEvent]:
    if not is_specific_security_report(report):
        merged_html = "\n".join(section.html for section in sections)
        return parse_report_document(merged_html.encode("utf-8"), report)
    return _parse_specific_security_report_sections(sections, report)


def parse_report_document(document_bytes: bytes, report: ReportRecord) -> list[HoldingEvent]:
    candidate_texts = _iter_document_texts(document_bytes)
    for text in candidate_texts:
        rows = _table_rows(text)
        match = _find_relevant_table(rows)
        if not match:
            continue
        header_map, body_rows = match
        fallback_dates = _extract_dates_from_text(text)
        events: list[HoldingEvent] = []
        for row in body_rows:
            if len(row) < len(header_map):
                continue
            company_name = row[header_map["company_name"]].strip() if "company_name" in header_map else ""
            if not company_name or company_name in {"합계", "총계"}:
                continue
            ticker = row[header_map["ticker"]].strip() if "ticker" in header_map else None
            effective_date = None
            if "effective_date" in header_map:
                raw_date = row[header_map["effective_date"]]
                try:
                    effective_date = parse_iso_date(raw_date)
                except ValueError:
                    effective_date = None
            if effective_date is None and fallback_dates:
                effective_date = fallback_dates[0]
            delta_shares = parse_number(row[header_map["delta_shares"]]) if "delta_shares" in header_map else None
            shares_after = parse_number(row[header_map["shares_after"]]) if "shares_after" in header_map else None
            ownership_after = parse_number(row[header_map["ownership_after"]]) if "ownership_after" in header_map else None
            change_reason = row[header_map["change_reason"]] if "change_reason" in header_map else None
            events.append(
                HoldingEvent(
                    report_receipt_no=report.receipt_no,
                    ticker=ticker or None,
                    company_name=company_name,
                    effective_date=effective_date,
                    disclosed_at=report.disclosed_at,
                    delta_shares=delta_shares,
                    shares_after=shares_after,
                    ownership_after=ownership_after,
                    change_reason=change_reason,
                    event_type=_infer_event_type(delta_shares, change_reason),
                )
            )
        if events:
            return events
    raise ValueError("Could not locate a holdings table in the report document.")


def _parse_specific_security_report_sections(sections: Sequence[ReportSection], report: ReportRecord) -> list[HoldingEvent]:
    company_name = report.corp_name
    ticker = report.stock_code
    effective_date = None
    shares_after = None
    ownership_after = None
    delta_shares = None
    delta_ownership = None
    inspected_sections: list[str] = []

    for section in sections:
        section_title = clean_text(section.title)
        if section_title:
            inspected_sections.append(section_title)
        rows = _table_rows(section.html)
        for row in rows:
            normalized = [clean_text(cell) for cell in row]
            compacted = [_compact_text(cell) for cell in normalized]
            if "회사명" in compacted:
                company_name = _cell_after(normalized, "회사명") or company_name
            if "회사코드" in compacted:
                ticker = _cell_after(normalized, "회사코드") or ticker

        summary = _find_specific_security_summary(rows)
        if summary:
            effective_date = summary["effective_date"]
            shares_after = summary["shares_after"]
            ownership_after = summary["ownership_after"]
            delta_shares = summary["delta_shares"]
            delta_ownership = summary["delta_ownership"]

    missing = []
    if not company_name:
        missing.append("company_name")
    if not ticker:
        missing.append("ticker")
    if effective_date is None:
        missing.append("effective_date")
    if shares_after is None:
        missing.append("shares_after")
    if ownership_after is None:
        missing.append("ownership_after")
    if delta_shares is None:
        missing.append("delta_shares")
    if missing:
        where = ", ".join(inspected_sections) or "no viewer sections"
        raise ValueError(f"Could not parse specific-security report fields: {', '.join(missing)}; sections={where}")

    change_reason = "임원ㆍ주요주주 특정증권등 소유상황보고서"
    if delta_ownership is not None:
        change_reason += f" / 지분율 증감 {delta_ownership:.4%}"
    return [
        HoldingEvent(
            report_receipt_no=report.receipt_no,
            ticker=ticker,
            company_name=company_name,
            effective_date=effective_date,
            disclosed_at=report.disclosed_at,
            delta_shares=delta_shares,
            shares_after=shares_after,
            ownership_after=ownership_after,
            change_reason=change_reason,
            event_type=_infer_event_type(delta_shares, change_reason),
        )
    ]


def _find_specific_security_summary(rows: list[list[str]]) -> dict[str, float | str | None] | None:
    current_row = None
    delta_row = None
    for row in rows:
        if not row:
            continue
        label = _compact_text(row[0])
        if label == "이번보고서":
            current_row = row
        elif label == "증감":
            delta_row = row
    if current_row is None or delta_row is None:
        return None
    if len(current_row) < 6:
        raise ValueError("specific-security summary row has fewer columns than expected")
    if len(delta_row) < 5:
        raise ValueError("specific-security delta row has fewer columns than expected")
    return {
        "effective_date": _parse_report_date(current_row[1]),
        "shares_after": parse_number(current_row[4]),
        "ownership_after": _parse_percent_column(current_row[5]),
        "delta_shares": parse_number(delta_row[3]),
        "delta_ownership": _parse_percent_column(delta_row[4]),
    }


def _cell_after(row: list[str], label: str) -> str | None:
    index = None
    for position, cell in enumerate(row):
        if _compact_text(cell) == label:
            index = position
            break
    if index is None:
        return None
    if index + 1 >= len(row):
        return None
    value = row[index + 1].strip()
    return value or None


def _compact_text(value: str) -> str:
    return re.sub(r"[\s\xa0]+", "", clean_text(value))


def _parse_report_date(value: str) -> str:
    text = clean_text(value)
    match = re.search(r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if match:
        year, month, day = match.groups()
        return parse_iso_date(f"{year}-{int(month):02d}-{int(day):02d}")
    match = re.search(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}|20\d{6})", text)
    if match:
        return parse_iso_date(match.group(1))
    raise ValueError(f"Unsupported report date format: {value}")


def _parse_percent_column(value: str) -> float | None:
    number = parse_number(value)
    if number is None:
        return None
    if "%" in clean_text(value):
        return number
    return number / 100.0


def _infer_event_type(delta_shares: float | None, change_reason: str | None) -> str | None:
    reason = clean_text(change_reason)
    if "매수" in reason:
        return "buy"
    if "매도" in reason:
        return "sell"
    if delta_shares is None:
        return None
    if delta_shares > 0:
        return "buy"
    if delta_shares < 0:
        return "sell"
    return "flat"
