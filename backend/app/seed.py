from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from .models import (
    Application,
    Snapshot,
    Discussion,
    Coverage,
    RawRecord,
    Classification,
)
from .config import settings
from .db import utcnow

NAMES = [
    "FlowNote",
    "PixelGarden",
    "HabitNest",
    "DataCanvas",
    "Readwise Mini",
    "FocusRoom",
    "MelodyLab",
    "TinyBudget",
    "StudyOrbit",
    "RecipeLeaf",
    "MoodAtlas",
    "PaperTrail",
    "ClipCraft",
    "SleepWell",
    "QueryGarden",
    "TaskBloom",
    "WordWander",
    "GamePocket",
    "ChartNest",
    "TravelSketch",
    "BookBridge",
    "MindMaple",
    "ColorMuse",
    "DailySprout",
]
CATEGORIES = [
    "生产力",
    "内容创作",
    "生活方式",
    "数据分析",
    "教育学习",
    "生产力",
    "游戏娱乐",
    "生活方式",
]
TOOLS = ["Claude Code", "Cursor", "Lovable", "Codex", "Bolt", "GitHub Copilot"]
LANGUAGES = ["TypeScript", "Python", "JavaScript", "Swift", "Go"]


def seed_demo(db):
    if settings.data_mode != "demo":
        raise ValueError("Demo seed is forbidden in live mode")
    now = utcnow()
    today = now.date()
    existing = set(db.scalars(select(Application.id)))
    count = 0
    for i in range(72):
        app_id = 900000 + i
        if app_id in existing:
            continue
        name = NAMES[i % 24] + (" " + str(i // 24 + 1) if i >= 24 else "")
        category = CATEGORIES[i % 8]
        tool = TOOLS[i % 6]
        created = now - timedelta(days=90 - i if i < 60 else i - 60 + 1)
        url = f"https://example.com/vibescope-demo/app-{i+1}"
        quote = f"This application was built with {tool} using AI-assisted development."
        app = Application(
            id=app_id,
            name=name,
            full_name=f'demo/{name.lower().replace(" ","-")}',
            description=f"{name} 是一个面向日常使用的{category}应用。",
            summary=f"把复杂的小事变简单：通过清晰的工作流帮助你完成{category}任务。此项目为演示样例。",
            url=url,
            homepage=None,
            language=LANGUAGES[i % 5],
            created_at=created,
            first_seen_at=max(created, now - timedelta(days=40 - i % 12)),
            last_observed_at=now,
            category=category if i % 17 else "未知",
            kind=(
                "application"
                if i < 66
                else ("developer_tool" if i < 69 else "resource")
            ),
            evidence_level="explicit" if i < 64 else ("weak" if i < 68 else "unknown"),
            tools=[tool] + (["Cursor"] if i % 7 == 0 and tool != "Cursor" else []),
            method="demo",
            model="synthetic-fixture",
            prompt_version="demo-v1",
            evidence=[{"quote": quote, "url": url}],
            classified_at=now,
            readme=quote,
            content_hash=f"demo-{i}",
        )
        db.add(app)
        db.flush()
        stars = 180 + i * 71
        for j in range(36):
            day = today - timedelta(days=35 - j)
            if day < created.date() or (i == 3 and j == 28):
                continue
            gain = (i % 9 + 1) * 3 + (j % 5) * 2
            if i % 11 == 0 and j > 27:
                gain = -4
            stars = max(0, stars + gain)
            db.add(
                Snapshot(
                    app_id=app_id,
                    snapshot_date=day,
                    stars=stars,
                    forks=max(1, stars // 12),
                    observed_at=datetime.combine(
                        day, datetime.min.time(), tzinfo=timezone.utc
                    ),
                )
            )
        app.stars = stars
        app.forks = max(1, stars // 12)
        db.add(
            Classification(
                app_id=app_id,
                category=app.category,
                kind=app.kind,
                evidence_level=app.evidence_level,
                tools=app.tools,
                evidence=app.evidence,
                method="demo",
                model="synthetic-fixture",
                prompt_version="demo-v1",
                classified_at=now,
                content_hash=app.content_hash,
            )
        )
        db.add(
            RawRecord(
                source="demo",
                source_id=str(app_id),
                payload={"demo": True, "name": name, "description": app.description},
                observed_at=now,
            )
        )
        if i % 3 == 0:
            db.add(
                Discussion(
                    id=800000 + i,
                    app_id=app_id,
                    title=f"Show HN: {name} — a small idea, shipped with AI (演示)",
                    url=url,
                    score=18 + i * 3,
                    comments=3 + i,
                    posted_at=now - timedelta(days=i % 7),
                    observed_at=now,
                )
            )
        count += 1
    if count:
        db.add(
            Coverage(
                source="demo",
                status="complete",
                detail={
                    "sample_count": 72,
                    "synthetic": True,
                    "history_days": 36,
                    "note": "独立演示数据，不代表真实市场。",
                },
                observed_at=now,
            )
        )
    db.commit()
    return count
