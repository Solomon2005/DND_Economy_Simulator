"""Лаунчер: проверка зависимостей и запуск приложения.

Запуск без терминала: pythonw main.py (см. create_shortcut.py).
"""
import importlib
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

REQUIRED = (
    ("customtkinter", "CustomTkinter"),
    ("sqlalchemy", "SQLAlchemy"),
    ("networkx", "NetworkX"),
    ("matplotlib", "Matplotlib"),
)


def check_dependencies() -> list[str]:
    missing = []
    for module, package in REQUIRED:
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(package)
    return missing


def main() -> int:
    missing = check_dependencies()
    if missing:
        message = (
            "Не установлены компоненты: " + ", ".join(missing) + "\n"
            "Установите их командой:\n"
            f"    {sys.executable} -m pip install -r requirements.txt"
        )
        print(message, file=sys.stderr)
        try:
            from tkinter import messagebox
            messagebox.showerror("Ошибка зависимостей", message)
        except Exception:
            pass
        return 1

    # запуск приложения в текущем интерпретаторе
    return subprocess.call([sys.executable, str(PROJECT_ROOT / "main.py")])


if __name__ == "__main__":
    sys.exit(main())
