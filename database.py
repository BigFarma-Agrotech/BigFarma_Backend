import time

from sqlalchemy import create_engine, event, exc
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # Replace pooled connections before Supabase's pooler drops them
    **({} if _is_sqlite else {"pool_recycle": 300}),
)

# Supabase's pooler closes idle connections, and a request that picks up a dead
# one fails ("content sometimes doesn't load"). Checking every connection
# (pool_pre_ping) would cost a database round trip on every request, which is
# slow from Render, so only connections idle for a while are checked.
IDLE_CHECK_SECONDS = 60

if not _is_sqlite:
    @event.listens_for(engine, "checkin")
    def _remember_last_use(dbapi_connection, connection_record):
        connection_record.info["last_used"] = time.monotonic()

    @event.listens_for(engine, "checkout")
    def _check_if_idle(dbapi_connection, connection_record, connection_proxy):
        last_used = connection_record.info.get("last_used")
        if last_used is None or time.monotonic() - last_used < IDLE_CHECK_SECONDS:
            return
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except Exception:
            # Tells the pool to throw this connection away and connect afresh
            raise exc.DisconnectionError()

# expire_on_commit=False: after a commit, keep using the loaded objects instead
# of re-SELECTing each one on next access (code that needs fresh values calls
# db.refresh explicitly)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
