"""ORM-модели базы данных (SQLite + SQLAlchemy 2.0).

Денежные значения хранятся как целые медные монеты (*_copper).
Время симуляции — целое число игровых часов Campaign.game_hour.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Игровое время и управление симуляцией
    game_hour: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="stopped", nullable=False)
    # stopped | running | paused
    speed: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    settlements: Mapped[list["Settlement"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    resources: Mapped[list["Resource"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    traders: Mapped[list["Trader"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    routes: Mapped[list["TradeRoute"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["TradeTransaction"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    events: Mapped[list["EconomicEvent"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (UniqueConstraint("campaign_id", "name", name="uq_settlement_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(30), default="village", nullable=False)
    population: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # колонка есть в старых БД как NOT NULL — без неё INSERT падает
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    campaign: Mapped["Campaign"] = relationship(back_populates="settlements")
    inventories: Mapped[list["SettlementInventory"]] = relationship(
        back_populates="settlement", cascade="all, delete-orphan"
    )


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (UniqueConstraint("campaign_id", "name", name="uq_resource_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="шт", nullable=False)
    base_price_copper: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    perishable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    campaign: Mapped["Campaign"] = relationship(back_populates="resources")


class SettlementInventory(Base):
    """Склад поселения = его локальный рынок ресурса."""

    __tablename__ = "settlement_inventories"
    __table_args__ = (UniqueConstraint("settlement_id", "resource_id", name="uq_inventory"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    settlement_id: Mapped[int] = mapped_column(
        ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # колонка есть в старых БД как NOT NULL — без неё INSERT падает
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_capacity: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    production_rate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # в сутки
    consumption_rate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # в сутки
    price_copper: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    settlement: Mapped["Settlement"] = relationship(back_populates="inventories")
    resource: Mapped["Resource"] = relationship()


class TradeRoute(Base):
    """Торговый маршрут между двумя поселениями (движение в обе стороны)."""

    __tablename__ = "trade_routes"
    __table_args__ = (
        UniqueConstraint("campaign_id", "from_settlement_id", "to_settlement_id",
                         name="uq_route_direction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    from_settlement_id: Mapped[int] = mapped_column(
        ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    to_settlement_id: Mapped[int] = mapped_column(
        ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    distance: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)  # км
    travel_hours: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    transport_cost_copper: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # за единицу
    capacity: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    risk_level: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)  # 0..1
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    seasonal_restriction: Mapped[str] = mapped_column(String(100), default="", nullable=False)

    campaign: Mapped["Campaign"] = relationship(back_populates="routes")
    from_settlement: Mapped["Settlement"] = relationship(foreign_keys=[from_settlement_id])
    to_settlement: Mapped["Settlement"] = relationship(foreign_keys=[to_settlement_id])

    def other_endpoint(self, settlement_id: int) -> int:
        """Противоположный конец маршрута (маршрут двусторонний)."""
        return (self.to_settlement_id if self.from_settlement_id == settlement_id
                else self.from_settlement_id)


class Trader(Base):
    __tablename__ = "traders"
    __table_args__ = (UniqueConstraint("campaign_id", "name", name="uq_trader_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    home_settlement_id: Mapped[int] = mapped_column(
        ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    current_settlement_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlements.id", ondelete="CASCADE"), nullable=True
    )
    capital_copper: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    cargo_capacity: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    strategy: Mapped[str] = mapped_column(String(30), default="traveling", nullable=False)
    negotiation_skill: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)  # 0..1
    # колонка есть в старых БД как NOT NULL — без неё INSERT падает
    risk_tolerance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)  # 0..1
    min_profit_margin: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    activity: Mapped[str] = mapped_column(String(50), default="idle", nullable=False)
    # idle | traveling
    journey_route_id: Mapped[int | None] = mapped_column(
        ForeignKey("trade_routes.id", ondelete="SET NULL"), nullable=True
    )
    journey_remaining_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    campaign: Mapped["Campaign"] = relationship(back_populates="traders")
    home_settlement: Mapped["Settlement"] = relationship(foreign_keys=[home_settlement_id])
    current_settlement: Mapped["Settlement"] = relationship(foreign_keys=[current_settlement_id])
    cargo: Mapped[list["TraderCargo"]] = relationship(
        back_populates="trader", cascade="all, delete-orphan"
    )


class TraderCargo(Base):
    __tablename__ = "trader_cargo"
    __table_args__ = (UniqueConstraint("trader_id", "resource_id", name="uq_cargo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    trader: Mapped["Trader"] = relationship(back_populates="cargo")
    resource: Mapped["Resource"] = relationship()


class TradeTransaction(Base):
    __tablename__ = "trade_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    game_hour: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    settlement_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlements.id", ondelete="SET NULL"), nullable=True
    )
    trader_id: Mapped[int | None] = mapped_column(
        ForeignKey("traders.id", ondelete="SET NULL"), nullable=True
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # trade_buy | trade_sell | player_purchase | player_sale
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_unit_copper: Mapped[int] = mapped_column(Integer, nullable=False)
    total_copper: Mapped[int] = mapped_column(Integer, nullable=False)
    counterparty: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    bookkeeping_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    campaign: Mapped["Campaign"] = relationship(back_populates="transactions")
    settlement: Mapped["Settlement"] = relationship()
    trader: Mapped["Trader"] = relationship()
    resource: Mapped["Resource"] = relationship()


class Negotiation(Base):
    __tablename__ = "negotiations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    game_hour: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trader_id: Mapped[int | None] = mapped_column(
        ForeignKey("traders.id", ondelete="SET NULL"), nullable=True
    )
    settlement_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlements.id", ondelete="SET NULL"), nullable=True
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    market_price_copper: Mapped[int] = mapped_column(Integer, nullable=False)
    final_price_copper: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    history_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)

    trader: Mapped["Trader"] = relationship()


class EconomicEvent(Base):
    __tablename__ = "economic_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    game_hour: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    settlement_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlements.id", ondelete="SET NULL"), nullable=True
    )
    resource_id: Mapped[int | None] = mapped_column(
        ForeignKey("resources.id", ondelete="SET NULL"), nullable=True
    )
    trader_id: Mapped[int | None] = mapped_column(
        ForeignKey("traders.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    amount_copper: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("trade_transactions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    campaign: Mapped["Campaign"] = relationship(back_populates="events")
    settlement: Mapped["Settlement"] = relationship()
    resource: Mapped["Resource"] = relationship()
    trader: Mapped["Trader"] = relationship()


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    settlement_id: Mapped[int] = mapped_column(
        ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    game_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    price_copper: Mapped[int] = mapped_column(Integer, nullable=False)

    settlement: Mapped["Settlement"] = relationship()
    resource: Mapped["Resource"] = relationship()
