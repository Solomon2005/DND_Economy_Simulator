"""Переговоры о цене: конечное число раундов, детерминировано.

Итог фиксируется: согласованная цена, число раундов, история, причина.
"""
from dataclasses import dataclass, field


@dataclass
class NegotiationResult:
    agreed_price: int
    accepted: bool
    rounds: int
    history: list = field(default_factory=list)
    reason: str = ""


def negotiate(
    market_price: int,
    skill: float,
    side: str = "buy",
    scarcity: float = 0.0,
    max_rounds: int = 5,
) -> NegotiationResult:
    """Провести торг.

    side="buy":  торговец покупает — он тянет вниз, рынок держится.
    side="sell": торговец продаёт — он тянет вверх, рынок давит вниз.
    skill (0..1): чем выше, тем ближе торгующаяся сторона к своей цели.
    scarcity (0..1): дефицит ужесточает позицию контр-стороны.
    """
    if market_price <= 0:
        return NegotiationResult(0, False, 0, [], "рыночная цена не задана")
    skill = max(0.0, min(1.0, skill))
    scarcity = max(0.0, min(1.0, scarcity))
    max_rounds = max(1, max_rounds)

    tolerance = market_price * (0.05 * (1.0 - skill) + 0.01)
    history = []

    if side == "buy":
        # стартовый оффер торговца и позиция рынка
        trader_offer = int(market_price * (1.0 - 0.15 * (0.5 + skill)))
        market_pos = int(market_price * (1.0 + 0.05 * scarcity))
        direction = 1  # торговец поднимает
    else:
        trader_offer = int(market_price * (1.0 + 0.15 * (0.5 + skill)))
        market_pos = int(market_price * (1.0 - 0.05 * (1.0 - scarcity)))
        direction = -1  # рынок опускает

    trader_offer = max(1, trader_offer)
    market_pos = max(1, market_pos)

    rounds = 0
    agreed = False
    while rounds < max_rounds:
        rounds += 1
        gap = market_pos - trader_offer if direction == 1 else trader_offer - market_pos
        if gap <= tolerance:
            agreed = True
            break
        history.append({"round": rounds, "trader_offer": trader_offer,
                        "market_pos": market_pos})
        # стороны сближаются: торговец делает шаг к рынку
        step = max(1, int(abs(gap) * (0.4 + 0.3 * skill)))
        if direction == 1:
            trader_offer = min(market_pos, trader_offer + step)
            market_pos = max(trader_offer, market_pos - max(1, int(abs(gap) * 0.25)))
        else:
            trader_offer = max(market_pos, trader_offer - step)
            market_pos = min(trader_offer, market_pos + max(1, int(abs(gap) * 0.25)))

    if agreed:
        price = (trader_offer + market_pos) // 2
        return NegotiationResult(
            agreed_price=max(1, price), accepted=True, rounds=rounds,
            history=history,
            reason=f"сделка после {rounds} раунд(ов): разница в пределах допуска",
        )

    # раунды исчерпаны: принимаем последний оффер, только если он близок к рынку
    final_gap = abs(market_pos - trader_offer)
    if final_gap <= market_price * 0.15:
        price = (trader_offer + market_pos) // 2
        return NegotiationResult(
            agreed_price=max(1, price), accepted=True, rounds=rounds,
            history=history,
            reason=f"финальное предложение принято после {rounds} раунд(ов)",
        )
    return NegotiationResult(
        agreed_price=max(1, trader_offer), accepted=False, rounds=rounds,
        history=history,
        reason=(
            f"торг сорвался: после {rounds} раунд(ов) разница "
            f"{final_gap} CP слишком велика"
        ),
    )
