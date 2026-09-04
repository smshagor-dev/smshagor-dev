#!/usr/bin/env python3
"""Sync public ORCID works into the GitHub profile README."""

from __future__ import annotations

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
START = "<!-- ORCID-PUBLICATIONS:START -->"
END = "<!-- ORCID-PUBLICATIONS:END -->"

PUBLISHED_TYPES = {
    "journal-article",
    "conference-paper",
    "conference-abstract",
    "conference-poster",
    "book",
    "book-chapter",
    "edited-book",
    "encyclopedia-entry",
    "dictionary-entry",
    "magazine-article",
    "newspaper-article",
    "report",
    "review",
    "dissertation-thesis",
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
        "User-Agent": "smshagor-dev-profile-orcid-sync/1.0 (+https://github.com/smshagor-dev/smshagor-dev)",
    }
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=30) as response:
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
    display = "-".join(parts) if parts else "Date not listed"

    def as_int(value: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    return display, (as_int(year), as_int(month), as_int(day))


def clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value.replace("[", "\\[").replace("]", "\\]").replace("|", "\\|")


def external_ids(summary: dict, group: dict) -> list[dict]:
    ids = (summary.get("external-ids") or {}).get("external-id") or []
    if ids:
        return ids
    return (group.get("external-ids") or {}).get("external-id") or []


def work_link(summary: dict, group: dict) -> str:
    for ext in external_ids(summary, group):
        kind = str(ext.get("external-id-type") or "").lower()
        value = str(ext.get("external-id-value") or "").strip()
        if kind == "doi" and value:
            value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
            return f"https://doi.org/{value}"

    url = (summary.get("url") or {}).get("value")
    if url:
        return str(url).strip()
    return ORCID_PROFILE


def choose_summary(group: dict) -> dict | None:
    summaries = group.get("work-summary") or []
    if not summaries:
        return None

    def score(item: dict) -> tuple[int, int]:
        try:
            display_index = int(item.get("display-index") or 0)
        except (TypeError, ValueError):
            display_index = 0
        modified = ((item.get("last-modified-date") or {}).get("value") or 0)
        try:
            modified_int = int(modified)
        except (TypeError, ValueError):
            modified_int = 0
        return display_index, modified_int

    return max(summaries, key=score)


def parse_works(payload: dict) -> list[dict]:
    works: list[dict] = []
    seen: set[str] = set()

    for group in payload.get("group") or []:
        summary = choose_summary(group)
        if not summary:
            continue

        title_obj = summary.get("title") or {}
        title = nested_value(title_obj, "title") or "Untitled work"
        work_type = str(summary.get("type") or "other").lower()
        date_text, date_key = publication_date(summary)
        journal = nested_value(summary, "journal-title")
        link = work_link(summary, group)

        dedupe_key = f"{link.lower()}::{title.lower()}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        works.append(
            {
                "title": title,
                "type": work_type,
                "type_label": TYPE_LABELS.get(work_type, work_type.replace("-", " ").title()),
                "date": date_text,
                "date_key": date_key,
                "journal": journal,
                "link": link,
            }
        )

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
        if item["date"]:
            metadata.append(item["date"])
        metadata.append(f"`{item['type_label']}`")
        suffix = " · ".join(metadata)
        lines.append(f"{index}. **[{title}]({item['link']})** — {suffix}")
    return "\n".join(lines)


def render_block(works: list[dict]) -> str:
    preprints = [work for work in works if work["type"] == "preprint"]
    published = [work for work in works if work["type"] in PUBLISHED_TYPES]
    other = [work for work in works if work["type"] not in PUBLISHED_TYPES and work["type"] != "preprint"]

    synced = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    sections = [
        START,
        "## <code>Research & Publications</code>",
        "",
        "<p align=\"left\">",
        f"  <a href=\"{ORCID_PROFILE}\"><img src=\"https://img.shields.io/badge/ORCID-{ORCID_ID}-A6CE39?style=for-the-badge&logo=orcid&logoColor=white\" alt=\"ORCID {ORCID_ID}\" /></a>",
        f"  <img src=\"https://img.shields.io/badge/Public%20Works-{len(works)}-2f81f7?style=for-the-badge\" alt=\"{len(works)} public ORCID works\" />",
        f"  <img src=\"https://img.shields.io/badge/Published-{len(published)}-238636?style=for-the-badge\" alt=\"{len(published)} published works\" />",
        f"  <img src=\"https://img.shields.io/badge/Preprints-{len(preprints)}-bf8700?style=for-the-badge\" alt=\"{len(preprints)} preprints\" />",
        "</p>",
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
        sections.extend(
            [
                "",
                "### Other Research Outputs",
                "",
                render_list(other, "No other public research outputs currently listed on ORCID."),
            ]
        )

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
    payload = fetch_json(ORCID_WORKS_API)
    works = parse_works(payload)
    update_readme(render_block(works))
    published = sum(work["type"] in PUBLISHED_TYPES for work in works)
    preprints = sum(work["type"] == "preprint" for work in works)
    other = len(works) - published - preprints
    print(f"ORCID sync complete: total={len(works)}, published={published}, preprints={preprints}, other={other}")


if __name__ == "__main__":
    main()
