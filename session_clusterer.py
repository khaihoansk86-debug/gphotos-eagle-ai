"""
Temporal Session Clustering & Anchor Metadata Propagation Engine
Zero-overhead, pure Python session clustering based on chronological timestamps.
Groups photo/video bursts into 15-45 minute treatment sessions and propagates customer anchors.
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

def parse_label_datetime(label: str) -> Optional[datetime]:
    """Extracts timestamp from Google Photos DOM label: 'Ảnh – Dọc – 11:27:47 12 thg 11, 2026'"""
    if not label:
        return None
    # 1. Pattern: HH:MM:SS dd thg MM, yyyy
    m = re.search(r'(\d{1,2}):(\d{2}):(\d{2})\s+(\d{1,2})\s+thg\s+(\d{1,2}),\s*(\d{4})', label)
    if m:
        h, mn, s, day, month, year = map(int, m.groups())
        return datetime(year, month, day, h, mn, s)
    # 2. Pattern: dd thg MM, yyyy
    m2 = re.search(r'(\d{1,2})\s+thg\s+(\d{1,2}),\s*(\d{4})', label)
    if m2:
        day, month, year = map(int, m2.groups())
        return datetime(year, month, day, 12, 0, 0)
    return None

class SessionClusterer:
    def __init__(self, max_gap_seconds: int = 2100):
        # 35 minutes default threshold between consecutive photos in a single treatment
        self.max_gap_seconds = max_gap_seconds

    def cluster(self, items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Sorts items chronologically and groups items with gap <= max_gap_seconds into sessions.
        Items without valid datetimes are put into singleton fallback sessions.
        """
        valid_items = []
        invalid_items = []

        for it in items:
            dt = it.get('dt')
            if not dt and 'label' in it:
                dt = parse_label_datetime(it['label'])
                it['dt'] = dt
            if dt:
                valid_items.append(it)
            else:
                invalid_items.append(it)

        valid_items.sort(key=lambda x: x['dt'])

        sessions = []
        current_session = []

        for it in valid_items:
            if not current_session:
                current_session.append(it)
            else:
                diff = (it['dt'] - current_session[-1]['dt']).total_seconds()
                if 0 <= diff <= self.max_gap_seconds:
                    current_session.append(it)
                else:
                    sessions.append(current_session)
                    current_session = [it]

        if current_session:
            sessions.append(current_session)

        # Append invalid items as individual items
        for inv in invalid_items:
            sessions.append([inv])

        return sessions

    def enrich_sessions_with_customers(
        self,
        sessions: List[List[Dict[str, Any]]],
        vip_customers: List[Tuple[str, str, List[str]]]
    ) -> List[Dict[str, Any]]:
        """
        Detects customer anchors in each session and propagates to all items in that session.
        Also calculates Before / In-Process / After timeline journey.
        """
        enriched_sessions = []

        for s_idx, session in enumerate(sessions):
            if not session:
                continue

            # 1. Identify customer anchor within the session
            cid, cname = None, None
            for it in session:
                lbl = it.get('label') or it.get('name') or ''
                tags = it.get('tags') or []
                
                # Check tags first
                for t in tags:
                    for v_cid, v_cname, _ in vip_customers:
                        if v_cid.lower() in t.lower() or v_cname.lower() in t.lower():
                            cid, cname = v_cid, v_cname
                            break
                    if cid:
                        break
                if cid:
                    break

                # Check date / name patterns
                for v_cid, v_cname, dates in vip_customers:
                    for d in dates:
                        if d in lbl:
                            cid, cname = v_cid, v_cname
                            break
                    if cid:
                        break
                if cid:
                    break

            start_dt = session[0].get('dt')
            end_dt = session[-1].get('dt')
            duration_mins = (end_dt - start_dt).total_seconds() / 60 if (start_dt and end_dt) else 0.0

            total_items = len(session)
            
            # 2. Tag each item with customer & journey phase
            for idx, it in enumerate(session):
                if cid:
                    it['customer_id'] = cid
                    it['customer_name'] = cname

                # Phase assignment based on timeline position within the session
                if total_items >= 3:
                    ratio = idx / (total_items - 1)
                    if ratio <= 0.25:
                        it['phase'] = 'before'
                        it['phase_label'] = 'Giai_Đoạn_Trước_Điều_Trị'
                    elif ratio <= 0.75:
                        it['phase'] = 'in_process'
                        it['phase_label'] = 'Giai_Đoạn_Đang_Điều_Trị'
                    else:
                        it['phase'] = 'after'
                        it['phase_label'] = 'Giai_Đoạn_Sau_Kết_Quả'
                else:
                    it['phase'] = 'in_process'
                    it['phase_label'] = 'Giai_Đoạn_Đang_Điều_Trị'

            enriched_sessions.append({
                'session_id': f"sess_{s_idx+1:03d}",
                'customer_id': cid,
                'customer_name': cname,
                'start_time': start_dt.isoformat() if start_dt else None,
                'end_time': end_dt.isoformat() if end_dt else None,
                'duration_minutes': round(duration_mins, 1),
                'total_items': total_items,
                'items': session
            })

        return enriched_sessions
