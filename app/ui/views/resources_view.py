"""Вид управления ресурсами."""
import customtkinter as ctk

from app.core.exceptions import AppError
from app.economy.currency import format_copper, parse_money
from app.services.resource_service import ResourceService
from app.ui.components import error_message, info_message, make_treeview


class ResourcesView:
    """Вид управления ресурсами кампании."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self.service = ResourceService()
        self._build()

    def _build(self) -> None:
        form = ctk.CTkFrame(self.container)
        form.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(form, text="Название:").grid(row=0, column=0, padx=5, pady=5)
        self.name_entry = ctk.CTkEntry(form, width=160)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(form, text="Категория:").grid(row=0, column=2, padx=5, pady=5)
        self.category_entry = ctk.CTkEntry(form, width=120)
        self.category_entry.grid(row=0, column=3, padx=5, pady=5)

        ctk.CTkLabel(form, text="Единица:").grid(row=0, column=4, padx=5, pady=5)
        self.unit_entry = ctk.CTkEntry(form, width=70)
        self.unit_entry.insert(0, "шт")
        self.unit_entry.grid(row=0, column=5, padx=5, pady=5)

        ctk.CTkLabel(form, text="Базовая цена:").grid(row=0, column=6, padx=5, pady=5)
        self.price_entry = ctk.CTkEntry(form, width=120)
        self.price_entry.insert(0, "1 gp")
        self.price_entry.grid(row=0, column=7, padx=5, pady=5)

        ctk.CTkButton(form, text="Создать", command=self._create).grid(row=0, column=8, padx=5, pady=5)
        ctk.CTkButton(form, text="Изменить выбранный",
                      command=self._edit).grid(row=0, column=9, padx=5, pady=5)
        ctk.CTkButton(form, text="Удалить выбранный", fg_color="#8b2e2e",
                      command=self._delete).grid(row=0, column=10, padx=5, pady=5)

        self.tree = make_treeview(self.container, [
            ("name", "Название", 180),
            ("category", "Категория", 130),
            ("unit", "Единица", 80),
            ("price", "Базовая цена", 130),
        ])
        self.refresh()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for r in self.service.get_resources(self.campaign_id):
            self.tree.insert(
                "", "end", iid=str(r.id), text=r.name,
                values=(r.category, r.unit, format_copper(r.base_price_copper)),
            )

    def _create(self) -> None:
        name = self.name_entry.get().strip()
        if not name:
            error_message(self.container, "Введите название ресурса")
            return
        try:
            base_price = parse_money(self.price_entry.get())
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        if base_price <= 0:
            error_message(self.container, "Базовая цена должна быть положительной")
            return
        try:
            self.service.create_resource(
                self.campaign_id, name,
                self.category_entry.get().strip(),
                self.unit_entry.get().strip() or "шт",
                base_price,
            )
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.name_entry.delete(0, "end")
        self.refresh()

    def _edit(self) -> None:
        selection = self.tree.selection()
        if not selection:
            error_message(self.container, "Выберите ресурс в таблице")
            return
        resource_id = int(selection[0])
        current = next(
            (r for r in self.service.get_resources(self.campaign_id)
             if r.id == resource_id), None)
        if current is None:
            return

        dialog = ctk.CTkToplevel(self.container)
        dialog.title("Изменить ресурс")
        dialog.transient(self.container.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)

        entries = {}
        for row, (key, label, value) in enumerate((
            ("name", "Название:", current.name),
            ("category", "Категория:", current.category),
            ("unit", "Единица:", current.unit),
            ("price", "Базовая цена:", format_copper(current.base_price_copper)),
        )):
            ctk.CTkLabel(dialog, text=label).grid(
                row=row, column=0, padx=8, pady=6, sticky="w")
            entry = ctk.CTkEntry(dialog, width=220)
            entry.insert(0, value)
            entry.grid(row=row, column=1, padx=8, pady=6)
            entries[key] = entry

        def save() -> None:
            try:
                price = parse_money(entries["price"].get())
            except AppError as exc:
                error_message(dialog, str(exc))
                return
            try:
                self.service.update_resource(
                    self.campaign_id, resource_id,
                    name=entries["name"].get(),
                    category=entries["category"].get().strip(),
                    unit=entries["unit"].get().strip(),
                    base_price_copper=price,
                )
            except AppError as exc:
                error_message(dialog, str(exc))
                return
            dialog.destroy()
            self.refresh()
            info_message(self.container, "Ресурс обновлён")

        ctk.CTkButton(dialog, text="Сохранить", command=save).grid(
            row=4, column=1, padx=8, pady=10, sticky="e")

    def _delete(self) -> None:
        selection = self.tree.selection()
        if not selection:
            error_message(self.container, "Выберите ресурс в таблице")
            return
        try:
            self.service.delete_resource(self.campaign_id, int(selection[0]))
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()
        info_message(self.container, "Ресурс удалён")
