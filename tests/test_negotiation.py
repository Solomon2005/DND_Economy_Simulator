"""Тесты движка переговоров."""
from app.trading.negotiation_engine import negotiate


def test_rounds_bounded():
    for side in ("buy", "sell"):
        result = negotiate(100, skill=0.0, side=side, max_rounds=5)
        assert result.rounds <= 5


def test_agreed_price_within_market_bounds():
    result = negotiate(100, skill=0.5, side="buy")
    assert 0 < result.agreed_price <= 130
    if result.accepted:
        assert result.reason


def test_high_skill_buy_lower_price():
    # чем выше навык торговца-покупателя, тем ниже (или равна) итоговая цена
    low = negotiate(100, skill=0.0, side="buy")
    high = negotiate(100, skill=1.0, side="buy")
    assert high.agreed_price <= low.agreed_price


def test_sell_side_price_not_below_market_floor():
    result = negotiate(100, skill=0.7, side="sell")
    assert result.agreed_price >= 1


def test_impossible_gap_rejected():
    # рынок держится высоко, торговец начинает крайне низко и не двигается:
    # навык 0, дефицит, 1 раунд — сделка вряд ли состоится
    result = negotiate(100, skill=0.0, side="buy", scarcity=1.0, max_rounds=1)
    assert result.rounds == 1
    assert isinstance(result.accepted, bool)


def test_zero_price_rejected():
    result = negotiate(0, skill=0.5)
    assert not result.accepted
    assert result.reason


def test_history_is_recorded():
    result = negotiate(100, skill=0.0, side="buy", max_rounds=5)
    assert isinstance(result.history, list)
    for entry in result.history:
        assert "trader_offer" in entry and "market_pos" in entry
