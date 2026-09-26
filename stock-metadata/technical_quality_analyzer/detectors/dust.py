import cv2
import numpy as np
import math
from .base import BaseDetector
from ..models import DetectorResult, Status, Anomaly

class DustDetector(BaseDetector):
    def __init__(self, config, db=None):
        super().__init__(config)
        self.db = db
        
    def analyze(self, original_img, analysis_img, context):
        h, w = analysis_img.shape[:2]
        gray = cv2.cvtColor(analysis_img, cv2.COLOR_BGR2GRAY)
        
        mode = getattr(self.config, "mode", "production")
        min_score = (
            getattr(self.config, "dust_min_score_production", 0.65)
            if mode == "production"
            else getattr(self.config, "dust_min_score_paranoid", 0.45)
        )
        
        # 1. Texture complexity analysis (local standard deviation map)
        gray_f = gray.astype(np.float32)
        blur_mean = cv2.blur(gray_f, (15, 15))
        sq_mean = cv2.blur(gray_f ** 2, (15, 15))
        var = np.maximum(0, sq_mean - blur_mean ** 2)
        std_map = np.sqrt(var)
        
        # Low texture regions (very smooth: sky, flat background, calm water)
        low_texture = std_map < 8.5
        
        # 2. Sky Segmentation (Color + low texture + spatial prior)
        hsv = cv2.cvtColor(analysis_img, cv2.COLOR_BGR2HSV)
        h_chan, s_chan, v_chan = cv2.split(hsv)
        
        blue_sky = (h_chan >= 85) & (h_chan <= 135) & (s_chan > 20) & (v_chan > 70)
        overcast_sky = (s_chan < 50) & (v_chan > 120)
        sky_color = blue_sky | overcast_sky
        sky_mask = (low_texture & sky_color).astype(np.uint8)
        
        kernel_sky = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        sky_mask = cv2.morphologyEx(sky_mask, cv2.MORPH_CLOSE, kernel_sky)
        sky_mask = cv2.morphologyEx(sky_mask, cv2.MORPH_OPEN, kernel_sky)
        
        # 3. Structural edge map (to avoid flagging edges of buildings, twigs, wires)
        edges = cv2.Canny(gray, 40, 100)
        edges_dilated = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
        
        # 4. Local Background Estimation & Dark Spot Detection
        # Background is estimated using a medium-large median filter
        bg_est = cv2.medianBlur(gray, 25).astype(np.float32)
        diff = bg_est - gray_f
        contrast = diff / (bg_est + 1.0)
        
        # Candidate binary mask based on regional expectation
        cand_mask = np.zeros((h, w), dtype=np.uint8)
        
        # Subtle dust visible in smooth sky (3.5% to 35% attenuation)
        cand_mask[(sky_mask > 0) & (contrast > 0.035) & (contrast < 0.38)] = 255
        
        # Moderate dust in low-texture non-sky areas (5% to 38%)
        cand_mask[(sky_mask == 0) & (low_texture) & (contrast > 0.05) & (contrast < 0.38)] = 255
        
        # Outside low-texture: only in paranoid mode, with stricter contrast
        if mode == "paranoid":
            cand_mask[(~low_texture) & (contrast > 0.12) & (contrast < 0.35)] = 255
            
        # Mask out outer frame margins (1.5%)
        margin_x = max(5, int(w * 0.015))
        margin_y = max(5, int(h * 0.015))
        cand_mask[:margin_y, :] = 0
        cand_mask[-margin_y:, :] = 0
        cand_mask[:, :margin_x] = 0
        cand_mask[:, -margin_x:] = 0
        
        contours, _ = cv2.findContours(cand_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        anomalies = []
        high_conf_count = 0
        sky_candidates_count = 0
        
        file_path = context.get("file_path", "")
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Dust candidates in normalized analysis resolution: approx 2.2px to 28px radius
            if not (15 < area < 2500):
                continue
                
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
                
            circularity = 4 * np.pi * (area / (perimeter * perimeter))
            if circularity < 0.55:
                continue
                
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = min(bw, bh) / max(bw, bh)
            if aspect_ratio < 0.45:
                continue
                
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Connected object check: if the spot touches a strong structural edge, ignore
            mask_spot = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(mask_spot, [cnt], -1, 255, -1)
            touches_edge = np.any((mask_spot > 0) & (edges_dilated > 0))
            if touches_edge:
                continue
                
            # Neighborhood texture context: sample annulus around candidate
            pad = int(max(bw, bh) * 2.0)
            nx1, ny1 = max(0, cx - pad), max(0, cy - pad)
            nx2, ny2 = min(w, cx + pad), min(h, cy + pad)
            
            # Annulus patch excluding the candidate's bounding box
            patch = std_map[ny1:ny2, nx1:nx2].copy()
            bx1, by1 = max(0, x - nx1), max(0, y - ny1)
            bx2, by2 = min(patch.shape[1], bx1 + bw), min(patch.shape[0], by1 + bh)
            patch[by1:by2, bx1:bx2] = -1.0
            annulus_vals = patch[patch >= 0]
            surround_std = float(np.mean(annulus_vals)) if len(annulus_vals) > 0 else float(std_map[cy, cx])
            
            in_sky = bool(sky_mask[cy, cx] > 0)
            
            # Texture penalty: sensor dust is not credible in high-noise regions
            if surround_std > 18.0 and not in_sky:
                continue
                
            cnt_contrast = float(np.max(contrast[y:y+bh, x:x+bw]))
            
            # Multi-condition scoring
            # 1. Shape score (combining aspect ratio, rectangular fill, and perimeter circularity)
            circ_score = min(1.0, max(0.0, (circularity - 0.45) / 0.35))
            aspect_score = min(1.0, max(0.0, (aspect_ratio - 0.45) / 0.45))
            rect_fill = area / max(1.0, float(bw * bh))
            fill_score = min(1.0, max(0.0, 1.0 - abs(rect_fill - 0.78) / 0.45))
            shape_score = 0.40 * aspect_score + 0.35 * fill_score + 0.25 * circ_score
            
            # 2. Texture smoothness score (annulus standard deviation)
            text_score = min(1.0, max(0.0, 1.0 - (surround_std / 12.0)))
            
            # 3. Contrast score (typical dust attenuation: 5% - 25%)
            cont_score = min(1.0, max(0.0, 1.0 - abs(cnt_contrast - 0.12) / 0.15))
            
            # 4. Regional prior
            sky_score = 1.0 if in_sky else 0.4
            
            composite_score = 0.30 * text_score + 0.30 * shape_score + 0.20 * cont_score + 0.20 * sky_score
            
            if composite_score < min_score:
                continue
                
            x_norm = round(cx / w, 4)
            y_norm = round(cy / h, 4)
            radius = round(math.sqrt(area / math.pi), 1)
            
            persistent = False
            seen_count = 1
            if self.db:
                persistent, seen_count = self.db.check_and_add(
                    x_norm, y_norm,
                    file_path,
                    self.config.dust_persistence_tolerance,
                    score=composite_score
                )
                
            if persistent:
                high_conf_count += 1
                conf = min(0.98, 0.85 + 0.04 * seen_count)
            else:
                conf = round(composite_score * (0.88 if in_sky else 0.72), 2)
                
            if in_sky:
                sky_candidates_count += 1
                
            desc_parts = ["Sensor dust candidate"]
            if in_sky:
                desc_parts.append("(in sky)")
            if persistent:
                desc_parts.append(f"(confirmed across {seen_count} images)")
                
            anomalies.append(Anomaly(
                x_norm=x_norm,
                y_norm=y_norm,
                width_norm=bw / w,
                height_norm=bh / h,
                description=" ".join(desc_parts),
                confidence=conf,
                persistent=persistent,
                score=round(composite_score, 2),
                in_sky=in_sky,
                radius_px=radius,
                seen_count=seen_count
            ))

        # Status and Warnings evaluation
        status = Status.PASS
        warnings = []
        is_smartphone = bool(context.get("is_smartphone", False))
        
        if high_conf_count > 0:
            status = Status.HIGH_RISK
            label = "sensor defect" if is_smartphone else "sensor dust"
            warnings.append(
                f"High-confidence {label}: {high_conf_count} candidate(s) confirmed across multiple images at identical sensor coordinates."
            )
        elif is_smartphone:
            # Smartphone cameras feature sealed optical modules with no interchangeable lenses.
            # Unconfirmed isolated specks are airborne insects, distant birds, or scene artifacts.
            status = Status.PASS
            if len(anomalies) > 0 and mode == "paranoid":
                warnings.append(
                    f"[PARANOID] {len(anomalies)} isolated airborne/scene candidate(s) noted (smartphone camera, sealed optics)."
                )
        elif sky_candidates_count >= 3:
            status = Status.HIGH_RISK
            warnings.append(
                f"Multiple prominent dust spots detected in sky region ({sky_candidates_count} candidates)."
            )
        elif sky_candidates_count >= 2:
            status = Status.REVIEW
            warnings.append(
                f"Possible sensor dust detected ({sky_candidates_count} candidates in sky region)."
            )
        elif sky_candidates_count == 1:
            if mode == "paranoid":
                status = Status.REVIEW
                warnings.append("[PARANOID] 1 potential dust candidate in sky flagged for visual review.")
            else:
                # Production mode: a single isolated unconfirmed spot is not an automatic rejection
                status = Status.PASS
        elif len(anomalies) > 0:
            if mode == "paranoid":
                status = Status.REVIEW
                warnings.append(f"[PARANOID] {len(anomalies)} potential candidate(s) flagged for visual inspection.")
            else:
                status = Status.PASS
                
        metrics = {
            "candidates": len(anomalies),
            "sky_candidates": sky_candidates_count,
            "persistent": high_conf_count,
            "is_smartphone": is_smartphone,
            "mode": mode,
            "max_score": max([a.score for a in anomalies], default=0.0)
        }
        
        return DetectorResult(
            detector_name="sensor_dust",
            status=status,
            warnings=warnings,
            anomalies=anomalies,
            metrics=metrics
        )
