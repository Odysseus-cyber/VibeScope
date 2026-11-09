import logging, signal, time
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from .db import init_db, SessionLocal, utcnow
from .models import Job
from .pipeline import enqueue, process_next
from .config import settings

log = logging.getLogger("vibescope.worker")


def schedule(kind):
    with SessionLocal() as db:
        enqueue(db, kind)


def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    # A single worker process is the default. Persisted interrupted jobs are retryable.
    with SessionLocal() as db:
        for job in db.scalars(select(Job).where(Job.status == "running")):
            job.status = "failed"
            job.error = "Worker restarted before task completed; retry is available"
            job.finished_at = utcnow()
        db.commit()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        schedule, "cron", hour=0, minute=10, args=["sync"], id="daily_sync"
    )
    scheduler.add_job(schedule, "interval", hours=1, args=["hn"], id="hourly_hn")
    scheduler.add_job(
        schedule, "cron", day_of_week="mon", hour=1, args=["report"], id="weekly_report"
    )
    scheduler.start()
    stop = False

    def shutdown(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    log.info("Worker running in %s mode", settings.data_mode)
    try:
        while not stop:
            if not process_next():
                time.sleep(1)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
