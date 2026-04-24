from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.models import AlertMessage


def send_kakao_alerts(access_token: str, alerts: list[AlertMessage], web_url: str = "https://dart.fss.or.kr") -> None:
    endpoint = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    for alert in alerts:
        template_object = json.dumps(
            {
                "object_type": "text",
                "text": alert.message,
                "link": {
                    "web_url": web_url,
                    "mobile_web_url": web_url,
                },
            },
            ensure_ascii=False,
        )
        request = Request(
            endpoint,
            data=urlencode({"template_object": template_object}).encode("utf-8"),
            headers={"Authorization": f"Bearer {access_token}"},
            method="POST",
        )
        with urlopen(request) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
            if payload.get("result_code") not in (0, None):
                raise RuntimeError(f"Kakao alert failed: {payload}")


def send_kakao_text_message(access_token: str, text: str, web_url: str = "https://dart.fss.or.kr") -> dict[str, object]:
    endpoint = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    template_object = json.dumps(
        {
            "object_type": "text",
            "text": text,
            "link": {
                "web_url": web_url,
                "mobile_web_url": web_url,
            },
        },
        ensure_ascii=False,
    )
    request = Request(
        endpoint,
        data=urlencode({"template_object": template_object}).encode("utf-8"),
        headers={"Authorization": f"Bearer {access_token}"},
        method="POST",
    )
    with urlopen(request) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
        if payload.get("result_code") not in (0, None):
            raise RuntimeError(f"Kakao test message failed: {payload}")
        return payload
