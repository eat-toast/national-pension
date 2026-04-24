from __future__ import annotations

import unittest

from src.collect.probe import _extract_excerpt, _viewer_url, probe_filings_by_date


class _FakeClient:
    def __init__(self) -> None:
        self.api_key = "test"

    def get_json(self, endpoint, params):
        return {
            "status": "000",
            "total_page": 1,
            "list": [
                {
                    "rcept_no": "20260420000259",
                    "corp_name": "HL만도",
                    "report_nm": "임원ㆍ주요주주특정증권등소유상황보고서",
                    "flr_nm": "기타보고자",
                }
            ],
        }

    def fetch_text(self, url: str) -> str:
        if "main.do" in url:
            return 'viewDoc("20260420000259", "11336236", "1", "674", "2512", "dart4.xsd", "")'
        return "<html><body>보고자 : 국민연금공단</body></html>"


class ProbeTest(unittest.TestCase):
    def test_probe_matches_keyword_in_viewer(self) -> None:
        result = probe_filings_by_date(_FakeClient(), "2026-04-20", "국민연금")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["match_count"], 1)
        self.assertTrue(result["matches"][0]["viewer_keyword_hit"])

    def test_viewer_url_builder(self) -> None:
        url = _viewer_url(
            {
                "rcpNo": "1",
                "dcmNo": "2",
                "eleId": "3",
                "offset": "4",
                "length": "5",
                "dtd": "dart4.xsd",
            }
        )
        self.assertIn("viewer.do", url)
        self.assertIn("rcpNo=1", url)

    def test_excerpt(self) -> None:
        excerpt = _extract_excerpt("aaaa 국민연금공단 bbbb", "국민연금")
        self.assertIn("국민연금", excerpt)


if __name__ == "__main__":
    unittest.main()
