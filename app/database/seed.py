"""Демонстрационный мир: заполняет пустую кампанию, чтобы симуляция работала."""
from app.database.models import (
    Resource,
    Settlement,
    SettlementInventory,
    TradeRoute,
    Trader,
)
from app.database.session import session_scope


def seed_demo_world(campaign_id: int) -> bool:
    """Создать три деревни, два города, рынки, маршруты и торговцев.

    Ничего не делает, если в кампании уже есть поселения.
    Возвращает True, если мир был создан.
    """
    with session_scope() as session:
        if session.query(Settlement).filter_by(campaign_id=campaign_id).first():
            return False

        village_a = Settlement(
            campaign_id=campaign_id, name="Дубравка", type="village",
            population=120, description="Аграрная деревня")
        village_b = Settlement(
            campaign_id=campaign_id, name="Лесная", type="village",
            population=90, description="Лесная деревня")
        village_c = Settlement(
            campaign_id=campaign_id, name="Речная", type="village",
            population=150, description="Деревня у реки")
        city_a = Settlement(
            campaign_id=campaign_id, name="Североград", type="city",
            population=1200, description="Крупный торговый город")
        city_b = Settlement(
            campaign_id=campaign_id, name="Приморск", type="city",
            population=900, description="Портовый город")
        session.add_all([village_a, village_b, village_c, city_a, city_b])
        session.flush()

        wheat = Resource(campaign_id=campaign_id, name="Пшеница",
                         category="Еда", unit="мешок", base_price_copper=50)
        iron = Resource(campaign_id=campaign_id, name="Железо",
                        category="Сырьё", unit="слиток", base_price_copper=120)
        cloth = Resource(campaign_id=campaign_id, name="Ткань",
                         category="Ремесло", unit="рулон", base_price_copper=80)
        session.add_all([wheat, iron, cloth])
        session.flush()

        # деревни производят пшеницу и покупают железо/ткань,
        # города наоборот — покупают пшеницу, производят ремесло
        markets = {
            village_a: (
                (wheat, 200, 500, 240, 20, 50),
                (iron, 10, 300, 0, 5, 150),
                (cloth, 20, 300, 0, 4, 110),
            ),
            village_b: (
                (wheat, 180, 500, 200, 25, 55),
                (iron, 5, 300, 0, 4, 160),
                (cloth, 15, 300, 0, 5, 115),
            ),
            village_c: (
                (wheat, 220, 500, 260, 18, 45),
                (iron, 8, 300, 0, 6, 145),
                (cloth, 25, 300, 0, 6, 105),
            ),
            city_a: (
                (wheat, 60, 500, 0, 180, 80),
                (iron, 80, 500, 20, 30, 120),
                (cloth, 100, 400, 60, 10, 80),
            ),
            city_b: (
                (wheat, 40, 500, 0, 220, 90),
                (iron, 60, 500, 10, 35, 115),
                (cloth, 80, 400, 80, 12, 75),
            ),
        }
        for settlement, rows in markets.items():
            for resource, quantity, capacity, production, consumption, price in rows:
                session.add(SettlementInventory(
                    settlement_id=settlement.id, resource_id=resource.id,
                    quantity=quantity, storage_capacity=capacity,
                    production_rate=production,
                    consumption_rate=consumption,
                    price_copper=price,
                ))

        for start, end, distance, hours, cost in (
            (village_a, city_a, 12.0, 10, 2),
            (village_b, city_a, 18.0, 14, 3),
            (village_c, city_b, 15.0, 12, 2),
            (city_a, city_b, 20.0, 16, 3),
        ):
            session.add(TradeRoute(
                campaign_id=campaign_id,
                from_settlement_id=start.id, to_settlement_id=end.id,
                distance=distance, travel_hours=hours,
                transport_cost_copper=cost, capacity=100,
                risk_level=0.05, enabled=True,
            ))

        for name, home in (
            ("Иван", village_a), ("Марта", city_a),
            ("Святослав", village_b), ("Агата", city_b),
            ("Тимур", village_c),
        ):
            session.add(Trader(
                campaign_id=campaign_id, name=name,
                home_settlement_id=home.id, current_settlement_id=home.id,
                capital_copper=10000, cargo_capacity=50,
                strategy="traveling",
            ))
    return True
