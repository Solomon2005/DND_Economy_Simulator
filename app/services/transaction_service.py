"""Сервис транзакций игроков и отчётов по сделкам."""
from app.core.config import load_config
from app.core.exceptions import AppError
from app.database.models import (
    Campaign,
    EconomicEvent,
    Resource,
    Settlement,
    SettlementInventory,
    TradeTransaction,
)
from app.database.session import session_scope

PLAYER_KINDS = ("player_purchase", "player_sale")


class TransactionService:
    """Запись сделок игроков с настраиваемым влиянием на экономику."""

    def record_player_transaction(
        self,
        campaign_id: int,
        settlement_id: int,
        resource_id: int,
        kind: str,
        quantity: int,
        price_per_unit_copper: int,
        counterparty: str = "",
        description: str = "",
        mode: str | None = None,
    ) -> TradeTransaction:
        """Записать сделку игроков.

        mode="full"        — склад поселения меняется (экономическое влияние);
        mode="bookkeeping"  — только запись в книгу (ручная отчётность).
        mode по умолчанию — из настроек (player_transaction_mode).
        """
        if kind not in PLAYER_KINDS:
            raise AppError("Тип сделки игроков: «покупка» или «продажа»")
        if quantity <= 0:
            raise AppError("Количество должно быть положительным")
        if price_per_unit_copper <= 0:
            raise AppError("Цена за единицу должна быть положительной")
        cfg = load_config()
        mode = mode or cfg["player_transaction_mode"]
        if mode not in ("full", "bookkeeping"):
            raise AppError(f"Неизвестный режим сделки: {mode}")

        with session_scope() as session:
            campaign = session.get(Campaign, campaign_id)
            settlement = session.get(Settlement, settlement_id)
            resource = session.get(Resource, resource_id)
            if campaign is None or settlement is None or resource is None:
                raise AppError("Кампания, поселение или ресурс не найдены")
            if settlement.campaign_id != campaign_id:
                raise AppError("Поселение не принадлежит кампании")

            entry = session.query(SettlementInventory).filter_by(
                settlement_id=settlement_id, resource_id=resource_id).first()

            if mode == "full":
                if entry is None:
                    raise AppError(
                        "Ресурса нет на складе поселения — откройте позицию "
                        "или используйте режим «только учёт»"
                    )
                if kind == "player_purchase":
                    # игроки забирают товар со склада
                    if entry.quantity < quantity:
                        raise AppError(
                            f"На складе только {entry.quantity}, "
                            f"запрошено {quantity}"
                        )
                    entry.quantity -= quantity
                else:
                    # игроки продают товар поселению — учитываем ёмкость
                    free = entry.storage_capacity - entry.quantity
                    if free < quantity:
                        raise AppError(
                            f"Свободно на складе только {free} из "
                            f"{entry.storage_capacity}"
                        )
                    entry.quantity += quantity

            total = quantity * price_per_unit_copper
            tx = TradeTransaction(
                campaign_id=campaign_id, game_hour=campaign.game_hour,
                settlement_id=settlement_id, resource_id=resource_id,
                kind=kind, quantity=quantity,
                price_per_unit_copper=price_per_unit_copper, total_copper=total,
                counterparty=counterparty, description=description,
                bookkeeping_only=(mode == "bookkeeping"),
            )
            session.add(tx)
            session.flush()

            verb = "купил" if kind == "player_purchase" else "продал"
            stock_note = " (без изменения склада: режим учёта)" \
                if mode == "bookkeeping" else ""
            session.add(EconomicEvent(
                campaign_id=campaign_id, game_hour=campaign.game_hour,
                category="player_transaction", settlement_id=settlement_id,
                resource_id=resource_id,
                description=(
                    f"Игроки {verb} {quantity} {resource.unit} «{resource.name}» "
                    f"в «{settlement.name}» по {price_per_unit_copper} CP "
                    f"(итого {total} CP). {description}{stock_note}".strip()
                ),
                amount_copper=total, transaction_id=tx.id,
            ))
            session.commit()
            return tx

    def get_transactions(self, campaign_id: int, kind: str | None = None,
                         limit: int = 500) -> list[TradeTransaction]:
        with session_scope() as session:
            query = session.query(TradeTransaction).filter_by(
                campaign_id=campaign_id)
            if kind:
                query = query.filter_by(kind=kind)
            return query.order_by(
                TradeTransaction.game_hour.desc(), TradeTransaction.id.desc()
            ).limit(limit).all()
