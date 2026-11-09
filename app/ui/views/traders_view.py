"""Вид управления торговцами."""
import customtkinter as ctk

from app.core.exceptions import AppError
from app.economy.currency import format_copper, parse_money
from app.services.settlement_service import SettlementService
from app.services.trader_service import TraderService
from app.ui.components import ask_string, error_message, info_message, make_treeview


class TradersView:
    """Вид управления торговцами кампании."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self.service = TraderService()
        self._settlements = SettlementService()
        self._build()

    def _build(self) -> None:
        form = ctk.CTkFrame(self.container)
        form.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(form, text="Имя:").grid(row=0, column=0, padx=5, pady=5)
        self.name_entry = ctk.CTkEntry(form, width=170)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(form, text="Дом:").grid(row=0, column=2, padx=5, pady=5)
        self.home_combo = ctk.CTkComboBox(form, width=170, state="readonly")
        self.home_combo.grid(row=0, column=3, padx=5, pady=5)

        ctk.CTkLabel(form, text="Капитал:").grid(row=0, column=4, padx=5, pady=5)
        self.capital_entry = ctk.CTkEntry(form, width=110)
        self.capital_entry.insert(0, "100 gp")
        self.capital_entry.grid(row=0, column=5, padx=5, pady=5)

        ctk.CTkButton(form, text="Создать", command=self._create).grid(row=0, column=6, padx=5, pady=5)
        ctk.CTkButton(form, text="Капитал ±", command=self._adjust_capital).grid(
            row=0, column=7, padx=5, pady=5)
        ctk.CTkButton(form, text="Удалить выбранный", fg_color="#8b2e2e",
                      command=self._delete).grid(row=0, column=8, padx=5, pady=5)

        self.tree = make_treeview(self.container, [
            ("name", "Имя", 170),
            ("home", "Дом", 150),
            ("where", "Где", 150),
            ("capital", "Капитал", 120),
            ("activity", "Статус", 110),
        ])
        self.refresh()

    def refresh(self) -> None:
        settlements = self._settlements.get_settlements(self.campaign_id)
        by_id = {s.id: s.name for s in settlements}
        self.home_combo.configure(values=[s.name for s in settlements])
        if settlements and self.home_combo.get() not in by_id.values():
            self.home_combo.set(settlements[0].name)

        self.tree.delete(*self.tree.get_children())
        for t in self.service.get_traders(self.campaign_id):
            where = (
                "в пути" if t.activity == "traveling"
                else by_id.get(t.current_settlement_id, "—")
            )
            self.tree.insert(
                "", "end", iid=str(t.id), text=t.name,
                values=(
                    by_id.get(t.home_settlement_id, "—"),
                    where,
                    format_copper(t.capital_copper),
                    "в пути" if t.activity == "traveling" else "на месте",
                ),
            )

    def _create(self) -> None:
        name = self.name_entry.get().strip()
        if not name:
            error_message(self.container, "Введите имя торговца")
            return
        settlements = self._settlements.get_settlements(self.campaign_id)
        home = next((s for s in settlements if s.name == self.home_combo.get()), None)
        if home is None:
            error_message(self.container, "Сначала создайте поселение")
            return
        try:
            capital = parse_money(self.capital_entry.get())
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        if capital <= 0:
            error_message(self.container, "Капитал должен быть положительным")
            return
        strategy = "traveling"  # стратегия не влияет на движок — выбор убран из UI
        try:
            self.service.create_trader(self.campaign_id, name, home.id, capital, strategy)
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.name_entry.delete(0, "end")
        self.refresh()

    def _adjust_capital(self) -> None:
        selection = self.tree.selection()
        if not selection:
            error_message(self.container, "Выберите торговца в таблице")
            return
        value = ask_string(
            self.container, "Капитал торговца",
            "Изменение капитала в CP\n(напр. 500 или -200):")
        if value is None:
            return
        try:
            delta = int(value.strip())
        except ValueError:
            error_message(self.container, "Нужно целое число медных монет")
            return
        if delta == 0:
            return
        try:
            self.service.adjust_capital(int(selection[0]), delta,
                                        reason="вручную из интерфейса")
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()

    def _delete(self) -> None:
        selection = self.tree.selection()
        if not selection:
            error_message(self.container, "Выберите торговца в таблице")
            return
        try:
            self.service.delete_trader(int(selection[0]))
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()
        info_message(self.container, "Торговец удалён")
