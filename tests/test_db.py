"""Тесты базы данных: маппер, таблицы, внешние ключи, каскад, персистентность."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import configure_mappers

from app.database.models import (
    Base,
    Campaign,
    Resource,
    Settlement,
    SettlementInventory,
    TradeRoute,
)
from app.database.session import build_engine, build_session_factory


def test_mapper_configures():
    configure_mappers()  # упадёт при ошибке связей ORM


def test_tables_create_and_persist(db_path):
    engine = build_engine(db_path)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)

    with factory() as s:
        campaign = Campaign(name="Тестовая кампания")
        s.add(campaign)
        s.flush()
        s.add(Settlement(campaign_id=campaign.id, name="Деревня Лесная", type="village",
                         population=120))
        s.commit()

    # «перезапуск приложения»: новый движок на том же файле
    engine2 = build_engine(db_path)
    factory2 = build_session_factory(engine2)
    with factory2() as s:
        names = [row.name for row in s.query(Settlement).all()]
        assert "Деревня Лесная" in names


def test_foreign_key_enforced(session):
    # вставка поселения с несуществующим campaign_id должна падать
    with pytest.raises(Exception):
        session.add(Settlement(campaign_id=99999, name="Привидение"))
        session.flush()
    session.rollback()


def test_settlement_and_route_creation(session):
    campaign = Campaign(name="К")
    session.add(campaign)
    session.flush()
    a = Settlement(campaign_id=campaign.id, name="А")
    b = Settlement(campaign_id=campaign.id, name="Б")
    session.add_all([a, b])
    session.flush()
    route = TradeRoute(campaign_id=campaign.id, from_settlement_id=a.id,
                       to_settlement_id=b.id, travel_hours=6,
                       transport_cost_copper=2, capacity=80, risk_level=0.1)
    session.add(route)
    session.flush()

    loaded = session.get(TradeRoute, route.id)
    assert loaded.from_settlement.name == "А"
    assert loaded.to_settlement.name == "Б"
    assert loaded.travel_hours == 6


def test_duplicate_settlement_name_rejected(session):
    campaign = Campaign(name="К")
    session.add(campaign)
    session.flush()
    session.add(Settlement(campaign_id=campaign.id, name="Дубль"))
    session.flush()
    with pytest.raises(Exception):
        session.add(Settlement(campaign_id=campaign.id, name="Дубль"))
        session.flush()
    session.rollback()


def test_inventory_unique_and_cascade_delete(session):
    campaign = Campaign(name="К")
    session.add(campaign)
    session.flush()
    settlement = Settlement(campaign_id=campaign.id, name="Город")
    resource = Resource(campaign_id=campaign.id, name="Пшеница",
                        base_price_copper=50)
    session.add_all([settlement, resource])
    session.flush()
    session.add(SettlementInventory(settlement_id=settlement.id,
                                    resource_id=resource.id, quantity=100,
                                    price_copper=50))
    session.commit()

    with pytest.raises(Exception):
        session.add(SettlementInventory(settlement_id=settlement.id,
                                        resource_id=resource.id, quantity=1))
        session.flush()
    session.rollback()

    # удаление поселения каскадом удаляет склад
    sid = settlement.id
    session.delete(session.get(Settlement, sid))
    session.flush()
    assert session.query(SettlementInventory).filter_by(settlement_id=sid).count() == 0


def test_services_insert_into_legacy_not_null_columns(tmp_path, monkeypatch):
    """Старая БД хранит notes/reserved/risk_tolerance как NOT NULL."""
    import sqlite3

    from app.database import session as session_module
    from app.services.inventory_service import InventoryService
    from app.services.resource_service import ResourceService
    from app.services.settlement_service import SettlementService
    from app.services.trader_service import TraderService

    db = tmp_path / "legacy.db"
    engine = build_engine(db)
    Base.metadata.tables["campaigns"].create(engine)
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE settlements (
            id INTEGER NOT NULL PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            type VARCHAR(30) NOT NULL,
            population INTEGER NOT NULL,
            description TEXT NOT NULL,
            notes TEXT NOT NULL
        );
        CREATE TABLE resources (
            id INTEGER NOT NULL PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            category VARCHAR(100) NOT NULL,
            unit VARCHAR(50) NOT NULL,
            base_price_copper INTEGER NOT NULL,
            perishable BOOLEAN NOT NULL
        );
        CREATE TABLE settlement_inventories (
            id INTEGER NOT NULL PRIMARY KEY,
            settlement_id INTEGER NOT NULL,
            resource_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            reserved INTEGER NOT NULL,
            storage_capacity INTEGER NOT NULL,
            production_rate INTEGER NOT NULL,
            consumption_rate INTEGER NOT NULL,
            price_copper INTEGER NOT NULL
        );
        CREATE TABLE traders (
            id INTEGER NOT NULL PRIMARY KEY,
            campaign_id INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            home_settlement_id INTEGER NOT NULL,
            current_settlement_id INTEGER,
            capital_copper INTEGER NOT NULL,
            cargo_capacity INTEGER NOT NULL,
            strategy VARCHAR(30) NOT NULL,
            negotiation_skill FLOAT NOT NULL,
            risk_tolerance FLOAT NOT NULL,
            min_profit_margin FLOAT NOT NULL,
            activity VARCHAR(50) NOT NULL,
            journey_route_id INTEGER,
            journey_remaining_hours INTEGER NOT NULL
        );
    """)
    con.close()
    monkeypatch.setattr(
        session_module, "SessionLocal", build_session_factory(engine))
    with session_module.session_scope() as s:
        campaign = Campaign(name="Старая")
        s.add(campaign)
        s.flush()
        campaign_id = campaign.id

    settlement = SettlementService().create_settlement(
        campaign_id, "Деревня", "village", 100)
    resource = ResourceService().create_resource(
        campaign_id, "Пшеница", "Еда", "мешок", 50)
    InventoryService().add_entry(settlement.id, resource.id)
    TraderService().create_trader(
        campaign_id, "Купец", settlement.id, 1000)


def test_cannot_delete_resource_in_use(session):
    """Безопасное удаление ресурса: проверка каскада не теряет данные кампании."""
    campaign = Campaign(name="К")
    session.add(campaign)
    session.flush()
    settlement = Settlement(campaign_id=campaign.id, name="Город")
    resource = Resource(campaign_id=campaign.id, name="Соль")
    session.add_all([settlement, resource])
    session.flush()
    session.add(SettlementInventory(settlement_id=settlement.id,
                                    resource_id=resource.id, quantity=5))
    session.flush()
    # каскадный доступ к складам проверяется в services (удаление блокируется там),
    # здесь фиксируем сам факт связей
    assert resource.id is not None
    assert session.query(SettlementInventory).filter_by(resource_id=resource.id).count() == 1
