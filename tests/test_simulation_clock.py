"""Тесты часов симуляции: статус, персистентность, безопасная остановка."""
import time

from app.core.config import load_config
from app.database.models import Campaign
from app.database.session import session_scope
from app.services.simulation_service import SimulationService
from app.simulation.simulation_clock import SimulationClock

CFG = load_config()


def _status(campaign_id):
    with session_scope() as s:
        c = s.get(Campaign, campaign_id)
        return c.status, c.speed, c.game_hour


def test_status_and_speed_persist(campaign_id):
    clock = SimulationClock(campaign_id, CFG)
    service = SimulationService(campaign_id, clock)
    service.set_speed(5)
    service.set_status("paused")
    # «перезапуск приложения»: новое состояние читается из БД
    status, speed, _ = _status(campaign_id)
    assert (status, speed) == ("paused", 5)
    clock.stop()


def test_running_status_writes_to_db_and_survives(campaign_id):
    clock = SimulationClock(campaign_id, CFG)
    service = SimulationService(campaign_id, clock)
    service.set_status("running")
    service.set_status("paused")
    status, _, _ = _status(campaign_id)
    assert status == "paused"  # после «перезапуска» статус остаётся paused
    clock.stop()


def test_manual_advance_blocked_while_running(campaign_id):
    from app.core.exceptions import AppError
    clock = SimulationClock(campaign_id, CFG)
    service = SimulationService(campaign_id, clock)
    service.set_status("running")
    try:
        import pytest
        with pytest.raises(AppError):
            service.advance(24)
    finally:
        service.set_status("stopped")
        clock.stop()


def test_manual_advance_when_paused(campaign_id):
    clock = SimulationClock(campaign_id, CFG)
    service = SimulationService(campaign_id, clock)
    service.set_status("paused")
    service.advance(48)
    state = service.get_state()
    assert state["game_hour"] == 48
    assert "День" in state["date"]
    clock.stop()


def test_error_status_is_visible(campaign_id):
    clock = SimulationClock(campaign_id, CFG)
    service = SimulationService(campaign_id, clock)
    service.set_status("error")
    state = service.get_state()
    assert state["status"] == "error"
    assert state["last_error"] is None
    clock.stop()


def test_clock_ticks_when_running_and_stops_safely(campaign_id):
    clock = SimulationClock(campaign_id, CFG)
    service = SimulationService(campaign_id, clock)
    # ускорим: тик каждые 0.05 с, чтобы тест не длился
    clock.cfg = {**CFG, "tick_real_seconds": 0.05}
    service.set_status("running")
    deadline = time.time() + 5
    while time.time() < deadline:
        if _status(campaign_id)[2] > 0:
            break
        time.sleep(0.05)
    assert _status(campaign_id)[2] > 0  # тик(и) реально выполнились
    service.set_status("stopped")
    clock.stop(timeout=5)
    assert not (clock._thread and clock._thread.is_alive())
    saved = _status(campaign_id)
    assert saved[0] == "stopped"
    assert saved[2] > 0  # игровое время сохранено
