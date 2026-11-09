"""Вид управления поселениями."""
import customtkinter as ctk

from app.core.exceptions import AppError
from app.services.settlement_service import SettlementService
from app.ui.components import error_message, info_message, make_treeview

TYPE_LABELS = {
    "village": "Деревня",
    "town": "Городок",
    "city": "Город",
    "port": "Порт",
    "fortress": "Крепость",
    "mining": "Рудничный посёлок",
    "trading_post": "Торговый пост",
}


class SettlementsView:
    """Вид управления поселениями одной кампании."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self.service = SettlementService()
        self._build()

    def _build(self) -> None:
        form = ctk.CTkFrame(self.container)
        form.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(form, text="Название:").grid(row=0, column=0, padx=5, pady=5)
        self.name_entry = ctk.CTkEntry(form, width=200)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(form, text="Тип:").grid(row=0, column=2, padx=5, pady=5)
        self.type_var = ctk.StringVar(value="village")
        ctk.CTkComboBox(
            form, variable=self.type_var, width=170,
            values=list(TYPE_LABELS.values()), state="readonly",
        ).grid(row=0, column=3, padx=5, pady=5)

        ctk.CTkLabel(form, text="Население:").grid(row=0, column=4, padx=5, pady=5)
        self.population_entry = ctk.CTkEntry(form, width=90)
        self.population_entry.insert(0, "100")
        self.population_entry.grid(row=0, column=5, padx=5, pady=5)

        ctk.CTkButton(form, text="Создать", command=self._create).grid(row=0, column=6, padx=5, pady=5)
        ctk.CTkButton(form, text="Изменить выбранный",
                      command=self._edit).grid(row=0, column=7, padx=5, pady=5)
        ctk.CTkButton(form, text="Удалить выбранный", fg_color="#8b2e2e",
                      command=self._delete).grid(row=0, column=8, padx=5, pady=5)

        self.tree = make_treeview(self.container, [
            ("name", "Название", 200),
            ("type", "Тип", 140),
            ("population", "Население", 100),
            ("description", "Описание", 300),
        ])
        self.refresh()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for s in self.service.get_settlements(self.campaign_id):
            self.tree.insert(
                "", "end", iid=str(s.id), text=s.name,
                values=(TYPE_LABELS.get(s.type, s.type), s.population, s.description),
            )

    def _create(self) -> None:
        name = self.name_entry.get().strip()
        if not name:
            error_message(self.container, "Введите название поселения")
            return
        type_key = next(
            (k for k, v in TYPE_LABELS.items() if v == self.type_var.get()), "village"
        )
        try:
            population = int(self.population_entry.get())
        except ValueError:
            error_message(self.container, "Население должно быть целым числом")
            return
        try:
            self.service.create_settlement(self.campaign_id, name, type_key, population)
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.name_entry.delete(0, "end")
        self.refresh()

    def _edit(self) -> None:
        selection = self.tree.selection()
        if not selection:
            error_message(self.container, "Выберите поселение в таблице")
            return
        settlement_id = int(selection[0])
        current = next(
            (s for s in self.service.get_settlements(self.campaign_id)
             if s.id == settlement_id), None)
        if current is None:
            return

        dialog = ctk.CTkToplevel(self.container)
        dialog.title("Изменить поселение")
        dialog.transient(self.container.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(dialog, text="Название:").grid(
            row=0, column=0, padx=8, pady=6, sticky="w")
        name_entry = ctk.CTkEntry(dialog, width=220)
        name_entry.insert(0, current.name)
        name_entry.grid(row=0, column=1, padx=8, pady=6)

        ctk.CTkLabel(dialog, text="Тип:").grid(
            row=1, column=0, padx=8, pady=6, sticky="w")
        type_var = ctk.StringVar(value=TYPE_LABELS.get(current.type, current.type))
        ctk.CTkComboBox(dialog, variable=type_var, width=200, state="readonly",
                        values=list(TYPE_LABELS.values())).grid(
            row=1, column=1, padx=8, pady=6)

        ctk.CTkLabel(dialog, text="Население:").grid(
            row=2, column=0, padx=8, pady=6, sticky="w")
        pop_entry = ctk.CTkEntry(dialog, width=220)
        pop_entry.insert(0, str(current.population))
        pop_entry.grid(row=2, column=1, padx=8, pady=6)

        ctk.CTkLabel(dialog, text="Описание:").grid(
            row=3, column=0, padx=8, pady=6, sticky="nw")
        desc_box = ctk.CTkTextbox(dialog, width=220, height=80)
        desc_box.insert("1.0", current.description)
        desc_box.grid(row=3, column=1, padx=8, pady=6)

        def save() -> None:
            try:
                population = int(pop_entry.get())
            except ValueError:
                error_message(dialog, "Население должно быть целым числом")
                return
            type_key = next(
                (k for k, v in TYPE_LABELS.items() if v == type_var.get()),
                current.type)
            try:
                self.service.update_settlement(
                    settlement_id, name=name_entry.get(),
                    settlement_type=type_key, population=population,
                    description=desc_box.get("1.0", "end").rstrip("\n"))
            except AppError as exc:
                error_message(dialog, str(exc))
                return
            dialog.destroy()
            self.refresh()
            info_message(self.container, "Поселение обновлено")

        ctk.CTkButton(dialog, text="Сохранить", command=save).grid(
            row=4, column=1, padx=8, pady=10, sticky="e")

    def _delete(self) -> None:
        selection = self.tree.selection()
        if not selection:
            error_message(self.container, "Выберите поселение в таблице")
            return
        try:
            self.service.delete_settlement(int(selection[0]))
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        self.refresh()
        info_message(self.container, "Поселение удалено")
