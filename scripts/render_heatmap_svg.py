#!/usr/bin/env python3
"""Render data/contributions.json into a custom GitHub-profile SVG heatmap."""

from __future__ import annotations

import argparse
import html
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

COLORS = {
    0: "#161b22",
    1: "#3b3118",
    2: "#705b1d",
    3: "#a98227",
    4: "#D4AF37",
}
BG = "#0d0d0d"
BORDER = "#3b3218"
TEXT = "#c9d1d9"
MUTED = "#7d8590"
GOLD = "#D4AF37"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render contribution heatmap SVG.")
    parser.add_argument("-i", "--input", type=Path, default=Path("data/contributions.json"))
    parser.add_argument("-o", "--output", type=Path, default=Path("contrib-heatmap.svg"))
    return parser.parse_args()


def fmt_int(value: int) -> str:
    return f"{value:,}"


def sunday_on_or_before(day: date) -> date:
    return day - timedelta(days=(day.weekday() + 1) % 7)


def render(payload: dict[str, Any]) -> str:
    width, height = 860, 236
    left, top = 48, 104
    cell, gap = 10, 3
    step = cell + gap

    days = payload.get("days", [])
    by_date = {
        date.fromisoformat(item["date"]): item
        for item in days
        if item.get("date")
    }

    if days:
        first = min(by_date)
        last = max(by_date)
        grid_start = sunday_on_or_before(first)
    else:
        last = date.today()
        first = last - timedelta(days=364)
        grid_start = sunday_on_or_before(first)

    metrics = payload.get("metrics", {})
    total = int(metrics.get("total_contributions", 0) or 0)
    current = int(metrics.get("current_streak", 0) or 0)
    longest = int(metrics.get("longest_streak", 0) or 0)
    best = metrics.get("best_day") or {}
    best_count = int(best.get("count", 0) or 0)

    cells = []
    max_weeks = 53
    for day, item in sorted(by_date.items()):
        delta = (day - grid_start).days
        if delta < 0:
            continue
        week = delta // 7
        row = delta % 7
        if week >= max_weeks:
            continue
        x = left + week * step
        y = top + row * step
        level = max(0, min(4, int(item.get("level", 0) or 0)))
        count = int(item.get("count", 0) or 0)
        title = html.escape(f"{day.isoformat()}: {count} contribution{'s' if count != 1 else ''}")
        cells.append(
            f'<g><title>{title}</title><rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{COLORS[level]}"/></g>'
        )

    month_labels = []
    cursor = date(grid_start.year, grid_start.month, 1)
    if cursor < grid_start:
        cursor = date(
            cursor.year + (1 if cursor.month == 12 else 0),
            1 if cursor.month == 12 else cursor.month + 1,
            1,
        )

    seen_x = -999
    while cursor <= last:
        week = (cursor - grid_start).days // 7
        x = left + week * step
        if 0 <= week < max_weeks and x - seen_x > 28:
            month_labels.append(
                f'<text x="{x}" y="92" class="month">{cursor.strftime("%b")}</text>'
            )
            seen_x = x
        cursor = date(
            cursor.year + (1 if cursor.month == 12 else 0),
            1 if cursor.month == 12 else cursor.month + 1,
            1,
        )

    weekdays = [
        ("Mon", top + step + 8),
        ("Wed", top + 3 * step + 8),
        ("Fri", top + 5 * step + 8),
    ]
    weekday_nodes = "".join(
        f'<text x="16" y="{y}" class="weekday">{label}</text>'
        for label, y in weekdays
    )

    legend_x = 724
    legend = [f'<text x="{legend_x}" y="214" class="muted">Less</text>']
    for i in range(5):
        legend.append(
            f'<rect x="{legend_x + 32 + i*16}" y="205" width="10" height="10" rx="2" fill="{COLORS[i]}"/>'
        )
    legend.append(f'<text x="{legend_x + 116}" y="214" class="muted">More</text>')

    pending = ""
    if not days:
        pending = (
            '<text x="430" y="151" text-anchor="middle" class="pending">'
            'Heatmap pending first workflow run</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">GitHub contribution heatmap</title>
<desc id="desc">Trailing GitHub contribution activity for {html.escape(payload.get("username", "smshagor-dev"))}.</desc>
<style>
  .title{{fill:{GOLD};font:600 16px "SFMono-Regular",Consolas,monospace}}
  .stat{{fill:{TEXT};font:11px "SFMono-Regular",Consolas,monospace}}
  .muted,.month,.weekday{{fill:{MUTED};font:9px "SFMono-Regular",Consolas,monospace}}
  .pending{{fill:{MUTED};font:12px "SFMono-Regular",Consolas,monospace}}
</style>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="18" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>
<text x="24" y="32" class="title">CONTRIBUTION SIGNAL</text>
<text x="24" y="57" class="stat">TOTAL <tspan fill="{GOLD}">{fmt_int(total)}</tspan></text>
<text x="205" y="57" class="stat">CURRENT <tspan fill="{GOLD}">{current}d</tspan></text>
<text x="386" y="57" class="stat">LONGEST <tspan fill="{GOLD}">{longest}d</tspan></text>
<text x="567" y="57" class="stat">BEST DAY <tspan fill="{GOLD}">{best_count}</tspan></text>
{''.join(month_labels)}
{weekday_nodes}
{''.join(cells)}
{pending}
{''.join(legend)}
</svg>'''


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.write_text(render(payload), encoding="utf-8")
    print(f"Generated: {args.output}")


if __name__ == "__main__":
    main()
