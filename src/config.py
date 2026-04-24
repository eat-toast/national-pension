from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(slots=True)
class AppConfig:
    dart_api_key: str | None
    kakao_access_token: str | None
    kakao_web_url: str
    kakao_test_message: str
    ssl_cert_file: str | None
    dart_retries: int
    dart_timeout_seconds: float
    dart_retry_delay_seconds: float
    dart_request_delay_seconds: float
    db_path: Path
    output_dir: Path

    @classmethod
    def from_env(cls) -> "AppConfig":
        _load_env_file()
        return cls(
            dart_api_key=os.getenv("DART_API_KEY"),
            kakao_access_token=os.getenv("KAKAO_ACCESS_TOKEN"),
            kakao_web_url=os.getenv("KAKAO_WEB_URL", "https://dart.fss.or.kr"),
            kakao_test_message=os.getenv("KAKAO_TEST_MESSAGE", "[NPS Tracker] 카카오 API 연결 테스트"),
            ssl_cert_file=os.getenv("SSL_CERT_FILE") or _default_ssl_cert_file(),
            dart_retries=_parse_int(os.getenv("DART_RETRIES"), 5),
            dart_timeout_seconds=_parse_float(os.getenv("DART_TIMEOUT_SECONDS"), 20.0),
            dart_retry_delay_seconds=_parse_float(os.getenv("DART_RETRY_DELAY_SECONDS"), 1.0),
            dart_request_delay_seconds=_parse_float(os.getenv("DART_REQUEST_DELAY_SECONDS"), 0.35),
            db_path=Path(os.getenv("NPS_DB_PATH", "data/nps_portfolio.sqlite3")),
            output_dir=Path(os.getenv("NPS_OUTPUT_DIR", "output")),
        )


def _default_ssl_cert_file() -> str | None:
    for candidate in ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem"):
        if Path(candidate).exists():
            return candidate
    return None


def _parse_int(value: str | None, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_float(value: str | None, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default
