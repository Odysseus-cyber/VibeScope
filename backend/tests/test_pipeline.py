from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import pipeline, collectors, classifier
from app.config import settings
from app.db import Base
from app.models import Application, Classification, Discussion, Job


@pytest.fixture
def sessions(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(pipeline, "SessionLocal", factory)
    monkeypatch.setattr(settings, "data_mode", "live")
    monkeypatch.setattr(settings, "warehouse_enabled", False)
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "daily_classification_limit", 100)
    yield factory
    engine.dispose()


def add_app(db, app_id=1, **changes):
    values = dict(
        id=app_id,
        name="TaskApp",
        full_name=f"maker/app-{app_id}",
        url=f"https://github.com/maker/app-{app_id}",
        description="A task manager",
        readme="Built with Cursor.",
        created_at=datetime.now(timezone.utc),
    )
    values.update(changes)
    app = Application(**values)
    db.add(app)
    db.commit()
    return app


def test_all_source_failure_is_failed_not_partial(sessions, monkeypatch):
    monkeypatch.setattr(
        collectors.GitHubCollector,
        "iter_records",
        lambda self, *a, **k: iter(
            [
                {
                    "type": "coverage",
                    "source": "github",
                    "status": "failed",
                    "detail": {"reason": "rate limited"},
                }
            ]
        ),
    )
    with sessions() as db:
        job_id = pipeline.enqueue(db, "github").id
    pipeline.process_next()
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "failed"
        assert job.summary["collected_records"] == 0
        assert "No source records" in job.error


def test_some_source_success_is_partial(sessions, monkeypatch):
    events = [
        {
            "type": "repository",
            "data": {
                "id": 1,
                "name": "TaskApp",
                "full_name": "maker/app-1",
                "url": "https://github.com/maker/app-1",
                "created_at": "2026-10-01T00:00:00Z",
                "description": "Task app",
                "readme": "Built with Cursor.",
                "stars": 42,
                "forks": 1,
            },
        },
        {
            "type": "coverage",
            "source": "github",
            "status": "partial",
            "detail": {"reason": "sample limit"},
        },
    ]
    monkeypatch.setattr(
        collectors.GitHubCollector, "iter_records", lambda self, *a, **k: iter(events)
    )
    with sessions() as db:
        job_id = pipeline.enqueue(db, "github").id
    pipeline.process_next()
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "partial"
        assert job.summary["collected_records"] == 1
        assert job.summary["classified"] == 1


def test_enabling_llm_reclassifies_unchanged_content(sessions, monkeypatch):
    with sessions() as db:
        app = add_app(db)
        job = pipeline.enqueue(db, "classify")
        assert pipeline.classify_pending(db, job)["classified"] == 1
        assert pipeline.classify_pending(db, job)["classified"] == 0
        monkeypatch.setattr(settings, "llm_base_url", "https://model.example/v1")
        monkeypatch.setattr(settings, "llm_api_key", "test-token")
        monkeypatch.setattr(settings, "llm_model", "test-model")
        calls = []

        def successful_model(*args, **kwargs):
            calls.append(kwargs)
            return {
                **classifier._rules(*args[:3]),
                "method": "llm",
                "model": "test-model",
            }

        monkeypatch.setattr(classifier, "classify_project", successful_model)
        assert pipeline.classify_pending(db, job)["classified"] == 1
        assert app.method == "llm"
        assert pipeline.classify_pending(db, job)["classified"] == 0
        assert len(calls) == 1


def test_model_fallback_retries_next_day_but_not_same_day(sessions, monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "https://model.example/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-token")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    calls = []

    def failing_model(*args, **kwargs):
        calls.append(1)
        return {**classifier._rules(*args[:3]), "fallback_reason": "provider_error"}

    monkeypatch.setattr(classifier, "classify_project", failing_model)
    with sessions() as db:
        add_app(db)
        job = pipeline.enqueue(db, "classify")
        assert pipeline.classify_pending(db, job)["classified"] == 1
        assert pipeline.classify_pending(db, job)["classified"] == 0
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        monkeypatch.setattr(pipeline, "utcnow", lambda: tomorrow)
        assert pipeline.classify_pending(db, job)["classified"] == 1
        assert len(calls) == 2


def test_daily_budget_and_manual_override(sessions, monkeypatch):
    monkeypatch.setattr(settings, "daily_classification_limit", 1)
    with sessions() as db:
        add_app(db, 1, manual_override=True, category="其他")
        add_app(db, 2)
        add_app(db, 3)
        job = pipeline.enqueue(db, "classify")
        assert pipeline.classify_pending(db, job) == {
            "classified": 1,
            "remaining_daily_budget": 0,
        }
        assert pipeline.classify_pending(db, job)["classified"] == 0
        assert db.get(Application, 1).category == "其他"
        assert db.scalar(select(func.count()).select_from(Classification)) == 1


def test_hn_before_repository_can_be_linked_later(sessions):
    with sessions() as db:
        job = pipeline.enqueue(db, "sync")
        pipeline.ingest_event(
            db,
            {
                "type": "discussion",
                "data": {
                    "id": 44,
                    "title": "Show HN",
                    "url": "https://github.com/Maker/app-1",
                    "score": 3,
                    "comments": 2,
                    "repo_full_name": "maker/app-1",
                    "posted_at": "2026-10-01T00:00:00Z",
                },
            },
            job,
        )
        assert db.get(Discussion, 44).app_id is None
        add_app(db)
        assert pipeline.relink_discussions(db) == 1
        assert db.get(Discussion, 44).app_id == 1
        assert pipeline.relink_discussions(db) == 0
