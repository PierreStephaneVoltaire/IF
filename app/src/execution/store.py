import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .schemas import Job, JobEvent


TERMINAL = {"succeeded", "failed", "cancelled", "uncertain"}


class JobStore:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, key TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, priority INTEGER NOT NULL,
                    created REAL NOT NULL, status TEXT NOT NULL, lease REAL,
                    document TEXT NOT NULL, UNIQUE(owner, key)
                );
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status, priority, created);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                    event TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _save(self, db, job: Job):
        job.updated_at = time.time()
        db.execute("UPDATE jobs SET status=?, lease=?, document=? WHERE id=?",
                   (job.status, job.lease_until, job.model_dump_json(), job.job_id))

    def _event(self, db, job_id: str, event: str, data: dict):
        db.execute("INSERT INTO events(job_id,event,data,created) VALUES(?,?,?,?)",
                   (job_id, event, json.dumps(data, allow_nan=False), time.time()))


    def get(self, job_id: str, owner: str | None = None) -> Job:
        with self.connect() as db:
            return self._get(db, job_id, owner)

    def _get(self, db, job_id: str, owner: str | None = None) -> Job:
        row = db.execute("SELECT document FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        job = Job.model_validate_json(row["document"])
        if owner is not None and owner != job.owner:
            raise KeyError(job_id)
        return job


    def events(self, job_id: str, owner: str, after: int = 0) -> list[JobEvent]:
        with self.connect() as db:
            self._get(db, job_id, owner)
            return [JobEvent(sequence=row['sequence'], job_id=job_id, event=row['event'], data=json.loads(row['data']), created_at=row['created']) for row in db.execute("SELECT * FROM events WHERE job_id=? AND sequence>? ORDER BY sequence LIMIT 100", (job_id, after))]
