"""Database connection management for Debrief (SQLite via SQLModel)."""

from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import URL, Engine
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  (importing registers the tables on SQLModel.metadata)

# backend/debrief.db, resolved from this file's location so it is the same
# no matter which folder the server is started from.
DEFAULT_DATABASE_PATH: Path = Path(__file__).resolve().parent.parent / "debrief.db"

# Name of the execution option used to ask for a particular kind of BEGIN.
SQLITE_BEGIN_MODE_OPTION = "sqlite_begin_mode"


class SqliteBeginMode(StrEnum):
    """How SQLite starts a transaction."""

    DEFERRED = "DEFERRED"    # no lock until the first read or write (the default)
    IMMEDIATE = "IMMEDIATE"  # take the write lock right away


class DatabaseManager:
    """Owns the SQLite engine and hands out one database session per request."""

    def __init__(
        self,
        database_path: Path | str = DEFAULT_DATABASE_PATH,
        *,
        busy_timeout_seconds: float = 5.0,
        echo: bool = False,
    ) -> None:
        url = URL.create(drivername="sqlite", database=str(database_path))
        self._engine: Engine = create_engine(
            url,
            echo=echo,
            connect_args={
                # FastAPI runs request code in a thread pool, so a connection may
                # be used from a different thread than the one that created it.
                "check_same_thread": False,
                # How long a request waits for another request's write lock.
                "timeout": busy_timeout_seconds,
            },
        )
        self._configure_sqlite(self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_tables(self) -> None:
        """Create every table that does not exist yet."""
        SQLModel.metadata.create_all(self._engine)

    def get_session(self) -> Iterator[Session]:
        """Yield one session for the duration of a request, then close it.

        Services commit explicitly. If a request fails before committing, closing
        the session rolls the open transaction back.

        ``expire_on_commit=False`` keeps loaded objects readable after a commit,
        so building a response never triggers a hidden extra query.
        """
        with Session(self._engine, expire_on_commit=False) as session:
            yield session

    def dispose(self) -> None:
        """Close all pooled connections (used on shutdown and in tests)."""
        self._engine.dispose()

    @staticmethod
    def _configure_sqlite(engine: Engine) -> None:
        """Apply the SQLite settings Debrief depends on."""

        @event.listens_for(engine, "connect")
        def on_connect(dbapi_connection, _connection_record) -> None:
            # Stop the sqlite3 driver from deciding when a transaction begins;
            # we emit BEGIN ourselves in on_begin below.
            dbapi_connection.isolation_level = None
            # SQLite ignores foreign keys unless this is switched on per connection.
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        @event.listens_for(engine, "begin")
        def on_begin(connection) -> None:
            # Ordinary transactions begin DEFERRED. A transaction that was
            # requested through begin_write_transaction() begins IMMEDIATE.
            requested = connection.get_execution_options().get(
                SQLITE_BEGIN_MODE_OPTION, SqliteBeginMode.DEFERRED
            )
            mode = SqliteBeginMode(requested)  # raises ValueError for unknown values
            connection.exec_driver_sql(f"BEGIN {mode.value}")


def begin_write_transaction(session: Session) -> None:
    """Start a transaction that takes SQLite's write lock immediately.

    Call this as the FIRST database action of any "check, then save" operation
    (the booking overlap check, rule R5). Other writers then wait until this
    transaction commits or rolls back, so their checks see its result.

    The execution option only takes effect when it is passed on the first
    connection request of a transaction. If the session already has a
    read-only transaction open (for example from the sign-in lookup earlier
    in the same request), that transaction is committed first, which is
    harmless because it has changed nothing. If the session holds unsaved
    changes, this raises instead of silently committing them.
    """
    if session.in_transaction():
        if session.new or session.dirty or session.deleted:
            raise RuntimeError(
                "Cannot start a write transaction while the session has pending changes."
            )
        session.commit()
    session.connection(execution_options={SQLITE_BEGIN_MODE_OPTION: SqliteBeginMode.IMMEDIATE})