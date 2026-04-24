from __future__ import annotations

import unittest

from src.collect.service import sync_reports
from src.db.repository import Repository
from src.models import ReportRecord


class _FakeClient:
    def __init__(self) -> None:
        self.api_key = "test"

    def list_reports_by_keywords(self, start_date, end_date, report_keywords):
        return [
            ReportRecord(
                receipt_no="20260420000259",
                corp_code="01042775",
                corp_name="HL만도",
                stock_code="204320",
                report_name="임원ㆍ주요주주특정증권등소유상황보고서",
                filer_name="기타보고자",
                disclosed_at="2026-04-20",
            ),
            ReportRecord(
                receipt_no="20260420000522",
                corp_code="12345678",
                corp_name="HK이노엔",
                stock_code="195940",
                report_name="임원ㆍ주요주주특정증권등소유상황보고서",
                filer_name="기타보고자",
                disclosed_at="2026-04-20",
            ),
        ]

    def fetch_text(self, url: str) -> str:
        if "20260420000259" in url and "main.do" in url:
            return """
            var node1 = {};
            node1['text'] = "1. 발행회사에 관한 사항";
            node1['rcpNo'] = "20260420000259";
            node1['dcmNo'] = "11336236";
            node1['eleId'] = "2";
            node1['offset'] = "3465";
            node1['length'] = "1488";
            node1['dtd'] = "dart4.xsd";
            treeData.push(node1);
            var node1 = {};
            node1['text'] = "2. 보고자에 관한 사항";
            node1['rcpNo'] = "20260420000259";
            node1['dcmNo'] = "11336236";
            node1['eleId'] = "3";
            node1['offset'] = "4957";
            node1['length'] = "6118";
            node1['dtd'] = "dart4.xsd";
            treeData.push(node1);
            var node1 = {};
            node1['text'] = "3. 특정증권등의 소유상황";
            node1['rcpNo'] = "20260420000259";
            node1['dcmNo'] = "11336236";
            node1['eleId'] = "4";
            node1['offset'] = "11079";
            node1['length'] = "29145";
            node1['dtd'] = "dart4.xsd";
            treeData.push(node1);
            """
        if "20260420000259" in url and "viewer.do" in url and "eleId=2" in url:
            return """
            <table>
              <tr><td>회 사 명</td><td>HL만도</td></tr>
              <tr><td>법인구분</td><td>유가증권상장법인</td><td>회사코드</td><td>204320</td></tr>
            </table>
            """
        if "20260420000259" in url and "viewer.do" in url and "eleId=3" in url:
            return "<html><body>보고자 : 국민연금공단</body></html>"
        if "20260420000259" in url and "viewer.do" in url and "eleId=4" in url:
            return """
            <table>
              <tr><th></th><th>보고서 작성 기준일</th><th>특정증권등의 수(주)</th><th>비율(%)</th><th>주식수(주)</th><th>비율(%)</th></tr>
              <tr><td>이번보고서</td><td>2026년 04월 15일</td><td>4,685,078</td><td>9.98</td><td>4,685,078</td><td>9.98</td></tr>
              <tr><td colspan="2">증 감</td><td>-453,075</td><td>-0.96</td><td>-453,075</td><td>-0.96</td></tr>
            </table>
            """
        if "20260420000522" in url and "main.do" in url:
            return 'viewDoc("20260420000522", "11330000", "1", "1", "1000", "dart4.xsd", "")'
        if "20260420000522" in url and "viewer.do" in url:
            return "<html><body>다른 보고자</body></html>"
        return ""

    def download_document(self, receipt_no: str) -> bytes:
        return self.fetch_text(f"https://example.test/{receipt_no}/viewer.do").encode("utf-8")


class SyncServiceTest(unittest.TestCase):
    def test_sync_filters_by_keyword_in_viewer(self) -> None:
        repository = Repository(":memory:")
        try:
            result = sync_reports(repository, _FakeClient(), "2026-04-20", "2026-04-20")
            self.assertEqual(result["candidates"], 2)
            self.assertEqual(result["keyword_matched"], 1)
            self.assertEqual(result["parsed"], 1)
            self.assertEqual(result["skipped"], 1)
            rows = repository.list_events_until("2026-04-20", "effective_date")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["company_name"], "HL만도")
        finally:
            repository.close()


if __name__ == "__main__":
    unittest.main()
