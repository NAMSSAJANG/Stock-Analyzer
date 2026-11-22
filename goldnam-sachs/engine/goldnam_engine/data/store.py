"""Portable SQL storage. Postgres in deployment; explicit SQLite for local tests only."""

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.pool import StaticPool

from .universe import serialize

metadata = MetaData()
records = Table(
    "goldnam_records",
    metadata,
    Column("kind", String(40), primary_key=True),
    Column("key", String(400), primary_key=True),
    Column("payload", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


class Store:
    def __init__(self, url: str | None = None) -> None:
        address = url or os.getenv("DATABASE_URL", "")
        if not address:
            raise ValueError("DATABASE_URL 미설정")
        if address.startswith("postgres://"):
            address = "postgresql+psycopg://" + address.removeprefix("postgres://")
        elif address.startswith("postgresql://"):
            address = "postgresql+psycopg://" + address.removeprefix("postgresql://")
        if os.getenv("RENDER") and not address.startswith("postgresql+"):
            raise ValueError("배포 환경은 Postgres가 필요합니다")
        options: dict[str, Any] = {"pool_pre_ping": True}
        if address == "sqlite://":
            options.update(poolclass=StaticPool, connect_args={"check_same_thread": False})
        self.engine = create_engine(address, **options)
        if self.engine.dialect.name not in {"postgresql", "sqlite"}:
            raise ValueError("지원하지 않는 저장소")
        metadata.create_all(self.engine)

    def put_many(self, kind: str, items: list[tuple[str, dict[str, Any]]]) -> None:
        insert = pg_insert if self.engine.dialect.name == "postgresql" else sqlite_insert
        with self.engine.begin() as connection:
            for key, payload in items:
                statement = insert(records).values(
                    kind=kind,
                    key=key,
                    payload=serialize(payload),
                    updated_at=datetime.now(timezone.utc),
                )
                connection.execute(
                    statement.on_conflict_do_update(
                        index_elements=[records.c.kind, records.c.key],
                        set_={
                            "payload": statement.excluded.payload,
                            "updated_at": statement.excluded.updated_at,
                        },
                    )
                )

    def put(self, kind: str, key: str, payload: dict[str, Any]) -> None:
        self.put_many(kind, [(key, payload)])

    def get(self, kind: str, key: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(records.c.payload).where(records.c.kind == kind, records.c.key == key)
            ).first()
        return dict(row[0]) if row else None

    def list(self, kind: str, prefix: str = "", limit: int = 10000) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(records.c.key, records.c.payload)
                .where(records.c.kind == kind, records.c.key.startswith(prefix, autoescape=True))
                .order_by(records.c.key.desc())
                .limit(limit)
            ).all()
        return [{"id": str(row[0]), **dict(row[1])} for row in rows]

    def remove(self, kind: str, key: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(delete(records).where(records.c.kind == kind, records.c.key == key))
