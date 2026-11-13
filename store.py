"""Small, shared SQLite catalog. No model calls and no in-memory job state."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'catalog.sqlite'
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, name TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources,
                path TEXT NOT NULL, sha TEXT NOT NULL, dhash TEXT NOT NULL, thumb TEXT NOT NULL,
                kind TEXT NOT NULL, width INTEGER, height INTEGER, UNIQUE(source_id,path,sha));
            CREATE INDEX IF NOT EXISTS assets_source ON assets(source_id);
            CREATE INDEX IF NOT EXISTS assets_sha ON assets(sha);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources,
                instruction TEXT NOT NULL, policy TEXT NOT NULL, budget INTEGER NOT NULL,
                used INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'ready');
            CREATE TABLE IF NOT EXISTS job_assets(job_id TEXT REFERENCES jobs, asset_id TEXT REFERENCES assets,
                state TEXT NOT NULL DEFAULT 'pending', batch_id TEXT, detail INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(job_id,asset_id));
            CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs,
                worker TEXT NOT NULL, lease TEXT NOT NULL, expires REAL NOT NULL, sheet TEXT NOT NULL,
                submitted TEXT);
            CREATE TABLE IF NOT EXISTS decisions(job_id TEXT REFERENCES jobs, asset_id TEXT REFERENCES assets,
                body TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(job_id,asset_id));
            CREATE TABLE IF NOT EXISTS imports(library TEXT NOT NULL, sha TEXT NOT NULL, job_id TEXT NOT NULL,
                asset_id TEXT NOT NULL, status TEXT NOT NULL, eagle_id TEXT, marker TEXT NOT NULL,
                PRIMARY KEY(library,sha));
            CREATE TABLE IF NOT EXISTS usages(id TEXT PRIMARY KEY, asset_id TEXT REFERENCES assets,
                worker TEXT NOT NULL, purpose TEXT NOT NULL, reference TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS chat_messages(id TEXT PRIMARY KEY, sender TEXT NOT NULL,
                text TEXT NOT NULL, payload TEXT, created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_messages(created_at);
            PRAGMA user_version=1;
            ''')
            columns={r['name'] for r in db.execute('PRAGMA table_info(assets)')}
            if 'active' not in columns:
                db.execute('ALTER TABLE assets ADD COLUMN active INTEGER NOT NULL DEFAULT 1')

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        if write:
            db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
