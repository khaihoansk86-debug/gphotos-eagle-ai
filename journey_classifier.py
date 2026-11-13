"""
Universal Temporal Journey & Phase Classification Engine
Classifies media into chronological stages: Before (Giai đoạn Trước) ➔ In-Process (Đang Thực Hiện) ➔ After (Sau / Kết Quả).
Works across Spa/Skincare, Dental Clinics, F&B Culinary, Fitness, and E-commerce.
"""

import os
import re
from typing import List, Dict, Any, Optional
from pathlib import Path


class JourneyClassifier:
    """
    Classifies media into journey phases:
    - 'before': Initial state, diagnosis, consultation, raw ingredients, starting form.
    - 'inprocess': Active operation, doctor/chef/trainer technique, tools, procedure.
    - 'after': Final outcome, mirror reveal, plated dish, customer smile & satisfaction.
    """

    @staticmethod
    def parse_timestamp_from_name(name: str) -> Optional[int]:
        """
        Extracts approximate epoch seconds or comparable integer from name strings:
        e.g. 'Ảnh – Dọc – 112747 12 thg 11, 2026' or '11:27:47 12 thg 11, 2026'
        """
        if not name:
            return None
        # Match time HHMMSS or HH:MM:SS
        time_match = re.search(r"(\d{2})[:\s]?(\d{2})[:\s]?(\d{2})", name)
        # Match date DD thg MM, YYYY
        date_match = re.search(r"(\d{1,2})\s+thg\s+(\d{1,2}),?\s+(\d{4})", name)

        if time_match and date_match:
            hh, mm, ss = [int(x) for x in time_match.groups()]
            dd, month, yyyy = [int(x) for x in date_match.groups()]
            # Create a comparable numerical sort key: YYYYMMDDHHMMSS
            return yyyy * 10000000000 + month * 100000000 + dd * 1000000 + hh * 10000 + mm * 100 + ss
        return None

    @classmethod
    def classify_session_items(
        cls,
        items: List[Dict[str, Any]],
        domain: str = "dermatology_spa"
    ) -> List[Dict[str, Any]]:
        """
        Takes a list of items belonging to one session/customer, sorts chronologically,
        and assigns 'phase' ('before', 'inprocess', 'after') and domain-aware tags.
        """
        if not items:
            return []

        # Sort items chronologically
        def get_sort_key(it):
            name = it.get("name", "")
            ts = cls.parse_timestamp_from_name(name)
            if ts is not None:
                return ts
            return it.get("modificationTime", 0)

        sorted_items = sorted(items, key=get_sort_key)
        n = len(sorted_items)

        # Single or 2 items edge case
        if n == 1:
            return [{**sorted_items[0], "journey_phase": "inprocess", "phase_tag": cls.get_phase_tag("inprocess", domain)}]
        elif n == 2:
            return [
                {**sorted_items[0], "journey_phase": "before", "phase_tag": cls.get_phase_tag("before", domain)},
                {**sorted_items[1], "journey_phase": "after", "phase_tag": cls.get_phase_tag("after", domain)}
            ]

        # Calculate phase thresholds:
        # First 15% (min 1) = before
        # Last 15% (min 1) = after
        # Middle 70% = inprocess
        before_cutoff = max(1, int(round(n * 0.18)))
        after_cutoff = max(before_cutoff + 1, n - max(1, int(round(n * 0.18))))

        annotated = []
        for idx, it in enumerate(sorted_items):
            if idx < before_cutoff:
                phase = "before"
            elif idx >= after_cutoff:
                phase = "after"
            else:
                phase = "inprocess"

            annotated.append({
                **it,
                "journey_phase": phase,
                "phase_tag": cls.get_phase_tag(phase, domain)
            })

        return annotated

    @staticmethod
    def get_phase_tag(phase: str, domain: str = "dermatology_spa") -> str:
        domain_tags = {
            "dermatology_spa": {
                "before": "Giai_Đoạn_Trước_Liệu_Trình",
                "inprocess": "Giai_Đoạn_Đang_Thao_Tác",
                "after": "Giai_Đoạn_Sau_Kết_Quả"
            },
            "dental_clinic": {
                "before": "Giai_Đoạn_Trước_Chỉnh_Nha",
                "inprocess": "Giai_Đoạn_Bác_Sĩ_Thao_Tác",
                "after": "Giai_Đoạn_Nụ_Cười_Hoàn_Thiện"
            },
            "food_beverage": {
                "before": "Giai_Đoạn_Nguyên_Liệu_Sơ_Chế",
                "inprocess": "Giai_Đoạn_Nấu_Nướng_Pha_Chế",
                "after": "Giai_Đoạn_Thành_Phẩm_Bày_Bàn"
            }
        }
        return domain_tags.get(domain, domain_tags["dermatology_spa"]).get(phase, f"Giai_Đoạn_{phase.title()}")
