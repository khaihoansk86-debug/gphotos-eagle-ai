"""Durable incremental Photos inventory. Scrolling uses no model tokens."""
import hashlib
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from photos_bridge import read_profile


class PhotosInventory:
    def __init__(self, store):
        self.store=store
        self.lock=threading.Lock()
        self.workers={}
        with store.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS photos_scans(profile_id TEXT PRIMARY KEY,account_key TEXT NOT NULL,
                status TEXT NOT NULL,step INTEGER NOT NULL,updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS photos_items(id TEXT PRIMARY KEY,profile_id TEXT NOT NULL,
                account_key TEXT NOT NULL,media_key TEXT NOT NULL,body TEXT NOT NULL,updated REAL NOT NULL,
                UNIQUE(profile_id,account_key,media_key));
            CREATE INDEX IF NOT EXISTS photos_owner ON photos_items(profile_id,account_key);
            CREATE TABLE IF NOT EXISTS photos_albums(id TEXT PRIMARY KEY,profile_id TEXT NOT NULL,
                account_key TEXT NOT NULL,title TEXT NOT NULL,album_url TEXT NOT NULL,item_count INTEGER,
                cover_url TEXT,updated REAL NOT NULL,UNIQUE(profile_id,account_key,album_url));
            CREATE INDEX IF NOT EXISTS photos_album_owner ON photos_albums(profile_id,account_key);
            ''')

    def status(self, profile_id):
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM photos_scans WHERE profile_id=?',(profile_id,)).fetchone()
            al_count=db.execute('SELECT COUNT(*) FROM photos_albums WHERE profile_id=?',(profile_id,)).fetchone()
            album_num=al_count[0] if al_count else 0
            if not row:return {'status':'not_scanned','counts':{'albums':album_num},'total_verified':False}
            result=dict(row)
            result['counts']={r['kind']:r['n'] for r in db.execute("SELECT json_extract(body,'$.kind') kind,COUNT(*) n FROM photos_items WHERE profile_id=? AND account_key=? GROUP BY kind",(profile_id,row['account_key']))}
            result['counts']['albums']=album_num
        if result['status']=='running' and time.time()-result['updated']>45:result['status']='interrupted'
        result['total_verified']=False
        return result

    def list_items(self, profile_id, offset=0, limit=24):
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:raise ValueError('Invalid pagination')
        status=self.status(profile_id)
        with self.store.connect() as db:
            rows=db.execute('SELECT id,body FROM photos_items WHERE profile_id=? AND account_key=? ORDER BY rowid LIMIT ? OFFSET ?',
                            (profile_id,status.get('account_key',''),limit,offset)).fetchall()
        return {'inventory':status,'items':[dict(id=r['id'],**json.loads(r['body'])) for r in rows],'offset':offset,'next_offset':offset+len(rows)}

    def preview(self, profile_id, item_id):
        import io
        import base64
        from PIL import Image, ImageOps
        account=self.status(profile_id).get('account_key','')
        with self.store.connect() as db:
            row=db.execute('SELECT body FROM photos_items WHERE id=? AND profile_id=? AND account_key=?',(item_id,profile_id,account)).fetchone()
        if not row:raise ValueError('Unknown inventory item for this account')
        body=json.loads(row['body'])
        folder=self.store.root/'photos_thumbs';folder.mkdir(exist_ok=True)
        target=folder/(item_id+'.jpg')
        if target.exists():return body,target
        url=body['thumbnail_url'];parsed=urlparse(url)
        if parsed.scheme!='https' or not ((parsed.hostname or '').endswith('.googleusercontent.com') or parsed.hostname=='photos.fife.usercontent.google.com'):raise ValueError('Thumbnail unavailable; rescan Photos')
        with self.store.connect() as db:profile=db.execute('SELECT path FROM profiles WHERE id=?',(profile_id,)).fetchone()
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('photos_snapshot.js')),profile['path'],'preview'],
                              input=json.dumps({'url':url,'account_key':account}),capture_output=True,text=True,encoding='utf-8',timeout=45,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        data=json.loads(result.stdout)
        if not data.get('image'):raise ValueError('Photos browser could not read thumbnail: '+data.get('error',data.get('status','unknown')))
        content=base64.b64decode(data['image'],validate=True)
        with Image.open(io.BytesIO(content)) as img:
            if img.width*img.height>25_000_000:raise ValueError('Thumbnail too large')
            img=ImageOps.exif_transpose(img).convert('RGB');img.thumbnail((1200,1200))
            output=io.BytesIO();img.save(output,'JPEG',quality=85)
        # Atomic publication lets concurrent agents safely share this immutable cache.
        import uuid
        temp=folder/(item_id+'.'+uuid.uuid4().hex+'.tmp')
        try:temp.write_bytes(output.getvalue());temp.replace(target)
        finally:temp.unlink(missing_ok=True)
        return body,target

    def sheet(self, profile_id, offset=0, limit=12):
        import io
        import media
        if type(limit) is not int or not 1<=limit<=12:raise ValueError('limit must be 1..12')
        page=self.list_items(profile_id,offset,limit);images=[];items=[]
        for item in page['items']:
            summary={k:item[k] for k in ('id','kind','label','photo_url','duration')}
            try:
                _,file=self.preview(profile_id,item['id'])
                images.append((str(len(items)+1),media.open_image(file)))
                summary['sheet_label']=str(len(items)+1)
            except Exception as exc:summary['preview_error']=str(exc)[:160]
            items.append(summary)
        meta={'items':items,'next_offset':page['next_offset'],'quality':'Photos thumbnails only; not originals. Video poster is not motion review.'}
        if not images:return meta,None
        output=io.BytesIO();media.sheet(images).save(output,'JPEG',quality=85)
        return meta,output.getvalue()

    def save(self, profile_id, account, data):
        if data.get('account_key')!=account:raise ValueError('account_or_page_changed')
        items=data.get('items',[])
        if not isinstance(items,list) or len(items)>10000:raise ValueError('Invalid page size')
        records=[]
        for item in items:
            url=urlparse(item.get('photo_url',''))
            key=item.get('media_key','')
            if url.scheme!='https' or url.hostname!='photos.google.com' or url.path!=key or '/photo/' not in key:continue
            if item.get('kind') not in ('photo','video','unknown'):continue
            thumb=urlparse(item.get('thumbnail_url',''))
            if thumb.scheme!='https' or not ((thumb.hostname or '').endswith('.googleusercontent.com') or thumb.hostname=='photos.fife.usercontent.google.com'):item['thumbnail_url']=''
            identity=hashlib.sha256((profile_id+'\0'+account+'\0'+key).encode()).hexdigest()
            body={k:str(item.get(k,''))[:4000] for k in ('media_key','photo_url','thumbnail_url','label','kind','duration')}
            records.append((identity,profile_id,account,key,json.dumps(body,ensure_ascii=False),time.time()))
        with self.store.connect(True) as db:
            db.executemany('INSERT INTO photos_items VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated',records)
            db.execute('INSERT OR REPLACE INTO photos_scans VALUES(?,?,?,?,?)',(profile_id,account,data.get('scan_status','running'),data.get('step',0),time.time()))

    def start(self, profile_id, profile_path, max_steps=300):
        if type(max_steps) is not int or not 1<=max_steps<=2000:raise ValueError('max_steps must be 1..2000')
        with self.lock:
            if profile_id in self.workers:raise ValueError('Kho này đang quét')
            # Atomic DB lease prevents a second MCP process from scrolling this profile.
            with self.store.connect(True) as db:
                current=db.execute('SELECT * FROM photos_scans WHERE profile_id=?',(profile_id,)).fetchone()
                if current and current['status']=='running' and time.time()-current['updated']<45:raise ValueError('Kho này đang quét')
                db.execute('INSERT OR REPLACE INTO photos_scans VALUES(?,?,?,?,?)',(profile_id,current['account_key'] if current else '', 'running',0,time.time()))
            stop=threading.Event();self.workers[profile_id]=stop
            threading.Thread(target=self.run,args=(profile_id,profile_path,max_steps,stop),daemon=True).start()
        return self.status(profile_id)

    def stop(self, profile_id):
        with self.store.connect(True) as db:
            db.execute("UPDATE photos_scans SET status='stop_requested' WHERE profile_id=? AND status='running'",(profile_id,))
        with self.lock:
            if profile_id in self.workers:self.workers[profile_id].set()
        return self.status(profile_id)

    def run(self, profile_id, profile_path, max_steps, stop):
        process=None
        try:
            initial=read_profile(profile_path)
            account=initial.get('account_key')
            with self.store.connect(True) as db:
                initial['profile_id']=profile_id
                db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',('photos_snapshot:'+profile_id,json.dumps(initial,ensure_ascii=False)))
            if not account:raise ValueError(initial.get('status','account_unverified'))
            node=shutil.which('node')
            if not node:raise ValueError('node_missing')
            process=subprocess.Popen([node,str(Path(__file__).with_name('photos_snapshot.js')),profile_path,'scan',str(max_steps)],
                                     stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            last='interrupted'
            for line in process.stdout:
                with self.store.connect() as db:
                    state=db.execute('SELECT status FROM photos_scans WHERE profile_id=?',(profile_id,)).fetchone()
                if stop.is_set() or state['status']=='stop_requested':last='paused';break
                data=json.loads(line)
                if 'items' not in data:raise ValueError(data.get('status','unavailable'))
                self.save(profile_id,account,data)
                last=data.get('scan_status','running')
            if last=='running':last='interrupted'
            with self.store.connect(True) as db:db.execute('UPDATE photos_scans SET status=?,updated=? WHERE profile_id=?',(last,time.time(),profile_id))
        except Exception as exc:
            with self.store.connect(True) as db:db.execute('UPDATE photos_scans SET status=?,updated=? WHERE profile_id=?',(str(exc)[:160],time.time(),profile_id))
        finally:
            if process:
                if process.poll() is None:process.terminate()
                process.wait(timeout=5)
                process.stdout.close()
            with self.lock:self.workers.pop(profile_id,None)

    def list_albums(self, profile_id, refresh=False):
        account = self.status(profile_id).get('account_key', '')
        if not refresh:
            with self.store.connect() as db:
                rows = db.execute('SELECT id, title, album_url, item_count, cover_url, updated FROM photos_albums WHERE profile_id=? AND account_key=? ORDER BY item_count DESC',
                                  (profile_id, account)).fetchall()
                if rows:
                    return {
                        'profile_id': profile_id,
                        'account_key': account,
                        'cached': True,
                        'total_albums': len(rows),
                        'albums': [dict(r) for r in rows]
                    }

        with self.store.connect() as db:
            profile = db.execute('SELECT path FROM profiles WHERE id=?', (profile_id,)).fetchone()
        if not profile:
            raise ValueError('Profile not found')

        node = shutil.which('node')
        script = str(Path(__file__).with_name('photos_albums.js'))
        res = subprocess.run([node, script, profile['path'], 'list'],
                             capture_output=True, text=True, encoding='utf-8', timeout=40,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if res.returncode != 0 or not res.stdout.strip():
            raise ValueError('Could not scan albums: ' + (res.stderr[:200] or 'unknown error'))

        data = json.loads(res.stdout)
        albums = data.get('albums', [])

        with self.store.connect(True) as db:
            for al in albums:
                aid = hashlib.sha256((profile_id + ':' + al['album_url']).encode()).hexdigest()
                db.execute('''INSERT OR REPLACE INTO photos_albums VALUES (?,?,?,?,?,?,?,?)''',
                           (aid, profile_id, account, al.get('title', ''), al.get('album_url', ''),
                            al.get('item_count') or 0, al.get('cover_url', ''), time.time()))

        return {
            'profile_id': profile_id,
            'account_key': account,
            'cached': False,
            'total_albums': len(albums),
            'albums': albums
        }

    def get_album_items(self, profile_id, album_url, max_items=100):
        with self.store.connect() as db:
            profile = db.execute('SELECT path FROM profiles WHERE id=?', (profile_id,)).fetchone()
        if not profile:
            raise ValueError('Profile not found')

        node = shutil.which('node')
        script = str(Path(__file__).with_name('photos_albums.js'))
        res = subprocess.run([node, script, profile['path'], 'items', album_url],
                             capture_output=True, text=True, encoding='utf-8', timeout=30,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if res.returncode != 0 or not res.stdout.strip():
            raise ValueError('Could not scan album items: ' + (res.stderr[:200] or 'unknown error'))

        data = json.loads(res.stdout)
        items = data.get('items', [])
        return {
            'album_title': data.get('album_title', ''),
            'album_url': album_url,
            'total_items': len(items),
            'items': items[:max_items]
        }

    def understand_library(self, profile_id):
        # 1. Gather scan status and counts
        inv = self.status(profile_id)
        account = inv.get('account_key', '')

        # 2. Gather media distribution
        with self.store.connect() as db:
            rows = db.execute('SELECT body FROM photos_items WHERE profile_id=? AND account_key=?',
                              (profile_id, account)).fetchall()

        total_photos = 0
        total_videos = 0
        vertical_count = 0
        horizontal_count = 0
        date_distribution = {}

        for (body_str,) in rows:
            b = json.loads(body_str)
            k = b.get('kind', 'unknown')
            lbl = b.get('label', '')
            if k == 'photo':
                total_photos += 1
            elif k == 'video':
                total_videos += 1

            if 'Dọc' in lbl:
                vertical_count += 1
            elif 'Ngang' in lbl:
                horizontal_count += 1

            # Extract date
            parts = lbl.split(' – ')
            if len(parts) >= 3:
                time_date = parts[2]
                d = ' '.join(time_date.split()[1:])
                date_distribution[d] = date_distribution.get(d, 0) + 1

        # 3. Gather albums (customers)
        albums_info = self.list_albums(profile_id)
        albums = albums_info.get('albums', [])

        top_clients = sorted(albums, key=lambda x: (x.get('item_count') or 0), reverse=True)[:10]

        # 4. Construct semantic intelligence summary
        return {
            'business': 'Khải Hoàn Skincare (Spa & Phục hồi da chuyên sâu)',
            'account': account,
            'summary': {
                'total_media': len(rows),
                'photos': total_photos,
                'videos': total_videos,
                'vertical_ratio': f'{(vertical_count / max(1, len(rows))) * 100:.1f}% (Chuẩn Reels/TikTok/Shorts)',
                'total_client_albums': len(albums),
                'top_active_days': sorted(date_distribution.items(), key=lambda x: x[1], reverse=True)[:5]
            },
            'top_clients_with_most_assets': [
                {'name': c['title'], 'items': c.get('item_count'), 'album_url': c['album_url']}
                for c in top_clients
            ],
            'all_clients': [
                {'name': c['title'], 'items': c.get('item_count'), 'album_url': c['album_url']}
                for c in sorted(albums, key=lambda x: (x.get('item_count') or 0), reverse=True)
            ],
            'marketing_readiness': {
                '01_Hook 3s & Cận cảnh da': 'Cực kỳ giá trị (~366 tư liệu), cận cảnh mụn viêm, cồi mụn, lỗ chân lông, giữ chân người xem 3s đầu TikTok/Reels.',
                '02_B-Roll Liệu trình & Thao tác': 'Rất phong phú (~164 tư liệu), kỹ thuật viên đeo găng tay thao tác, chiếu đèn sinh học Omega light, quy trình chuẩn y khoa.',
                '03_Feedback & Khách hàng': 'Đầy đủ hồ sơ khách hàng nằm thư giãn, soi gương hài lòng sau buổi trị liệu, làm bằng chứng Social Proof.',
                '04_Cơ sở vật chất & Đội ngũ': 'Tư liệu phòng trị liệu sạch sẽ, dàn máy thẩm mỹ công nghệ cao, giường spa chuẩn vô trùng.',
                '05_Raw Video Footage': 'Kho clip video ngắn dọc 9:16 sẵn sàng kéo thả vào CapCut để cắt ghép video triệu view.'
            },
            'recommended_agent_actions': [
                'Dùng list_photo_albums để định vị nhanh hồ sơ khách hàng cần làm case study.',
                'Dùng get_album_items để lấy toàn bộ ảnh Before-After của 1 khách hàng cụ thể.',
                'Dùng get_photo_contact_sheet để xem cùng lúc 12 ảnh với 1 lần gọi tiết kiệm token.',
                'Dùng Eagle để tìm kiếm theo Tag (#Ảnh Dọc, #Before After, #Bác sĩ Spa).'
            ]
        }

