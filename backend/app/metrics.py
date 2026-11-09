from datetime import timedelta
from sqlalchemy import select, func, text, and_, table, column, inspect
from sqlalchemy.orm import aliased
from .models import Application, Snapshot, AppSetting
from .config import settings
from .db import utcnow

CATEGORIES = [
    "生产力",
    "开发辅助",
    "内容创作",
    "生活方式",
    "教育学习",
    "游戏娱乐",
    "数据分析",
    "其他",
    "未知",
]
ELIGIBLE = and_(
    Application.kind == "application", Application.evidence_level == "explicit"
)


def as_of(db):
    return db.scalar(select(func.max(Snapshot.snapshot_date))) or utcnow().date()


def app_dict(app, growth=None):
    names = [
        "id",
        "name",
        "full_name",
        "description",
        "summary",
        "url",
        "homepage",
        "category",
        "tools",
        "language",
        "kind",
        "evidence_level",
        "stars",
        "forks",
        "created_at",
        "first_seen_at",
        "last_observed_at",
        "method",
        "evidence",
        "manual_override",
    ]
    result = {key: getattr(app, key) for key in names}
    result.update(growth_7d=None, growth_30d=None)
    if growth:
        result.update(growth)
    return result


def metric_app(row):
    app, week, month, stars, forks = row
    return app_dict(
        app, {"growth_7d": week, "growth_30d": month, "stars": stars, "forks": forks}
    )


def metrics_rows(db):
    if ads_ready(db):
        ads = table(
            "ads_app_metrics",
            column("app_id"),
            column("growth_7d"),
            column("growth_30d"),
            column("stars"),
            column("forks"),
            schema="ads",
        )
        return select(
            Application,
            ads.c.growth_7d,
            ads.c.growth_30d,
            func.coalesce(ads.c.stars, Application.stars).label("metric_stars"),
            func.coalesce(ads.c.forks, Application.forks).label("metric_forks"),
        ).outerjoin(ads, ads.c.app_id == Application.id)
    current, week, month = aliased(Snapshot), aliased(Snapshot), aliased(Snapshot)
    end = as_of(db)
    # Exact boundaries match the dbt ADS model; absence stays NULL, including decreases.
    return (
        select(
            Application,
            (current.stars - week.stars).label("growth_7d"),
            (current.stars - month.stars).label("growth_30d"),
            func.coalesce(current.stars, Application.stars).label("metric_stars"),
            func.coalesce(current.forks, Application.forks).label("metric_forks"),
        )
        .outerjoin(
            current,
            and_(current.app_id == Application.id, current.snapshot_date == end),
        )
        .outerjoin(
            week,
            and_(
                week.app_id == Application.id,
                week.snapshot_date == end - timedelta(days=7),
            ),
        )
        .outerjoin(
            month,
            and_(
                month.app_id == Application.id,
                month.snapshot_date == end - timedelta(days=30),
            ),
        )
    )


def list_apps(
    db,
    q="",
    category="",
    tool="",
    language="",
    kind="",
    evidence_level="",
    created_after=None,
    sort="growth_7d",
    page=1,
    page_size=12,
    eligible_only=True,
):
    query = metrics_rows(db)
    if eligible_only:
        query = query.where(ELIGIBLE)
    if q:
        query = query.where(
            func.lower(
                Application.name
                + " "
                + Application.description
                + " "
                + Application.summary
            ).contains(q.lower(), autoescape=True)
        )
    if category:
        query = query.where(Application.category == category)
    if language:
        query = query.where(Application.language == language)
    if kind:
        query = query.where(Application.kind == kind)
    if evidence_level:
        query = query.where(Application.evidence_level == evidence_level)
    if created_after:
        query = query.where(func.date(Application.created_at) >= created_after)
    if tool:
        # Match the displayed bucket after normalization, including empty tool arrays.
        if db.bind.dialect.name == "postgresql":
            membership = "EXISTS (SELECT 1 FROM json_array_elements_text(applications.tools) AS t(value) WHERE coalesce(nullif(trim(t.value),''),'未知') = :tool)"
        else:
            membership = "EXISTS (SELECT 1 FROM json_each(applications.tools) WHERE coalesce(nullif(trim(value),''),'未知') = :tool)"
        if tool == "未知":
            membership = (
                "(json_array_length(applications.tools)=0 OR " + membership + ")"
            )
        query = query.where(text(membership).bindparams(tool=tool))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order = (
        column("metric_stars").desc()
        if sort == "stars"
        else (
            Application.created_at.desc()
            if sort == "newest"
            else text("growth_7d DESC NULLS LAST")
        )
    )
    rows = db.execute(
        query.order_by(order, Application.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [metric_app(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def metadata(db):
    latest = db.scalar(select(func.max(Application.last_observed_at)))
    tools = set()
    for value in db.scalars(select(Application.tools)):
        tools.update(value or ["未知"])
    return {
        "mode": settings.data_mode,
        "as_of": as_of(db),
        "last_updated": latest,
        "llm_enabled": bool(
            settings.llm_base_url and settings.llm_api_key and settings.llm_model
        ),
        "categories": CATEGORIES,
        "tools": sorted(tools),
        "languages": sorted(
            x for x in db.scalars(select(Application.language).distinct()) if x
        ),
    }


def daily_metrics(db, start, end, eligible_count, warehouse_ready=False):
    """One SQL range query; fill absent dates without inventing observations."""
    if warehouse_ready:
        rows = db.execute(
            text(
                "SELECT snapshot_date, stars, apps, growth FROM dws.dws_daily_metrics "
                "WHERE snapshot_date BETWEEN :start AND :end ORDER BY snapshot_date"
            ),
            {"start": start, "end": end},
        ).mappings()
        observed = {row["snapshot_date"]: dict(row) for row in rows}
    else:
        previous = aliased(Snapshot)
        previous_date = (
            Snapshot.snapshot_date - 1
            if db.bind.dialect.name == "postgresql"
            else func.date(Snapshot.snapshot_date, "-1 day")
        )
        query = (
            select(
                Snapshot.snapshot_date,
                func.sum(Snapshot.stars).label("stars"),
                func.count(Snapshot.id).label("apps"),
                func.count(previous.id).label("paired"),
                func.sum(Snapshot.stars - previous.stars).label("delta"),
            )
            .join(Application, Application.id == Snapshot.app_id)
            .outerjoin(
                previous,
                and_(
                    previous.app_id == Snapshot.app_id,
                    previous.snapshot_date == previous_date,
                ),
            )
            .where(
                ELIGIBLE, Snapshot.snapshot_date >= start, Snapshot.snapshot_date <= end
            )
            .group_by(Snapshot.snapshot_date)
        )
        observed = {}
        for row in db.execute(query):
            complete = (
                eligible_count > 0
                and row.apps == eligible_count
                and row.paired == eligible_count
            )
            observed[row.snapshot_date] = {
                "stars": row.stars,
                "apps": row.apps,
                "growth": row.delta if complete else None,
            }
    daily = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        row = observed.get(day)
        daily.append(
            {
                "date": day,
                "stars": row["stars"] if row else None,
                "apps": row["apps"] if row else 0,
                "growth": row["growth"] if row else None,
            }
        )
    return daily


def overview(db, window=30):
    end = as_of(db)
    start = end - timedelta(days=window - 1)
    eligible_count = db.scalar(
        select(func.count()).select_from(Application).where(ELIGIBLE)
    )
    tracked = db.scalar(select(func.count()).select_from(Application))
    query = metrics_rows(db).where(ELIGIBLE).subquery()
    growth_count, growth_sum, stars = db.execute(
        select(
            func.count(query.c.growth_7d),
            func.sum(query.c.growth_7d),
            func.coalesce(func.sum(query.c.metric_stars), 0),
        )
    ).one()
    # Count observed dates, not elapsed calendar days across an unobserved gap.
    coverage_days = db.scalar(
        select(func.count(func.distinct(Snapshot.snapshot_date)))
        .join(Application, Application.id == Snapshot.app_id)
        .where(ELIGIBLE)
    )
    kpis = {
        "tracked": tracked,
        "eligible": eligible_count,
        "classified": db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.classified_at.is_not(None))
        ),
        "new_created": db.scalar(
            select(func.count())
            .select_from(Application)
            .where(
                ELIGIBLE,
                func.date(Application.created_at) >= start,
                func.date(Application.created_at) <= end,
            )
        ),
        "new_discovered": db.scalar(
            select(func.count())
            .select_from(Application)
            .where(
                ELIGIBLE,
                func.date(Application.first_seen_at) >= start,
                func.date(Application.first_seen_at) <= end,
            )
        ),
        "stars": stars,
        "growth_7d": (
            growth_sum if eligible_count and growth_count == eligible_count else None
        ),
        "growth_7d_eligible": growth_count,
        "coverage_days": coverage_days,
    }
    ready = ads_ready(db)
    if ready:
        categories = [
            {
                "name": r["category"],
                "count": r["count"],
                "percentage": float(r["percentage"]),
            }
            for r in db.execute(
                text(
                    "SELECT * FROM ads.ads_category_metrics ORDER BY count DESC, category"
                )
            ).mappings()
        ]
        tools = [
            {
                "name": r["tool"],
                "count": r["count"],
                "percentage": float(r["percentage"]),
            }
            for r in db.execute(
                text("SELECT * FROM ads.ads_tool_metrics ORDER BY count DESC, tool")
            ).mappings()
        ]
    else:
        category = func.coalesce(func.nullif(Application.category, ""), "未知")
        categories = [
            {
                "name": name,
                "count": count,
                "percentage": (
                    round(100 * count / eligible_count, 2) if eligible_count else 0
                ),
            }
            for name, count in db.execute(
                select(category, func.count())
                .where(ELIGIBLE)
                .group_by(category)
                .order_by(func.count().desc(), category)
            )
        ]
        if db.bind.dialect.name == "postgresql":
            tool_sql = "SELECT coalesce(nullif(trim(t.value),''),'未知') AS name, count(DISTINCT a.id) AS count FROM applications a CROSS JOIN LATERAL json_array_elements_text(CASE WHEN json_array_length(a.tools)=0 THEN '[\"未知\"]'::json ELSE a.tools END) t(value) WHERE a.kind='application' AND a.evidence_level='explicit' GROUP BY 1 ORDER BY count DESC, name"
        else:
            tool_sql = "SELECT coalesce(nullif(trim(t.value),''),'未知') AS name, count(DISTINCT a.id) AS count FROM applications a,json_each(CASE WHEN json_array_length(a.tools)=0 THEN '[\"未知\"]' ELSE a.tools END) t WHERE a.kind='application' AND a.evidence_level='explicit' GROUP BY 1 ORDER BY count DESC, name"
        tools = [
            {
                "name": r.name,
                "count": r.count,
                "percentage": (
                    round(100 * r.count / eligible_count, 2) if eligible_count else 0
                ),
            }
            for r in db.execute(text(tool_sql))
        ]
    return {
        "meta": metadata(db),
        "kpis": kpis,
        "categories": categories,
        "tools": tools,
        "daily": daily_metrics(db, start, end, eligible_count, ready),
        "leaders": list_apps(db, page_size=6)["items"],
    }


def ads_ready(db):
    if not settings.warehouse_enabled or db.bind.dialect.name != "postgresql":
        return False
    dirty = db.get(AppSetting, "warehouse_dirty")
    if dirty and dirty.value:
        return False
    inspector = inspect(db.bind)
    for schema, name in [
        ("ads", "ads_app_metrics"),
        ("ads", "ads_category_metrics"),
        ("ads", "ads_tool_metrics"),
        ("dws", "dws_daily_metrics"),
    ]:
        if not inspector.has_table(name, schema=schema):
            return False
    return db.scalar(text("SELECT max(as_of) FROM ads.ads_app_metrics")) == as_of(db)
