import threading
import uuid
from typing import Any, Callable

from app.services import analyzer

ProgressCallback = Callable[[int, int, str, str], None]

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _run_job(job_id: str, mode: str = "swing", target_date: str | None = None) -> None:
    def on_progress(done: int, total: int, phase: str, message: str) -> None:
        pct = int((done / total) * 100) if total else 0
        _update(job_id, progress=pct, total=total, done=done, phase=phase, message=message)

    try:
        result = analyzer.run_full_analysis(mode=mode, target_date=target_date, progress_callback=on_progress)
        _update(
            job_id,
            status="completed",
            progress=100,
            message="Analysis complete",
            result=result,
        )
        try:
            from app.services.redis_cache import invalidate_all_caches
            invalidate_all_caches()
        except Exception as e:
            print(f"Failed to invalidate cache after job run: {e}")
    except Exception as exc:
        _update(
            job_id,
            status="failed",
            message="Analysis failed",
            error=str(exc),
        )


def start_job(mode: str = "swing", target_date: str | None = None) -> str:
    from app.services import market_data

    existing = get_running_job()
    if existing:
        return existing["job_id"]

    job_id = str(uuid.uuid4())
    total = len(market_data.get_watchlist())
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "progress": 0,
            "total": total,
            "done": 0,
            "phase": "starting",
            "message": "Starting analysis…",
            "result": None,
            "error": None,
            "trade_mode": mode,
            "target_date": target_date,
        }
    thread = threading.Thread(target=_run_job, args=(job_id, mode, target_date), daemon=True)
    thread.start()
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def get_running_job() -> dict[str, Any] | None:
    with _lock:
        for job in _jobs.values():
            if job.get("status") == "running":
                return dict(job)
    return None
