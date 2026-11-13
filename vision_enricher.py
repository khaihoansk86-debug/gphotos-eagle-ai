"""
Universal AI Vision & Context Enrichment Engine
Enriches Eagle DAM assets with:
1. Star Quality Scoring (1-5 Stars for Eagle DAM) & Sharpness metrics
2. Temporal Journey Phases (Before ➔ In-Process ➔ After)
3. Specialized Technique & Tool detection
4. Tailored 3s TikTok viral hooks, CapCut pacing, and Customer Case Study metadata.
Universal across Spa, Dental Clinic, Culinary F&B, Fitness, and E-commerce.
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
        date_str: Optional[str] = None,
        journey_phase: Optional[str] = None,
        quality_info: Optional[Dict[str, Any]] = None,
        tool_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generates production-grade marketing briefs, CapCut editing instructions, and Eagle annotations.
        """
        project = self.taxonomy.get_active_project()
        domain = project.get("domain", "dermatology_spa")
        pillar = self.taxonomy.match_pillar(asset_label)
        pillar_id = pillar.get("id") if pillar else "treatment"
        pillar_name = pillar.get("folder_name", "") if pillar else "04_B-Roll Liệu trình"

        # 1. Tailor 3s Hook and CapCut Pacing by Journey Phase & Pillar
        if journey_phase == "before":
            hook_text = "🎯 3S ĐẦU GIAI ĐOẠN TRƯỚC (BEFORE): 'Nền da thực tế của khách trước khi làm: Cận cảnh mụn viêm, bít tắc chân lông.'"
            capcut_pacing = "Zoom cận cảnh 120% chậm trong 2s đầu để nhấn mạnh tình trạng ban đầu cần can thiệp."
            audio_vibe = "Âm thanh cảnh báo / Nhạc kịch tính tạo tò mò giải pháp."
        elif journey_phase == "after":
            hook_text = "💬 3S ĐẦU GIAI ĐOẠN KẾT QUẢ (AFTER): 'Sau 60 phút: Làn da dịu đỏ, sạch mụn, khách soi gương nở nụ cười rạng rỡ!'"
            capcut_pacing = "Lia chậm 1.5s cận cảnh gương mặt sáng mịn, chuyển động mượt mà."
            audio_vibe = "Nhạc tươi vui, tích cực, acoustic lofi nhẹ nhàng tạo niềm tin (Social Proof)."
        elif pillar_id == "hook":
            hook_text = "🎯 3S ĐẦU GIẬT TÍT: 'Bao lâu rồi bạn chưa đi lấy nhân mụn chuẩn y khoa?' (Hiệu ứng Zoom-in cận cảnh cồi mụn)."
            capcut_pacing = "Cắt nhịp nhanh 0.4s - 0.6s ở 3s đầu để tạo visual shock, sau đó chậm dần."
            audio_vibe = "Nhạc ASMR / Trending TikTok giòn tan hoặc âm thanh thỏa mãn thị giác (Satisfying sound)."
        elif pillar_id == "feedback":
            hook_text = "💬 3S ĐẦU CHẠM CẢM XÚC: 'Gương mặt sau liệu trình: Khách soi gương cười không ngớt!'"
            capcut_pacing = "Nhịp chậm rãi 1.2s, lia nụ cười và làn da căng bóng mịn màng sau buổi trị liệu."
            audio_vibe = "Nhạc tươi vui, tích cực, acoustic lofi nhẹ nhàng tạo niềm tin (Trust vibe)."
        elif pillar_id == "facility":
            hook_text = "🏥 3S ĐẦU KHẲNG ĐỊNH UY TÍN: 'Không gian chuẩn vô trùng & máy móc công nghệ cao chuyên sâu.'"
            capcut_pacing = "Góc quay Cinematic lia chậm sảnh chờ, phòng dịch vụ và trang thiết bị hiện đại."
            audio_vibe = "Nhạc sang trọng, hiện đại, phong thái phòng khám chuyên nghiệp."
        elif pillar_id == "video":
            hook_text = "🎬 3S ĐẦU BẮT TREND REELS: Đoạn clip dọc 9:16 sẵn sàng lồng tiếng Voiceover chuyên gia hoặc chèn Text giật tít."
            capcut_pacing = "Kéo thả trực tiếp vào timeline CapCut, cắt bỏ 1s đầu và 1s cuối để nhịp mượt."
            audio_vibe = "Âm thanh môi trường chân thực kết hợp nhạc nền bắt tai."
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

        # 2. Collect rich tags
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

        # Quality tag & star
        rating = 3
        if quality_info:
            rating = quality_info.get("rating", 3)
            tags.append(quality_info.get("tag", "Chất_Lượng_Tiêu_Chuẩn"))

        # Journey Phase tag
        phase_label_map = {
            "before": "01_Giai_Đoạn_Trước (Before)",
            "inprocess": "02_Giai_Đoạn_Thực_Hiện (In-Process)",
            "after": "03_Giai_Đoạn_Kết_Quả (After)"
        }
        phase_label = phase_label_map.get(journey_phase, "Tiêu_Chuẩn")
        if journey_phase:
            from journey_classifier import JourneyClassifier
            tags.append(JourneyClassifier.get_phase_tag(journey_phase, domain))

        # Specialized Tool tags
        if tool_tags:
            for tt in tool_tags:
                if tt not in tags:
                    tags.append(tt)

        # 3. Construct rich Eagle Annotation
        star_icons = "⭐" * rating
        quality_str = f"{star_icons} ({rating}/5 Sao - Điểm nét: {quality_info.get('sharpness', 'N/A') if quality_info else 'Chuẩn'})"
        
        annotation = (
            f"🌿 DỰ ÁN: {project.get('name', 'Khải Hoàn Skincare')}\n"
            f"📁 TRỤ CỘT: {pillar_name}\n"
            f"⭐ CHẤT LƯỢNG HÌNH ẢNH: {quality_str}\n"
            f"⏳ TIẾN TRÌNH KHÁCH HÀNG: {phase_label}\n"
            f"📐 ĐỊNH DẠNG: {format_badge}\n"
        )
        if tool_tags:
            annotation += f"🛠️ CÔNG ĐOẠN / DỤNG CỤ: {', '.join(tool_tags)}\n"
        annotation += (
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
            "rating": rating,
            "journey_phase": journey_phase
        }
