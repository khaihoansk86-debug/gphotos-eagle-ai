"""
AI Vision & Context Enrichment Engine
Enriches Eagle DAM assets with marketing briefs, 3s TikTok hooks, CapCut editing directions, and customer case study metadata.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from taxonomy_manager import TaxonomyManager

ROOT = Path(__file__).parent


class VisionEnricher:
    def __init__(self, taxonomy_manager: Optional[TaxonomyManager] = None):
        self.taxonomy = taxonomy_manager or TaxonomyManager()

    def generate_brief(
        self,
        asset_label: str,
        kind: str = "photo",
        customer_name: Optional[str] = None,
        photo_url: Optional[str] = None,
        date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates production-grade marketing briefs, CapCut editing instructions, and Eagle annotations.
        """
        project = self.taxonomy.get_active_project()
        pillar = self.taxonomy.match_pillar(asset_label)
        pillar_id = pillar.get("id") if pillar else "treatment"
        pillar_name = pillar.get("folder_name", "") if pillar else "04_B-Roll Liệu trình"

        # Determine 3s Hook based on pillar
        if pillar_id == "hook":
            hook_text = "🎯 3S ĐẦU GIẬT TÍT: 'Bao lâu rồi bạn chưa đi lấy nhân mụn chuẩn y khoa?' (Hiệu ứng Zoom-in cận cảnh cồi mụn)."
            capcut_pacing = "Cắt nhịp nhanh 0.4s - 0.6s ở 3s đầu để tạo visual shock, sau đó chậm dần."
            audio_vibe = "Nhạc ASMR / Trending TikTok giòn tan hoặc âm thanh thỏa mãn thị giác (Satisfying sound)."
        elif pillar_id == "feedback":
            hook_text = "💬 3S ĐẦU CHẠM CẢM XÚC: 'Gương mặt sau 60 phút điều trị mụn tại Khải Hoàn: Khách soi gương cười không ngớt!'"
            capcut_pacing = "Nhịp chậm rãi 1.2s, lia nụ cười và làn da căng bóng mịn màng sau buổi trị liệu."
            audio_vibe = "Nhạc tươi vui, tích cực, acoustic lofi nhẹ nhàng tạo niềm tin (Trust vibe)."
        elif pillar_id == "facility":
            hook_text = "🏥 3S ĐẦU KHẲNG ĐỊNH UY TÍN: 'Không gian chuẩn vô trùng & máy móc công nghệ cao chuyên sâu trị mụn.'"
            capcut_pacing = "Góc quay Cinematic lia chậm sảnh chờ, phòng khám và máy ánh sáng sinh học."
            audio_vibe = "Nhạc sang trọng, hiện đại, phong thái phòng khám y khoa cao cấp."
        elif pillar_id == "video":
            hook_text = "🎬 3S ĐẦU BẮT TREND REELS: Đoạn clip dọc 9:16 sẵn sàng lồng tiếng Voiceover bác sĩ hoặc chèn Text giật tít."
            capcut_pacing = "Kéo thả trực tiếp vào timeline CapCut, cắt bỏ 1s đầu và 1s cuối để nhịp mượt."
            audio_vibe = "Âm thanh môi trường chân thực tại Spa kết hợp nhạc nền bắt tai."
        else:
            hook_text = "💆‍♀️ 3S ĐẦU TẬP TRUNG TAY NGHỀ: 'Từng bước vô trùng tỉ mỉ của Kỹ thuật viên giúp khách an tâm tuyệt đối.'"
            capcut_pacing = "Nhịp vừa phải 0.8s - 1.0s, quay rõ găng tay y tế, sát khuẩn và đắp mặt nạ phục hồi."
            audio_vibe = "Nhạc thư giãn Spa, tiếng nước chảy nhẹ hoặc tiếng máy êm ái."

        # Orientation
        is_vertical = "dọc" in asset_label.lower() or "vertical" in asset_label.lower()
        format_badge = "DỌC 9:16 (Chuẩn TikTok / Reels / Shorts)" if is_vertical else "NGANG (Chuẩn Website / Bài Viết Facebook)"

        # Clean title
        clean_title = asset_label.replace("Ảnh Ảnh", "Ảnh").replace("Video Video", "Video").strip()
        if customer_name and customer_name not in clean_title:
            clean_title = f"{clean_title} – {customer_name}"

        # Tags
        tags = [
            project.get("name", "Khải Hoàn Skincare"),
            pillar.get("tag", "Tư_Liệu_Spa") if pillar else "Tư_Liệu_Spa",
            "Dọc_9:16" if is_vertical else "Ảnh_Ngang"
        ]
        if kind == "video":
            tags.append("Raw_Video_Footage")
        if customer_name:
            safe_cname = "".join([c for c in customer_name.replace(" ", "_") if c.isalnum() or c == "_"])
            tags.append(f"Khách_{safe_cname}")

        # Construct Annotation
        annotation = (
            f"🌿 DỰ ÁN: {project.get('name', 'Khải Hoàn Skincare')}\n"
            f"📁 TRỤ CỘT: {pillar_name}\n"
            f"📐 ĐỊNH DẠNG: {format_badge}\n"
            f"----------------------------------------\n"
            f"{hook_text}\n\n"
            f"🎬 HƯỚNG DẪN DỰNG CAPCUT / TIKTOK:\n"
            f"• Nhịp cắt: {capcut_pacing}\n"
            f"• Gợi ý âm thanh: {audio_vibe}\n"
            f"• Góc text an toàn: Đặt tiêu đề ở giữa khung hình, tránh 120px bên dưới bị icon TikTok che khuất.\n"
        )
        if customer_name:
            annotation += f"\n👥 HỒ SƠ KHÁCH HÀNG: {customer_name}"
        if date_str:
            annotation += f"\n📅 NGÀY ĐIỀU TRỊ: {date_str}"
        if photo_url:
            annotation += f"\n🔗 LINK GỐC GOOGLE PHOTOS: {photo_url}"

        return {
            "title": clean_title,
            "pillar_id": pillar_id,
            "pillar_name": pillar_name,
            "tags": tags,
            "annotation": annotation,
            "is_vertical": is_vertical
        }
