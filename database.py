from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # Supabase's pooler closes idle connections; without these, the next request
    # on a dead pooled connection fails ("content sometimes doesn't load")
    **({} if _is_sqlite else {"pool_pre_ping": True, "pool_recycle": 300}),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()