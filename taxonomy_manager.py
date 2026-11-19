"""
Dynamic Project Taxonomy Manager
Handles configurable content pillars, Eagle folder structures, and marketing taxonomies across different business domains (Spa, Dental, F&B, etc.).
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from eagle_client import EagleClient

ROOT = Path(__file__).parent
TAXONOMY_FILE = ROOT / "project_taxonomy.json"


class TaxonomyManager:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or TAXONOMY_FILE
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Taxonomy config not found at {self.config_path}")
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def save(self):
        self.config_path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def list_projects(self) -> List[Dict[str, Any]]:
        projects = []
        active_id = self.data.get("active_project", "khaihoan_skincare")
        for pid, p in self.data.get("projects", {}).items():
            projects.append({
                "id": pid,
                "name": p.get("name"),
                "domain": p.get("domain"),
                "is_active": pid == active_id,
                "pillar_count": len(p.get("pillars", []))
            })
        return projects

    def get_active_project(self) -> Dict[str, Any]:
        active_id = self.data.get("active_project", "khaihoan_skincare")
        return self.data.get("projects", {}).get(active_id, {})

    def set_active_project(self, project_id: str) -> Dict[str, Any]:
        if project_id not in self.data.get("projects", {}):
            raise ValueError(f"Project '{project_id}' does not exist in taxonomy config.")
        self.data["active_project"] = project_id
        self.save()
        return self.get_active_project()

    def register_project(self, project_id: str, name: str, domain: str, pillars: List[Dict[str, Any]], tag_groups: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        projects = self.data.setdefault("projects", {})
        projects[project_id] = {
            "name": name,
            "domain": domain,
            "pillars": pillars or [],
            "tag_groups": tag_groups or []
        }
        self.save()
        return projects[project_id]

    def get_pillars(self) -> List[Dict[str, Any]]:
        return self.get_active_project().get("pillars", [])

    def match_pillar(self, label: str, visual_tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Matches an asset's label and visual tags against the active project's pillars.
        Returns the best-matching pillar.
        """
        pillars = self.get_pillars()
        text = (label or "").lower()
        tags_text = " ".join([t.lower() for t in (visual_tags or [])])
        full_text = f"{text} {tags_text}"

        # 1. Raw video rule
        if "video" in text or "clip" in text:
            for p in pillars:
                if p.get("id") == "video":
                    return p

        # 2. Check keyword matches with priority
        best_match = None
        max_score = 0
        for p in pillars:
            score = 0
            for kw in p.get("visual_keywords", []):
                if kw.lower() in full_text:
                    score += 1
            if score > max_score:
                max_score = score
                best_match = p

        # Default fallback to treatment/b-roll or first pillar if not matched
        return best_match or (pillars[0] if pillars else None)

    def sync_folders_to_eagle(self, eagle_client: Optional[EagleClient] = None) -> Dict[str, str]:
        """
        Ensures all content pillar folders exist in the active Eagle library.
        Returns a mapping of {pillar_id: eagle_folder_id}.
        """
        client = eagle_client or EagleClient()
        if not client.is_connected():
            return {}

        pillars = self.get_pillars()
        folder_mapping = {}

        for pillar in pillars:
            name = pillar.get("folder_name")
            if not name:
                continue
            folder_id = client.get_or_create_folder(name)
            folder_mapping[pillar.get("id")] = folder_id

        # Also create Tag Groups if defined and supported
        tag_groups = self.get_active_project().get("tag_groups", [])
        if tag_groups and hasattr(client, "create_tag_groups"):
            try:
                client.create_tag_groups(tag_groups)
            except Exception:
                pass

        return folder_mapping
