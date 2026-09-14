import hashlib
import json
import time
import uuid

from .schemas import Job, JobRequest
from .store import JobStore, TERMINAL


class TurnStore(JobStore):
    def __init__(self, path):
        super().__init__(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    owner TEXT NOT NULL, conversation TEXT NOT NULL, thread TEXT,
                    PRIMARY KEY(owner, conversation)
                );
                CREATE TABLE IF NOT EXISTS inputs (
                    owner TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    execution TEXT NOT NULL, error TEXT, PRIMARY KEY(owner, key)
                );
            """)
            if "error" not in {row[1] for row in db.execute("PRAGMA table_info(inputs)")}:
                db.execute("ALTER TABLE inputs ADD COLUMN error TEXT")

    def existing(self, owner, request):
        fingerprint = self.fingerprint(request)
        with self.connect() as db:
            row = db.execute("SELECT * FROM inputs WHERE owner=? AND key=?", (owner, request.idempotency_key)).fetchone()
            if not row:
                return None
            if row["fingerprint"] != fingerprint:
                raise ValueError("Idempotency key already used for a different request")
            if row["error"]:
                raise ValueError(row["error"])
            return self._get(db, row["execution"], owner)

    @staticmethod
    def fingerprint(request):
        payload = {key: value for key, value in request.payload.items() if key not in {"history", "history_path", "runtime_context", "persona", "directives", "specialist_directives"}}
        return hashlib.sha256(json.dumps({"conversation_id": request.conversation_id, "kind": request.kind, "payload": payload}, sort_keys=True, allow_nan=False).encode()).hexdigest()

    def record_input(self, owner, request, execution):
        with self.connect() as db:
            db.execute("INSERT INTO inputs VALUES(?,?,?,?,?)", (owner, request.idempotency_key, self.fingerprint(request), execution, "Follow-up acceptance is pending or uncertain. Inspect turn events before explicitly retrying with a new key."))

    def confirm_input(self, owner, key):
        with self.connect() as db:
            db.execute("UPDATE inputs SET error=NULL WHERE owner=? AND key=?", (owner, key))

    def start(self, owner: str, request: JobRequest) -> Job:
        now = time.time()
        job = Job(job_id=uuid.uuid4().hex, owner=owner, request=request, status="starting", worker_id="native", created_at=now, updated_at=now)
        with self.connect() as db:
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)", (job.job_id, owner, request.idempotency_key, self.fingerprint(request), request.priority, now, job.status, None, job.model_dump_json()))
            db.execute("INSERT INTO inputs VALUES(?,?,?,?,NULL)", (owner, request.idempotency_key, self.fingerprint(request), job.job_id))
            self._event(db, job.job_id, "starting", {})
        return job

    def save(self, job):
        with self.connect() as db:
            self._save(db, job)
        return job

    def thread(self, owner, conversation):
        with self.connect() as db:
            row = db.execute("SELECT thread FROM conversations WHERE owner=? AND conversation=?", (owner, conversation)).fetchone()
            return row["thread"] if row else None

    def bind(self, job):
        with self.connect() as db:
            db.execute("INSERT INTO conversations VALUES(?,?,?) ON CONFLICT(owner,conversation) DO UPDATE SET thread=excluded.thread", (job.owner, job.request.conversation_id, job.thread_id))
            self._save(db, job)

    def list(self, owner=None, conversation=None, active=False, undelivered=False):
        conditions, params = [], []
        for column, value in (("owner", owner), ("json_extract(document, '$.request.conversation_id')", conversation)):
            if value is not None:
                conditions.append(column + "=?")
                params.append(value)
        if active:
            conditions.append("status IN ('starting','running','cancel_requested')")
        if undelivered:
            conditions.append("json_extract(document, '$.request.payload.delivery') IS NOT NULL AND coalesce(json_extract(document, '$.result.delivered'), 0)=0")
        query = "SELECT document FROM jobs" + (" WHERE " + " AND ".join(conditions) if conditions else "") + " ORDER BY created"
        with self.connect() as db:
            return [Job.model_validate_json(row[0]) for row in db.execute(query, params)]

    def event(self, job_id, event, data):
        with self.connect() as db:
            self._get(db, job_id)
            self._event(db, job_id, event, data)
