from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import Lot, ChipLog  # noqa: F401 — register models
    Base.metadata.create_all(bind=engine)
    _migrate_schema()


def _migrate_schema():
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if not insp.has_table("die_records"):
        return
    cols = {c["name"] for c in insp.get_columns("die_records")}
    alters = []
    if "booton" not in cols:
        alters.append("ALTER TABLE die_records ADD COLUMN booton VARCHAR(32)")
    if "tested" not in cols:
        alters.append("ALTER TABLE die_records ADD COLUMN tested VARCHAR(32)")
    if not alters:
        return
    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
