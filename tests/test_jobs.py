import json
import time
from pathlib import Path

from scraperunner.config import ScrapeConfig
from scraperunner.web import jobs as jobs_module
from scraperunner.web.jobs import JOB_FILE, Job, JobManager, JobState
from scraperunner.web.scheduler import Scheduler


def fake_run(pages_html):
    """Replace run_crawl with something instant that reports one page per entry."""
    from scraperunner.models import Item, PageResult

    def run(config, on_page=None, on_image=None, should_stop=None):
        config.output_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for url, price in pages_html:
            page = PageResult(url=url, status=200, items=[Item(title="t", link=url + "#p", image=None, price=price, old_price=None, text="")])
            results.append(page)
            if on_page:
                on_page(page)
        with (config.output_dir / "pages.json").open("w", encoding="utf-8") as fh:
            json.dump([p.to_dict() for p in results], fh)
    return run


def wait_done(job: Job, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while job.state.is_active and time.time() < deadline:
        time.sleep(0.02)
    assert not job.state.is_active


def test_finished_jobs_are_saved_and_restored(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(jobs_module, "run_crawl", fake_run([("https://s.com/", "10 ₴")]))
    manager = JobManager(tmp_path)
    job = manager.start(ScrapeConfig(start_url="https://s.com/"))
    wait_done(job)

    assert job.state is JobState.DONE
    assert (tmp_path / job.id / JOB_FILE).exists()

    restored = JobManager(tmp_path).get(job.id)
    assert restored is not None
    assert restored.summary()["items"] == 1
    assert restored.pages[0].items[0].price == "10 ₴"   # loaded lazily from pages.json


def test_interrupted_job_is_marked_failed_on_restore(tmp_path: Path):
    folder = tmp_path / "abc"
    folder.mkdir()
    (folder / JOB_FILE).write_text(json.dumps({
        "id": "abc", "config": ScrapeConfig(start_url="https://s.com/", output_dir=folder).to_dict(),
        "state": "running", "created_at": 1.0,
    }), encoding="utf-8")
    job = JobManager(tmp_path).get("abc")
    assert job.state is JobState.FAILED and "restart" in job.error


def test_previous_run_of_same_url(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(jobs_module, "run_crawl", fake_run([("https://s.com/", "10 ₴")]))
    manager = JobManager(tmp_path)
    first = manager.start(ScrapeConfig(start_url="https://s.com/"))
    wait_done(first)
    other = manager.start(ScrapeConfig(start_url="https://other.com/"))
    wait_done(other)
    second = manager.start(ScrapeConfig(start_url="https://s.com/"))
    wait_done(second)

    assert manager.previous(second) is first
    assert manager.previous(first) is None


def test_scheduler_persists_and_launches_due_runs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(jobs_module, "run_crawl", fake_run([("https://s.com/", "10 ₴")]))
    manager = JobManager(tmp_path)
    scheduler = Scheduler(manager, tmp_path / "schedules.json", tick_seconds=3600)
    schedule, job = scheduler.add(ScrapeConfig(start_url="https://s.com/"), interval_hours=1)
    wait_done(job)
    assert job.schedule_id == schedule.id

    assert scheduler.run_due(now=time.time()) == []                 # not due yet
    (launched,) = scheduler.run_due(now=time.time() + 3601)          # due
    wait_done(launched)
    assert scheduler.get(schedule.id).last_job_id == launched.id

    reloaded = Scheduler(manager, tmp_path / "schedules.json", tick_seconds=3600)
    assert [s.id for s in reloaded.all()] == [schedule.id]
    assert reloaded.remove(schedule.id) and reloaded.all() == []
    scheduler.stop()
    reloaded.stop()
