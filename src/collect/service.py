from __future__ import annotations

from src.collect.dart_client import DEFAULT_REPORT_KEYWORDS, DartClient
from src.collect.probe import fetch_viewer_sections, inspect_report_for_keyword
from src.db.repository import Repository
from src.parse.report_parser import is_specific_security_report, parse_report_document, parse_report_viewer_sections


def sync_reports(repository: Repository, client: DartClient, start_date: str, end_date: str) -> dict[str, int]:
    reports = client.list_reports_by_keywords(
        start_date,
        end_date,
        DEFAULT_REPORT_KEYWORDS,
    )
    keyword_matched = 0
    parsed_count = 0
    failed_count = 0
    skipped_count = 0
    for report in reports:
        try:
            sections = None
            if is_specific_security_report(report):
                sections = fetch_viewer_sections(client, report.receipt_no)
                if not any("국민연금공단" in section.html for section in sections):
                    skipped_count += 1
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
        except Exception as exc:  # noqa: BLE001
            report.parse_status = "failed"
            report.parse_error = str(exc)
            repository.upsert_report(report)
            failed_count += 1
    return {
        "candidates": len(reports),
        "keyword_matched": keyword_matched,
        "parsed": parsed_count,
        "failed": failed_count,
        "skipped": skipped_count,
    }
