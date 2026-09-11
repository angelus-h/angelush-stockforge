import cv2
import numpy as np
from .base import BaseDetector
from ..models import DetectorResult, Status, Anomaly

class DeadPixelDetector(BaseDetector):
    def analyze(self, original_img, analysis_img, context):
        gray = cv2.cvtColor(analysis_img, cv2.COLOR_BGR2GRAY)
        
        kernel = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]])
        filtered = cv2.filter2D(gray, -1, kernel)
        
        _, thresh = cv2.threshold(filtered, self.config.dead_pixel_threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        anomalies = []
        h, w = analysis_img.shape[:2]
        
        for cnt in contours:
            # A dead pixel should be literally 1 or 2 pixels on the resized analysis image, and extremely bright relative to its immediate surrounding
            # We filter for area, but the main filtering happens with the threshold
            if cv2.contourArea(cnt) <= 2: 
                x, y, bw, bh = cv2.boundingRect(cnt)
                
                # Double check: extract the patch and check its maximum intensity against neighbors
                # to avoid false positives on natural highlights (like sun glint on flowers)
                px = int(x + bw/2)
                py = int(y + bh/2)
                
                if 1 < px < w-1 and 1 < py < h-1:
                    patch = gray[py-1:py+2, px-1:px+2]
                    center_val = patch[1, 1]
                    bg_mean = (np.sum(patch) - center_val) / 8.0
                    
                    if center_val > 250 and (center_val - bg_mean) > 150:
                        anomalies.append(Anomaly(
                            x_norm=x/w, y_norm=y/h,
                            width_norm=bw/w, height_norm=bh/h,
                            description="Possible dead/hot pixel",
                            confidence=0.8
                        ))
        
        status = Status.PASS
        warnings = []
        if len(anomalies) > 5:
            status = Status.REVIEW
            warnings.append(f"Found {len(anomalies)} potential dead/hot pixels.")
            
        return DetectorResult(
            detector_name="dead_pixels",
            status=status,
            warnings=warnings,
            anomalies=anomalies,
            metrics={"count": len(anomalies)}
        )
