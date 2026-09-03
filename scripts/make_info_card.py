#!/usr/bin/env python3
"""Generate the matching animated neofetch-style profile information card."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

GOLD = "#D4AF37"
SILVER = "#c9d1d9"
MUTED = "#7d8590"
BG = "#0d0d0d"
BORDER = "#3b3218"

INFO = [
    ("OS", "Linux · Windows · Edge"),
    ("Host", "smshagor-dev"),
    ("Role", "Full-Stack + AI / Autonomous Systems"),
    ("Languages", "TypeScript · Python · C++20 · Go · PHP"),
    ("Web", "Next.js · React · Node.js · Laravel"),
    ("AI", "PyTorch · TensorFlow · OpenCV · ONNX"),
    ("Vision", "YOLOv8 · real-time perception"),
    ("Robotics", "ESKF · VIO · UWB/TDOA · LiDAR"),
    ("Edge", "Jetson · Raspberry Pi · ESP32 · ROS"),
    ("Data", "PostgreSQL · MySQL · MongoDB · Redis"),
    ("Security", "V2X · ML-KEM · ZKP · mTLS"),
    ("Infra", "Docker · Nginx · CI/CD · AWS · GCP"),
    ("Portfolio", "smsagor.com"),
    ("GitHub", "github.com/smshagor-dev"),
    ("Location", "Voronezh, Russia · UTC+3"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate info-card.svg")
    parser.add_argument("-o", "--output", type=Path, default=Path("info-card.svg"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    width, height = 490, 520
    start_y, line_h = 84, 27

    lines = []
    css = []
    for i, (key, value) in enumerate(INFO):
        y = start_y + i * line_h
        delay = 0.10 + i * 0.075
        css.append(f".l{i}{{animation-delay:{delay:.3f}s}}")
        lines.append(
            f'<g class="row l{i}">'
            f'<text x="28" y="{y}" class="key">{html.escape(key)}</text>'
            f'<text x="126" y="{y}" class="value">{html.escape(value)}</text>'
            '</g>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">The Cipher Stack</title>
<desc id="desc">Animated terminal-style technical profile of Shahanur Islam Shagor.</desc>
<style>
  .row {{ opacity:0; animation: enter .55s cubic-bezier(.2,.7,.2,1) forwards; }}
  {''.join(css)}
  .key {{ fill:{GOLD}; font:600 12px "SFMono-Regular",Consolas,"Liberation Mono",monospace; }}
  .value {{ fill:{SILVER}; font:11.2px "SFMono-Regular",Consolas,"Liberation Mono",monospace; }}
  .cursor {{ animation: blink 1s step-end infinite; }}
  @keyframes enter {{ from{{opacity:0;transform:translateX(-8px)}} to{{opacity:1;transform:translateX(0)}} }}
  @keyframes blink {{ 50%{{opacity:0}} }}
</style>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="18" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>
<circle cx="24" cy="25" r="5" fill="#ff5f57"/>
<circle cx="42" cy="25" r="5" fill="#febc2e"/>
<circle cx="60" cy="25" r="5" fill="#28c840"/>
<text x="245" y="30" text-anchor="middle" fill="{GOLD}" font-size="12" font-family="monospace">The Cipher Stack</text>
<line x1="18" y1="47" x2="472" y2="47" stroke="#252525"/>
<text x="28" y="65" fill="{MUTED}" font-size="10.5" font-family="monospace">shagor@cipher:~$ neofetch --engineering</text>
{''.join(lines)}
<text x="28" y="500" fill="{MUTED}" font-size="10.5" font-family="monospace">status: <tspan fill="{GOLD}">building</tspan> <tspan class="cursor" fill="{GOLD}">▋</tspan></text>
</svg>'''

    args.output.write_text(svg, encoding="utf-8")
    print(f"Generated: {args.output}")


if __name__ == "__main__":
    main()
