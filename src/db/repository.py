from __future__ import annotations

import sqlite3
from pathlib import Path

from src.db.schema import init_db
from src.models import BasisType, HoldingEvent, ReportRecord, SnapshotRow


class Repository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        init_db(self.connection)

    def close(self) -> None:
        self.connection.close()

    def upsert_report(self, report: ReportRecord) -> None:
        self.connection.execute(
            """
            INSERT INTO reports (
                receipt_no, corp_code, corp_name, stock_code, report_name, filer_name,
                disclosed_at, is_amended, original_receipt_no, source_url, raw_payload,
                parse_status, parse_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(receipt_no) DO UPDATE SET
                corp_code=excluded.corp_code,
                corp_name=excluded.corp_name,
                stock_code=excluded.stock_code,
                report_name=excluded.report_name,
                filer_name=excluded.filer_name,
                disclosed_at=excluded.disclosed_at,
                is_amended=excluded.is_amended,
                original_receipt_no=excluded.original_receipt_no,
                source_url=excluded.source_url,
                raw_payload=excluded.raw_payload,
                parse_status=excluded.parse_status,
                parse_error=excluded.parse_error
            """,
            (
                report.receipt_no,
                report.corp_code,
                report.corp_name,
                report.stock_code,
                report.report_name,
                report.filer_name,
                report.disclosed_at,
                int(report.is_amended),
                report.original_receipt_no,
                report.source_url,
                report.raw_payload,
                report.parse_status,
                report.parse_error,
            ),
        )
        self.connection.commit()

    def replace_events_for_report(self, receipt_no: str, events: list[HoldingEvent]) -> None:
        self.connection.execute(
            "DELETE FROM holding_events WHERE report_receipt_no = ?",
            (receipt_no,),
        )
        self.connection.executemany(
            """
            INSERT INTO holding_events (
                report_receipt_no, ticker, company_name, effective_date, disclosed_at,
                delta_shares, shares_after, ownership_after, change_reason, event_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event.report_receipt_no,
                    event.ticker,
                    event.company_name,
                    event.effective_date,
                    event.disclosed_at,
                    event.delta_shares,
                    event.shares_after,
                    event.ownership_after,
                    event.change_reason,
                    event.event_type,
                )
                for event in events
            ],
        )
        self.connection.commit()

    def list_events_until(self, as_of_date: str, basis_type: BasisType) -> list[sqlite3.Row]:
        basis_column = "effective_date" if basis_type == "effective_date" else "disclosed_at"
        query = f"""
            SELECT e.*, COALESCE(s.sector_name, '미분류') AS sector_name
            FROM holding_events e
            LEFT JOIN sector_map s ON s.ticker = e.ticker
            WHERE COALESCE({basis_column}, disclosed_at) <= ?
            ORDER BY COALESCE({basis_column}, disclosed_at), disclosed_at, id
        """
        return list(self.connection.execute(query, (as_of_date,)))

    def save_snapshot(self, as_of_date: str, basis_type: BasisType, rows: list[SnapshotRow]) -> int:
        cursor = self.connection.execute(
            "INSERT INTO snapshot_runs (as_of_date, basis_type) VALUES (?, ?)",
            (as_of_date, basis_type),
        )
        run_id = int(cursor.lastrowid)
        self.connection.executemany(
            """
            INSERT INTO snapshot_rows (
                run_id, ticker, company_name, estimated_shares, estimated_ownership,
                last_delta_shares, last_change_reason, last_effective_date,
                last_disclosed_at, sector_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    row.ticker,
                    row.company_name,
                    row.estimated_shares,
                    row.estimated_ownership,
                    row.last_delta_shares,
                    row.last_change_reason,
                    row.last_effective_date,
                    row.last_disclosed_at,
                    row.sector_name,
                )
                for row in rows
            ],
        )
        self.connection.commit()
        return run_id

    def list_snapshot_rows(self, run_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT * FROM snapshot_rows
                WHERE run_id = ?
                ORDER BY estimated_ownership DESC, company_name
                """,
                (run_id,),
            )
        )

    def upsert_sector(self, ticker: str, sector_name: str) -> None:
        self.connection.execute(
            """
            INSERT INTO sector_map (ticker, sector_name)
            VALUES (?, ?)
            ON CONFLICT(ticker) DO UPDATE SET sector_name=excluded.sector_name
            """,
            (ticker, sector_name),
        )
        self.connection.commit()

    def get_previous_event(self, ticker: str | None, disclosed_at: str) -> sqlite3.Row | None:
        if not ticker:
            return None
        return self.connection.execute(
            """
            SELECT *
            FROM holding_events
            WHERE ticker = ? AND disclosed_at < ?
            ORDER BY COALESCE(effective_date, disclosed_at) DESC, disclosed_at DESC, id DESC
            LIMIT 1
            """,
            (ticker, disclosed_at),
        ).fetchone()

    def list_events_since(self, since_date: str) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT *
                FROM holding_events
                WHERE disclosed_at >= ?
                ORDER BY disclosed_at, id
                """,
                (since_date,),
            )
        )
