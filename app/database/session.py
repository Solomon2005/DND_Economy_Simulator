"""Создание движка SQLAlchemy, включение PRAGMA foreign_keys, фабрика сессий."""
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATA_DIR, DB_PATH
from app.database.models import Base


def build_engine(db_path):
    """Создать движок SQLite с включёнными внешними ключами."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def build_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


# Основная БД приложения
engine = build_engine(DB_PATH)
SessionLocal = build_session_factory(engine)


def init_db() -> None:
    """Создать каталоги и таблицы основной БД (без пересоздания существующих)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "backups").mkdir(exist_ok=True)
    (DATA_DIR / "exports").mkdir(exist_ok=True)
    Base.metadata.create_all(engine)


def check_integrity() -> str:
    """PRAGMA integrity_check: 'ok' или текст проблемы."""
    with engine.connect() as connection:
        result = connection.execute(text("PRAGMA integrity_check")).scalar()
    return result or "ok"


@contextmanager
def session_scope():
    """Короткая сессия с автокоммитом/откатом — единая точка записи."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
