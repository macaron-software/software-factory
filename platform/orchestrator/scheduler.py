"""
WSJF Scheduler - Weighted Shortest Job First with WIP limits.
===============================================================
Priority queue with aging, preemption, and load balancing.
"""

from __future__ import annotations

import heapq
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(order=True)
class ScheduledTask:
    """A task in the priority queue."""
    priority_score: float              # Lower = higher priority (heap is min-heap)
    task_id: str = field(compare=False)
    session_id: str = field(compare=False)
    description: str = field(compare=False, default="")
    assigned_agent: Optional[str] = field(compare=False, default=None)
    created_at: float = field(compare=False, default_factory=time.time)
    started_at: Optional[float] = field(compare=False, default=None)
    business_value: float = field(compare=False, default=5.0)
    time_criticality: float = field(compare=False, default=5.0)
    risk_reduction: float = field(compare=False, default=5.0)
    job_size: float = field(compare=False, default=5.0)
    status: str = field(compare=False, default="pending")  # pending, running, done, failed


class WsjfScheduler:
    """WSJF-based scheduler with WIP limits and aging."""

    def __init__(self, wip_limit: int = 15, aging_factor: float = 0.1):
        self.wip_limit = wip_limit
        self.aging_factor = aging_factor
        self._queue: list[ScheduledTask] = []
        self._running: dict[str, ScheduledTask] = {}
        self._completed: list[ScheduledTask] = []

    def calculate_wsjf(self, task: ScheduledTask) -> float:
        """Calculate WSJF score. Higher = more urgent."""
        cost_of_delay = task.business_value + task.time_criticality + task.risk_reduction
        # Add aging: tasks get more urgent over time
        age_minutes = (time.time() - task.created_at) / 60.0
        aging_bonus = age_minutes * self.aging_factor

        wsjf = (cost_of_delay + aging_bonus) / max(task.job_size, 0.1)
        return wsjf

    def enqueue(self, task: ScheduledTask) -> bool:
        """Add a task to the queue. Returns False if queue is full."""
        # Use negative WSJF because heapq is min-heap (we want max WSJF first)
        task.priority_score = -self.calculate_wsjf(task)
        heapq.heappush(self._queue, task)
        logger.debug(f"Enqueued task {task.task_id[:8]} (WSJF={-task.priority_score:.1f})")
        return True

    def dequeue(self) -> Optional[ScheduledTask]:
        """Get the highest priority task (respecting WIP limit)."""
        if len(self._running) >= self.wip_limit:
            return None
        if not self._queue:
            return None

        # Recalculate priorities (aging)
        refreshed = []
        while self._queue:
            task = heapq.heappop(self._queue)
            task.priority_score = -self.calculate_wsjf(task)
            refreshed.append(task)

        for t in refreshed:
            heapq.heappush(self._queue, t)

        task = heapq.heappop(self._queue)
        task.status = "running"
        task.started_at = time.time()
        self._running[task.task_id] = task
        return task

    def complete(self, task_id: str, success: bool = True):
        """Mark a task as completed."""
        task = self._running.pop(task_id, None)
        if task:
            task.status = "done" if success else "failed"
            self._completed.append(task)

    def cancel(self, task_id: str):
        """Cancel a running task."""
        task = self._running.pop(task_id, None)
        if task:
            task.status = "pending"
            task.started_at = None
            self.enqueue(task)

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def running_count(self) -> int:
        return len(self._running)

    @property
    def wip_available(self) -> int:
        return max(0, self.wip_limit - len(self._running))

    def get_stats(self) -> dict:
        return {
            "pending": self.pending_count,
            "running": self.running_count,
            "completed": len(self._completed),
            "wip_limit": self.wip_limit,
            "wip_used": self.running_count,
            "wip_available": self.wip_available,
        }
