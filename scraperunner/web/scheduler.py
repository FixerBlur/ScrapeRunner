from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from scraperunner.config import ScrapeConfig
from scraperunner.web.jobs import Job, JobManager

log = logging.getLogger(__name__)


@dataclass
class Schedule:
    """Rerun one crawl configuration every ``interval_hours``."""

    id: str
    config: ScrapeConfig
    interval_hours: float
    created_at: float
    next_run: float
    last_job_id: str | None = None
    keep_runs: int = 30  # older finished runs of this schedule are deleted

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "config": self.config.to_dict(),
            "interval_hours": self.interval_hours,
            "created_at": self.created_at,
            "next_run": self.next_run,
            "last_job_id": self.last_job_id,
            "keep_runs": self.keep_runs,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Schedule":
        return cls(
            id=data["id"],
            config=ScrapeConfig.from_dict(data["config"]),
            interval_hours=data["interval_hours"],
            created_at=data["created_at"],
            next_run=data["next_run"],
            last_job_id=data.get("last_job_id"),
            keep_runs=data.get("keep_runs", 30),
        )

    def summary(self) -> dict:
        return {**self.to_dict(), "start_url": self.config.start_url}


class Scheduler:
    """Launches due schedules from a background thread; the list persists as JSON."""

    def __init__(self, manager: JobManager, path: Path, tick_seconds: float = 30.0) -> None:
        self._manager = manager
        self._path = path
        self._tick = tick_seconds
        self._lock = threading.Lock()
        self._schedules: dict[str, Schedule] = {}
        self._load()
        self._stop = threading.Event()
        threading.Thread(target=self._loop, name="scheduler", daemon=True).start()

    def add(
        self, config: ScrapeConfig, interval_hours: float, keep_runs: int = 30, run_now: bool = True
    ) -> tuple[Schedule, Job | None]:
        now = time.time()
        schedule = Schedule(
            id=uuid4().hex[:12], config=config, interval_hours=interval_hours,
            created_at=now, next_run=now + interval_hours * 3600, keep_runs=keep_runs,
        )
        with self._lock:
            self._schedules[schedule.id] = schedule
            job = self._launch(schedule) if run_now else None
            self._save()
        return schedule, job

    def remove(self, schedule_id: str) -> bool:
        with self._lock:
            removed = self._schedules.pop(schedule_id, None) is not None
            if removed:
                self._save()
        return removed

    def run_now(self, schedule_id: str) -> Job | None:
        with self._lock:
            schedule = self._schedules.get(schedule_id)
            if schedule is None:
                return None
            job = self._launch(schedule)
            self._save()
            return job

    def get(self, schedule_id: str) -> Schedule | None:
        return self._schedules.get(schedule_id)

    def all(self) -> list[Schedule]:
        return sorted(self._schedules.values(), key=lambda s: s.created_at, reverse=True)

    def run_due(self, now: float | None = None) -> list[Job]:
        """Launch every schedule whose time has come. Called by the loop; public for tests."""
        now = time.time() if now is None else now
        started = []
        with self._lock:
            for schedule in self._schedules.values():
                if schedule.next_run <= now:
                    started.append(self._launch(schedule))
                    schedule.next_run = now + schedule.interval_hours * 3600
            if started:
                self._save()
        return started

    def stop(self) -> None:
        self._stop.set()

    def _launch(self, schedule: Schedule) -> Job:
        self._prune(schedule)
        job = self._manager.start(schedule.config, schedule_id=schedule.id)
        schedule.last_job_id = job.id
        log.info("Schedule %s started job %s", schedule.id, job.id)
        return job

    def _prune(self, schedule: Schedule) -> None:
        """Keep the newest ``keep_runs - 1`` finished runs so the new one fits the quota."""
        for old in self._manager.runs_of(schedule.id)[max(schedule.keep_runs - 1, 0):]:
            self._manager.delete(old.id)
            log.info("Schedule %s removed old run %s", schedule.id, old.id)

    def _loop(self) -> None:
        while not self._stop.wait(self._tick):
            try:
                self.run_due()
            except Exception:  # keep the loop alive whatever a launch does
                log.exception("Scheduler tick failed")

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump([s.to_dict() for s in self._schedules.values()], fh, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open(encoding="utf-8") as fh:
                self._schedules = {s["id"]: Schedule.from_dict(s) for s in json.load(fh)}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("Could not read %s: %s", self._path, exc)
