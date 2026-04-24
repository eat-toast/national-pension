from __future__ import annotations

import unittest

from src.models import ReportRecord, ReportSection
from src.parse.report_parser import parse_report_document, parse_report_viewer_sections


class ReportParserTest(unittest.TestCase):
    def test_parse_html_table(self) -> None:
        report = ReportRecord(
            receipt_no="20240101000001",
            corp_code="001",
            corp_name="삼성전자",
            stock_code="005930",
            report_name="주식등의대량보유상황보고서",
            filer_name="국민연금공단",
            disclosed_at="2024-01-10",
        )
        html = """
        <html>
          <body>
            <table>
              <tr>
                <th>종목명</th><th>종목코드</th><th>변동일</th><th>직전 보고서 대비 증감 수량</th>
                <th>보유주식등의 수</th><th>보유비율</th><th>변동 사유</th>
              </tr>
              <tr>
                <td>삼성전자</td><td>005930</td><td>2024-01-05</td><td>1,000</td>
                <td>10,000</td><td>7.26%</td><td>장내매수</td>
              </tr>
            </table>
          </body>
        </html>
        """
        events = parse_report_document(html.encode("utf-8"), report)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.ticker, "005930")
        self.assertEqual(event.company_name, "삼성전자")
        self.assertEqual(event.effective_date, "2024-01-05")
        self.assertAlmostEqual(event.ownership_after or 0.0, 0.0726, places=4)
        self.assertEqual(event.event_type, "buy")

    def test_parse_specific_security_viewer_sections(self) -> None:
        report = ReportRecord(
            receipt_no="20260420000259",
            corp_code="01042775",
            corp_name="HL만도",
            stock_code="204320",
            report_name="임원ㆍ주요주주특정증권등소유상황보고서",
            filer_name="기타보고자",
            disclosed_at="2026-04-20",
        )
        sections = [
            ReportSection(
                title="1. 발행회사에 관한 사항",
                url="https://example.test/issuer",
                html="""
                <table>
                  <tr><td>회 사 명</td><td colspan="3">HL만도</td></tr>
                  <tr><td>법인구분</td><td>유가증권상장법인</td><td>회사코드</td><td>204320</td></tr>
                  <tr><td>발행주식 총수</td><td colspan="3">46,957,120</td></tr>
                </table>
                """,
            ),
            ReportSection(
                title="3. 특정증권등의 소유상황",
                url="https://example.test/ownership",
                html="""
                <table>
                  <tr>
                    <th rowspan="2"></th><th rowspan="2">보고서<br/>작성 기준일</th>
                    <th colspan="2">특정증권등</th><th colspan="2">주권</th>
                  </tr>
                  <tr>
                    <th>특정증권등의<br/>수(주)</th><th>비율(%)</th>
                    <th>주식수(주)</th><th>비율(%)</th>
                  </tr>
                  <tr>
                    <td>직전보고서</td><td>2026년 03월 31일</td><td>5,138,153</td><td>10.94</td><td>5,138,153</td><td>10.94</td>
                  </tr>
                  <tr>
                    <td>이번보고서</td><td>2026년 04월 15일</td><td>4,685,078</td><td>9.98</td><td>4,685,078</td><td>9.98</td>
                  </tr>
                  <tr>
                    <td colspan="2">증 &nbsp; &nbsp; 감</td><td>-453,075</td><td>-0.96</td><td>-453,075</td><td>-0.96</td>
                  </tr>
                </table>
                """,
            ),
        ]

        events = parse_report_viewer_sections(sections, report)

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.ticker, "204320")
        self.assertEqual(event.company_name, "HL만도")
        self.assertEqual(event.effective_date, "2026-04-15")
        self.assertEqual(event.shares_after, 4685078)
        self.assertEqual(event.delta_shares, -453075)
        self.assertAlmostEqual(event.ownership_after or 0.0, 0.0998, places=4)
        self.assertEqual(event.event_type, "sell")


if __name__ == "__main__":
    unittest.main()
