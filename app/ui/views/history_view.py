"""Вид «История событий»: журнал экономики с фильтрами."""
import customtkinter as ctk

from app.services.event_service import EventService
from app.services.settlement_service import SettlementService
from app.simulation.game_calendar import format_game_date
from app.ui.components import make_treeview

CATEGORY_LABELS = {
    "production": "Производство",
    "consumption": "Потребление",
    "purchase": "Закупка",
    "sale": "Продажа",
    "negotiation": "Переговоры",
    "failed_trade": "Сбой сделки",
    "trader_departure": "Выезд торговца",
    "trader_arrival": "Прибытие торговца",
    "price_change": "Изменение цены",
    "player_transaction": "Сделка игроков",
    "manual_adjustment": "Ручная правка",
    "economic_event": "Экономическое событие",
}


class HistoryView:
    """Журнал событий с фильтрами по категории, поселению и тексту."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self.service = EventService()
        self._settlements = SettlementService()
        self._build()

    def _build(self) -> None:
        filters = ctk.CTkFrame(self.container, fg_color="transparent")
        filters.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(filters, text="Категория:").pack(side="left", padx=5)
        self.category_var = ctk.StringVar(value="все")
        self.category_combo = ctk.CTkComboBox(
            filters, variable=self.category_var, width=170, state="readonly",
            values=["все"], command=lambda _: self.refresh())
        self.category_combo.pack(side="left", padx=5)

        ctk.CTkLabel(filters, text="Поселение:").pack(side="left", padx=5)
        self.settlement_var = ctk.StringVar(value="все")
        self.settlement_combo = ctk.CTkComboBox(
            filters, variable=self.settlement_var, width=160, state="readonly",
            values=["все"], command=lambda _: self.refresh())
        self.settlement_combo.pack(side="left", padx=5)

        ctk.CTkLabel(filters, text="Поиск:").pack(side="left", padx=5)
        self.search_entry = ctk.CTkEntry(filters, width=220)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<Return>", lambda _: self.refresh())
        ctk.CTkButton(filters, text="Найти",
                      command=self.refresh).pack(side="left", padx=5)
        ctk.CTkButton(filters, text="Сбросить историю", fg_color="#8e3b3b",
                      hover_color="#6d2d2d",
                      command=self._reset_history).pack(side="right", padx=5)

        self.tree = make_treeview(self.container, [
            ("date", "Дата", 170),
            ("category", "Категория", 140),
            ("settlement", "Поселение", 130),
            ("trader", "Торговец", 140),
            ("description", "Описание", 500),
        ])
        self.refresh()

    def _reset_history(self) -> None:
        from tkinter import messagebox
        if not messagebox.askyesno(
                "Сброс истории",
                "Удалить все записи журнала? Действие необратимо.",
                parent=self.container):
            return
        self.service.clear_events(self.campaign_id)
        self.refresh()

    def refresh(self) -> None:
        # обновить списки фильтров (могли появиться новые записи)
        settlements = self._settlements.get_settlements(self.campaign_id)
        s_names = ["все"] + [s.name for s in settlements]
        if s_names != self.settlement_combo.cget("values"):
            self.settlement_combo.configure(values=s_names)
        self._settlement_by_name = {s.name: s.id for s in settlements}

        categories = ["все"] + [
            CATEGORY_LABELS.get(c, c)
            for c in self.service.get_categories(self.campaign_id)
        ]
        if categories != self.category_combo.cget("values"):
            self.category_combo.configure(values=categories)

        category_key = next(
            (k for k, v in CATEGORY_LABELS.items()
             if v == self.category_var.get()), None)
        settlement_id = self._settlement_by_name.get(self.settlement_var.get())

        events = self.service.get_events(
            self.campaign_id,
            category=category_key,
            settlement_id=settlement_id,
            search=self.search_entry.get().strip(),
        )

        settlement_names = {s.id: s.name for s in settlements}
        trader_names = {}
        from app.services.trader_service import TraderService
        for t in TraderService().get_traders(self.campaign_id):
            trader_names[t.id] = t.name

        self.tree.delete(*self.tree.get_children())
        for e in events:
            self.tree.insert(
                "", "end", iid=str(e.id),
                text=format_game_date(e.game_hour),
                values=(
                    CATEGORY_LABELS.get(e.category, e.category),
                    settlement_names.get(e.settlement_id, "—"),
                    trader_names.get(e.trader_id, "—"),
                    e.description,
                ),
            )
