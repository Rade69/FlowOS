"""SQLAlchemy engine i session factory.

Konfiguriše SQLite sa WAL režimom, uključenim stranim ključevima,
i kratkim transakcijama. Backend je jedini writer — svi upisi
idu kroz ovaj engine.
"""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_data_directory() -> Path:
    """Vraća putanju do FlowOS data direktorijuma."""
    base = Path.home() / "AppData" / "Local" / "FlowOS" / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def create_sqlite_engine(db_path: str | Path | None = None) -> Engine:
    """Kreira SQLAlchemy engine za SQLite sa WAL režimom.

    Args:
        db_path: Putanja do .db fajla. Ako nije zadato,
                 koristi %LOCALAPPDATA%/FlowOS/data/flowos.db

    Returns:
        SQLAlchemy Engine konfigurisan za SQLite/WAL.
    """
    if db_path is None:
        db_path = get_data_directory() / "flowos.db"

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
        # PoolSize=1 jer je SQLite single-writer
        pool_size=1,
        max_overflow=0,
    )

    # WAL režim + strani ključevi pri svakoj konekciji
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Kreira session factory za zadati engine.

    Args:
        engine: SQLAlchemy Engine

    Returns:
        sessionmaker konfigurisan za kratke transakcije.
    """
    return sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)
