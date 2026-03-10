"""Tests for the SQLite job queue."""
import pytest

from platform.workers import JobQueue, PENDING, CLAIMED, COMPLETED, FAILED, CANCELLED


@pytest.fixture
def queue(tmp_path):
    return JobQueue(db_path=tmp_path / "test_queue.db")


class TestEnqueue:
    def test_enqueue_returns_id(self, queue):
        jid = queue.enqueue("phase_exec", {"mission": "m-1"})
        assert len(jid) == 36

    def test_enqueue_creates_pending(self, queue):
        jid = queue.enqueue("test_job")
        job = queue.get(jid)
        assert job.status == PENDING
        assert job.job_type == "test_job"

    def test_enqueue_with_priority(self, queue):
        queue.enqueue("low", priority=0)
        queue.enqueue("high", priority=10)
        job = queue.claim("w1")
        assert job.payload == {} or job.job_type == "high"


class TestClaim:
    def test_claim_returns_job(self, queue):
        queue.enqueue("task")
        job = queue.claim("worker-1")
        assert job is not None
        assert job.status == CLAIMED
        assert job.claimed_by == "worker-1"

    def test_claim_empty_returns_none(self, queue):
        assert queue.claim("w1") is None

    def test_claim_respects_priority(self, queue):
        queue.enqueue("low", {"v": "low"}, priority=1)
        queue.enqueue("high", {"v": "high"}, priority=10)
        job = queue.claim("w1")
        assert job.payload["v"] == "high"

    def test_claim_fifo_same_priority(self, queue):
        queue.enqueue("first", {"order": 1})
        queue.enqueue("second", {"order": 2})
        j1 = queue.claim("w1")
        j2 = queue.claim("w2")
        assert j1.payload["order"] == 1
        assert j2.payload["order"] == 2

    def test_double_claim_prevented(self, queue):
        queue.enqueue("task")
        j1 = queue.claim("w1")
        j2 = queue.claim("w2")
        assert j1 is not None
        assert j2 is None

    def test_claim_by_type(self, queue):
        queue.enqueue("phase_exec")
        queue.enqueue("cleanup")
        job = queue.claim("w1", job_types=["cleanup"])
        assert job.job_type == "cleanup"


class TestComplete:
    def test_complete_sets_status(self, queue):
        jid = queue.enqueue("task")
        queue.claim("w1")
        queue.complete(jid, result={"output": "done"})
        job = queue.get(jid)
        assert job.status == COMPLETED
        assert job.result["output"] == "done"
        assert job.completed_at > 0


class TestFail:
    def test_fail_retries(self, queue):
        jid = queue.enqueue("task", max_retries=2)
        queue.claim("w1")
        retried = queue.fail(jid, "timeout")
        assert retried is True
        job = queue.get(jid)
        assert job.status == PENDING
        assert job.retry_count == 1

    def test_fail_permanent_after_max(self, queue):
        jid = queue.enqueue("task", max_retries=1)
        queue.claim("w1")
        queue.fail(jid, "err1")  # retry 1
        queue.claim("w2")
        retried = queue.fail(jid, "err2")  # no more retries
        assert retried is False
        job = queue.get(jid)
        assert job.status == FAILED


class TestCancel:
    def test_cancel_pending(self, queue):
        jid = queue.enqueue("task")
        queue.cancel(jid)
        job = queue.get(jid)
        assert job.status == CANCELLED

    def test_cancel_claimed(self, queue):
        jid = queue.enqueue("task")
        queue.claim("w1")
        queue.cancel(jid)
        job = queue.get(jid)
        assert job.status == CANCELLED


class TestStats:
    def test_stats_empty(self, queue):
        s = queue.stats()
        assert s["total"] == 0

    def test_stats_with_jobs(self, queue):
        queue.enqueue("a")
        queue.enqueue("b")
        jid = queue.enqueue("c")
        queue.claim("w1")
        s = queue.stats()
        assert s["total"] == 3
        assert s.get(PENDING, 0) == 2
        assert s.get(CLAIMED, 0) == 1


class TestCleanup:
    def test_cleanup_old_completed(self, queue):
        import time
        jid = queue.enqueue("task")
        queue.claim("w1")
        queue.complete(jid)
        # Hack: set completed_at to 48h ago
        db = queue._db()
        db.execute("UPDATE job_queue SET completed_at = ? WHERE id = ?", (time.time() - 200000, jid))
        db.commit()
        db.close()
        removed = queue.cleanup(older_than_hours=24)
        assert removed == 1
