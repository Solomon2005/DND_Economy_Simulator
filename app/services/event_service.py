"""Сервис журнала событий экономики."""
from app.database.models import EconomicEvent
from app.database.session import session_scope


class EventService:
    """Чтение журнала событий с фильтрацией."""

    def get_events(self, campaign_id: int, category: str | None = None,
                   settlement_id: int | None = None,
                   search: str = "", limit: int = 500) -> list[EconomicEvent]:
        with session_scope() as session:
            query = session.query(EconomicEvent).filter_by(campaign_id=campaign_id)
            if category:
                query = query.filter_by(category=category)
            if settlement_id:
                query = query.filter_by(settlement_id=settlement_id)
            rows = query.order_by(
                EconomicEvent.game_hour.desc(), EconomicEvent.id.desc()
            ).limit(limit).all()
        if search:
            # SQLite LIKE сворачивает только ASCII, поэтому кириллицу
            # фильтруем в Python после ограниченной выборки
            needle = search.casefold()
            rows = [e for e in rows if needle in e.description.casefold()]
        return rows

    def clear_events(self, campaign_id: int) -> int:
        """Удалить всю историю событий кампании. Вернуть число записей."""
        with session_scope() as session:
            deleted = session.query(EconomicEvent).filter_by(
                campaign_id=campaign_id).delete(synchronize_session=False)
        return deleted

    def get_categories(self, campaign_id: int) -> list[str]:
        with session_scope() as session:
            rows = session.query(EconomicEvent.category).filter_by(
                campaign_id=campaign_id).distinct().all()
            return sorted(r[0] for r in rows)
