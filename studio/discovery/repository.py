"""SQLite connections are local to each operation; no event-loop or shared connection use."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from .errors import DiscoveryError


class Repository:
    def __init__(self, settings):
        self.settings = settings
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            if db.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise sqlite3.DatabaseError("Unsupported discovery database schema version")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS discovery_search_cache (
                    cache_key TEXT PRIMARY KEY, response_json TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS discovery_videos (
                    video_id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS discovery_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, search_id TEXT UNIQUE NOT NULL,
                    requested_at REAL NOT NULL, request_json TEXT NOT NULL,
                    result_count INTEGER, cache_hit INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL, error_code TEXT
                );
                CREATE TABLE IF NOT EXISTS discovery_request_window (requested_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS discovery_window_time ON discovery_request_window(requested_at);
                CREATE TABLE IF NOT EXISTS discovery_api_budget (
                    day INTEGER PRIMARY KEY, calls INTEGER NOT NULL DEFAULT 0,
                    units INTEGER NOT NULL DEFAULT 0, blocked INTEGER NOT NULL DEFAULT 0
                );
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.settings.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def begin_search(self, request, now):
        search_id = str(uuid4())
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM discovery_request_window WHERE requested_at <= ?", (now - 60,))
            count = db.execute("SELECT COUNT(*) FROM discovery_request_window").fetchone()[0]
            if count >= self.settings.requests_per_minute:
                raise DiscoveryError("rate_limited", "Discovery request limit reached; retry in a minute.", 429, True)
            db.execute("INSERT INTO discovery_request_window VALUES (?)", (now,))
            db.execute("DELETE FROM discovery_search_cache WHERE expires_at <= ?", (now,))
            db.execute("DELETE FROM discovery_videos WHERE expires_at <= ?", (now,))
            db.execute("DELETE FROM discovery_api_budget WHERE day < ?", (int(now // 86400) - 2,))
            db.execute("DELETE FROM discovery_history WHERE requested_at < ?", (now - 30 * 86400,))
            db.execute("""DELETE FROM discovery_history WHERE id NOT IN
                       (SELECT id FROM discovery_history ORDER BY id DESC LIMIT 999)""")
            db.execute("""INSERT INTO discovery_history(search_id, requested_at, request_json, status)
                       VALUES (?, ?, ?, 'pending')""", (search_id, now, request.model_dump_json()))
        return search_id

    def finish_search(self, search_id, count=None, cache_hit=False, error_code=None):
        with self.connection() as db:
            db.execute("""UPDATE discovery_history SET result_count=?, cache_hit=?, status=?, error_code=?
                       WHERE search_id=?""", (count, int(cache_hit), "error" if error_code else "success", error_code, search_id))

    def cached_search(self, cache_key, now):
        with self.connection() as db:
            row = db.execute("SELECT response_json FROM discovery_search_cache WHERE cache_key=? AND expires_at > ?",
                             (cache_key, now)).fetchone()
        return json.loads(row[0]) if row else None

    def cache_search(self, cache_key, response, expires):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO discovery_search_cache VALUES (?, ?, ?)",
                       (cache_key, json.dumps(response, ensure_ascii=False), expires))

    def cached_videos(self, ids, now):
        if not ids:
            return {}
        with self.connection() as db:
            rows = db.execute(f"SELECT video_id, metadata_json FROM discovery_videos WHERE expires_at > ? AND video_id IN ({','.join('?' for _ in ids)})",
                              (now, *ids)).fetchall()
        return {row["video_id"]: json.loads(row["metadata_json"]) for row in rows}

    def cache_videos(self, videos, expires):
        with self.connection() as db:
            db.executemany("INSERT OR REPLACE INTO discovery_videos VALUES (?, ?, ?)",
                           [(v["video_id"], json.dumps(v, ensure_ascii=False), expires) for v in videos])

    def reserve_api_call(self, cost, now):
        day = int(now // 86400)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO discovery_api_budget(day) VALUES (?)", (day,))
            budget = db.execute("SELECT * FROM discovery_api_budget WHERE day=?", (day,)).fetchone()
            if budget["blocked"] or budget["calls"] >= self.settings.api_calls_per_day or budget["units"] + cost > self.settings.quota_units_per_day:
                raise DiscoveryError("local_quota_exceeded", "Discovery daily API budget exhausted (UTC reset).", 429, True)
            db.execute("UPDATE discovery_api_budget SET calls=calls+1, units=units+? WHERE day=?", (cost, day))

    def block_day(self, now):
        with self.connection() as db:
            db.execute("UPDATE discovery_api_budget SET blocked=1 WHERE day=?", (int(now // 86400),))

    def history(self, limit, before_id, now):
        with self.connection() as db:
            rows = db.execute("""SELECT * FROM discovery_history WHERE id < ? AND requested_at >= ?
                              ORDER BY id DESC LIMIT ?""", (before_id or 2**63 - 1, now - 30 * 86400, limit + 1)).fetchall()
        items = [{
            "search_id": r["search_id"],
            "requested_at": datetime.fromtimestamp(r["requested_at"], timezone.utc),
            "request": json.loads(r["request_json"]), "result_count": r["result_count"],
            "cache_hit": bool(r["cache_hit"]), "status": r["status"], "error_code": r["error_code"],
        } for r in rows[:limit]]
        return {"items": items, "next_before_id": rows[limit - 1]["id"] if len(rows) > limit else None}
