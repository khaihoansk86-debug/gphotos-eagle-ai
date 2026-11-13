import tempfile
import unittest
from unittest.mock import patch
from core import Catalog
from photos_bridge import read_profile


class PhotosBridgeTests(unittest.TestCase):
    def test_missing_bridge_does_not_claim_signed_out_or_zero_totals(self):
        with tempfile.TemporaryDirectory() as path:
            result = read_profile(path)
            self.assertEqual(result['status'], 'bridge_required')
            self.assertNotIn('total_photos', result)
            self.assertNotIn('visible', result)

    def test_status_persists_and_is_isolated_by_profile(self):
        with tempfile.TemporaryDirectory() as path:
            c = Catalog(path)
            with c.store.connect() as db:
                db.execute('INSERT INTO profiles VALUES(?,?,?)', ('other','Other','unused'))
            snapshot={'status':'account_visible','visible':{'photo':2,'video':1,'unknown':3},'total_photos':None,'total_videos':None}
            with patch('photos_bridge.read_profile',return_value=snapshot):
                c.refresh_photo_profile('default')
            c = Catalog(path)
            self.assertEqual(c.get_photo_profile_status('default')['visible']['photo'],2)
            self.assertIsNone(c.get_photo_profile_status('default')['total_photos'])
            self.assertEqual(c.get_photo_profile_status('other')['status'],'not_checked')
            with self.assertRaises(ValueError):c.refresh_photo_profile('missing')

if __name__=='__main__': unittest.main()
