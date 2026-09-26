"""
Raw & Image Loader utility for StockForge.
Provides high-performance preview and thumbnail generation for standard images
(JPG, PNG, WEBP, TIFF) and RAW formats (DNG, ORF, ODF, CR2, CR3, NEF, ARW, PEF, RAF, RW2).
"""

import io
import base64
from pathlib import Path
from PIL import Image

try:
    import rawpy
except ImportError:
    rawpy = None

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff",
    ".dng", ".orf", ".odf", ".cr2", ".cr3", ".nef", ".arw", ".pef", ".raf", ".rw2"
}

RAW_EXTENSIONS = {
    ".dng", ".orf", ".odf", ".cr2", ".cr3", ".nef", ".arw", ".pef", ".raf", ".rw2"
}


def is_supported_file(file_path) -> bool:
    return Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS


def load_image_safely(image_path) -> Image.Image:
    """
    Safely load an image or extract preview from a RAW file (DNG, ORF, CR2, etc.).
    Returns an independent in-memory PIL Image object.
    """
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {image_path}")

    ext = p.suffix.lower()

    # RAW formats: extract embedded camera JPEG first for instant decoding
    if ext in RAW_EXTENSIONS:
        if rawpy is not None:
            try:
                with rawpy.imread(str(p)) as raw:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        im = Image.open(io.BytesIO(thumb.data))
                        im.load()
                        return im
            except Exception:
                pass

        # Binary search fallback for embedded camera JPEG preview
        try:
            with open(p, "rb") as f:
                data = f.read()
            pos = 0
            best_im = None
            best_area = 0
            while True:
                start = data.find(b"\xff\xd8\xff", pos)
                if start == -1:
                    break
                end = data.find(b"\xff\xd9", start + 4)
                if end != -1:
                    chunk = data[start : end + 2]
                    pos = end + 2
                    try:
                        im = Image.open(io.BytesIO(chunk))
                        area = im.size[0] * im.size[1]
                        if area > best_area:
                            best_area = area
                            best_im = im
                    except Exception:
                        pass
                else:
                    break
            if best_im is not None:
                best_im.load()
                return best_im
        except Exception:
            pass

    # Standard PIL Loader
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(p) as img:
        im = img.copy()
        im.load()
        return im


def get_thumbnail_bytes(image_path: str, max_dim: int = 240, quality: int = 75) -> bytes:
    """
    Generate JPEG thumbnail bytes from image or RAW file for fast, safe UI rendering.
    """
    try:
        im = load_image_safely(image_path)
        if im is None:
            return b""

        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            if im.mode == "P":
                im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")

        im.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()
    except Exception:
        return b""


def encode_thumbnail_base64(image_path: str, max_dim: int = 768) -> str:
    """
    Resize image or RAW file to max_dim and return base64 string for LLM vision models.
    """
    im = load_image_safely(image_path)
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        if im.mode == "P":
            im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")

    im.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def generate_histogram(image_path: str, width: int = 560, height: int = 180):
    """
    Computes an RGB + Luminance photographic histogram and returns:
    1. Rendered PNG bytes (Lightroom / Capture One style dark photographic curve).
    2. Exposure & clipping stats (shadow_clip_pct, highlight_clip_pct, mean_luma, contrast_std).
    3. Pandas DataFrame of bins (0-255) for interactive chart inspection.
    """
    import cv2
    import numpy as np
    import pandas as pd

    pil_im = load_image_safely(image_path)
    if pil_im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", pil_im.size, (255, 255, 255))
        if pil_im.mode == "P":
            pil_im = pil_im.convert("RGBA")
        bg.paste(pil_im, mask=pil_im.split()[-1] if pil_im.mode in ("RGBA", "LA") else None)
        pil_im = bg
    elif pil_im.mode != "RGB":
        pil_im = pil_im.convert("RGB")

    aspect = pil_im.size[1] / max(1, pil_im.size[0])
    thumb = pil_im.resize((600, int(600 * aspect)), Image.Resampling.BILINEAR)
    arr = np.array(thumb)

    r_hist, _ = np.histogram(arr[:, :, 0], bins=256, range=(0, 256))
    g_hist, _ = np.histogram(arr[:, :, 1], bins=256, range=(0, 256))
    b_hist, _ = np.histogram(arr[:, :, 2], bins=256, range=(0, 256))
    luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    l_hist, _ = np.histogram(luma, bins=256, range=(0, 256))

    total_px = arr.shape[0] * arr.shape[1]
    shadow_clip = np.sum((arr[:, :, 0] <= 1) & (arr[:, :, 1] <= 1) & (arr[:, :, 2] <= 1))
    highlight_clip = np.sum((arr[:, :, 0] >= 254) & (arr[:, :, 1] >= 254) & (arr[:, :, 2] >= 254))
    shadow_pct = float((shadow_clip / total_px) * 100.0)
    highlight_pct = float((highlight_clip / total_px) * 100.0)
    mean_luma = float(np.mean(luma))
    contrast_std = float(np.std(luma))

    stats = {
        "shadow_clip_pct": shadow_pct,
        "highlight_clip_pct": highlight_pct,
        "mean_luma": mean_luma,
        "contrast_std": contrast_std,
    }

    df = pd.DataFrame({
        "Red": r_hist,
        "Green": g_hist,
        "Blue": b_hist,
        "Luminance": l_hist
    }, index=range(256))

    canvas = np.full((height, width, 3), 22, dtype=np.uint8)

    for pct in [0.25, 0.5, 0.75]:
        x = int(pct * width)
        cv2.line(canvas, (x, 0), (x, height), (42, 42, 42), 1)
        y = int(pct * height)
        cv2.line(canvas, (0, y), (width, y), (42, 42, 42), 1)

    max_val = max(
        float(np.percentile(r_hist, 99.5)),
        float(np.percentile(g_hist, 99.5)),
        float(np.percentile(b_hist, 99.5)),
        float(np.percentile(l_hist, 99.5)),
        1.0
    )

    def to_pts(h_data):
        pts = []
        for i in range(256):
            x = int(i * (width - 1) / 255.0)
            norm_val = min(1.0, float(h_data[i]) / max_val)
            y = int((height - 1) * (1.0 - norm_val * 0.92))
            pts.append([x, y])
        return np.array(pts, dtype=np.int32)

    overlay = canvas.copy()
    l_pts = to_pts(l_hist)
    cv2.fillPoly(overlay, [np.vstack([[0, height], l_pts, [width - 1, height]])], (80, 80, 80))
    r_pts = to_pts(r_hist)
    cv2.fillPoly(overlay, [np.vstack([[0, height], r_pts, [width - 1, height]])], (30, 30, 160))
    g_pts = to_pts(g_hist)
    cv2.fillPoly(overlay, [np.vstack([[0, height], g_pts, [width - 1, height]])], (30, 160, 30))
    b_pts = to_pts(b_hist)
    cv2.fillPoly(overlay, [np.vstack([[0, height], b_pts, [width - 1, height]])], (160, 60, 30))

    cv2.addWeighted(overlay, 0.45, canvas, 0.55, 0, canvas)

    cv2.polylines(canvas, [l_pts], False, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.polylines(canvas, [r_pts], False, (70, 70, 255), 1, cv2.LINE_AA)
    cv2.polylines(canvas, [g_pts], False, (70, 255, 70), 1, cv2.LINE_AA)
    cv2.polylines(canvas, [b_pts], False, (255, 130, 70), 1, cv2.LINE_AA)

    s_col = (50, 120, 255) if shadow_pct > 0.5 else (110, 110, 110)
    cv2.circle(canvas, (14, 15), 5, s_col, -1)
    cv2.putText(canvas, f"Shadows: {shadow_pct:.1f}%", (24, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (190, 190, 190), 1, cv2.LINE_AA)

    h_col = (30, 30, 255) if highlight_pct > 0.5 else (110, 110, 110)
    cv2.circle(canvas, (width - 130, 15), 5, h_col, -1)
    cv2.putText(canvas, f"Highlights: {highlight_pct:.1f}%", (width - 118, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (190, 190, 190), 1, cv2.LINE_AA)

    success, enc = cv2.imencode(".png", canvas)
    return (enc.tobytes() if success else b""), stats, df
