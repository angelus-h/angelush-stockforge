import cv2
import numpy as np
from .base import BaseDetector
from ..models import DetectorResult, Status

class ExposureDetector(BaseDetector):
    def analyze(self, original_img, analysis_img, context):
        gray = cv2.cvtColor(analysis_img, cv2.COLOR_BGR2GRAY)
        
        total_pixels = gray.size
        shadows = np.sum(gray < 5)
        highlights = np.sum(gray > 250)
        
        shadow_pct = (shadows / total_pixels) * 100
        highlight_pct = (highlights / total_pixels) * 100
        
        status = Status.PASS
        warnings = []
        
        if shadow_pct > self.config.shadow_clipping_threshold_percent:
            status = Status.REVIEW
            warnings.append(f"Shadow clipping: {shadow_pct:.2f}%")
            
        if highlight_pct > self.config.highlight_clipping_threshold_percent:
            status = Status.REVIEW
            warnings.append(f"Highlight clipping: {highlight_pct:.2f}%")
            
        if shadow_pct > 5.0 or highlight_pct > 5.0:
            status = Status.HIGH_RISK
            warnings.append("Severe clipping detected.")
            
        return DetectorResult(
            detector_name="exposure",
            status=status,
            warnings=warnings,
            metrics={
                "shadow_clipping_percent": float(shadow_pct),
                "highlight_clipping_percent": float(highlight_pct)
            }
        )
