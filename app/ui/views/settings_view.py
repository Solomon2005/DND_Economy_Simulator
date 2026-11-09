"""Вид «Настройки»: параметры симуляции, режимы и тема оформления."""
import customtkinter as ctk

from app.core.config import load_config, save_config
from app.core.exceptions import AppError
from app.services.backup_service import create_backup, list_backups, restore_backup
from app.simulation.simulation_clock import SimulationClock
from app.ui.components import error_message, info_message


class SettingsView:
    """Редактирование config.json с сохранением в один клик."""

    def __init__(self, container, clock: SimulationClock):
        self.container = container
        self.clock = clock
        self._build()

    def _build(self) -> None:
        cfg = load_config()

        appearance = ctk.CTkFrame(self.container)
        appearance.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(appearance, text="Тема оформления:").pack(
            side="left", padx=10, pady=8)
        self.theme_var = ctk.StringVar(
            value="Тёмная" if cfg["theme"] == "dark" else "Светлая")
        ctk.CTkComboBox(
            appearance, variable=self.theme_var, width=130, state="readonly",
            values=["Тёмная", "Светлая"],
            command=lambda _: ctk.set_appearance_mode(
                "dark" if self.theme_var.get() == "Тёмная" else "light"),
        ).pack(side="left", padx=10, pady=8)

        form = ctk.CTkFrame(self.container)
        form.pack(fill="x", padx=10, pady=5)

        # (ключ, подпись, шаг для чисел)
        self._fields: dict[str, ctk.CTkEntry] = {}
        numeric = [
            ("price_k", "Скорость реакции цены (0.01–0.5)"),
            ("price_min_factor", "Мин. цена от базовой (доля)"),
            ("price_max_factor", "Макс. цена от базовой (доля)"),
            ("tick_game_hours", "Игровых часов в тике"),
            ("tick_real_seconds", "Реальных секунд на тик (1x)"),
            ("negotiation_max_rounds", "Макс. раундов торга"),
            ("default_storage_capacity", "Склад по умолчанию, ед."),
        ]
        for i, (key, label) in enumerate(numeric):
            ctk.CTkLabel(form, text=label).grid(row=i, column=0, padx=8,
                                                pady=4, sticky="w")
            entry = ctk.CTkEntry(form, width=110)
            entry.insert(0, str(cfg[key]))
            entry.grid(row=i, column=1, padx=8, pady=4, sticky="w")
            self._fields[key] = entry

        flags = ctk.CTkFrame(self.container, fg_color="transparent")
        flags.pack(fill="x", padx=10, pady=5)
        self._checks: dict[str, ctk.CTkCheckBox] = {}
        for key, label in (
            ("seasonal_production", "Сезонные множители производства"),
            ("record_daily_flows", "Писать производство/потребление раз в сутки"),
        ):
            check = ctk.CTkCheckBox(flags, text=label)
            if cfg[key]:
                check.select()
            check.pack(anchor="w", padx=8, pady=3)
            self._checks[key] = check

        modes = ctk.CTkFrame(self.container, fg_color="transparent")
        modes.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(modes, text="Режим сделок игроков по умолчанию:").pack(
            side="left", padx=8)
        self.mode_var = ctk.StringVar(
            value="Полное влияние" if cfg["player_transaction_mode"] == "full"
            else "Только учёт")
        ctk.CTkComboBox(
            modes, variable=self.mode_var, width=200, state="readonly",
            values=["Полное влияние", "Только учёт"],
        ).pack(side="left", padx=8)

        ctk.CTkButton(self.container, text="Сохранить настройки",
                      command=self._save).pack(padx=10, pady=(12, 4),
                                               anchor="w")

        backups = ctk.CTkFrame(self.container)
        backups.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(backups, text="Резервные копии базы данных",
                     font=("Arial", 13, "bold")).pack(
            anchor="w", padx=8, pady=(6, 2))
        row = ctk.CTkFrame(backups, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(row, text="Создать копию",
                      command=self._backup).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Восстановить последнюю",
                      fg_color="#8b6f2e",
                      command=self._restore).pack(side="left", padx=4)
        self.backups_label = ctk.CTkLabel(row, text="", font=("Arial", 12))
        self.backups_label.pack(side="left", padx=10)
        self._refresh_backups()

        ctk.CTkLabel(
            self.container,
            text="Настройки хранятся в config.json в папке проекта. "
                 "Изменения применяются сразу после сохранения.",
            font=("Arial", 12), fg_color="#2b2b2b", corner_radius=6,
            justify="left").pack(fill="x", padx=10, pady=5)

    def _refresh_backups(self) -> None:
        backups = list_backups()
        if backups:
            newest = backups[0].name
            self.backups_label.configure(
                text=f"Копий: {len(backups)}, последняя: {newest}")
        else:
            self.backups_label.configure(text="Копий пока нет")

    def _backup(self) -> None:
        try:
            path = create_backup()
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self._refresh_backups()
        info_message(self.container, f"Создана резервная копия:\n{path}")

    def _restore(self) -> None:
        backups = list_backups()
        if not backups:
            error_message(self.container, "Резервных копий нет")
            return
        try:
            restore_backup(backups[0], clock=self.clock)
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        info_message(
            self.container,
            f"База восстановлена из копии:\n{backups[0].name}")
        self._refresh_backups()

    def _save(self) -> None:
        cfg = load_config()
        try:
            for key, entry in self._fields.items():
                value = entry.get().strip()
                cfg[key] = float(value) if "." in value else int(value)
            if not 0 < cfg["price_k"] <= 1:
                raise ValueError("Скорость реакции цены: 0 < значение ≤ 1")
            if cfg["price_min_factor"] <= 0 or \
                    cfg["price_max_factor"] <= cfg["price_min_factor"]:
                raise ValueError("Границы цены: 0 < мин < макс")
            if cfg["tick_game_hours"] <= 0 or cfg["tick_real_seconds"] <= 0:
                raise ValueError("Интервалы тика должны быть положительными")
            if not 1 <= cfg["negotiation_max_rounds"] <= 20:
                raise ValueError("Раунды торга: от 1 до 20")
            if cfg["default_storage_capacity"] <= 0:
                raise ValueError("Склад по умолчанию должен быть положительным")
        except ValueError as exc:
            error_message(self.container, f"Некорректное значение: {exc}")
            return
        for key, check in self._checks.items():
            cfg[key] = bool(check.get())
        cfg["player_transaction_mode"] = (
            "full" if self.mode_var.get() == "Полное влияние"
            else "bookkeeping"
        )
        cfg["theme"] = "dark" if self.theme_var.get() == "Тёмная" else "light"
        save_config(cfg)
        # часы симуляции читают конфиг — подхватываем новые параметры
        self.clock.cfg = cfg
        info_message(self.container, "Настройки сохранены в config.json")
