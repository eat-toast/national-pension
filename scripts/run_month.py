#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MonthRange:
    month: str
    start_date: str
    end_date: str


@dataclass(frozen=True)
class Step:
    label: str
    command: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run NPS report sync, snapshot build, and XLSX export for one month.",
    )
    parser.add_argument("month", help="Target month in YYYY-MM format, e.g. 2025-06")
    parser.add_argument(
        "--basis",
        choices=("disclosure_date", "effective_date"),
        default="disclosure_date",
        help="Snapshot/export basis. Defaults to disclosure_date.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=60,
        help="Print a progress heartbeat while a long step is still running. Defaults to 60.",
    )
    return parser.parse_args()


def month_range(value: str) -> MonthRange:
    try:
        year_text, month_text = value.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        if len(year_text) != 4 or len(month_text) != 2:
            raise ValueError
        last_day = calendar.monthrange(year, month)[1]
    except ValueError as exc:
        raise SystemExit("month must be in YYYY-MM format, e.g. 2025-06") from exc
    return MonthRange(value, f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}")


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_elapsed(seconds: float) -> str:
    total_seconds = int(seconds)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def display_command(command: list[str]) -> str:
    display = ["python3" if part == sys.executable else part for part in command]
    return " ".join(display)


def run_step(step: Step, dry_run: bool, heartbeat_seconds: int) -> None:
    print(f"\n[{now_text()}] START {step.label}", flush=True)
    print("+ " + display_command(step.command), flush=True)
    if dry_run:
        print(f"[{now_text()}] DRY-RUN {step.label}", flush=True)
        return
    started_at = time.monotonic()
    process = subprocess.Popen(step.command)
    next_heartbeat_at = started_at + max(heartbeat_seconds, 1)
    while True:
        return_code = process.poll()
        if return_code is not None:
            elapsed = format_elapsed(time.monotonic() - started_at)
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, step.command)
            print(f"[{now_text()}] DONE  {step.label} ({elapsed})", flush=True)
            return
        if time.monotonic() >= next_heartbeat_at:
            elapsed = format_elapsed(time.monotonic() - started_at)
            print(f"[{now_text()}] ... still running {step.label} ({elapsed} elapsed)", flush=True)
            next_heartbeat_at += max(heartbeat_seconds, 1)
        time.sleep(1)


def main() -> int:
    args = parse_args()
    dates = month_range(args.month)
    steps = [
        Step(
            "1/3 collect DART reports",
            [
                sys.executable,
                "-m",
                "src.cli.main",
                "sync-reports",
                "--from",
                dates.start_date,
                "--to",
                dates.end_date,
            ],
        ),
        Step(
            "2/3 build DB snapshot",
            [
                sys.executable,
                "-m",
                "src.cli.main",
                "build-snapshot",
                "--date",
                dates.end_date,
                "--basis",
                args.basis,
            ],
        ),
        Step(
            "3/3 export Excel",
            [
                sys.executable,
                "-m",
                "src.cli.main",
                "export-xlsx",
                "--date",
                dates.end_date,
                "--basis",
                args.basis,
            ],
        ),
    ]
    print("=" * 72, flush=True)
    print(f"[{now_text()}] MONTH {dates.month}: {dates.start_date} to {dates.end_date} ({args.basis})", flush=True)
    print("=" * 72, flush=True)
    started_at = time.monotonic()
    for step in steps:
        run_step(step, args.dry_run, args.heartbeat_seconds)
    print(
        f"\n[{now_text()}] MONTH DONE {dates.month} ({format_elapsed(time.monotonic() - started_at)})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
