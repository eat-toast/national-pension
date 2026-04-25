#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.sector_trends import build_sector_trends
from src.config import AppConfig
from src.dashboard.baseline import baseline_year_from_path, load_baseline_holdings
from src.dashboard.service import build_dashboard_data, render_dashboard_html
from src.db.repository import Repository
from src.export.combined_html_writer import export_combined_html
from src.export.sector_trends_writer import export_sector_trends_csv, render_sector_trends_html
from src.snapshot.service import calculate_snapshot_rows
from src.utils import parse_iso_date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the static GitHub Pages site.")
    parser.add_argument("--date", default="2025-12-31", help="Portfolio dashboard date.")
    parser.add_argument("--from", dest="start_date", default="2025-01-01", help="Sector trend start date.")
    parser.add_argument("--to", dest="end_date", default="2026-04-20", help="Sector trend end date.")
    parser.add_argument(
        "--basis",
        choices=("effective_date", "disclosure_date"),
        default="disclosure_date",
        help="Date basis used for snapshots and trends.",
    )
    parser.add_argument("--baseline", default="국내주식 종목별 투자 현황(2024년 말).xlsx")
    parser.add_argument("--site-dir", default="site", help="Output directory for GitHub Pages artifact.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    as_of_date = parse_iso_date(args.date)
    start_date = parse_iso_date(args.start_date)
    end_date = parse_iso_date(args.end_date)
    basis = args.basis
    site_dir = Path(args.site_dir)

    config = AppConfig.from_env()
    if not config.db_path.exists():
        raise SystemExit(
            f"Database not found: {config.db_path}. "
            "Run sync-reports first, or provide NPS_DB_PATH for an existing SQLite database."
        )

    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        raise SystemExit(f"Baseline workbook not found: {baseline_path}")

    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    repository = Repository(config.db_path)
    try:
        baseline_rows = load_baseline_holdings(baseline_path)

        dashboard_snapshot_rows, sector_rows = calculate_snapshot_rows(repository, as_of_date, basis)
        dashboard_event_rows = [dict(row) for row in repository.list_events_until(as_of_date, basis)]
        dashboard_data = build_dashboard_data(
            baseline_rows=baseline_rows,
            snapshot_rows=dashboard_snapshot_rows,
            event_rows=dashboard_event_rows,
            sector_rows=[asdict(row) for row in sector_rows],
            as_of_date=as_of_date,
            basis_type=basis,
            baseline_year=baseline_year_from_path(baseline_path),
        )
        dashboard_html = render_dashboard_html(dashboard_data)

        trend_event_rows = [dict(row) for row in repository.list_events_until(end_date, basis)]
        trends = build_sector_trends(trend_event_rows, baseline_rows, start_date, end_date, basis)
        trend_snapshot_rows, _ = calculate_snapshot_rows(repository, end_date, basis)

        csv_path = site_dir / "nps_sector_trends.csv"
        export_sector_trends_csv(csv_path, trends["monthly"] + trends["quarterly"])
        sector_html = render_sector_trends_html(
            trends["monthly"],
            trends["quarterly"],
            start_date=start_date,
            end_date=end_date,
            basis_type=basis,
            csv_name=csv_path.name,
            sector_company_rows=_sector_company_rows(trend_snapshot_rows),
        )

        (site_dir / "dashboard.html").write_text(dashboard_html, encoding="utf-8")
        (site_dir / "sector-trends.html").write_text(sector_html, encoding="utf-8")
        export_combined_html(
            site_dir / "index.html",
            dashboard_html=dashboard_html,
            sector_trends_html=sector_html,
        )
        (site_dir / ".nojekyll").write_text("", encoding="utf-8")
        (site_dir / "site-meta.json").write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "dashboard_date": as_of_date,
                    "trend_start_date": start_date,
                    "trend_end_date": end_date,
                    "basis": basis,
                    "baseline": str(baseline_path),
                    "files": [
                        "index.html",
                        "dashboard.html",
                        "sector-trends.html",
                        "nps_sector_trends.csv",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        repository.close()

    print(json.dumps({"site_dir": str(site_dir), "index": str(site_dir / "index.html")}, ensure_ascii=False, indent=2))
    return 0


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
