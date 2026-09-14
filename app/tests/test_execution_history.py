import pytest

from execution.schemas import Job, JobRequest
from execution.store import JobStore


def test_historical_jobs_and_events_remain_scoped_after_queue_retirement(tmp_path):
    store = JobStore(str(tmp_path / 'history.sqlite3'))
    job = Job(job_id='legacy', owner='alice', request=JobRequest(conversation_id='old', payload={}, idempotency_key='legacy'), status='succeeded', created_at=1, updated_at=2, worker_id='old-worker', result={'content': 'retained'})
    with store.connect() as db:
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', ('legacy','alice','legacy','fingerprint',0,1,'succeeded',None,job.model_dump_json()))
        store._event(db, 'legacy', 'succeeded', {})
    reopened = JobStore(store.path)
    assert reopened.get('legacy', 'alice').result == {'content': 'retained'}
    assert reopened.events('legacy', 'alice')[0].event == 'succeeded'
    with pytest.raises(KeyError):
        reopened.get('legacy', 'bob')
    assert not hasattr(reopened, 'claim') and not hasattr(reopened, 'submit')
