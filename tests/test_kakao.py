from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from src.alerts.kakao import send_kakao_text_message


class _FakeResponse:
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps({"result_code": 0}).encode("utf-8")


class KakaoAlertTest(unittest.TestCase):
    @patch("src.alerts.kakao.urlopen", return_value=_FakeResponse())
    def test_send_kakao_text_message(self, mocked_urlopen) -> None:
        payload = send_kakao_text_message("token-value", "테스트 메시지", "https://dart.fss.or.kr")
        self.assertEqual(payload["result_code"], 0)
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://kapi.kakao.com/v2/api/talk/memo/default/send")
        self.assertEqual(request.headers["Authorization"], "Bearer token-value")


if __name__ == "__main__":
    unittest.main()
