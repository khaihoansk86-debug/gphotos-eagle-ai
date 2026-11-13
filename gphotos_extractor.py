import os
import sys
import json
import time
import subprocess
import platform
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("GPhotosExtractor")

class GPhotosExtractor:
    def __init__(self, profile_dir: Optional[str] = None, debug_port: int = 9222):
        self.debug_port = debug_port
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.profile_dir = profile_dir or os.path.join(current_dir, "browser_profile")
        os.makedirs(self.profile_dir, exist_ok=True)

    def launch_persistent_chrome(self, target_url="https://photos.google.com"):
        from urllib.parse import urlparse
        if urlparse(target_url).scheme != "https" or urlparse(target_url).hostname != "photos.google.com":
            raise ValueError("Chỉ cho phép URL https://photos.google.com")
        system = platform.system()
        args = ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", "--user-data-dir=" + os.path.abspath(self.profile_dir), "--new-window", target_url]
        if system == "Windows":
            candidates = [os.path.expandvars(p) for p in (
                r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
                r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")]
            browser = next((p for p in candidates if os.path.isfile(p)), None)
            if not browser:
                raise RuntimeError("Không tìm thấy Chrome/Edge")
            subprocess.Popen([browser, *args])
        elif system == "Darwin":
            subprocess.Popen(["open", "-na", "Google Chrome", "--args", *args])
        else:
            subprocess.Popen(["google-chrome", *args])
        return True

    @staticmethod
    def get_browser_js_crawler_code() -> str:
        """
        Returns a JavaScript snippet that can be executed in the browser console
        or injected via CDP to auto-scroll and extract all visible Google Photos items.
        Costs 0 AI tokens.
        """
        return """
(async function extractGPhotos(maxScrolls = 20) {
    console.log("🚀 Bắt đầu quét Google Photos...");
    const collected = new Map();
    let lastHeight = 0;

    for (let i = 0; i < maxScrolls; i++) {
        // Find all photo/video elements
        const elements = document.querySelectorAll('div[data-latest-bg], a[data-id], div[role="img"]');
        
        elements.forEach((el, index) => {
            let bgUrl = el.getAttribute('data-latest-bg') || '';
            let styleBg = el.style.backgroundImage || '';
            let href = el.closest('a')?.getAttribute('href') || '';
            let ariaLabel = el.getAttribute('aria-label') || el.closest('a')?.getAttribute('aria-label') || '';
            let isVideo = ariaLabel.toLowerCase().includes('video') || !!el.querySelector('[data-video-duration]');

            let extractedUrl = bgUrl;
            if (!extractedUrl && styleBg) {
                const match = styleBg.match(/url\\(["']?(.*?)["']?\\)/);
                if (match) extractedUrl = match[1];
            }

            if (extractedUrl && extractedUrl.startsWith('http')) {
                // Normalize to clean base URL
                const cleanUrl = extractedUrl.split('=')[0];
                if (!collected.has(cleanUrl)) {
                    collected.set(cleanUrl, {
                        id: 'gp_' + (collected.size + 1),
                        url: extractedUrl,
                        type: isVideo ? 'video' : 'photo',
                        label: ariaLabel || `Item ${collected.size + 1}`
                    });
                }
            }
        });

        // Scroll down
        window.scrollBy(0, window.innerHeight * 1.5);
        await new Promise(r => setTimeout(r, 600));

        if (document.body.scrollHeight === lastHeight && i > 5) {
            console.log("Đã cuộn đến đáy trang!");
            break;
        }
        lastHeight = document.body.scrollHeight;
    }

    const result = Array.from(collected.values());
    console.log(`✅ Đã bóc tách thành công ${result.length} ảnh/video!`);
    
    // Copy result to clipboard & prompt download
    const jsonStr = JSON.stringify(result, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'gphotos_export.json';
    a.click();
    return result;
})();
"""

    @staticmethod
    def scan_local_folder(folder_path: str) -> List[Dict[str, Any]]:
        """
        Scans a local directory (e.g. from Google Takeout or AirDrop) for images and videos.
        """
        valid_img_ext = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp"}
        valid_vid_ext = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        results = []

        if not os.path.exists(folder_path):
            return results

        idx = 1
        for root, _, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                full_path = os.path.join(root, file)
                if ext in valid_img_ext:
                    results.append({
                        "id": f"local_{idx}",
                        "path": full_path,
                        "name": file,
                        "type": "photo"
                    })
                    idx += 1
                elif ext in valid_vid_ext:
                    results.append({
                        "id": f"local_{idx}",
                        "path": full_path,
                        "name": file,
                        "type": "video"
                    })
                    idx += 1

        return results
