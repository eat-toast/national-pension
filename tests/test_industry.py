from __future__ import annotations

import unittest

from src.analysis.industry import sector_from_industry_code


class IndustryTest(unittest.TestCase):
    def test_sector_from_industry_code(self) -> None:
        self.assertEqual(sector_from_industry_code("303"), "자동차")
        self.assertEqual(sector_from_industry_code("412"), "건설")
        self.assertEqual(sector_from_industry_code(None), "미분류")


if __name__ == "__main__":
    unittest.main()
