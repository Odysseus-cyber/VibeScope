from datetime import date, datetime
from sqlalchemy import (
    String,
    Text,
    Integer,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, utcnow


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(400), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text)
    homepage: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    category: Mapped[str] = mapped_column(String(100), default="未知")
    kind: Mapped[str] = mapped_column(String(30), default="application")
    evidence_level: Mapped[str] = mapped_column(String(30), default="unknown")
    tools: Mapped[list] = mapped_column(JSON, default=list)
    method: Mapped[str] = mapped_column(String(30), default="rules")
    model: Mapped[str] = mapped_column(String(100), default="")
    prompt_version: Mapped[str] = mapped_column(String(100), default="")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    classified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    readme: Mapped[str] = mapped_column(Text, default="")
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        UniqueConstraint("app_id", "snapshot_date", name="uq_snapshot_app_date"),
        Index("ix_snapshot_date", "snapshot_date"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    snapshot_date: Mapped[date] = mapped_column(Date)
    stars: Mapped[int] = mapped_column(Integer)
    forks: Mapped[int] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class RawRecord(Base):
    __tablename__ = "raw_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Discussion(Base):
    __tablename__ = "discussions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    app_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Classification(Base):
    __tablename__ = "classifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    category: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30))
    evidence_level: Mapped[str] = mapped_column(String(30))
    tools: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    method: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100), default="")
    prompt_version: Mapped[str] = mapped_column(String(100), default="")
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    content_hash: Mapped[str] = mapped_column(String(64), default="")


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    body: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    facts: Mapped[dict] = mapped_column(JSON)
    sources: Mapped[list] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(10))


class Coverage(Base):
    __tablename__ = "coverage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(30))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    status: Mapped[str] = mapped_column(String(30))
    detail: Mapped[dict] = mapped_column(JSON)
    run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict | str] = mapped_column(JSON)
