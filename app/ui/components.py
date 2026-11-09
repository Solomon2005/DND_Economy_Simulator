"""Переиспользуемые элементы интерфейса."""
from tkinter import ttk

import customtkinter as ctk


def make_treeview(parent, columns: list[tuple[str, str, int]]) -> ttk.Treeview:
    """Создать таблицу: columns = [(id, заголовок, ширина), ...].

    Колонка #0 — текст узла (первая колонка данных).
    """
    frame = ctk.CTkFrame(parent)
    frame.pack(fill="both", expand=True, padx=5, pady=5)

    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="tree headings")
    tree.heading("#0", text=columns[0][1])
    tree.column("#0", width=columns[0][2], anchor="w")
    for col_id, title, width in columns[1:]:
        tree.heading(col_id, text=title)
        tree.column(col_id, width=width, anchor="w")

    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


def ask_string(parent, title: str, prompt: str, initial: str = "") -> str | None:
    """Модальный строковый ввод; None при отмене."""
    import tkinter as tk
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.transient(parent.winfo_toplevel())
    tk.Label(dialog, text=prompt, padx=10, pady=8).pack()
    var = tk.StringVar(value=initial)
    entry = tk.Entry(dialog, textvariable=var, width=30)
    entry.select_range(0, "end")
    entry.pack(padx=10, pady=(0, 8))
    result: dict = {}

    def ok() -> None:
        result["value"] = var.get()
        dialog.destroy()

    def cancel() -> None:
        dialog.destroy()

    buttons = tk.Frame(dialog)
    buttons.pack(pady=(0, 8))
    tk.Button(buttons, text="OK", width=8, command=ok).pack(side="left", padx=4)
    tk.Button(buttons, text="Отмена", width=8, command=cancel).pack(side="left", padx=4)
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.grab_set()
    entry.focus_set()
    dialog.wait_window()
    return result.get("value")


def error_message(parent, text: str) -> None:
    from tkinter import messagebox
    messagebox.showerror("Ошибка", text, parent=parent)


def info_message(parent, text: str) -> None:
    from tkinter import messagebox
    messagebox.showinfo("Информация", text, parent=parent)
