import time
import os
import cv2
import numpy as np
from PIL import Image, ImageOps

from .models import QualityReport, Status, DetectorResult
from .config import QualityConfig
from .detectors.dust import DustDetector
from .detectors.sharpness import SharpnessDetector
from .detectors.exposure import ExposureDetector
from .detectors.dead_pixels import DeadPixelDetector
from .fingerprint.dust_database import DustDatabase

class TechnicalQualityAnalyzer:
    def __init__(self, config: QualityConfig, db_path: str = None):
        self.config = config
        self.db = DustDatabase(db_path) if db_path else None
        self.detectors = [
            DustDetector(config, self.db),
            SharpnessDetector(config),
            ExposureDetector(config),
            DeadPixelDetector(config)
        ]
        
    def analyze_image(self, path: str) -> QualityReport:
        start_time = time.time()
        try:
            pil_img = Image.open(path)
            pil_img = ImageOps.exif_transpose(pil_img)
            width, height = pil_img.size
            fmt = pil_img.format
            
            cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            scale = min(1.0, self.config.analysis_resolution_max_dim / max(width, height))
            if scale < 1.0:
                cv_img_analysis = cv2.resize(cv_img, (0,0), fx=scale, fy=scale)
            else:
                cv_img_analysis = cv_img
                
            context = {
                "original_shape": cv_img.shape,
                "analysis_shape": cv_img_analysis.shape,
                "scale": scale,
                "file_path": path
            }
            
            results = {}
            overall_status = Status.PASS
            
            for detector in self.detectors:
                try:
                    res = detector.analyze(cv_img, cv_img_analysis, context)
                    results[res.detector_name] = res
                    
                    if res.status == Status.ERROR:
                        overall_status = Status.ERROR
                        break
                    
                    if res.status == Status.HIGH_RISK:
                        overall_status = Status.HIGH_RISK
                    elif res.status == Status.REVIEW and overall_status != Status.HIGH_RISK:
                        overall_status = Status.REVIEW
                        
                except Exception as e:
                    results[detector.__class__.__name__] = DetectorResult(
                        detector_name=detector.__class__.__name__,
                        status=Status.ERROR,
                        error_msg=str(e)
                    )
                    overall_status = Status.ERROR
            
            return QualityReport(
                file_path=path,
                filename=os.path.basename(path),
                width=width,
                height=height,
                format=fmt or "UNKNOWN",
                overall_status=overall_status,
                overall_confidence=1.0,
                technical_quality=results,
                processing_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            return QualityReport(
                file_path=path,
                filename=os.path.basename(path),
                width=0,
                height=0,
                format="UNKNOWN",
                overall_status=Status.ERROR,
                overall_confidence=0.0,
                technical_quality={},
                processing_time_seconds=time.time() - start_time,
                error_msg=str(e)
            )
