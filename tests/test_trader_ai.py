"""Тесты решений торговца (trader_ai)."""
from app.trading.trader_ai import (
    MIN_ABSOLUTE_PROFIT,
    Opportunity,
    choose_best,
    evaluate_opportunity,
)

GOOD = dict(
    route_id=1, resource_id=1, buy_price=50, sell_price=80,
    capital=10000, cargo_free=50, destination_free_space=100,
    source_stock=200, route_capacity=100, transport_cost_per_unit=2,
    risk_level=0.05, min_profit_margin=0.15,
)


def test_profitable_trade_accepted():
    op = evaluate_opportunity(**GOOD)
    assert op.accepted
    # количество ограничено грузом/складом/капиталом/вместимостью
    assert 0 < op.quantity <= 50
    assert op.net_profit >= MIN_ABSOLUTE_PROFIT
    assert "прибыль" in op.reason


def test_insufficient_capital_rejected():
    op = evaluate_opportunity(**{**GOOD, "capital": 10})  # меньше цены единицы
    assert not op.accepted
    assert "капитал" in op.reason


def test_no_cargo_space_rejected():
    op = evaluate_opportunity(**{**GOOD, "cargo_free": 0})
    assert not op.accepted
    assert "груз" in op.reason


def test_no_destination_stock_rejected():
    op = evaluate_opportunity(**{**GOOD, "destination_free_space": 0})
    assert not op.accepted
    assert "склада" in op.reason


def test_unprofitable_rejected():
    # цена назначения ниже закупки
    op = evaluate_opportunity(**{**GOOD, "sell_price": 40})
    assert not op.accepted


def test_transport_costs_kill_margin():
    # издержки съедают всю разницу цен
    op = evaluate_opportunity(**{**GOOD, "transport_cost_per_unit": 30})
    assert not op.accepted
    assert "издержк" in op.reason or "прибыль" in op.reason


def test_risk_reduces_profit():
    safe = evaluate_opportunity(**{**GOOD, "risk_level": 0.0})
    risky = evaluate_opportunity(**{**GOOD, "risk_level": 1.0})
    assert risky.net_profit < safe.net_profit


def test_min_margin_enforced():
    # маржа 0.15 при затратах qty*52 требует ≥ 7.8% — ограничение
    # достигается высокой маржой
    op = evaluate_opportunity(**{**GOOD, "min_profit_margin": 10.0})
    assert not op.accepted
    assert "маржи" in op.reason


def test_zero_demand_equivalent_no_space():
    op = evaluate_opportunity(**{**GOOD, "destination_free_space": 0})
    assert not op.accepted


def test_choose_best_prefers_higher_profit():
    a = Opportunity(1, 1, 10, 50, 60, 5, 500, 50, True, "ок")
    b = Opportunity(2, 1, 10, 50, 90, 5, 500, 350, True, "ок")
    assert choose_best([a, b]).route_id == 2


def test_choose_best_returns_none_when_all_rejected():
    rejected = evaluate_opportunity(**{**GOOD, "sell_price": 10})
    assert choose_best([rejected]) is None
