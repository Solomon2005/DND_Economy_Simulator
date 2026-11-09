"""Сервис управления ресурсами."""
from app.core.exceptions import AppError
from app.database.models import Resource, SettlementInventory, TraderCargo
from app.database.session import session_scope


class ResourceService:
    """Сервис для управления ресурсами."""

    def create_resource(self, campaign_id: int, name: str, category: str, unit: str, base_price_copper: int, perishable: bool = False) -> Resource:
        """Создать ресурс."""
        if base_price_copper <= 0:
            raise AppError("Базовая цена должна быть положительной")
        with session_scope() as session:
            if session.query(Resource).filter_by(campaign_id=campaign_id, name=name).first():
                raise AppError(f"Ресурс «{name}» уже существует")
            resource = Resource(
                campaign_id=campaign_id,
                name=name,
                category=category,
                unit=unit,
                base_price_copper=base_price_copper,
                perishable=perishable,
            )
            session.add(resource)
            session.commit()
            return resource

    def get_resources(self, campaign_id: int) -> list[Resource]:
        """Получить все ресурсы кампании."""
        with session_scope() as session:
            return session.query(Resource).filter_by(campaign_id=campaign_id).all()

    def update_resource(self, campaign_id: int, resource_id: int, *,
                        name: str | None = None, category: str | None = None,
                        unit: str | None = None,
                        base_price_copper: int | None = None) -> None:
        """Изменить свойства ресурса (включая базовую цену)."""
        with session_scope() as session:
            resource = session.get(Resource, resource_id)
            if resource is None or resource.campaign_id != campaign_id:
                raise AppError("Ресурс не найден")
            if name is not None:
                name = name.strip()
                if not name:
                    raise AppError("Название не может быть пустым")
                duplicate = session.query(Resource).filter(
                    Resource.campaign_id == campaign_id,
                    Resource.name == name,
                    Resource.id != resource_id,
                ).first()
                if duplicate:
                    raise AppError(f"Ресурс «{name}» уже существует")
                resource.name = name
            if category is not None:
                resource.category = category
            if unit is not None:
                resource.unit = unit
            if base_price_copper is not None:
                if base_price_copper <= 0:
                    raise AppError("Базовая цена должна быть положительной")
                resource.base_price_copper = base_price_copper
            session.commit()

    def delete_resource(self, campaign_id: int, resource_id: int) -> None:
        """Безопасно удалить ресурс: запрет, если он есть на складах или в грузе."""
        with session_scope() as session:
            resource = session.get(Resource, resource_id)
            if resource is None or resource.campaign_id != campaign_id:
                raise AppError("Ресурс не найден")
            in_use = session.query(SettlementInventory).filter_by(
                resource_id=resource_id
            ).count()
            if in_use:
                raise AppError(
                    "Нельзя удалить ресурс: он есть на складах поселений. "
                    "Сначала очистите остатки."
                )
            in_cargo = session.query(TraderCargo).filter_by(
                resource_id=resource_id
            ).count()
            if in_cargo:
                raise AppError(
                    "Нельзя удалить ресурс: он находится в грузе торговцев. "
                    "Сначала дождитесь продажи или уберите груз."
                )
            session.delete(resource)
            session.commit()