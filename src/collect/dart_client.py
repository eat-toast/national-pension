from __future__ import annotations

import json
import ssl
import time
from dataclasses import dataclass, field
from http.client import RemoteDisconnected
from socket import timeout as SocketTimeout
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.models import ReportRecord
from src.utils import parse_iso_date


LIST_ENDPOINT = "https://opendart.fss.or.kr/api/list.json"
DOCUMENT_ENDPOINT = "https://opendart.fss.or.kr/api/document.xml"
MAJORSTOCK_ENDPOINT = "https://opendart.fss.or.kr/api/majorstock.json"
ELESTOCK_ENDPOINT = "https://opendart.fss.or.kr/api/elestock.json"
DEFAULT_REPORT_KEYWORDS = [
    "주식등의대량보유상황보고서",
    "임원ㆍ주요주주",
    "특정증권",
]
DEFAULT_REPORT_DETAIL_TYPES = ["D001", "D002"]


@dataclass(slots=True)
class DartClient:
    api_key: str
    ssl_cert_file: str | None = None
    retries: int = 5
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 20.0
    request_delay_seconds: float = 0.35
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    _last_request_at: float = field(default=0.0, init=False, repr=False)

    def _ssl_context(self) -> ssl.SSLContext | None:
        if self.ssl_cert_file:
            return ssl.create_default_context(cafile=self.ssl_cert_file)
        return None

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urlencode(params)
        return json.loads(self._fetch_url(f"{endpoint}?{query}").decode("utf-8"))

    def _get_bytes(self, endpoint: str, params: dict[str, Any]) -> bytes:
        query = urlencode(params)
        return self._fetch_url(f"{endpoint}?{query}")

    def get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._get_json(endpoint, params)

    def fetch_text(self, url: str) -> str:
        return self._fetch_url(url).decode("utf-8", errors="ignore")

    def _fetch_url(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                self._throttle()
                request = Request(url, headers=self._headers())
                with urlopen(request, context=self._ssl_context(), timeout=self.timeout_seconds) as response:  # noqa: S310
                    self._last_request_at = time.monotonic()
                    return response.read()
            except HTTPError as exc:
                last_error = exc
                if not _should_retry_http_error(exc) or attempt == self.retries:
                    break
                time.sleep(self._backoff_seconds(attempt))
            except (RemoteDisconnected, TimeoutError, SocketTimeout, URLError, ssl.SSLError) as exc:
                last_error = exc
                if attempt == self.retries:
                    break
                time.sleep(self._backoff_seconds(attempt))
        assert last_error is not None
        raise last_error

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.5,en;q=0.3",
            "Connection": "close",
            "Referer": "https://dart.fss.or.kr/",
        }

    def _throttle(self) -> None:
        if self.request_delay_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.request_delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _backoff_seconds(self, attempt: int) -> float:
        return self.retry_delay_seconds * (2 ** (attempt - 1))

    def list_reports(self, start_date: str, end_date: str) -> list[ReportRecord]:
        return self.list_reports_by_detail_types(
            start_date,
            end_date,
            DEFAULT_REPORT_DETAIL_TYPES,
        )

    def list_reports_by_detail_types(
        self,
        start_date: str,
        end_date: str,
        detail_types: list[str],
    ) -> list[ReportRecord]:
        reports: list[ReportRecord] = []
        seen: set[str] = set()
        for detail_type in detail_types:
            page_no = 1
            while True:
                payload = self._get_json(
                    LIST_ENDPOINT,
                    {
                        "crtfc_key": self.api_key,
                        "bgn_de": parse_iso_date(start_date).replace("-", ""),
                        "end_de": parse_iso_date(end_date).replace("-", ""),
                        "last_reprt_at": "Y",
                        "pblntf_detail_ty": detail_type,
                        "page_no": page_no,
                        "page_count": 100,
                    },
                )
                status = payload.get("status")
                if status not in {"000", "013"}:
                    raise RuntimeError(f"DART list.json failed: {status} {payload.get('message')}")
                for item in payload.get("list", []):
                    receipt_no = item["rcept_no"]
                    if receipt_no in seen:
                        continue
                    seen.add(receipt_no)
                    reports.append(_report_from_list_item(item))
                total_pages = int(payload.get("total_page", 1) or 1)
                if page_no >= total_pages:
                    break
                page_no += 1
        return reports

    def list_reports_by_keywords(
        self,
        start_date: str,
        end_date: str,
        report_keywords: list[str],
    ) -> list[ReportRecord]:
        reports: list[ReportRecord] = []
        page_no = 1
        while True:
            payload = self._get_json(
                LIST_ENDPOINT,
                {
                    "crtfc_key": self.api_key,
                    "bgn_de": parse_iso_date(start_date).replace("-", ""),
                    "end_de": parse_iso_date(end_date).replace("-", ""),
                    "last_reprt_at": "Y",
                    "pblntf_ty": "D",
                    "page_no": page_no,
                    "page_count": 100,
                },
            )
            status = payload.get("status")
            if status not in {"000", "013"}:
                raise RuntimeError(f"DART list.json failed: {status} {payload.get('message')}")
            for item in payload.get("list", []):
                report_name = item.get("report_nm", "")
                if not any(keyword in report_name for keyword in report_keywords):
                    continue
                reports.append(
                    ReportRecord(
                        receipt_no=item["rcept_no"],
                        corp_code=item.get("corp_code"),
                        corp_name=item.get("corp_name", ""),
                        stock_code=item.get("stock_code"),
                        report_name=report_name,
                        filer_name=item.get("flr_nm", ""),
                        disclosed_at=parse_iso_date(item["rcept_dt"]),
                        is_amended="정정" in report_name or "[기재정정]" in report_name,
                        source_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item['rcept_no']}",
                        raw_payload=json.dumps(item, ensure_ascii=False),
                    )
                )
            total_pages = int(payload.get("total_page", 1) or 1)
            if page_no >= total_pages:
                break
            page_no += 1
        return reports

    def download_document(self, receipt_no: str) -> bytes:
        return self._get_bytes(
            DOCUMENT_ENDPOINT,
            {
                "crtfc_key": self.api_key,
                "rcept_no": receipt_no,
            },
        )

    def majorstock_reports(self, corp_code: str) -> list[dict[str, Any]]:
        return self._ownership_reports(MAJORSTOCK_ENDPOINT, corp_code)

    def elestock_reports(self, corp_code: str) -> list[dict[str, Any]]:
        return self._ownership_reports(ELESTOCK_ENDPOINT, corp_code)

    def company_profile(self, corp_code: str) -> dict[str, Any]:
        payload = self._get_json(
            "https://opendart.fss.or.kr/api/company.json",
            {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
            },
        )
        status = payload.get("status")
        if status != "000":
            raise RuntimeError(f"DART company.json failed: {status} {payload.get('message')}")
        return payload

    def _ownership_reports(self, endpoint: str, corp_code: str) -> list[dict[str, Any]]:
        payload = self._get_json(
            endpoint,
            {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
            },
        )
        status = payload.get("status")
        if status == "013":
            return []
        if status != "000":
            raise RuntimeError(f"DART ownership API failed: {status} {payload.get('message')}")
        return payload.get("list", [])


def _report_from_list_item(item: dict[str, Any]) -> ReportRecord:
    report_name = item.get("report_nm", "")
    return ReportRecord(
        receipt_no=item["rcept_no"],
        corp_code=item.get("corp_code"),
        corp_name=item.get("corp_name", ""),
        stock_code=item.get("stock_code"),
        report_name=report_name,
        filer_name=item.get("flr_nm", ""),
        disclosed_at=parse_iso_date(item["rcept_dt"]),
        is_amended="정정" in report_name or "[기재정정]" in report_name,
        source_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item['rcept_no']}",
        raw_payload=json.dumps(item, ensure_ascii=False),
    )


def _should_retry_http_error(error: HTTPError) -> bool:
    return error.code in {408, 425, 429, 500, 502, 503, 504}
