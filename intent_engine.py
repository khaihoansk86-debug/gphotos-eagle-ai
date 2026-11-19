"""
Intent Resolution & Skill Guidance Engine
Introspects user natural language queries and maps them to standard MCP tool sequences,
active business domains, skill execution plans, and architectural invariants.
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

SKILLS_DIR = Path(r"D:\shared_skills\skills")
LOCAL_SKILLS_DIR = Path(__file__).parent

class IntentEngine:
    DOMAINS = {
        "khaihoan_skincare": {
            "name": "Khải Hoàn Skincare & Spa",
            "keywords": ["spa", "skincare", "mụn", "nặn mụn", "chăm sóc da", "phục hồi", "khải hoàn", "da", "ktv", "liệu trình"]
        },
        "fb_culinary": {
            "name": "Nhà Hàng & F&B Ẩm Thực",
            "keywords": ["f&b", "ẩm thực", "nhà hàng", "món ăn", "nấu", "bếp", "đầu bếp", "cafe", "nướng", "pha chế", "menu"]
        },
        "fitness_gym": {
            "name": "Phòng Gym & Thể Hình Pro",
            "keywords": ["gym", "thể hình", "fitness", "tạ", "bài tập", "pt", "huấn luyện viên", "cơ bắp", "cardio", "workout"]
        },
        "nha_khoa_clinic": {
            "name": "Nha Khoa & Răng Hàm Mặt",
            "keywords": ["nha khoa", "răng", "niềng răng", "implant", "bọc sứ", "nụ cười", "tẩy trắng", "dental"]
        }
    }

    INTENTS = {
        "fix_thumbnails": {
            "title": "Khắc Phục Lỗi Mắt Gạch Chéo / Thumbnail Eagle Bị Lỗi",
            "keywords": ["mắt gạch chéo", "gạch chéo", "mất hình", "lỗi ảnh", "broken", "thumbnail", "không hiện", "không thấy hình", "dấu x"],
            "skill": "universal-media-classifier",
            "tools": [
                {
                    "step": 1,
                    "tool": "fix_eagle_thumbnails",
                    "args": {},
                    "purpose": "Đồng bộ 100% tên file vật lý trên ổ đĩa khớp chính xác với metadata.json['name'] + '.' + ext"
                }
            ],
            "invariants": [
                "Hợp đồng tên file vật lý: Disk filename == metadata.json['name'] + '.' + ext",
                "Lọc sạch toàn bộ ký tự cấm của Windows/macOS: [:*?\"<>|/\\\\]"
            ]
        },
        "treatment_sessions": {
            "title": "Gom Cụm Phiên Điều Trị 35 Phút & Lan Truyền Điểm Neo Khách Hàng",
            "keywords": ["phiên", "ca", "buổi", "khách", "before", "after", "trước sau", "hành trình", "liệu trình", "session", "cluster", "gom cụm", "35 phút"],
            "skill": "universal-media-classifier",
            "tools": [
                {
                    "step": 1,
                    "tool": "cluster_treatment_sessions",
                    "args": {"max_gap_minutes": 35},
                    "purpose": "Gom các tư liệu trong khoảng thời gian <= 35 phút thành từng ca và phân chia Before/In-Process/After (0.05s, 0% RAM)"
                },
                {
                    "step": 2,
                    "tool": "reorganize_eagle_tree",
                    "args": {},
                    "purpose": "Cập nhật hồ sơ ca khách hàng con MP_<CUST> và MV_<CUST> vào sơ đồ cây 2 nhánh"
                }
            ],
            "invariants": [
                "Cửa sổ thời gian chuẩn: 35 phút (2.100 giây)",
                "Tự động chia tỷ lệ 25% đầu: Before, 50% giữa: In-Process, 25% cuối: After",
                "Tuyệt đối không tải mô hình AI khuôn mặt nặng nề để bảo vệ RAM máy"
            ]
        },
        "video_reels_tiktok": {
            "title": "Phân Tích Video Dọc 9:16 (Hook 3s, Phụ Đề Whisper, ASMR >4.5kHz)",
            "keywords": ["video", "clip", "reels", "tiktok", "hook", "hook 3s", "asmr", "whisper", "lời thoại", "giọng nói", "câm", "không tiếng", "b-roll", "dọc"],
            "skill": "universal-media-classifier",
            "tools": [
                {
                    "step": 1,
                    "tool": "analyze_video_asset",
                    "args": {"video_path": "<ASSET_ID_OR_PATH>"},
                    "purpose": "Tua nhanh 5s/10s bóc keyframes, nhận diện giọng nói tiếng Việt bằng Faster-Whisper và đo dải tần ASMR >4.5kHz"
                },
                {
                    "step": 2,
                    "tool": "enrich_and_sync_eagle",
                    "args": {},
                    "purpose": "Ghi thông tin timeline, Hook 3s và chỉ dẫn CapCut vào Annotation và Tag của Eagle DAM"
                }
            ],
            "invariants": [
                "Toàn bộ video dọc 9:16 bắt buộc xếp vào nhánh '🎬 2. KHO VIDEO CLIPS'",
                "Không để video lọt vào nhánh '📸 1. KHO HÌNH ẢNH'",
                "Đo tần số ASMR ở dải tần sắc bén >4.5kHz (tiếng kim loại, sủi bọt, gắp cồi mụn)"
            ]
        },
        "hero_burst": {
            "title": "Lọc Ảnh 5 Sao Hero & Chụp Liên Tục (Burst Laplacian)",
            "keywords": ["hero", "5 sao", "5 star", "ảnh nét", "nét nhất", "chụp liên tiếp", "burst", "trùng lặp", "laplacian", "độ nét"],
            "skill": "universal-media-classifier",
            "tools": [
                {
                    "step": 1,
                    "tool": "filter_burst_duplicates",
                    "args": {"threshold": 80},
                    "purpose": "Đo độ biến thiên Laplacian tìm ảnh sắc nét nhất làm ảnh Hero và gom ảnh phụ"
                },
                {
                    "step": 2,
                    "tool": "reorganize_eagle_tree",
                    "args": {},
                    "purpose": "Đưa ảnh nét nhất vào folder '⭐ 1.1 Ảnh 5 Sao Hero (Quảng Cáo & Bìa Bài Viết)'"
                }
            ],
            "invariants": [
                "Không dùng token AI để so sánh ảnh chùm; sử dụng OpenCV Laplacian variance",
                "Chỉ gán ⭐⭐⭐⭐⭐ Hero cho ảnh đạt điểm nét cao nhất trong chuỗi"
            ]
        },
        "switch_domain": {
            "title": "Chuyển Đổi Ngữ Cảnh Ngành Nghề Kinh Doanh",
            "keywords": ["chuyển ngành", "đổi ngành", "dự án", "ngành nghề", "spa", "nha khoa", "nhà hàng", "f&b", "gym", "phòng tập"],
            "skill": "universal-media-classifier",
            "tools": [
                {
                    "step": 1,
                    "tool": "switch_taxonomy_project",
                    "args": {"project_id": "<PROJECT_ID>"},
                    "purpose": "Kích hoạt bộ Content Pillars, Tag Groups và quy tắc nhận diện cho ngành nghề mới"
                },
                {
                    "step": 2,
                    "tool": "reorganize_eagle_tree",
                    "args": {},
                    "purpose": "Đồng bộ lại cấu trúc thư mục Eagle DAM tương ứng với ngành nghề mới"
                }
            ],
            "invariants": [
                "Luôn giữ vững cấu trúc 2 nhánh gốc: Kho Hình Ảnh và Kho Video Clips",
                "Cập nhật Content Pillars và từ khóa nhận diện phù hợp từng ngành"
            ]
        },
        "read_skill_guide": {
            "title": "Tra Cứu & Học Tài Liệu Kỹ Năng (Skill Guidance)",
            "keywords": ["skill", "kỹ năng", "hướng dẫn", "rule", "nguyên tắc", "tài liệu", "đọc skill", "quy trình"],
            "skill": "universal-media-classifier",
            "tools": [
                {
                    "step": 1,
                    "tool": "get_skill_guide",
                    "args": {"skill_name": "universal-media-classifier"},
                    "purpose": "Đọc toàn bộ nội dung hướng dẫn chuẩn, sơ đồ luồng và quy tắc vận hành của kỹ năng"
                }
            ],
            "invariants": [
                "Agent phải đọc kỹ năng trước khi thực hiện các tác vụ phân loại phức tạp"
            ]
        },
        "general_classification": {
            "title": "Quy Trình Phân Loại & Tối Ưu Hóa Toàn Diện Vào Eagle DAM",
            "keywords": ["phân loại", "phân loại ảnh", "sắp xếp", "đồng bộ", "eagle", "quản lý kho", "dọn dẹp", "tổ chức"],
            "skill": "universal-media-classifier",
            "tools": [
                {
                    "step": 1,
                    "tool": "switch_taxonomy_project",
                    "args": {"project_id": "<PROJECT_ID>"},
                    "purpose": "Xác nhận đúng ngữ cảnh ngành nghề mục tiêu"
                },
                {
                    "step": 2,
                    "tool": "cluster_treatment_sessions",
                    "args": {"max_gap_minutes": 35},
                    "purpose": "Gom cụm ca điều trị và lan truyền điểm neo khách hàng (0.05s)"
                },
                {
                    "step": 3,
                    "tool": "filter_burst_duplicates",
                    "args": {},
                    "purpose": "Chấm điểm Laplacian lọc ảnh 5 sao Hero"
                },
                {
                    "step": 4,
                    "tool": "reorganize_eagle_tree",
                    "args": {},
                    "purpose": "Tái thiết lập cấu trúc 2 nhánh 100% rạch ròi tại D:\\test.library"
                },
                {
                    "step": 5,
                    "tool": "fix_eagle_thumbnails",
                    "args": {},
                    "purpose": "Đảm bảo 100% thumbnail hiển thị hoàn hảo, không có mắt gạch chéo"
                }
            ],
            "invariants": [
                "Sơ đồ cây 2 nhánh rạch ròi 100%: 📸 1. KHO HÌNH ẢNH vs 🎬 2. KHO VIDEO CLIPS",
                "Hợp đồng tên file vật lý: disk filename == metadata name + ext",
                "Tuyệt đối không chạy AI token nặng trên chuỗi ảnh chùm"
            ]
        }
    }

    @classmethod
    def detect_domain(cls, query: str) -> str:
        q = (query or "").lower()
        for dom_id, info in cls.DOMAINS.items():
            for kw in info["keywords"]:
                if kw in q:
                    return dom_id
        return "khaihoan_skincare"

    @classmethod
    def resolve_intent(cls, user_query: str) -> Dict[str, Any]:
        """
        Analyzes user query and maps to matching intent, recommended skill,
        ordered tool call sequence, and architectural invariants.
        """
        q = (user_query or "").strip().lower()
        domain_id = cls.detect_domain(q)
        domain_info = cls.DOMAINS.get(domain_id, cls.DOMAINS["khaihoan_skincare"])

        matched_key = "general_classification"
        best_score = 0

        for key, conf in cls.INTENTS.items():
            score = 0
            for kw in conf["keywords"]:
                if kw in q:
                    score += len(kw)  # longer phrase matches get higher weight
            if score > best_score:
                best_score = score
                matched_key = key

        matched_intent = cls.INTENTS[matched_key]

        # Customize project_id in tool args if needed
        plan = []
        for step_info in matched_intent["tools"]:
            tool_call = {
                "step": step_info["step"],
                "tool": step_info["tool"],
                "args": dict(step_info["args"]),
                "purpose": step_info["purpose"]
            }
            if tool_call["args"].get("project_id") == "<PROJECT_ID>":
                tool_call["args"]["project_id"] = domain_id
            plan.append(tool_call)

        return {
            "status": "success",
            "user_query": user_query,
            "detected_intent": matched_key,
            "intent_title": matched_intent["title"],
            "target_domain": {
                "id": domain_id,
                "name": domain_info["name"]
            },
            "recommended_skill": matched_intent["skill"],
            "tool_execution_plan": plan,
            "invariants": matched_intent["invariants"],
            "best_practice_guidance": (
                f"Đã xác định nhu cầu: '{matched_intent['title']}' cho ngành '{domain_info['name']}'. "
                f"Agent hãy thực thi tuần tự {len(plan)} bước trên qua MCP Endpoint để đảm bảo năng lực tối đa và độ chính xác 100%."
            )
        }

    @classmethod
    def list_skills(cls) -> List[Dict[str, Any]]:
        """Scans registered skills and returns their catalog metadata."""
        skills = []
        # 1. Search shared_skills directory
        if SKILLS_DIR.exists():
            for sdir in SKILLS_DIR.iterdir():
                if sdir.is_dir():
                    mf = sdir / "SKILL.md"
                    if mf.exists():
                        skills.append(cls._parse_skill_md(sdir.name, mf))

        # 2. Local repo skill
        repo_skill = LOCAL_SKILLS_DIR / "SKILL.md"
        if repo_skill.exists() and not any(s["name"] == "universal-media-classifier" for s in skills):
            skills.append(cls._parse_skill_md("universal-media-classifier", repo_skill))

        return skills

    @classmethod
    def _parse_skill_md(cls, default_name: str, path: Path) -> Dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        name = default_name
        desc = ""
        arg_hint = ""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                front = parts[1]
                for line in front.splitlines():
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()
                    elif line.startswith("argument-hint:"):
                        arg_hint = line.split(":", 1)[1].strip()
        return {
            "name": name,
            "description": desc or "No description provided",
            "argument_hint": arg_hint,
            "path": str(path),
            "size_bytes": len(text)
        }

    @classmethod
    def get_skill_content(cls, skill_name: str) -> Optional[str]:
        target = SKILLS_DIR / skill_name / "SKILL.md"
        if target.exists():
            return target.read_text(encoding="utf-8")
        local_target = LOCAL_SKILLS_DIR / "SKILL.md"
        if local_target.exists():
            return local_target.read_text(encoding="utf-8")
        return None

    @classmethod
    def register_or_update_skill(cls, skill_name: str, description: str, content: str) -> Dict[str, Any]:
        """Dynamically registers or updates a skill in the shared skills repository."""
        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '', skill_name.strip().lower())
        if not clean_name:
            raise ValueError("Invalid skill name")
        target_dir = SKILLS_DIR / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)
        skill_file = target_dir / "SKILL.md"

        # Ensure YAML frontmatter
        if not content.startswith("---"):
            full_content = (
                f"---\n"
                f"name: {clean_name}\n"
                f"description: >\n"
                f"  {description.strip()}\n"
                f"---\n\n"
                f"{content.strip()}\n"
            )
        else:
            full_content = content

        skill_file.write_text(full_content, encoding="utf-8")
        return {
            "status": "registered",
            "skill_name": clean_name,
            "path": str(skill_file),
            "size": len(full_content)
        }
