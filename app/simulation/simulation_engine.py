"""Движок симуляции: один тик — производство, потребление, цены, торговцы.

Тик детерминирован и выполняется под замком в фоновом потоке.
Каждое значимое изменение попадает в журнал EconomicEvent.
"""
import json
import logging

from sqlalchemy import select

from app.core.exceptions import AppError
from app.database.models import (
    Campaign,
    EconomicEvent,
    Negotiation,
    PriceHistory,
    Resource,
    Settlement,
    SettlementInventory,
    Trader,
    TraderCargo,
    TradeRoute,
    TradeTransaction,
)
from app.economy.market_engine import apply_consumption, apply_production
from app.economy.price_engine import compute_price
from app.simulation.game_calendar import (
    SEASON_PRODUCTION_FACTOR,
    crosses_day_boundary,
    season_allows,
    season_for_hour,
)
from app.trading.negotiation_engine import negotiate
from app.trading.trader_ai import choose_best, evaluate_opportunity

logger = logging.getLogger("app.simulation")


def _event(session, campaign_id, game_hour, category, description, *,
           settlement_id=None, resource_id=None, trader_id=None,
           amount_copper=None, transaction_id=None) -> None:
    session.add(EconomicEvent(
        campaign_id=campaign_id, game_hour=game_hour, category=category,
        description=description, settlement_id=settlement_id,
        resource_id=resource_id, trader_id=trader_id,
        amount_copper=amount_copper, transaction_id=transaction_id,
    ))


def _scarcity(entry) -> float:
    """Дефицит: доля спроса от (остаток + спрос) за период; 0.5 при равенстве."""
    demand = entry.consumption_rate
    total = entry.quantity + demand
    if total <= 0:
        return 0.0
    return round(demand / total, 4)


def run_tick(session, campaign_id: int, cfg: dict, hours: int | None = None) -> int:
    """Выполнить один тик симуляции. Вернуть новое game_hour."""
    dt = hours if hours is not None else int(cfg["tick_game_hours"])
    if dt <= 0:
        raise AppError("Длительность тика должна быть положительной")

    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise AppError("Кампания не найдена")

    old_hour = campaign.game_hour
    new_hour = old_hour + dt
    campaign.game_hour = new_hour
    season = season_for_hour(new_hour)
    daily = cfg.get("record_daily_flows", True) and crosses_day_boundary(
        old_hour, new_hour)
    season_factor = (
        SEASON_PRODUCTION_FACTOR.get(season, 1.0)
        if cfg.get("seasonal_production", True) else 1.0
    )

    _tick_inventories(session, campaign, cfg, dt, new_hour, season_factor, daily)
    stats = _tick_traders(session, campaign, cfg, dt, new_hour, season)
    logger.info(
        "тик выполнен: час=%s, торговцев=%d, маршрутов=%d, возможностей=%d, "
        "принято=%d, покупок=%d, продаж=%d, в пути=%d",
        new_hour, stats["traders"], stats["routes"], stats["opportunities"],
        stats["accepted"], stats["purchases"], stats["sales"],
        stats["traveling"],
    )
    for reason in stats["rejections"]:
        logger.info("  сделка отклонена: %s", reason)
    return new_hour


def _tick_inventories(session, campaign, cfg, dt, game_hour, season_factor, daily):
    """Производство, потребление и цены по всем складам."""
    entries = session.query(SettlementInventory).join(
        Settlement, Settlement.id == SettlementInventory.settlement_id
    ).filter(Settlement.campaign_id == campaign.id).all()
    resources = {r.id: r for r in session.query(Resource).filter_by(
        campaign_id=campaign.id).all()}

    for entry in entries:
        resource = resources.get(entry.resource_id)
        if resource is None:
            continue
        if entry.storage_capacity < 0:
            raise AppError(
                f"Отрицательная ёмкость склада «{resource.name}». "
                "Исправьте значение в разделе «Склады»."
            )
        if entry.quantity < 0:
            raise AppError(
                f"Отрицательный остаток «{resource.name}». "
                "Исправьте значение в разделе «Склады»."
            )
        old_price = entry.price_copper
        old_qty = entry.quantity

        # производство с ограничением склада
        entry.quantity = apply_production(
            entry.quantity, entry.production_rate, dt,
            entry.storage_capacity, season_factor,
        )
        produced = entry.quantity - old_qty

        # потребление без ухода ниже нуля
        entry.quantity = apply_consumption(
            entry.quantity, entry.consumption_rate, dt)
        consumed = old_qty + produced - entry.quantity

        if daily and produced > 0:
            _event(session, campaign.id, game_hour, "production",
                   f"{resource.name}: произведено {produced}, остаток {entry.quantity}",
                   settlement_id=entry.settlement_id, resource_id=resource.id)
        if daily and consumed > 0:
            _event(session, campaign.id, game_hour, "consumption",
                   f"{resource.name}: потреблено {consumed}, остаток {entry.quantity}",
                   settlement_id=entry.settlement_id, resource_id=resource.id)

        # цена: спрос за период = потребление за dt
        demand = int(entry.consumption_rate * (dt / 24.0))
        new_price = compute_price(
            entry.price_copper, resource.base_price_copper,
            supply=entry.quantity, demand=demand,
            price_k=cfg["price_k"],
            min_factor=cfg["price_min_factor"],
            max_factor=cfg["price_max_factor"],
        )
        if new_price != old_price:
            entry.price_copper = new_price
            session.add(PriceHistory(
                settlement_id=entry.settlement_id, resource_id=resource.id,
                game_hour=game_hour, price_copper=new_price,
            ))
            # заметное изменение фиксируется в журнале (shortcut: порог 10% базы)
            if abs(new_price - old_price) >= max(1, resource.base_price_copper * 0.1):
                _event(session, campaign.id, game_hour, "price_change",
                       f"{resource.name}: цена {old_price} → {new_price} CP "
                       f"(остаток {entry.quantity}, спрос {demand})",
                       settlement_id=entry.settlement_id, resource_id=resource.id)

    # retention: история цен ограничена числом игровых суток
    days = int(cfg.get("price_history_days", 90))
    if daily and days > 0:
        cutoff = game_hour - days * 24
        campaign_settlements = select(Settlement.id).where(
            Settlement.campaign_id == campaign.id)
        session.query(PriceHistory).filter(
            PriceHistory.game_hour < cutoff,
            PriceHistory.settlement_id.in_(campaign_settlements),
        ).delete(synchronize_session=False)


def _cargo_lot(session, trader_id: int, resource_id: int):
    return session.query(TraderCargo).filter_by(
        trader_id=trader_id, resource_id=resource_id).first()


def _cargo_total(trader) -> int:
    return sum(lot.quantity for lot in trader.cargo)


def _routes_from(session, settlement_id: int, season: str) -> list[TradeRoute]:
    """Включённые маршруты, соединяющие поселение с соседями (оба направления)."""
    routes = session.query(TradeRoute).filter(
        TradeRoute.enabled.is_(True),
        (TradeRoute.from_settlement_id == settlement_id)
        | (TradeRoute.to_settlement_id == settlement_id),
    ).all()
    return [r for r in routes if season_allows(r.seasonal_restriction, season)]


def _return_home(session, campaign, trader, game_hour, season) -> None:
    """Вернуть торговца домой, если из текущего места некуда ехать."""
    if trader.current_settlement_id == trader.home_settlement_id:
        return
    home = session.get(Settlement, trader.home_settlement_id)
    if home is None:
        return
    origin_id = trader.current_settlement_id
    home_route = next(
        (r for r in _routes_from(session, origin_id, season)
         if r.other_endpoint(origin_id) == home.id), None)
    if home_route is not None:
        trader.activity = "traveling"
        trader.journey_route_id = home_route.id
        trader.journey_remaining_hours = home_route.travel_hours
        _event(session, campaign.id, game_hour, "trader_departure",
               f"{trader.name} возвращается домой в «{home.name}» "
               f"за {home_route.travel_hours} ч",
               settlement_id=origin_id, trader_id=trader.id)
        return
    # shortcut: обратного маршрута нет — возвращаем сразу, иначе торговец
    # навсегда застревает в чужом поселении
    trader.current_settlement_id = home.id
    trader.activity = "idle"
    trader.journey_route_id = None
    trader.journey_remaining_hours = 0
    _event(session, campaign.id, game_hour, "trader_arrival",
           f"{trader.name} вернулся домой в «{home.name}» "
           f"(обратного маршрута нет)",
           settlement_id=home.id, trader_id=trader.id)


def _tick_traders(session, campaign, cfg, dt, game_hour, season) -> dict:
    """Движение торговцев, прибытие, продажа и поиск новых сделок."""
    traders = session.query(Trader).filter_by(campaign_id=campaign.id).all()
    stats = {"traders": len(traders), "routes": 0, "opportunities": 0,
             "accepted": 0, "purchases": 0, "sales": 0, "traveling": 0,
             "rejections": []}
    for trader in traders:
        if trader.activity == "traveling":
            stats["sales"] += _advance_journey(
                session, campaign, cfg, trader, dt, game_hour)
        elif trader.current_settlement_id is not None:
            current = session.get(Settlement, trader.current_settlement_id)
            # повторная попытка продать нераспроданный груз
            if current is not None and _cargo_total(trader) > 0:
                stats["sales"] += _sell_cargo(
                    session, campaign, cfg, trader, current, game_hour)
            result = _try_local_trade(
                session, campaign, cfg, trader, game_hour, season)
            stats["routes"] += result["routes"]
            stats["opportunities"] += result["opportunities"]
            stats["accepted"] += result["accepted"]
            stats["purchases"] += result["purchases"]
            stats["rejections"].extend(result["rejections"])
        if trader.activity == "traveling":
            stats["traveling"] += 1
    return stats


def _advance_journey(session, campaign, cfg, trader, dt, game_hour) -> int:
    """Уменьшить время пути; по прибытии — продать груз. Вернуть число продаж."""
    trader.journey_remaining_hours -= dt
    if trader.journey_remaining_hours > 0:
        return 0
    route = session.get(TradeRoute, trader.journey_route_id) \
        if trader.journey_route_id else None
    if route is None:
        trader.activity = "idle"
        trader.journey_remaining_hours = 0
        return 0
    dest_id = route.other_endpoint(trader.current_settlement_id)
    trader.current_settlement_id = dest_id
    trader.activity = "idle"
    trader.journey_remaining_hours = 0
    dest = session.get(Settlement, dest_id)
    _event(session, campaign.id, game_hour, "trader_arrival",
           f"{trader.name} прибыл в «{dest.name}» за {route.travel_hours} ч",
           settlement_id=dest.id, trader_id=trader.id)
    return _sell_cargo(session, campaign, cfg, trader, dest, game_hour)


def _sell_cargo(session, campaign, cfg, trader, dest, game_hour) -> int:
    """Продажа груза по прибытии: переговоры, склад, капитал.

    Возвращает число успешно проданных позиций.
    """
    sold = 0
    entries = {e.resource_id: e for e in session.query(
        SettlementInventory).filter_by(settlement_id=dest.id).all()}
    for lot in list(trader.cargo):
        if lot.quantity <= 0:
            continue
        entry = entries.get(lot.resource_id)
        if entry is None:
            # у пункта назначения нет рынка этого ресурса — продать некому
            continue
        free = entry.storage_capacity - entry.quantity
        if free <= 0:
            continue
        resource = session.get(Resource, lot.resource_id)
        sell_qty = min(lot.quantity, free)

        scarcity = _scarcity(entry)
        result = negotiate(
            entry.price_copper, trader.negotiation_skill, side="sell",
            scarcity=scarcity, max_rounds=cfg["negotiation_max_rounds"],
        )
        session.add(Negotiation(
            campaign_id=campaign.id, game_hour=game_hour, trader_id=trader.id,
            settlement_id=dest.id, resource_id=resource.id, quantity=sell_qty,
            market_price_copper=entry.price_copper,
            final_price_copper=result.agreed_price, accepted=result.accepted,
            rounds=result.rounds, history_json=json.dumps(
                result.history, ensure_ascii=False),
            reason=result.reason,
        ))
        if not result.accepted:
            _event(session, campaign.id, game_hour, "failed_trade",
                   f"{trader.name} не продал {resource.name} в «{dest.name}»: "
                   f"{result.reason}",
                   settlement_id=dest.id, resource_id=resource.id,
                   trader_id=trader.id)
            continue

        price = result.agreed_price
        total = sell_qty * price
        entry.quantity += sell_qty
        trader.capital_copper += total
        lot.quantity -= sell_qty
        if lot.quantity <= 0:
            session.delete(lot)

        tx = TradeTransaction(
            campaign_id=campaign.id, game_hour=game_hour, settlement_id=dest.id,
            trader_id=trader.id, resource_id=resource.id, kind="trade_sell",
            quantity=sell_qty, price_per_unit_copper=price, total_copper=total,
            counterparty=f"Рынок «{dest.name}»",
            description=f"Продажа {sell_qty} {resource.unit} «{resource.name}» "
                        f"по {price} CP",
        )
        session.add(tx)
        session.flush()
        _event(session, campaign.id, game_hour, "sale",
               f"{trader.name} продал {sell_qty} {resource.unit} «{resource.name}» "
               f"в «{dest.name}» по {price} CP (торг: {result.reason})",
               settlement_id=dest.id, resource_id=resource.id,
               trader_id=trader.id, amount_copper=total, transaction_id=tx.id)
        sold += 1
    return sold


def _try_local_trade(session, campaign, cfg, trader, game_hour, season) -> dict:
    """Найти лучшую сделку среди соседей и отправиться в путь.

    Возвращает счётчики для журнала симуляции.
    """
    stats = {"routes": 0, "opportunities": 0, "accepted": 0,
             "purchases": 0, "rejections": []}
    origin_id = trader.current_settlement_id
    routes = _routes_from(session, origin_id, season)
    stats["routes"] = len(routes)
    if not routes:
        _return_home(session, campaign, trader, game_hour, season)
        return stats

    origin_entries = session.query(SettlementInventory).filter_by(
        settlement_id=origin_id).all()
    origin_entries = [e for e in origin_entries if e.quantity > 0]
    cargo_free = trader.cargo_capacity - _cargo_total(trader)
    if not origin_entries or cargo_free <= 0:
        _return_home(session, campaign, trader, game_hour, season)
        return stats

    opportunities = []
    context = []  # (op, origin_entry, dest_entry, route)
    for route in routes:
        dest_id = route.other_endpoint(origin_id)
        dest_entries = {e.resource_id: e for e in session.query(
            SettlementInventory).filter_by(settlement_id=dest_id).all()}
        for origin_entry in origin_entries:
            resource_id = origin_entry.resource_id
            dest_entry = dest_entries.get(resource_id)
            if dest_entry is None:
                continue  # в пункте назначения нет рынка
            free_dest = dest_entry.storage_capacity - dest_entry.quantity
            op = evaluate_opportunity(
                route_id=route.id, resource_id=resource_id,
                buy_price=origin_entry.price_copper,
                sell_price=dest_entry.price_copper,
                capital=trader.capital_copper, cargo_free=cargo_free,
                destination_free_space=free_dest, route_capacity=route.capacity,
                transport_cost_per_unit=route.transport_cost_copper,
                risk_level=route.risk_level,
                min_profit_margin=trader.min_profit_margin,
                source_stock=origin_entry.quantity,
            )
            opportunities.append(op)
            if op.accepted:
                context.append((op, origin_entry, dest_entry, route))

    stats["opportunities"] = len(opportunities)
    stats["accepted"] = len(context)
    stats["rejections"] = [o.reason for o in opportunities if not o.accepted][:5]

    best = choose_best(opportunities)
    if best is None:
        # прибыльных сделок нет — возвращаемся домой, чтобы не застрять
        _return_home(session, campaign, trader, game_hour, season)
        return stats

    match = next(c for c in context if c[0] is best)
    op, origin_entry, dest_entry, route, = match
    resource = session.get(Resource, op.resource_id)
    origin = session.get(Settlement, origin_id)
    dest = session.get(Settlement, route.other_endpoint(origin_id))

    # переговоры о закупочной цене
    result = negotiate(
        origin_entry.price_copper, trader.negotiation_skill, side="buy",
        scarcity=_scarcity(origin_entry),
        max_rounds=cfg["negotiation_max_rounds"],
    )
    session.add(Negotiation(
        campaign_id=campaign.id, game_hour=game_hour, trader_id=trader.id,
        settlement_id=origin_id, resource_id=resource.id, quantity=op.quantity,
        market_price_copper=origin_entry.price_copper,
        final_price_copper=result.agreed_price, accepted=result.accepted,
        rounds=result.rounds, history_json=json.dumps(
            result.history, ensure_ascii=False),
        reason=result.reason,
    ))
    if not result.accepted:
        _event(session, campaign.id, game_hour, "failed_trade",
               f"{trader.name} не купил «{resource.name}» в «{origin.name}»: "
               f"{result.reason}",
               settlement_id=origin_id, resource_id=resource.id,
               trader_id=trader.id)
        _return_home(session, campaign, trader, game_hour, season)
        return stats

    price = result.agreed_price
    unit_total = price + route.transport_cost_copper
    qty = min(
        op.quantity,
        trader.capital_copper // unit_total,
        origin_entry.quantity,
        cargo_free,
        dest_entry.storage_capacity - dest_entry.quantity,
        route.capacity,
    )
    if qty <= 0:
        return stats

    total = qty * price
    transport = qty * route.transport_cost_copper
    trader.capital_copper -= total + transport
    origin_entry.quantity -= qty

    lot = _cargo_lot(session, trader.id, resource.id)
    if lot is None:
        lot = TraderCargo(trader_id=trader.id, resource_id=resource.id, quantity=qty)
        session.add(lot)
        trader.cargo.append(lot)
    else:
        lot.quantity += qty

    tx = TradeTransaction(
        campaign_id=campaign.id, game_hour=game_hour, settlement_id=origin_id,
        trader_id=trader.id, resource_id=resource.id, kind="trade_buy",
        quantity=qty, price_per_unit_copper=price, total_copper=total,
        counterparty=f"Рынок «{origin.name}»",
        description=f"Закупка {qty} {resource.unit} «{resource.name}» по {price} CP "
                    f"+ издержки {transport} CP",
    )
    session.add(tx)
    session.flush()
    _event(session, campaign.id, game_hour, "purchase",
           f"{trader.name} купил {qty} {resource.unit} «{resource.name}» "
           f"в «{origin.name}» по {price} CP (торг: {result.reason})",
           settlement_id=origin_id, resource_id=resource.id,
           trader_id=trader.id, amount_copper=total, transaction_id=tx.id)

    trader.activity = "traveling"
    trader.journey_route_id = route.id
    trader.journey_remaining_hours = route.travel_hours
    _event(session, campaign.id, game_hour, "trader_departure",
           f"{trader.name} выехал из «{origin.name}» в «{dest.name}» "
           f"на {route.travel_hours} ч (издержки {transport} CP)",
           settlement_id=origin_id, trader_id=trader.id, amount_copper=transport)
    stats["purchases"] = 1
    return stats
