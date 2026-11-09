"""Расчёт цены из спроса и предложения. Чистая функция — детерминирована."""
from app.core.exceptions import AppError


def clamp_price(price: int, base_price: int, min_factor: float, max_factor: float) -> int:
    """Ограничить цену настройками относительно базовой цены."""
    low = max(1, int(base_price * min_factor))
    high = max(low, int(base_price * max_factor))
    return max(low, min(high, int(price)))


def compute_price(
    current_price: int,
    base_price: int,
    supply: int,
    demand: int,
    price_k: float,
    min_factor: float,
    max_factor: float,
) -> int:
    """Новая цена: постепенная реакция на дисбаланс спроса и предложения.

    pressure = (demand - supply) / max(demand, supply, 1) лежит в [-1; 1],
    цена меняется не более чем на price_k за тик — без резких колебаний.
    """
    if current_price <= 0 or base_price <= 0:
        raise AppError("Цена и базовая цена должны быть положительными")
    if supply < 0 or demand < 0:
        raise AppError("Предложение и спрос не могут быть отрицательными")
    denominator = max(demand, supply, 1)
    pressure = (demand - supply) / denominator
    raw = current_price * (1.0 + price_k * pressure)
    return clamp_price(int(raw + 0.5), base_price, min_factor, max_factor)
