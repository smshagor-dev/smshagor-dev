#!/usr/bin/env python3
"""Fetch public GitHub contribution-calendar data without an API token."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_USERNAME = "smshagor-dev"
COUNT_RE = re.compile(r"([\d,]+)\s+contributions?", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch GitHub public contribution data.")
    parser.add_argument(
        "--username",
        default=os.getenv("PROFILE_GITHUB_USERNAME", DEFAULT_USERNAME),
        help=f"GitHub username (default: {DEFAULT_USERNAME})",
    )
    parser.add_argument(
        "--days", type=int, default=365,
        help="Trailing number of calendar days to request (default: 365)",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("data/contributions.json"),
        help="JSON output path",
    )
    return parser.parse_args()


def http_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": "smshagor-dev-profile-art/1.0 (+https://github.com/smshagor-dev)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


def contribution_count(cell: Any, tooltips: dict[str, str]) -> int:
    direct = cell.get("data-count")
    if direct and str(direct).isdigit():
        return int(direct)

    labels = [
        cell.get("aria-label", ""),
        cell.get("data-content", ""),
        tooltips.get(cell.get("id", ""), ""),
    ]
    for label in labels:
        if not label:
            continue
        if "No contributions" in label:
            return 0
        match = COUNT_RE.search(label)
        if match:
            return int(match.group(1).replace(",", ""))

    return 0


def parse_calendar(html_text: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    tooltips = {
        tip.get("for"): tip.get_text(" ", strip=True)
        for tip in soup.find_all("tool-tip")
        if tip.get("for")
    }

    cells = soup.select("[data-date][data-level]")
    days: dict[str, dict[str, Any]] = {}
    for cell in cells:
        day = cell.get("data-date")
        if not day or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            continue
        try:
            level = int(cell.get("data-level", 0))
        except (TypeError, ValueError):
            level = 0
        level = max(0, min(4, level))
        days[day] = {
            "date": day,
            "count": contribution_count(cell, tooltips),
            "level": level,
        }

    return [days[key] for key in sorted(days)]


def compute_metrics(days: list[dict[str, Any]], requested_end: date) -> dict[str, Any]:
    counts = {date.fromisoformat(item["date"]): int(item["count"]) for item in days}
    total = sum(counts.values())

    best_date = None
    best_count = 0
    for day, count in counts.items():
        if count > best_count:
            best_date, best_count = day, count

    longest = 0
    run = 0
    previous = None
    for day in sorted(counts):
        count = counts[day]
        if previous is None or day == previous + timedelta(days=1):
            run = run + 1 if count > 0 else 0
        else:
            run = 1 if count > 0 else 0
        longest = max(longest, run)
        previous = day

    cursor = requested_end
    if counts.get(cursor, 0) == 0:
        cursor -= timedelta(days=1)

    current = 0
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)

    return {
        "total_contributions": total,
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {
            "date": best_date.isoformat() if best_date else None,
            "count": best_count,
        },
    }


def main() -> None:
    args = parse_args()

    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", args.username):
        raise ValueError("Invalid GitHub username.")
    if not 30 <= args.days <= 366:
        raise ValueError("--days must be between 30 and 366.")

    end = date.today()
    start = end - timedelta(days=args.days - 1)
    url = f"https://github.com/users/{args.username}/contributions"

    response = http_session().get(
        url,
        params={"from": start.isoformat(), "to": end.isoformat()},
        timeout=(8, 25),
    )
    response.raise_for_status()

    days = parse_calendar(response.text)
    if len(days) < min(300, args.days - 10):
        raise RuntimeError(
            f"Contribution calendar parse returned only {len(days)} days. "
            "GitHub markup may have changed; refusing to overwrite good data."
        )

    metrics = compute_metrics(days, end)
    payload = {
        "username": args.username,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "metrics": metrics,
        "days": days,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temp.replace(args.output)

    print(
        f"Saved {len(days)} days / {metrics['total_contributions']} contributions "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
