from datetime import datetime, date, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.models import Application, Snapshot, Job
from app.main import app
from app.config import settings
from app.seed import seed_demo
from app import pipeline


@pytest.fixture
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    def dependency():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    monkeypatch.setattr(pipeline, "SessionLocal", sessions)
    monkeypatch.setattr(settings, "data_mode", "demo")
    monkeypatch.setattr(settings, "warehouse_enabled", False)
    monkeypatch.setattr(settings, "llm_api_key", "")
    yield TestClient(app), sessions
    app.dependency_overrides.clear()
    engine.dispose()


def make_app(db, app_id=1, **changes):
    now = datetime.now(timezone.utc)
    data = dict(
        id=app_id,
        name="TestApp",
        full_name=f"owner/app{app_id}",
        url="https://github.com/owner/app",
        description="A useful app",
        summary="应用",
        created_at=now - timedelta(days=50),
        category="生产力",
        kind="application",
        evidence_level="explicit",
        tools=["Cursor"],
        evidence=[
            {"quote": "Built with Cursor", "url": "https://github.com/owner/app"}
        ],
        stars=90,
        forks=5,
    )
    data.update(changes)
    a = Application(**data)
    db.add(a)
    db.commit()
    return a


def test_exact_boundary_missing_and_negative_growth(env):
    client, sessions = env
    today = date.today()
    with sessions() as db:
        make_app(db)
        db.add_all(
            [
                Snapshot(app_id=1, snapshot_date=today, stars=90, forks=5),
                Snapshot(
                    app_id=1,
                    snapshot_date=today - timedelta(days=7),
                    stars=100,
                    forks=5,
                ),
                Snapshot(
                    app_id=1,
                    snapshot_date=today - timedelta(days=29),
                    stars=50,
                    forks=1,
                ),
            ]
        )
        db.commit()
    result = client.get("/api/v1/apps/1").json()["app"]
    assert result["growth_7d"] == -10 and result["growth_30d"] is None
    r = client.get("/api/v1/overview?window=7")
    assert r.status_code == 200 and len(r.json()["daily"]) == 7
    assert client.get("/api/v1/overview?window=8").status_code == 422


def test_demo_idempotence_and_denominators(env):
    client, sessions = env
    with sessions() as db:
        assert seed_demo(db) == 72
        snapshots = db.scalar(select(func.count()).select_from(Snapshot))
        assert seed_demo(db) == 0
        assert db.scalar(select(func.count()).select_from(Snapshot)) == snapshots
    assert (
        client.get("/api/v1/apps?eligible_only=false&page_size=100").json()["total"]
        == 72
    )
    assert client.get("/api/v1/apps").json()["total"] == 64
    data = client.get("/api/v1/overview?window=30").json()
    assert sum(x["count"] for x in data["categories"]) == 64
    assert sum(x["percentage"] for x in data["tools"]) > 100
    assert data["kpis"]["coverage_days"] >= 30 and data["kpis"]["growth_7d"] is None
    assert client.get("/api/v1/apps?tool=Cursor").json()["total"] > 0
    assert client.get("/api/v1/apps?tool=Cur").json()["total"] == 0


def test_report_job_roundtrip(env):
    client, sessions = env
    with sessions() as db:
        seed_demo(db)
    r = client.post("/api/v1/reports", json={})
    assert r.status_code == 202
    job = r.json()
    assert client.post("/api/v1/reports").json()["id"] == job["id"]
    assert pipeline.process_next()
    done = client.get("/api/v1/jobs/" + job["id"]).json()
    assert done["status"] == "succeeded", done
    report = client.get("/api/v1/reports").json()["items"][0]
    assert report["mode"] == "demo" and "演示数据" in report["body"]
    assert str(report["facts"]["kpis"]["eligible"]) in report["body"]
    assert all(s["url"] in report["body"] for s in report["sources"])
    assert client.post("/api/v1/jobs/" + job["id"] + "/retry").status_code == 202


def test_manual_override_survives_reclassification(env):
    client, sessions = env
    with sessions() as db:
        make_app(db)
    r = client.patch(
        "/api/v1/apps/1/classification",
        json={
            "category": "其他",
            "kind": "resource",
            "evidence_level": "weak",
            "tools": ["Cursor", "Cursor"],
            "summary": "资源集合",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["manual_override"] and r.json()["tools"] == ["Cursor"]
    assert client.get("/api/v1/apps").json()["total"] == 0
    with sessions() as db:
        job = Job(id="manual-test", kind="classify", status="running")
        db.add(job)
        db.commit()
        assert pipeline.classify_pending(db, job)["classified"] == 0
        assert db.get(Application, 1).summary == "资源集合"


def test_export_and_input_validation(env):
    client, sessions = env
    with sessions() as db:
        make_app(db, name='=HYPERLINK("malicious")')
    response = client.get("/api/v1/apps/export.csv")
    assert response.status_code == 200 and "'=HYPERLINK" in response.text
    assert client.get("/api/v1/apps?page=0").status_code == 422
    assert client.get("/api/v1/apps/999999").status_code == 404
    assert client.post("/api/v1/jobs", json={"kind": "shell"}).status_code == 422


def test_live_seed_forbidden_and_cold_start(env, monkeypatch):
    client, sessions = env
    monkeypatch.setattr(settings, "data_mode", "live")
    with sessions() as db:
        with pytest.raises(ValueError):
            seed_demo(db)
        from app.reporting import create_report

        report = create_report(db)
        assert "观察摘要" in report.title and "历史快照不足" in report.body
    assert client.get("/api/v1/overview?window=90").json()["kpis"]["tracked"] == 0


def test_ingestion_retry_and_repository_rename(env):
    client, sessions = env
    with sessions() as db:
        a = make_app(db)
        a.manual_override = True
        a.category = "生活方式"
        db.commit()
        job = Job(id="ingest", kind="github", status="running")
        db.add(job)
        db.commit()
        event = {
            "type": "repository",
            "data": {
                "id": 1,
                "name": "Renamed",
                "full_name": "new-owner/new-name",
                "url": "https://github.com/new-owner/new-name",
                "stars": 120,
                "forks": 8,
                "readme": "Updated",
            },
        }
        pipeline.ingest_event(db, event, job)
        pipeline.ingest_event(db, event, job)
        assert db.scalar(select(func.count()).select_from(Application)) == 1
        assert db.scalar(select(func.count()).select_from(Snapshot)) == 1
        assert db.get(Application, 1).category == "生活方式"
        assert db.get(Application, 1).full_name == "new-owner/new-name"


def test_failure_is_retryable(env, monkeypatch):
    client, sessions = env

    def fail(db):
        raise RuntimeError("test unavailable")

    monkeypatch.setattr(pipeline, "run_warehouse", fail)
    response = client.post("/api/v1/jobs", json={"kind": "warehouse"})
    pipeline.process_next()
    done = client.get("/api/v1/jobs/" + response.json()["id"]).json()
    assert done["status"] == "failed" and "unavailable" in done["error"]
    assert client.post("/api/v1/jobs/" + done["id"] + "/retry").status_code == 202
