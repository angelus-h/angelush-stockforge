import cv2
import numpy as np

def draw_diagnostics(img_path: str, report: dict, output_path: str):
    img = cv2.imread(img_path)
    if img is None: return
    
    h, w = img.shape[:2]
    
    for det_name, det_res in report.get("technical_quality", {}).items():
        anomalies = det_res.get("anomalies", [])
            
        for anom in anomalies:
            x_norm = anom["x_norm"]
            y_norm = anom["y_norm"]
            w_norm = anom["width_norm"]
            h_norm = anom["height_norm"]
            desc = anom["description"]
                
            px = int(x_norm * w)
            py = int(y_norm * h)
            pw = int(w_norm * w)
            ph = int(h_norm * h)
            
            color = (0, 0, 255)
            if "persistent" in desc.lower():
                color = (0, 255, 255)
            
            cv2.rectangle(img, (px, py), (px+max(10, pw), py+max(10, ph)), color, 2)
            cv2.putText(img, det_name, (px, py-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
    cv2.imwrite(output_path, img)
