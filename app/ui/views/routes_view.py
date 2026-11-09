"""Вид управления торговыми маршрутами."""
import customtkinter as ctk

from app.core.exceptions import AppError
from app.economy.currency import format_copper
from app.services.settlement_service import SettlementService
from app.services.trade_route_service import TradeRouteService
from app.ui.components import error_message, info_message, make_treeview


class RoutesView:
    """Вид создания и управления маршрутами."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self.service = TradeRouteService()
        self._settlements = SettlementService()
        self._build()

    def _build(self) -> None:
        form = ctk.CTkFrame(self.container)
        form.pack(fill="x", padx=5, pady=5)

        row1 = ctk.CTkFrame(form, fg_color="transparent")
        row1.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(row1, text="Поселение 1:").pack(side="left", padx=5)
        self.from_combo = ctk.CTkComboBox(row1, width=160, state="readonly")
        self.from_combo.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="Поселение 2:").pack(side="left", padx=5)
        self.to_combo = ctk.CTkComboBox(row1, width=160, state="readonly")
        self.to_combo.pack(side="left", padx=5)
        self._reload_settlements()
        ctk.CTkLabel(row1, text="Расстояние, км:").pack(side="left", padx=5)
        self.distance_entry = ctk.CTkEntry(row1, width=70)
        self.distance_entry.insert(0, "20")
        self.distance_entry.pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="Часов в пути:").pack(side="left", padx=5)
        self.hours_entry = ctk.CTkEntry(row1, width=60)
        self.hours_entry.insert(0, "12")
        self.hours_entry.pack(side="left", padx=5)

        row2 = ctk.CTkFrame(form, fg_color="transparent")
        row2.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(row2, text="Издержки за ед., CP:").pack(side="left", padx=5)
        self.cost_entry = ctk.CTkEntry(row2, width=70)
        self.cost_entry.insert(0, "2")
        self.cost_entry.pack(side="left", padx=5)
        ctk.CTkLabel(row2, text="Вместимость:").pack(side="left", padx=5)
        self.capacity_entry = ctk.CTkEntry(row2, width=70)
        self.capacity_entry.insert(0, "100")
        self.capacity_entry.pack(side="left", padx=5)
        ctk.CTkLabel(row2, text="Риск (0..1):").pack(side="left", padx=5)
        self.risk_entry = ctk.CTkEntry(row2, width=60)
        self.risk_entry.insert(0, "0.05")
        self.risk_entry.pack(side="left", padx=5)
        ctk.CTkLabel(row2, text="Сезон (напр. winter):").pack(side="left", padx=5)
        self.season_entry = ctk.CTkEntry(row2, width=110)
        self.season_entry.pack(side="left", padx=5)
        ctk.CTkButton(row2, text="Создать", command=self._create).pack(side="left", padx=5)

        actions = ctk.CTkFrame(self.container, fg_color="transparent")
        actions.pack(fill="x", padx=5, pady=2)
        ctk.CTkButton(actions, text="Вкл/выкл выбранный",
                      command=self._toggle).pack(side="left", padx=5)
        ctk.CTkButton(actions, text="Удалить выбранный", fg_color="#8b2e2e",
                      command=self._delete).pack(side="left", padx=5)

        self.tree = make_treeview(self.container, [
            ("route", "Маршрут", 260),
            ("distance", "Км", 60),
            ("hours", "Часов", 70),
            ("cost", "Издержки/ед.", 110),
            ("capacity", "Вместимость", 100),
            ("risk", "Риск", 60),
            ("status", "Статус", 110),
            ("season", "Сезон", 100),
        ])
        self.refresh()

    def _reload_settlements(self) -> None:
        """Перечитать поселения: новые сразу доступны в обоих списках."""
        settlements = self._settlements.get_settlements(self.campaign_id)
        self._by_name = {s.name: s.id for s in settlements}
        names = list(self._by_name)
        for combo in (self.from_combo, self.to_combo):
            combo.configure(values=names)
            if names and combo.get() not in self._by_name:
                combo.set(names[0])

    def refresh(self) -> None:
        self._reload_settlements()
        settlements = {s.id: s.name
                       for s in self._settlements.get_settlements(self.campaign_id)}
        self.tree.delete(*self.tree.get_children())
        for r in self.service.get_routes(self.campaign_id):
            self.tree.insert(
                "", "end", iid=str(r.id),
                text=f"{settlements.get(r.from_settlement_id, '—')} ↔ "
                     f"{settlements.get(r.to_settlement_id, '—')}",
                values=(
                    r.distance, r.travel_hours,
                    format_copper(r.transport_cost_copper),
                    r.capacity, f"{r.risk_level:.2f}",
                    "включён" if r.enabled else "выключен",
                    r.seasonal_restriction or "—",
                ),
            )

    def _create(self) -> None:
        try:
            from_id = self._by_name[self.from_combo.get()]
            to_id = self._by_name[self.to_combo.get()]
            self.service.create_route(
                self.campaign_id, from_id, to_id,
                distance=float(self.distance_entry.get()),
                travel_hours=int(self.hours_entry.get()),
                transport_cost_copper=int(self.cost_entry.get()),
                capacity=int(self.capacity_entry.get()),
                risk_level=float(self.risk_entry.get()),
                seasonal_restriction=self.season_entry.get().strip(),
            )
        except (AppError, ValueError) as exc:
            error_message(self.container, f"Не удалось создать маршрут: {exc}")
            return
        self.refresh()
        info_message(self.container, "Маршрут создан")

    def _selected_id(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            error_message(self.container, "Выберите маршрут в таблице")
            return None
        return int(selection[0])

    def _toggle(self) -> None:
        route_id = self._selected_id()
        if route_id is None:
            return
        routes = {r.id: r for r in self.service.get_routes(self.campaign_id)}
        self.service.set_enabled(route_id, not routes[route_id].enabled)
        self.refresh()

    def _delete(self) -> None:
        route_id = self._selected_id()
        if route_id is None:
            return
        try:
            self.service.delete_route(route_id)
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()
