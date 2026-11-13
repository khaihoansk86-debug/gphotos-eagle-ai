"""
Burst-Shot & Duplicate Clustering Engine
Detects rapid burst shots and visual duplicates locally via perceptual hashing (dHash) and Laplacian sharpness scoring without consuming AI tokens.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import cv2
import numpy as np


class DuplicateFilter:
    @staticmethod
    def compute_dhash(image_path: str, hash_size: int = 8) -> Optional[int]:
        """
        Computes 64-bit difference hash (dHash) for an image.
        Uses Unicode-safe cv2.imdecode.
        """
        try:
            raw = np.fromfile(image_path, dtype=np.uint8)
            img = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return None
            resized = cv2.resize(img, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
            diff = resized[:, 1:] > resized[:, :-1]
            return sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])
        except Exception:
            return None

    @staticmethod
    def compute_sharpness(image_path: str) -> float:
        """
        Measures image sharpness using the variance of the Laplacian.
        Higher value indicates a sharper, clearer image.
        """
        try:
            raw = np.fromfile(image_path, dtype=np.uint8)
            img = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return 0.0
            return float(cv2.Laplacian(img, cv2.CV_64F).var())
        except Exception:
            return 0.0

    @classmethod
    def cluster_burst_shots(
        cls,
        items: List[Dict[str, Any]],
        hash_threshold: int = 10
    ) -> Dict[str, Any]:
        """
        Groups items into 'Hero' assets and 'Angle Variations' (duplicates).
        Each item is expected to have 'id', 'path', and optional 'date_str'.
        """
        clusters = []
        heroes = []
        variations = []

        # Process each item
        computed_items = []
        for it in items:
            p = it.get("path")
            if p and os.path.exists(p):
                h = cls.compute_dhash(p)
                s = cls.compute_sharpness(p)
                computed_items.append({**it, "dhash": h, "sharpness": s})

        # Cluster by hash proximity
        visited = set()
        for i, item_a in enumerate(computed_items):
            if item_a["id"] in visited or item_a.get("dhash") is None:
                continue

            current_cluster = [item_a]
            visited.add(item_a["id"])

            for j in range(i + 1, len(computed_items)):
                item_b = computed_items[j]
                if item_b["id"] in visited or item_b.get("dhash") is None:
                    continue

                # Calculate hamming distance
                hamming_dist = bin(item_a["dhash"] ^ item_b["dhash"]).count("1")
                if hamming_dist <= hash_threshold:
                    current_cluster.append(item_b)
                    visited.add(item_b["id"])

            if len(current_cluster) > 1:
                # Pick the sharpest one as Hero
                current_cluster.sort(key=lambda x: x.get("sharpness", 0.0), reverse=True)
                hero = current_cluster[0]
                cluster_vars = current_cluster[1:]
                heroes.append(hero["id"])
                for v in cluster_vars:
                    variations.append(v["id"])
                clusters.append({
                    "hero_id": hero["id"],
                    "hero_label": hero.get("label", ""),
                    "variations": [v["id"] for v in cluster_vars],
                    "count": len(current_cluster)
                })
            else:
                heroes.append(item_a["id"])

        return {
            "total_evaluated": len(computed_items),
            "hero_count": len(heroes),
            "variation_count": len(variations),
            "clusters": clusters,
            "hero_ids": set(heroes),
            "variation_ids": set(variations)
        }
