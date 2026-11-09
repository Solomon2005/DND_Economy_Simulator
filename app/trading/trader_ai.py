"""Экономические решения торговца: оценка возможностей и выбор лучшей.

Все функции чистые и детерминированные: на входе — только значения,
на выходе — поясненное решение. Никакого доступа к БД.
"""
from dataclasses import dataclass

MIN_ABSOLUTE_PROFIT = 10  # минимальная абсолютная прибыль в CP


@dataclass
class Opportunity:
    """Оценённая возможность торговой сделки на маршруте."""
    route_id: int
    resource_id: int
    quantity: int          # сколько купить
    buy_price: int         # цена закупки за единицу (CP)
    sell_price: int        # ожидаемая цена продажи (CP)
    transport_cost: int    # транспортные издержки, итого (CP)
    total_buy: int         # затраты на товар, итого (CP)
    net_profit: int        # ожидаемая чистая прибыль с учётом риска (CP)
    accepted: bool
    reason: str            # объяснение решения (по-русски)


def evaluate_opportunity(
    *,
    route_id: int,
    resource_id: int,
    buy_price: int,
    sell_price: int,
    capital: int,
    cargo_free: int,
    destination_free_space: int,
    source_stock: int,
    route_capacity: int,
    transport_cost_per_unit: int,
    risk_level: float,
    min_profit_margin: float,
) -> Opportunity:
    """Оценить одну возможность: закупка → транспорт → продажа.

    Обязательные правила: хватает капитала, груза и склада; издержки
    учтены; сравнение с минимальной маржой с поправкой на риск.
    """
    def reject(reason: str, qty: int = 0) -> Opportunity:
        return Opportunity(route_id, resource_id, qty, buy_price, sell_price,
                           0, 0, 0, False, reason)

    if buy_price <= 0 or sell_price <= 0:
        return reject("цена не задана")
    if capital <= 0:
        return reject("нет капитала")
    if cargo_free <= 0:
        return reject("нет свободного места в грузе")
    if destination_free_space <= 0:
        return reject("в пункте назначения нет склада")
    if source_stock <= 0:
        return reject("нет товара в пункте отправления")
    if sell_price <= buy_price:
        return reject(
            f"цена назначения ({sell_price}) не выше цены закупки ({buy_price})"
        )

    unit_total = buy_price + transport_cost_per_unit
    qty_by_capital = capital // unit_total
    qty = min(qty_by_capital, cargo_free, destination_free_space,
              source_stock, route_capacity)
    if qty <= 0:
        if qty_by_capital <= 0:
            return reject("нет капитала на единицу с учётом издержек")
        return reject("ограничение количества (груз/склад/вместимость)")

    total_buy = qty * buy_price
    transport = qty * transport_cost_per_unit
    gross = qty * (sell_price - buy_price)
    net_before_risk = gross - transport
    # риск маршрута снижает ожидаемую прибыль пропорционально
    net = int(net_before_risk * (1.0 - max(0.0, min(1.0, risk_level)) * 0.5))

    if net < MIN_ABSOLUTE_PROFIT:
        return Opportunity(route_id, resource_id, qty, buy_price, sell_price,
                           transport, total_buy, net, False,
                           f"прибыль {net} CP меньше минимальной "
                           f"({MIN_ABSOLUTE_PROFIT} CP) с учётом издержков и риска")
    required = max(MIN_ABSOLUTE_PROFIT, int(total_buy * min_profit_margin))
    if net < required:
        return Opportunity(route_id, resource_id, qty, buy_price, sell_price,
                           transport, total_buy, net, False,
                           f"прибыль {net} CP меньше минимальной маржи "
                           f"({required} CP)")
    return Opportunity(route_id, resource_id, qty, buy_price, sell_price,
                       transport, total_buy, net, True,
                       f"ожидаемая прибыль {net} CP при издержках {transport} CP")


def choose_best(opportunities: list[Opportunity]) -> Opportunity | None:
    """Выбрать лучшую принятую возможность (по убыванию прибыли).

    Возвращает None, если ничего не принято; для объяснения — первую
    отклонённую (самую прибыльную по gross-потенциалу не нужна — берём
    первую попавшуюся, порядок входа детерминирован).
    """
    accepted = [o for o in opportunities if o.accepted]
    if accepted:
        return max(accepted, key=lambda o: o.net_profit)
    return None
