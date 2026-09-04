#!/usr/bin/env python3
"""Sync public ORCID works into the GitHub profile README."""

from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ORCID_ID = "0009-0003-7730-3202"
ORCID_PROFILE = f"https://orcid.org/{ORCID_ID}"
ORCID_WORKS_API = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"
README = Path("README.md")
STATS_SVG = Path("assets/research/orcid-stats.svg")
START = "<!-- ORCID-PUBLICATIONS:START -->"
END = "<!-- ORCID-PUBLICATIONS:END -->"

PUBLISHED_TYPES = {
    "journal-article", "conference-paper", "conference-abstract",
    "conference-poster", "book", "book-chapter", "edited-book",
    "encyclopedia-entry", "dictionary-entry", "magazine-article",
    "newspaper-article", "report", "review", "dissertation-thesis",
}

TYPE_LABELS = {
    "journal-article": "Journal Article",
    "preprint": "Preprint",
    "conference-paper": "Conference Paper",
    "conference-abstract": "Conference Abstract",
    "conference-poster": "Conference Poster",
    "book": "Book",
    "book-chapter": "Book Chapter",
    "edited-book": "Edited Book",
    "dissertation-thesis": "Thesis",
    "report": "Report",
    "review": "Review",
    "data-set": "Dataset",
    "software": "Software",
    "working-paper": "Working Paper",
    "other": "Other",
}


def fetch_json(url: str, attempts: int = 4) -> dict:
    headers = {
        "Accept": "application/json",
        "User-Agent": "smshagor-dev-profile-orcid-sync/2.0 (+https://github.com/smshagor-dev/smshagor-dev)",
    }
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Unable to fetch ORCID data after {attempts} attempts: {last_error}")


def nested_value(obj: dict | None, key: str) -> str:
    if not isinstance(obj, dict):
        return ""
    value = obj.get(key)
    if isinstance(value, dict):
        raw = value.get("value")
        return str(raw).strip() if raw is not None else ""
    return ""


def publication_date(summary: dict) -> tuple[str, tuple[int, int, int]]:
    date = summary.get("publication-date") or {}
    year = nested_value(date, "year")
    month = nested_value(date, "month")
    day = nested_value(date, "day")
    parts = [p for p in (year, month, day) if p]

    def as_int(value: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    return ("-".join(parts) if parts else "Date not listed"), (
        as_int(year), as_int(month), as_int(day)
    )


def clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value.replace("[", "\\[").replace("]", "\\]").replace("|", "\\|")


def external_ids(summary: dict, group: dict) -> list[dict]:
    ids = (summary.get("external-ids") or {}).get("external-id") or []
    return ids or (group.get("external-ids") or {}).get("external-id") or []


def work_link(summary: dict, group: dict) -> str:
    for ext in external_ids(summary, group):
        kind = str(ext.get("external-id-type") or "").lower()
        value = str(ext.get("external-id-value") or "").strip()
        if kind == "doi" and value:
            value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
            return f"https://doi.org/{value}"
    url = (summary.get("url") or {}).get("value")
    return str(url).strip() if url else ORCID_PROFILE


def choose_summary(group: dict) -> dict | None:
    summaries = group.get("work-summary") or []
    if not summaries:
        return None

    def score(item: dict) -> tuple[int, int]:
        try:
            display_index = int(item.get("display-index") or 0)
        except (TypeError, ValueError):
            display_index = 0
        try:
            modified = int(((item.get("last-modified-date") or {}).get("value") or 0))
        except (TypeError, ValueError):
            modified = 0
        return display_index, modified

    return max(summaries, key=score)


def parse_works(payload: dict) -> list[dict]:
    works: list[dict] = []
    seen: set[str] = set()
    for group in payload.get("group") or []:
        summary = choose_summary(group)
        if not summary:
            continue
        title = nested_value(summary.get("title") or {}, "title") or "Untitled work"
        work_type = str(summary.get("type") or "other").lower()
        date_text, date_key = publication_date(summary)
        journal = nested_value(summary, "journal-title")
        link = work_link(summary, group)
        dedupe_key = f"{link.lower()}::{title.lower()}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        works.append({
            "title": title,
            "type": work_type,
            "type_label": TYPE_LABELS.get(work_type, work_type.replace("-", " ").title()),
            "date": date_text,
            "date_key": date_key,
            "journal": journal,
            "link": link,
        })
    works.sort(key=lambda item: item["date_key"], reverse=True)
    return works


def render_list(items: list[dict], empty_message: str) -> str:
    if not items:
        return f"_{empty_message}_"
    lines: list[str] = []
    for index, item in enumerate(items, 1):
        title = clean_text(item["title"])
        journal = clean_text(item["journal"])
        metadata = []
        if journal:
            metadata.append(f"*{journal}*")
        metadata.append(item["date"])
        metadata.append(f"`{item['type_label']}`")
        lines.append(f"{index}. **[{title}]({item['link']})** — {' · '.join(metadata)}")
    return "\n".join(lines)


def render_stats_svg(total: int, published: int, preprints: int) -> None:
    STATS_SVG.parent.mkdir(parents=True, exist_ok=True)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="120" viewBox="0 0 1000 120" role="img" aria-label="ORCID research statistics">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0d1117"/><stop offset="1" stop-color="#111827"/></linearGradient>
  </defs>
  <rect x="1" y="1" width="998" height="118" rx="16" fill="url(#bg)" stroke="#30363d"/>
  <circle cx="54" cy="60" r="27" fill="#A6CE39"/>
  <text x="54" y="67" text-anchor="middle" fill="#fff" font-family="Arial,sans-serif" font-size="21" font-weight="700">iD</text>
  <text x="94" y="49" fill="#f0f6fc" font-family="Segoe UI,Arial,sans-serif" font-size="17" font-weight="700">ORCID</text>
  <text x="94" y="73" fill="#8b949e" font-family="Consolas,monospace" font-size="14">{html.escape(ORCID_ID)}</text>
  <line x1="350" y1="25" x2="350" y2="95" stroke="#30363d"/>
  <text x="445" y="50" text-anchor="middle" fill="#58a6ff" font-family="Segoe UI,Arial,sans-serif" font-size="28" font-weight="700">{total}</text>
  <text x="445" y="76" text-anchor="middle" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="600">PUBLIC WORKS</text>
  <line x1="540" y1="25" x2="540" y2="95" stroke="#30363d"/>
  <text x="635" y="50" text-anchor="middle" fill="#3fb950" font-family="Segoe UI,Arial,sans-serif" font-size="28" font-weight="700">{published}</text>
  <text x="635" y="76" text-anchor="middle" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="600">PUBLISHED</text>
  <line x1="730" y1="25" x2="730" y2="95" stroke="#30363d"/>
  <text x="850" y="50" text-anchor="middle" fill="#d4af37" font-family="Segoe UI,Arial,sans-serif" font-size="28" font-weight="700">{preprints}</text>
  <text x="850" y="76" text-anchor="middle" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="600">PREPRINTS</text>
</svg>'''
    STATS_SVG.write_text(svg, encoding="utf-8")


def render_block(works: list[dict]) -> str:
    preprints = [work for work in works if work["type"] == "preprint"]
    published = [work for work in works if work["type"] in PUBLISHED_TYPES]
    other = [work for work in works if work["type"] not in PUBLISHED_TYPES and work["type"] != "preprint"]
    synced = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    render_stats_svg(len(works), len(published), len(preprints))

    sections = [
        START,
        "## <code>Research & Publications</code>",
        "",
        f"<a href=\"{ORCID_PROFILE}\"><img src=\"./assets/research/orcid-stats.svg\" width=\"100%\" alt=\"ORCID research statistics: {len(works)} public works, {len(published)} published, {len(preprints)} preprints\" /></a>",
        "",
        f"> Automatically synchronized from my public [ORCID record]({ORCID_PROFILE}) every 6 hours. Last sync: **{synced}**.",
        "",
        "### Published Works",
        "",
        render_list(published, "No works currently classified by ORCID as published/formal outputs."),
        "",
        "### Preprints",
        "",
        render_list(preprints, "No public preprints currently listed on ORCID."),
    ]
    if other:
        sections.extend(["", "### Other Research Outputs", "", render_list(other, "No other public research outputs currently listed on ORCID.")])
    sections.extend(["", END])
    return "\n".join(sections)


def update_readme(block: str) -> None:
    text = README.read_text(encoding="utf-8")
    if START in text and END in text:
        pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
        updated = pattern.sub(block, text, count=1)
    else:
        anchor = "## <code>Featured Gallery</code>"
        if anchor not in text:
            anchor = "## <code>Tech Arsenal</code>"
        if anchor not in text:
            raise RuntimeError("Could not find a safe README insertion anchor.")
        updated = text.replace(anchor, block + "\n\n---\n\n" + anchor, 1)
    README.write_text(updated, encoding="utf-8")


def main() -> None:
    works = parse_works(fetch_json(ORCID_WORKS_API))
    update_readme(render_block(works))
    published = sum(work["type"] in PUBLISHED_TYPES for work in works)
    preprints = sum(work["type"] == "preprint" for work in works)
    other = len(works) - published - preprints
    print(f"ORCID sync complete: total={len(works)}, published={published}, preprints={preprints}, other={other}")


if __name__ == "__main__":
    main()
