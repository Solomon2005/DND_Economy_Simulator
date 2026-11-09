"""Сервис отчётов и данных для графиков (только реальные данные БД)."""
import csv
import logging
from pathlib import Path

from sqlalchemy import func

from app.core.config import DATA_DIR
from app.core.exceptions import AppError
from app.database.models import (
    EconomicEvent,
    Negotiation,
    PriceHistory,
    Resource,
    Settlement,
    TradeTransaction,
    Trader,
)
from app.database.session import session_scope

EXPORT_DIR = DATA_DIR / "exports"
logger = logging.getLogger(__name__)

# знак денежного потока поселения по типу сделки
BALANCE_SIGN = {
    "trade_buy": 1,          # торговец купил у поселения — деньги пришли
    "player_purchase": 1,    # игроки купили у поселения — деньги пришли
    "trade_sell": -1,        # торговец продал поселению — деньги ушли
    "player_sale": -1,       # игроки продали поселению — деньги ушли
}


class ReportService:
    """Агрегация данных для графиков, сводок и экспорта."""

    def price_series(self, campaign_id: int, resource_id: int,
                     settlement_id: int | None = None) -> list[dict]:
        """История цены: [{game_hour, price, settlement_id}]."""
        with session_scope() as session:
            query = session.query(PriceHistory, Settlement.name).join(
                Settlement, Settlement.id == PriceHistory.settlement_id
            ).join(
                Resource, Resource.id == PriceHistory.resource_id
            ).filter(
                Resource.campaign_id == campaign_id,
                PriceHistory.resource_id == resource_id,
            )
            if settlement_id:
                query = query.filter(PriceHistory.settlement_id == settlement_id)
            rows = query.order_by(PriceHistory.game_hour).all()
            return [
                {"game_hour": ph.game_hour, "price": ph.price_copper,
                 "settlement": name}
                for ph, name in rows
            ]

    def trade_volume_by_day(self, campaign_id: int) -> list[tuple[int, int]]:
        """Объём сделок по игровым суткам: [(день, CP)] — сумма считается в SQL."""
        day = (TradeTransaction.game_hour / 24).label("day")
        with session_scope() as session:
            rows = session.query(
                day, func.sum(TradeTransaction.total_copper)
            ).filter_by(campaign_id=campaign_id).group_by(day).order_by(day).all()
        return [(int(d), int(total or 0)) for d, total in rows]

    def settlement_balances(self, campaign_id: int) -> list[dict]:
        """Балансы поселений: продажи минус покупки по записанным сделкам."""
        with session_scope() as session:
            rows = session.query(
                TradeTransaction.settlement_id,
                TradeTransaction.kind,
                TradeTransaction.total_copper,
            ).filter_by(campaign_id=campaign_id).all()
            names = {s.id: s.name for s in session.query(Settlement).filter_by(
                campaign_id=campaign_id).all()}
        totals: dict[int, int] = {}
        for sid, kind, total in rows:
            if sid is None:
                continue
            sign = BALANCE_SIGN.get(kind)
            if sign is None:
                logger.warning("неизвестный тип сделки %s пропущен в балансе",
                               kind)
                continue
            totals[sid] = totals.get(sid, 0) + sign * total
        return [
            {"settlement": names.get(sid, "?"), "balance": total}
            for sid, total in sorted(totals.items(),
                                     key=lambda kv: -abs(kv[1]))
        ]

    def trader_profits(self, campaign_id: int) -> list[dict]:
        """Текущие капиталы торговцев (как индикатор прибыльности)."""
        with session_scope() as session:
            traders = session.query(Trader).filter_by(
                campaign_id=campaign_id).order_by(
                Trader.capital_copper.desc()).all()
            return [{"name": t.name, "capital": t.capital_copper}
                    for t in traders]

    def summary(self, campaign_id: int) -> dict:
        """Сводка для вкладки «Отчёты»."""
        with session_scope() as session:
            event_count = session.query(EconomicEvent).filter_by(
                campaign_id=campaign_id).count()
            tx_count = session.query(TradeTransaction).filter_by(
                campaign_id=campaign_id).count()
            rows = session.query(
                Resource.name, func.sum(TradeTransaction.total_copper)
            ).join(TradeTransaction,
                   TradeTransaction.resource_id == Resource.id).filter(
                Resource.campaign_id == campaign_id
            ).group_by(Resource.name).order_by(
                func.sum(TradeTransaction.total_copper).desc()).all()
        volumes = [(name, int(total or 0)) for name, total in rows]
        return {
            "event_count": event_count,
            "tx_count": tx_count,
            "top_resources": volumes[:10],
            "balances": self.settlement_balances(campaign_id),
            "traders": self.trader_profits(campaign_id),
            "volume_by_day": self.trade_volume_by_day(campaign_id),
        }

    def clear_history(self, campaign_id: int) -> dict[str, int]:
        """Удалить историю сделок, цен, переговоров и событий кампании.

        Поселения, склады, торговцы, маршруты и капиталы не меняются.
        Возвращает число удалённых записей по видам.
        """
        with session_scope() as session:
            settlement_ids = [
                sid for (sid,) in session.query(Settlement.id).filter_by(
                    campaign_id=campaign_id).all()
            ]
            counts = {
                "events": session.query(EconomicEvent).filter_by(
                    campaign_id=campaign_id).delete(synchronize_session=False),
                "negotiations": session.query(Negotiation).filter_by(
                    campaign_id=campaign_id).delete(synchronize_session=False),
                "transactions": session.query(TradeTransaction).filter_by(
                    campaign_id=campaign_id).delete(synchronize_session=False),
            }
            if settlement_ids:
                counts["prices"] = session.query(PriceHistory).filter(
                    PriceHistory.settlement_id.in_(settlement_ids)
                ).delete(synchronize_session=False)
            else:
                counts["prices"] = 0
        return counts

    def export_events_csv(self, campaign_id: int) -> Path:
        """Экспорт журнала событий в CSV (UTF-8 с BOM для Excel)."""
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = EXPORT_DIR / "events.csv"
        with session_scope() as session:
            query = session.query(EconomicEvent).filter_by(
                campaign_id=campaign_id).order_by(
                EconomicEvent.game_hour)
            if not query.first():
                raise AppError("Журнал событий пуст — экспортировать нечего")
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh, delimiter=";")
                writer.writerow(["game_hour", "category", "description",
                                 "amount_copper"])
                for e in query.yield_per(500):
                    writer.writerow([e.game_hour, e.category, e.description,
                                     e.amount_copper if e.amount_copper is not None else ""])
        return path
