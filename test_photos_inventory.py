import tempfile
import unittest
from pathlib import Path
from core import Catalog


class InventoryTests(unittest.TestCase):
    def test_rescan_deduplicates_and_accounts_remain_isolated(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            c=Catalog(folder)
            item={'media_key':'/photo/A','photo_url':'https://photos.google.com/photo/A','thumbnail_url':'https://lh3.googleusercontent.com/a','kind':'photo','label':'Ảnh','duration':''}
            data={'account_key':'one@example.com','items':[item,item],'step':1,'scan_status':'running'}
            c.photos.save('default','one@example.com',data)
            c.photos.save('default','one@example.com',data)
            self.assertEqual(c.get_photo_inventory('default')['counts'],{'photo':1})
            self.assertFalse(c.get_photo_inventory('default')['total_verified'])
            with self.assertRaises(ValueError):c.photos.save('default','two@example.com',data)
            data['account_key']='two@example.com';data['items']=[]
            c.photos.save('default','two@example.com',data)
            self.assertEqual(c.list_photo_items('default')['items'],[])
            c.photos.save('default','one@example.com',{**data,'account_key':'one@example.com'})
            self.assertEqual(len(c.list_photo_items('default')['items']),1)
            with self.assertRaises(ValueError):c.list_photo_items('default',limit=101)

    def test_external_urls_are_rejected_and_previews_are_scoped(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            c=Catalog(folder)
            item={'media_key':'/photo/A','photo_url':'https://evil.example/photo/A','thumbnail_url':'http://localhost/private','kind':'photo'}
            c.photos.save('default','x',{'account_key':'x','items':[item]})
            self.assertEqual(c.list_photo_items('default')['items'],[])
            with self.assertRaises(ValueError):c.get_photo_preview('default','../../private')

if __name__=='__main__':unittest.main()
