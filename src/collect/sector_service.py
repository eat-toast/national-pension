from __future__ import annotations

from src.analysis.industry import sector_from_industry_code
from src.collect.dart_client import DartClient
from src.db.repository import Repository


def sync_sector_map(repository: Repository, client: DartClient) -> dict[str, int]:
    tickers = repository.list_event_tickers()
    updated = 0
    skipped = 0
    errors = 0
    for row in tickers:
        ticker = row["ticker"]
        corp_code = row["corp_code"]
        if not ticker or not corp_code:
            skipped += 1
            continue
        try:
            profile = client.company_profile(corp_code)
        except Exception:
            errors += 1
            continue
        sector_name = sector_from_industry_code(profile.get("induty_code"))
        repository.upsert_sector(ticker, sector_name)
        updated += 1
    return {"candidates": len(tickers), "updated": updated, "skipped": skipped, "errors": errors}
