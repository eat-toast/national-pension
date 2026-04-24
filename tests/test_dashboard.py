from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.dashboard.baseline import load_baseline_holdings
from src.dashboard.service import export_dashboard
from src.db.repository import Repository
from src.models import HoldingEvent, ReportRecord


ROOT = Path(__file__).resolve().parents[1]
BASELINE_2024 = ROOT / "국내주식 종목별 투자 현황(2024년 말).xlsx"


class DashboardTest(unittest.TestCase):
    def test_loads_2024_baseline_excel(self) -> None:
        rows = load_baseline_holdings(BASELINE_2024)
        self.assertGreater(len(rows), 1000)
        self.assertEqual(rows[0].company_name, "삼성전자")
        self.assertAlmostEqual(rows[0].ownership or 0, 0.0726, places=4)

    def test_export_dashboard_html(self) -> None:
        repository = Repository(":memory:")
        try:
            repository.upsert_report(
                ReportRecord(
                    receipt_no="1",
                    corp_code="00126380",
                    corp_name="삼성전자",
                    stock_code="005930",
                    report_name="주식등의대량보유상황보고서",
                    filer_name="국민연금공단",
                    disclosed_at="2025-01-03",
                )
            )
            repository.replace_events_for_report(
                "1",
                [
                    HoldingEvent(
                        report_receipt_no="1",
                        ticker="005930",
                        company_name="삼성전자",
                        effective_date=None,
                        disclosed_at="2025-01-03",
                        delta_shares=1000,
                        shares_after=10000,
                        ownership_after=0.08,
                        change_reason="장내매수",
                        event_type="buy",
                    )
                ],
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "dashboard.html"
                export_dashboard(output, BASELINE_2024, repository, "2025-12-31", "disclosure_date")
                html = output.read_text(encoding="utf-8")
                self.assertIn("국민연금 국내주식 변동 대시보드", html)
                self.assertIn("DASHBOARD_DATA", html)
                self.assertIn("삼성전자", html)
                self.assertIn("종목별 히스토리", html)
                self.assertIn("stockSearch", html)
                self.assertIn("ownershipDelta", html)
                self.assertIn("0.007400000000000004", html)
        finally:
            repository.close()


if __name__ == "__main__":
    unittest.main()
