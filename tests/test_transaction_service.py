"""Интеграционные тесты транзакций игроков."""
import pytest

from app.core.exceptions import AppError
from app.services.inventory_service import InventoryService
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService
from app.services.transaction_service import TransactionService


@pytest.fixture
def setup(campaign_id):
    settlement = SettlementService().create_settlement(campaign_id, "Таверна", "town", 400)
    resource = ResourceService().create_resource(campaign_id, "Эликсир", "Зелья",
                                                 "шт", 500)
    inventory = InventoryService()
    inventory.add_entry(settlement.id, resource.id, price_copper=500)
    inventory.adjust_quantity(settlement.id, resource.id, 10)
    return settlement, resource


def test_player_purchase_full_mode(campaign_id, setup):
    settlement, resource = setup
    svc = TransactionService()
    tx = svc.record_player_transaction(
        campaign_id, settlement.id, resource.id, "player_purchase",
        3, 500, counterparty="Отряд", mode="full")
    assert tx.total_copper == 1500
    assert not tx.bookkeeping_only
    entry = InventoryService().get_inventory(settlement.id)[0]
    assert entry.quantity == 7  # 10 - 3


def test_player_sale_full_mode(campaign_id, setup):
    settlement, resource = setup
    svc = TransactionService()
    svc.record_player_transaction(
        campaign_id, settlement.id, resource.id, "player_sale",
        5, 450, mode="full")
    entry = InventoryService().get_inventory(settlement.id)[0]
    assert entry.quantity == 15  # 10 + 5


def test_bookkeeping_mode_keeps_stock(campaign_id, setup):
    settlement, resource = setup
    svc = TransactionService()
    tx = svc.record_player_transaction(
        campaign_id, settlement.id, resource.id, "player_purchase",
        100, 500, mode="bookkeeping")
    assert tx.bookkeeping_only
    entry = InventoryService().get_inventory(settlement.id)[0]
    assert entry.quantity == 10  # склад не изменился


def test_purchase_more_than_stock_rejected(campaign_id, setup):
    settlement, resource = setup
    with pytest.raises(AppError):
        TransactionService().record_player_transaction(
            campaign_id, settlement.id, resource.id, "player_purchase",
            50, 500, mode="full")


def test_invalid_inputs_rejected(campaign_id, setup):
    settlement, resource = setup
    svc = TransactionService()
    with pytest.raises(AppError):
        svc.record_player_transaction(campaign_id, settlement.id, resource.id,
                                      "player_purchase", 0, 500)
    with pytest.raises(AppError):
        svc.record_player_transaction(campaign_id, settlement.id, resource.id,
                                      "player_purchase", 1, 0)
    with pytest.raises(AppError):
        svc.record_player_transaction(campaign_id, settlement.id, resource.id,
                                      "trade_buy", 1, 500)


def test_transaction_writes_event(campaign_id, setup):
    from app.database.models import EconomicEvent
    from app.database.session import session_scope
    settlement, resource = setup
    TransactionService().record_player_transaction(
        campaign_id, settlement.id, resource.id, "player_sale",
        2, 600, mode="full")
    with session_scope() as s:
        events = s.query(EconomicEvent).filter_by(
            category="player_transaction").all()
        assert len(events) == 1
        assert "Эликсир" in events[0].description
        assert events[0].amount_copper == 1200


def test_transactions_listed_and_volume(campaign_id, setup):
    settlement, resource = setup
    svc = TransactionService()
    svc.record_player_transaction(campaign_id, settlement.id, resource.id,
                                  "player_purchase", 1, 500)
    svc.record_player_transaction(campaign_id, settlement.id, resource.id,
                                  "player_sale", 2, 400)
    assert len(svc.get_transactions(campaign_id)) == 2
    only_buys = svc.get_transactions(campaign_id, kind="player_purchase")
    assert len(only_buys) == 1
