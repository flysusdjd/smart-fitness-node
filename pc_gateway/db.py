from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from . import config


Base = declarative_base()


class DatabaseManager:
    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    @property
    def enabled(self) -> bool:
        return config.MYSQL_ENABLED

    def _ensure_engine(self) -> Engine:
        if not self.enabled:
            raise RuntimeError("MySQL backend is disabled. Set MYSQL_ENABLED=true to enable it.")

        if self._engine is None:
            self._engine = create_engine(
                config.DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=config.DATABASE_ECHO,
                future=True,
            )
            self._session_factory = sessionmaker(
                bind=self._engine,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False,
                future=True,
            )
        return self._engine

    def _ensure_session_factory(self) -> sessionmaker[Session]:
        self._ensure_engine()
        if self._session_factory is None:
            raise RuntimeError("Database session factory is not initialized.")
        return self._session_factory

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self._ensure_session_factory()()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_all(self) -> None:
        # Import here so model metadata is registered before create_all runs.
        from . import db_models  # noqa: F401

        engine = self._ensure_engine()
        Base.metadata.create_all(engine)

    def health(self) -> dict[str, object]:
        if not self.enabled:
            return {
                "enabled": False,
                "connected": False,
                "databaseUrl": config.DATABASE_URL,
                "message": "MySQL backend is disabled.",
            }

        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
            return {
                "enabled": True,
                "connected": True,
                "databaseUrl": config.DATABASE_URL,
                "message": "MySQL connection is healthy.",
            }
        except Exception as exc:
            return {
                "enabled": True,
                "connected": False,
                "databaseUrl": config.DATABASE_URL,
                "message": str(exc),
            }


db_manager = DatabaseManager()
