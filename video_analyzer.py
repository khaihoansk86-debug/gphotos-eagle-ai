"""
Universal Video Intelligence & Deep Analysis Engine (Production Grade)
Combines:
1. PySceneDetect: Automatic shot boundary & scene transition detection + middle keyframe extraction.
2. Faster-Whisper: Local, lightning-fast Vietnamese speech-to-text with exact word/sentence timestamps.
3. Audio Spectrum & ASMR Analyzer: Separates speech, tactile instrument clicks (ASMR), music, and silence.
4. QualityScorer & ToolDetector: 1-5 Star rating, blur detection, medical/spa/culinary tool recognition.
5. Viral Hook & CapCut Recommender: Pinpoints the 3s Golden Moment for TikTok/Reels retention.
Universal across Spa/Skincare, Dental Clinic, Culinary F&B, Fitness, and E-commerce.
"""

import os
import re
import tempfile
import subprocess
import wave
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

# 1. FFmpeg
try:
    import imageio_ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False

# 2. PySceneDetect
try:
    from scenedetect import detect, ContentDetector, AdaptiveDetector
    SCENEDETECT_AVAILABLE = True
except ImportError:
    SCENEDETECT_AVAILABLE = False

# 3. Faster-Whisper
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

from quality_scorer import QualityScorer
from tool_detector import ToolDetector


class VideoAnalyzer:
    _whisper_model = None

    @classmethod
    def get_ffmpeg_exe(cls) -> Optional[str]:
        if FFMPEG_AVAILABLE:
            try:
                return imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                pass
        capcut_path = r"C:\Users\Admin\AppData\Local\CapCut\Apps\8.1.1.3417\ffmpeg.exe"
        if os.path.exists(capcut_path):
            return capcut_path
        return None

    @classmethod
    def get_whisper_model(cls) -> Optional[Any]:
        """Lazy load lightweight Whisper model (tiny, int8 on CPU)"""
        if not WHISPER_AVAILABLE:
            return None
        if cls._whisper_model is None:
            try:
                # Use tiny for instant 1-2s inference with low RAM footprint
                cls._whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            except Exception:
                cls._whisper_model = False
        return cls._whisper_model if cls._whisper_model is not False else None

    @classmethod
    def probe_video(cls, video_path: str) -> Dict[str, Any]:
        """Extracts technical parameters: duration, fps, resolution, aspect ratio, audio stream."""
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

            # Check audio stream via ffmpeg probe
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
    def extract_audio_numpy(cls, video_path: str) -> Tuple[Optional[np.ndarray], int]:
        """
        Extracts mono 16kHz audio track and loads into float32 numpy array.
        Bypasses PyAV bugs by decoding directly with ffmpeg and standard wave library.
        """
        ffmpeg_exe = cls.get_ffmpeg_exe()
        if not ffmpeg_exe or not os.path.exists(video_path):
            return None, 16000

        tmp_wav = None
        try:
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

            cmd = [ffmpeg_exe, "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", tmp_wav]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if res.returncode == 0 and os.path.exists(tmp_wav) and os.path.getsize(tmp_wav) > 1000:
                with wave.open(tmp_wav, "rb") as wf:
                    sr = wf.getframerate()
                    raw = wf.readframes(wf.getnframes())
                    audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                return audio_np, sr
            return None, 16000
        except Exception:
            return None, 16000
        finally:
            if tmp_wav and os.path.exists(tmp_wav):
                try:
                    os.remove(tmp_wav)
                except Exception:
                    pass

    @classmethod
    def transcribe_audio_whisper(cls, audio_np: Optional[np.ndarray]) -> List[Dict[str, Any]]:
        """
        Transcribes speech in Vietnamese using faster-whisper with timestamps.
        Returns list of dialogue turns: [{'start': 2.1, 'end': 5.4, 'text': '...'}]
        """
        if audio_np is None or len(audio_np) < 8000:
            return []

        model = cls.get_whisper_model()
        if not model:
            return []

        try:
            # Language explicitly set to Vietnamese ('vi')
            segments, info = model.transcribe(
                audio_np,
                beam_size=1,
                language="vi",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400)
            )
            dialogue = []
            for s in segments:
                txt = s.text.strip()
                if txt:
                    dialogue.append({
                        "start": round(s.start, 1),
                        "end": round(s.end, 1),
                        "start_str": cls.format_seconds(s.start),
                        "end_str": cls.format_seconds(s.end),
                        "text": txt
                    })
            return dialogue
        except Exception:
            return []

    @classmethod
    def detect_scenes_or_scrub(
        cls,
        video_path: str,
        duration: float,
        interval_fallback: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Detects actual camera cuts/scene changes using PySceneDetect.
        Falls back seamlessly to 5s-10s interval scrubbing if single-shot video.
        """
        scenes_data = []

        if SCENEDETECT_AVAILABLE and duration >= 3.0:
            try:
                # ContentDetector looks for sharp cuts/transitions in video
                scene_list = detect(video_path, ContentDetector(threshold=27.0))
                if scene_list and len(scene_list) > 1:
                    for i, (start_tc, end_tc) in enumerate(scene_list):
                        s_sec = start_tc.get_seconds()
                        e_sec = end_tc.get_seconds()
                        mid_sec = s_sec + (e_sec - s_sec) / 2.0
                        scenes_data.append({
                            "type": "scene",
                            "scene_no": i + 1,
                            "start": round(s_sec, 1),
                            "end": round(e_sec, 1),
                            "keyframe_time": round(mid_sec, 1),
                            "start_str": cls.format_seconds(s_sec),
                            "end_str": cls.format_seconds(e_sec),
                            "keyframe_str": cls.format_seconds(mid_sec)
                        })
                    return scenes_data
            except Exception:
                pass

        # Fallback: Human-like 5s - 10s interval scrubbing
        if duration <= 18.0:
            step = max(2.5, interval_fallback if interval_fallback < 4 else 3.5)
        elif duration <= 75.0:
            step = interval_fallback
        else:
            step = max(8.0, interval_fallback)

        timestamps = list(np.arange(0.0, duration, step))
        if duration - timestamps[-1] > 1.5:
            timestamps.append(round(duration - 0.5, 1))

        for i, t in enumerate(timestamps):
            t_next = timestamps[i + 1] if i + 1 < len(timestamps) else duration
            scenes_data.append({
                "type": "interval",
                "scene_no": i + 1,
                "start": round(t, 1),
                "end": round(t_next, 1),
                "keyframe_time": round(t, 1),
                "start_str": cls.format_seconds(t),
                "end_str": cls.format_seconds(t_next),
                "keyframe_str": cls.format_seconds(t)
            })

        return scenes_data

    @classmethod
    def evaluate_video_keyframes(
        cls,
        video_path: str,
        scenes: List[Dict[str, Any]],
        domain: str = "dermatology_spa"
    ) -> List[Dict[str, Any]]:
        """
        Samples the keyframe for each scene/interval, evaluates Laplacian sharpness,
        detects tools, and measures visual motion.
        """
        evaluated = []
        if not video_path or not os.path.exists(video_path):
            return evaluated

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return evaluated

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        prev_gray = None

        for sc in scenes:
            t = sc["keyframe_time"]
            frame_no = int(t * fps)
            frame_no = max(0, min(frame_no, total_frames - 1))

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 1. Sharpness & Star Rating
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if sharpness >= 220.0:
                stars = 5
            elif sharpness >= 100.0:
                stars = 4
            elif sharpness >= 45.0:
                stars = 3
            else:
                stars = 2

            # 2. Activity / Motion score
            motion_score = 0.0
            if prev_gray is not None and prev_gray.shape == gray.shape:
                diff = cv2.absdiff(gray, prev_gray)
                motion_score = float(np.mean(diff))
            prev_gray = gray

            # 3. Detect tools & techniques
            fd, tmp_img = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            cv2.imwrite(tmp_img, frame)
            tool_tags = ToolDetector.detect_techniques(tmp_img, domain=domain)
            try:
                os.remove(tmp_img)
            except Exception:
                pass

            # 4. Highlight score
            highlight_score = (sharpness * 0.45) + (len(tool_tags) * 85.0) + (motion_score * 4.0)

            # Visual summary
            desc_parts = []
            if "Cận_Cảnh_Mụn_Viêm" in tool_tags or "Kỹ_Thuật_Lấy_Nhân_Mụn" in tool_tags:
                desc_parts.append("🎯 Cận cảnh mụn & cồi mụn rõ nét")
            if "Thao_Tác_Găng_Y_Tế_Vô_Trùng" in tool_tags:
                desc_parts.append("🧤 KTV thao tác găng y tế chuẩn xác")
            if "Chiếu_Đèn_Sinh_Học_Omega" in tool_tags:
                desc_parts.append("💡 Chiếu đèn ánh sáng sinh học Omega")
            if "Máy_Thẩm_Mỹ_Công_Nghệ_Cao" in tool_tags:
                desc_parts.append("🏥 Thiết bị công nghệ cao & không gian vô trùng")
            if not desc_parts:
                desc_parts.append("💆‍♀️ Quy trình điều trị thực tế")

            evaluated.append({
                **sc,
                "sharpness": round(sharpness, 1),
                "stars": stars,
                "motion_score": round(motion_score, 1),
                "tool_tags": tool_tags,
                "highlight_score": round(highlight_score, 1),
                "visual_summary": " + ".join(desc_parts)
            })

        cap.release()
        return evaluated

    @classmethod
    def analyze_audio_slices(
        cls,
        audio_np: Optional[np.ndarray],
        sr: int,
        scenes: List[Dict[str, Any]],
        dialogue: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Correlates audio dynamics (Speech, ASMR, Music, Silence) for each scene.
        """
        if audio_np is None or len(audio_np) == 0:
            return [{**sc, "audio_label": "🔇 Video không có tiếng", "has_voice": False, "is_asmr": False} for sc in scenes]

        results = []
        for sc in scenes:
            s_idx = int(sc["start"] * sr)
            e_idx = min(int(sc["end"] * sr), len(audio_np))
            chunk = audio_np[s_idx:e_idx]

            # Check if Whisper captured spoken words in this timeframe
            matching_words = [d["text"] for d in dialogue if not (d["end"] < sc["start"] or d["start"] > sc["end"])]

            if len(chunk) < 256:
                results.append({**sc, "audio_label": "🔇 Yên tĩnh", "has_voice": False, "is_asmr": False, "transcript": ""})
                continue

            rms = float(np.sqrt(np.mean(chunk ** 2)))
            fft = np.abs(np.fft.rfft(chunk))
            freqs = np.fft.rfftfreq(len(chunk), 1.0 / sr)
            total_e = float(np.sum(fft ** 2)) + 1e-9
            vocal_e = float(np.sum(fft[(freqs >= 300) & (freqs <= 3400)] ** 2)) / total_e
            high_e = float(np.sum(fft[freqs > 4500] ** 2)) / total_e

            if matching_words:
                speech_preview = " / ".join(matching_words)
                audio_label = f"🗣️ Lời thoại: \"{speech_preview}\""
                has_voice = True
                is_asmr = False
            elif vocal_e >= 0.38 and rms >= 0.035:
                audio_label = "🗣️ Có tiếng nói / Lời thoại tư vấn"
                has_voice = True
                is_asmr = False
            elif high_e >= 0.22 and rms >= 0.025:
                audio_label = "🎧 Âm thanh ASMR / Tiếng lách cách dụng cụ y tế"
                has_voice = False
                is_asmr = True
            elif rms < 0.015:
                audio_label = "🔇 Yên tĩnh / Âm lượng nhỏ"
                has_voice = False
                is_asmr = False
            else:
                audio_label = "🎵 Nhạc nền hoặc âm thanh môi trường spa"
                has_voice = False
                is_asmr = False

            results.append({
                **sc,
                "audio_label": audio_label,
                "has_voice": has_voice,
                "is_asmr": is_asmr,
                "transcript": " ".join(matching_words)
            })

        return results

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
        Complete end-to-end video pipeline:
        1. Probes video technical specs.
        2. Detects camera shot transitions (PySceneDetect) or interval fast-forwards.
        3. Evaluates keyframes for sharpness (1-5 stars) and tool signatures.
        4. Transcribes speech via Faster-Whisper and segments audio via FFT (Speech, ASMR, Music).
        5. Identifies Golden Moment for CapCut / TikTok 3s Hook.
        6. Builds structured Eagle Annotation & Tags.
        """
        probe = cls.probe_video(video_path)
        if not probe["valid"]:
            return {"status": "error", "message": "Không thể giải mã file video"}

        duration = probe["duration"]

        # 1. Shot boundary / Scene cuts via PySceneDetect
        raw_scenes = cls.detect_scenes_or_scrub(video_path, duration=duration, interval_fallback=5.0)

        # 2. Keyframe evaluation (QualityScorer & ToolDetector)
        evaluated_scenes = cls.evaluate_video_keyframes(video_path, raw_scenes, domain=domain)

        # 3. Audio extraction & Whisper speech transcription
        audio_np, sr = cls.extract_audio_numpy(video_path)
        dialogue = cls.transcribe_audio_whisper(audio_np)
        timeline = cls.analyze_audio_slices(audio_np, sr, evaluated_scenes, dialogue)

        # 4. Golden Moment / Top Highlight selection
        if timeline:
            best_sc = max(timeline, key=lambda x: x.get("highlight_score", 0))
            best_hook_time = f"{best_sc['start_str']} - {best_sc['end_str']}"
            best_hook_desc = best_sc.get("visual_summary", "Thao tác đắt giá nhất")
        else:
            best_hook_time = "00:00 - 00:03"
            best_hook_desc = "Cận cảnh mở đầu"

        # 5. Audio Profile & Tags
        has_voice = any(t.get("has_voice") for t in timeline) or len(dialogue) > 0
        has_asmr = any(t.get("is_asmr") for t in timeline)

        if has_voice and has_asmr:
            audio_profile = "🗣️ Có Lời Thoại / Phụ Đề + 🎧 Âm Thanh ASMR Thao Tác"
        elif has_voice:
            audio_profile = "🗣️ Có Giọng Nói / Lời Thoại Hướng Dẫn"
        elif has_asmr:
            audio_profile = "🎧 Âm Thanh ASMR Dụng Cụ Thực Tế (Satisfying Sound)"
        elif probe["has_audio"]:
            audio_profile = "🎵 Nhạc Nền / Âm Thanh Môi Trường Spa Thư Giãn"
        else:
            audio_profile = "🔇 Video Câm (Không Có Tiếng - Cần Lồng Nhạc CapCut)"

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
        if dialogue:
            tags.append("Đã_Bóc_Phụ_Đề_AI")

        for sc in timeline:
            for tt in sc.get("tool_tags", []):
                if tt not in tags:
                    tags.append(tt)

        if customer_name:
            safe_c = "".join([c for c in customer_name.replace(" ", "_") if c.isalnum() or c == "_"])
            tags.append(f"Khách_{safe_c}")

        avg_stars = int(round(np.mean([sc.get("stars", 4) for sc in timeline]))) if timeline else 4
        star_str = "⭐" * avg_stars

        # 6. Formulate Rich Eagle Annotation
        anno_lines = [
            f"🎬 PHÂN TÍCH VIDEO CHUYÊN SÂU (Scene Cuts & Audio AI):",
            f"• Định dạng: {probe['aspect_ratio_str']} | Độ dài: {duration}s ({probe['fps']} FPS)",
            f"• Đánh giá chất lượng: {star_str} ({avg_stars}/5 Sao)",
            f"• Tổng quan âm thanh: {audio_profile}",
            f"----------------------------------------",
            f"📍 BẢN ĐỒ PHÂN CẢNH THEO THỜI GIAN (TIMELINE):"
        ]

        for sc in timeline:
            star_pill = "⭐" * sc.get("stars", 4)
            tag_type = "🎬 Cảnh " + str(sc.get("scene_no", 1)) if sc.get("type") == "scene" else "⏱️ Khúc " + str(sc.get("scene_no", 1))
            anno_lines.append(
                f"{tag_type} [{sc['start_str']} ➔ {sc['end_str']}]: {sc.get('visual_summary')} ({star_pill}, Nét: {sc.get('sharpness')})\n"
                f"   🔊 Âm thanh: {sc.get('audio_label')}"
            )

        if dialogue:
            anno_lines.extend([
                f"----------------------------------------",
                f"🗣️ TRÍCH LỜI THOẠI & PHỤ ĐỀ AI (WHISPER):"
            ])
            for d in dialogue:
                anno_lines.append(f"• [{d['start_str']} - {d['end_str']}]: \"{d['text']}\"")

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
            "dialogue": dialogue,
            "timeline": timeline
        }
