"""Тесты производства и потребления."""
import pytest

from app.economy.market_engine import apply_consumption, apply_production


def test_production_adds_proportional_to_time():
    assert apply_production(100, daily_rate=24, dt_hours=12, capacity=1000) == 112


def test_production_respects_capacity():
    assert apply_production(99, daily_rate=24, dt_hours=24, capacity=100) == 100


def test_production_seasonal_factor():
    winter = apply_production(0, 20, 24, 1000, season_factor=0.7)
    summer = apply_production(0, 20, 24, 1000, season_factor=1.1)
    assert winter == 14
    assert summer == 22


def test_production_rejects_invalid():
    with pytest.raises(ValueError):
        apply_production(-1, 10, 24, 100)
    with pytest.raises(ValueError):
        apply_production(10, -5, 24, 100)


def test_consumption_never_negative():
    assert apply_consumption(5, daily_rate=24, dt_hours=24) == 0
    assert apply_consumption(100, daily_rate=24, dt_hours=24) == 76


def test_consumption_partial_time():
    assert apply_consumption(50, daily_rate=10, dt_hours=12) == 45


def test_consumption_rejects_invalid():
    with pytest.raises(ValueError):
        apply_consumption(-5, 10, 24)
    with pytest.raises(ValueError):
        apply_consumption(10, -1, 24)
