"""Интеграционные тесты сервиса торговых маршрутов."""
import pytest

from app.core.exceptions import AppError
from app.services.settlement_service import SettlementService
from app.services.trade_route_service import TradeRouteService


@pytest.fixture
def places(campaign_id):
    svc = SettlementService()
    a = svc.create_settlement(campaign_id, "А", "village", 100)
    b = svc.create_settlement(campaign_id, "Б", "town", 500)
    return a, b


def test_create_and_get(campaign_id, places):
    a, b = places
    svc = TradeRouteService()
    route = svc.create_route(campaign_id, a.id, b.id, distance=15,
                             travel_hours=10, transport_cost_copper=3,
                             capacity=60, risk_level=0.1)
    assert route.id is not None
    routes = svc.get_routes(campaign_id)
    assert len(routes) == 1
    assert routes[0].travel_hours == 10


def test_reject_self_route(campaign_id, places):
    a, _ = places
    with pytest.raises(AppError):
        TradeRouteService().create_route(campaign_id, a.id, a.id)


def test_reject_duplicate(campaign_id, places):
    a, b = places
    svc = TradeRouteService()
    svc.create_route(campaign_id, a.id, b.id)
    with pytest.raises(AppError):
        svc.create_route(campaign_id, a.id, b.id)
    # маршрут двусторонний: обратное направление — тот же самый маршрут
    with pytest.raises(AppError):
        svc.create_route(campaign_id, b.id, a.id)


def test_reject_invalid_values(campaign_id, places):
    a, b = places
    svc = TradeRouteService()
    with pytest.raises(AppError):
        svc.create_route(campaign_id, a.id, b.id, travel_hours=0)
    with pytest.raises(AppError):
        svc.create_route(campaign_id, a.id, b.id, risk_level=1.5)


def test_toggle_and_delete(campaign_id, places):
    a, b = places
    svc = TradeRouteService()
    route = svc.create_route(campaign_id, a.id, b.id)
    svc.set_enabled(route.id, False)
    assert svc.get_routes(campaign_id)[0].enabled is False
    svc.delete_route(route.id)
    assert svc.get_routes(campaign_id) == []


def test_neighbors_respect_enabled_and_season(campaign_id, places):
    a, b = places
    svc = TradeRouteService()
    route = svc.create_route(campaign_id, a.id, b.id, seasonal_restriction="winter")
    assert len(svc.get_neighbors(a.id)) == 1
    assert len(svc.get_neighbors(b.id)) == 1  # маршрут двусторонний
    assert len(svc.get_neighbors(a.id, season="winter")) == 1
    assert len(svc.get_neighbors(a.id, season="summer")) == 0
    svc.set_enabled(route.id, False)
    assert svc.get_neighbors(a.id) == []
    assert svc.get_neighbors(b.id) == []


def test_russian_season_restriction_is_understood(campaign_id, places):
    """Старые данные с «зима» не должны молча отключать маршрут."""
    a, b = places
    route = TradeRouteService().create_route(
        campaign_id, a.id, b.id, seasonal_restriction="Зима")
    assert len(TradeRouteService().get_neighbors(a.id, season="winter")) == 1
