from __future__ import annotations

import unittest

from src.analysis.sector_trends import build_sector_trends
from src.dashboard.baseline import BaselineHolding


class SectorTrendsTest(unittest.TestCase):
    def test_builds_monthly_and_quarterly_sector_trends(self) -> None:
        rows = [
            {
                "id": 1,
                "ticker": "005930",
                "company_name": "삼성전자",
                "disclosed_at": "2025-01-10",
                "effective_date": "2025-01-09",
                "delta_shares": 100,
                "ownership_after": 0.08,
                "sector_name": "IT",
            },
            {
                "id": 2,
                "ticker": "005930",
                "company_name": "삼성전자",
                "disclosed_at": "2025-02-10",
                "effective_date": "2025-02-09",
                "delta_shares": -20,
                "ownership_after": 0.075,
                "sector_name": "IT",
            },
            {
                "id": 3,
                "ticker": "000080",
                "company_name": "하이트진로",
                "disclosed_at": "2025-04-01",
                "effective_date": "2025-03-30",
                "delta_shares": 50,
                "ownership_after": 0.06,
                "sector_name": "음식료",
            },
        ]
        baseline = [
            BaselineHolding(1, "삼성전자", None, None, 0.07),
            BaselineHolding(2, "하이트진로", None, None, 0.05),
        ]

        trends = build_sector_trends(rows, baseline, "2025-01-01", "2025-12-31", "disclosure_date")

        monthly = {(row.period, row.sector_name): row for row in trends["monthly"]}
        self.assertAlmostEqual(monthly[("2025-01", "IT")].net_ownership_delta, 0.01)
        self.assertAlmostEqual(monthly[("2025-02", "IT")].net_ownership_delta, -0.005)
        self.assertEqual(monthly[("2025-02", "IT")].decrease_count, 1)
        quarterly = {(row.period, row.sector_name): row for row in trends["quarterly"]}
        self.assertAlmostEqual(quarterly[("2025-Q1", "IT")].net_ownership_delta, 0.005)
        self.assertAlmostEqual(quarterly[("2025-Q2", "음식료")].net_ownership_delta, 0.01)


if __name__ == "__main__":
    unittest.main()
