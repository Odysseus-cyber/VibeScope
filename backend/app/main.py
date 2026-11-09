import csv, io
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db, init_db, utcnow
from .models import (
    Application,
    Snapshot,
    Discussion,
    Classification,
    Job,
    Report,
    Coverage,
    RawRecord,
)
from .metrics import (
    metadata,
    overview,
    list_apps,
    metrics_rows,
    app_dict,
    CATEGORIES,
    as_of,
    metric_app,
    ads_ready,
    ELIGIBLE,
)
from .pipeline import enqueue, KINDS, mark_dirty


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(
    title="VibeScope API",
    description="AI 辅助开发应用趋势观察站 · UTC 指标 · 可追溯数据",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)
P = "/api/v1"


@app.get(P + "/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "mode": settings.data_mode}


@app.get(P + "/meta")
def get_meta(db: Session = Depends(get_db)):
    return metadata(db)


@app.get(P + "/overview")
@app.get(P + "/trends")
def get_overview(window: int = Query(30, ge=7, le=90), db: Session = Depends(get_db)):
    if window not in (7, 30, 90):
        raise HTTPException(422, "window 必须为 7、30 或 90")
    return overview(db, window)


def filters(
    q: str = "",
    category: str = "",
    tool: str = "",
    language: str = "",
    kind: str = "",
    evidence_level: str = "",
    created_after: date | None = None,
    sort: Literal["growth_7d", "stars", "newest"] = "growth_7d",
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=1000),
    eligible_only: bool = True,
):
    return dict(
        q=q,
        category=category,
        tool=tool,
        language=language,
        kind=kind,
        evidence_level=evidence_level,
        created_after=created_after,
        sort=sort,
        page=page,
        page_size=page_size,
        eligible_only=eligible_only,
    )


@app.get(P + "/apps")
def get_apps(params: dict = Depends(filters), db: Session = Depends(get_db)):
    result = list_apps(db, **params)
    result["meta"] = metadata(db)
    return result


@app.get(P + "/apps/export.csv")
def export_apps(params: dict = Depends(filters), db: Session = Depends(get_db)):
    params.update(page=1, page_size=10000)
    stream = io.StringIO()
    writer = csv.writer(stream)
    columns = [
        "name",
        "url",
        "category",
        "tools",
        "language",
        "stars",
        "forks",
        "growth_7d",
        "growth_30d",
        "created_at",
        "first_seen_at",
        "evidence_level",
    ]
    writer.writerow(["data_mode"] + columns)
    for item in list_apps(db, **params)["items"]:
        row = []
        for key in columns:
            value = item[key]
            if isinstance(value, list):
                value = "; ".join(value)
            value = "" if value is None else str(value)
            if value.startswith(("=", "+", "-", "@", "\t", "\r")) and not isinstance(
                item[key], (int, float)
            ):
                value = "'" + value
            row.append(value)
        writer.writerow([settings.data_mode] + row)
    return Response(
        "\ufeff" + stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vibescope-apps.csv"'},
    )


@app.get(P + "/apps/{app_id}")
def get_app(app_id: int, db: Session = Depends(get_db)):
    row = db.execute(metrics_rows(db).where(Application.id == app_id)).first()
    if not row:
        raise HTTPException(404, "应用不存在")
    a = row[0]
    snapshots = {
        s.snapshot_date: s
        for s in db.scalars(
            select(Snapshot)
            .where(Snapshot.app_id == app_id)
            .order_by(Snapshot.snapshot_date)
        )
    }
    history = []
    if snapshots:
        start = min(snapshots)
        end = as_of(db)
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            current = snapshots.get(day)
            previous = snapshots.get(day - timedelta(days=1))
            history.append(
                {
                    "date": day,
                    "stars": current.stars if current else None,
                    "forks": current.forks if current else None,
                    "growth": (
                        current.stars - previous.stars if current and previous else None
                    ),
                }
            )
    return {
        "app": metric_app(row),
        "history": history,
        "discussions": list(
            db.scalars(
                select(Discussion)
                .where(Discussion.app_id == app_id)
                .order_by(Discussion.posted_at.desc())
            )
        ),
        "classification": {
            k: getattr(a, k)
            for k in [
                "method",
                "model",
                "prompt_version",
                "classified_at",
                "manual_override",
                "evidence",
            ]
        },
    }


class Evidence(BaseModel):
    quote: str = Field(min_length=1, max_length=3000)
    url: str = Field(max_length=2000)

    @field_validator("url")
    @classmethod
    def http_url(cls, v):
        if not v.startswith(("https://", "http://")):
            raise ValueError("来源必须是 HTTP(S) 链接")
        return v


class Correction(BaseModel):
    category: str
    kind: Literal["application", "developer_tool", "resource"]
    evidence_level: Literal["explicit", "weak", "unknown"]
    tools: list[str] = Field(default_factory=list, max_length=20)
    summary: str = Field(default="", max_length=3000)
    evidence: list[Evidence] | None = None

    @field_validator("category")
    @classmethod
    def valid_category(cls, v):
        if v not in CATEGORIES:
            raise ValueError("未知分类")
        return v


@app.patch(P + "/apps/{app_id}/classification")
def correct_app(app_id: int, body: Correction, db: Session = Depends(get_db)):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(404, "应用不存在")
    values = body.model_dump(exclude_none=True)
    if body.evidence_level == "explicit" and not values.get("evidence", a.evidence):
        raise HTTPException(422, "明确声明需要来源证据")
    values["tools"] = list(
        dict.fromkeys(x.strip() for x in values["tools"] if x.strip())
    )
    for key, value in values.items():
        setattr(a, key, value)
    a.manual_override = True
    a.method = "manual"
    a.model = "human"
    a.prompt_version = "manual-v1"
    a.classified_at = utcnow()
    db.add(
        Classification(
            app_id=a.id,
            category=a.category,
            kind=a.kind,
            evidence_level=a.evidence_level,
            tools=a.tools,
            evidence=a.evidence,
            method="manual",
            model="human",
            prompt_version="manual-v1",
            content_hash=a.content_hash,
        )
    )
    mark_dirty(db)
    db.commit()
    if settings.warehouse_enabled:
        enqueue(db, "warehouse")
    return get_app(app_id, db)["app"]


class JobRequest(BaseModel):
    kind: Literal["sync", "github", "hn", "classify", "warehouse", "report"] = "sync"


@app.get(P + "/jobs")
def get_jobs(db: Session = Depends(get_db)):
    return {
        "items": list(
            db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100))
        )
    }


@app.get(P + "/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return job


@app.post(P + "/jobs", status_code=202)
def post_job(body: JobRequest, db: Session = Depends(get_db)):
    return enqueue(db, body.kind)


@app.post(P + "/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    if job.status in ("running", "queued"):
        raise HTTPException(409, "任务尚未结束")
    return enqueue(db, job.kind)


@app.get(P + "/reports")
def get_reports(db: Session = Depends(get_db)):
    return {
        "items": list(
            db.scalars(select(Report).order_by(Report.created_at.desc()).limit(50))
        )
    }


@app.get(P + "/reports/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "报告不存在")
    return report


@app.post(P + "/reports", status_code=202)
def post_report(db: Session = Depends(get_db)):
    return enqueue(db, "report")


@app.get(P + "/quality")
def quality(db: Session = Depends(get_db)):
    count = lambda model: db.scalar(select(func.count()).select_from(model))
    coverage = list(
        db.scalars(select(Coverage).order_by(Coverage.observed_at.desc()).limit(20))
    )
    total = count(Application)
    unknown = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.evidence_level != "explicit")
    )
    latest = db.scalar(select(func.max(Application.last_observed_at)))
    stale = (
        not latest
        or (utcnow().replace(tzinfo=None) - latest.replace(tzinfo=None)).total_seconds()
        > 48 * 3600
    )
    failures = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.status == "failed", Job.created_at >= utcnow() - timedelta(days=7))
    )
    ranked = select(
        Coverage.id,
        func.row_number()
        .over(
            partition_by=Coverage.source,
            order_by=(Coverage.observed_at.desc(), Coverage.id.desc()),
        )
        .label("rank"),
    ).subquery()
    latest_sources = list(
        db.scalars(
            select(Coverage)
            .join(ranked, Coverage.id == ranked.c.id)
            .where(ranked.c.rank == 1)
        )
    )
    partial = sum(c.status != "complete" for c in latest_sources)
    duplicate = db.scalar(
        select(func.count()).select_from(
            select(Snapshot.app_id, Snapshot.snapshot_date)
            .group_by(Snapshot.app_id, Snapshot.snapshot_date)
            .having(func.count() > 1)
            .subquery()
        )
    )
    checks = [
        {
            "name": "快照唯一性",
            "status": "pass" if not duplicate else "fail",
            "value": duplicate,
            "detail": "同一项目、同一 UTC 日期仅保留一条快照",
        },
        {
            "name": "数据新鲜度",
            "status": "warn" if stale else "pass",
            "value": latest,
            "detail": "最近一次项目观测应在四十八小时内",
        },
        {
            "name": "证据待核验",
            "status": "warn" if unknown else "pass",
            "value": unknown,
            "detail": f"分母为全部 {total} 个候选项目；弱线索与未知不进入默认榜单",
        },
        {
            "name": "采集覆盖",
            "status": "warn" if partial or not coverage else "pass",
            "value": partial,
            "detail": "每个数据源最近一次运行的截断、失败与窗口信息",
        },
        {
            "name": "近七日失败任务",
            "status": "warn" if failures else "pass",
            "value": failures,
            "detail": "可查看错误详情并重新执行",
        },
    ]
    if ads_ready(db):
        from sqlalchemy import text

        dwd_rows = db.scalar(text("SELECT count(*) FROM dwd.dwd_applications"))
        dws_rows = db.scalar(text("SELECT count(*) FROM dws.dws_daily_metrics"))
        ads_rows = db.scalar(text("SELECT count(*) FROM ads.ads_app_metrics"))
    else:
        dwd_rows = total
        dws_rows = db.scalar(
            select(func.count(func.distinct(Snapshot.snapshot_date)))
            .join(Application, Application.id == Snapshot.app_id)
            .where(ELIGIBLE)
        )
        ads_rows = total
    return {
        "meta": metadata(db),
        "checks": checks,
        "layers": [
            {"name": "ODS · 原始响应", "rows": count(RawRecord)},
            {"name": "DWD · 应用明细", "rows": dwd_rows},
            {"name": "DWS · 每日汇总", "rows": dws_rows},
            {"name": "ADS · 应用指标", "rows": ads_rows},
        ],
        "coverage": coverage,
    }
