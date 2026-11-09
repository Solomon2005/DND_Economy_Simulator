"""Сервис складов поселений: остатки, ставки, ручные корректировки."""
from app.core.config import load_config
from app.core.exceptions import AppError
from app.database.models import (
    Campaign,
    EconomicEvent,
    Resource,
    Settlement,
    SettlementInventory,
)
from app.database.session import session_scope


class InventoryService:
    """Сервис управления складскими позициями поселений."""

    def get_inventory(self, settlement_id: int) -> list[SettlementInventory]:
        with session_scope() as session:
            return session.query(SettlementInventory).filter_by(
                settlement_id=settlement_id
            ).order_by(SettlementInventory.id).all()

    def add_entry(self, settlement_id: int, resource_id: int,
                  price_copper: int | None = None) -> SettlementInventory:
        """Открыть позицию ресурса на складе поселения."""
        cfg = load_config()
        if price_copper is not None and price_copper <= 0:
            raise AppError("Цена должна быть положительной")
        if cfg["default_storage_capacity"] <= 0:
            raise AppError("Склад по умолчанию должен быть положительным")
        with session_scope() as session:
            settlement = session.get(Settlement, settlement_id)
            resource = session.get(Resource, resource_id)
            if settlement is None or resource is None:
                raise AppError("Поселение или ресурс не найдены")
            exists = session.query(SettlementInventory).filter_by(
                settlement_id=settlement_id, resource_id=resource_id
            ).first()
            if exists:
                raise AppError("Позиция уже есть на складе")
            entry = SettlementInventory(
                settlement_id=settlement_id,
                resource_id=resource_id,
                price_copper=price_copper if price_copper is not None
                else resource.base_price_copper,
                storage_capacity=cfg["default_storage_capacity"],
            )
            session.add(entry)
            session.flush()
            return entry

    def adjust_quantity(self, settlement_id: int, resource_id: int, delta: int,
                        reason: str = "") -> None:
        """Ручная корректировка остатка с записью в журнал событий.

        Отрицательный остаток и превышение ёмкости запрещены: иначе тик
        молча уничтожил бы товар.
        """
        with session_scope() as session:
            entry = session.query(SettlementInventory).filter_by(
                settlement_id=settlement_id, resource_id=resource_id
            ).first()
            if entry is None:
                raise AppError("Позиция не найдена на складе")
            new_qty = entry.quantity + delta
            if new_qty < 0:
                raise AppError(
                    f"Недостаточно товара: есть {entry.quantity}, запрошено {delta}"
                )
            if new_qty > entry.storage_capacity:
                raise AppError(
                    f"Недостаточно места: ёмкость {entry.storage_capacity}, "
                    f"а после правки будет {new_qty}. Увеличьте ёмкость склада."
                )
            campaign = session.get(Campaign, entry.settlement.campaign_id)
            resource = session.get(Resource, resource_id)
            entry.quantity = new_qty
            session.add(EconomicEvent(
                campaign_id=campaign.id,
                game_hour=campaign.game_hour,
                category="manual_adjustment",
                settlement_id=settlement_id,
                resource_id=resource_id,
                description=(
                    f"Ручная корректировка: {resource.name} {delta:+d} "
                    f"(осталось {new_qty}). {reason}".strip()
                ),
            ))
            session.commit()

    def update_entry(self, settlement_id: int, resource_id: int, *,
                     production_rate: int | None = None,
                     consumption_rate: int | None = None,
                     price_copper: int | None = None,
                     storage_capacity: int | None = None) -> None:
        """Изменить параметры складской позиции (ставки, цену, ёмкость)."""
        with session_scope() as session:
            entry = session.query(SettlementInventory).filter_by(
                settlement_id=settlement_id, resource_id=resource_id
            ).first()
            if entry is None:
                raise AppError("Позиция не найдена на складе")
            values = {
                "production_rate": production_rate,
                "consumption_rate": consumption_rate,
                "price_copper": price_copper,
                "storage_capacity": storage_capacity,
            }
            for field, value in values.items():
                if value is None:
                    continue
                if value < 0:
                    raise AppError("Значения не могут быть отрицательными")
                if field == "price_copper" and value <= 0:
                    raise AppError("Цена должна быть положительной")
                if field == "storage_capacity" and value < entry.quantity:
                    raise AppError(
                        f"Ёмкость не может быть меньше текущего остатка "
                        f"({entry.quantity})"
                    )
                setattr(entry, field, value)
            session.commit()

    def remove_entry(self, settlement_id: int, resource_id: int) -> None:
        with session_scope() as session:
            entry = session.query(SettlementInventory).filter_by(
                settlement_id=settlement_id, resource_id=resource_id
            ).first()
            if entry is None:
                raise AppError("Позиция не найдена на складе")
            session.delete(entry)
            session.commit()
