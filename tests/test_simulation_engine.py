"""Интеграционные тесты движка симуляции на временной БД."""
import pytest

from app.core.config import load_config
from app.database.models import (
    Campaign,
    EconomicEvent,
    PriceHistory,
    SettlementInventory,
    TradeTransaction,
)
from app.database.session import session_scope
from app.services.inventory_service import InventoryService
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService
from app.services.trade_route_service import TradeRouteService
from app.services.trader_service import TraderService
from app.simulation.simulation_engine import run_tick

CFG = load_config()


@pytest.fixture
def world(campaign_id):
    """Два поселения, связанные маршрутом, склады и торговец."""
    settlements = SettlementService()
    origin = settlements.create_settlement(campaign_id, "Лесная", "village", 120)
    dest = settlements.create_settlement(campaign_id, "Городок", "town", 900)
    resource = ResourceService().create_resource(
        campaign_id, "Пшеница", "Еда", "мешок", 50)
    inventory = InventoryService()
    inventory.add_entry(origin.id, resource.id, price_copper=50)
    inventory.add_entry(dest.id, resource.id, price_copper=80)
    inventory.update_entry(origin.id, resource.id, storage_capacity=300)
    inventory.update_entry(dest.id, resource.id, storage_capacity=500)
    route = TradeRouteService().create_route(
        campaign_id, origin.id, dest.id, travel_hours=10,
        transport_cost_copper=2, capacity=100, risk_level=0.0)
    trader = TraderService().create_trader(
        campaign_id, "Иван Купец", origin.id, 10000)
    return {
        "campaign_id": campaign_id, "origin": origin, "dest": dest,
        "resource": resource, "route": route, "trader": trader,
    }


def _tick(campaign_id, hours=None, cfg=None):
    with session_scope() as s:
        return run_tick(s, campaign_id, cfg or CFG, hours=hours)


def test_tick_advances_game_time_and_persists(world):
    _tick(world["campaign_id"])
    with session_scope() as s:
        campaign = s.get(Campaign, world["campaign_id"])
        assert campaign.game_hour == CFG["tick_game_hours"]
    _tick(world["campaign_id"], hours=24)
    with session_scope() as s:
        campaign = s.get(Campaign, world["campaign_id"])
        assert campaign.game_hour == CFG["tick_game_hours"] + 24


def test_production_and_consumption_in_tick(world):
    inventory = InventoryService()
    origin_id, res_id = world["origin"].id, world["resource"].id
    inventory.adjust_quantity(origin_id, res_id, 100)
    inventory.update_entry(origin_id, res_id, production_rate=24,
                           consumption_rate=12, storage_capacity=300)
    # изолируем от торговли: закупка торговцем в этом же тике
    with session_scope() as s:
        from app.database.models import TradeRoute
        s.get(TradeRoute, world["route"].id).enabled = False
    _tick(world["campaign_id"], hours=24)
    entry = inventory.get_inventory(origin_id)[0]
    # день 1 кампании — Январь (зима): фактор производства 0.7
    # 100 + int(24 * 0.7)=16 произведено - 12 потреблено = 104
    assert entry.quantity == 104


def test_stock_never_negative(world):
    inventory = InventoryService()
    origin_id, res_id = world["origin"].id, world["resource"].id
    inventory.update_entry(origin_id, res_id, consumption_rate=1000)
    _tick(world["campaign_id"], hours=24)
    assert inventory.get_inventory(origin_id)[0].quantity >= 0


def test_price_reacts_and_history_recorded(world):
    inventory = InventoryService()
    dest_id, res_id = world["dest"].id, world["resource"].id
    inventory.update_entry(dest_id, res_id, consumption_rate=50,
                           price_copper=80)
    _tick(world["campaign_id"], hours=24)
    with session_scope() as s:
        # спрос 50 против остатка 0 — цена не должна упасть ниже границы
        entry = s.query(SettlementInventory).filter_by(
            settlement_id=dest_id, resource_id=res_id).first()
        assert entry.price_copper >= 80  # спрос растёт — цена не падает
        history = s.query(PriceHistory).filter_by(
            settlement_id=dest_id, resource_id=res_id).all()
        assert len(history) >= 1


def test_trader_buys_departs_arrives_and_sells(world):
    inventory = InventoryService()
    origin_id, dest_id = world["origin"].id, world["dest"].id
    res_id = world["resource"].id
    inventory.adjust_quantity(origin_id, res_id, 200)

    # тик 1: торговец оценивает сделку, покупает и выезжает
    _tick(world["campaign_id"], hours=6)
    with session_scope() as s:
        from app.database.models import Trader
        trader = s.get(Trader, world["trader"].id)
        assert trader.activity == "traveling"
        assert trader.journey_remaining_hours == 10
        assert trader.capital_copper < 10000
        assert sum(c.quantity for c in trader.cargo) > 0
        origin_entry = s.query(SettlementInventory).filter_by(
            settlement_id=origin_id, resource_id=res_id).first()
        assert origin_entry.quantity == 200 - sum(
            c.quantity for c in trader.cargo)

    # тик 2: время пути проходит, прибытие и продажа
    _tick(world["campaign_id"], hours=10)
    with session_scope() as s:
        from app.database.models import Trader
        trader = s.get(Trader, world["trader"].id)
        assert trader.activity == "idle"
        assert trader.current_settlement_id == dest_id
        assert sum(c.quantity for c in trader.cargo) == 0
        assert trader.capital_copper > 0
        dest_entry = s.query(SettlementInventory).filter_by(
            settlement_id=dest_id, resource_id=res_id).first()
        assert dest_entry.quantity > 0
        tx_kinds = {t.kind for t in s.query(TradeTransaction).all()}
        assert {"trade_buy", "trade_sell"} <= tx_kinds


def test_trader_cannot_afford_without_capital(world):
    with session_scope() as s:
        from app.database.models import Trader
        trader = s.get(Trader, world["trader"].id)
        trader.capital_copper = 5  # почти нет денег
    _tick(world["campaign_id"], hours=6)
    with session_scope() as s:
        from app.database.models import Trader
        trader = s.get(Trader, world["trader"].id)
        assert trader.activity == "idle"
        assert trader.capital_copper >= 0
        assert sum(c.quantity for c in trader.cargo) == 0


def test_disabled_route_blocks_trading(world):
    with session_scope() as s:
        from app.database.models import TradeRoute
        route = s.get(TradeRoute, world["route"].id)
        route.enabled = False
    _tick(world["campaign_id"], hours=6)
    with session_scope() as s:
        from app.database.models import Trader
        trader = s.get(Trader, world["trader"].id)
        assert trader.activity == "idle"


def test_event_history_records_trade_chain(world):
    inventory = InventoryService()
    inventory.adjust_quantity(world["origin"].id, world["resource"].id, 200)
    _tick(world["campaign_id"], hours=6)
    _tick(world["campaign_id"], hours=10)
    with session_scope() as s:
        categories = {e.category for e in s.query(EconomicEvent).all()}
        assert "purchase" in categories
        assert "trader_departure" in categories
        assert "trader_arrival" in categories
        assert "sale" in categories


def test_events_and_transactions_survive_restart(world):
    """Персистентность: данные тика живут после «перезапуска» (новая сессия)."""
    inventory = InventoryService()
    inventory.adjust_quantity(world["origin"].id, world["resource"].id, 200)
    _tick(world["campaign_id"], hours=6)
    with session_scope() as s:  # новая сессия = новая «перезагрузка»
        assert s.query(EconomicEvent).count() > 0
        assert s.query(TradeTransaction).count() > 0
        campaign = s.get(Campaign, world["campaign_id"])
        assert campaign.game_hour == 6


def test_russian_winter_restriction_allows_trading(world):
    """Маршрут с ограничением «зима» работает зимой (старые данные)."""
    with session_scope() as s:
        from app.database.models import TradeRoute
        s.get(TradeRoute, world["route"].id).seasonal_restriction = "зима"
    InventoryService().adjust_quantity(
        world["origin"].id, world["resource"].id, 200)
    _tick(world["campaign_id"], hours=6)  # 6-й час = январь, зима
    with session_scope() as s:
        from app.database.models import Trader
        trader = s.get(Trader, world["trader"].id)
        assert trader.activity == "traveling"
        assert sum(c.quantity for c in trader.cargo) > 0


def test_single_route_allows_return_trip(world):
    """Один маршрут двусторонний: торговец возвращается и торгует снова."""
    inventory = InventoryService()
    inventory.adjust_quantity(world["origin"].id, world["resource"].id, 300)
    for _ in range(20):
        _tick(world["campaign_id"], hours=6)
    with session_scope() as s:
        from app.database.models import Trader
        trader = s.get(Trader, world["trader"].id)
        assert trader.current_settlement_id == world["origin"].id
        buys = s.query(TradeTransaction).filter_by(kind="trade_buy").count()
        sells = s.query(TradeTransaction).filter_by(kind="trade_sell").count()
        assert buys >= 2 and sells >= 2


def test_trading_continues_over_multiple_rounds(world):
    """Один двусторонний маршрут: несколько кругов покупка → путь → продажа."""
    inventory = InventoryService()
    inventory.adjust_quantity(world["origin"].id, world["resource"].id, 300)
    for _ in range(40):
        _tick(world["campaign_id"], hours=6)
    with session_scope() as s:
        from app.database.models import Trader
        trader = s.get(Trader, world["trader"].id)
        buys = s.query(TradeTransaction).filter_by(kind="trade_buy").count()
        sells = s.query(TradeTransaction).filter_by(kind="trade_sell").count()
        assert buys >= 2 and sells >= 2
        assert trader.capital_copper > 0
        assert all(c.quantity >= 0 for c in trader.cargo)
