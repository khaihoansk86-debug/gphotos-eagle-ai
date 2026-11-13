import tempfile
import unittest
from pathlib import Path
from core import Catalog

class MonitorTests(unittest.TestCase):
    def test_profile_selection_and_empty_counts_persist(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            c=Catalog(folder)
            with c.store.connect() as db:
                db.execute('INSERT INTO profiles VALUES(?,?,?)',('existing','khaihoanskincare','private-profile-path'))
            self.assertEqual(c.get_monitor()['selected_profile']['id'],'existing')
            c.select_photo_profile('default')
            c=Catalog(folder)
            self.assertEqual(c.get_monitor()['selected_profile']['id'],'default')
            self.assertEqual(c.get_monitor()['imports'],{})
            self.assertEqual(c.get_monitor()['recent_imports'],[])
            self.assertNotIn('path',c.list_photo_profiles()[0])
            with self.assertRaises(ValueError):c.select_photo_profile('not-found')

if __name__=='__main__':unittest.main()
