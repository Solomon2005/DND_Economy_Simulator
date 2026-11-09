"""Сервис управления торговыми маршрутами."""
from app.core.exceptions import AppError
from app.database.models import Settlement, TradeRoute
from app.database.session import session_scope
from app.simulation.game_calendar import season_allows


class TradeRouteService:
    """Сервис создания и управления маршрутами между поселениями."""

    def create_route(
        self,
        campaign_id: int,
        from_settlement_id: int,
        to_settlement_id: int,
        distance: float = 10.0,
        travel_hours: int = 8,
        transport_cost_copper: int = 1,
        capacity: int = 100,
        risk_level: float = 0.05,
        enabled: bool = True,
        seasonal_restriction: str = "",
    ) -> TradeRoute:
        if from_settlement_id == to_settlement_id:
            raise AppError("Маршрут должен соединять разные поселения")
        with session_scope() as session:
            for sid in (from_settlement_id, to_settlement_id):
                settlement = session.get(Settlement, sid)
                if settlement is None or settlement.campaign_id != campaign_id:
                    raise AppError("Поселение не найдено в этой кампании")
            if travel_hours <= 0:
                raise AppError("Время в пути должно быть больше нуля")
            if distance < 0 or transport_cost_copper < 0 or capacity <= 0:
                raise AppError("Расстояние, издержки и вместимость некорректны")
            if not 0 <= risk_level <= 1:
                raise AppError("Уровень риска должен быть в диапазоне 0..1")
            duplicate = session.query(TradeRoute).filter(
                TradeRoute.campaign_id == campaign_id,
                TradeRoute.from_settlement_id.in_(
                    (from_settlement_id, to_settlement_id)),
                TradeRoute.to_settlement_id.in_(
                    (from_settlement_id, to_settlement_id)),
            ).first()
            if duplicate:
                raise AppError("Такой маршрут уже существует")
            route = TradeRoute(
                campaign_id=campaign_id,
                from_settlement_id=from_settlement_id,
                to_settlement_id=to_settlement_id,
                distance=distance,
                travel_hours=travel_hours,
                transport_cost_copper=transport_cost_copper,
                capacity=capacity,
                risk_level=risk_level,
                enabled=enabled,
                seasonal_restriction=seasonal_restriction,
            )
            session.add(route)
            session.flush()
            return route

    def get_routes(self, campaign_id: int) -> list[TradeRoute]:
        with session_scope() as session:
            return session.query(TradeRoute).filter_by(campaign_id=campaign_id).all()

    def set_enabled(self, route_id: int, enabled: bool) -> None:
        with session_scope() as session:
            route = session.get(TradeRoute, route_id)
            if route is None:
                raise AppError("Маршрут не найден")
            route.enabled = enabled
            session.commit()

    def delete_route(self, route_id: int) -> None:
        with session_scope() as session:
            route = session.get(TradeRoute, route_id)
            if route is None:
                raise AppError("Маршрут не найден")
            session.delete(route)
            session.commit()

    def get_neighbors(self, settlement_id: int, season: str = "") -> list[TradeRoute]:
        """Включённые маршруты, соединяющие поселение с соседями (оба направления)."""
        with session_scope() as session:
            routes = session.query(TradeRoute).filter(
                TradeRoute.enabled.is_(True),
                (TradeRoute.from_settlement_id == settlement_id)
                | (TradeRoute.to_settlement_id == settlement_id),
            ).all()
            if season:
                routes = [r for r in routes
                          if season_allows(r.seasonal_restriction, season)]
            return routes



