import cv2
import numpy as np
from .base import BaseDetector
from ..models import DetectorResult, Status, Anomaly

class NoiseDetector(BaseDetector):
    """
    Detects digital sensor noise, high-ISO grain, and chrominance (color) artifacts.
    Combines:
    1. Immerkaer Fast Noise Variance Estimation across luminance.
    2. Homogeneous/smooth patch analysis (e.g. sky, clean backgrounds, walls) where noise is most critical.
    3. CIELAB high-frequency chroma fluctuation analysis (color noise).
    """

    def analyze(self, original_img: np.ndarray, analysis_img: np.ndarray, context: dict) -> DetectorResult:
        gray = cv2.cvtColor(analysis_img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # 1. Immerkaer Fast Noise Variance Estimation
        immerkaer_sigma = self._estimate_immerkaer_noise(gray)

        # 2. Patch-based analysis: find smooth/homogeneous regions to measure background noise
        patch_size = 32
        smooth_sigma, num_smooth_patches = self._estimate_smooth_patch_noise(gray, patch_size)

        # 3. Chrominance (Color) Noise Analysis via CIELAB
        chroma_noise = self._estimate_chroma_noise(analysis_img)

        # Determine effective representative noise score
        # If smooth regions (like sky or flat walls) exist, their noise is what stock reviewers penalize first.
        if num_smooth_patches >= 5 and smooth_sigma > 0:
            effective_sigma = (smooth_sigma * 0.7) + (immerkaer_sigma * 0.3)
        else:
            effective_sigma = immerkaer_sigma

        # Select thresholds based on mode
        is_paranoid = getattr(self.config, "mode", "production") == "paranoid"
        if is_paranoid:
            lum_review = self.config.noise_sigma_review_paranoid
            lum_high_risk = self.config.noise_sigma_high_risk_paranoid
            chroma_review = self.config.chroma_noise_review_paranoid
            chroma_high_risk = self.config.chroma_noise_high_risk_paranoid
        else:
            lum_review = self.config.noise_sigma_review_production
            lum_high_risk = self.config.noise_sigma_high_risk_production
            chroma_review = self.config.chroma_noise_review_production
            chroma_high_risk = self.config.chroma_noise_high_risk_production

        warnings = []
        status = Status.PASS

        # Evaluate luminance noise
        if effective_sigma >= lum_high_risk:
            status = Status.HIGH_RISK
            warnings.append(f"Severe digital noise / heavy grain detected (noise level: {effective_sigma:.1f}, limit: {lum_high_risk:.1f})")
        elif effective_sigma >= lum_review:
            status = Status.REVIEW
            warnings.append(f"Elevated digital noise detected in flat areas (noise level: {effective_sigma:.1f}, threshold: {lum_review:.1f})")

        # Evaluate chroma (color) noise
        if chroma_noise >= chroma_high_risk:
            status = Status.HIGH_RISK
            warnings.append(f"Severe chrominance / color noise artifacts detected (chroma score: {chroma_noise:.1f}, limit: {chroma_high_risk:.1f})")
        elif chroma_noise >= chroma_review:
            if status != Status.HIGH_RISK:
                status = Status.REVIEW
            warnings.append(f"Noticeable chrominance (color) noise detected (chroma score: {chroma_noise:.1f}, threshold: {chroma_review:.1f})")

        return DetectorResult(
            detector_name="noise",
            status=status,
            score=round(float(effective_sigma), 1),
            warnings=warnings,
            metrics={
                "effective_sigma": round(float(effective_sigma), 2),
                "immerkaer_sigma": round(float(immerkaer_sigma), 2),
                "smooth_patch_sigma": round(float(smooth_sigma), 2) if smooth_sigma > 0 else None,
                "smooth_patches_count": int(num_smooth_patches),
                "chroma_noise": round(float(chroma_noise), 2)
            }
        )

    def _estimate_immerkaer_noise(self, gray: np.ndarray) -> float:
        """
        Fast Noise Variance Estimation using Immerkaer's Laplacian kernel.
        Formula: sigma = sqrt(pi / 2) * (1 / (6 * (W - 2) * (H - 2))) * sum(|conv|)
        """
        h, w = gray.shape
        if h < 5 or w < 5:
            return 0.0

        kernel = np.array([
            [1, -2, 1],
            [-2, 4, -2],
            [1, -2, 1]
        ], dtype=np.float64)

        filtered = cv2.filter2D(gray.astype(np.float64), cv2.CV_64F, kernel)
        # Exclude borders to match (w-2)*(h-2)
        inner = filtered[1:-1, 1:-1]
        total_sum = np.sum(np.abs(inner))
        
        c = np.sqrt(np.pi / 2.0) / (6.0 * (w - 2) * (h - 2))
        sigma = c * total_sum
        return float(sigma)

    def _estimate_smooth_patch_noise(self, gray: np.ndarray, patch_size: int = 32) -> tuple:
        """
        Identifies smooth/flat patches in the image (low edge content) and measures local standard deviation.
        Returns: (average_std_of_smooth_patches, count_of_smooth_patches)
        """
        h, w = gray.shape
        if h < patch_size or w < patch_size:
            return 0.0, 0

        # Compute Sobel gradients to find flat vs detailed regions
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(grad_x, grad_y)

        patch_vars = []
        patch_grads = []

        step_y = patch_size
        step_x = patch_size

        for y in range(0, h - patch_size + 1, step_y):
            for x in range(0, w - patch_size + 1, step_x):
                patch_gray = gray[y:y+patch_size, x:x+patch_size]
                patch_mag = magnitude[y:y+patch_size, x:x+patch_size]

                mean_grad = float(np.mean(patch_mag))
                std_dev = float(np.std(patch_gray))

                patch_grads.append(mean_grad)
                patch_vars.append(std_dev)

        if not patch_grads:
            return 0.0, 0

        # Consider the bottom 20% lowest gradient patches as "smooth regions"
        patch_grads = np.array(patch_grads)
        patch_vars = np.array(patch_vars)
        cutoff = np.percentile(patch_grads, 20)

        smooth_mask = (patch_grads <= cutoff) & (patch_grads < 15.0)  # Must be truly low gradient
        smooth_vars = patch_vars[smooth_mask]

        if len(smooth_vars) == 0:
            return 0.0, 0

        # Use median to avoid outliers
        return float(np.median(smooth_vars)), len(smooth_vars)

    def _estimate_chroma_noise(self, bgr_img: np.ndarray) -> float:
        """
        Measures high-frequency chrominance noise by analyzing residual variations
        in CIELAB color channels (a* and b*) after small spatial smoothing.
        """
        lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2Lab)
        # a* and b* channels
        a_channel = lab[:, :, 1].astype(np.float32)
        b_channel = lab[:, :, 2].astype(np.float32)

        # High-pass filter via difference of Gaussians / median
        blur_a = cv2.GaussianBlur(a_channel, (5, 5), 0)
        blur_b = cv2.GaussianBlur(b_channel, (5, 5), 0)

        diff_a = np.abs(a_channel - blur_a)
        diff_b = np.abs(b_channel - blur_b)

        # High frequency chroma standard deviation
        chroma_residual = np.sqrt(diff_a**2 + diff_b**2)
        return float(np.mean(chroma_residual) * 1.5)
