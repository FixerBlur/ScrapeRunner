from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from scraperunner.compare import compare_items
from scraperunner.config import FetchMode, ScrapeConfig, Selectors
from scraperunner.parser.items import validate_selectors
from scraperunner.web.jobs import Job, JobManager
from scraperunner.web.scheduler import Scheduler

STATIC_DIR = Path(__file__).parent / "static"
EXPORT_FILES = ("items.xlsx", "items.csv", "items.json", "pages.json", "links.csv")
SELECTOR_FIELDS = ("card", "title", "price", "old_price", "link", "image")


class JobRequest(BaseModel):
    """Form payload. Field names mirror ScrapeConfig so they map 1:1."""

    url: str = Field(min_length=1)
    depth: int = Field(1, ge=0, le=10)
    max_pages: int = Field(50, ge=1, le=5000)
    mode: FetchMode = FetchMode.AUTO
    pages: str | None = None
    page_pattern: str | None = None
    delay: float = Field(0.5, ge=0)
    timeout: float = Field(15.0, gt=0)
    retries: int = Field(2, ge=0, le=10)
    concurrency: int = Field(4, ge=1, le=16)
    proxy: str | None = None
    same_domain: bool = True
    respect_robots: bool = True
    extract_text: bool = False
    download_images: bool = False
    selectors: dict[str, str | None] = Field(default_factory=dict)
    repeat_hours: float | None = Field(None, gt=0, le=24 * 30)
    keep_runs: int = Field(30, ge=1, le=1000)

    @field_validator("pages", "page_pattern", "proxy", mode="before")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("selectors")
    @classmethod
    def _valid_selectors(cls, value: dict) -> dict:
        unknown = set(value) - set(SELECTOR_FIELDS)
        if unknown:
            raise ValueError(f"Unknown selector fields: {sorted(unknown)}")
        cleaned = {name: (text.strip() or None) if isinstance(text, str) else None for name, text in value.items()}
        validate_selectors(Selectors(**cleaned))
        return cleaned

    def to_config(self) -> ScrapeConfig:
        data = self.model_dump(exclude={"url", "selectors", "repeat_hours", "keep_runs"})
        return ScrapeConfig(start_url=self.url, selectors=Selectors(**self.selectors), **data)


def create_app(results_root: Path = Path("results")) -> FastAPI:
    results_root.mkdir(parents=True, exist_ok=True)
    manager = JobManager(results_root)
    scheduler = Scheduler(manager, results_root / "schedules.json")

    app = FastAPI(title="ScrapeRunner", docs_url="/api/docs", redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/results", StaticFiles(directory=results_root), name="results")

    def job_or_404(job_id: str) -> Job:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return job

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    # --- jobs ---------------------------------------------------------------

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return [job.summary() for job in manager.all()]

    @app.post("/api/jobs", status_code=201)
    def start_job(request: JobRequest) -> dict:
        config = request.to_config()
        if request.repeat_hours:
            schedule, job = scheduler.add(config, request.repeat_hours, keep_runs=request.keep_runs)
            return {**job.summary(), "schedule": schedule.summary()}
        return manager.start(config).summary()

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict:
        return job_or_404(job_id).summary()

    @app.get("/api/jobs/{job_id}/pages")
    def job_pages(job_id: str) -> dict:
        job = job_or_404(job_id)
        return {"pages": [page.to_dict() for page in job.pages], "local_images": job.local_images}

    @app.get("/api/jobs/{job_id}/changes")
    def job_changes(job_id: str, against: str | None = None) -> dict:
        job = job_or_404(job_id)
        previous = job_or_404(against) if against else manager.previous(job)
        if previous is None:
            return {"against": None, "changes": None}
        changes = compare_items(
            [item for page in previous.pages for item in page.items],
            [item for page in job.pages for item in page.items],
        )
        return {"against": previous.summary(), "changes": changes.to_dict()}

    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: str) -> dict:
        job = job_or_404(job_id)
        if job.state.is_active:
            raise HTTPException(409, "Cancel the run before deleting it")
        return {"deleted": manager.delete(job_id)}

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        job_or_404(job_id)
        return {"cancelled": manager.cancel(job_id)}

    @app.get("/api/jobs/{job_id}/files/{name}")
    def job_file(job_id: str, name: str) -> FileResponse:
        job = job_or_404(job_id)
        path = job.config.output_dir / name
        if name not in EXPORT_FILES or not path.exists():
            raise HTTPException(404, "File not found")
        return FileResponse(path, filename=f"{job_id}-{name}")

    # --- schedules ----------------------------------------------------------

    @app.get("/api/schedules")
    def list_schedules() -> list[dict]:
        return [schedule.summary() for schedule in scheduler.all()]

    @app.post("/api/schedules/{schedule_id}/run")
    def run_schedule(schedule_id: str) -> dict:
        job = scheduler.run_now(schedule_id)
        if job is None:
            raise HTTPException(404, "Schedule not found")
        return job.summary()

    @app.delete("/api/schedules/{schedule_id}")
    def delete_schedule(schedule_id: str) -> dict:
        if not scheduler.remove(schedule_id):
            raise HTTPException(404, "Schedule not found")
        return {"deleted": True}

    return app


app = create_app()
