from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.alerts.kakao import send_kakao_alerts, send_kakao_text_message
from src.alerts.service import build_alerts
from src.analysis.sector_trends import build_sector_trends
from src.collect.dart_client import DartClient
from src.collect.probe import probe_filings_by_date
from src.collect.sector_service import sync_sector_map
from src.collect.service import sync_reports
from src.config import AppConfig
from src.dashboard.baseline import baseline_year_from_path, load_baseline_holdings
from src.dashboard.service import build_dashboard_data, export_dashboard, render_dashboard_html
from src.db.repository import Repository
from src.export.combined_html_writer import export_combined_html
from src.export.sector_trends_writer import export_sector_trends_csv, export_sector_trends_report
from src.export.sector_trends_writer import render_sector_trends_html
from src.export.xlsx_writer import export_snapshot_workbook
from src.snapshot.service import build_snapshot, calculate_snapshot_rows
from src.utils import parse_iso_date, safe_slug


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="국민연금 포트폴리오 추적기")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync-reports", help="DART 공시를 수집합니다.")
    sync_parser.add_argument("--from", dest="start_date", required=True)
    sync_parser.add_argument("--to", dest="end_date", required=True)

    probe_parser = subparsers.add_parser("probe-filings", help="특정 날짜의 후보 공시 본문에서 키워드를 찾습니다.")
    probe_parser.add_argument("--date", required=True)
    probe_parser.add_argument("--keyword", default="국민연금")
    probe_parser.add_argument(
        "--report-keyword",
        action="append",
        dest="report_keywords",
        help="후보 공시를 좁히는 보고서명 키워드. 여러 번 지정 가능",
    )

    snapshot_parser = subparsers.add_parser("build-snapshot", help="DB에서 스냅샷을 계산합니다.")
    snapshot_parser.add_argument("--date", required=True)
    snapshot_parser.add_argument("--basis", choices=("effective_date", "disclosure_date"), required=True)

    export_parser = subparsers.add_parser("export-xlsx", help="스냅샷을 엑셀로 출력합니다.")
    export_parser.add_argument("--date", required=True)
    export_parser.add_argument("--basis", choices=("effective_date", "disclosure_date"), required=True)
    export_parser.add_argument("--output")

    dashboard_parser = subparsers.add_parser("export-dashboard", help="2024 기준선과 변동 이벤트로 HTML 대시보드를 출력합니다.")
    dashboard_parser.add_argument("--date", required=True)
    dashboard_parser.add_argument("--basis", choices=("effective_date", "disclosure_date"), default="disclosure_date")
    dashboard_parser.add_argument("--baseline", default="국내주식 종목별 투자 현황(2024년 말).xlsx")
    dashboard_parser.add_argument("--output")

    sector_trends_parser = subparsers.add_parser("export-sector-trends", help="월별/분기별 섹터 변화 HTML과 CSV를 출력합니다.")
    sector_trends_parser.add_argument("--from", dest="start_date", required=True)
    sector_trends_parser.add_argument("--to", dest="end_date", required=True)
    sector_trends_parser.add_argument("--basis", choices=("effective_date", "disclosure_date"), default="disclosure_date")
    sector_trends_parser.add_argument("--baseline", default="국내주식 종목별 투자 현황(2024년 말).xlsx")
    sector_trends_parser.add_argument("--output")
    sector_trends_parser.add_argument("--csv-output")

    combined_parser = subparsers.add_parser("export-combined-dashboard", help="포트폴리오와 섹터 변화 탭을 한 HTML로 출력합니다.")
    combined_parser.add_argument("--date", required=True, help="포트폴리오 대시보드 기준일")
    combined_parser.add_argument("--from", dest="start_date", required=True, help="섹터 변화 시작일")
    combined_parser.add_argument("--to", dest="end_date", required=True, help="섹터 변화 종료일")
    combined_parser.add_argument("--basis", choices=("effective_date", "disclosure_date"), default="disclosure_date")
    combined_parser.add_argument("--baseline", default="국내주식 종목별 투자 현황(2024년 말).xlsx")
    combined_parser.add_argument("--output")
    combined_parser.add_argument("--csv-output")

    alerts_parser = subparsers.add_parser("send-alerts", help="카카오톡 나에게 보내기 알림을 보냅니다.")
    alerts_parser.add_argument("--since", required=True)
    alerts_parser.add_argument("--dry-run", action="store_true")

    kakao_test_parser = subparsers.add_parser("test-kakao", help="카카오톡 나에게 보내기 테스트 메시지를 보냅니다.")
    kakao_test_parser.add_argument("--text")
    kakao_test_parser.add_argument("--dry-run", action="store_true")

    sector_parser = subparsers.add_parser("rebuild-sector-summary", help="섹터 요약 스냅샷을 다시 계산합니다.")
    sector_parser.add_argument("--date", required=True)
    sector_parser.add_argument("--basis", choices=("effective_date", "disclosure_date"), required=True)

    sync_sector_parser = subparsers.add_parser("sync-sector-map", help="회사개황 업종코드로 섹터 매핑을 갱신합니다.")
    sync_sector_parser.add_argument("--limit", type=int, help="처리할 종목 수를 제한합니다.")
    sync_sector_parser.add_argument(
        "--include-existing",
        action="store_true",
        help="이미 섹터가 저장된 종목도 다시 갱신합니다.",
    )
    sync_sector_parser.add_argument("--progress", action="store_true", help="종목별 처리 결과를 출력합니다.")
    sync_sector_parser.set_defaults(command="sync-sector-map")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.from_env()
    repository = Repository(config.db_path)
    try:
        if args.command == "sync-reports":
            if not config.dart_api_key:
                raise RuntimeError("DART_API_KEY is required for sync-reports.")
            client = DartClient(
                config.dart_api_key,
                ssl_cert_file=config.ssl_cert_file,
                retries=config.dart_retries,
                retry_delay_seconds=config.dart_retry_delay_seconds,
                timeout_seconds=config.dart_timeout_seconds,
                request_delay_seconds=config.dart_request_delay_seconds,
            )
            result = sync_reports(
                repository,
                client,
                parse_iso_date(args.start_date),
                parse_iso_date(args.end_date),
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "probe-filings":
            if not config.dart_api_key:
                raise RuntimeError("DART_API_KEY is required for probe-filings.")
            client = DartClient(
                config.dart_api_key,
                ssl_cert_file=config.ssl_cert_file,
                retries=config.dart_retries,
                retry_delay_seconds=config.dart_retry_delay_seconds,
                timeout_seconds=config.dart_timeout_seconds,
                request_delay_seconds=config.dart_request_delay_seconds,
            )
            result = probe_filings_by_date(
                client,
                parse_iso_date(args.date),
                args.keyword,
                args.report_keywords,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command in {"build-snapshot", "rebuild-sector-summary"}:
            _, rows, sector_rows = build_snapshot(repository, parse_iso_date(args.date), args.basis)
            print(
                json.dumps(
                    {
                        "snapshot_rows": len(rows),
                        "sector_rows": len(sector_rows),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        if args.command == "sync-sector-map":
            if not config.dart_api_key:
                raise RuntimeError("DART_API_KEY is required for sync-sector-map.")
            client = DartClient(
                config.dart_api_key,
                ssl_cert_file=config.ssl_cert_file,
                retries=config.dart_retries,
                retry_delay_seconds=config.dart_retry_delay_seconds,
                timeout_seconds=config.dart_timeout_seconds,
                request_delay_seconds=config.dart_request_delay_seconds,
            )
            result = sync_sector_map(
                repository,
                client,
                only_missing=not args.include_existing,
                limit=args.limit,
                progress=args.progress,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "export-xlsx":
            as_of_date = parse_iso_date(args.date)
            _, rows, sector_rows = build_snapshot(repository, as_of_date, args.basis)
            event_rows = [dict(row) for row in repository.list_events_until(as_of_date, args.basis)]
            output_path = (
                Path(args.output)
                if args.output
                else config.output_dir / f"nps_snapshot_{safe_slug(as_of_date)}_{args.basis}.xlsx"
            )
            exported = export_snapshot_workbook(output_path, as_of_date, args.basis, rows, event_rows, sector_rows)
            print(str(exported))
            return 0

        if args.command == "export-dashboard":
            as_of_date = parse_iso_date(args.date)
            output_path = (
                Path(args.output)
                if args.output
                else config.html_output_dir / f"nps_dashboard_{safe_slug(as_of_date)}_{args.basis}.html"
            )
            exported = export_dashboard(output_path, args.baseline, repository, as_of_date, args.basis)
            print(str(exported))
            return 0

        if args.command == "export-sector-trends":
            start_date = parse_iso_date(args.start_date)
            end_date = parse_iso_date(args.end_date)
            baseline_rows = load_baseline_holdings(args.baseline)
            event_rows = [dict(row) for row in repository.list_events_until(end_date, args.basis)]
            trends = build_sector_trends(event_rows, baseline_rows, start_date, end_date, args.basis)
            snapshot_rows, _ = calculate_snapshot_rows(repository, end_date, args.basis)
            output_path = (
                Path(args.output)
                if args.output
                else config.html_output_dir
                / f"nps_sector_trends_{safe_slug(start_date)}_{safe_slug(end_date)}_{args.basis}.html"
            )
            csv_path = (
                Path(args.csv_output)
                if args.csv_output
                else output_path.with_suffix(".csv")
            )
            html_path, exported_csv_path = export_sector_trends_report(
                output_path,
                csv_path,
                trends["monthly"],
                trends["quarterly"],
                start_date=start_date,
                end_date=end_date,
                basis_type=args.basis,
                sector_company_rows=_sector_company_rows(snapshot_rows),
            )
            print(json.dumps({"html": str(html_path), "csv": str(exported_csv_path)}, ensure_ascii=False, indent=2))
            return 0

        if args.command == "export-combined-dashboard":
            as_of_date = parse_iso_date(args.date)
            start_date = parse_iso_date(args.start_date)
            end_date = parse_iso_date(args.end_date)
            baseline_rows = load_baseline_holdings(args.baseline)
            snapshot_rows, sector_rows = calculate_snapshot_rows(repository, as_of_date, args.basis)
            dashboard_event_rows = [dict(row) for row in repository.list_events_until(as_of_date, args.basis)]
            trend_event_rows = [dict(row) for row in repository.list_events_until(end_date, args.basis)]
            dashboard_data = build_dashboard_data(
                baseline_rows=baseline_rows,
                snapshot_rows=snapshot_rows,
                event_rows=dashboard_event_rows,
                sector_rows=[asdict(row) for row in sector_rows],
                as_of_date=as_of_date,
                basis_type=args.basis,
                baseline_year=baseline_year_from_path(args.baseline),
            )
            trends = build_sector_trends(trend_event_rows, baseline_rows, start_date, end_date, args.basis)
            trend_snapshot_rows, _ = calculate_snapshot_rows(repository, end_date, args.basis)
            output_path = (
                Path(args.output)
                if args.output
                else config.html_output_dir / f"nps_combined_{safe_slug(as_of_date)}_{args.basis}.html"
            )
            csv_path = (
                Path(args.csv_output)
                if args.csv_output
                else output_path.with_name(f"{output_path.stem}_sector_trends.csv")
            )
            export_sector_trends_csv(csv_path, trends["monthly"] + trends["quarterly"])
            sector_html = render_sector_trends_html(
                trends["monthly"],
                trends["quarterly"],
                start_date=start_date,
                end_date=end_date,
                basis_type=args.basis,
                csv_name=csv_path.name,
                sector_company_rows=_sector_company_rows(trend_snapshot_rows),
            )
            combined = export_combined_html(
                output_path,
                dashboard_html=render_dashboard_html(dashboard_data),
                sector_trends_html=sector_html,
            )
            print(json.dumps({"html": str(combined), "csv": str(csv_path)}, ensure_ascii=False, indent=2))
            return 0

        if args.command == "send-alerts":
            alerts = build_alerts(repository, parse_iso_date(args.since))
            if args.dry_run:
                print(json.dumps([asdict(alert) for alert in alerts], ensure_ascii=False, indent=2))
                return 0
            if not config.kakao_access_token:
                raise RuntimeError("KAKAO_ACCESS_TOKEN is required unless --dry-run is used.")
            send_kakao_alerts(config.kakao_access_token, alerts, config.kakao_web_url)
            print(json.dumps({"alerts_sent": len(alerts)}, ensure_ascii=False, indent=2))
            return 0

        if args.command == "test-kakao":
            text = args.text or config.kakao_test_message
            if args.dry_run:
                print(
                    json.dumps(
                        {
                            "text": text,
                            "web_url": config.kakao_web_url,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            if not config.kakao_access_token:
                raise RuntimeError("KAKAO_ACCESS_TOKEN is required unless --dry-run is used.")
            result = send_kakao_text_message(config.kakao_access_token, text, config.kakao_web_url)
            print(json.dumps({"message_sent": True, "response": result}, ensure_ascii=False, indent=2))
            return 0

        parser.error(f"Unsupported command: {args.command}")
        return 2
    finally:
        repository.close()


def _sector_company_rows(snapshot_rows: list[object]) -> list[dict[str, object]]:
    return [
        {
            "sectorName": getattr(row, "sector_name"),
            "companyName": getattr(row, "company_name"),
            "ticker": getattr(row, "ticker") or "",
            "estimatedShares": getattr(row, "estimated_shares"),
            "ownership": getattr(row, "estimated_ownership"),
            "lastDeltaShares": getattr(row, "last_delta_shares"),
            "lastChangeReason": getattr(row, "last_change_reason") or "",
            "lastDisclosedAt": getattr(row, "last_disclosed_at"),
        }
        for row in snapshot_rows
    ]


if __name__ == "__main__":
    raise SystemExit(main())
