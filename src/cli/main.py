from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.alerts.kakao import send_kakao_alerts, send_kakao_text_message
from src.alerts.service import build_alerts
from src.collect.dart_client import DartClient
from src.collect.probe import probe_filings_by_date
from src.collect.sector_service import sync_sector_map
from src.collect.service import sync_reports
from src.config import AppConfig
from src.db.repository import Repository
from src.export.xlsx_writer import export_snapshot_workbook
from src.snapshot.service import build_snapshot
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
            result = sync_sector_map(repository, client)
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


if __name__ == "__main__":
    raise SystemExit(main())
