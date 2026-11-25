"""
Max's job runner: timed work stored in the `jobs` table (reminders, chasing overdue tasks, ...).

Every few seconds `tick()`:
  1. jobs left 'running' by a stop in the middle are marked failed, NOT repeated: they may already have posted
     (a reminder is sent at most once; a missing reminder is better than a double one);
  2. claims due jobs atomically (each job is handed out once, even with two runners);
  3. drops jobs that are too late to be useful ('missed', e.g. a "starts in 15 minutes" reminder 3 h late);
  4. runs the handler for the job's kind; an error before posting is retried with growing gaps, 3 tries.
A handler returns None (done) or a short status such as 'skipped' (e.g. the task was already closed).
Jobs are scheduled with a dedupe_key, so the same reminder is never scheduled twice.
"""

import json
import logging
from typing import Awaitable, Callable

from agent.clock import Clock
from store import Store

log = logging.getLogger("max")

MAX_LATE_S = {"remind_meeting": 10 * 60, "remind_task_due": 12 * 3600, "chase_overdue": 24 * 3600,
              "join_own_meeting": 20 * 60, "expire_approval": 7 * 86400}
DEFAULT_MAX_LATE_S = 6 * 3600
MAX_ATTEMPTS = 3

Handler = Callable[[dict], Awaitable[str | None]]


class JobRunner:
    def __init__(self, store: Store, clock: Clock, handlers: dict[str, Handler]):
        self.store, self.clock, self.handlers = store, clock, handlers

    @staticmethod
    def max_late(job: dict) -> float:
        payload = job.get("payload") or {}
        return payload.get("maxLateS") or MAX_LATE_S.get(job["kind"], DEFAULT_MAX_LATE_S)

    async def tick(self) -> dict:
        now = self.clock.now().timestamp()
        counts = {"done": 0, "skipped": 0, "missed": 0, "retry": 0, "failed": 0, "interrupted": 0}
        for j in self.store.stale_running_jobs(now):
            self.store.finish_job(j["id"], "failed", "interrupted while running; not repeated (may have posted)")
            counts["interrupted"] += 1
        for row in self.store.claim_jobs(now):
            job = dict(row)
            job["payload"] = json.loads(job["payload"] or "{}")
            late = now - job["run_at"]
            if late > self.max_late(job):
                self.store.finish_job(job["id"], "missed", f"{int(late)} s late")
                counts["missed"] += 1
                log.info("Job %s (%s) missed: %d s late", job["id"], job["kind"], late)
                continue
            handler = self.handlers.get(job["kind"])
            if handler is None:
                self.store.finish_job(job["id"], "failed", f"no handler for {job['kind']}")
                counts["failed"] += 1
                continue
            try:
                result = await handler(job)
            except Exception as e:  # the post did not go out: try again later, a few times
                err = f"{type(e).__name__}: {e}"[:300]
                if job["attempts"] < MAX_ATTEMPTS:
                    self.store.finish_job(job["id"], "pending", err, retry_at=now + 60 * job["attempts"] ** 2)
                    counts["retry"] += 1
                else:
                    self.store.finish_job(job["id"], "failed", err)
                    counts["failed"] += 1
                log.warning("Job %s (%s) error: %s", job["id"], job["kind"], err)
                continue
            status = result or "done"
            self.store.finish_job(job["id"], status)
            counts["skipped" if status == "skipped" else "done"] += 1
            log.info("Job %s (%s) %s", job["id"], job["kind"], status)
        return counts
