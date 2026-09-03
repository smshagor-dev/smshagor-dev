#!/usr/bin/env python3
"""Prepare a portrait for the animated ASCII SVG renderer."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import remove


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove a portrait background, enhance contrast, and normalize framing."
    )
    parser.add_argument("input", type=Path, help="Input portrait image, e.g. hero.png")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("source-prepped.png"),
        help="Output PNG path (default: source-prepped.png)"
    )
    parser.add_argument(
        "--size", type=int, default=768,
        help="Square output canvas size in pixels (default: 768)"
    )
    parser.add_argument(
        "--padding", type=float, default=0.08,
        help="Transparent padding around detected subject, 0.0-0.30 (default: 0.08)"
    )
    return parser.parse_args()


def subject_bbox(alpha: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(alpha > 10)
    if len(xs) == 0 or len(ys) == 0:
        raise RuntimeError("Background removal produced an empty alpha mask.")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def enhance_rgb(rgb: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    l_chan = clahe.apply(l_chan)
    enhanced = cv2.cvtColor(cv2.merge((l_chan, a_chan, b_chan)), cv2.COLOR_LAB2RGB)
    blur = cv2.GaussianBlur(enhanced, (0, 0), 1.15)
    sharpened = cv2.addWeighted(enhanced, 1.12, blur, -0.12, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def main() -> None:
    args = parse_args()

    if not args.input.is_file():
        raise FileNotFoundError(f"Input portrait not found: {args.input}")
    if args.size < 256:
        raise ValueError("--size must be at least 256")
    if not 0.0 <= args.padding <= 0.30:
        raise ValueError("--padding must be between 0.0 and 0.30")

    original = Image.open(args.input).convert("RGBA")
    cutout = remove(original).convert("RGBA")
    rgba = np.array(cutout)

    x0, y0, x1, y1 = subject_bbox(rgba[..., 3])
    w, h = x1 - x0, y1 - y0
    pad_x = round(w * args.padding)
    pad_y = round(h * args.padding)

    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(rgba.shape[1], x1 + pad_x)
    y1 = min(rgba.shape[0], y1 + pad_y)
    crop = rgba[y0:y1, x0:x1]
    crop[..., :3] = enhance_rgb(crop[..., :3])

    target = args.size
    scale = min(target / crop.shape[1], target / crop.shape[0])
    new_w = max(1, round(crop.shape[1] * scale))
    new_h = max(1, round(crop.shape[0] * scale))

    resized = Image.fromarray(crop, "RGBA").resize(
        (new_w, new_h), Image.Resampling.LANCZOS
    )
    canvas = Image.new("RGBA", (target, target), (0, 0, 0, 0))
    left = (target - new_w) // 2
    top = (target - new_h) // 2
    canvas.alpha_composite(resized, (left, top))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, optimize=True)
    print(f"Prepared portrait: {args.output}")


if __name__ == "__main__":
    main()
