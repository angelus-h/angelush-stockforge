import unittest
import numpy as np
import cv2
import tempfile
import shutil
from pathlib import Path

import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "stock-metadata"))
sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from technical_quality_analyzer.config import QualityConfig
from technical_quality_analyzer.detectors.noise import NoiseDetector
from technical_quality_analyzer.analyzer import TechnicalQualityAnalyzer
from technical_quality_analyzer.models import Status
import db


class TestNoiseDetector(unittest.TestCase):
    def setUp(self):
        self.config = QualityConfig(mode="production")
        self.detector = NoiseDetector(self.config)
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_image_passes(self):
        # A clean smooth image should have minimal noise
        clean_img = np.full((500, 500, 3), 128, dtype=np.uint8)
        context = {"file_path": "dummy.jpg"}
        result = self.detector.analyze(clean_img, clean_img, context)

        self.assertEqual(result.status, Status.PASS)
        self.assertLess(result.metrics["effective_sigma"], 2.0)
        self.assertEqual(len(result.warnings), 0)

    def test_heavy_noise_triggers_high_risk(self):
        # Image with heavy Gaussian noise
        base = np.full((500, 500, 3), 128, dtype=np.float32)
        noise = np.random.normal(0, 25, (500, 500, 3))
        noisy_img = np.clip(base + noise, 0, 255).astype(np.uint8)

        context = {"file_path": "noisy.jpg"}
        result = self.detector.analyze(noisy_img, noisy_img, context)

        self.assertEqual(result.status, Status.HIGH_RISK)
        self.assertGreaterEqual(result.score, self.config.noise_sigma_high_risk_production)
        self.assertTrue(any("noise" in w.lower() for w in result.warnings))

    def test_chroma_color_noise_detection(self):
        # Base grayscale image with high frequency color channel noise (chroma grain)
        gray = np.full((400, 400), 128, dtype=np.uint8)
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR).astype(np.float32)

        # Inject strong alternating color spikes (chroma noise)
        chroma_noise = np.random.normal(0, 15, (400, 400, 3))
        # Keep luminance roughly constant while perturbing channels
        chroma_noise[:, :, 0] += 10
        chroma_noise[:, :, 2] -= 10
        noisy_bgr = np.clip(bgr + chroma_noise, 0, 255).astype(np.uint8)

        context = {"file_path": "chroma_noise.jpg"}
        result = self.detector.analyze(noisy_bgr, noisy_bgr, context)

        self.assertIn(result.status, [Status.REVIEW, Status.HIGH_RISK])
        self.assertGreater(result.metrics["chroma_noise"], 3.5)

    def test_analyzer_integration_and_db_persistence(self):
        img_path = Path(self.temp_dir.name) / "test_sample.jpg"
        img = np.full((400, 400, 3), 150, dtype=np.uint8)
        cv2.imwrite(str(img_path), img)

        analyzer = TechnicalQualityAnalyzer(self.config, db_path=":memory:")
        report = analyzer.analyze_image(str(img_path))

        self.assertIn("noise", report.technical_quality)
        noise_res = report.technical_quality["noise"]
        self.assertIsNotNone(noise_res.score)

        # Test SQLite storage
        test_db = Path(self.temp_dir.name) / "test.db"
        db.init_db(str(test_db))
        img_id = db.insert_image(
            file_path=str(img_path),
            file_name="test_sample.jpg",
            directory=str(self.temp_dir.name),
            db_path=str(test_db)
        )

        db.update_image(
            img_id,
            qc_status=report.overall_status.value,
            qc_sharpness=85.0,
            qc_noise=noise_res.score,
            qc_dust_count=0,
            db_path=str(test_db)
        )

        saved_img = db.get_image_by_id(img_id, db_path=str(test_db))
        self.assertIsNotNone(saved_img)
        self.assertEqual(saved_img["qc_noise"], noise_res.score)


if __name__ == "__main__":
    unittest.main()
