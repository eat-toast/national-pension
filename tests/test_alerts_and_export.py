from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from src.alerts.service import build_alerts
from src.db.repository import Repository
from src.export.xlsx_writer import export_snapshot_workbook
from src.models import HoldingEvent, ReportRecord, SnapshotRow
from src.snapshot.service import build_snapshot


class AlertsAndExportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Repository(":memory:")

    def tearDown(self) -> None:
        self.repository.close()

    def _insert_report(self, receipt_no: str, disclosed_at: str) -> None:
        self.repository.upsert_report(
            ReportRecord(
                receipt_no=receipt_no,
                corp_code="00126380",
                corp_name="삼성전자",
                stock_code="005930",
                report_name="주식등의대량보유상황보고서",
                filer_name="국민연금공단",
                disclosed_at=disclosed_at,
            )
        )

    def test_alert_rules(self) -> None:
        self._insert_report("1", "2024-01-10")
        self._insert_report("2", "2024-02-10")
        self.repository.replace_events_for_report(
            "1",
            [
                HoldingEvent(
                    report_receipt_no="1",
                    ticker="005930",
                    company_name="삼성전자",
                    effective_date="2024-01-05",
                    disclosed_at="2024-01-10",
                    delta_shares=1000,
                    shares_after=10000,
                    ownership_after=0.095,
                    change_reason="장내매수",
                    event_type="buy",
                )
            ],
        )
        self.repository.replace_events_for_report(
            "2",
            [
                HoldingEvent(
                    report_receipt_no="2",
                    ticker="005930",
                    company_name="삼성전자",
                    effective_date="2024-02-05",
                    disclosed_at="2024-02-10",
                    delta_shares=800,
                    shares_after=10800,
                    ownership_after=0.105,
                    change_reason="장내매수",
                    event_type="buy",
                )
            ],
        )
        alerts = build_alerts(self.repository, "2024-01-01")
        categories = [alert.category for alert in alerts]
        self.assertIn("new_5pct", categories)
        self.assertIn("cross_10pct", categories)
        self.assertIn("ownership_change", categories)

    def test_export_creates_valid_xlsx_archive(self) -> None:
        self._insert_report("1", "2024-01-10")
        self.repository.replace_events_for_report(
            "1",
            [
                HoldingEvent(
                    report_receipt_no="1",
                    ticker="005930",
                    company_name="삼성전자",
                    effective_date="2024-01-05",
                    disclosed_at="2024-01-10",
                    delta_shares=1000,
                    shares_after=10000,
                    ownership_after=0.0726,
                    change_reason="장내매수",
                    event_type="buy",
                )
            ],
        )
        _, rows, sectors = build_snapshot(self.repository, "2024-01-31", "effective_date")
        events = [dict(row) for row in self.repository.list_events_until("2024-01-31", "effective_date")]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "snapshot.xlsx"
            export_snapshot_workbook(output_path, "2024-01-31", "effective_date", rows, events, sectors)
            self.assertTrue(output_path.exists())
            with ZipFile(output_path) as archive:
                names = set(archive.namelist())
                self.assertIn("xl/workbook.xml", names)
                self.assertIn("xl/worksheets/sheet1.xml", names)


if __name__ == "__main__":
    unittest.main()
