"""Host-driven Vision catalog. All front ends call these same operations."""
import json
import time
import uuid
from pathlib import Path
from eagle_client import EagleClient
from store import Store
import media


def uid():
    return uuid.uuid4().hex


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def text(value, name, maximum=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{name}: nonempty text, at most {maximum} characters')
    return value.strip()


class Catalog:
    def __init__(self, root=None, policy_path=None):
        self.store = Store(root or Path(__file__).parent / 'v2' / 'data')
        self.policy_path = Path(policy_path or Path(__file__).parent / 'content_policy.json')
        for name in ('thumbs', 'sheets'):
            (self.store.root / name).mkdir(exist_ok=True)
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,path TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO profiles VALUES(?,?,?)',('default','Kho Photos hiện có',str(Path(__file__).parent/'browser_profile')))

        from photos_inventory import PhotosInventory
        self.photos=PhotosInventory(self.store)

        with self.store.connect(write=True) as db:
            count = db.execute('SELECT COUNT(*) FROM chat_messages').fetchone()[0]
            if count == 0:
                welcome = (
                    "👋 Chào bạn! Tôi là Agent đồng hành cùng bạn. "
                    "Tôi đã kết nối và kiểm tra thấy kho Photos 'khaihoanskincare' hiện có 629 ảnh và 507 video. "
                    "Khung chat này được đồng bộ 2 chiều với cửa sổ chat Antigravity/GPT. "
                    "Bạn có thể nhắn chỉ đạo cho tôi tại đây bất cứ lúc nào!"
                )
                db.execute(
                    'INSERT INTO chat_messages(id, sender, text, payload, created_at) VALUES(?,?,?,?,?)',
                    (uid(), 'agent', welcome, None, time.time())
                )

    def start_photo_scan(self, profile_id, max_steps=300):
        with self.store.connect() as db:
            profile=self._row(db,'SELECT path FROM profiles WHERE id=?',(profile_id,))
        return self.photos.start(profile_id,profile['path'],max_steps)

    def stop_photo_scan(self, profile_id):
        return self.photos.stop(profile_id)

    def get_photo_inventory(self, profile_id):
        return self.photos.status(profile_id)

    def list_photo_items(self, profile_id, offset=0, limit=24):
        return self.photos.list_items(profile_id,offset,limit)

    def list_photo_albums(self, profile_id, refresh=False):
        return self.photos.list_albums(profile_id, refresh)

    def get_album_items(self, profile_id, album_url, max_items=100):
        return self.photos.get_album_items(profile_id, album_url, max_items)

    def understand_photos_library(self, profile_id):
        return self.photos.understand_library(profile_id)

    def get_photo_contact_sheet(self, profile_id, offset=0, limit=12):
        return self.photos.sheet(profile_id,offset,limit)

    def get_photo_preview(self, profile_id, item_id):
        body,file=self.photos.preview(profile_id,item_id)
        return {'id':item_id,'kind':body['kind'],'photo_url':body['photo_url'],
                'quality':'Cached Photos thumbnail, not original; video poster only'},file.read_bytes()

    def list_photo_profiles(self):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,name FROM profiles ORDER BY rowid')]

    def get_photo_profile_status(self, profile_id):
        with self.store.connect() as db:
            self._row(db,'SELECT id FROM profiles WHERE id=?',(profile_id,))
            row=db.execute('SELECT value FROM preferences WHERE key=?',('photos_snapshot:'+profile_id,)).fetchone()
        return json.loads(row['value']) if row else {'profile_id':profile_id,'status':'not_checked'}

    def refresh_photo_profile(self, profile_id):
        from photos_bridge import read_profile
        with self.store.connect() as db:
            profile=self._row(db,'SELECT path FROM profiles WHERE id=?',(profile_id,))
        result=read_profile(profile['path'])
        result['profile_id']=profile_id
        with self.store.connect(True) as db:
            db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',('photos_snapshot:'+profile_id,encoded(result)))
        return result

    def get_eagle_libraries(self):
        import ntpath
        client=EagleClient()
        if not client.is_connected():
            return {'libraries':[],'current':{},'selected_path':''}
        try:
            info=client.request('/api/library/info') or {}
            history=client.request('/api/library/history') or []
        except Exception:
            info, history = {}, []
        current=info.get('library',{})
        libraries={}
        for path in history:
            if not isinstance(path,str) or not path.strip():continue
            normalized=ntpath.normpath(path)
            libraries[ntpath.normcase(normalized)]={'path':normalized,'name':ntpath.basename(normalized).removesuffix('.library')}
        if current.get('path'):
            path=ntpath.normpath(current['path'])
            libraries[ntpath.normcase(path)]={'path':path,'name':current.get('name') or ntpath.basename(path)}
        with self.store.connect() as db:
            selected=db.execute("SELECT value FROM preferences WHERE key='eagle_target'").fetchone()
        return {'libraries':list(libraries.values()),'current':current,'selected_path':selected['value'] if selected else current.get('path','')}

    def select_eagle_library(self, library_path):
        import ntpath
        libraries=self.get_eagle_libraries()
        match=next((x for x in libraries['libraries'] if ntpath.normcase(x['path'])==ntpath.normcase(ntpath.normpath(library_path))),None)
        if not match:raise ValueError('Thư viện không có trong danh sách Eagle')
        with self.store.connect(True) as db:
            db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',('eagle_target',match['path']))
        return {'selected':match,'note':'Đã lưu đích cho agent; chưa chuyển thư viện đang mở hoặc nhập ảnh'}

    def get_source_preview(self):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT a.id,a.kind,s.name source FROM assets a JOIN sources s ON a.source_id=s.id WHERE a.active=1 ORDER BY a.rowid DESC LIMIT 12')]

    def select_photo_profile(self, profile_id):
        with self.store.connect(True) as db:
            profile=self._row(db,'SELECT id,name FROM profiles WHERE id=?',(profile_id,))
            db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',('selected_profile',profile_id))
        return dict(profile)

    def open_photo_profile(self, profile_id, album_url='https://photos.google.com'):
        from gphotos_extractor import GPhotosExtractor
        with self.store.connect() as db:
            profile=self._row(db,'SELECT path FROM profiles WHERE id=?',(profile_id,))
        GPhotosExtractor(profile['path']).launch_persistent_chrome(album_url)
        self.select_photo_profile(profile_id)
        return {'opened':True,'profile_id':profile_id,'login_verified':False}

    def get_monitor(self):
        with self.store.connect() as db:
            chosen=db.execute("SELECT value FROM preferences WHERE key='selected_profile'").fetchone()
            profile=db.execute('SELECT id,name FROM profiles WHERE id=?',(chosen['value'],)).fetchone() if chosen else None
            if not profile:
                profile=db.execute("SELECT id,name FROM profiles ORDER BY (id!='default') DESC,rowid DESC LIMIT 1").fetchone()
            counts={r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) n FROM imports GROUP BY status')}
            decisions={r['action']:r['n'] for r in db.execute("SELECT json_extract(body,'$.action') action,COUNT(*) n FROM decisions GROUP BY action")}
            recent=[dict(r) for r in db.execute('''SELECT i.asset_id,i.status,i.eagle_id,i.library,d.body FROM imports i
                JOIN decisions d ON d.job_id=i.job_id AND d.asset_id=i.asset_id ORDER BY i.rowid DESC LIMIT 12''')]
            workers=[dict(r) for r in db.execute('SELECT worker,job_id,expires FROM batches WHERE submitted IS NULL AND expires>? ORDER BY expires DESC LIMIT 10',(time.time(),))]
            for item in recent:
                body=json.loads(item.pop('body'))
                item.update(title=body.get('title',''),category=body.get('category_id',''),description=body.get('description',''))
        return {'selected_profile':dict(profile) if profile else None,'imports':counts,'decisions':decisions,'recent_imports':recent,'workers':workers}

    def register_source(self, name, folder):
        folder = Path(folder).expanduser().resolve(strict=True)
        if not folder.is_dir():
            raise ValueError('Source must be a local media folder or unpacked Photos Takeout')
        with self.store.connect(True) as db:
            row = db.execute('SELECT id FROM sources WHERE path=?', (str(folder),)).fetchone()
            if row:
                return {'source_id': row['id']}
            source_id = uid()
            db.execute('INSERT INTO sources VALUES(?,?,?)', (source_id, text(name, 'name', 200), str(folder)))
        return {'source_id': source_id}

    def list_sources(self):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,name FROM sources ORDER BY name LIMIT 100')]

    def list_jobs(self):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT j.id,j.instruction,j.status,s.name source FROM jobs j JOIN sources s ON s.id=j.source_id ORDER BY j.rowid DESC LIMIT 100')]

    def get_decisions(self, job_id, offset=0, limit=20):
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=50:
            raise ValueError('Invalid pagination')
        with self.store.connect() as db:
            self._row(db,'SELECT id FROM jobs WHERE id=?',(job_id,))
            rows=db.execute('SELECT body FROM decisions WHERE job_id=? ORDER BY created LIMIT ? OFFSET ?',(job_id,limit,offset)).fetchall()
        return [json.loads(r['body']) for r in rows]

    def index_source(self, source_id):
        with self.store.connect() as db:
            source = self._row(db, 'SELECT * FROM sources WHERE id=?', (source_id,))
        root = Path(source['path']).resolve(strict=True)
        added = reused = errors = 0
        samples = []
        # Each item commits independently: interruption can safely resume by rerunning.
        for path in root.rglob('*'):
            if path.suffix.lower() not in media.IMAGE_EXT | media.VIDEO_EXT or not path.is_file():
                continue
            try:
                path = path.resolve(strict=True)
                if not path.is_relative_to(root):
                    continue
                sha = media.digest(path)
                with self.store.connect() as db:
                    found = db.execute('SELECT id FROM assets WHERE source_id=? AND path=? AND sha=?',
                                       (source_id, str(path), sha)).fetchone()
                if found:
                    with self.store.connect(True) as db:
                        db.execute('UPDATE assets SET active=(sha=?) WHERE source_id=? AND path=?',(sha,source_id,str(path)))
                    reused += 1
                    continue
                asset_id = uid()
                thumb = self.store.root / 'thumbs' / f'{sha}.jpg'
                kind, width, height, dhash = media.prepare(path, thumb)
                with self.store.connect(True) as db:
                    db.execute('UPDATE assets SET active=0 WHERE source_id=? AND path=?',(source_id,str(path)))
                    db.execute('INSERT OR IGNORE INTO assets(id,source_id,path,sha,dhash,thumb,kind,width,height) VALUES(?,?,?,?,?,?,?,?,?)',
                               (asset_id, source_id, str(path), sha, dhash, str(thumb), kind, width, height))
                added += 1
            except (OSError, ValueError) as e:
                errors += 1
                if len(samples) < 5:
                    samples.append({'name': path.name, 'error': str(e)[:200]})
        return {'added': added, 'reused': reused, 'errors': errors, 'error_samples': samples}

    def create_job(self, source_id, instruction, budget=100):
        if type(budget) is not int or not 1 <= budget <= 100000:
            raise ValueError('budget must be 1..100000 image deliveries')
        policy = json.loads(self.policy_path.read_text(encoding='utf-8'))
        job_id = uid()
        with self.store.connect(True) as db:
            self._row(db, 'SELECT id FROM sources WHERE id=?', (source_id,))
            # Exact byte copies share a single representative per job, never delete originals.
            assets = db.execute('SELECT MIN(id) id FROM assets WHERE source_id=? AND active=1 GROUP BY sha', (source_id,)).fetchall()
            if not assets:
                raise ValueError('Index this source first')
            db.execute('INSERT INTO jobs(id,source_id,instruction,policy,budget) VALUES(?,?,?,?,?)',
                       (job_id, source_id, text(instruction, 'instruction'), encoded(policy), budget))
            db.executemany('INSERT INTO job_assets(job_id,asset_id) VALUES(?,?)', [(job_id,r['id']) for r in assets])
        return self.get_job_status(job_id)

    def get_job_status(self, job_id):
        with self.store.connect() as db:
            job = self._row(db, 'SELECT * FROM jobs WHERE id=?', (job_id,))
            counts = {r['state']: r['n'] for r in db.execute('SELECT state,COUNT(*) n FROM job_assets WHERE job_id=? GROUP BY state', (job_id,))}
            source_count = db.execute('SELECT COUNT(*) FROM assets WHERE source_id=?', (job['source_id'],)).fetchone()[0]
        return {'job_id': job_id, 'status': job['status'], 'counts': counts, 'indexed_records': source_count,
                'unique_contents': sum(counts.values()), 'image_deliveries': job['used'], 'budget': job['budget']}

    def next_batch(self, job_id, worker, limit=6):
        worker = text(worker, 'worker', 120)
        if type(limit) is not int or not 1 <= limit <= 12:
            raise ValueError('limit must be 1..12')
        with self.store.connect(True) as db:
            job = self._row(db, 'SELECT * FROM jobs WHERE id=?', (job_id,))
            if job['status'] == 'paused':
                raise ValueError('Job paused')
            self._budget(job)
            existing = db.execute('SELECT * FROM batches WHERE job_id=? AND worker=? AND submitted IS NULL AND expires>?',
                                  (job_id, worker, time.time())).fetchone()
            if existing:
                batch_id, lease, sheet_path = existing['id'], existing['lease'], existing['sheet']
            else:
                db.execute("UPDATE job_assets SET state='pending',batch_id=NULL WHERE job_id=? AND state='leased' AND batch_id IN (SELECT id FROM batches WHERE expires<=? AND submitted IS NULL)", (job_id,time.time()))
                # Sort by hash to put visually similar candidates nearby, without O(N²).
                # This is candidate ordering, never an automatic near-duplicate verdict.
                rows = db.execute("SELECT a.* FROM assets a JOIN job_assets j ON a.id=j.asset_id WHERE j.job_id=? AND j.state='pending' ORDER BY a.kind,a.dhash,a.id LIMIT ?", (job_id,limit)).fetchall()
                if not rows:
                    return {'job_id': job_id, 'batch': None, 'status': self._counts(db, job_id)}, None
                batch_id, lease = uid(), uid()
                sheet_path = str(self.store.root / 'sheets' / f'{batch_id}.jpg')
                canvas = media.sheet([(r['id'][:8], media.open_image(r['thumb'])) for r in rows])
                canvas.save(sheet_path, 'JPEG', quality=85)
                db.execute('INSERT INTO batches VALUES(?,?,?,?,?,?,NULL)', (batch_id,job_id,worker,lease,time.time()+1800,sheet_path))
                db.executemany("UPDATE job_assets SET state='leased',batch_id=?,detail=0 WHERE job_id=? AND asset_id=?", [(batch_id,job_id,r['id']) for r in rows])
            rows = db.execute('SELECT a.id,a.kind,a.width,a.height FROM assets a JOIN job_assets j ON a.id=j.asset_id WHERE j.batch_id=?', (batch_id,)).fetchall()
            db.execute("UPDATE jobs SET used=used+1,status='reviewing' WHERE id=?", (job_id,))
            policy = json.loads(job['policy'])
        return {'job_id': job_id, 'batch_id': batch_id, 'lease': lease, 'lease_seconds': 1800,
                'instruction': job['instruction'], 'policy': policy,
                'items': [{**dict(r), 'label': r['id'][:8]} for r in rows]}, Path(sheet_path).read_bytes()

    def get_asset_view(self, job_id, batch_id, lease, asset_id, size=1200, crop=None):
        if size not in (768, 1200, 1600):
            raise ValueError('size must be 768,1200,1600')
        with self.store.connect(True) as db:
            self._lease(db, job_id, batch_id, lease)
            job = self._row(db, 'SELECT * FROM jobs WHERE id=?', (job_id,))
            if job['status'] == 'paused':
                raise ValueError('Job paused')
            self._budget(job)
            row = self._row(db, 'SELECT a.* FROM assets a JOIN job_assets j ON a.id=j.asset_id WHERE j.job_id=? AND j.batch_id=? AND a.id=?', (job_id,batch_id,asset_id))
            self._verify_path(db, row)
            path = row['thumb'] if row['kind'] == 'video' else row['path']
            image = media.detail(path, size, crop)
            db.execute('UPDATE job_assets SET detail=1 WHERE job_id=? AND asset_id=?', (job_id,asset_id))
            db.execute('UPDATE jobs SET used=used+1 WHERE id=?', (job_id,))
        return {'asset_id':asset_id,'kind':row['kind'],'view':'sampled_video_frames' if row['kind']=='video' else 'photo'}, image

    def submit_decisions(self, job_id, batch_id, lease, decisions):
        if not isinstance(decisions, list) or not 1 <= len(decisions) <= 12:
            raise ValueError('Provide 1..12 decisions')
        body = encoded(decisions)
        with self.store.connect(True) as db:
            batch = self._row(db, 'SELECT * FROM batches WHERE id=? AND job_id=? AND lease=?', (batch_id,job_id,lease))
            if batch['submitted']:
                if batch['submitted'] != body:
                    raise ValueError('Batch already submitted with different decisions')
                return {'accepted':len(decisions), 'replayed':True}
            self._lease(db, job_id,batch_id,lease)
            job = self._row(db, 'SELECT * FROM jobs WHERE id=?', (job_id,))
            if job['status']=='paused':
                raise ValueError('Job paused')
            policy = json.loads(job['policy'])
            members = {r['asset_id']:r for r in db.execute('SELECT * FROM job_assets WHERE batch_id=?', (batch_id,))}
            seen = set()
            for d in decisions:
                if not isinstance(d,dict) or d.get('asset_id') not in members or d['asset_id'] in seen:
                    raise ValueError('Invalid, duplicate, or foreign asset ID')
                seen.add(d['asset_id'])
                if d.get('action') not in ('keep','review','skip'):
                    raise ValueError('action must be keep/review/skip')
                text(d.get('reason'), 'reason',1000)
                if d['action'] == 'keep':
                    if not members[d['asset_id']]['detail']:
                        raise ValueError('Open individual asset view before keeping/describing it')
                    text(d.get('title'),'title',150)
                    text(d.get('description'),'description',3000)
                    text(d.get('limitations'),'limitations',1000)
                    if d.get('category_id') not in policy['categories'] or d.get('quality') not in policy['quality']:
                        raise ValueError('Invalid category/quality')
                    if not isinstance(d.get('tags'),list) or not 1 <= len(d['tags']) <= 8 or any(t not in policy['tags'] for t in d['tags']):
                        raise ValueError('Use 1..8 approved tags; edit policy for new vocabulary')
                    if not isinstance(d.get('uses'),list) or not 1 <= len(d['uses']) <= 3:
                        raise ValueError('Provide 1..3 content uses with reasons')
                    for use in d['uses']:
                        text(use,'use',500)
                if d.get('duplicate_of'):
                    if d['duplicate_of'] == d['asset_id']:
                        raise ValueError('An asset cannot duplicate itself')
                    self._row(db,'SELECT asset_id FROM job_assets WHERE job_id=? AND asset_id=?',(job_id,d['duplicate_of']))
                d = {**d, 'schema_version':policy['version'], 'rights':'unknown'}
                db.execute('INSERT INTO decisions VALUES(?,?,?,?)', (job_id,d['asset_id'],encoded(d),time.time()))
                db.execute("UPDATE job_assets SET state='decided' WHERE job_id=? AND asset_id=?", (job_id,d['asset_id']))
            db.execute("UPDATE job_assets SET state='pending',batch_id=NULL WHERE batch_id=? AND state='leased'", (batch_id,))
            db.execute('UPDATE batches SET submitted=? WHERE id=?',(body,batch_id))
            remaining=db.execute("SELECT COUNT(*) FROM job_assets WHERE job_id=? AND state!='decided'",(job_id,)).fetchone()[0]
            if not remaining:
                db.execute("UPDATE jobs SET status='ready_to_commit' WHERE id=?",(job_id,))
        return {'accepted':len(decisions), 'replayed':False}

    def control_job(self, job_id, action, extra_budget=0):
        if action not in ('pause','resume') or type(extra_budget) is not int or not 0 <= extra_budget <= 100000:
            raise ValueError('pause/resume and nonnegative extra_budget required')
        with self.store.connect(True) as db:
            self._row(db,'SELECT id FROM jobs WHERE id=?',(job_id,))
            db.execute('UPDATE jobs SET status=?,budget=budget+? WHERE id=?',('paused' if action=='pause' else 'ready',extra_budget,job_id))
        return self.get_job_status(job_id)

    def search_assets(self, query='', offset=0, limit=20):
        if not isinstance(query,str) or len(query)>500:
            raise ValueError('query must be at most 500 characters')
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('Invalid pagination')
        with self.store.connect() as db:
            rows = db.execute("SELECT d.asset_id,d.job_id,d.body FROM decisions d WHERE json_extract(body,'$.action')='keep' AND body LIKE ? ORDER BY created DESC LIMIT ? OFFSET ?",('%'+query+'%',limit,offset)).fetchall()
        return {'items':[{'asset_id':r['asset_id'],'job_id':r['job_id'],'metadata':json.loads(r['body'])} for r in rows], 'next_offset':offset+len(rows)}

    def get_catalog_asset(self, asset_id, size=1200):
        """Read approved metadata + image for production agents after a batch closes."""
        if size not in (768,1200,1600):
            raise ValueError('size must be 768,1200,1600')
        with self.store.connect() as db:
            row=self._row(db,"SELECT a.*,d.body FROM assets a JOIN decisions d ON a.id=d.asset_id WHERE a.id=? AND json_extract(d.body,'$.action')='keep' ORDER BY d.created DESC LIMIT 1",(asset_id,))
            self._verify_path(db,row)
            imports=[dict(r) for r in db.execute('SELECT library,status,eagle_id FROM imports WHERE sha=?',(row['sha'],))]
        image=media.detail(row['thumb'] if row['kind']=='video' else row['path'],size)
        return {'asset_id':asset_id,'file_path':row['path'],'metadata':json.loads(row['body']),
                'eagle':imports,'usage':self.get_usage(asset_id)},image

    def record_usage(self, asset_id, worker, purpose, reference):
        with self.store.connect(True) as db:
            self._row(db,'SELECT id FROM assets WHERE id=?',(asset_id,))
            db.execute('INSERT INTO usages VALUES(?,?,?,?,?,?)',(uid(),asset_id,text(worker,'worker',120),text(purpose,'purpose',500),text(reference,'reference',1000),time.time()))
        return {'recorded':True}

    def get_usage(self, asset_id):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT worker,purpose,reference,created FROM usages WHERE asset_id=? ORDER BY created DESC LIMIT 50',(asset_id,))]

    def commit_to_eagle(self, job_id, asset_ids, library_path):
        if not isinstance(asset_ids,list) or not 1 <= len(asset_ids) <= 50 or len(set(asset_ids)) != len(asset_ids):
            raise ValueError('Provide 1..50 unique asset IDs')
        client = EagleClient()
        eagle = client.request
        def check_library():
            info = eagle('/api/library/info')
            if not isinstance(info,dict) or info.get('library',{}).get('path',info.get('path')) != library_path:
                raise ValueError('Eagle library differs from explicitly requested library_path')
        check_library()
        results=[]
        for asset_id in asset_ids:
            with self.store.connect() as db:
                row=self._row(db,'SELECT a.*,d.body,j.policy FROM assets a JOIN decisions d ON a.id=d.asset_id JOIN jobs j ON j.id=d.job_id WHERE d.job_id=? AND a.id=?',(job_id,asset_id))
                self._verify_path(db,row)
            decision=json.loads(row['body'])
            if decision['action']!='keep':
                raise ValueError('Only keep decisions can be committed')
            # Confirm library for every item, outside the DB transaction.
            check_library()
            with self.store.connect(True) as db:
                prior=db.execute('SELECT * FROM imports WHERE library=? AND sha=?',(library_path,row['sha'])).fetchone()
                if prior:
                    results.append({'asset_id':asset_id,'status':prior['status'],'eagle_id':prior['eagle_id']})
                    continue
                marker='gphotos-vision:'+row['sha']
                db.execute('INSERT INTO imports VALUES(?,?,?,?,?,?,?)',(library_path,row['sha'],job_id,asset_id,'importing',None,marker))
            try:
                category=json.loads(row['policy'])['categories'][decision['category_id']]
                folders=eagle('/api/folder/list') or []
                # Use top-level exact category only, never reuse same-name nested folders.
                folder=next((f['id'] for f in folders if f.get('name')==category),None)
                if folder is None:
                    folder=eagle('/api/folder/create',{'folderName':category})['id']
                check_library()
                annotation=decision['description']+'\n\nContent: '+'; '.join(decision['uses'])+'\nQuality: '+decision['quality']+'\nLimitations: '+decision['limitations']+'\nRights: unknown\n'+marker
                result=eagle('/api/item/addFromPath',{'path':row['path'],'name':decision['title'],'tags':decision['tags'],'annotation':annotation,'folderId':folder,'rating':decision.get('rating', {'good':5,'usable':3,'review':1}[decision['quality']])})
                eagle_id=result.get('id') if isinstance(result,dict) else result if isinstance(result,str) else None
                status='imported' if eagle_id else 'uncertain'
            except Exception:
                status,eagle_id='uncertain',None
            with self.store.connect(True) as db:
                db.execute('UPDATE imports SET status=?,eagle_id=? WHERE library=? AND sha=?',(status,eagle_id,library_path,row['sha']))
            results.append({'asset_id':asset_id,'status':status,'eagle_id':eagle_id})
        return {'items':results,'note':'importing/uncertain must be reconciled manually; never retry blindly'}

    @staticmethod
    def _row(db, sql, params):
        row=db.execute(sql,params).fetchone()
        if row is None:
            raise ValueError('Unknown ID or item outside requested scope')
        return row

    @staticmethod
    def _budget(job):
        if job['used'] >= job['budget']:
            raise ValueError('paused_budget: increase budget explicitly to continue')

    def _lease(self,db,job,batch,lease):
        row=self._row(db,'SELECT * FROM batches WHERE id=? AND job_id=? AND lease=?',(batch,job,lease))
        if row['submitted'] or row['expires'] <= time.time():
            raise ValueError('Batch submitted or lease expired; request a new batch')

    def _verify_path(self,db,row):
        source=self._row(db,'SELECT path FROM sources WHERE id=?',(row['source_id'],))
        path=Path(row['path']).resolve(strict=True)
        if not path.is_relative_to(Path(source['path']).resolve()) or media.digest(path)!=row['sha']:
            raise ValueError('Source file moved outside root or changed; index again')

    @staticmethod
    def _counts(db,job):
        return {r['state']:r['n'] for r in db.execute('SELECT state,COUNT(*) n FROM job_assets WHERE job_id=? GROUP BY state',(job,))}

    def send_chat_message(self, sender: str, text: str, payload: dict = None) -> dict:
        msg_id = uid()
        now = time.time()
        payload_str = json.dumps(payload, ensure_ascii=False) if payload else None
        with self.store.connect(write=True) as db:
            db.execute(
                'INSERT INTO chat_messages(id, sender, text, payload, created_at) VALUES(?,?,?,?,?)',
                (msg_id, sender, text, payload_str, now)
            )
        return {'id': msg_id, 'sender': sender, 'text': text, 'payload': payload, 'created_at': now}

    def list_chat_messages(self, limit: int = 50, after_timestamp: float = 0) -> list:
        with self.store.connect() as db:
            rows = db.execute(
                'SELECT id, sender, text, payload, created_at FROM chat_messages WHERE created_at > ? ORDER BY created_at ASC LIMIT ?',
                (after_timestamp, limit)
            ).fetchall()
            return [
                {
                    'id': r['id'],
                    'sender': r['sender'],
                    'text': r['text'],
                    'payload': json.loads(r['payload']) if r['payload'] else None,
                    'created_at': r['created_at']
                }
                for r in rows
            ]

    def list_taxonomy_projects(self) -> list:
        from taxonomy_manager import TaxonomyManager
        mgr = TaxonomyManager()
        return mgr.list_projects()

    def switch_taxonomy_project(self, project_id: str) -> dict:
        from taxonomy_manager import TaxonomyManager
        mgr = TaxonomyManager()
        active = mgr.set_active_project(project_id)
        folders = mgr.sync_folders_to_eagle()
        return {
            "status": "switched",
            "active_project": active,
            "eagle_folders": folders
        }

    def enrich_and_sync_eagle(self, library_path: str = None) -> dict:
        import apply_customer_folders
        if not library_path:
            client = EagleClient()
            info = client.get_library_info() if client.is_connected() else {}
            library_path = info.get('library', {}).get('path', info.get('path', r"D:\test.library"))
        return apply_customer_folders.run(library_path)

    def filter_burst_duplicates(self, threshold: int = 10) -> dict:
        from duplicate_filter import DuplicateFilter
        client = EagleClient()
        info = client.get_library_info() if client.is_connected() else {}
        lib_path = info.get('library', {}).get('path', info.get('path', r"D:\test.library"))
        images_dir = Path(lib_path) / "images"
        items = []
        if images_dir.exists():
            for d in images_dir.glob("*.info"):
                meta_file = d / "metadata.json"
                if not meta_file.exists():
                    continue
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    item_id = d.name.replace(".info", "")
                    ext = meta.get("ext", "jpg")
                    img_file = d / f"{item_id}.{ext}"
                    if not img_file.exists():
                        for f in d.iterdir():
                            if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                                img_file = f
                                break
                    if img_file.exists():
                        items.append({
                            "id": item_id,
                            "label": meta.get("name", ""),
                            "path": str(img_file),
                            "tags": meta.get("tags", [])
                        })
                except Exception:
                    continue
        if not items:
            return {"status": "no_local_images_found", "library_path": lib_path}
        
        eval_items = items[:200]
        result = DuplicateFilter.cluster_burst_shots(eval_items, hash_threshold=threshold)
        result["total_in_library"] = len(items)
        return result
