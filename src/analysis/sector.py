from __future__ import annotations

from collections import defaultdict

from src.models import SectorSummaryRow, SnapshotRow


def summarize_sectors(rows: list[SnapshotRow]) -> list[SectorSummaryRow]:
    grouped: dict[str, dict[str, float | int]] = defaultdict(lambda: {"company_count": 0, "ownership_sum": 0.0, "delta_sum": 0.0})
    for row in rows:
        sector_name = row.sector_name or "미분류"
        grouped[sector_name]["company_count"] += 1
        grouped[sector_name]["ownership_sum"] += row.estimated_ownership or 0.0
        grouped[sector_name]["delta_sum"] += row.last_delta_shares or 0.0
    summaries: list[SectorSummaryRow] = []
    for sector_name, values in grouped.items():
        delta_sum = float(values["delta_sum"])
        if delta_sum > 0:
            direction = "순매수"
        elif delta_sum < 0:
            direction = "순매도"
        else:
            direction = "중립"
        sample_row = rows[0] if rows else None
        summaries.append(
            SectorSummaryRow(
                as_of_date=sample_row.as_of_date if sample_row else "",
                basis_type=sample_row.basis_type if sample_row else "effective_date",
                sector_name=sector_name,
                company_count=int(values["company_count"]),
                ownership_sum=float(values["ownership_sum"]),
                net_direction=direction,
            )
        )
    return sorted(summaries, key=lambda row: row.ownership_sum, reverse=True)
