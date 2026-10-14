from __future__ import annotations
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from common import DATA_DIR, dumps, digest, utcnow, normalize_symbol, safe_url

class Store:
    """Single-user local storage. No session identity is implied by this database."""
    def __init__(self, path=None):
        self.path = Path(path or DATA_DIR / "workspace.sqlite")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS watch(symbol TEXT PRIMARY KEY, reason TEXT, question TEXT, note TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY, symbol TEXT, created_at TEXT, input_hash TEXT, payload TEXT, UNIQUE(symbol,input_hash));
            CREATE TABLE IF NOT EXISTS inputs(id TEXT PRIMARY KEY, payload TEXT);
            CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY, symbol TEXT, snapshot_id TEXT, created_at TEXT, note TEXT);
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, symbol TEXT, title TEXT, day TEXT, end_day TEXT, kind TEXT, source TEXT, status TEXT, question TEXT, origin TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS tracks(event_id TEXT PRIMARY KEY, created_at TEXT);
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, payload TEXT, saved_at TEXT);
            CREATE TRIGGER IF NOT EXISTS immutable_snapshot_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'Snapshots are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_snapshot_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'Snapshots are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_input_update BEFORE UPDATE ON inputs BEGIN SELECT RAISE(ABORT,'Inputs are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_input_delete BEFORE DELETE ON inputs BEGIN SELECT RAISE(ABORT,'Inputs are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_decision_update BEFORE UPDATE ON decisions BEGIN SELECT RAISE(ABORT,'Decisions are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_decision_delete BEFORE DELETE ON decisions BEGIN SELECT RAISE(ABORT,'Decisions are append-only'); END;
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def watches(self):
        with self.connect() as db: return [dict(r) for r in db.execute("SELECT * FROM watch ORDER BY updated_at DESC")]

    def save_watch(self, symbol, reason="", question="", note=""):
        symbol = normalize_symbol(symbol)
        with self.connect() as db:
            db.execute("INSERT INTO watch VALUES(?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET reason=excluded.reason,question=excluded.question,note=excluded.note,updated_at=excluded.updated_at", (symbol,reason,question,note,utcnow()))

    def remove_watch(self, symbol):
        with self.connect() as db: db.execute("DELETE FROM watch WHERE symbol=?", (symbol,))

    def save_snapshot(self, result, inputs):
        input_id = digest(inputs)
        key = digest({"inputs":input_id, "engine":result["engine_version"]})
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO inputs VALUES(?,?)", (input_id,dumps(inputs)))
            existing = db.execute("SELECT id FROM snapshots WHERE symbol=? AND input_hash=?", (result["symbol"],key)).fetchone()
            if existing: return existing[0]
            sid = str(uuid.uuid4())
            payload = dict(result, input_id=input_id)
            db.execute("INSERT INTO snapshots VALUES(?,?,?,?,?)", (sid,result["symbol"],utcnow(),key,dumps(payload)))
        return sid

    def snapshots(self, symbol, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM snapshots WHERE symbol=? ORDER BY rowid DESC LIMIT ?", (symbol,limit)).fetchall()
        return [dict(r, payload=json.loads(r["payload"])) for r in rows]

    def input_data(self, input_id):
        with self.connect() as db: row=db.execute("SELECT payload FROM inputs WHERE id=?",(input_id,)).fetchone()
        return json.loads(row[0]) if row else {}

    def decision(self, symbol, snapshot_id, note):
        if not note.strip(): raise ValueError("판단 내용을 입력하세요.")
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM snapshots WHERE id=? AND symbol=?", (snapshot_id,symbol)).fetchone():
                raise ValueError("선택 종목과 분석 기록이 일치하지 않습니다.")
            db.execute("INSERT INTO decisions VALUES(?,?,?,?,?)", (str(uuid.uuid4()),symbol,snapshot_id,utcnow(),note.strip()))

    def decisions(self, symbol):
        with self.connect() as db: return [dict(r) for r in db.execute("SELECT * FROM decisions WHERE symbol=? ORDER BY rowid DESC",(symbol,))]

    def upsert_event(self, event):
        if event.get("source") and not safe_url(event["source"]): raise ValueError("출처는 http 또는 https 주소를 입력하세요.")
        event = dict(event)
        event.setdefault("id", str(uuid.uuid4()))
        fields = [event.get(k, "") for k in ["id","symbol","title","day","end_day","kind","source","status","question","origin"]]
        with self.connect() as db:
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,day=excluded.day,end_day=excluded.end_day,source=excluded.source,status=excluded.status,updated_at=excluded.updated_at",(*fields,utcnow()))
        return event["id"]

    def events(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT e.*, CASE WHEN t.event_id IS NULL THEN 0 ELSE 1 END AS tracked FROM events e LEFT JOIN tracks t ON e.id=t.event_id ORDER BY day,title")]

    def track(self, event_id, enabled=True):
        with self.connect() as db:
            if enabled: db.execute("INSERT OR IGNORE INTO tracks VALUES(?,?)",(event_id,utcnow()))
            else: db.execute("DELETE FROM tracks WHERE event_id=?",(event_id,))

    def cache_get(self, key):
        with self.connect() as db: row = db.execute("SELECT * FROM cache WHERE key=?",(key,)).fetchone()
        return dict(row, payload=json.loads(row["payload"])) if row else None

    def cache_put(self, key, payload):
        with self.connect() as db:
            db.execute("INSERT INTO cache VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,saved_at=excluded.saved_at",(key,dumps(payload),utcnow()))

    def export(self):
        with self.connect() as db:
            tables = {t:[dict(r) for r in db.execute(f"SELECT * FROM {t}")] for t in ["watch","snapshots","inputs","decisions","events","tracks"]}
        return dumps({"format":"stock-analyzer-d01-export", "created_at":utcnow(), "tables":tables})
