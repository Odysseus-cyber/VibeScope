import os, subprocess, uuid
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from sqlalchemy import select, func
from .db import SessionLocal, utcnow
from .models import (
    Application,
    Snapshot,
    RawRecord,
    Coverage,
    Discussion,
    Classification,
    Job,
    AppSetting,
)
from .config import settings

KINDS = {"sync", "github", "hn", "classify", "warehouse", "report"}


def enqueue(db, kind):
    existing = db.scalar(
        select(Job)
        .where(Job.kind == kind, Job.status.in_(["queued", "running"]))
        .order_by(Job.created_at)
    )
    if existing:
        return existing
    job = Job(id=str(uuid.uuid4()), kind=kind)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def timestamp(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else utcnow()


def mark_dirty(db):
    obj = db.get(AppSetting, "warehouse_dirty")
    if obj:
        obj.value = True
    else:
        db.add(AppSetting(key="warehouse_dirty", value=True))


def ingest_event(db, event, job):
    kind = event["type"]
    now = utcnow()
    if kind == "raw":
        db.add(
            RawRecord(
                source=event["source"],
                source_id=str(event["source_id"]),
                payload=event["payload"],
                run_id=job.id,
            )
        )
    elif kind == "coverage":
        db.add(
            Coverage(
                source=event["source"],
                status=event["status"],
                detail=event.get("detail", {}),
                run_id=job.id,
            )
        )
        if event["status"] != "complete":
            job.errors += 1
    elif kind == "repository":
        data = event["data"]
        app = db.get(Application, data["id"])
        if not app:
            app = Application(
                id=data["id"],
                name=data["name"],
                full_name=data["full_name"],
                url=data["url"],
                created_at=timestamp(data.get("created_at")),
            )
            db.add(app)
        for key in [
            "name",
            "full_name",
            "description",
            "url",
            "homepage",
            "language",
            "readme",
            "stars",
            "forks",
        ]:
            if key in data:
                setattr(
                    app,
                    key,
                    (
                        data[key]
                        if data[key] is not None or key in ("homepage", "language")
                        else (0 if key in ("stars", "forks") else "")
                    ),
                )
        app.last_observed_at = now
        db.flush()
        snapshot = db.scalar(
            select(Snapshot).where(
                Snapshot.app_id == app.id, Snapshot.snapshot_date == now.date()
            )
        )
        if not snapshot:
            snapshot = Snapshot(
                app_id=app.id,
                snapshot_date=now.date(),
                stars=app.stars,
                forks=app.forks,
            )
            db.add(snapshot)
        else:
            snapshot.stars = app.stars
            snapshot.forks = app.forks
            snapshot.observed_at = now
        mark_dirty(db)
        job.processed += 1
    elif kind == "discussion":
        data = event.get("data", event)
        full_name = data.get("repo_full_name")
        app_id = (
            db.scalar(
                select(Application.id).where(
                    func.lower(Application.full_name) == full_name.lower()
                )
            )
            if full_name
            else None
        )
        disc = db.get(Discussion, data["id"])
        if not disc:
            disc = Discussion(
                id=data["id"],
                title=data["title"],
                url=data["url"],
                posted_at=timestamp(data.get("posted_at")),
            )
            db.add(disc)
        for key in ["title", "url", "score", "comments"]:
            setattr(disc, key, data.get(key, 0 if key in ("score", "comments") else ""))
        disc.app_id = app_id
        disc.observed_at = now
        job.processed += 1
    db.commit()


def relink_discussions(db):
    """Attach previously observed HN stories after their repository is discovered."""
    from .collectors import github_repo_from_url

    repositories = {
        name.lower(): app_id
        for app_id, name in db.execute(select(Application.id, Application.full_name))
    }
    linked = 0
    for discussion in db.scalars(select(Discussion).where(Discussion.app_id.is_(None))):
        full_name = github_repo_from_url(discussion.url)
        app_id = repositories.get(full_name) if full_name else None
        if app_id is not None:
            discussion.app_id = app_id
            linked += 1
    if linked:
        db.commit()
    return linked


def classify_pending(db, job):
    from .classifier import classify_project, content_fingerprint, PROMPT_VERSION

    today = utcnow().date()
    start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    used = db.scalar(
        select(func.count())
        .select_from(Classification)
        .where(
            Classification.classified_at >= start,
            Classification.method.in_(["llm", "rules"]),
        )
    )
    available = max(0, settings.daily_classification_limit - used)
    use_model = bool(
        settings.llm_base_url and settings.llm_api_key and settings.llm_model
    )
    target_method = "llm" if use_model else "rules"
    target_model = settings.llm_model if use_model else "deterministic-rules-v1"
    done = 0
    for app in db.scalars(
        select(Application)
        .where(Application.manual_override.is_(False))
        .order_by(Application.first_seen_at)
    ):
        fingerprint = content_fingerprint(app.description, app.readme)
        identity = {
            "content_hash": fingerprint,
            "method": target_method,
            "model": target_model,
            "prompt_version": PROMPT_VERSION,
            "base_url": settings.llm_base_url if use_model else "",
        }
        attempt = db.get(AppSetting, f"classification_attempt:{app.id}")
        last_attempt = (
            attempt.value if attempt and isinstance(attempt.value, dict) else {}
        )
        same_target = last_attempt.get("target") == identity
        same_result = (
            fingerprint == app.content_hash
            and app.method == target_method
            and app.model == target_model
            and app.prompt_version == PROMPT_VERSION
        )
        if same_result and (not last_attempt or same_target):
            continue
        # A provider failure must remain retryable, without consuming the daily
        # budget repeatedly for the same input/configuration on one day.
        if (
            same_target
            and not last_attempt.get("succeeded")
            and last_attempt.get("date") == today.isoformat()
        ):
            continue
        if done >= available:
            break
        result = classify_project(
            app.description,
            app.readme,
            app.url,
            llm_base_url=settings.llm_base_url,
            llm_api_key=settings.llm_api_key,
            llm_model=settings.llm_model,
        )
        for key in [
            "category",
            "kind",
            "tools",
            "summary",
            "evidence_level",
            "evidence",
            "method",
            "model",
            "prompt_version",
        ]:
            if key in result:
                setattr(app, key, result[key])
        app.content_hash = fingerprint
        app.classified_at = utcnow()
        db.add(
            Classification(
                app_id=app.id,
                category=app.category,
                kind=app.kind,
                evidence_level=app.evidence_level,
                tools=app.tools,
                evidence=app.evidence,
                method=app.method,
                model=app.model,
                prompt_version=app.prompt_version,
                content_hash=fingerprint,
            )
        )
        attempt_value = {
            "target": identity,
            "date": today.isoformat(),
            "succeeded": app.method == target_method and app.model == target_model,
        }
        if attempt:
            attempt.value = attempt_value
        else:
            db.add(
                AppSetting(key=f"classification_attempt:{app.id}", value=attempt_value)
            )
        mark_dirty(db)
        done += 1
        job.processed += 1
        db.commit()
    return {"classified": done, "remaining_daily_budget": available - done}


def run_warehouse(db):
    if not settings.warehouse_enabled:
        return {
            "status": "disabled",
            "detail": "SQL metrics available; dbt runs in PostgreSQL deployment",
        }
    if db.bind.dialect.name != "postgresql":
        return {"status": "disabled", "detail": "dbt warehouse requires PostgreSQL"}
    project = os.getenv("DBT_PROJECT_DIR", settings.warehouse_dir)
    command = [
        "dbt",
        "build",
        "--project-dir",
        project,
        "--profiles-dir",
        os.getenv("DBT_PROFILES_DIR", project),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=240)
    if result.returncode:
        raise RuntimeError("dbt build failed: " + result.stdout[-2500:])
    item = db.get(AppSetting, "warehouse_dirty")
    if item:
        item.value = False
    else:
        db.add(AppSetting(key="warehouse_dirty", value=False))
    db.commit()
    return {"status": "succeeded", "detail": "dbt models and data tests passed"}


def process_next():
    with SessionLocal() as db:
        query = (
            select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1)
        )
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        job = db.scalar(query)
        if not job:
            return False
        job.status = "running"
        job.started_at = utcnow()
        job.progress = 5
        db.commit()
        try:
            summary = {}
            collected = 0
            if job.kind == "report":
                from .reporting import create_report

                report = create_report(db)
                summary = {"report_id": report.id}
            elif settings.data_mode == "demo" and job.kind in (
                "sync",
                "github",
                "hn",
                "classify",
            ):
                from .seed import seed_demo

                summary = {
                    "mode": "demo",
                    "seeded": seed_demo(db),
                    "note": "演示模式未访问外部数据源",
                }
                summary["warehouse"] = run_warehouse(db)
            else:
                if job.kind in ("sync", "github", "hn"):
                    from .collectors import GitHubCollector, HNCollector

                    if job.kind in ("sync", "github"):
                        existing = [
                            {"id": a.id, "full_name": a.full_name}
                            for a in db.scalars(select(Application))
                        ]
                        for event in GitHubCollector(
                            token=settings.github_token, limit=settings.tracking_limit
                        ).iter_records(existing, utcnow().date() - timedelta(days=90)):
                            ingest_event(db, event, job)
                            if event["type"] == "repository":
                                collected += 1
                        summary["relinked_discussions"] = relink_discussions(db)
                    job.progress = 40
                    db.commit()
                    if job.kind in ("sync", "hn"):
                        ids = list(
                            db.scalars(
                                select(Discussion.id)
                                .order_by(Discussion.posted_at.desc())
                                .limit(200)
                            )
                        )
                        for event in HNCollector().iter_records(existing_ids=ids):
                            ingest_event(db, event, job)
                            if event["type"] == "discussion":
                                collected += 1
                job.progress = 70
                db.commit()
                if job.kind in ("sync", "github", "classify"):
                    summary.update(classify_pending(db, job))
                if job.kind in ("sync", "github", "classify", "warehouse"):
                    summary["warehouse"] = run_warehouse(db)
            if settings.data_mode == "live" and job.kind in ("sync", "github", "hn"):
                summary["collected_records"] = collected
            job.summary = summary
            job.status = "partial" if job.errors else "succeeded"
            if (
                settings.data_mode == "live"
                and job.kind in ("sync", "github", "hn")
                and job.errors
                and collected == 0
            ):
                job.status = "failed"
                job.error = "No source records were collected successfully; see source coverage for errors."
            job.progress = 100
        except Exception as exc:
            db.rollback()
            job = db.get(Job, job.id)
            job.status = "failed"
            job.errors += 1
            message = str(exc)
            for secret in (settings.github_token, settings.llm_api_key):
                if secret:
                    message = message.replace(secret, "[redacted]")
            job.error = f"{type(exc).__name__}: {message[:3000]}"
        job.finished_at = utcnow()
        db.commit()
    return True
