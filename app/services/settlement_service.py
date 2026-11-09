"""Сервис управления поселениями."""
from app.core.exceptions import AppError
from app.database.models import Settlement, TradeRoute, Trader
from app.database.session import session_scope


class SettlementService:
    """Сервис для управления поселениями."""

    def create_settlement(self, campaign_id: int, name: str, settlement_type: str, population: int) -> Settlement:
        """Создать поселение."""
        with session_scope() as session:
            if session.query(Settlement).filter_by(campaign_id=campaign_id, name=name).first():
                raise AppError(f"Поселение «{name}» уже существует")
            settlement = Settlement(
                campaign_id=campaign_id,
                name=name,
                type=settlement_type,
                population=population,
            )
            session.add(settlement)
            session.commit()
            return settlement

    def update_settlement(self, settlement_id: int, *, name: str | None = None,
                          settlement_type: str | None = None,
                          population: int | None = None,
                          description: str | None = None) -> None:
        """Изменить свойства поселения."""
        with session_scope() as session:
            settlement = session.get(Settlement, settlement_id)
            if settlement is None:
                raise AppError("Поселение не найдено")
            if name is not None:
                name = name.strip()
                if not name:
                    raise AppError("Название не может быть пустым")
                duplicate = session.query(Settlement).filter(
                    Settlement.campaign_id == settlement.campaign_id,
                    Settlement.name == name,
                    Settlement.id != settlement_id,
                ).first()
                if duplicate:
                    raise AppError(f"Поселение «{name}» уже существует")
                settlement.name = name
            if settlement_type is not None:
                settlement.type = settlement_type
            if population is not None:
                if population < 0:
                    raise AppError("Население не может быть отрицательным")
                settlement.population = population
            if description is not None:
                settlement.description = description
            session.commit()

    def get_settlements(self, campaign_id: int) -> list[Settlement]:
        """Получить все поселения кампании."""
        with session_scope() as session:
            return session.query(Settlement).filter_by(campaign_id=campaign_id).all()

    def delete_settlement(self, settlement_id: int) -> None:
        """Удалить поселение и связанные данные (с защитой торговцев)."""
        with session_scope() as session:
            settlement = session.get(Settlement, settlement_id)
            if not settlement:
                raise AppError("Поселение не найдено")
            traders = session.query(Trader).filter(
                (Trader.home_settlement_id == settlement_id)
                | (Trader.current_settlement_id == settlement_id)
            ).count()
            if traders:
                raise AppError(
                    "Нельзя удалить поселение: к нему привязаны торговцы. "
                    "Сначала удалите или перенесите торговцев."
                )
            # Удаление связанных маршрутов
            session.query(TradeRoute).filter(
                (TradeRoute.from_settlement_id == settlement_id) |
                (TradeRoute.to_settlement_id == settlement_id)
            ).delete()
            session.delete(settlement)
            session.commit()
