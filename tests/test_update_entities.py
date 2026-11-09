"""Тесты редактирования поселений и ресурсов."""
import pytest

from app.core.exceptions import AppError
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService


def test_update_settlement(campaign_id):
    svc = SettlementService()
    s = svc.create_settlement(campaign_id, "Старая", "village", 100)
    svc.update_settlement(s.id, name="Новая", settlement_type="city",
                          population=5000, description="Столица")
    loaded = svc.get_settlements(campaign_id)[0]
    assert (loaded.name, loaded.type, loaded.population) == ("Новая", "city", 5000)
    assert loaded.description == "Столица"


def test_update_settlement_validates(campaign_id):
    svc = SettlementService()
    a = svc.create_settlement(campaign_id, "А", "village", 10)
    svc.create_settlement(campaign_id, "Б", "town", 20)
    with pytest.raises(AppError):
        svc.update_settlement(a.id, name="Б")      # дубликат имени
    with pytest.raises(AppError):
        svc.update_settlement(a.id, name="   ")    # пустое имя
    with pytest.raises(AppError):
        svc.update_settlement(a.id, population=-5)  # отрицательное население


def test_update_resource(campaign_id):
    svc = ResourceService()
    r = svc.create_resource(campaign_id, "Старое", "Еда", "шт", 100)
    svc.update_resource(campaign_id, r.id, name="Новое", category="Товары",
                        unit="мешок", base_price_copper=250)
    loaded = svc.get_resources(campaign_id)[0]
    assert loaded.name == "Новое"
    assert loaded.base_price_copper == 250
    assert loaded.unit == "мешок"


def test_update_resource_validates(campaign_id):
    svc = ResourceService()
    a = svc.create_resource(campaign_id, "А", "Еда", "шт", 100)
    svc.create_resource(campaign_id, "Б", "Еда", "шт", 100)
    with pytest.raises(AppError):
        svc.update_resource(campaign_id, a.id, name="Б")
    with pytest.raises(AppError):
        svc.update_resource(campaign_id, a.id, base_price_copper=0)
    with pytest.raises(AppError):
        svc.update_resource(campaign_id, a.id + 999, name="X")
