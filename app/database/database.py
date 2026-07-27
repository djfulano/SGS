from sqlalchemy import create_engine
from sqlalchemy import event

from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL


engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=(
        {
            "timeout": 30,
            "check_same_thread": False,
        }
        if DATABASE_URL.startswith("sqlite")
        else {}
    ),
)


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def configurar_sqlite(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()
