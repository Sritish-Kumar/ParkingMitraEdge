"""
edge/outbox.py — the durable buffer that survives crashes and outages.

Every event is written here BEFORE we try to publish it, and only marked
sent once the broker has acknowledged it. That ordering is the whole
point:

    write to disk  ->  publish  ->  mark sent

If we crash between step 1 and 3, the event is still on disk and gets
republished at startup. If we had published first and crashed before
recording it, the event would be gone with no way to know.

Because every payload carries a unique event_id and the central Ingest
rejects IDs it has already seen, republishing is always safe. Sending
twice costs nothing. Losing one loses a violation.
"""

import json
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    event_id   TEXT PRIMARY KEY,
    topic      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at REAL NOT NULL,
    sent_at    REAL
);
CREATE INDEX IF NOT EXISTS idx_unsent ON outbox (sent_at, created_at);
"""


class Outbox:
    def __init__(self, path: str = "outbox.db"):
        # check_same_thread=False: the pipeline writes, the publisher reads.
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        # WAL lets a reader and a writer work at the same time.
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.commit()
        self._lock = threading.Lock()

    def add(self, topic: str, payload: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO outbox VALUES (?, ?, ?, ?, NULL)",
                (payload["event_id"], topic, json.dumps(payload), time.time()),
            )
            self._db.commit()

    def pending(self, limit: int = 50) -> list[tuple]:
        """Oldest unsent first, so events leave in the order they happened."""
        with self._lock:
            return self._db.execute(
                "SELECT event_id, topic, payload FROM outbox "
                "WHERE sent_at IS NULL ORDER BY created_at LIMIT ?",
                (limit,),
            ).fetchall()

    def mark_sent(self, event_id: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE outbox SET sent_at = ? WHERE event_id = ?",
                (time.time(), event_id),
            )
            self._db.commit()

    def counts(self) -> tuple[int, int]:
        with self._lock:
            unsent = self._db.execute(
                "SELECT COUNT(*) FROM outbox WHERE sent_at IS NULL"
            ).fetchone()[0]
            sent = self._db.execute(
                "SELECT COUNT(*) FROM outbox WHERE sent_at IS NOT NULL"
            ).fetchone()[0]
            return unsent, sent

    def purge_sent(self, older_than_seconds: float = 86400) -> int:
        """Keep sent events for a day as a local audit trail, then drop them."""
        with self._lock:
            cur = self._db.execute(
                "DELETE FROM outbox WHERE sent_at IS NOT NULL AND sent_at < ?",
                (time.time() - older_than_seconds,),
            )
            self._db.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._db.close()