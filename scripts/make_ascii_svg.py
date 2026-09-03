#!/usr/bin/env python3
"""Render source-prepped.png as an animated terminal-style ASCII portrait SVG."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

RAMP = " .`:-=+*cs#%@"
GOLD = "#D4AF37"
BG = "#0d0d0d"
BORDER = "#3b3218"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an animated ASCII portrait SVG.")
    parser.add_argument(
        "-i", "--input", type=Path, default=Path("source-prepped.png"),
        help="Prepared transparent portrait PNG"
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("hxni-ascii.svg"),
        help="Output SVG path"
    )
    parser.add_argument("--cols", type=int, default=52, help="ASCII columns")
    parser.add_argument("--rows", type=int, default=43, help="ASCII rows")
    return parser.parse_args()


def brightness_to_char(value: int) -> str:
    idx = round((value / 255) * (len(RAMP) - 1))
    return RAMP[max(0, min(idx, len(RAMP) - 1))]


def make_lines(image: Image.Image, cols: int, rows: int) -> list[str]:
    rgba = image.convert("RGBA").resize((cols, rows), Image.Resampling.LANCZOS)
    arr = np.array(rgba)
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    gray = np.dot(rgb[..., :3], [0.2126, 0.7152, 0.0722]).astype(np.uint8)

    lines: list[str] = []
    for y in range(rows):
        chars = []
        for x in range(cols):
            if alpha[y, x] < 24:
                chars.append(" ")
                continue
            chars.append(brightness_to_char(255 - int(gray[y, x])))
        lines.append("".join(chars).rstrip())
    return lines


def render_svg(lines: list[str], output: Path) -> None:
    width, height = 370, 520
    x0, y0 = 24, 72
    line_h = 9.6
    font_size = 7.6
    reveal_width = 320

    clip_defs = []
    text_nodes = []
    css_delays = []

    for i, line in enumerate(lines):
        y = y0 + i * line_h
        delay = i * 0.045
        clip_defs.append(
            f'<clipPath id="wipe{i}"><rect x="{x0}" y="{y-line_h+2:.1f}" width="0" height="{line_h+1:.1f}">'
            f'<animate attributeName="width" from="0" to="{reveal_width}" dur="0.65s" begin="{delay:.3f}s" fill="freeze" />'
            '</rect></clipPath>'
        )
        text_nodes.append(
            f'<text class="ascii line{i}" x="{x0}" y="{y:.1f}" clip-path="url(#wipe{i})">{html.escape(line)}</text>'
        )
        css_delays.append(f".line{i}{{animation-delay:{delay:.3f}s}}")

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">Animated ASCII portrait</title>
<desc id="desc">Gold terminal ASCII portrait of Shahanur Islam Shagor.</desc>
<defs>
  <filter id="goldGlow" x="-30%" y="-30%" width="160%" height="160%">
    <feGaussianBlur stdDeviation="1.25" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  {''.join(clip_defs)}
</defs>
<style>
  .ascii {{
    fill: {GOLD};
    font: {font_size}px "SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
    white-space: pre;
    opacity: 0;
    animation: fin .55s ease forwards;
  }}
  {''.join(css_delays)}
  .cursor {{ animation: blink 1s step-end infinite; }}
  @keyframes fin {{ from {{ opacity:0; transform:translateY(2px) }} to {{ opacity:.96; transform:translateY(0) }} }}
  @keyframes blink {{ 50% {{ opacity:0 }} }}
</style>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="18" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>
<circle cx="24" cy="25" r="5" fill="#ff5f57"/>
<circle cx="42" cy="25" r="5" fill="#febc2e"/>
<circle cx="60" cy="25" r="5" fill="#28c840"/>
<text x="185" y="30" text-anchor="middle" fill="#8b8b8b" font-size="11" font-family="monospace">portrait://cipher-stack</text>
<line x1="18" y1="47" x2="352" y2="47" stroke="#252525"/>
<g filter="url(#goldGlow)">{''.join(text_nodes)}</g>
<text x="24" y="500" fill="#777" font-size="10" font-family="monospace">$ render --identity shagor <tspan class="cursor" fill="{GOLD}">▋</tspan></text>
</svg>'''

    output.write_text(svg, encoding="utf-8")
    print(f"Generated: {output}")


def main() -> None:
    args = parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(
            f"{args.input} not found. Run: python scripts/prep_photo.py hero.png"
        )
    if args.cols < 24 or args.rows < 20:
        raise ValueError("ASCII grid is too small.")

    image = Image.open(args.input).convert("RGBA")
    rgb = Image.new("RGB", image.size, (13, 13, 13))
    rgb.paste(image.convert("RGB"), mask=image.getchannel("A"))
    rgb = ImageEnhance.Contrast(rgb).enhance(1.12)
    rgba = rgb.convert("RGBA")
    rgba.putalpha(image.getchannel("A"))

    lines = make_lines(rgba, args.cols, args.rows)
    render_svg(lines, args.output)


if __name__ == "__main__":
    main()
