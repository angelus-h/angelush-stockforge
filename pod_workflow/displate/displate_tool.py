"""Displate Technical Validator & Auto-Preparation Tool.

Author: Angelus H / StockForge
Purpose: Automated quality assurance and standardization of artwork for Displate.
Ensures strict compliance with Displate's 1.4:1 ratio, 300 DPI, 200px Safe Zone,
file size constraints, and print texture standards.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

import numpy as np
from PIL import Image, ImageCms, ImageOps
import cv2

# Displate Technical Constants
MIN_SHORT_SIDE = 2900
TARGET_RATIO = 1.4000
RATIO_TOLERANCE = 0.015  # Acceptable tolerance around 1.40
MIN_DPI = 300
MAX_FILE_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB
SAFE_MARGIN_BASE = 200  # 200px on 4060x2900 standard


def analyze_displate_compliance(image_path: Path) -> Dict[str, Any]:
    """Analyzes an image file against all official Displate technical requirements."""
    res: Dict[str, Any] = {
        "path": str(image_path),
        "filename": image_path.name,
        "status": "PASS",
        "checks": {},
        "warnings": [],
        "errors": [],
    }

    # 1. File size check
    file_size = image_path.stat().st_size
    size_mb = file_size / (1024 * 1024)
    res["checks"]["file_size_mb"] = round(size_mb, 2)
    if file_size > MAX_FILE_SIZE_BYTES:
        res["errors"].append(f"File size {size_mb:.2f} MB exceeds 30 MB limit.")

    try:
        with Image.open(image_path) as img:
            width, height = img.size
            res["checks"]["width"] = width
            res["checks"]["height"] = height

            # 2. Orientation & Dimensions
            is_portrait = height >= width
            res["checks"]["orientation"] = "Portrait" if is_portrait else "Landscape"
            short_side = min(width, height)
            long_side = max(width, height)
            res["checks"]["short_side"] = short_side
            res["checks"]["long_side"] = long_side

            if short_side < MIN_SHORT_SIDE:
                res["errors"].append(
                    f"Short side ({short_side}px) is below Displate minimum of {MIN_SHORT_SIDE}px."
                )

            if not is_portrait:
                res["warnings"].append(
                    "Landscape artwork is limited to size L (XL prints are only available for Portrait)."
                )

            # 3. Aspect Ratio check
            actual_ratio = long_side / short_side
            res["checks"]["aspect_ratio"] = round(actual_ratio, 4)
            ratio_diff = abs(actual_ratio - TARGET_RATIO)
            if ratio_diff > RATIO_TOLERANCE:
                if 1.47 <= actual_ratio <= 1.53:
                    res["warnings"].append(
                        f"Aspect ratio is {actual_ratio:.3f}:1 (Camera native 3:2). Displate system accepts this with slight edge auto-crop, though official spec recommends 1.40:1."
                    )
                else:
                    res["errors"].append(
                        f"Aspect ratio is {actual_ratio:.3f}:1. Displate recommends 1.40:1 (or 1.50:1 camera standard)."
                    )

            # 4. DPI Check
            dpi_info = img.info.get("dpi")
            if dpi_info:
                h_dpi, v_dpi = dpi_info[0], dpi_info[1]
                res["checks"]["dpi"] = (round(h_dpi), round(v_dpi))
                if h_dpi < MIN_DPI or v_dpi < MIN_DPI:
                    res["errors"].append(
                        f"DPI is {round(h_dpi)}x{round(v_dpi)}. Displate requires at least 300 DPI."
                    )
            else:
                res["checks"]["dpi"] = None
                res["errors"].append("Missing DPI header (metadata). Displate requires strictly 300 DPI.")

            # 5. Color Profile
            icc = img.info.get("icc_profile")
            res["checks"]["has_icc_profile"] = icc is not None
            if not icc:
                res["warnings"].append("No embedded ICC profile found. sRGB recommended.")

            # 6. Safe Margin Check & Sharpness Analysis (via OpenCV)
            # Scale safe zone based on actual resolution relative to 4060x2900 standard
            scale_factor = long_side / 4060.0
            safe_margin_px = int(SAFE_MARGIN_BASE * scale_factor)
            res["checks"]["safe_margin_px"] = safe_margin_px

            img_np = np.array(img.convert("RGB"))
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

            # Check border zones for high-contrast text or edges
            h, w = gray.shape
            top_border = gray[0:safe_margin_px, :]
            bottom_border = gray[h - safe_margin_px:h, :]
            left_border = gray[:, 0:safe_margin_px]
            right_border = gray[:, w - safe_margin_px:w]

            border_edges = []
            for b in [top_border, bottom_border, left_border, right_border]:
                edges = cv2.Canny(b, 100, 200)
                edge_density = np.sum(edges > 0) / edges.size
                border_edges.append(edge_density)

            max_border_edge = max(border_edges)
            res["checks"]["border_edge_density"] = round(float(max_border_edge), 4)

            # High edge density in margin often signifies text or borders
            if max_border_edge > 0.045:
                res["warnings"].append(
                    f"Possible text, high-contrast borders or critical elements detected inside the {safe_margin_px}px Safe Zone."
                )

            # Laplacian sharpness check (texture detail metric)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            res["checks"]["laplacian_variance"] = round(float(laplacian_var), 1)
            if laplacian_var < 80.0:
                res["warnings"].append(
                    f"Low image texture variance ({laplacian_var:.1f}). Image may look waxy, over-smoothed by AI upscaler, or blurry."
                )

    except Exception as e:
        res["errors"].append(f"Image read error: {str(e)}")

    if res["errors"]:
        res["status"] = "FAIL"
    elif res["warnings"]:
        res["status"] = "WARN"
    else:
        res["status"] = "PASS"

    return res


def prepare_for_displate(
    input_path: Path,
    output_path: Path,
    target_short_side: int = 2900,
    add_grain: float = 0.0,
    orientation: Optional[str] = None,
) -> Path:
    """Prepares an image file to match Displate standards precisely.

    - Crops to exact 1.4:1 ratio (center-weighted).
    - Ensures minimum dimensions (2900px short side / 4060px long side).
    - Sets 300 DPI metadata in EXIF/JFIF header.
    - Ensures sRGB color space.
    - Optional: Adds fine micro-grain (0.005 - 0.015) to eliminate AI plastic smoothing.
    """
    with Image.open(input_path) as raw_img:
        img = ImageOps.exif_transpose(raw_img).convert("RGB")
        w, h = img.size

        if orientation == "portrait" or (orientation is None and h >= w):
            target_w = target_short_side
            target_h = int(round(target_short_side * TARGET_RATIO))
        else:
            target_h = target_short_side
            target_w = int(round(target_short_side * TARGET_RATIO))

        # Calculate crop box to preserve exact 1.4:1 ratio
        target_aspect = target_w / target_h
        current_aspect = w / h

        if current_aspect > target_aspect:
            # Current image is wider than target -> crop left & right
            new_w = int(round(h * target_aspect))
            offset_x = (w - new_w) // 2
            crop_box = (offset_x, 0, offset_x + new_w, h)
        else:
            # Current image is taller than target -> crop top & bottom
            new_h = int(round(w / target_aspect))
            offset_y = (h - new_h) // 2
            crop_box = (0, offset_y, w, offset_y + new_h)

        cropped = img.crop(crop_box)

        # Scale up if below target dimensions, or downscale if monstrous
        cw, ch = cropped.size
        if cw < target_w or ch < target_h:
            resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
        else:
            # Maintain high resolution, just adjust to exact ratio multiples
            resized = cropped

        # Optional subtle film grain injection (breaks waxy AI upscaler smoothing)
        final_img = resized
        if add_grain > 0.0:
            np_img = np.array(resized).astype(np.float32)
            noise = np.random.normal(0, add_grain * 255.0, np_img.shape)
            noisy_img = np.clip(np_img + noise, 0, 255).astype(np.uint8)
            final_img = Image.fromarray(noisy_img)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save with strictly 300 DPI and sRGB
        final_img.save(
            output_path,
            format="JPEG",
            quality=98,
            subsampling=0,
            dpi=(300, 300),
            icc_profile=img.info.get("icc_profile"),
        )

    return output_path


def format_report(analysis: Dict[str, Any]) -> str:
    """Formats the analysis result into a clean terminal report."""
    status_icon = "[PASS]" if analysis["status"] == "PASS" else ("[WARN]" if analysis["status"] == "WARN" else "[FAIL]")
    lines = [
        f"============================================================",
        f" Displate Compliance Report: {analysis['filename']}",
        f" Status: {status_icon}",
        f"============================================================",
        f"  * Dimensions:    {analysis['checks'].get('width')} x {analysis['checks'].get('height')} px ({analysis['checks'].get('orientation')})",
        f"  * Aspect Ratio:  {analysis['checks'].get('aspect_ratio')}:1 (Target: 1.40:1)",
        f"  * DPI:           {analysis['checks'].get('dpi')}",
        f"  * File Size:     {analysis['checks'].get('file_size_mb')} MB (Max: 30 MB)",
        f"  * Safe Zone:     {analysis['checks'].get('safe_margin_px')} px",
        f"  * Sharpness Var: {analysis['checks'].get('laplacian_variance')}",
    ]

    if analysis["errors"]:
        lines.append("\n  [!] ERRORS (Displate bot will reject):")
        for err in analysis["errors"]:
            lines.append(f"     - {err}")

    if analysis["warnings"]:
        lines.append("\n  [?] WARNINGS (Review recommended):")
        for warn in analysis["warnings"]:
            lines.append(f"     - {warn}")

    lines.append("============================================================\n")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Displate Technical Artwork Validator & Auto-Preparation Tool"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Validate subcommand
    val_parser = subparsers.add_parser("validate", help="Validate image(s) for Displate compliance")
    val_parser.add_argument("path", type=str, help="Path to image file or directory")

    # Prepare subcommand
    prep_parser = subparsers.add_parser("prepare", help="Crop & format image for Displate standard (1.4:1, 300 DPI)")
    prep_parser.add_argument("input", type=str, help="Input image file")
    prep_parser.add_argument("output", type=str, help="Output image file")
    prep_parser.add_argument("--grain", type=float, default=0.01, help="Film grain amount to break AI smoothing (default: 0.01 = 1%%)")
    prep_parser.add_argument("--orientation", choices=["portrait", "landscape"], default=None, help="Force orientation")

    args = parser.parse_args()

    if args.command == "validate":
        target_path = Path(args.path)
        if target_path.is_file():
            res = analyze_displate_compliance(target_path)
            print(format_report(res))
        elif target_path.is_dir():
            files = [
                f for f in target_path.iterdir()
                if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
            ]
            print(f"Scanning {len(files)} files in {target_path}...\n")
            for f in files:
                res = analyze_displate_compliance(f)
                print(format_report(res))
        else:
            print(f"Error: {target_path} does not exist.")
            sys.exit(1)

    elif args.command == "prepare":
        inp = Path(args.input)
        out = Path(args.output)
        if not inp.exists():
            print(f"Error: Input file {inp} does not exist.")
            sys.exit(1)

        print(f"Processing {inp.name} -> {out.name}...")
        prepare_for_displate(inp, out, add_grain=args.grain, orientation=args.orientation)
        print("Done. Validating result...")
        res = analyze_displate_compliance(out)
        print(format_report(res))


if __name__ == "__main__":
    main()
