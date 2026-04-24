#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run monthly NPS sync/snapshot/export jobs for a full or partial year.",
    )
    parser.add_argument("year", type=int, help="Target year, e.g. 2025")
    parser.add_argument("--from-month", type=int, default=1, help="First month to run. Defaults to 1.")
    parser.add_argument("--to-month", type=int, default=12, help="Last month to run. Defaults to 12.")
    parser.add_argument(
        "--basis",
        choices=("disclosure_date", "effective_date"),
        default="disclosure_date",
        help="Snapshot/export basis. Defaults to disclosure_date.",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=60,
        help="Pass-through heartbeat interval for each monthly job. Defaults to 60.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    return parser.parse_args()


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


def validate_months(from_month: int, to_month: int) -> None:
    if not 1 <= from_month <= 12:
        raise SystemExit("--from-month must be between 1 and 12")
    if not 1 <= to_month <= 12:
        raise SystemExit("--to-month must be between 1 and 12")
    if from_month > to_month:
        raise SystemExit("--from-month must be less than or equal to --to-month")


def main() -> int:
    args = parse_args()
    validate_months(args.from_month, args.to_month)

    script_dir = Path(__file__).resolve().parent
    run_month = script_dir / "run_month.py"
    months = [f"{args.year:04d}-{month:02d}" for month in range(args.from_month, args.to_month + 1)]

    print("=" * 72, flush=True)
    print(f"[{now_text()}] YEAR START {args.year} ({months[0]} to {months[-1]}, {args.basis})", flush=True)
    print("=" * 72, flush=True)

    started_at = time.monotonic()
    for index, month in enumerate(months, start=1):
        print("\n" + "#" * 72, flush=True)
        print(f"[{now_text()}] MONTH {index}/{len(months)}: {month}", flush=True)
        print("#" * 72, flush=True)
        command = [
            sys.executable,
            str(run_month),
            month,
            "--basis",
            args.basis,
            "--heartbeat-seconds",
            str(args.heartbeat_seconds),
        ]
        if args.dry_run:
            command.append("--dry-run")
        subprocess.run(command, check=True)

    print("\n" + "=" * 72, flush=True)
    print(f"[{now_text()}] YEAR DONE {args.year} ({format_elapsed(time.monotonic() - started_at)})", flush=True)
    print("=" * 72, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
