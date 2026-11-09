"""Сервисы приложения и общие функции."""
from app.database.models import Campaign
from app.database.session import init_db, session_scope


def get_or_create_campaign(name: str = "Основная кампания") -> int:
    """Вернуть id единственной кампании, создав её при первом запуске."""
    init_db()  # каталоги и таблицы создаются один раз, дальше — no-op
    with session_scope() as session:
        campaign = session.query(Campaign).first()
        if campaign is None:
            campaign = Campaign(name=name)
            session.add(campaign)
            session.flush()
        campaign_id = campaign.id
    # пустая кампания получает демо-мир, чтобы симуляция сразу работала
    from app.database.seed import seed_demo_world
    seed_demo_world(campaign_id)
    return campaign_id
