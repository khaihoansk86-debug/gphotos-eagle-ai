"""
Universal Domain Tool & Technique Detection Engine
Extracts visual signatures (color distributions, masks, chromatic variance, local saturation)
and correlates with domain-specific tool definitions (Spa tools, Dental equipment, Culinary techniques).
Universal across industries, fully configurable via project_taxonomy.json.
"""

import os
from typing import List, Dict, Any, Optional
import cv2
import numpy as np


class ToolDetector:
    """
    Analyzes image color features and visual signatures to detect industry tools and techniques:
    - Spa/Skincare: Blue gloves, acne inflammation, Omega light therapy, peel brush, skin texture.
    - Dental: Dental chair, ultrasonic scalers, orthodontic brackets, teeth whitening lamps.
    - Culinary: Flaming wok, pan searing, cocktail shaker, espresso portafilter, knife prep.
    """

    @classmethod
    def analyze_image_signatures(cls, image_path: str) -> Dict[str, float]:
        """
        Extracts foundational visual metrics from an image without external AI APIs:
        - skin_ratio: Proportion of natural human skin tones
        - inflam_ratio: Proportion of inflamed/red skin areas (acne, lesions, flush)
        - medical_blue_ratio: Sterile nitrile gloves, clinic cloth, dental bibs
        - violet_cyan_ratio: Photodynamic therapy (Omega Light, UV sterilizer, laser)
        - warmth_ratio: Warm golden/red tones (pan frying, baked goods, warm interiors)
        - metallic_contrast: High-specular reflections typical of medical/kitchen stainless steel
        """
        metrics = {
            "skin_ratio": 0.0,
            "inflam_ratio": 0.0,
            "medical_blue_ratio": 0.0,
            "violet_cyan_ratio": 0.0,
            "warmth_ratio": 0.0,
            "metallic_specular": 0.0
        }
        if not image_path or not os.path.exists(image_path):
            return metrics

        try:
            raw = np.fromfile(image_path, dtype=np.uint8)
            img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
            if img is None:
                return metrics

            h, w = img.shape[:2]
            total_px = h * w

            # 1. YCrCb for Skin and Inflammation Detection
            ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
            # Standard skin chromaticity boundaries
            skin_mask = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
            metrics["skin_ratio"] = float(np.sum(skin_mask > 0) / total_px)

            # High Cr within skin indicates inflammation / acne redness / irritation
            cr = ycrcb[:, :, 1]
            metrics["inflam_ratio"] = float(np.sum((skin_mask > 0) & (cr > 146)) / total_px)

            # 2. Medical Blue / Cyan Nitrile Gloves (Blue channel dominantly higher than red)
            b, g, r = cv2.split(img)
            blue_mask = (b > 120) & (b > (r.astype(np.int32) + 25)) & (g > 60)
            metrics["medical_blue_ratio"] = float(np.sum(blue_mask) / total_px)

            # 3. HSV for Violet / Cyan / Light Therapy
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            # Violet/Magenta/Cyan range for Omega LED light
            violet_mask = cv2.inRange(hsv, np.array([130, 70, 70]), np.array([170, 255, 255]))
            cyan_mask = cv2.inRange(hsv, np.array([80, 80, 80]), np.array([105, 255, 255]))
            metrics["violet_cyan_ratio"] = float(np.sum((violet_mask > 0) | (cyan_mask > 0)) / total_px)

            # 4. Warmth ratio (Red/Orange/Yellow in HSV: H 0-30 or 160-180, S > 60, V > 70)
            warm_mask = ((hsv[:, :, 0] < 28) | (hsv[:, :, 0] > 165)) & (hsv[:, :, 1] > 60) & (hsv[:, :, 2] > 70)
            metrics["warmth_ratio"] = float(np.sum(warm_mask) / total_px)

            # 5. Metallic / Specular (Very high brightness with low saturation)
            specular = (hsv[:, :, 2] > 230) & (hsv[:, :, 1] < 45)
            metrics["metallic_specular"] = float(np.sum(specular) / total_px)

            return metrics
        except Exception:
            return metrics

    @classmethod
    def detect_techniques(
        cls,
        image_path: str,
        domain: str = "dermatology_spa",
        custom_rules: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Maps visual metrics to specific technique and tool tags for the active industry domain.
        """
        metrics = cls.analyze_image_signatures(image_path)
        detected_tags = []

        if domain == "dermatology_spa":
            # 1. Sterile Gloved Technique / Extractions
            if metrics["medical_blue_ratio"] >= 0.035:
                detected_tags.append("Thao_Tác_Găng_Y_Tế_Vô_Trùng")
                detected_tags.append("Quy_Trình_Chuẩn_Y_Khoa")

            # 2. Acne / Skin Pathology Focus (Hook Macro)
            if metrics["inflam_ratio"] >= 0.04 or (metrics["skin_ratio"] >= 0.48 and metrics["inflam_ratio"] >= 0.02):
                detected_tags.append("Cận_Cảnh_Mụn_Viêm")
                detected_tags.append("Kỹ_Thuật_Lấy_Nhân_Mụn")

            # 3. Omega Light / Photodynamic Therapy
            if metrics["violet_cyan_ratio"] >= 0.06:
                detected_tags.append("Chiếu_Đèn_Sinh_Học_Omega")
                detected_tags.append("Phục_Hồi_Da_Sau_Liệu_Trình")

            # 4. High Tech Spa Equipment / Clinic Environment
            if metrics["skin_ratio"] < 0.15 and metrics["metallic_specular"] >= 0.04:
                detected_tags.append("Máy_Thẩm_Mỹ_Công_Nghệ_Cao")
                detected_tags.append("Phòng_Khám_Vô_Trùng")

            # 5. Mask / Serum Layering
            if metrics["skin_ratio"] >= 0.25 and metrics["metallic_specular"] >= 0.05 and metrics["medical_blue_ratio"] < 0.02:
                detected_tags.append("Đắp_Mặt_Nạ_Dưỡng_Chất")

        elif domain == "dental_clinic":
            # 1. Clinic Gloves / Instrument Operation
            if metrics["medical_blue_ratio"] >= 0.03:
                detected_tags.append("Bác_Sĩ_Thao_Tác_Nha_Khoa")
            # 2. Specular Highlights on Teeth / Metal Scaler / Brackets
            if metrics["metallic_specular"] >= 0.05:
                detected_tags.append("Dụng_Cụ_Nha_Khoa_Chuyên_Dụng")
            # 3. Clean Teeth Whitening / Mirror Reveal
            if metrics["skin_ratio"] >= 0.20 and metrics["inflam_ratio"] < 0.015:
                detected_tags.append("Nụ_Cười_Răng_Trắng_Sáng")

        elif domain == "food_beverage":
            # 1. Hot Pan / Flaming Wok / Grilling
            if metrics["warmth_ratio"] >= 0.25:
                detected_tags.append("Chế_Biến_Nhiệt_Nóng_Hổi")
                detected_tags.append("Món_Nướng_Xào_Signature")
            # 2. Plating & Food Presentation
            if metrics["metallic_specular"] >= 0.06 and metrics["warmth_ratio"] >= 0.10:
                detected_tags.append("Bày_Đĩa_Trang_Trí_Ẩm_Thực")

        return detected_tags
