from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from src.dashboard.baseline import BaselineHolding, normalize_company_name
from src.models import BasisType


PeriodType = Literal["month", "quarter"]


@dataclass(slots=True)
class SectorTrendRow:
    period_type: PeriodType
    period: str
    sector_name: str
    event_count: int
    company_count: int
    increase_count: int
    decrease_count: int
    net_delta_shares: float
    abs_delta_shares: float
    net_ownership_delta: float
    abs_ownership_delta: float


def build_sector_trends(
    event_rows: list[dict[str, Any]],
    baseline_rows: list[BaselineHolding],
    start_date: str,
    end_date: str,
    basis_type: BasisType,
) -> dict[str, list[SectorTrendRow]]:
    enriched = _with_ownership_deltas(event_rows, baseline_rows)
    filtered = [
        row
        for row in enriched
        if start_date <= _basis_date(row, basis_type) <= end_date
    ]
    return {
        "monthly": _group_sector_trends(filtered, "month", basis_type),
        "quarterly": _group_sector_trends(filtered, "quarter", basis_type),
    }


def _group_sector_trends(
    event_rows: list[dict[str, Any]],
    period_type: PeriodType,
    basis_type: BasisType,
) -> list[SectorTrendRow]:
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "event_count": 0,
            "companies": set(),
            "increase_count": 0,
            "decrease_count": 0,
            "net_delta_shares": 0.0,
            "abs_delta_shares": 0.0,
            "net_ownership_delta": 0.0,
            "abs_ownership_delta": 0.0,
        }
    )
    for row in event_rows:
        date = _basis_date(row, basis_type)
        if not date:
            continue
        period = _period_key(date, period_type)
        sector_name = str(row.get("sector_name") or "미분류")
        target = grouped[(period, sector_name)]
        target["event_count"] += 1
        target["companies"].add(str(row.get("ticker") or row.get("company_name") or ""))
        delta_shares = _as_float(row.get("delta_shares")) or 0.0
        if delta_shares > 0:
            target["increase_count"] += 1
        elif delta_shares < 0:
            target["decrease_count"] += 1
        target["net_delta_shares"] += delta_shares
        target["abs_delta_shares"] += abs(delta_shares)
        ownership_delta = _as_float(row.get("ownership_delta")) or 0.0
        target["net_ownership_delta"] += ownership_delta
        target["abs_ownership_delta"] += abs(ownership_delta)

    rows: list[SectorTrendRow] = []
    for (period, sector_name), values in grouped.items():
        rows.append(
            SectorTrendRow(
                period_type=period_type,
                period=period,
                sector_name=sector_name,
                event_count=int(values["event_count"]),
                company_count=len(values["companies"]),
                increase_count=int(values["increase_count"]),
                decrease_count=int(values["decrease_count"]),
                net_delta_shares=float(values["net_delta_shares"]),
                abs_delta_shares=float(values["abs_delta_shares"]),
                net_ownership_delta=float(values["net_ownership_delta"]),
                abs_ownership_delta=float(values["abs_ownership_delta"]),
            )
        )
    return sorted(rows, key=lambda row: (row.period, row.sector_name))


def _with_ownership_deltas(
    event_rows: list[dict[str, Any]],
    baseline_rows: list[BaselineHolding],
) -> list[dict[str, Any]]:
    baseline_by_name = {normalize_company_name(row.company_name): row.ownership for row in baseline_rows}
    previous_by_key: dict[str, float] = {}
    enriched: list[dict[str, Any]] = []
    for row in sorted(
        event_rows,
        key=lambda item: (
            str(item.get("disclosed_at") or ""),
            str(item.get("effective_date") or ""),
            int(item.get("id") or 0),
        ),
    ):
        copied = dict(row)
        key = str(row.get("ticker") or normalize_company_name(str(row.get("company_name") or "")))
        ownership_after = _as_float(row.get("ownership_after"))
        previous = previous_by_key.get(key)
        if previous is None:
            previous = baseline_by_name.get(normalize_company_name(str(row.get("company_name") or "")))
        copied["ownership_delta"] = (
            ownership_after - previous
            if ownership_after is not None and previous is not None
            else None
        )
        if ownership_after is not None:
            previous_by_key[key] = ownership_after
        enriched.append(copied)
    return enriched


def _basis_date(row: dict[str, Any], basis_type: BasisType) -> str:
    if basis_type == "effective_date":
        return str(row.get("effective_date") or row.get("disclosed_at") or "")
    return str(row.get("disclosed_at") or "")


def _period_key(date: str, period_type: PeriodType) -> str:
    if period_type == "month":
        return date[:7]
    month = int(date[5:7])
    quarter = ((month - 1) // 3) + 1
    return f"{date[:4]}-Q{quarter}"


def _as_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
