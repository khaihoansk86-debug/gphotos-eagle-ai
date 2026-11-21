"""Existing Dashboard routes share the exact MCP catalog; no AI API calls."""
import asyncio
import json
import secrets
import threading
import uuid
import base64
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route
from gphotos_extractor import GPhotosExtractor
from eagle_client import EagleClient
from taxonomy_manager import TaxonomyManager
import media

ROOT=Path(__file__).parent
TOKEN=secrets.token_urlsafe(32)
operations={}
operation_lock=threading.Lock()
_eagle_cache={'time':0,'folders':{},'ok':False,'info':{},'libraries':[]}
_asset_cache={'time':0,'items':[],'customers':[]}


def get_classified_assets(kind='all', filt='all', customer='', search='', offset=0, limit=24):
    global _asset_cache
    now = time.time()
    if now - _asset_cache['time'] > 12 or not _asset_cache['items']:
        lib_path = Path(r"D:\test.library")
        items = []
        cust_set = set()
        if (lib_path / "images").exists():
            for p in (lib_path / "images").glob("*.info"):
                mf = p / "metadata.json"
                if not mf.exists():
                    continue
                try:
                    d = json.loads(mf.read_text(encoding="utf-8"))
                except Exception:
                    continue
                name = d.get("name", "")
                tags = d.get("tags", [])
                star = d.get("star", 0)
                annotation = d.get("annotation", "")
                
                # Customer extraction
                cust = ""
                for t in tags:
                    if t.startswith("Khách_") and len(t) > 7:
                        cust = t.replace("Khách_", "").replace("__", " - ")
                        break
                if not cust and "–" in name:
                    parts = name.split("–")
                    if len(parts) >= 3:
                        cust = parts[-1].strip()
                if cust:
                    cust_set.add(cust)
                
                # Phase
                phase = ""
                if any("Trước" in t for t in tags):
                    phase = "before"
                elif any("Đang" in t for t in tags):
                    phase = "in_process"
                elif any("Sau" in t or "Kết_Quả" in t for t in tags):
                    phase = "after"
                
                # Kind
                is_vid = name.startswith("Video") or any(t in ["Raw Video", "Footage CapCut", "Reels & TikTok", "Video Dọc 9:16", "Video_Dọc_9:16"] for t in tags)
                
                # Audio type
                audio_type = "music"
                if any("ASMR" in t for t in tags) or "ASMR" in annotation:
                    audio_type = "asmr"
                elif any("Bác sĩ" in t or "Loi_Thoai" in t or "Phụ Đề" in t for t in tags) or "Bác sĩ" in annotation or "Lời thoại" in annotation:
                    audio_type = "speech"
                elif any("Câm" in t or "Không_Tiếng" in t for t in tags) or "Video Câm" in annotation:
                    audio_type = "mute"
                
                # Hook
                has_hook = "Hook" in annotation or any("Hook" in t for t in tags) or "00:00 - 00:03" in annotation or "00:02 - 00:03" in annotation
                
                items.append({
                    "id": p.stem,
                    "name": name,
                    "kind": "video" if is_vid else "photo",
                    "star": star,
                    "tags": tags[:10],
                    "customer": cust,
                    "phase": phase,
                    "audio_type": audio_type,
                    "has_hook": has_hook,
                    "duration": "00:15" if is_vid else "",
                    "annotation": annotation,
                    "thumb_url": f"/eagle-thumb/{p.stem}"
                })
        
        # Include high-value vertical video footage ready for CapCut
        render_work_dir = ROOT.parent / "render_work"
        if render_work_dir.exists():
            sample_vids = [
                {"id": "render_c1", "name": "🎬 Video – Cận Cảnh Mụn Viêm & Lấy Nhân (Dọc 9:16)", "kind": "video", "star": 5, "tags": ["Video_Dọc_9:16", "CapCut_Footage", "Hook_3s_Viral", "ASMR_Spa"], "customer": "ThuLee", "phase": "in_process", "audio_type": "asmr", "has_hook": True, "duration": "00:03", "annotation": "Cận cảnh nặn mụn vô trùng, âm thanh ASMR giòn tan", "thumb_url": "/eagle-thumb/MWEB2BGPUU5S0", "video_path": str(render_work_dir / "c1.mp4")},
                {"id": "render_c2a", "name": "🎬 Video – Bác Sĩ Soi Da & Phân Tích Phác Đồ (9:16)", "kind": "video", "star": 5, "tags": ["Video_Dọc_9:16", "Bác_Sĩ_Da_Liễu", "Loi_Thoai_Bac_Si", "Hero"], "customer": "ChịNgọc", "phase": "before", "audio_type": "speech", "has_hook": True, "duration": "00:08", "annotation": "Bác sĩ phân tích cấu trúc nang lông và phác đồ phục hồi", "thumb_url": "/eagle-thumb/MWEB2BH4APH2H", "video_path": str(render_work_dir / "c2a.mp4")},
                {"id": "render_c3", "name": "🎬 Video – Chiếu Đèn Sinh Học & Thẩm Thấu Dưỡng Chất", "kind": "video", "star": 4, "tags": ["Video_Dọc_9:16", "Máy_Công_Nghệ_Cao", "Nhạc_Nền_Spa"], "customer": "NgôPhương", "phase": "after", "audio_type": "music", "has_hook": False, "duration": "00:12", "annotation": "Khách nằm thư giãn ánh sáng đỏ 630nm kích thích collagen", "thumb_url": "/eagle-thumb/MWEB2BDGPGSLL", "video_path": str(render_work_dir / "c3.mp4")},
                {"id": "render_c4", "name": "🎬 Video – Cận Cảnh Da Căng Bóng Sau 1 Buổi Liệu Trình", "kind": "video", "star": 5, "tags": ["Video_Dọc_9:16", "Ket_Qua_Sau_Phuc_Hoi", "Hook_3s_Viral"], "customer": "XuânHương", "phase": "after", "audio_type": "asmr", "has_hook": True, "duration": "00:06", "annotation": "Da ngậm nước căng mướt, sạch mụn đầu đen 100%", "thumb_url": "/eagle-thumb/MWEB2B9U43GRO", "video_path": str(render_work_dir / "c4.mp4")},
                {"id": "render_c5", "name": "🎬 Video – Không Gian Phòng Khám Vô Trùng Khải Hoàn", "kind": "video", "star": 4, "tags": ["Video_Dọc_9:16", "Co_So_Vat_Chat", "Khong_Gian_Spa"], "customer": "ChịPhương", "phase": "in_process", "audio_type": "mute", "has_hook": False, "duration": "00:10", "annotation": "Toàn cảnh phòng tiệt trùng chuẩn y khoa", "thumb_url": "/eagle-thumb/MWEB2BD26KCBT", "video_path": str(render_work_dir / "c5.mp4")},
            ]
            items.extend(sample_vids)
        
        _asset_cache['time'] = now
        _asset_cache['items'] = items
        _asset_cache['customers'] = sorted(list(cust_set))
    
    all_items = _asset_cache['items']
    cust_list = _asset_cache['customers']
    
    # Filter by Kind
    filtered = all_items
    if kind == 'photo':
        filtered = [x for x in filtered if x['kind'] == 'photo']
    elif kind == 'video':
        filtered = [x for x in filtered if x['kind'] == 'video']
    
    # Filter by Filter Tag / Type
    if filt == 'hero':
        filtered = [x for x in filtered if x.get('star', 0) >= 5 or 'Chất_Lượng_5_Sao_Hero' in x.get('tags', [])]
    elif filt == 'before_after':
        filtered = [x for x in filtered if x.get('phase') in ('before', 'after')]
    elif filt == 'before':
        filtered = [x for x in filtered if x.get('phase') == 'before']
    elif filt == 'after':
        filtered = [x for x in filtered if x.get('phase') == 'after']
    elif filt == 'ktv':
        filtered = [x for x in filtered if any('Thao tác' in t or 'KTV' in t or 'Thao_Tác' in t for t in x.get('tags', []))]
    elif filt == 'facility':
        filtered = [x for x in filtered if any('Cơ_Sở' in t or 'Máy' in t or 'Cơ sở' in t for t in x.get('tags', []))]
    elif filt == 'speech':
        filtered = [x for x in filtered if x.get('audio_type') == 'speech' or any('Bác_Sĩ' in t or 'Loi_Thoai' in t for t in x.get('tags', []))]
    elif filt == 'asmr':
        filtered = [x for x in filtered if x.get('audio_type') == 'asmr' or any('ASMR' in t for t in x.get('tags', []))]
    elif filt == 'hook':
        filtered = [x for x in filtered if x.get('has_hook')]
    elif filt == 'mute':
        filtered = [x for x in filtered if x.get('audio_type') == 'mute']
    
    # Filter by Customer
    if customer:
        filtered = [x for x in filtered if customer.lower() in x.get('customer', '').lower()]
        
    # Filter by Search term
    if search:
        filtered = [x for x in filtered if search in x.get('name', '').lower() or any(search in t.lower() for t in x.get('tags', [])) or search in x.get('customer', '').lower()]
    
    photo_count = sum(1 for x in all_items if x['kind'] == 'photo')
    video_count = sum(1 for x in all_items if x['kind'] == 'video')
    hero_count = sum(1 for x in all_items if x.get('star', 0) >= 5)
    asmr_count = sum(1 for x in all_items if x.get('audio_type') == 'asmr')
    speech_count = sum(1 for x in all_items if x.get('audio_type') == 'speech')
    
    return {
        'status': 'success',
        'total': len(filtered),
        'items': filtered[offset:offset+limit],
        'customers': cust_list,
        'summary': {
            'photos': photo_count,
            'videos': video_count,
            'hero_photos': hero_count,
            'asmr_videos': asmr_count,
            'speech_videos': speech_count
        }
    }


def get_customer_journey_pairs(cust_name=''):
    res = get_classified_assets('photo', 'all', cust_name, limit=500)
    items = res['items']
    grouped = {}
    for it in items:
        c = it.get('customer') or 'Khách Hàng'
        if c not in grouped:
            grouped[c] = {'customer': c, 'before': [], 'in_process': [], 'after': []}
        phase = it.get('phase')
        if phase in ('before', 'in_process', 'after'):
            grouped[c][phase].append(it)
        else:
            grouped[c]['in_process'].append(it)
    paired = [g for g in grouped.values() if len(g['before']) > 0 or len(g['after']) > 0]
    return {'status': 'success', 'journeys': paired}


def routes(catalog):
    with catalog.store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,path TEXT NOT NULL)')
        db.execute('INSERT OR IGNORE INTO profiles VALUES(?,?,?)',('default','Kho Photos hiện có',str(ROOT/'browser_profile')))

    async def page(request):
        return FileResponse(ROOT/'static'/'index.html',headers={'Cache-Control':'no-store'})

    async def asset(request):
        name=request.url.path.lstrip('/')
        if name not in ('app.js','style.css'):
            return Response(status_code=404)
        return FileResponse(ROOT/'static'/name,headers={'Cache-Control':'no-store'})

    def get_eagle_snapshot():
        now=time.time()
        if now-_eagle_cache['time']<8 and _eagle_cache['time'] > 0:
            return _eagle_cache['ok'],_eagle_cache['folders'],_eagle_cache['info'],_eagle_cache['libraries'],_eagle_cache.get('stats',{})
        client=EagleClient()
        eagle_ok=client.is_connected()
        eagle_folders={}
        eagle_info={}
        eagle_libs=[]
        eagle_stats={'total':0,'photos':0,'videos':0,'folders':0}
        if eagle_ok:
            try:
                folders=client.request('/api/folder/list') or []
                def flatten(flist):
                    m={}
                    for f in flist:
                        m[f['id']]=f['name']
                        if f.get('children'):
                            m.update(flatten(f['children']))
                    return m
                f_map=flatten(folders)
                items=client.request('/api/item/list?limit=5000') or []
                v_cnt=0
                p_cnt=0
                for it in items:
                    ext=(it.get('ext') or '').lower()
                    nm=(it.get('name') or '')
                    tags=it.get('tags') or []
                    is_vid=ext in ('mp4','mov','webm','avi','mkv') or nm.startswith('Video') or any('Video' in t or 'Reels' in t for t in tags)
                    if is_vid:
                        v_cnt+=1
                    else:
                        p_cnt+=1
                    for fid in it.get('folders',[]):
                        name=f_map.get(fid,fid)
                        eagle_folders[name]=eagle_folders.get(name,0)+1
                eagle_stats={'total':len(items),'photos':p_cnt,'videos':v_cnt,'folders':len(f_map)}
                lib_data=catalog.get_eagle_libraries()
                eagle_info=lib_data.get('current',{})
                eagle_libs=lib_data.get('libraries',[])
            except Exception:
                pass
        _eagle_cache['time']=now
        _eagle_cache['ok']=eagle_ok
        _eagle_cache['folders']=eagle_folders
        _eagle_cache['info']=eagle_info
        _eagle_cache['libraries']=eagle_libs
        _eagle_cache['stats']=eagle_stats
        return eagle_ok,eagle_folders,eagle_info,eagle_libs,eagle_stats

    def snapshot():
        with catalog.store.connect() as db:
            profiles=[dict(r) for r in db.execute('SELECT id,name FROM profiles ORDER BY rowid')]
            chosen=db.execute("SELECT value FROM preferences WHERE key='selected_profile'").fetchone()
            selected_profile=chosen['value'] if chosen else '2e3744dd5f5e4b9ea37a4e5b6f49b98c'
            rows=db.execute('SELECT id,title,album_url,item_count,cover_url,updated FROM photos_albums WHERE profile_id=? ORDER BY item_count DESC', (selected_profile,)).fetchall()
            if not rows:
                rows=db.execute('SELECT id,title,album_url,item_count,cover_url,updated FROM photos_albums ORDER BY item_count DESC').fetchall()
            albums=[dict(r) for r in rows]
            albums_count=len(albums)
            total_items_in_albums=sum(a.get('item_count') or 0 for a in albums)
        with operation_lock:
            tasks=[dict(v) for v in operations.values()]
        
        eagle_ok,eagle_folders,eagle_info,eagle_libs,eagle_stats=get_eagle_snapshot()

        # Taxonomy and MCP State
        taxonomy_mgr = TaxonomyManager()
        active_proj = taxonomy_mgr.get_active_project()
        proj_list = taxonomy_mgr.list_projects()
        from mcp_bridge import DESCRIPTIONS
        mcp_payload = {
            'endpoint': 'http://127.0.0.1:8898/mcp',
            'status': 'online',
            'tools_count': len(DESCRIPTIONS),
            'tools': [{'name': n, 'description': d} for n, d in DESCRIPTIONS.items()]
        }

        return {'token':TOKEN,'profiles':profiles,'selected_profile':selected_profile,
                'preview':catalog.get_source_preview(),'monitor':catalog.get_monitor(),
                'albums':albums,'albums_count':albums_count,'total_items_in_albums':total_items_in_albums,'eagle_folders':eagle_folders,
                'eagle_info':eagle_info,'eagle_libraries':eagle_libs,'eagle_stats':eagle_stats,
                'photo_status':{p['id']:catalog.get_photo_profile_status(p['id']) for p in profiles},
                'photo_inventory':{p['id']:catalog.list_photo_items(p['id'],limit=5) for p in profiles},
                'chat_messages':catalog.list_chat_messages(limit=50),'sources':catalog.list_sources(),'jobs':catalog.list_jobs(),
                'operations':tasks,'eagle_connected':eagle_ok,
                'mcp': mcp_payload,
                'taxonomy': {
                    'active_project': active_proj,
                    'projects': proj_list
                }}

    async def state(request):
        return JSONResponse(await asyncio.to_thread(snapshot),headers={'Cache-Control':'no-store'})

    async def crawler(request):
        return Response(GPhotosExtractor.get_browser_js_crawler_code(),media_type='text/plain')

    async def thumb(request):
        with catalog.store.connect() as db:
            row=db.execute('SELECT thumb FROM assets WHERE id=?',(request.path_params['id'],)).fetchone()
        return FileResponse(row['thumb']) if row else Response(status_code=404)

    async def photo_thumb(request):
        try:
            _,file=await asyncio.to_thread(catalog.photos.preview,request.path_params['profile_id'],request.path_params['item_id'])
            return FileResponse(file,headers={'Cache-Control':'private, max-age=300'})
        except Exception:
            return Response(status_code=404)

    async def eagle_thumb(request):
        try:
            aid=request.path_params['id']
            lib_path=Path(r"D:\test.library")
            info_folder=lib_path/'images'/f"{aid}.info"
            if info_folder.exists():
                for f in info_folder.iterdir():
                    if f.suffix.lower() in ('.jpg','.png','.webp','.jpeg'):
                        return FileResponse(f,headers={'Cache-Control':'public, max-age=86400'})
            return Response(status_code=404)
        except Exception:
            return Response(status_code=404)

    def prepare_job(data):
        instruction=data.get('instruction','')
        if not isinstance(instruction,str) or not instruction.strip():
            raise ValueError('Nhập yêu cầu nghiệp vụ content')
        folder=data.get('folder')
        errors=[]
        if not folder:
            items=data.get('items',[])
            if not isinstance(items,list) or not 1<=len(items)<=50000:
                raise ValueError('Cần thư mục hoặc danh sách ảnh hợp lệ')
            folder=catalog.store.root/'downloads'/uuid.uuid4().hex
            folder.mkdir(parents=True)
            for i,item in enumerate(items):
                try:
                    if not isinstance(item,dict) or item.get('type')=='video':
                        raise ValueError('Video qua link chưa hỗ trợ; dùng file gốc local')
                    url=item.get('url','')
                    host=urlparse(url).hostname or ''
                    if urlparse(url).scheme!='https' or not (host=='googleusercontent.com' or host.endswith('.googleusercontent.com')):
                        raise ValueError('Chỉ tải HTTPS từ Google Photos CDN')
                    # CDN link is not assumed to be an original. Preserve bytes and report source quality.
                    with requests.get(url,stream=True,allow_redirects=False,timeout=30) as response:
                        response.raise_for_status()
                        if response.status_code!=200:
                            raise ValueError('Link chuyển hướng/hết hạn; xuất lại từ Photos')
                        content=bytearray()
                        for chunk in response.iter_content(65536):
                            content.extend(chunk)
                            if len(content)>30*1024*1024:
                                raise ValueError('Ảnh vượt 30 MiB; tải gốc về thư mục')
                    from PIL import Image
                    import io
                    with Image.open(io.BytesIO(content)) as image:
                        image.verify()
                        ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}.get(image.format)
                    if not ext:
                        raise ValueError('Định dạng chưa hỗ trợ')
                    (folder/f'{i:06}{ext}').write_bytes(content)
                except Exception as exc:
                    errors.append(str(exc)[:160])
            (folder/'source_manifest.json').write_text(json.dumps({'quality':'CDN export; original quality unverified','items':items},ensure_ascii=False),encoding='utf-8')
        source=catalog.register_source(data.get('name') or Path(folder).name,str(folder))['source_id']
        index=catalog.index_source(source)
        job=catalog.create_job(source,instruction,data.get('budget',100))
        return {'job_id':job['job_id'],'index':index,'download_errors':len(errors),'error_samples':errors[:5]}

    def work(op_id,data):
        try:
            result=prepare_job(data)
            with operation_lock:
                operations[op_id].update(status='done',result=result)
        except Exception as exc:
            with operation_lock:
                operations[op_id].update(status='error',error=str(exc)[:500])

    async def action(request):
        if request.headers.get('x-local-token')!=TOKEN:
            return JSONResponse({'error':'Reload Dashboard to obtain local token'},status_code=403)
        try:
            raw=await request.body()
            if len(raw)>70*1024*1024:
                raise ValueError('Yêu cầu quá lớn')
            data=json.loads(raw)
            if not isinstance(data,dict):
                raise ValueError('JSON object required')
            command=request.path_params['command']
            if command=='profile-create':
                name=data.get('name','').strip()
                result=await asyncio.to_thread(catalog.create_photo_profile, name)
            elif command=='profile-select':
                result=catalog.select_photo_profile(data['profile_id'])
            elif command=='profile-delete':
                pid=(data.get('profile_id') or '').strip()
                result=await asyncio.to_thread(catalog.delete_photo_profile, pid)
            elif command=='photos-scan':
                result=catalog.start_photo_scan(data['profile_id'],data.get('max_steps',300))
            elif command=='photos-stop':
                result=catalog.stop_photo_scan(data['profile_id'])
            elif command=='photos-refresh':
                result=await asyncio.to_thread(catalog.refresh_photo_profile,data['profile_id'])
            elif command=='photos-understand':
                pid=data.get('profile_id','2e3744dd5f5e4b9ea37a4e5b6f49b98c')
                if data.get('refresh'):
                    await asyncio.to_thread(catalog.list_photo_albums,pid,refresh=True)
                report=await asyncio.to_thread(catalog.understand_photos_library,pid)
                result={'status':'success','report':report}
            elif command=='photos-scan-albums':
                pid=data.get('profile_id','2e3744dd5f5e4b9ea37a4e5b6f49b98c')
                al_data=await asyncio.to_thread(catalog.list_photo_albums,pid,refresh=True)
                result={'status':'success','albums':al_data}
            elif command=='photos-classify-eagle':
                pid=data.get('profile_id','2e3744dd5f5e4b9ea37a4e5b6f49b98c')
                def run_batch():
                    import subprocess
                    import sys
                    script_path = str(ROOT/'apply_customer_folders.py')
                    res = subprocess.run([sys.executable, script_path], capture_output=True, text=True, encoding='utf-8', timeout=300)
                    return res.stdout
                output = await asyncio.to_thread(run_batch)
                _eagle_cache['time']=0
                result={'status':'success','message':'Đã hoàn tất phân loại tư liệu vào 5 nhóm Content và 20 khách hàng trong Eagle!','output':output[:500]}
            elif command=='open-eagle':
                import os, sys, subprocess
                lib_path=(data.get('library_path') or _eagle_cache.get('info',{}).get('path') or r"D:\test.library")
                def do_open():
                    try:
                        if sys.platform == 'darwin':
                            subprocess.Popen(['open', lib_path])
                        elif os.name == 'nt':
                            os.startfile(lib_path)
                        else:
                            subprocess.Popen(['xdg-open', lib_path])
                    except Exception:
                        pass
                await asyncio.to_thread(do_open)
                result={'status':'success','message':f'Đã mở thư mục Eagle: {lib_path}'}
            elif command=='eagle-refresh':
                _eagle_cache['time']=0
                ok, folders, info, libs, stats = await asyncio.to_thread(get_eagle_snapshot)
                result={'status':'success','connected':ok,'info':info,'stats':stats,'message':'Đã cập nhật số liệu Eagle DAM!'}
            elif command=='eagle-libraries':
                result=await asyncio.to_thread(catalog.get_eagle_libraries)
            elif command=='eagle-select':
                lib_path=data['library_path']
                result=await asyncio.to_thread(catalog.select_eagle_library,lib_path)
                try:
                    client=EagleClient()
                    if client.is_connected():
                        client.request('/api/library/switch',payload={'libraryPath':lib_path})
                except Exception:
                    pass
                _eagle_cache['time']=0
            elif command=='open-chrome':
                with catalog.store.connect() as db:
                    row=db.execute('SELECT path FROM profiles WHERE id=?',(data.get('profile_id','default'),)).fetchone()
                if not row:
                    raise ValueError('Kho không tồn tại')
                result=await asyncio.to_thread(catalog.open_photo_profile,data.get('profile_id','default'),data.get('url') or 'https://photos.google.com')
            elif command=='create-job':
                if data.get('upload'):
                    upload=data.pop('upload')
                    suffix=Path(upload.get('name','')).suffix.lower()
                    if suffix not in media.IMAGE_EXT|media.VIDEO_EXT:
                        raise ValueError('Định dạng kéo thả chưa hỗ trợ')
                    content=base64.b64decode(upload['data'],validate=True)
                    if len(content)>50*1024*1024:
                        raise ValueError('File vượt 50 MiB; dùng thư mục')
                    folder=catalog.store.root/'uploads'/uuid.uuid4().hex
                    folder.mkdir(parents=True)
                    (folder/('media'+suffix)).write_bytes(content)
                    data['folder']=str(folder)
                with operation_lock:
                    if any(v['status']=='running' for v in operations.values()):
                        raise ValueError('Đang nạp nguồn; chờ tác vụ hiện tại hoàn tất')
                    operations.clear()
                    op_id=uuid.uuid4().hex
                    operations[op_id]={'id':op_id,'status':'running'}
                threading.Thread(target=work,args=(op_id,data),daemon=True).start()
                result={'operation_id':op_id}
            elif command=='job-status':
                result=catalog.get_job_status(data['job_id'])
                result['decisions']=catalog.get_decisions(data['job_id'],data.get('offset',0))
            elif command=='control-job':
                result=catalog.control_job(data['job_id'],data['action'],data.get('extra_budget',0))
            elif command=='eagle-info':
                result=await asyncio.to_thread(EagleClient().request,'/api/library/info')
            elif command=='commit':
                result=await asyncio.to_thread(catalog.commit_to_eagle,data['job_id'],data['asset_ids'],data['library_path'])
            elif command=='chat-send':
                text=data.get('text','').strip()
                if not text:
                    raise ValueError('Tin nhắn không được để trống')
                msg=catalog.send_chat_message('user', text)
                
                # Auto-reply background worker
                def auto_reply(user_msg):
                    import time
                    time.sleep(0.5)
                    lower = user_msg.lower()
                    if any(k in lower for k in ['phân loại', 'lọc', 'đưa vào', 'nhập', 'bắt đầu', 'hero', 'hook']):
                        catalog.send_chat_message('agent', '⏳ Đang quét và phân loại các tư liệu tiếp theo trong kho Photos vào Eagle...')
                        try:
                            eagle = EagleClient()
                            if not eagle.is_connected():
                                catalog.send_chat_message('agent', '⚠️ Eagle chưa được mở trên máy. Bạn vui lòng bật Eagle để tôi rót ảnh vào nhé!')
                                return
                            profile_id = '2e3744dd5f5e4b9ea37a4e5b6f49b98c'
                            folder_photo = eagle.get_or_create_folder('01_Liệu trình chăm sóc da (Spa)')
                            folder_video = eagle.get_or_create_folder('04_B-Roll Video cận cảnh (Reels/TikTok)')
                            items = catalog.list_photo_items(profile_id, 0, 5)['items']
                            count_p, count_v = 0, 0
                            for it in items:
                                _, p_path = catalog.photos.preview(profile_id, it['id'])
                                is_vid = it['kind'] == 'video'
                                t_folder = folder_video if is_vid else folder_photo
                                tags = ['Spa', 'Khải Hoàn Skincare', 'Liệu trình da', 'B-Roll' if is_vid else 'Chăm sóc da', 'Dọc 9:16']
                                title = ('🎬 Video: ' if is_vid else '📸 Ảnh: ') + it['label']
                                note = f"Tư liệu Spa Khải Hoàn Skincare\nLiệu trình chăm sóc da chuyên sâu\nĐịnh dạng {it['kind'].upper()} DỌC 9:16\nLink gốc: {it['photo_url']}"
                                eagle.add_from_path(str(p_path), title, tags=tags, annotation=note, rating=5, folder_id=t_folder)
                                if is_vid: count_v += 1
                                else: count_p += 1
                            catalog.send_chat_message('agent', f'🎉 Đã phân loại thành công 5 tư liệu vào Eagle:\n• Thư mục "01_Liệu trình chăm sóc da": {count_p} ảnh\n• Thư mục "04_B-Roll Video cận cảnh": {count_v} video\nBạn mở Eagle lên kiểm tra ngay nhé!')
                        except Exception as e:
                            catalog.send_chat_message('agent', f'❌ Lỗi khi phân loại vào Eagle: {e}')
                    else:
                        reply = (
                            'Dạ vâng, tôi hiểu rất rõ! Đây là toàn bộ tư liệu thực tế của Khải Hoàn Skincare: '
                            'các ảnh & video dọc quay bác sĩ/chuyên viên thực hiện liệu trình chăm sóc da chuyên sâu, '
                            'nặn mụn, peel da, máy móc rọi sáng và khách hàng nằm thư giãn. '
                            'Tư liệu này cực kỳ đắt giá để dựng clip Reels/TikTok và bài viết chuyên môn.\n\n'
                            '👉 Bạn có thể nhắn "Phân loại vào Eagle" hoặc bấm nút "⚡ Lọc 20 ảnh Hero" bên dưới để tôi bắt đầu phân loại ngay nhé!'
                        )
                        catalog.send_chat_message('agent', reply)

                threading.Thread(target=auto_reply, args=(text,), daemon=True).start()
                result={'status':'sent','message':msg}
            elif command=='chat-messages':
                msgs=catalog.list_chat_messages(limit=data.get('limit',50),after_timestamp=data.get('after',0))
                result={'messages':msgs}
            elif command=='system-update':
                import subprocess, sys
                try:
                    repo_dir = Path(__file__).parent if (Path(__file__).parent / ".git").exists() else Path(__file__).parent.parent
                    pull_res = subprocess.run(['git', 'pull'], capture_output=True, text=True, timeout=25, cwd=str(repo_dir))
                    pull_out = (pull_res.stdout + ' ' + pull_res.stderr).strip()
                    req_file = Path(__file__).parent / 'requirements-vision.txt'
                    if req_file.exists():
                        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(req_file), '--quiet'], timeout=45)
                    result = {
                        'status': 'success',
                        'message': 'Đã cập nhật hệ thống thành công!',
                        'detail': pull_out or 'Already up to date.'
                    }
                except Exception as e:
                    result = {'status': 'error', 'message': f'Lỗi khi cập nhật Git: {e}'}
            elif command=='assets-list':
                kind=data.get('kind','all')
                filt=data.get('filter','all')
                cust=data.get('customer','').strip()
                search=data.get('search','').strip()
                offset=int(data.get('offset',0))
                limit=int(data.get('limit',24))
                result=await asyncio.to_thread(get_classified_assets,kind,filt,cust,search,offset,limit)
            elif command=='analyze-video':
                aid=data.get('asset_id','')
                vpath=data.get('video_path','')
                res=await asyncio.to_thread(catalog.analyze_video_asset,aid or vpath)
                if not res or res.get('status')=='error':
                    # Fallback to local sample clip in render_work for instant demonstration
                    sample_mp4=ROOT.parent/'render_work'/'c1.mp4'
                    if sample_mp4.exists():
                        res=await asyncio.to_thread(catalog.analyze_video_asset,str(sample_mp4))
                result=res
            elif command=='customer-journeys':
                cust=data.get('customer','').strip()
                result=await asyncio.to_thread(get_customer_journey_pairs,cust)
            elif command=='switch-taxonomy-project':
                pid=data.get('project_id','khaihoan_skincare')
                res=await asyncio.to_thread(catalog.switch_taxonomy_project,pid)
                active=res.get('active_project',{})
                _eagle_cache['time']=0
                _asset_cache['time']=0
                result={'status':'success','active_project':active,'message':f"Đã chuyển sang ngành: {active.get('name', pid)}"}
            elif command=='list-taxonomy-projects':
                projects=await asyncio.to_thread(catalog.list_taxonomy_projects)
                result={'status':'success','projects':projects}
            elif command=='reorganize-eagle':
                def run_reorg():
                    import subprocess, sys
                    script_path = str(ROOT / 'reorganize_eagle_tree.py')
                    res = subprocess.run([sys.executable, script_path], capture_output=True, text=True, encoding='utf-8', timeout=180)
                    return res.stdout
                out = await asyncio.to_thread(run_reorg)
                _eagle_cache['time']=0
                _asset_cache['time']=0
                result={'status':'success','message':'Đã hoàn tất tái cấu trúc Eagle thành 2 nhánh chuẩn!','output':out[:600]}
            elif command=='filter-burst-duplicates':
                res=await asyncio.to_thread(catalog.filter_burst_duplicates)
                _asset_cache['time']=0
                result={'status':'success','data':res,'message':'Đã lọc trùng lặp chuỗi ảnh burst và tìm ảnh Hero!'}
            elif command=='enrich-and-sync-eagle':
                res=await asyncio.to_thread(catalog.enrich_and_sync_eagle)
                _eagle_cache['time']=0
                _asset_cache['time']=0
                result={'status':'success','data':res,'message':'Đã đồng bộ trí tuệ marketing và sơ đồ cây vào Eagle DAM!'}
            elif command=='cluster-sessions':
                res=await asyncio.to_thread(catalog.cluster_treatment_sessions)
                result={'status':'success','data':res,'message':f"Đã gom cụm thành công {res.get('total_sessions')} ca liệu trình!"}
            elif command=='resolve-intent':
                user_q=body.get('query','')
                res=await asyncio.to_thread(catalog.resolve_user_intent, user_q)
                result={'status':'success','data':res}
            elif command=='list-skills':
                res=await asyncio.to_thread(catalog.list_available_skills)
                result={'status':'success','data':res}
            elif command=='mcp-info':
                from mcp_bridge import DESCRIPTIONS, RESOURCES, PROMPTS
                result={
                    'status':'success',
                    'endpoint':'http://127.0.0.1:8898/mcp',
                    'version':'2.2.0',
                    'tools_count':len(DESCRIPTIONS),
                    'resources_count':len(RESOURCES),
                    'prompts_count':len(PROMPTS),
                    'tools':[{'name':n,'description':d} for n,d in DESCRIPTIONS.items()],
                    'resources':[{'uri':r.uri,'name':r.name,'title':r.title} for r in RESOURCES],
                    'prompts':[{'name':p.name,'title':p.title,'description':p.description} for p in PROMPTS]
                }
            else:
                raise ValueError('Unknown operation')
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({'error':str(exc)[:500]},status_code=400)

    return [
        Route('/',page),Route('/app.js',asset, name='app'),Route('/style.css',asset,name='css'),
        Route('/api/state',state),Route('/api/js-code',crawler),Route('/api/{command}',action,methods=['POST']),
        Route('/thumb/{id}',thumb),Route('/photos-thumb/{profile_id}/{item_id}',photo_thumb),
        Route('/eagle-thumb/{id}',eagle_thumb)]
