"""Игровые часы: фоновый поток выполнения тиков симуляции.

Игровое время отделено от реального: реальный интервал тика
= tick_real_seconds / speed. Тики выполняются строго под одним замком,
поэтому дубликаты исключены. GUI часы не блокируют.
"""
import logging
import threading

from sqlalchemy import select

from app.core.config import load_config
from app.database import session as db_session
from app.database.models import Campaign
from app.database.session import session_scope
from app.simulation.simulation_engine import run_tick

logger = logging.getLogger("app.simulation")


class SimulationClock:
    """Фоновый исполнитель тиков для одной кампании."""

    def __init__(self, campaign_id: int, cfg: dict | None = None):
        self.campaign_id = campaign_id
        self.cfg = cfg or load_config()
        self.last_error: str | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._tick_lock = threading.Lock()

    # --- управление потоком -------------------------------------------
    def start(self) -> None:
        """Запустить цикл (идемпотентно). Поток сам читает статус из БД."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="simulation-clock")
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Остановить цикл и дождаться завершения (безопасное завершение)."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None

    # --- внутреннее ----------------------------------------------------
    def _read_state(self) -> tuple[str, int]:
        # ссылка через модуль: единая точка подмены фабрики (тесты, миграции)
        session = db_session.SessionLocal()
        try:
            row = session.execute(
                select(Campaign.status, Campaign.speed).where(
                    Campaign.id == self.campaign_id)
            ).first()
            return (row[0], row[1]) if row else ("stopped", 1)
        finally:
            session.close()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                status, speed = self._read_state()
            except Exception:
                logger.exception("не удалось прочитать статус симуляции")
                status, speed = "stopped", 1
            if status == "running":
                try:
                    self.run_one_tick()
                    delay = self.cfg["tick_real_seconds"] / max(1, speed)
                except Exception as exc:
                    # не даём потоку умереть молча: ошибка видна в UI и в логе
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    logger.exception("ошибка тика симуляции")
                    self._set_error_status()
                    delay = 0.25
            else:
                delay = 0.25
            self._stop_event.wait(delay)

    def _set_error_status(self) -> None:
        """Перевести кампанию в статус error, чтобы ошибка была видна в GUI."""
        try:
            with session_scope() as session:
                campaign = session.get(Campaign, self.campaign_id)
                if campaign is not None:
                    campaign.status = "error"
        except Exception:
            logger.exception("не удалось записать статус error")

    def run_one_tick(self, hours: int | None = None) -> bool:
        """Выполнить один тик; False, если тик уже идёт (защита от дублей)."""
        if not self._tick_lock.acquire(blocking=False):
            return False
        try:
            with session_scope() as session:
                run_tick(session, self.campaign_id, self.cfg, hours=hours)
            return True
        finally:
            self._tick_lock.release()
