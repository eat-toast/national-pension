from __future__ import annotations

import unittest
from http.client import RemoteDisconnected
from unittest.mock import patch

from src.collect.dart_client import DartClient


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class DartClientTest(unittest.TestCase):
    @patch("src.collect.dart_client.time.sleep")
    @patch("src.collect.dart_client.urlopen")
    def test_fetch_retries_after_remote_disconnect(self, mocked_urlopen, mocked_sleep) -> None:
        mocked_urlopen.side_effect = [
            RemoteDisconnected("closed"),
            _FakeResponse(b"ok"),
        ]
        client = DartClient("key", retries=2, request_delay_seconds=0, retry_delay_seconds=0.1)

        self.assertEqual(client.fetch_text("https://example.test"), "ok")
        self.assertEqual(mocked_urlopen.call_count, 2)
        mocked_sleep.assert_called_once_with(0.1)

    @patch("src.collect.dart_client.urlopen", return_value=_FakeResponse(b"ok"))
    def test_fetch_uses_browser_like_headers(self, mocked_urlopen) -> None:
        client = DartClient("key", request_delay_seconds=0)

        client.fetch_text("https://example.test")

        request = mocked_urlopen.call_args.args[0]
        self.assertIn("Mozilla/5.0", request.headers["User-agent"])
        self.assertEqual(request.headers["Connection"], "close")
        self.assertEqual(request.headers["Referer"], "https://dart.fss.or.kr/")


if __name__ == "__main__":
    unittest.main()
