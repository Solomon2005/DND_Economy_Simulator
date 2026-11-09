"""Производство и потребление: чистые функции, ограниченные складом."""


def apply_production(
    current: int, daily_rate: int, dt_hours: int, capacity: int,
    season_factor: float = 1.0,
) -> int:
    """Новый остаток после производства за dt_hours.

    Производство не превышает ёмкость склада; отрицательные ставки и
    остатки невозможны.
    """
    if current < 0 or capacity < 0:
        raise ValueError("остаток и ёмкость не могут быть отрицательными")
    if daily_rate < 0:
        raise ValueError("ставка производства не может быть отрицательной")
    made = int(daily_rate * (dt_hours / 24.0) * max(0.0, season_factor))
    # существующий запас не обрезаем, даже если он уже выше ёмкости
    return min(current + made, max(capacity, current))


def apply_consumption(
    current: int, daily_rate: int, dt_hours: int,
) -> int:
    """Новый остаток после потребления за dt_hours (не ниже нуля)."""
    if current < 0:
        raise ValueError("остаток не может быть отрицательным")
    if daily_rate < 0:
        raise ValueError("ставка потребления не может быть отрицательной")
    want = int(daily_rate * (dt_hours / 24.0))
    return max(current - want, 0)
