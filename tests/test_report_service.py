"""Тесты сервиса отчётов и экспорта."""
import pytest

from app.core.exceptions import AppError
from app.services.inventory_service import InventoryService
from app.services.report_service import ReportService
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService
from app.services.transaction_service import TransactionService


@pytest.fixture
def setup(campaign_id):
    a = SettlementService().create_settlement(campaign_id, "А", "village", 100)
    b = SettlementService().create_settlement(campaign_id, "Б", "town", 500)
    res = ResourceService().create_resource(campaign_id, "Мёд", "Еда", "бутыль", 40)
    inv = InventoryService()
    inv.add_entry(a.id, res.id, price_copper=40)
    inv.add_entry(b.id, res.id, price_copper=60)
    inv.adjust_quantity(a.id, res.id, 20)
    return a, b, res


def test_price_series_empty_without_ticks(campaign_id, setup):
    _, _, res = setup
    assert ReportService().price_series(campaign_id, res.id) == []


def test_price_series_after_tick(campaign_id, setup):
    from app.core.config import load_config
    from app.database.session import session_scope
    from app.simulation.simulation_engine import run_tick
    a, _, res = setup
    with session_scope() as s:
        run_tick(s, campaign_id, load_config(), hours=6)
    series = ReportService().price_series(campaign_id, res.id)
    # у поселения А есть остаток при нулевом спросе — цена изменилась (падает);
    # у поеления Б спрос=предложение=0 — цена не двигалась, записи нет
    assert len(series) >= 1
    assert all("price" in p and "game_hour" in p for p in series)
    place_a = [p for p in series if p["settlement"] == "А"]
    assert place_a and place_a[0]["price"] < 40


def test_trade_volume_by_day(campaign_id, setup):
    a, _, res = setup
    svc = TransactionService()
    svc.record_player_transaction(campaign_id, a.id, res.id,
                                  "player_purchase", 2, 40)   # 80
    svc.record_player_transaction(campaign_id, a.id, res.id,
                                  "player_sale", 1, 50)       # 50
    volume = ReportService().trade_volume_by_day(campaign_id)
    assert volume == [(0, 130)]


def test_summary_counts_and_top_resources(campaign_id, setup):
    a, _, res = setup
    TransactionService().record_player_transaction(
        campaign_id, a.id, res.id, "player_purchase", 5, 40)
    data = ReportService().summary(campaign_id)
    assert data["tx_count"] == 1
    assert data["event_count"] >= 1
    assert data["top_resources"] == [("Мёд", 200)]
    assert any(b["settlement"] == "А" for b in data["balances"])


def test_clear_history_removes_trade_data(campaign_id, setup):
    from app.database.models import (
        EconomicEvent,
        Negotiation,
        PriceHistory,
        Settlement,
        TradeTransaction,
    )
    from app.database.session import session_scope

    a, b, res = setup
    TransactionService().record_player_transaction(
        campaign_id, a.id, res.id, "player_purchase", 1, 40)
    with session_scope() as s:
        s.add(PriceHistory(settlement_id=a.id, resource_id=res.id,
                           game_hour=6, price_copper=42))
        s.add(Negotiation(
            campaign_id=campaign_id, game_hour=6, settlement_id=a.id,
            resource_id=res.id, market_price_copper=40,
            final_price_copper=41, accepted=True))

    counts = ReportService().clear_history(campaign_id)

    assert counts["transactions"] == 1
    assert counts["prices"] == 1
    assert counts["negotiations"] == 1
    assert counts["events"] >= 1
    with session_scope() as s:
        assert s.query(TradeTransaction).filter_by(
            campaign_id=campaign_id).count() == 0
        assert s.query(EconomicEvent).filter_by(
            campaign_id=campaign_id).count() == 0
        assert s.query(Negotiation).filter_by(
            campaign_id=campaign_id).count() == 0
        assert s.query(PriceHistory).count() == 0
        # справочники и склады остаются на месте
        assert s.query(Settlement).filter_by(
            campaign_id=campaign_id).count() == 2


def test_clear_history_keeps_other_campaign(campaign_id, setup):
    from app.database.models import (
        Campaign,
        EconomicEvent,
        Negotiation,
        PriceHistory,
        Resource,
        Settlement,
        TradeTransaction,
    )
    from app.database.session import session_scope

    a, _, res = setup
    TransactionService().record_player_transaction(
        campaign_id, a.id, res.id, "player_purchase", 1, 40)

    with session_scope() as s:
        other = Campaign(name="Другая")
        s.add(other)
        s.flush()
        other_id = other.id
        place = Settlement(campaign_id=other_id, name="Чужое",
                           type="village", population=10)
        goods = Resource(campaign_id=other_id, name="Чужой",
                         category="Прочее", unit="шт", base_price_copper=1)
        s.add_all([place, goods])
        s.flush()
        s.add(TradeTransaction(
            campaign_id=other_id, resource_id=goods.id,
            kind="player_purchase", quantity=1,
            price_per_unit_copper=1, total_copper=1))
        s.add(EconomicEvent(campaign_id=other_id, category="purchase",
                            description="чужое событие"))
        s.add(PriceHistory(settlement_id=place.id, resource_id=goods.id,
                           game_hour=1, price_copper=1))
        s.add(Negotiation(
            campaign_id=other_id, resource_id=goods.id,
            market_price_copper=1, final_price_copper=1))

    ReportService().clear_history(campaign_id)

    with session_scope() as s:
        assert s.query(TradeTransaction).filter_by(
            campaign_id=other_id).count() == 1
        assert s.query(EconomicEvent).filter_by(
            campaign_id=other_id).count() == 1
        assert s.query(Negotiation).filter_by(
            campaign_id=other_id).count() == 1
        assert s.query(PriceHistory).count() == 1


def test_export_events_csv(campaign_id, setup):
    a, _, res = setup
    TransactionService().record_player_transaction(
        campaign_id, a.id, res.id, "player_purchase", 1, 40)
    path = ReportService().export_events_csv(campaign_id)
    assert path.exists()
    text = path.read_text(encoding="utf-8-sig")
    assert "player_transaction" in text
    assert "Мёд" in text


def test_export_empty_journal_rejected(campaign_id):
    # кампания без каких-либо действий — журнал пуст
    with pytest.raises(AppError):
        ReportService().export_events_csv(campaign_id)
