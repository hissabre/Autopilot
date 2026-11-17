"""SQLite store. One row per prospect, plus an event log and a suppression list."""
import json
import sqlite3
from datetime import datetime, timezone

from .config import home


def db_path():
    return home() / "data" / "autopilot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
  id INTEGER PRIMARY KEY,
  place_id TEXT UNIQUE,
  market TEXT,
  name TEXT,
  category TEXT,
  address TEXT,
  phone TEXT,
  rating REAL,
  reviews INTEGER,
  maps_url TEXT,
  raw JSON,
  email TEXT,
  email_source TEXT,
  owner_name TEXT,
  facts JSON,
  site_slug TEXT,
  site_url TEXT,
  site_deploy_id TEXT,
  status TEXT,             -- found|no_email|enriched|site_built|deployed|contacted|followed_up|interested|question|not_interested|unsubscribed|bounced|won|lost|needs_human|taken_down
  message_id TEXT,
  contacted_at TEXT,
  last_followup_at TEXT,
  followups INTEGER DEFAULT 0,
  auto_replies INTEGER DEFAULT 0,
  call_requested INTEGER DEFAULT 0,
  call_number TEXT,
  called_at TEXT,
  plan TEXT,
  mrr REAL DEFAULT 0,
  currency TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  prospect_id INTEGER,
  kind TEXT,
  detail TEXT,
  at TEXT
);
CREATE TABLE IF NOT EXISTS suppression (
  email TEXT PRIMARY KEY,
  reason TEXT,
  at TEXT
);
CREATE TABLE IF NOT EXISTS sends (
  day TEXT PRIMARY KEY,
  count INTEGER
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path=None):
        path = path or db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # ── prospects ──
    def add_prospect(self, p: dict) -> int | None:
        try:
            cur = self.conn.execute(
                """INSERT INTO prospects(place_id, market, name, category, address, phone, rating, reviews,
                   maps_url, raw, status, currency, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p["place_id"], p["market"], p["name"], p.get("category"), p.get("address"), p.get("phone"),
                 p.get("rating"), p.get("reviews"), p.get("maps_url"), json.dumps(p.get("raw", {})),
                 "found", p.get("currency"), now(), now()),
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None  # already known

    def update(self, pid: int, **fields):
        if not fields:
            return
        for k in ("facts", "raw"):
            if k in fields and not isinstance(fields[k], str):
                fields[k] = json.dumps(fields[k], ensure_ascii=False)
        fields["updated_at"] = now()
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE prospects SET {cols} WHERE id=?", (*fields.values(), pid))
        self.conn.commit()

    def get(self, pid: int):
        return self.conn.execute("SELECT * FROM prospects WHERE id=?", (pid,)).fetchone()

    def by_status(self, *statuses, limit=1000):
        q = ",".join("?" * len(statuses))
        return self.conn.execute(
            f"SELECT * FROM prospects WHERE status IN ({q}) ORDER BY rating DESC, reviews DESC LIMIT ?",
            (*statuses, limit)).fetchall()

    def by_email(self, email: str):
        return self.conn.execute("SELECT * FROM prospects WHERE lower(email)=lower(?) ORDER BY id DESC",
                                 (email,)).fetchone()

    def by_message_id(self, mid: str):
        return self.conn.execute("SELECT * FROM prospects WHERE message_id=?", (mid,)).fetchone()

    def all(self):
        return self.conn.execute("SELECT * FROM prospects ORDER BY updated_at DESC").fetchall()

    # ── events ──
    def log(self, pid, kind, detail=""):
        self.conn.execute("INSERT INTO events(prospect_id, kind, detail, at) VALUES(?,?,?,?)",
                          (pid, kind, detail[:4000] if isinstance(detail, str) else json.dumps(detail), now()))
        self.conn.commit()

    def events(self, pid=None, limit=200):
        if pid:
            return self.conn.execute("SELECT * FROM events WHERE prospect_id=? ORDER BY id DESC LIMIT ?",
                                     (pid, limit)).fetchall()
        return self.conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    # ── suppression ──
    def suppress(self, email, reason):
        self.conn.execute("INSERT OR REPLACE INTO suppression VALUES(?,?,?)", (email.lower(), reason, now()))
        self.conn.commit()

    def is_suppressed(self, email):
        return self.conn.execute("SELECT 1 FROM suppression WHERE email=?", (email.lower(),)).fetchone() is not None

    # ── send counters ──
    def sent_today(self, day):
        r = self.conn.execute("SELECT count FROM sends WHERE day=?", (day,)).fetchone()
        return r["count"] if r else 0

    def bump_sent(self, day):
        self.conn.execute("INSERT INTO sends(day,count) VALUES(?,1) ON CONFLICT(day) DO UPDATE SET count=count+1",
                          (day,))
        self.conn.commit()

    def meta_get(self, k, default=None):
        r = self.conn.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return r["v"] if r else default

    def meta_set(self, k, v):
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, str(v)))
        self.conn.commit()
