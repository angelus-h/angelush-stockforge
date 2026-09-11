import unittest
import numpy as np
import cv2
import os
from technical_quality_analyzer.analyzer import TechnicalQualityAnalyzer
from technical_quality_analyzer.config import QualityConfig
from technical_quality_analyzer.models import Status

class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.config = QualityConfig(mode="paranoid")
        self.analyzer = TechnicalQualityAnalyzer(self.config, db_path=":memory:")
        
        self.test_img_path = "test_img.jpg"
        img = np.zeros((1000, 1000, 3), dtype=np.uint8)
        img += 128
        noise = np.random.normal(0, 10, img.shape).astype(np.uint8)
        img = cv2.add(img, noise)
        cv2.imwrite(self.test_img_path, img)
        
    def tearDown(self):
        if os.path.exists(self.test_img_path):
            os.remove(self.test_img_path)
            
    def test_clean_image(self):
        report = self.analyzer.analyze_image(self.test_img_path)
        self.assertIn(report.overall_status, [Status.PASS, Status.REVIEW])
        
if __name__ == '__main__':
    unittest.main()
