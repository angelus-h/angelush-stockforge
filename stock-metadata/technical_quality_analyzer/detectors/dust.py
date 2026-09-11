import cv2
import numpy as np
from .base import BaseDetector
from ..models import DetectorResult, Status, Anomaly

class DustDetector(BaseDetector):
    def __init__(self, config, db=None):
        super().__init__(config)
        self.db = db
        
    def analyze(self, original_img, analysis_img, context):
        gray = cv2.cvtColor(analysis_img, cv2.COLOR_BGR2GRAY)
        gray_blur = cv2.medianBlur(gray, 5)
        
        kernel_size = max(5, int(analysis_img.shape[1] * 0.02))
        if kernel_size % 2 == 0: kernel_size += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        
        blackhat = cv2.morphologyEx(gray_blur, cv2.MORPH_BLACKHAT, kernel)
        _, thresh = cv2.threshold(blackhat, 15, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        anomalies = []
        high_conf = 0
        status = Status.PASS
        warnings = []
        h, w = analysis_img.shape[:2]
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Increased minimum area and slightly decreased maximum area to ignore 
            # high-frequency texture noise (like flowers in a field)
            if 15 < area < (w * h * 0.005):
                perimeter = cv2.arcLength(cnt, True)
                if perimeter == 0: continue
                circularity = 4 * np.pi * (area / (perimeter * perimeter))
                
                # Increased circularity threshold to filter out irregularly shaped shadows (leaves, ground)
                if circularity > 0.6:
                    M = cv2.moments(cnt)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        x_norm = cx / w
                        y_norm = cy / h
                        
                        persistent = False
                        if self.db:
                            persistent = self.db.check_and_add(
                                x_norm, y_norm, 
                                context["file_path"], 
                                self.config.dust_persistence_tolerance
                            )
                        
                        conf = 0.7 if not persistent else 0.95
                        if persistent:
                            high_conf += 1
                            
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        anomalies.append(Anomaly(
                            x_norm=x_norm, y_norm=y_norm,
                            width_norm=bw/w, height_norm=bh/h,
                            description=f"Sensor dust candidate{' (persistent)' if persistent else ''}",
                            confidence=conf,
                            persistent=persistent
                        ))
        
        if high_conf > 0 or len(anomalies) >= 3:
            status = Status.HIGH_RISK
            warnings.append(f"Found {len(anomalies)} dust candidates, {high_conf} highly persistent.")
        elif len(anomalies) > 0:
            status = Status.REVIEW
            warnings.append(f"Found {len(anomalies)} potential dust candidates.")
            
        return DetectorResult(
            detector_name="sensor_dust",
            status=status,
            warnings=warnings,
            anomalies=anomalies,
            metrics={"candidates": len(anomalies), "persistent": high_conf}
        )
