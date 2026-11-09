"""Общие фикстуры: временные базы данных для тестов."""
import pytest

from app.database.session import build_engine, build_session_factory
from app.database.models import Base, Campaign


@pytest.fixture
def session(tmp_path):
    engine = build_engine(tmp_path / "test.db")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    sess = factory()
    yield sess
    sess.close()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "persist.db"


@pytest.fixture
def campaign_id(tmp_path, monkeypatch):
    """Временная БД вместо основной + id созданной кампании.

    Сервисы используют session_scope() из app.database.session,
    поэтому подменяем там фабрику сессий.
    """
    from app.database import session as session_module
    engine = build_engine(tmp_path / "service.db")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(session_module, "SessionLocal", build_session_factory(engine))
    with session_module.session_scope() as s:
        campaign = Campaign(name="Тест")
        s.add(campaign)
        s.flush()
        return campaign.id
