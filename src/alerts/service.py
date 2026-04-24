from __future__ import annotations

from src.db.repository import Repository
from src.models import AlertMessage


def build_alerts(repository: Repository, since_date: str) -> list[AlertMessage]:
    alerts: list[AlertMessage] = []
    for event in repository.list_events_since(since_date):
        previous = repository.get_previous_event(event["ticker"], event["disclosed_at"])
        current_ownership = event["ownership_after"] or 0.0
        previous_ownership = previous["ownership_after"] if previous else None

        if previous is None and current_ownership >= 0.05:
            alerts.append(
                AlertMessage(
                    category="new_5pct",
                    ticker=event["ticker"],
                    company_name=event["company_name"],
                    effective_date=event["effective_date"],
                    disclosed_at=event["disclosed_at"],
                    message=f"{event['company_name']} 신규 5% 편입 추정 ({current_ownership:.2%})",
                )
            )

        if previous_ownership is not None and previous_ownership < 0.10 <= current_ownership:
            alerts.append(
                AlertMessage(
                    category="cross_10pct",
                    ticker=event["ticker"],
                    company_name=event["company_name"],
                    effective_date=event["effective_date"],
                    disclosed_at=event["disclosed_at"],
                    message=f"{event['company_name']} 보유비율 10% 이상 도달 ({current_ownership:.2%})",
                )
            )

        if previous_ownership is not None and abs(current_ownership - previous_ownership) >= 0.009999:
            direction = "증가" if current_ownership > previous_ownership else "감소"
            alerts.append(
                AlertMessage(
                    category="ownership_change",
                    ticker=event["ticker"],
                    company_name=event["company_name"],
                    effective_date=event["effective_date"],
                    disclosed_at=event["disclosed_at"],
                    message=f"{event['company_name']} 지분율 1%p 이상 {direction} ({previous_ownership:.2%} -> {current_ownership:.2%})",
                )
            )
    return alerts
