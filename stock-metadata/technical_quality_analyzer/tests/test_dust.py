import unittest
import numpy as np
import cv2
import os
import sys
from pathlib import Path

# Ensure stock-metadata is on sys.path
SM_DIR = Path(__file__).resolve().parent.parent.parent
if str(SM_DIR) not in sys.path:
    sys.path.insert(0, str(SM_DIR))

from technical_quality_analyzer.analyzer import TechnicalQualityAnalyzer
from technical_quality_analyzer.config import QualityConfig
from technical_quality_analyzer.models import Status

class TestDustDetection(unittest.TestCase):
    def setUp(self):
        self.test_img_path = "test_sky_dust.jpg"
        # 1000x1000 image: upper 600px is smooth blue sky, lower 400px is textured ground
        img = np.zeros((1000, 1000, 3), dtype=np.uint8)
        
        # Sky: blue (B=235, G=190, R=140 in BGR) with very slight gradient
        for y in range(600):
            img[y, :] = [235 - y//10, 190 - y//12, 140 - y//15]
            
        # Ground: high frequency random noise
        ground_noise = np.random.randint(40, 180, (400, 1000, 3), dtype=np.uint8)
        img[600:, :] = ground_noise
        
        # Add a subtle, soft-edged sensor dust spot in the sky at (cx=500, cy=250, radius=12)
        # 12% darkening with Gaussian profile
        y_grid, x_grid = np.ogrid[:1000, :1000]
        dist_sq = (x_grid - 500)**2 + (y_grid - 250)**2
        sigma = 6.0
        attenuation = 0.12 * np.exp(-dist_sq / (2 * sigma**2))
        
        # Apply darkening
        for c in range(3):
            chan = img[:, :, c].astype(np.float32)
            chan = chan * (1.0 - attenuation)
            img[:, :, c] = np.clip(chan, 0, 255).astype(np.uint8)
            
        cv2.imwrite(self.test_img_path, img)

    def tearDown(self):
        if os.path.exists(self.test_img_path):
            os.remove(self.test_img_path)

    def test_dust_in_sky_detected(self):
        # 1. In paranoid mode: single candidate in sky should trigger REVIEW
        cfg_paranoid = QualityConfig(mode="paranoid")
        analyzer_paranoid = TechnicalQualityAnalyzer(cfg_paranoid)
        rep = analyzer_paranoid.analyze_image(self.test_img_path)
        dust = rep.technical_quality["sensor_dust"]
        
        # Spot in the sky should be detected
        self.assertGreaterEqual(len(dust.anomalies), 1)
        spot = dust.anomalies[0]
        self.assertAlmostEqual(spot.x_norm, 0.5, delta=0.03)
        self.assertAlmostEqual(spot.y_norm, 0.25, delta=0.03)
        self.assertTrue(spot.in_sky)
        self.assertEqual(dust.status, Status.REVIEW)

        # 2. In production mode: an isolated single spot is registered as candidate but remains PASS
        cfg_prod = QualityConfig(mode="production")
        analyzer_prod = TechnicalQualityAnalyzer(cfg_prod)
        rep_prod = analyzer_prod.analyze_image(self.test_img_path)
        dust_prod = rep_prod.technical_quality["sensor_dust"]
        self.assertGreaterEqual(len(dust_prod.anomalies), 1)
        self.assertEqual(dust_prod.status, Status.PASS)

if __name__ == '__main__':
    unittest.main()
