"""Вид складов поселения: остатки, ставки, ручные корректировки."""
import customtkinter as ctk

from app.core.exceptions import AppError
from app.economy.currency import format_copper, parse_money
from app.services.inventory_service import InventoryService
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService
from app.ui.components import error_message, info_message, make_treeview


class InventoryView:
    """Вид управления складом выбранного поселения."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self.service = InventoryService()
        self._settlements = SettlementService()
        self._resources = ResourceService()
        self._build()

    def _build(self) -> None:
        top = ctk.CTkFrame(self.container, fg_color="transparent")
        top.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(top, text="Поселение:").pack(side="left", padx=5)
        self.settlement_combo = ctk.CTkComboBox(top, width=180, state="readonly",
                                                command=lambda _: self.refresh())
        self.settlement_combo.pack(side="left", padx=5)

        ctk.CTkLabel(top, text="Ресурс:").pack(side="left", padx=5)
        self.resource_combo = ctk.CTkComboBox(top, width=160, state="readonly")
        self.resource_combo.pack(side="left", padx=5)
        ctk.CTkButton(top, text="Добавить на склад",
                      command=self._add_entry).pack(side="left", padx=5)

        form = ctk.CTkFrame(self.container)
        form.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(form, text="Произв./сут:").grid(row=0, column=0, padx=5, pady=5)
        self.prod_entry = ctk.CTkEntry(form, width=70)
        self.prod_entry.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(form, text="Потребл./сут:").grid(row=0, column=2, padx=5, pady=5)
        self.cons_entry = ctk.CTkEntry(form, width=70)
        self.cons_entry.grid(row=0, column=3, padx=5, pady=5)
        ctk.CTkLabel(form, text="Цена:").grid(row=0, column=4, padx=5, pady=5)
        self.price_entry = ctk.CTkEntry(form, width=100)
        self.price_entry.grid(row=0, column=5, padx=5, pady=5)
        ctk.CTkLabel(form, text="Склад, ед.:").grid(row=0, column=6, padx=5, pady=5)
        self.capacity_entry = ctk.CTkEntry(form, width=80)
        self.capacity_entry.grid(row=0, column=7, padx=5, pady=5)
        ctk.CTkButton(form, text="Применить к выбранной",
                      command=self._apply_params).grid(row=0, column=8, padx=5, pady=5)

        row2 = ctk.CTkFrame(self.container, fg_color="transparent")
        row2.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(row2, text="Корректировка (+/-):").pack(side="left", padx=5)
        self.delta_entry = ctk.CTkEntry(row2, width=80)
        self.delta_entry.pack(side="left", padx=5)
        ctk.CTkButton(row2, text="Скорректировать",
                      command=self._adjust).pack(side="left", padx=5)
        ctk.CTkButton(row2, text="Снять позицию", fg_color="#8b2e2e",
                      command=self._remove_entry).pack(side="left", padx=5)

        self.tree = make_treeview(self.container, [
            ("resource", "Ресурс", 180),
            ("settlement", "Поселение", 150),
            ("quantity", "Остаток", 90),
            ("capacity", "Склад", 90),
            ("prod", "Произв./сут", 110),
            ("cons", "Потребл./сут", 110),
            ("price", "Цена", 130),
        ])
        self.refresh()

    def _selected_settlement_id(self) -> int | None:
        return self._settlement_by_name.get(self.settlement_combo.get())

    def _reload_combos(self) -> None:
        settlements = self._settlements.get_settlements(self.campaign_id)
        self._settlement_by_name = {s.name: s.id for s in settlements}
        self.settlement_combo.configure(values=[s.name for s in settlements])
        if settlements and self.settlement_combo.get() not in self._settlement_by_name:
            self.settlement_combo.set(settlements[0].name)
        resources = self._resources.get_resources(self.campaign_id)
        self._resource_by_name = {r.name: r.id for r in resources}
        self.resource_combo.configure(values=[r.name for r in resources])
        if resources and self.resource_combo.get() not in self._resource_by_name:
            self.resource_combo.set(resources[0].name)

    def refresh(self) -> None:
        self._reload_combos()
        self.tree.delete(*self.tree.get_children())
        resource_names = {r.id: r.name
                          for r in self._resources.get_resources(self.campaign_id)}
        # запрос на поселение: поселений в кампании немного
        for settlement in self._settlements.get_settlements(self.campaign_id):
            for e in self.service.get_inventory(settlement.id):
                self.tree.insert(
                    "", "end", iid=f"{settlement.id}:{e.resource_id}",
                    text=resource_names.get(e.resource_id, "—"),
                    values=(settlement.name, e.quantity, e.storage_capacity,
                            e.production_rate, e.consumption_rate,
                            format_copper(e.price_copper)),
                )

    def _add_entry(self) -> None:
        settlement_id = self._selected_settlement_id()
        resource_id = self._resource_by_name.get(self.resource_combo.get())
        if settlement_id is None or resource_id is None:
            error_message(self.container, "Выберите поселение и ресурс")
            return
        try:
            self.service.add_entry(settlement_id, resource_id)
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()

    def _selected_entry(self) -> tuple[int, int] | None:
        selection = self.tree.selection()
        if not selection:
            error_message(self.container, "Выберите позицию в таблице")
            return None
        settlement_id, resource_id = selection[0].split(":", 1)
        return int(settlement_id), int(resource_id)

    def _apply_params(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        settlement_id, resource_id = entry
        try:
            price = parse_money(self.price_entry.get()) if self.price_entry.get() else None
            self.service.update_entry(
                settlement_id, resource_id,
                production_rate=int(self.prod_entry.get()),
                consumption_rate=int(self.cons_entry.get()),
                price_copper=price,
                storage_capacity=int(self.capacity_entry.get()),
            )
        except (AppError, ValueError) as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()
        info_message(self.container, "Параметры склада обновлены")

    def _adjust(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        settlement_id, resource_id = entry
        try:
            delta = int(self.delta_entry.get())
        except ValueError:
            error_message(self.container, "Корректировка должна быть целым числом")
            return
        try:
            self.service.adjust_quantity(settlement_id, resource_id, delta,
                                          reason="вручную из интерфейса")
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()

    def _remove_entry(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        settlement_id, resource_id = entry
        try:
            self.service.remove_entry(settlement_id, resource_id)
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()
