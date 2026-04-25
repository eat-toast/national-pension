from __future__ import annotations

from src.collect.dart_client import DEFAULT_REPORT_DETAIL_TYPES, DartClient
from src.collect.probe import fetch_viewer_sections, inspect_report_for_keyword
from src.db.repository import Repository
from src.models import HoldingEvent, ReportRecord
from src.parse.report_parser import is_specific_security_report, parse_report_document, parse_report_viewer_sections
from src.utils import clean_text, parse_number


def sync_reports(repository: Repository, client: DartClient, start_date: str, end_date: str) -> dict[str, int]:
    print(f"[sync-reports] listing reports {start_date}..{end_date}", flush=True)
    reports = client.list_reports_by_detail_types(
        start_date,
        end_date,
        DEFAULT_REPORT_DETAIL_TYPES,
    )
    print(f"[sync-reports] candidates: {len(reports)}", flush=True)
    keyword_matched = 0
    parsed_count = 0
    failed_count = 0
    skipped_count = 0
    majorstock_cache: dict[str, list[dict[str, str]]] = {}
    elestock_cache: dict[str, list[dict[str, str]]] = {}
    for index, report in enumerate(reports, start=1):
        label = f"{report.disclosed_at} {report.corp_name} {report.report_name} ({report.receipt_no})"
        print(f"[{index}/{len(reports)}] checking {label}", flush=True)
        try:
            official_events = _parse_official_ownership_events(client, report, majorstock_cache, elestock_cache)
            if official_events is not None:
                if not official_events:
                    skipped_count += 1
                    print(f"[{index}/{len(reports)}] skipped {label}: no 국민연금공단 ownership row", flush=True)
                    continue
                keyword_matched += 1
                repository.upsert_report(report)
                report.parse_status = "parsed"
                report.parse_error = None
                repository.upsert_report(report)
                repository.replace_events_for_report(report.receipt_no, official_events)
                parsed_count += 1
                print(f"[{index}/{len(reports)}] parsed {label}: {len(official_events)} event(s)", flush=True)
                continue

            sections = None
            if is_specific_security_report(report):
                sections = fetch_viewer_sections(client, report.receipt_no)
                if not any("국민연금공단" in section.html for section in sections):
                    skipped_count += 1
                    print(f"[{index}/{len(reports)}] skipped {label}: keyword not found in viewer", flush=True)
                    continue
            else:
                inspection = inspect_report_for_keyword(
                    client,
                    report.receipt_no,
                    "국민연금공단",
                    scan_all_sections=False,
                )
                if not (inspection.page_keyword_hit or inspection.viewer_keyword_hit):
                    skipped_count += 1
                    print(f"[{index}/{len(reports)}] skipped {label}: keyword not found", flush=True)
                    continue
            keyword_matched += 1
            repository.upsert_report(report)
            if is_specific_security_report(report):
                events = parse_report_viewer_sections(sections or [], report)
            else:
                document_bytes = client.download_document(report.receipt_no)
                events = parse_report_document(document_bytes, report)
            report.parse_status = "parsed"
            report.parse_error = None
            repository.upsert_report(report)
            repository.replace_events_for_report(report.receipt_no, events)
            parsed_count += 1
            print(f"[{index}/{len(reports)}] parsed {label}: {len(events)} event(s)", flush=True)
        except Exception as exc:  # noqa: BLE001
            report.parse_status = "failed"
            report.parse_error = str(exc)
            repository.upsert_report(report)
            failed_count += 1
            print(f"[{index}/{len(reports)}] failed {label}: {exc}", flush=True)
    return {
        "candidates": len(reports),
        "keyword_matched": keyword_matched,
        "parsed": parsed_count,
        "failed": failed_count,
        "skipped": skipped_count,
    }


def _parse_official_ownership_events(
    client: DartClient,
    report: ReportRecord,
    majorstock_cache: dict[str, list[dict[str, str]]],
    elestock_cache: dict[str, list[dict[str, str]]],
) -> list[HoldingEvent] | None:
    if not report.corp_code:
        return None
    if _is_majorstock_report(report):
        if report.corp_code not in majorstock_cache:
            majorstock_cache[report.corp_code] = client.majorstock_reports(report.corp_code)
        rows = majorstock_cache[report.corp_code]
        return [_majorstock_event(report, row) for row in rows if _is_target_row(report, row)]
    if is_specific_security_report(report):
        if report.corp_code not in elestock_cache:
            elestock_cache[report.corp_code] = client.elestock_reports(report.corp_code)
        rows = elestock_cache[report.corp_code]
        return [_elestock_event(report, row) for row in rows if _is_target_row(report, row)]
    return None


def _is_majorstock_report(report: ReportRecord) -> bool:
    return "주식등의대량보유상황보고서" in report.report_name


def _is_target_row(report: ReportRecord, row: dict[str, str]) -> bool:
    return row.get("rcept_no") == report.receipt_no and "국민연금공단" in clean_text(row.get("repror"))


def _majorstock_event(report: ReportRecord, row: dict[str, str]) -> HoldingEvent:
    delta_shares = parse_number(row.get("stkqy_irds"))
    change_reason = row.get("report_resn")
    return HoldingEvent(
        report_receipt_no=report.receipt_no,
        ticker=report.stock_code,
        company_name=row.get("corp_name") or report.corp_name,
        effective_date=None,
        disclosed_at=report.disclosed_at,
        delta_shares=delta_shares,
        shares_after=parse_number(row.get("stkqy")),
        ownership_after=_parse_rate(row.get("stkrt")),
        change_reason=change_reason,
        event_type=_infer_event_type(delta_shares, change_reason),
    )


def _elestock_event(report: ReportRecord, row: dict[str, str]) -> HoldingEvent:
    delta_shares = parse_number(row.get("sp_stock_lmp_irds_cnt"))
    change_reason = "임원ㆍ주요주주 소유보고"
    return HoldingEvent(
        report_receipt_no=report.receipt_no,
        ticker=report.stock_code,
        company_name=row.get("corp_name") or report.corp_name,
        effective_date=None,
        disclosed_at=report.disclosed_at,
        delta_shares=delta_shares,
        shares_after=parse_number(row.get("sp_stock_lmp_cnt")),
        ownership_after=_parse_rate(row.get("sp_stock_lmp_rate")),
        change_reason=change_reason,
        event_type=_infer_event_type(delta_shares, change_reason),
    )


def _parse_rate(value: str | None) -> float | None:
    number = parse_number(value)
    if number is None:
        return None
    if "%" in clean_text(value):
        return number
    return number / 100.0


def _infer_event_type(delta_shares: float | None, change_reason: str | None) -> str | None:
    reason = clean_text(change_reason)
    if "매수" in reason or "취득" in reason:
        return "buy"
    if "매도" in reason or "처분" in reason:
        return "sell"
    if delta_shares is None:
        return None
    if delta_shares > 0:
        return "buy"
    if delta_shares < 0:
        return "sell"
    return "flat"
