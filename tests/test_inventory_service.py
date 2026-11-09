"""Интеграционные тесты сервиса складов."""
import pytest

from app.core.exceptions import AppError
from app.database.models import EconomicEvent
from app.database.session import session_scope
from app.services.inventory_service import InventoryService
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService


@pytest.fixture
def setup(campaign_id):
    settlement = SettlementService().create_settlement(campaign_id, "Город", "city", 800)
    resource = ResourceService().create_resource(
        campaign_id, "Пшеница", "Еда", "мешок", 50)
    return settlement, resource


def test_add_entry_and_get(campaign_id, setup):
    settlement, resource = setup
    svc = InventoryService()
    entry = svc.add_entry(settlement.id, resource.id)
    assert entry.quantity == 0
    assert entry.price_copper == 50
    assert len(svc.get_inventory(settlement.id)) == 1
    with pytest.raises(AppError):
        svc.add_entry(settlement.id, resource.id)  # дубликат


def test_adjust_positive_and_negative_guard(campaign_id, setup):
    settlement, resource = setup
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    svc.adjust_quantity(settlement.id, resource.id, 100)
    assert svc.get_inventory(settlement.id)[0].quantity == 100
    svc.adjust_quantity(settlement.id, resource.id, -40)
    assert svc.get_inventory(settlement.id)[0].quantity == 60
    with pytest.raises(AppError):
        svc.adjust_quantity(settlement.id, resource.id, -100)  # ниже нуля запрещено


def test_adjust_writes_event(campaign_id, setup):
    settlement, resource = setup
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    svc.adjust_quantity(settlement.id, resource.id, 10, reason="списание")
    with session_scope() as s:
        events = s.query(EconomicEvent).filter_by(
            category="manual_adjustment").all()
        assert len(events) == 1
        assert "Пшеница" in events[0].description
        assert "+10" in events[0].description


def test_update_entry_params(campaign_id, setup):
    settlement, resource = setup
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    svc.update_entry(settlement.id, resource.id, production_rate=20,
                     consumption_rate=15, price_copper=75, storage_capacity=300)
    entry = svc.get_inventory(settlement.id)[0]
    assert (entry.production_rate, entry.consumption_rate) == (20, 15)
    assert entry.price_copper == 75
    assert entry.storage_capacity == 300
    with pytest.raises(AppError):
        svc.update_entry(settlement.id, resource.id, production_rate=-5)


def test_remove_entry(campaign_id, setup):
    settlement, resource = setup
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    svc.remove_entry(settlement.id, resource.id)
    assert svc.get_inventory(settlement.id) == []
    with pytest.raises(AppError):
        svc.remove_entry(settlement.id, resource.id)


def test_resource_in_use_cannot_be_deleted(campaign_id, setup):
    settlement, resource = setup
    InventoryService().add_entry(settlement.id, resource.id)
    with pytest.raises(AppError):
        ResourceService().delete_resource(campaign_id, resource.id)
