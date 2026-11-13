import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image


class DashboardTests(unittest.TestCase):
    def test_dashboard_to_catalog_and_back(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            os.environ['GPHOTOS_VISION_DATA']=str(Path(folder)/'data')
            import http_service
            from starlette.testclient import TestClient
            catalog=http_service.catalog
            photos=Path(folder)/'photos';photos.mkdir()
            Image.new('RGB',(800,600),'green').save(photos/'one.jpg')
            with TestClient(http_service.app,base_url='http://127.0.0.1:8898') as client:
                self.assertIn('Phiên Google Photos',client.get('/').text)
                self.assertEqual(client.get('/app.js').status_code,200)
                self.assertEqual(client.post('/api/profile-create',json={'name':'bad'}).status_code,403)
                token=client.get('/api/state').json()['token']
                headers={'X-Local-Token':token}
                profile=client.post('/api/profile-create',json={'name':'Test profile'},headers=headers).json()['profile_id']
                with patch('gphotos_extractor.subprocess.Popen') as launch:
                    with patch('gphotos_extractor.os.path.isfile',return_value=True):
                        result=client.post('/api/open-chrome',json={'profile_id':profile},headers=headers)
                        self.assertEqual(result.status_code,200,result.text)
                        self.assertFalse(launch.call_args.kwargs.get('shell',False))
                    bad=client.post('/api/open-chrome',json={'url':'https://evil.example'},headers=headers)
                    self.assertEqual(bad.status_code,400)
                result=client.post('/api/create-job',json={'folder':str(photos),'instruction':'Describe for social','budget':20},headers=headers)
                self.assertEqual(result.status_code,200,result.text)
                for _ in range(100):
                    state=client.get('/api/state').json()
                    if state['operations'][0]['status']!='running':break
                    time.sleep(.05)
                self.assertEqual(state['operations'][0]['status'],'done',state)
                job=state['jobs'][0]['id']
                batch,_=catalog.next_batch(job,'test-agent')
                asset=batch['items'][0]['id']
                catalog.get_asset_view(job,batch['batch_id'],batch['lease'],asset)
                decision={'asset_id':asset,'action':'keep','reason':'Clear','title':'Test','description':'Description','tags':['social'],'uses':['Social illustration'],'quality':'usable','limitations':'Rights unknown','category_id':'hero'}
                catalog.submit_decisions(job,batch['batch_id'],batch['lease'],[decision])
                status=client.post('/api/job-status',json={'job_id':job},headers=headers).json()
                self.assertEqual(status['counts']['decided'],1)
                self.assertEqual(status['decisions'][0]['title'],'Test')
                self.assertEqual(client.get('/thumb/'+asset).status_code,200)
                self.assertEqual(client.get('/api/state',headers={'Origin':'https://evil.example'}).status_code,403)

if __name__=='__main__':unittest.main()
