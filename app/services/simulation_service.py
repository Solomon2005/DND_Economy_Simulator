"""Сервис управления симуляцией: статус, скорость, ручное продвижение."""
from app.core.config import load_config
from app.core.exceptions import AppError
from app.database.models import Campaign, TradeTransaction
from app.database.session import session_scope
from app.simulation.game_calendar import format_game_date, season_for_hour
from app.simulation.simulation_clock import SimulationClock

VALID_STATUSES = ("stopped", "running", "paused", "error")
VALID_SPEEDS = (1, 2, 5, 10, 50)


class SimulationService:
    """Управление состоянием кампании и часами симуляции."""

    def __init__(self, campaign_id: int, clock: SimulationClock):
        self.campaign_id = campaign_id
        self.clock = clock

    def get_state(self) -> dict:
        with session_scope() as session:
            campaign = session.get(Campaign, self.campaign_id)
            if campaign is None:
                raise AppError("Кампания не найдена")
            return {
                "status": campaign.status,
                "speed": campaign.speed,
                "game_hour": campaign.game_hour,
                "date": format_game_date(campaign.game_hour),
                "season": season_for_hour(campaign.game_hour),
                "last_error": self.clock.last_error,
                "purchases": session.query(TradeTransaction).filter_by(
                    campaign_id=self.campaign_id, kind="trade_buy").count(),
                "sales": session.query(TradeTransaction).filter_by(
                    campaign_id=self.campaign_id, kind="trade_sell").count(),
            }

    def set_status(self, status: str) -> None:
        if status not in VALID_STATUSES:
            raise AppError(f"Неизвестный статус: {status}")
        with session_scope() as session:
            campaign = session.get(Campaign, self.campaign_id)
            campaign.status = status
        # цикл потока читает статус из БД; при запуске приложения поток стартует один раз
        if status == "running":
            self.clock.start()

    def set_speed(self, speed: int) -> None:
        if speed not in VALID_SPEEDS:
            raise AppError(f"Недопустимая скорость: {speed}x")
        with session_scope() as session:
            campaign = session.get(Campaign, self.campaign_id)
            campaign.speed = speed

    def advance(self, hours: int) -> None:
        """Вручную продвинуть игру на hours (недоступно при запущенной симуляции)."""
        if hours <= 0:
            raise AppError("Количество часов должно быть положительным")
        state = self.get_state()
        if state["status"] == "running":
            raise AppError(
                "Симуляция запущена: остановите её или используйте паузу"
            )
        if not self.clock.run_one_tick(hours=hours):
            raise AppError("Тик симуляции уже выполняется")

    def run_step(self) -> None:
        """Один ручной тик (кнопка «Шаг» на паузе)."""
        state = self.get_state()
        if state["status"] == "running":
            raise AppError("Симуляция уже запущена")
        if not self.clock.run_one_tick():
            raise AppError("Тик симуляции уже выполняется")
