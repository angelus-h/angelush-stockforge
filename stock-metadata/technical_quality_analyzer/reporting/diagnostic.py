import cv2
import numpy as np
from pathlib import Path


def draw_diagnostics(img_path: str, report: dict, output_path: str):
    img = None
    try:
        with open(img_path, "rb") as f:
            data = f.read()
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        pass

    if img is None:
        try:
            from dashboard import raw_loader
            pil_im = raw_loader.load_image_safely(img_path)
            if pil_im.mode != "RGB":
                pil_im = pil_im.convert("RGB")
            img = cv2.cvtColor(np.array(pil_im), cv2.COLOR_RGB2BGR)
        except Exception:
            pass

    if img is None:
        return
    
    h, w = img.shape[:2]
    
    for det_name, det_res in report.get("technical_quality", {}).items():
        anomalies = det_res.get("anomalies", [])
            
        for anom in anomalies:
            x_norm = anom.get("x_norm", 0.0)
            y_norm = anom.get("y_norm", 0.0)
            w_norm = anom.get("width_norm", 0.01)
            h_norm = anom.get("height_norm", 0.01)
            desc = anom.get("description", det_name)
            conf = anom.get("confidence", 0.7)
            score = anom.get("score", conf)
            in_sky = anom.get("in_sky", False)
            persistent = anom.get("persistent", False)
                
            px = int(x_norm * w)
            py = int(y_norm * h)
            pw = max(16, int(w_norm * w))
            ph = max(16, int(h_norm * h))
            
            # Position bounding box centered at (px, py)
            x1 = max(0, px - pw // 2)
            y1 = max(0, py - ph // 2)
            x2 = min(w, x1 + pw)
            y2 = min(h, y1 + ph)
            
            # Color code:
            # Persistent: Bright Magenta/Yellow (0, 255, 255)
            # Sky candidate: Orange (0, 165, 255)
            # Standard candidate: Red (0, 0, 255)
            if persistent:
                color = (0, 255, 255)
                label = f"DUST [PERSISTENT] {score:.2f}"
            elif in_sky:
                color = (0, 165, 255)
                label = f"DUST (Sky) {score:.2f}"
            else:
                color = (0, 0, 255)
                label = f"{det_name.upper()} {score:.2f}"
            
            # Draw targeting crosshair and circle
            radius = max(14, int(max(pw, ph) * 0.75))
            cv2.circle(img, (px, py), radius, color, 2)
            cv2.line(img, (px - radius - 5, py), (px + radius + 5, py), color, 1)
            cv2.line(img, (px, py - radius - 5), (px, py + radius + 5), color, 1)
            
            # Text background and label
            label_pos = (max(5, px - radius), max(20, py - radius - 8))
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(img, (label_pos[0] - 2, label_pos[1] - th - 4), (label_pos[0] + tw + 2, label_pos[1] + 2), (0, 0, 0), -1)
            cv2.putText(img, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
            
    try:
        ext = Path(output_path).suffix or ".jpg"
        success, enc = cv2.imencode(ext, img)
        if success:
            with open(output_path, "wb") as f:
                f.write(enc)
        else:
            cv2.imwrite(output_path, img)
    except Exception:
        cv2.imwrite(output_path, img)
