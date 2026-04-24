from __future__ import annotations

from collections import defaultdict

from src.analysis.sector import summarize_sectors
from src.db.repository import Repository
from src.models import BasisType, SectorSummaryRow, SnapshotRow


def calculate_snapshot_rows(
    repository: Repository,
    as_of_date: str,
    basis_type: BasisType,
) -> tuple[list[SnapshotRow], list[SectorSummaryRow]]:
    events = repository.list_events_until(as_of_date, basis_type)
    state: dict[str, dict[str, object]] = {}
    synthetic_index = 0
    for event in events:
        key = event["ticker"] or f"__unknown__:{event['company_name']}:{synthetic_index}"
        if event["ticker"] is None:
            synthetic_index += 1
        shares_after = event["shares_after"]
        previous = state.get(key)
        if shares_after is None and previous:
            base = previous.get("estimated_shares")
            if base is not None and event["delta_shares"] is not None:
                shares_after = float(base) + float(event["delta_shares"])
        state[key] = {
            "ticker": event["ticker"],
            "company_name": event["company_name"],
            "estimated_shares": shares_after,
            "estimated_ownership": event["ownership_after"],
            "last_delta_shares": event["delta_shares"],
            "last_change_reason": event["change_reason"],
            "last_effective_date": event["effective_date"],
            "last_disclosed_at": event["disclosed_at"],
            "sector_name": event["sector_name"] or "미분류",
        }

    rows = [
        SnapshotRow(
            as_of_date=as_of_date,
            basis_type=basis_type,
            ticker=value["ticker"],
            company_name=str(value["company_name"]),
            estimated_shares=value["estimated_shares"],
            estimated_ownership=value["estimated_ownership"],
            last_delta_shares=value["last_delta_shares"],
            last_change_reason=value["last_change_reason"],
            last_effective_date=value["last_effective_date"],
            last_disclosed_at=str(value["last_disclosed_at"]),
            sector_name=str(value["sector_name"]),
        )
        for value in sorted(
            state.values(),
            key=lambda item: (
                item["estimated_ownership"] is not None,
                item["estimated_ownership"] or -1.0,
                item["company_name"],
            ),
            reverse=True,
        )
    ]
    return rows, summarize_sectors(rows)


def build_snapshot(repository: Repository, as_of_date: str, basis_type: BasisType) -> tuple[int, list[SnapshotRow], list[SectorSummaryRow]]:
    rows, sector_rows = calculate_snapshot_rows(repository, as_of_date, basis_type)
    run_id = repository.save_snapshot(as_of_date, basis_type, rows)
    return run_id, rows, sector_rows
