"""Tests for the event store (append-only event log)."""
import time

import pytest

from platform.events import (
    Event,
    EventStore,
    MISSION_CREATED,
    PHASE_STARTED,
    PHASE_COMPLETED,
    AGENT_CALLED,
    TOOL_EXECUTED,
)


@pytest.fixture
def store(tmp_path):
    return EventStore(db_path=tmp_path / "test_events.db")


class TestEvent:
    def test_auto_id(self):
        e = Event(event_type="test")
        assert len(e.id) == 36  # UUID

    def test_auto_timestamp(self):
        e = Event(event_type="test")
        assert e.timestamp > 0

    def test_explicit_values(self):
        e = Event(id="x", event_type="t", aggregate_id="a", timestamp=1.0)
        assert e.id == "x"
        assert e.timestamp == 1.0


class TestEmit:
    def test_emit_and_query(self, store):
        store.emit_simple(MISSION_CREATED, "mission", "m-1", actor="user:alice", name="Test Mission")
        events = store.query(aggregate_id="m-1")
        assert len(events) == 1
        assert events[0].event_type == MISSION_CREATED
        assert events[0].actor == "user:alice"
        assert events[0].payload["name"] == "Test Mission"

    def test_emit_multiple(self, store):
        store.emit_simple(MISSION_CREATED, "mission", "m-1")
        store.emit_simple(PHASE_STARTED, "mission", "m-1", phase="design")
        store.emit_simple(PHASE_COMPLETED, "mission", "m-1", phase="design")
        events = store.replay("m-1")
        assert len(events) == 3
        assert [e.event_type for e in events] == [MISSION_CREATED, PHASE_STARTED, PHASE_COMPLETED]

    def test_emit_returns_event(self, store):
        e = store.emit_simple(AGENT_CALLED, "agent", "brain", tool="code_read")
        assert e.id
        assert e.event_type == AGENT_CALLED

    def test_listener_notified(self, store):
        received = []
        store.on_event(lambda e: received.append(e))
        store.emit_simple(TOOL_EXECUTED, "agent", "dev", tool="lint")
        assert len(received) == 1
        assert received[0].payload["tool"] == "lint"


class TestQuery:
    def test_filter_by_type(self, store):
        store.emit_simple(MISSION_CREATED, "mission", "m-1")
        store.emit_simple(PHASE_STARTED, "mission", "m-1")
        store.emit_simple(MISSION_CREATED, "mission", "m-2")
        events = store.query(event_type=MISSION_CREATED)
        assert len(events) == 2

    def test_filter_by_aggregate_type(self, store):
        store.emit_simple(AGENT_CALLED, "agent", "brain")
        store.emit_simple(PHASE_STARTED, "mission", "m-1")
        events = store.query(aggregate_type="agent")
        assert len(events) == 1

    def test_filter_by_since(self, store):
        store.emit(Event(event_type="old", aggregate_type="t", aggregate_id="a", timestamp=1000.0))
        store.emit(Event(event_type="new", aggregate_type="t", aggregate_id="a", timestamp=time.time()))
        events = store.query(since=time.time() - 60)
        assert len(events) == 1
        assert events[0].event_type == "new"

    def test_limit(self, store):
        for i in range(10):
            store.emit_simple("test", "t", "a")
        events = store.query(limit=3)
        assert len(events) == 3

    def test_empty_query(self, store):
        assert store.query() == []


class TestReplay:
    def test_replay_full_lifecycle(self, store):
        store.emit_simple(MISSION_CREATED, "mission", "m-1")
        store.emit_simple(PHASE_STARTED, "mission", "m-1", phase="design")
        store.emit_simple(AGENT_CALLED, "mission", "m-1", agent="architect")
        store.emit_simple(PHASE_COMPLETED, "mission", "m-1", phase="design")
        store.emit_simple(PHASE_STARTED, "mission", "m-1", phase="code")
        
        trail = store.replay("m-1")
        assert len(trail) == 5
        types = [e.event_type for e in trail]
        assert types[0] == MISSION_CREATED
        assert types[-1] == PHASE_STARTED

    def test_replay_isolates_aggregates(self, store):
        store.emit_simple(MISSION_CREATED, "mission", "m-1")
        store.emit_simple(MISSION_CREATED, "mission", "m-2")
        assert len(store.replay("m-1")) == 1
        assert len(store.replay("m-2")) == 1


class TestCount:
    def test_count_all(self, store):
        store.emit_simple("a", "t", "x")
        store.emit_simple("b", "t", "x")
        assert store.count() == 2

    def test_count_by_type(self, store):
        store.emit_simple(PHASE_STARTED, "mission", "m-1")
        store.emit_simple(PHASE_COMPLETED, "mission", "m-1")
        store.emit_simple(PHASE_STARTED, "mission", "m-2")
        assert store.count(event_type=PHASE_STARTED) == 2

    def test_count_by_aggregate(self, store):
        store.emit_simple("a", "mission", "m-1")
        store.emit_simple("b", "mission", "m-1")
        store.emit_simple("c", "mission", "m-2")
        assert store.count(aggregate_id="m-1") == 2


class TestStats:
    def test_stats_empty(self, store):
        s = store.stats()
        assert s["total"] == 0
        assert s["by_type"] == {}

    def test_stats_with_data(self, store):
        store.emit_simple(MISSION_CREATED, "mission", "m-1")
        store.emit_simple(PHASE_STARTED, "mission", "m-1")
        store.emit_simple(PHASE_STARTED, "mission", "m-2")
        s = store.stats()
        assert s["total"] == 3
        assert s["by_type"][PHASE_STARTED] == 2
        assert s["by_aggregate"]["mission"] == 3
