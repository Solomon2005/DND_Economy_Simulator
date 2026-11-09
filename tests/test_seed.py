"""Демо-мир: заполнение пустой кампании и запуск симуляции."""
from app.core.config import load_config
from app.database.models import Settlement, TradeTransaction, Trader
from app.database.seed import seed_demo_world
from app.database.session import session_scope
from app.services.settlement_service import SettlementService
from app.simulation.simulation_engine import run_tick


def test_seed_creates_world_once(campaign_id):
    assert seed_demo_world(campaign_id) is True
    settlements = SettlementService().get_settlements(campaign_id)
    assert {s.name for s in settlements} == {
        "Дубравка", "Лесная", "Речная", "Североград", "Приморск"}
    assert sum(s.type == "village" for s in settlements) == 3
    assert sum(s.type == "city" for s in settlements) == 2

    assert seed_demo_world(campaign_id) is False
    with session_scope() as s:
        assert s.query(Settlement).filter_by(
            campaign_id=campaign_id).count() == 5


def test_get_or_create_campaign_seeds_empty_db(tmp_path, monkeypatch):
    from app.database import session as session_module
    from app.database.models import Base
    from app.database.session import build_engine, build_session_factory
    from app.services import get_or_create_campaign

    engine = build_engine(tmp_path / "auto.db")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(
        session_module, "SessionLocal", build_session_factory(engine))

    campaign_id = get_or_create_campaign()
    with session_module.session_scope() as s:
        assert s.query(Settlement).filter_by(
            campaign_id=campaign_id).count() == 5


def test_seeded_world_trades_in_one_tick(campaign_id):
    seed_demo_world(campaign_id)
    with session_scope() as s:
        assert run_tick(s, campaign_id, load_config(), hours=6) == 6
    with session_scope() as s:
        assert s.query(TradeTransaction).filter_by(
            campaign_id=campaign_id, kind="trade_buy").count() >= 1
        assert s.query(Trader).filter_by(
            campaign_id=campaign_id, activity="traveling").count() >= 1
