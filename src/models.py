from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


BasisType = Literal["effective_date", "disclosure_date"]


@dataclass(slots=True)
class ReportRecord:
    receipt_no: str
    corp_code: str | None
    corp_name: str
    stock_code: str | None
    report_name: str
    filer_name: str
    disclosed_at: str
    is_amended: bool = False
    original_receipt_no: str | None = None
    source_url: str | None = None
    raw_payload: str | None = None
    parse_status: str = "pending"
    parse_error: str | None = None


@dataclass(slots=True)
class ReportSection:
    title: str
    url: str
    html: str


@dataclass(slots=True)
class HoldingEvent:
    report_receipt_no: str
    ticker: str | None
    company_name: str
    effective_date: str | None
    disclosed_at: str
    delta_shares: float | None
    shares_after: float | None
    ownership_after: float | None
    change_reason: str | None
    event_type: str | None


@dataclass(slots=True)
class SnapshotRow:
    as_of_date: str
    basis_type: BasisType
    ticker: str | None
    company_name: str
    estimated_shares: float | None
    estimated_ownership: float | None
    last_delta_shares: float | None
    last_change_reason: str | None
    last_effective_date: str | None
    last_disclosed_at: str
    sector_name: str = "미분류"


@dataclass(slots=True)
class SectorSummaryRow:
    as_of_date: str
    basis_type: BasisType
    sector_name: str
    company_count: int
    ownership_sum: float
    net_direction: str


@dataclass(slots=True)
class AlertMessage:
    category: str
    ticker: str | None
    company_name: str
    effective_date: str | None
    disclosed_at: str
    message: str
