import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from PIL import Image
from core import Catalog


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.photos=self.root/'photos'
        self.photos.mkdir()
        Image.new('RGB',(640,480),'red').save(self.photos/'a.jpg')
        Image.new('RGB',(480,640),'blue').save(self.photos/'b.jpg')
        shutil.copyfile(self.photos/'a.jpg',self.photos/'duplicate.jpg')
        self.c=Catalog(self.root/'data')
        self.source=self.c.register_source('Test',str(self.photos))['source_id']
        self.c.index_source(self.source)
        self.job=self.c.create_job(self.source,'Choose useful social and web assets',20)['job_id']

    def batch(self,worker='agent1',limit=6):
        return self.c.next_batch(self.job,worker,limit)[0]

    def decision(self,batch):
        return {'asset_id':batch['items'][0]['id'],'action':'keep','reason':'Clear subject',
                'title':'Test asset','description':'A clear test image. A plain background.',
                'tags':['social'],'uses':['Social illustration: clear subject'],
                'quality':'usable','limitations':'Rights unverified','category_id':'hero'}

    def view(self,batch,asset_id):
        return self.c.get_asset_view(self.job,batch['batch_id'],batch['lease'],asset_id)

    def submit(self,batch,items):
        return self.c.submit_decisions(self.job,batch['batch_id'],batch['lease'],items)

    def test_exact_duplicates_and_resume(self):
        self.assertEqual(self.c.get_job_status(self.job)['unique_contents'],2)
        self.assertEqual(self.c.index_source(self.source)['reused'],3)
        self.assertEqual(Catalog(self.root/'data').get_job_status(self.job)['unique_contents'],2)

    def test_multi_agent_leases_do_not_overlap(self):
        a=self.batch('a',1); b=self.batch('b',1)
        self.assertNotEqual(a['items'][0]['id'],b['items'][0]['id'])
        self.assertEqual(a['batch_id'],self.batch('a',1)['batch_id'])

    def test_keep_requires_detail_and_idempotency(self):
        batch=self.batch(); decision=self.decision(batch)
        with self.assertRaisesRegex(ValueError,'individual'):
            self.submit(batch,[decision])
        self.view(batch,decision['asset_id'])
        self.assertEqual(self.submit(batch,[decision])['accepted'],1)
        self.assertTrue(self.submit(batch,[decision])['replayed'])
        decision['title']='Changed'
        with self.assertRaises(ValueError):
            self.submit(batch,[decision])
        self.assertEqual(self.c.get_job_status(self.job)['counts']['pending'],1)

    def test_foreign_id_rolls_back_whole_submission(self):
        batch=self.batch(); decision=self.decision(batch)
        self.view(batch,decision['asset_id'])
        with self.assertRaises(ValueError):
            self.submit(batch,[decision,{'asset_id':'foreign','action':'skip','reason':'No'}])
        self.assertEqual(self.c.search_assets()['items'],[])

    def test_budget_and_changed_original(self):
        job=self.c.create_job(self.source,'test',1)['job_id']
        b,_=self.c.next_batch(job,'test')
        with self.assertRaisesRegex(ValueError,'budget'):
            self.c.get_asset_view(job,b['batch_id'],b['lease'],b['items'][0]['id'])
        b=self.batch()
        with self.c.store.connect() as db:
            path=db.execute('SELECT path FROM assets WHERE id=?',(b['items'][0]['id'],)).fetchone()[0]
        Path(path).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):
            self.view(b,b['items'][0]['id'])

    def test_usage_search_and_eagle_uncertain_no_retry(self):
        b=self.batch(); d=self.decision(b); self.view(b,d['asset_id']); self.submit(b,[d])
        self.assertEqual(len(self.c.search_assets('illustration')['items']),1)
        metadata,image=self.c.get_catalog_asset(d['asset_id'])
        self.assertTrue(image.startswith(b'\xff\xd8'))
        self.assertEqual(metadata['metadata']['title'],'Test asset')
        self.c.record_usage(d['asset_id'],'social-agent','Article','draft:123')
        self.assertEqual(len(self.c.get_usage(d['asset_id'])),1)
        def get(url,**kwargs):
            data={'library':{'path':'library'}} if url.endswith('/info') else [{'id':'f1','name':'01_Hero'}]
            return Mock(raise_for_status=lambda:None,json=lambda:{'status':'success','data':data})
        with patch('eagle_client.requests.get',side_effect=get),patch('eagle_client.requests.post',side_effect=TimeoutError) as post:
            first=self.c.commit_to_eagle(self.job,[d['asset_id']],'library')
            second=self.c.commit_to_eagle(self.job,[d['asset_id']],'library')
            self.assertEqual(first['items'][0]['status'],'uncertain')
            self.assertEqual(second['items'][0]['status'],'uncertain')
            self.assertEqual(post.call_count,1)

    def test_changed_path_new_job_uses_new_version(self):
        Image.new('RGB',(640,480),'green').save(self.photos/'a.jpg')
        self.c.index_source(self.source)
        job=self.c.create_job(self.source,'new job')['job_id']
        # red duplicate still exists + green replacement + blue original
        self.assertEqual(self.c.get_job_status(job)['unique_contents'],3)
        with self.c.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assets WHERE active=0').fetchone()[0],1)

    def test_mcp_real_stdio_image_and_error(self):
        async def run():
            from mcp.client.stdio import stdio_client,StdioServerParameters
            from mcp.client.session import ClientSession
            params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).parent/'mcp_bridge.py')],env={**os.environ,'GPHOTOS_VISION_DATA':str(self.root/'data')})
            async with stdio_client(params) as (r,w):
                async with ClientSession(r,w,read_timeout_seconds=15) as session:
                    await session.initialize()
                    listing=await session.list_tools()
                    self.assertGreater(len(listing.tools),10)
                    result=await session.call_tool('next_batch',{'job_id':self.job,'worker':'mcp-test'})
                    self.assertFalse(result.is_error, str(result.content))
                    self.assertTrue(any(c.type=='image' for c in result.content))
                    failed=await session.call_tool('get_job_status',{'job_id':'missing'})
                    self.assertTrue(failed.is_error)
        asyncio.run(run())


if __name__=='__main__':
    unittest.main()
