"""Тесты расчёта цен: реакция на спрос/предложение, границы, детерминизм."""
import pytest

from app.core.exceptions import AppError
from app.economy.price_engine import clamp_price, compute_price


def test_price_grows_when_demand_exceeds_supply():
    new = compute_price(100, 100, supply=10, demand=100, price_k=0.1,
                        min_factor=0.5, max_factor=3.0)
    assert new > 100


def test_price_falls_when_supply_exceeds_demand():
    new = compute_price(100, 100, supply=100, demand=10, price_k=0.1,
                        min_factor=0.5, max_factor=3.0)
    assert new < 100


def test_price_change_is_gradual():
    new = compute_price(100, 100, supply=0, demand=1000, price_k=0.05,
                        min_factor=0.5, max_factor=3.0)
    assert new <= 105  # не более чем на price_k за тик


def test_price_clamped_to_bounds():
    low = compute_price(51, 100, supply=1000, demand=0, price_k=1.0,
                        min_factor=0.5, max_factor=3.0)
    high = compute_price(299, 100, supply=0, demand=1000, price_k=1.0,
                         min_factor=0.5, max_factor=3.0)
    assert low == 50
    assert high == 300


def test_clamp_price_min_at_least_one():
    assert clamp_price(0, 10, min_factor=0.001, max_factor=3.0) == 1


def test_deterministic():
    args = dict(current_price=123, base_price=100, supply=40, demand=70,
                price_k=0.06, min_factor=0.5, max_factor=3.0)
    assert compute_price(**args) == compute_price(**args)


def test_invalid_inputs():
    with pytest.raises(AppError):
        compute_price(0, 100, 1, 1, 0.1, 0.5, 3.0)
    with pytest.raises(AppError):
        compute_price(100, 100, -1, 1, 0.1, 0.5, 3.0)
