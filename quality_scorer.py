"""
Universal Media Quality & Sharpness Scoring Engine
Evaluates visual clarity, Laplacian variance (blur), exposure/brightness balance, and dynamic contrast.
Assigns 1-5 Star Ratings directly compatible with Eagle DAM.
Universal across Spa, Dental, Culinary F&B, Fitness, and E-commerce.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import cv2
import numpy as np


class QualityScorer:
    """
    Evaluates image and video thumbnail quality:
    - Laplacian variance: Blur detection & sharpness.
    - Exposure balance: Detection of underexposed (too dark) or overexposed (blown out) frames.
    - Contrast distribution: Dynamic range of tones.
    Outputs:
    - rating: 1 to 5 (Integer, standard Eagle DAM rating)
    - quality_score: 0 to 100 float
    - quality_tier: 'hero_master', 'usable_broll', 'standard', 'suboptimal', 'blurry'
    - tag: Corresponding semantic tag
    """

    @classmethod
    def evaluate_image(cls, image_path: str) -> Dict[str, Any]:
        default_res = {
            "rating": 3,
            "quality_score": 60.0,
            "sharpness": 100.0,
            "brightness": 128.0,
            "contrast": 50.0,
            "quality_tier": "standard",
            "tag": "Chất_Lượng_3_Sao_Tiêu_Chuẩn"
        }
        if not image_path or not os.path.exists(image_path):
            return default_res

        try:
            raw = np.fromfile(image_path, dtype=np.uint8)
            img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
            if img is None:
                return default_res

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 1. Sharpness via Laplacian Variance
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            # 2. Brightness & Exposure check
            brightness = float(np.mean(gray))
            dark_pixels = np.sum(gray < 25) / gray.size
            blown_pixels = np.sum(gray > 240) / gray.size

            # Exposure penalty: heavily penalized if >30% underexposed or >20% blown out
            exposure_penalty = 0.0
            if dark_pixels > 0.35:
                exposure_penalty += 30.0
            elif dark_pixels > 0.20:
                exposure_penalty += 15.0

            if blown_pixels > 0.25:
                exposure_penalty += 30.0
            elif blown_pixels > 0.15:
                exposure_penalty += 15.0

            # 3. Contrast (Standard deviation of luminance)
            contrast = float(np.std(gray))

            # 4. Composite Quality Score (0 to 100)
            # Sharpness contribution (logarithmic scaling: 50 is soft, 250 is sharp, 600+ is pin-sharp)
            if sharpness <= 30.0:
                s_score = max(5.0, sharpness * 0.8)
            elif sharpness <= 150.0:
                s_score = 30.0 + (sharpness - 30.0) * (30.0 / 120.0)
            elif sharpness <= 500.0:
                s_score = 60.0 + (sharpness - 150.0) * (30.0 / 350.0)
            else:
                s_score = min(100.0, 90.0 + (sharpness - 500.0) * 0.02)

            contrast_score = min(100.0, (contrast / 65.0) * 100.0)
            composite = (s_score * 0.65) + (contrast_score * 0.35) - exposure_penalty
            quality_score = max(5.0, min(100.0, round(composite, 1)))

            # 5. Map to 1-5 Star Rating in Eagle DAM
            if quality_score >= 82.0 and sharpness >= 200.0:
                rating = 5
                tier = "hero_master"
                tag = "Chất_Lượng_5_Sao_Hero"
            elif quality_score >= 68.0 and sharpness >= 100.0:
                rating = 4
                tier = "usable_broll"
                tag = "Chất_Lượng_4_Sao_Sắc_Nét"
            elif quality_score >= 48.0 and sharpness >= 45.0:
                rating = 3
                tier = "standard"
                tag = "Chất_Lượng_3_Sao_Tiêu_Chuẩn"
            elif quality_score >= 30.0:
                rating = 2
                tier = "suboptimal"
                tag = "Chất_Lượng_2_Sao_Hơi_Mờ"
            else:
                rating = 1
                tier = "blurry"
                tag = "Chất_Lượng_1_Sao_Nhòe_Nét"

            return {
                "rating": rating,
                "quality_score": quality_score,
                "sharpness": round(sharpness, 1),
                "brightness": round(brightness, 1),
                "contrast": round(contrast, 1),
                "quality_tier": tier,
                "tag": tag
            }
        except Exception:
            return default_res
