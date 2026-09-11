import cv2
import numpy as np
from .base import BaseDetector
from ..models import DetectorResult, Status, Anomaly

class SharpnessDetector(BaseDetector):
    def analyze(self, original_img, analysis_img, context):
        gray = cv2.cvtColor(analysis_img, cv2.COLOR_BGR2GRAY)
        
        global_laplacian = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        h, w = gray.shape
        tiles_y = 3
        tiles_x = 3
        step_y = h // tiles_y
        step_x = w // tiles_x
        
        tile_vars = []
        for i in range(tiles_y):
            for j in range(tiles_x):
                tile = gray[i*step_y:(i+1)*step_y, j*step_x:(j+1)*step_x]
                var = cv2.Laplacian(tile, cv2.CV_64F).var()
                tile_vars.append(var)
                
        status = Status.PASS
        warnings = []
        anomalies = []
        
        if global_laplacian < self.config.sharpness_global_threshold:
            status = Status.REVIEW
            warnings.append(f"Global sharpness low: {global_laplacian:.1f}")
            
        max_var = max(tile_vars)
        if max_var > 0:
            for idx, var in enumerate(tile_vars):
                if var < max_var * self.config.sharpness_local_anomaly_ratio and var < self.config.sharpness_global_threshold:
                    ty = idx // tiles_x
                    tx = idx % tiles_x
                    tile = gray[ty*step_y:(ty+1)*step_y, tx*step_x:(tx+1)*step_x]
                    std_dev = np.std(tile)
                    if std_dev > 10:
                        status = Status.REVIEW
                        warnings.append(f"Local softness detected in tile {idx}")
                        anomalies.append(Anomaly(
                            x_norm=tx/tiles_x, y_norm=ty/tiles_y,
                            width_norm=1.0/tiles_x, height_norm=1.0/tiles_y,
                            description=f"Locally soft region (var: {var:.1f})",
                            confidence=0.8
                        ))
        
        return DetectorResult(
            detector_name="sharpness",
            status=status,
            score=float(global_laplacian),
            warnings=warnings,
            anomalies=anomalies,
            metrics={"global_variance": float(global_laplacian), "tile_variances": [float(v) for v in tile_vars]}
        )
