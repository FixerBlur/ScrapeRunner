from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from uuid import uuid4

from scraperunner.config import ScrapeConfig
from scraperunner.models import PageResult
from scraperunner.runner import run_crawl

log = logging.getLogger(__name__)

JOB_FILE = "job.json"


class JobState(str, Enum):
    RUNNING = "running"
    DOWNLOADING = "downloading"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def is_active(self) -> bool:
        return self in (JobState.RUNNING, JobState.DOWNLOADING)


@dataclass
class Job:
    """One crawl: live while its thread runs, then restored from ``job.json`` on later starts."""

    id: str
    config: ScrapeConfig
    state: JobState = JobState.RUNNING
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None
    schedule_id: str | None = None
    local_images: dict[str, str] = field(default_factory=dict)  # source URL -> served path
    stats: dict = field(default_factory=dict)                    # frozen at completion
    stop_requested: threading.Event = field(default_factory=threading.Event, repr=False)
    _pages: list[PageResult] | None = field(default=None, repr=False)

    @property
    def pages(self) -> list[PageResult]:
        if self._pages is None:
            self._pages = self._load_pages()
        return self._pages

    def summary(self) -> dict:
        stats = self.stats if not self.state.is_active else compute_stats(self._pages or [], self.local_images)
        return {
            "id": self.id,
            "state": self.state.value,
            "error": self.error,
            "start_url": self.config.start_url,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "schedule_id": self.schedule_id,
            "recent": [page.url for page in (self._pages or [])[-8:]] if self.state.is_active else [],
            **stats,
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "config": self.config.to_dict(),
            "state": self.state.value,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "schedule_id": self.schedule_id,
            "local_images": self.local_images,
            "stats": self.stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        state = JobState(data["state"])
        if state.is_active:  # the process died mid-run
            state, data = JobState.FAILED, {**data, "error": "Interrupted by server restart"}
        return cls(
            id=data["id"],
            config=ScrapeConfig.from_dict(data["config"]),
            state=state,
            created_at=data["created_at"],
            finished_at=data.get("finished_at"),
            error=data.get("error"),
            schedule_id=data.get("schedule_id"),
            local_images=data.get("local_images", {}),
            stats=data.get("stats", {}),
        )

    def _load_pages(self) -> list[PageResult]:
        path = self.config.output_dir / "pages.json"
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as fh:
            return [PageResult.from_dict(page) for page in json.load(fh)]


def compute_stats(pages: list[PageResult], local_images: dict[str, str]) -> dict:
    return {
        "pages_done": len(pages),
        "failed": sum(1 for page in pages if page.error),
        "items": sum(len(page.items) for page in pages),
        "links": sum(len(page.links) for page in pages),
        "images": len({image for page in pages for image in page.images}),
        "downloaded": len(local_images),
    }


class JobManager:
    """Starts crawls in daemon threads; finished runs persist on disk and are restored on startup."""

    def __init__(self, results_root: Path) -> None:
        self._root = results_root
        self._jobs: dict[str, Job] = {}
        self._restore()

    def start(self, config: ScrapeConfig, schedule_id: str | None = None) -> Job:
        job_id = uuid4().hex[:12]
        job = Job(id=job_id, config=replace(config, output_dir=self._root / job_id), schedule_id=schedule_id)
        job._pages = []
        self._jobs[job_id] = job
        threading.Thread(target=self._run, args=(job,), name=f"crawl-{job_id}", daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def previous(self, job: Job) -> Job | None:
        """The latest completed run of the same start URL before *job*."""
        earlier = (
            other for other in self._jobs.values()
            if other.state is JobState.DONE
            and other.config.start_url == job.config.start_url
            and other.created_at < job.created_at
        )
        return max(earlier, key=lambda other: other.created_at, default=None)

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or not job.state.is_active:
            return False
        job.stop_requested.set()
        return True

    def _run(self, job: Job) -> None:
        def on_image(url: str, path: Path | None) -> None:
            job.state = JobState.DOWNLOADING
            if path is not None:
                job.local_images[url] = f"/results/{path.relative_to(self._root).as_posix()}"

        try:
            run_crawl(
                job.config,
                on_page=job.pages.append,
                on_image=on_image,
                should_stop=job.stop_requested.is_set,
            )
        except Exception as exc:  # surfaced to the UI, so keep it broad
            log.exception("Job %s failed", job.id)
            job.state = JobState.FAILED
            job.error = str(exc)
        else:
            job.state = JobState.CANCELLED if job.stop_requested.is_set() else JobState.DONE
        job.finished_at = time.time()
        job.stats = compute_stats(job.pages, job.local_images)
        self._save(job)

    def _save(self, job: Job) -> None:
        job.config.output_dir.mkdir(parents=True, exist_ok=True)
        with (job.config.output_dir / JOB_FILE).open("w", encoding="utf-8") as fh:
            json.dump(job.to_dict(), fh, ensure_ascii=False, indent=2)

    def _restore(self) -> None:
        for job_file in sorted(self._root.glob(f"*/{JOB_FILE}")):
            try:
                with job_file.open(encoding="utf-8") as fh:
                    job = Job.from_dict(json.load(fh))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                log.warning("Skipping %s: %s", job_file, exc)
                continue
            self._jobs[job.id] = job
        if self._jobs:
            log.info("Restored %d previous runs from %s", len(self._jobs), self._root)
