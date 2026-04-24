from __future__ import annotations

import unittest

from src.db.repository import Repository
from src.models import HoldingEvent, ReportRecord
from src.snapshot.service import build_snapshot


class SnapshotServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Repository(":memory:")
        self.repository.upsert_sector("005930", "반도체")

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

    def test_effective_and_disclosure_basis_can_differ(self) -> None:
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

        _, effective_rows, _ = build_snapshot(self.repository, "2024-01-07", "effective_date")
        _, disclosure_rows, _ = build_snapshot(self.repository, "2024-01-07", "disclosure_date")

        self.assertEqual(len(effective_rows), 1)
        self.assertEqual(effective_rows[0].company_name, "삼성전자")
        self.assertEqual(disclosure_rows, [])

    def test_sector_defaults_to_unknown(self) -> None:
        self._insert_report("2", "2024-02-10")
        self.repository.replace_events_for_report(
            "2",
            [
                HoldingEvent(
                    report_receipt_no="2",
                    ticker="000660",
                    company_name="SK하이닉스",
                    effective_date="2024-02-05",
                    disclosed_at="2024-02-10",
                    delta_shares=500,
                    shares_after=5000,
                    ownership_after=0.0755,
                    change_reason="장내매수",
                    event_type="buy",
                )
            ],
        )
        _, rows, sectors = build_snapshot(self.repository, "2024-02-20", "effective_date")
        self.assertEqual(rows[0].sector_name, "미분류")
        self.assertEqual(sectors[0].sector_name, "미분류")


if __name__ == "__main__":
    unittest.main()
