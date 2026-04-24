from __future__ import annotations

from src.analysis.industry import sector_from_industry_code
from src.collect.dart_client import DartClient
from src.db.repository import Repository


def sync_sector_map(
    repository: Repository,
    client: DartClient,
    *,
    only_missing: bool = True,
    limit: int | None = None,
    progress: bool = False,
) -> dict[str, int]:
    tickers = repository.list_event_tickers(only_missing_sector=only_missing, limit=limit)
    updated = 0
    skipped = 0
    errors = 0
    for index, row in enumerate(tickers, start=1):
        ticker = row["ticker"]
        corp_code = row["corp_code"]
        company_name = row["company_name"]
        if not ticker or not corp_code:
            skipped += 1
            if progress:
                print(f"[{index}/{len(tickers)}] skipped {ticker or '-'} {company_name or ''}: missing corp_code")
            continue
        try:
            profile = client.company_profile(corp_code)
        except Exception:
            errors += 1
            if progress:
                print(f"[{index}/{len(tickers)}] error {ticker} {company_name or ''}: company profile failed")
            continue
        sector_name = sector_from_industry_code(profile.get("induty_code"))
        repository.upsert_sector(ticker, sector_name)
        updated += 1
        if progress:
            print(f"[{index}/{len(tickers)}] updated {ticker} {company_name or ''}: {sector_name}")
    return {"candidates": len(tickers), "updated": updated, "skipped": skipped, "errors": errors}
