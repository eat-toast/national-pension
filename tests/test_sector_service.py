from __future__ import annotations

import unittest

from src.collect.sector_service import sync_sector_map
from src.db.repository import Repository
from src.models import HoldingEvent, ReportRecord


class _SectorClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def company_profile(self, corp_code: str):
        self.calls.append(corp_code)
        return {"induty_code": {"00126937": "64992", "00150244": "11122", "00145109": "212"}[corp_code]}


class SectorServiceTest(unittest.TestCase):
    def test_sync_sector_map_limits_to_missing_rows(self) -> None:
        repository = Repository(":memory:")
        client = _SectorClient()
        try:
            self._add_event(repository, "r1", "00126937", "000070", "삼양홀딩스")
            self._add_event(repository, "r2", "00150244", "000080", "하이트진로")
            self._add_event(repository, "r3", "00145109", "000100", "유한양행")
            repository.upsert_sector("000070", "금융")

            result = sync_sector_map(repository, client, limit=2)

            self.assertEqual(result, {"candidates": 2, "updated": 2, "skipped": 0, "errors": 0})
            self.assertEqual(client.calls, ["00150244", "00145109"])
            rows = repository.connection.execute(
                "SELECT ticker, sector_name FROM sector_map ORDER BY ticker"
            ).fetchall()
            self.assertEqual(
                [(row["ticker"], row["sector_name"]) for row in rows],
                [("000070", "금융"), ("000080", "음식료"), ("000100", "헬스케어")],
            )
        finally:
            repository.close()

    def _add_event(
        self,
        repository: Repository,
        receipt_no: str,
        corp_code: str,
        ticker: str,
        company_name: str,
    ) -> None:
        repository.upsert_report(
            ReportRecord(
                receipt_no=receipt_no,
                corp_code=corp_code,
                corp_name=company_name,
                stock_code=ticker,
                report_name="임원ㆍ주요주주특정증권등소유상황보고서",
                filer_name="국민연금공단",
                disclosed_at="2026-04-20",
            )
        )
        repository.replace_events_for_report(
            receipt_no,
            [
                HoldingEvent(
                    report_receipt_no=receipt_no,
                    ticker=ticker,
                    company_name=company_name,
                    effective_date="2026-04-20",
                    disclosed_at="2026-04-20",
                    delta_shares=1,
                    shares_after=1,
                    ownership_after=0.1,
                    change_reason="테스트",
                    event_type="buy",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
