"""Вид «Экономическая симуляция»: управление часами и скоростью."""
import customtkinter as ctk

from app.core.exceptions import AppError
from app.services.simulation_service import SimulationService
from app.ui.components import error_message

STATUS_LABELS = {"running": "▶ запущена", "paused": "⏸ пауза",
                 "stopped": "⏹ стоп", "error": "⚠ ошибка"}
SPEEDS = (1, 2, 5, 10, 50)
POLL_MS = 1000


class SimulationView:
    """Панель управления симуляцией с опросом состояния раз в секунду."""

    def __init__(self, container, service: SimulationService):
        self.container = container
        self.service = service
        self._alive = True
        self._build()
        self._poll()

    def _build(self) -> None:
        state = ctk.CTkFrame(self.container)
        state.pack(fill="x", padx=10, pady=10)

        self.info = ctk.CTkLabel(state, text="", font=("Arial", 15), justify="left")
        self.info.pack(pady=8, anchor="w", padx=10)

        controls = ctk.CTkFrame(self.container, fg_color="transparent")
        controls.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(controls, text="▶ Старт", fg_color="#2e7d32",
                      command=lambda: self._set_status("running")).pack(
            side="left", padx=4)
        ctk.CTkButton(controls, text="⏸ Пауза",
                      command=lambda: self._set_status("paused")).pack(
            side="left", padx=4)
        ctk.CTkButton(controls, text="⏹ Стоп", fg_color="#8b2e2e",
                      command=lambda: self._set_status("stopped")).pack(
            side="left", padx=4)

        ctk.CTkLabel(controls, text="Скорость:").pack(side="left", padx=(16, 4))
        self.speed_var = ctk.StringVar(value="1x")
        speed_combo = ctk.CTkComboBox(
            controls, variable=self.speed_var, width=80, state="readonly",
            values=[f"{s}x" for s in SPEEDS], command=self._set_speed)
        speed_combo.pack(side="left", padx=4)

        manual = ctk.CTkFrame(self.container, fg_color="transparent")
        manual.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(manual, text="Ручной переход:").pack(side="left", padx=4)
        for label, hours in (("+1 час", 1), ("+1 день", 24),
                             ("+1 неделя", 168), ("+1 месяц", 720)):
            ctk.CTkButton(manual, text=label, width=90,
                          command=lambda h=hours: self._advance(h)).pack(
                side="left", padx=4)
        ctk.CTkButton(manual, text="Шаг (+6 ч)", width=90,
                      command=self._step).pack(side="left", padx=4)

        help_text = ctk.CTkLabel(
            self.container,
            text="Симуляция идёт в игровом времени: 1 тик = 6 игровых часов. "
                 "В реальном времени тик каждые 2 секунды при 1x. "
                 "Ручной переход доступен на паузе и при остановке.",
            font=("Arial", 12), fg_color="#2b2b2b", corner_radius=6,
            justify="left", wraplength=760)
        help_text.pack(fill="x", padx=10, pady=10)

    def refresh(self) -> None:
        try:
            state = self.service.get_state()
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        text = (
            f"Дата: {state['date']}    Сезон: {state['season']}\n"
            f"Статус: {STATUS_LABELS.get(state['status'], state['status'])}    "
            f"Скорость: {state['speed']}x    "
            f"Игровых часов прошло: {state['game_hour']}\n"
            f"Сделок: покупок {state['purchases']}, продаж {state['sales']}"
        )
        if state["status"] == "error" and state.get("last_error"):
            text += f"\nПоследняя ошибка: {state['last_error']}"
        self.info.configure(text=text)
        self.speed_var.set(f"{state['speed']}x")

    def _poll(self) -> None:
        if not self._alive:
            return
        self.refresh()
        try:
            self.container.after(POLL_MS, self._poll)
        except Exception:
            self._alive = False  # виджет уничтожен — тихо прекращаем опрос

    def _set_status(self, status: str) -> None:
        try:
            self.service.set_status(status)
        except AppError as exc:
            error_message(self.container, str(exc))
        self.refresh()

    def _set_speed(self, value: str) -> None:
        try:
            self.service.set_speed(int(value.rstrip("x")))
        except (AppError, ValueError) as exc:
            error_message(self.container, str(exc))
        self.refresh()

    def _advance(self, hours: int) -> None:
        try:
            self.service.advance(hours)
        except AppError as exc:
            error_message(self.container, str(exc))
        self.refresh()

    def _step(self) -> None:
        try:
            self.service.run_step()
        except AppError as exc:
            error_message(self.container, str(exc))
        self.refresh()
