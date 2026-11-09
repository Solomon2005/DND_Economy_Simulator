"""Регрессионные тесты исправлений аудита."""
import logging
import time
from logging.handlers import RotatingFileHandler

import pytest
from sqlalchemy import event

from app.core.config import load_config
from app.core.exceptions import AppError
from app.database.models import (
    Campaign,
    EconomicEvent,
    PriceHistory,
    SettlementInventory,
    TradeTransaction,
    TraderCargo,
)
from app.database.session import session_scope
from app.economy.market_engine import apply_production
from app.services.event_service import EventService
from app.services.inventory_service import InventoryService
from app.services.report_service import ReportService
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService
from app.services.simulation_service import SimulationService
from app.services.trader_service import TraderService
from app.services.transaction_service import TransactionService
from app.simulation.simulation_clock import SimulationClock
from app.simulation.simulation_engine import run_tick


def _world(campaign_id, name="Город"):
    settlement = SettlementService().create_settlement(
        campaign_id, name, "city", 800)
    resource = ResourceService().create_resource(
        campaign_id, "Пшеница", "Еда", "мешок", 50)
    return settlement, resource


# --- P1.1: ёмкость склада ------------------------------------------------

def test_adjust_above_capacity_rejected(campaign_id):
    settlement, resource = _world(campaign_id)
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    svc.update_entry(settlement.id, resource.id, storage_capacity=100)

    with pytest.raises(AppError, match="Недостаточно места"):
        svc.adjust_quantity(settlement.id, resource.id, 101)
    assert svc.get_inventory(settlement.id)[0].quantity == 0

    svc.adjust_quantity(settlement.id, resource.id, 100)
    assert svc.get_inventory(settlement.id)[0].quantity == 100


def test_capacity_below_stock_rejected(campaign_id):
    settlement, resource = _world(campaign_id)
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    svc.adjust_quantity(settlement.id, resource.id, 50)

    with pytest.raises(AppError, match="меньше текущего остатка"):
        svc.update_entry(settlement.id, resource.id, storage_capacity=49)
    entry = svc.get_inventory(settlement.id)[0]
    assert (entry.quantity, entry.storage_capacity) == (50, 500)

    svc.update_entry(settlement.id, resource.id, storage_capacity=50)
    assert svc.get_inventory(settlement.id)[0].storage_capacity == 50


def test_production_does_not_destroy_over_capacity_stock():
    # старая БД могла сохранить запас выше ёмкости — тик его не обрезает
    assert apply_production(600, 10, 24, 500) == 600


# --- P1.2: знаки балансов ------------------------------------------------

def test_settlement_balance_signs(campaign_id):
    settlement, resource = _world(campaign_id)
    svc = TransactionService()
    svc.record_player_transaction(
        campaign_id, settlement.id, resource.id, "player_purchase",
        1, 2200, mode="bookkeeping")
    svc.record_player_transaction(
        campaign_id, settlement.id, resource.id, "player_sale",
        1, 700, mode="bookkeeping")

    balances = ReportService().settlement_balances(campaign_id)
    assert balances == [{"settlement": settlement.name, "balance": 1500}]


def test_unknown_transaction_kind_is_not_counted(campaign_id):
    settlement, resource = _world(campaign_id)
    with session_scope() as s:
        s.add(TradeTransaction(
            campaign_id=campaign_id, settlement_id=settlement.id,
            resource_id=resource.id, kind="mystery", quantity=1,
            price_per_unit_copper=100, total_copper=100))
    assert ReportService().settlement_balances(campaign_id) == []


# --- P1.3: удаление ресурса ----------------------------------------------

def test_delete_resource_without_use_succeeds(campaign_id):
    _, resource = _world(campaign_id)
    ResourceService().delete_resource(campaign_id, resource.id)
    assert ResourceService().get_resources(campaign_id) == []


def test_delete_resource_blocked_by_trader_cargo(campaign_id):
    settlement, resource = _world(campaign_id)
    trader = TraderService().create_trader(
        campaign_id, "Купец", settlement.id, 1000)
    with session_scope() as s:
        s.add(TraderCargo(trader_id=trader.id, resource_id=resource.id,
                          quantity=5))

    with pytest.raises(AppError, match="грузе"):
        ResourceService().delete_resource(campaign_id, resource.id)

    with session_scope() as s:
        cargo = s.query(TraderCargo).filter_by(resource_id=resource.id).one()
        assert cargo.quantity == 5


# --- P2: валидация -------------------------------------------------------

def test_zero_price_is_rejected(campaign_id):
    settlement, resource = _world(campaign_id)
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    with pytest.raises(AppError, match="Цена"):
        svc.update_entry(settlement.id, resource.id, price_copper=0)
    with pytest.raises(AppError, match="Цена"):
        svc.add_entry(settlement.id, resource.id, price_copper=0)


def test_negative_stock_is_rejected(campaign_id):
    settlement, resource = _world(campaign_id)
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    with pytest.raises(AppError):
        svc.adjust_quantity(settlement.id, resource.id, -1)


def test_bad_default_capacity_blocks_new_entry(campaign_id, monkeypatch):
    from app.services import inventory_service
    settlement, resource = _world(campaign_id)
    monkeypatch.setattr(
        inventory_service, "load_config",
        lambda: {**load_config(), "default_storage_capacity": 0})
    with pytest.raises(AppError, match="Склад по умолчанию"):
        InventoryService().add_entry(settlement.id, resource.id)


def test_negative_capacity_in_db_stops_tick(campaign_id):
    settlement, resource = _world(campaign_id)
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    with session_scope() as s:
        s.query(SettlementInventory).filter_by(
            settlement_id=settlement.id, resource_id=resource.id
        ).one().storage_capacity = -1
    with pytest.raises(AppError, match="ёмкость"):
        with session_scope() as s:
            run_tick(s, campaign_id, load_config(), hours=1)


def test_negative_stock_in_db_stops_tick(campaign_id):
    settlement, resource = _world(campaign_id)
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    with session_scope() as s:
        s.query(SettlementInventory).filter_by(
            settlement_id=settlement.id, resource_id=resource.id
        ).one().quantity = -1
    with pytest.raises(AppError, match="Отрицательный остаток"):
        with session_scope() as s:
            run_tick(s, campaign_id, load_config(), hours=1)


def test_bad_tick_sets_error_status(campaign_id):
    settlement, resource = _world(campaign_id)
    svc = InventoryService()
    svc.add_entry(settlement.id, resource.id)
    svc.adjust_quantity(settlement.id, resource.id, 10)
    # обходим сервисную валидацию, имитируя старую/битую запись
    with session_scope() as s:
        s.query(SettlementInventory).filter_by(
            settlement_id=settlement.id, resource_id=resource.id
        ).one().price_copper = 0

    clock = SimulationClock(campaign_id, {**load_config(),
                                         "tick_real_seconds": 0.05})
    service = SimulationService(campaign_id, clock)
    service.set_status("running")
    try:
        deadline = time.time() + 5
        status = "running"
        while time.time() < deadline:
            status = service.get_state()["status"]
            if status == "error":
                break
            time.sleep(0.05)
        assert status == "error"
        assert "положительными" in (clock.last_error or "")
        service.set_status("stopped")
    finally:
        clock.stop(timeout=5)
    assert service.get_state()["status"] == "stopped"


def test_second_tick_is_rejected(campaign_id):
    clock = SimulationClock(campaign_id, load_config())
    service = SimulationService(campaign_id, clock)
    service.set_status("paused")
    assert clock._tick_lock.acquire(blocking=False)
    try:
        with pytest.raises(AppError, match="уже выполняется"):
            service.advance(1)
    finally:
        clock._tick_lock.release()
        clock.stop()


# --- P3: поиск по-русски -------------------------------------------------

def test_event_search_is_case_insensitive_cyrillic(campaign_id):
    with session_scope() as s:
        s.add(EconomicEvent(
            campaign_id=campaign_id, category="production",
            description="Пшеница: произведено 12"))
        s.add(EconomicEvent(
            campaign_id=campaign_id, category="production",
            description="Wheat harvested"))
    svc = EventService()
    for query in ("пшеница", "ПШЕНИЦА", "пшеНиЦа"):
        assert len(svc.get_events(campaign_id, search=query)) == 1
    assert len(svc.get_events(campaign_id, search="")) == 2
    assert len(svc.get_events(campaign_id, search="wheat")) == 1
    assert svc.get_events(campaign_id, search="рожь") == []


# --- P5: retention и запросы ---------------------------------------------

def test_price_history_retention(campaign_id):
    settlement, resource = _world(campaign_id)
    InventoryService().add_entry(settlement.id, resource.id)
    with session_scope() as s:
        campaign = s.get(Campaign, campaign_id)
        campaign.game_hour = 24
        s.add(PriceHistory(
            settlement_id=settlement.id, resource_id=resource.id,
            game_hour=0, price_copper=50))
        s.add(PriceHistory(
            settlement_id=settlement.id, resource_id=resource.id,
            game_hour=24, price_copper=50))

    cfg = {**load_config(), "price_history_days": 1}
    with session_scope() as s:
        run_tick(s, campaign_id, cfg, hours=24)

    with session_scope() as s:
        hours = [p.game_hour for p in s.query(PriceHistory).filter_by(
            resource_id=resource.id).all()]
    assert 0 not in hours
    assert 24 in hours


def _tick_select_count(campaign_id, resource_count):
    origin = SettlementService().create_settlement(
        campaign_id, "Лесная", "village", 120)
    dest = SettlementService().create_settlement(
        campaign_id, "Городок", "town", 900)
    resources = [ResourceService().create_resource(
        campaign_id, f"Товар {i}", "Прочее", "шт", 100)
        for i in range(resource_count)]
    inv = InventoryService()
    for res in resources:
        inv.add_entry(origin.id, res.id, price_copper=100)
        inv.add_entry(dest.id, res.id, price_copper=10)
        inv.adjust_quantity(origin.id, res.id, 10)
    from app.services.trade_route_service import TradeRouteService
    TradeRouteService().create_route(
        campaign_id, origin.id, dest.id, travel_hours=1,
        transport_cost_copper=1, capacity=100, risk_level=0.0)
    TraderService().create_trader(campaign_id, "Купец", origin.id, 10000)

    with session_scope() as s:
        engine = s.get_bind()
    counter = {"n": 0}

    def _count(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            counter["n"] += 1

    event.listen(engine, "before_cursor_execute", _count)
    try:
        with session_scope() as s:
            run_tick(s, campaign_id, load_config(), hours=1)
    finally:
        event.remove(engine, "before_cursor_execute", _count)
    return counter["n"]


def test_tick_select_count_does_not_grow_per_resource(campaign_id):
    one = _tick_select_count(campaign_id, 1)
    with session_scope() as s:
        second = Campaign(name="Вторая кампания")
        s.add(second)
        s.flush()
        second_id = second.id
    five = _tick_select_count(second_id, 5)
    # число SELECT не зависит от количества ресурсов (нет N+1)
    assert five <= one + 2


# --- P6: тема и логи -----------------------------------------------------

def test_theme_default_save_and_invalid_fallback(tmp_path, monkeypatch):
    from app.core import config
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)

    assert config.load_config()["theme"] == "dark"
    cfg = config.load_config()
    cfg["theme"] = "light"
    config.save_config(cfg)
    assert config.load_config()["theme"] == "light"

    cfg_file.write_text('{"theme": "neon"}', encoding="utf-8")
    assert config.load_config()["theme"] == "dark"


def test_logging_uses_rotating_handler(tmp_path, monkeypatch):
    import main
    from app.core import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    main._setup_logging()
    root = logging.getLogger()
    try:
        assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()


def test_launcher_dependencies_available():
    import launcher
    assert launcher.check_dependencies() == []
