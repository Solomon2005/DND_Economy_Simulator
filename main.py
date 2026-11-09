"""Точка входа приложения: инициализация БД и запуск главного окна."""
import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler


def _setup_logging() -> None:
    """Диагностика симуляции пишется в data/simulation.log (с ротацией)."""
    from app.core.config import DATA_DIR
    handler = RotatingFileHandler(
        DATA_DIR / "simulation.log", maxBytes=2 * 1024 * 1024,
        backupCount=3, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def _warn(title: str, text: str) -> None:
    """Показать предупреждение до создания главного окна (или в stderr)."""
    try:
        from tkinter import messagebox
        messagebox.showwarning(title, text)
    except Exception:
        sys.stderr.write(f"{title}: {text}\n")


def main() -> int:
    try:
        from app.database.session import check_integrity, init_db
        init_db()  # каталоги и таблицы создаются при первом запуске
        _setup_logging()

        integrity = check_integrity()
        if integrity != "ok":
            _warn(
                "Проблема с базой данных",
                f"PRAGMA integrity_check: {integrity}\n\n"
                "Рекомендуется восстановить базу из резервной копии "
                "(«Настройки» → «Восстановить последнюю»).",
            )

        from app.services.backup_service import auto_backup_if_due
        auto_backup_if_due()  # не чаще раза в сутки, молча

        from app.ui.main_window import run_app
        run_app()
        return 0
    except Exception:
        traceback.print_exc()
        # понятное сообщение об ошибке запуска
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Ошибка запуска",
                "Не удалось запустить приложение.\n\n"
                + traceback.format_exc(limit=3),
            )
        except Exception:
            sys.stderr.write(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
