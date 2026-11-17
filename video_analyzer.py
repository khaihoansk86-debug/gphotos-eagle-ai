"""
Universal Video Intelligence & Timeline Breakdown Engine
Simulates human video scrubbing at 5s - 10s intervals to detect visual highlights,
extracts and analyzes audio tracks (speech / dialogue vs ASMR tool sounds vs ambient music),
and compiles structured CapCut editing directions and Eagle DAM annotations.
Universal across Spa/Skincare, Dental Clinic, Culinary F&B, Fitness, and E-commerce.
"""

import os
import re
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

try:
    import imageio_ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False

from quality_scorer import QualityScorer
from tool_detector import ToolDetector


class VideoAnalyzer:
    """
    Deep Video Content Analyzer:
    - Interval keyframe inspection (simulating human fast-forwarding every 5s / 10s).
    - Audio separation and timeline sound analysis (Speech/Voice vs ASMR vs Music vs Silence).
    - Golden Moment / Highlight segment detection for CapCut / TikTok 3s Hook retention.
    - Rich Markdown Annotation for Eagle DAM right panel.
    """

    @classmethod
    def get_ffmpeg_exe(cls) -> Optional[str]:
        if FFMPEG_AVAILABLE:
            try:
                return imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                pass
        # Fallback to local CapCut ffmpeg if present
        capcut_path = r"C:\Users\Admin\AppData\Local\CapCut\Apps\8.1.1.3417\ffmpeg.exe"
        if os.path.exists(capcut_path):
            return capcut_path
        return None

    @classmethod
    def probe_video(cls, video_path: str) -> Dict[str, Any]:
        """
        Extracts foundational technical metrics of the video.
        """
        info = {
            "valid": False,
            "duration": 0.0,
            "fps": 0.0,
            "total_frames": 0,
            "width": 0,
            "height": 0,
            "is_vertical": True,
            "aspect_ratio_str": "Dọc 9:16 (TikTok/Reels)",
            "has_audio": False
        }
        if not video_path or not os.path.exists(video_path):
            return info

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return info

            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0.0
            cap.release()

            is_vertical = h > w
            ratio_str = "Dọc 9:16 (Chuẩn TikTok / Reels / Shorts)" if is_vertical else "Ngang 16:9 (Chuẩn YouTube / Website)"

            # Check audio stream via ffmpeg probe if available
            has_audio = False
            ffmpeg_exe = cls.get_ffmpeg_exe()
            if ffmpeg_exe:
                try:
                    res = subprocess.run([ffmpeg_exe, "-i", video_path], capture_output=True, text=True, timeout=5)
                    probe_txt = res.stdout + res.stderr
                    has_audio = "Audio:" in probe_txt
                except Exception:
                    pass

            return {
                "valid": True,
                "duration": round(duration, 2),
                "fps": round(fps, 1),
                "total_frames": total_frames,
                "width": w,
                "height": h,
                "is_vertical": is_vertical,
                "aspect_ratio_str": ratio_str,
                "has_audio": has_audio
            }
        except Exception:
            return info

    @classmethod
    def extract_audio_track(cls, video_path: str) -> Optional[str]:
        """
        Extracts mono 16kHz WAV audio to a temporary file.
        Returns the path to the extracted WAV file, or None if no audio exists.
        """
        ffmpeg_exe = cls.get_ffmpeg_exe()
        if not ffmpeg_exe or not os.path.exists(video_path):
            return None

        try:
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

            cmd = [ffmpeg_exe, "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", tmp_wav]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and os.path.exists(tmp_wav) and os.path.getsize(tmp_wav) > 1000:
                return tmp_wav
            if os.path.exists(tmp_wav):
                os.remove(tmp_wav)
            return None
        except Exception:
            return None

    @classmethod
    def analyze_audio_timeline(
        cls,
        wav_path: Optional[str],
        duration: float,
        interval_seconds: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Analyzes audio slice by slice matching the video scrubbing intervals:
        Identifies Speech/Dialogue, ASMR tool sounds, Music/Ambient, or Silence.
        """
        num_intervals = max(1, int(np.ceil(duration / interval_seconds)))
        results = []

        if not wav_path or not os.path.exists(wav_path):
            for i in range(num_intervals):
                t_start = i * interval_seconds
                t_end = min((i + 1) * interval_seconds, duration)
                results.append({
                    "start": t_start,
                    "end": t_end,
                    "rms": 0.0,
                    "sound_type": "mute",
                    "label": "🔇 Video không có tiếng",
                    "has_speech": False,
                    "is_asmr": False
                })
            return results

        try:
            import wave
            with wave.open(wav_path, "rb") as wf:
                sr = wf.getframerate()
                raw = wf.readframes(wf.getnframes())
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            audio_len = len(audio)
            samples_per_interval = int(interval_seconds * sr)

            for i in range(num_intervals):
                t_start = round(i * interval_seconds, 1)
                t_end = round(min((i + 1) * interval_seconds, duration), 1)

                idx_start = i * samples_per_interval
                idx_end = min((i + 1) * samples_per_interval, audio_len)
                chunk = audio[idx_start:idx_end]

                if len(chunk) < 256:
                    results.append({
                        "start": t_start,
                        "end": t_end,
                        "rms": 0.0,
                        "sound_type": "silence",
                        "label": "🔇 Yên tĩnh",
                        "has_speech": False,
                        "is_asmr": False
                    })
                    continue

                rms = float(np.sqrt(np.mean(chunk ** 2)))

                # Frequency spectrum analysis
                fft = np.abs(np.fft.rfft(chunk))
                freqs = np.fft.rfftfreq(len(chunk), 1.0 / sr)
                total_energy = float(np.sum(fft ** 2)) + 1e-9

                # Speech vocal formant band: 300Hz - 3400Hz
                vocal_energy = float(np.sum(fft[(freqs >= 300) & (freqs <= 3400)] ** 2)) / total_energy
                # High frequency tactile clicks/sizzles: > 4500Hz
                high_energy = float(np.sum(fft[freqs > 4500] ** 2)) / total_energy

                if rms < 0.015:
                    sound_type = "silence"
                    label = "🔇 Yên tĩnh / Âm lượng rất nhỏ"
                    has_speech = False
                    is_asmr = False
                elif vocal_energy >= 0.38 and rms >= 0.035:
                    sound_type = "speech"
                    label = "🗣️ Có giọng nói / Lời thoại (Bác sĩ/KTV hoặc khách hàng)"
                    has_speech = True
                    is_asmr = False
                elif high_energy >= 0.22 and rms >= 0.025:
                    sound_type = "asmr"
                    label = "🎧 Âm thanh ASMR / Tiếng lách cách dụng cụ y tế rõ nét"
                    has_speech = False
                    is_asmr = True
                elif rms >= 0.28:
                    sound_type = "climax"
                    label = "🔥 Âm thanh cao trào / Tiếng cười, phản ứng mạnh"
                    has_speech = vocal_energy >= 0.30
                    is_asmr = False
                else:
                    sound_type = "ambient"
                    label = "🎵 Nhạc nền hoặc âm thanh môi trường spa thư giãn"
                    has_speech = False
                    is_asmr = False

                results.append({
                    "start": t_start,
                    "end": t_end,
                    "rms": round(rms, 3),
                    "sound_type": sound_type,
                    "label": label,
                    "has_speech": has_speech,
                    "is_asmr": is_asmr
                })
        except Exception:
            for i in range(num_intervals):
                t_start = i * interval_seconds
                t_end = min((i + 1) * interval_seconds, duration)
                results.append({
                    "start": t_start,
                    "end": t_end,
                    "rms": 0.0,
                    "sound_type": "unknown",
                    "label": "🎵 Âm thanh môi trường",
                    "has_speech": False,
                    "is_asmr": False
                })

        return results

    @classmethod
    def scrub_and_sample_keyframes(
        cls,
        video_path: str,
        interval_seconds: float = 5.0,
        domain: str = "dermatology_spa"
    ) -> List[Dict[str, Any]]:
        """
        Simulates human scrubbing at 5s - 10s intervals:
        Extracts keyframes, scores sharpness, detects tools/techniques, and visual action.
        """
        samples = []
        if not video_path or not os.path.exists(video_path):
            return samples

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return samples

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0.0

        if duration <= 0:
            cap.release()
            return samples

        # Adaptive interval: 3s for short (<18s), 5s for medium (18-60s), 10s for long (>60s)
        if duration <= 18.0:
            step_sec = max(2.5, interval_seconds if interval_seconds < 4 else 3.5)
        elif duration <= 75.0:
            step_sec = interval_seconds
        else:
            step_sec = max(8.0, interval_seconds)

        timestamps = list(np.arange(0.0, duration, step_sec))
        if duration - timestamps[-1] > 1.5:
            timestamps.append(round(duration - 0.5, 1))

        prev_gray = None

        for t in timestamps:
            frame_no = int(t * fps)
            if frame_no >= total_frames:
                frame_no = max(0, total_frames - 1)

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 1. Sharpness & Quality
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            brightness = float(np.mean(gray))

            # Quality tier & star
            if sharpness >= 200.0:
                stars = 5
            elif sharpness >= 100.0:
                stars = 4
            elif sharpness >= 45.0:
                stars = 3
            else:
                stars = 2

            # 2. Activity / Motion score vs previous frame
            motion_score = 0.0
            if prev_gray is not None and prev_gray.shape == gray.shape:
                diff = cv2.absdiff(gray, prev_gray)
                motion_score = float(np.mean(diff))
            prev_gray = gray

            # 3. Save frame temporarily to run ToolDetector & QualityScorer
            fd, tmp_frame_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            cv2.imwrite(tmp_frame_path, frame)

            tool_tags = ToolDetector.detect_techniques(tmp_frame_path, domain=domain)
            try:
                os.remove(tmp_frame_path)
            except Exception:
                pass

            # 4. Highlight score (Golden moment candidate)
            # High sharpness + active tool/gloves/acne + good motion
            highlight_score = (sharpness * 0.4) + (len(tool_tags) * 80.0) + (motion_score * 5.0)

            # Describe what is happening visually at this timestamp
            desc_parts = []
            if "Cận_Cảnh_Mụn_Viêm" in tool_tags or "Kỹ_Thuật_Lấy_Nhân_Mụn" in tool_tags:
                desc_parts.append("🎯 Cận cảnh mụn & cồi mụn rõ nét")
            if "Thao_Tác_Găng_Y_Tế_Vô_Trùng" in tool_tags:
                desc_parts.append("🧤 KTV thao tác găng tay y tế chuẩn xác")
            if "Chiếu_Đèn_Sinh_Học_Omega" in tool_tags:
                desc_parts.append("💡 Chiếu đèn ánh sáng sinh học Omega phục hồi")
            if "Máy_Thẩm_Mỹ_Công_Nghệ_Cao" in tool_tags:
                desc_parts.append("🏥 Thiết bị công nghệ cao & phòng khám")
            if not desc_parts:
                desc_parts.append("💆‍♀️ Thao tác chăm sóc da thực tế")

            visual_summary = " + ".join(desc_parts)

            samples.append({
                "time": round(t, 1),
                "time_str": cls.format_seconds(t),
                "sharpness": round(sharpness, 1),
                "stars": stars,
                "motion_score": round(motion_score, 1),
                "tool_tags": tool_tags,
                "highlight_score": round(highlight_score, 1),
                "visual_summary": visual_summary
            })

        cap.release()
        return samples

    @staticmethod
    def format_seconds(seconds: float) -> str:
        s = int(round(seconds))
        mm = s // 60
        ss = s % 60
        return f"{mm:02d}:{ss:02d}"

    @classmethod
    def compile_video_intelligence(
        cls,
        video_path: str,
        customer_name: Optional[str] = None,
        photo_url: Optional[str] = None,
        date_str: Optional[str] = None,
        domain: str = "dermatology_spa"
    ) -> Dict[str, Any]:
        """
        Runs the complete end-to-end video analysis:
        1. Probes technical parameters.
        2. Fast-forwards / scrubs keyframes at 5s-10s intervals.
        3. Extracts and segments audio into Voice / ASMR / Music.
        4. Identifies Golden Moments / Top Highlights.
        5. Formats structured Eagle DAM Annotation and Tags.
        """
        probe = cls.probe_video(video_path)
        if not probe["valid"]:
            return {"status": "error", "message": "Không thể đọc định dạng video"}

        duration = probe["duration"]

        # 1. Scrub keyframes every 5s
        keyframes = cls.scrub_and_sample_keyframes(video_path, interval_seconds=5.0, domain=domain)

        # 2. Extract and analyze audio track
        wav_path = cls.extract_audio_track(video_path)
        audio_segments = cls.analyze_audio_timeline(wav_path, duration=duration, interval_seconds=5.0)
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass

        # 3. Merge video keyframes with audio segments
        timeline = []
        speech_segments = []
        asmr_segments = []

        for idx, kf in enumerate(keyframes):
            t_curr = kf["time"]
            # Match corresponding audio segment
            matched_audio = next(
                (a for a in audio_segments if a["start"] <= t_curr < a["end"]),
                audio_segments[-1] if audio_segments else None
            )

            a_label = matched_audio["label"] if matched_audio else "🔇 Không tiếng"
            if matched_audio and matched_audio.get("has_speech"):
                speech_segments.append(kf["time_str"])
            if matched_audio and matched_audio.get("is_asmr"):
                asmr_segments.append(kf["time_str"])

            timeline.append({
                "time_str": kf["time_str"],
                "stars": kf["stars"],
                "sharpness": kf["sharpness"],
                "visual": kf["visual_summary"],
                "audio": a_label,
                "highlight_score": kf["highlight_score"],
                "tool_tags": kf["tool_tags"]
            })

        # 4. Detect Top Highlight / Golden Moment
        if keyframes:
            best_kf = max(keyframes, key=lambda x: x["highlight_score"])
            best_hook_time = best_kf["time_str"]
            best_hook_desc = best_kf["visual_summary"]
        else:
            best_hook_time = "00:00"
            best_hook_desc = "Cận cảnh mở đầu"

        # Overall Audio Profile
        has_voice = len(speech_segments) > 0
        has_asmr = len(asmr_segments) > 0
        if has_voice and has_asmr:
            audio_profile = "🗣️ Có Lời Thoại Bác Sĩ / Khách Hàng + 🎧 Âm Thanh ASMR Thao Tác"
        elif has_voice:
            audio_profile = "🗣️ Có Lời Thoại / Hướng Dẫn Quy Trình Rõ Nét"
        elif has_asmr:
            audio_profile = "🎧 Âm Thanh ASMR Dụng Cụ Thực Tế (Satisfying Sound)"
        elif probe["has_audio"]:
            audio_profile = "🎵 Nhạc Nền / Âm Thanh Môi Trường Spa Thư Giãn"
        else:
            audio_profile = "🔇 Video Câm (Không Có Đường Tiếng - Cần Lồng Nhạc CapCut)"

        # 5. Formulate Eagle Tags
        tags = [
            "Khải Hoàn Skincare & Spa Phục Hồi Da",
            "Video_Dọc_9:16" if probe["is_vertical"] else "Video_Ngang_16:9",
            "CapCut_Footage",
            f"Thời_Lượng_{int(round(duration))}s"
        ]
        if has_voice:
            tags.append("Có_Lời_Thoại_Voiceover")
        if has_asmr:
            tags.append("Âm_Thanh_ASMR_Thao_Tác")
        if not probe["has_audio"]:
            tags.append("Video_Không_Tiếng")

        # Collect tools
        for kf in keyframes:
            for tt in kf["tool_tags"]:
                if tt not in tags:
                    tags.append(tt)

        if customer_name:
            safe_c = "".join([c for c in customer_name.replace(" ", "_") if c.isalnum() or c == "_"])
            tags.append(f"Khách_{safe_c}")

        # Average star rating
        avg_stars = int(round(np.mean([kf["stars"] for kf in keyframes]))) if keyframes else 4
        star_str = "⭐" * avg_stars

        # 6. Build Rich Eagle Annotation
        anno_lines = [
            f"🎬 PHÂN TÍCH NỘI DUNG VIDEO (Tua Nhanh Mỗi 5 Giây):",
            f"• Định dạng: {probe['aspect_ratio_str']} | Độ dài: {duration}s ({probe['fps']} FPS)",
            f"• Đánh giá chất lượng: {star_str} ({avg_stars}/5 Sao)",
            f"• Tổng quan âm thanh: {audio_profile}",
            f"----------------------------------------",
            f"📍 TIMELINE CHI TIẾT THEO TỪNG MỐC THỜI GIAN:"
        ]

        for item in timeline:
            star_pill = "⭐" * item["stars"]
            anno_lines.append(
                f"⏱️ [{item['time_str']}] {item['visual']} ({star_pill}, Nét: {item['sharpness']})\n"
                f"   🔊 Âm thanh: {item['audio']}"
            )

        anno_lines.extend([
            f"----------------------------------------",
            f"🔥 KHÚC HAY NHẤT (GOLDEN MOMENT) GỢI Ý CHO CAPCUT / TIKTOK:",
            f"👉 Cắt 3s đầu (Hook Viral): Lấy từ mốc [{best_hook_time}] ➔ {best_hook_desc}. Giữ chân người xem tuyệt đối!",
            f"👉 Hướng dẫn dựng CapCut: Kéo video vào Timeline, cắt bỏ 0.5s đầu và cuối. Lồng nhạc trend hoặc bật âm lượng ASMR lên 150%.",
            f"👉 Vị trí Text: Đặt tiêu đề ở giữa khung hình (vùng an toàn 9:16), tránh 150px bên dưới bị icon TikTok che."
        ])

        if customer_name:
            anno_lines.append(f"\n👥 HỒ SƠ KHÁCH HÀNG: {customer_name}")
        if date_str:
            anno_lines.append(f"📅 NGÀY GHI HÌNH: {date_str}")
        if photo_url:
            anno_lines.append(f"🔗 LINK GỐC GOOGLE PHOTOS: {photo_url}")

        full_annotation = "\n".join(anno_lines)

        return {
            "status": "success",
            "duration": duration,
            "is_vertical": probe["is_vertical"],
            "rating": avg_stars,
            "tags": tags,
            "annotation": full_annotation,
            "audio_profile": audio_profile,
            "best_hook_time": best_hook_time,
            "timeline": timeline
        }
