from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    **(
        {"connect_args": {"check_same_thread": False}}
        if settings.database_url.startswith("sqlite")
        else {}
    )
)
if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _sqlite_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session


def init_db():
    from . import models

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        identity = session.get(models.AppSetting, "data_mode")
        if identity and identity.value != settings.data_mode:
            raise RuntimeError(
                "Database belongs to another DATA_MODE; use a separate database/volume"
            )
        if not identity:
            session.add(models.AppSetting(key="data_mode", value=settings.data_mode))
            session.commit()
