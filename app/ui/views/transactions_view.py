"""Вид «Сделки игроков»: запись покупок/продаж и книга сделок."""
import customtkinter as ctk

from app.core.exceptions import AppError
from app.economy.currency import format_copper, parse_money
from app.services.inventory_service import InventoryService
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService
from app.services.transaction_service import TransactionService
from app.ui.components import error_message, info_message, make_treeview

KIND_LABELS = {
    "player_purchase": "Игроки купили",
    "player_sale": "Игроки продали",
}
MODE_LABELS = {"full": "Полное влияние на экономику",
               "bookkeeping": "Только учёт (без склада)"}


class TransactionsView:
    """Форма записи сделки игроков + список всех сделок кампании."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self.service = TransactionService()
        self._settlements = SettlementService()
        self._resources = ResourceService()
        self._inventory = InventoryService()
        self._build()

    def _build(self) -> None:
        form = ctk.CTkFrame(self.container)
        form.pack(fill="x", padx=5, pady=5)

        settlements = self._settlements.get_settlements(self.campaign_id)
        self._settlement_by_name = {s.name: s.id for s in settlements}
        resources = self._resources.get_resources(self.campaign_id)
        self._resource_by_name = {r.name: r.id for r in resources}

        r1 = ctk.CTkFrame(form, fg_color="transparent")
        r1.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(r1, text="Поселение:").pack(side="left", padx=5)
        self.settlement_combo = ctk.CTkComboBox(
            r1, width=170, state="readonly",
            values=list(self._settlement_by_name))
        self.settlement_combo.pack(side="left", padx=5)
        if settlements:
            self.settlement_combo.set(settlements[0].name)
        ctk.CTkLabel(r1, text="Ресурс:").pack(side="left", padx=5)
        self.resource_combo = ctk.CTkComboBox(
            r1, width=160, state="readonly", values=list(self._resource_by_name))
        self.resource_combo.pack(side="left", padx=5)
        if resources:
            self.resource_combo.set(resources[0].name)
        ctk.CTkLabel(r1, text="Тип:").pack(side="left", padx=5)
        self.kind_var = ctk.StringVar(value=KIND_LABELS["player_purchase"])
        ctk.CTkComboBox(r1, variable=self.kind_var, width=160, state="readonly",
                        values=list(KIND_LABELS.values())).pack(side="left", padx=5)

        r2 = ctk.CTkFrame(form, fg_color="transparent")
        r2.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(r2, text="Количество:").pack(side="left", padx=5)
        self.qty_entry = ctk.CTkEntry(r2, width=80)
        self.qty_entry.pack(side="left", padx=5)
        ctk.CTkLabel(r2, text="Цена за ед.:").pack(side="left", padx=5)
        self.price_entry = ctk.CTkEntry(r2, width=110)
        self.price_entry.insert(0, "1 gp")
        self.price_entry.pack(side="left", padx=5)
        ctk.CTkLabel(r2, text="Покупатель/продавец:").pack(side="left", padx=5)
        self.party_entry = ctk.CTkEntry(r2, width=170)
        self.party_entry.insert(0, "Отряд приключателей")
        self.party_entry.pack(side="left", padx=5)

        r3 = ctk.CTkFrame(form, fg_color="transparent")
        r3.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(r3, text="Режим:").pack(side="left", padx=5)
        self.mode_var = ctk.StringVar(value=MODE_LABELS["full"])
        ctk.CTkComboBox(r3, variable=self.mode_var, width=230, state="readonly",
                        values=list(MODE_LABELS.values())).pack(side="left", padx=5)
        ctk.CTkLabel(r3, text="Описание:").pack(side="left", padx=5)
        self.note_entry = ctk.CTkEntry(r3, width=240)
        self.note_entry.pack(side="left", padx=5)
        ctk.CTkButton(r3, text="Записать сделку",
                      command=self._record).pack(side="left", padx=5)

        self.tree = make_treeview(self.container, [
            ("date", "Дата", 170),
            ("settlement", "Поселение", 140),
            ("resource", "Ресурс", 130),
            ("kind", "Тип", 150),
            ("qty", "Кол-во", 70),
            ("price", "Цена/ед.", 110),
            ("total", "Итого", 130),
            ("party", "Контрагент", 180),
            ("mode", "Режим", 110),
        ])
        self.refresh()

    def refresh(self) -> None:
        settlements = self._settlements.get_settlements(self.campaign_id)
        resources = self._resources.get_resources(self.campaign_id)
        self._settlement_by_name = {s.name: s.id for s in settlements}
        self._resource_by_name = {r.name: r.id for r in resources}
        for combo, mapping in ((self.settlement_combo, self._settlement_by_name),
                               (self.resource_combo, self._resource_by_name)):
            combo.configure(values=list(mapping))
            if mapping and combo.get() not in mapping:
                combo.set(next(iter(mapping)))
        settlement_names = {s.id: s.name for s in settlements}
        resource_names = {r.id: r.name for r in resources}
        self.tree.delete(*self.tree.get_children())
        for tx in self.service.get_transactions(self.campaign_id):
            from app.simulation.game_calendar import format_game_date
            self.tree.insert(
                "", "end", iid=str(tx.id),
                text=format_game_date(tx.game_hour),
                values=(
                    settlement_names.get(tx.settlement_id, "—"),
                    resource_names.get(tx.resource_id, "—"),
                    KIND_LABELS.get(tx.kind, tx.kind),
                    tx.quantity, format_copper(tx.price_per_unit_copper),
                    format_copper(tx.total_copper),
                    tx.counterparty or "—",
                    "учёт" if tx.bookkeeping_only else "экономика",
                ),
            )

    def _record(self) -> None:
        settlement_id = self._settlement_by_name.get(self.settlement_combo.get())
        resource_id = self._resource_by_name.get(self.resource_combo.get())
        if settlement_id is None or resource_id is None:
            error_message(self.container,
                          "Сначала создайте поселение и ресурс")
            return
        kind = next(k for k, v in KIND_LABELS.items()
                    if v == self.kind_var.get())
        mode = next(m for m, v in MODE_LABELS.items()
                    if v == self.mode_var.get())
        try:
            quantity = int(self.qty_entry.get())
        except ValueError:
            error_message(self.container, "Количество должно быть целым числом")
            return
        try:
            price = parse_money(self.price_entry.get())
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        try:
            self.service.record_player_transaction(
                self.campaign_id, settlement_id, resource_id, kind,
                quantity, price, counterparty=self.party_entry.get().strip(),
                description=self.note_entry.get().strip(), mode=mode,
            )
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()
        info_message(self.container, "Сделка игроков записана")
