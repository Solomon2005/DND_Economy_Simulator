"""Сервис управления торговцами."""
from app.core.exceptions import AppError
from app.database.models import Trader
from app.database.session import session_scope


class TraderService:
    """Сервис для управления торговцами."""

    def create_trader(self, campaign_id: int, name: str, home_settlement_id: int,
                      capital_copper: int, strategy: str = "traveling") -> Trader:
        """Создать торговца."""
        with session_scope() as session:
            if session.query(Trader).filter_by(campaign_id=campaign_id, name=name).first():
                raise AppError(f"Торговец «{name}» уже существует")
            trader = Trader(
                campaign_id=campaign_id,
                name=name,
                home_settlement_id=home_settlement_id,
                current_settlement_id=home_settlement_id,
                capital_copper=capital_copper,
                strategy=strategy,
            )
            session.add(trader)
            session.commit()
            return trader

    def get_traders(self, campaign_id: int) -> list[Trader]:
        """Получить всех торговцев кампании."""
        with session_scope() as session:
            return session.query(Trader).filter_by(campaign_id=campaign_id).all()

    def adjust_capital(self, trader_id: int, delta_copper: int,
                       reason: str = "") -> None:
        """Ручная корректировка капитала торговца с записью в журнал."""
        from app.database.models import Campaign, EconomicEvent
        with session_scope() as session:
            trader = session.get(Trader, trader_id)
            if trader is None:
                raise AppError("Торговец не найден")
            new_capital = trader.capital_copper + delta_copper
            if new_capital < 0:
                raise AppError(
                    f"Капитал не может стать отрицательным: "
                    f"есть {trader.capital_copper}, списание {delta_copper}"
                )
            campaign = session.get(Campaign, trader.campaign_id)
            trader.capital_copper = new_capital
            session.add(EconomicEvent(
                campaign_id=campaign.id, game_hour=campaign.game_hour,
                category="manual_adjustment", trader_id=trader.id,
                description=(
                    f"Капитал торговца «{trader.name}» изменён на "
                    f"{delta_copper:+d} CP → {new_capital} CP. {reason}".strip()
                ),
                amount_copper=delta_copper,
            ))
            session.commit()

    def delete_trader(self, trader_id: int) -> None:
        """Удалить торговца."""
        with session_scope() as session:
            trader = session.get(Trader, trader_id)
            if not trader:
                raise AppError("Торговец не найден")
            session.delete(trader)
            session.commit()