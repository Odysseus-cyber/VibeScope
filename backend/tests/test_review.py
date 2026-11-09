from datetime import date, datetime, timedelta, timezone
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.config import settings
from app.main import app
from app.models import Application, Snapshot
from app.metrics import overview, daily_metrics, as_of
from app.reporting import create_report

DAY = date(2026, 11, 9)


@pytest.fixture
def review_env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    def dependency():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    monkeypatch.setattr(settings, "warehouse_enabled", False)
    monkeypatch.setattr(settings, "data_mode", "live")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_model", "")
    yield TestClient(app), sessions, engine
    app.dependency_overrides.clear()
    engine.dispose()


def add_app(db, app_id, **values):
    data = dict(
        id=app_id,
        name=f"App {app_id}",
        full_name=f"owner/repo{app_id}",
        url=f"https://github.com/owner/repo{app_id}",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        first_seen_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        kind="application",
        evidence_level="explicit",
        category="生产力",
        tools=["Cursor"],
        stars=999,
        forks=90,
    )
    data.update(values)
    record = Application(**data)
    db.add(record)
    db.flush()
    return record


def snap(db, app_id, offset, stars):
    db.add(
        Snapshot(
            app_id=app_id,
            snapshot_date=DAY + timedelta(days=offset),
            stars=stars,
            forks=stars // 10,
        )
    )


def test_daily_missing_samples_do_not_create_zero_or_partial_pool_growth(review_env):
    _, sessions, engine = review_env
    with sessions() as db:
        add_app(db, 1)
        add_app(db, 2)
        add_app(db, 3, kind="developer_tool")
        for app_id, offset, stars in [
            (1, -3, 80),
            (2, -3, 42),
            (1, -2, 90),
            (2, -2, 40),
            (1, -1, 95),
            (1, 0, 100),
            (2, 0, 42),
            (3, 0, 9000),
        ]:
            snap(db, app_id, offset, stars)
        db.commit()
        statements = []

        def observe(*args):
            statements.append(args[2])

        event.listen(engine, "before_cursor_execute", observe)
        try:
            rows = daily_metrics(db, DAY - timedelta(days=89), DAY, 2)
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        assert (
            len(statements) == 1
        )  # Date range length must not create a query per day.
        assert len(rows) == 90
        assert rows[-5] == {
            "date": DAY - timedelta(days=4),
            "stars": None,
            "apps": 0,
            "growth": None,
        }
        assert rows[-3]["stars"] == 130 and rows[-3]["growth"] == 8
        assert (
            rows[-2]["stars"] == 95
            and rows[-2]["apps"] == 1
            and rows[-2]["growth"] is None
        )
        assert rows[-1]["stars"] == 142 and rows[-1]["growth"] is None


def test_ready_warehouse_daily_uses_dws_and_fills_missing_dates():
    class Result:
        def mappings(self):
            return [{"snapshot_date": DAY, "stars": 42, "apps": 1, "growth": -3}]

    class Session:
        def execute(self, statement, params):
            assert "dws.dws_daily_metrics" in str(statement)
            assert params == {"start": DAY - timedelta(days=1), "end": DAY}
            return Result()

    assert daily_metrics(Session(), DAY - timedelta(days=1), DAY, 1, True) == [
        {"date": DAY - timedelta(days=1), "stars": None, "apps": 0, "growth": None},
        {"date": DAY, "stars": 42, "apps": 1, "growth": -3},
    ]


def test_metrics_use_asof_snapshots_for_counts_and_sorting(review_env):
    client, sessions, _ = review_env
    with sessions() as db:
        add_app(db, 1, stars=999)
        add_app(db, 2, stars=10)
        snap(db, 1, 0, 90)
        snap(db, 2, 0, 95)
        db.commit()
    listing = client.get("/api/v1/apps?sort=stars").json()["items"]
    assert [a["id"] for a in listing] == [2, 1]
    assert listing[0]["stars"] == 95 and listing[0]["forks"] == 9
    assert client.get("/api/v1/apps/1").json()["app"]["stars"] == 90
    assert client.get("/api/v1/overview").json()["kpis"]["stars"] == 185


def test_coverage_counts_observed_dates_and_detail_shows_missing_tail(review_env):
    client, sessions, _ = review_env
    with sessions() as db:
        add_app(db, 1)
        add_app(db, 2)
        snap(db, 1, -30, 10)
        snap(db, 1, -2, 20)
        snap(db, 2, 0, 50)
        db.commit()
    summary = client.get("/api/v1/overview?window=90").json()
    assert summary["kpis"]["coverage_days"] == 3
    detail = client.get("/api/v1/apps/1").json()["history"]
    assert detail[-1] == {
        "date": DAY.isoformat(),
        "stars": None,
        "forks": None,
        "growth": None,
    }
    assert detail[-2]["stars"] is None
    layers = client.get("/api/v1/quality").json()["layers"]
    assert layers[2]["name"] == "DWS · 每日汇总" and layers[2]["rows"] == 3
    assert layers[3]["name"] == "ADS · 应用指标" and layers[3]["rows"] == 2


def test_weekly_report_ranks_only_complete_subset_and_keeps_window_baseline(review_env):
    _, sessions, _ = review_env
    with sessions() as db:
        add_app(db, 1)
        add_app(
            db,
            2,
            created_at=datetime.combine(
                DAY - timedelta(days=6), datetime.min.time(), tzinfo=timezone.utc
            ),
        )
        snap(db, 1, -7, 100)
        snap(db, 1, 0, 90)
        snap(db, 2, 0, 500)
        db.commit()
        report = create_report(db)
        assert "趋势周报" in report.title and "1 / 2" in report.body
        assert report.facts["kpis"]["growth_7d"] is None
        assert report.facts["kpis"]["new_created"] == 1
        assert [a["id"] for a in report.facts["leaders"]] == [1]
        assert len(report.sources) == 1
        assert report.period_start == DAY - timedelta(days=6)
        assert (
            report.facts["report_context"]["growth_baseline_date"]
            == (DAY - timedelta(days=7)).isoformat()
        )
        assert "-10" in report.body


def test_cold_start_report_uses_current_stars_instead_of_null_growth_id_order(
    review_env,
):
    _, sessions, _ = review_env
    with sessions() as db:
        add_app(db, 1)
        add_app(db, 2)
        snap(db, 1, 0, 30)
        snap(db, 2, 0, 300)
        db.commit()
        report = create_report(db)
        assert "观察摘要" in report.title
        assert [a["id"] for a in report.facts["leaders"]] == [2, 1]
        assert report.facts["kpis"]["growth_7d_eligible"] == 0


@pytest.mark.parametrize(
    "observations",
    [
        [None, "bad", {"text": ["invalid"], "source_indices": [0]}],
        {"text": "invalid"},
        None,
    ],
)
def test_malformed_model_output_keeps_sql_report(review_env, monkeypatch, observations):
    _, sessions, _ = review_env
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(
        settings, "llm_base_url", "https://example.test/v1/chat/completions"
    )
    monkeypatch.setattr(settings, "llm_model", "test-model")

    def respond(url, **kwargs):
        assert url == "https://example.test/v1/chat/completions"
        content = json.dumps({"observations": observations})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.reporting.httpx.post", respond)
    with sessions() as db:
        add_app(db, 1)
        snap(db, 1, 0, 123)
        db.commit()
        report = create_report(db)
        assert report.method == "rules" and "123 Stars" in report.body
        assert "SQL 统计摘要" in report.body


def test_model_qualitative_observation_is_cited_and_versioned(review_env, monkeypatch):
    _, sessions, _ = review_env
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_base_url", "https://example.test/v1")
    monkeypatch.setattr(settings, "llm_model", "test-model")

    def respond(url, **kwargs):
        content = json.dumps(
            {
                "observations": [
                    {"text": "生产力应用聚焦日常工作流。", "source_indices": [0]},
                    {"text": "用户暴涨100%", "source_indices": [0]},
                ]
            }
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.reporting.httpx.post", respond)
    with sessions() as db:
        add_app(db, 1)
        snap(db, 1, 0, 123)
        db.commit()
        report = create_report(db)
        assert report.method == "llm" and "生产力应用聚焦日常工作流。" in report.body
        assert "用户暴涨" not in report.body
        assert report.facts["report_context"]["model"] == "test-model"
        assert report.facts["report_context"]["prompt_version"] == "report-v2"


def test_unknown_tool_distribution_drills_into_same_set(review_env):
    client, sessions, _ = review_env
    with sessions() as db:
        add_app(db, 1, tools=[])
        add_app(db, 2, tools=["未知"])
        add_app(db, 3, tools=["Cursor"])
        db.commit()
    distribution = client.get("/api/v1/overview").json()["tools"]
    unknown = next(row for row in distribution if row["name"] == "未知")
    listing = client.get("/api/v1/apps?tool=未知").json()
    assert unknown["count"] == listing["total"] == 2


def test_empty_database_asof_is_utc_and_partial_llm_config_is_disabled(
    review_env, monkeypatch
):
    client, sessions, _ = review_env
    monkeypatch.setattr(
        "app.metrics.utcnow", lambda: datetime(2026, 1, 2, 0, 30, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    with sessions() as db:
        assert as_of(db) == date(2026, 1, 2)
    assert client.get("/api/v1/meta").json()["llm_enabled"] is False
