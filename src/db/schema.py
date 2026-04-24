from __future__ import annotations

import sqlite3


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS reports (
            receipt_no TEXT PRIMARY KEY,
            corp_code TEXT,
            corp_name TEXT NOT NULL,
            stock_code TEXT,
            report_name TEXT NOT NULL,
            filer_name TEXT NOT NULL,
            disclosed_at TEXT NOT NULL,
            is_amended INTEGER NOT NULL DEFAULT 0,
            original_receipt_no TEXT,
            source_url TEXT,
            raw_payload TEXT,
            parse_status TEXT NOT NULL DEFAULT 'pending',
            parse_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS holding_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_receipt_no TEXT NOT NULL,
            ticker TEXT,
            company_name TEXT NOT NULL,
            effective_date TEXT,
            disclosed_at TEXT NOT NULL,
            delta_shares REAL,
            shares_after REAL,
            ownership_after REAL,
            change_reason TEXT,
            event_type TEXT,
            FOREIGN KEY(report_receipt_no) REFERENCES reports(receipt_no) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sector_map (
            ticker TEXT PRIMARY KEY,
            sector_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS snapshot_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            as_of_date TEXT NOT NULL,
            basis_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS snapshot_rows (
            run_id INTEGER NOT NULL,
            ticker TEXT,
            company_name TEXT NOT NULL,
            estimated_shares REAL,
            estimated_ownership REAL,
            last_delta_shares REAL,
            last_change_reason TEXT,
            last_effective_date TEXT,
            last_disclosed_at TEXT NOT NULL,
            sector_name TEXT NOT NULL DEFAULT '미분류',
            FOREIGN KEY(run_id) REFERENCES snapshot_runs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_holding_events_ticker_date
        ON holding_events(ticker, effective_date, disclosed_at);
        """
    )
