"""Резервное копирование и восстановление базы данных кампании."""
import sqlite3
import time
from pathlib import Path

from app.core.config import BACKUP_DIR, DB_PATH
from app.core.exceptions import AppError

AUTO_BACKUP_INTERVAL_SECONDS = 24 * 60 * 60  # сутки


def _copy_sqlite(src: Path, dst: Path) -> None:
    """Согласованная копия через SQLite backup API, а не копирование файла."""
    source = sqlite3.connect(src)
    try:
        target = sqlite3.connect(dst)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def create_backup(db_path: Path = DB_PATH,
                  backup_dir: Path = BACKUP_DIR) -> Path:
    """Создать копию БД: data/backups/campaign_ГГГГММДД_ЧЧММСС.db."""
    if not db_path.exists():
        raise AppError("База данных ещё не создана — копировать нечего")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"campaign_{stamp}.db"
    # одинаковая секунда — добавляем номер, чтобы не затереть копию
    counter = 1
    while target.exists():
        target = backup_dir / f"campaign_{stamp}_{counter}.db"
        counter += 1
    try:
        _copy_sqlite(db_path, target)
    except sqlite3.Error as exc:
        target.unlink(missing_ok=True)
        raise AppError(f"Не удалось создать резервную копию: {exc}") from exc
    return target


def list_backups(backup_dir: Path = BACKUP_DIR) -> list[Path]:
    if not backup_dir.exists():
        return []
    return sorted(backup_dir.glob("campaign_*.db"), reverse=True)


def restore_backup(backup_path: Path, db_path: Path = DB_PATH,
                   clock=None) -> None:
    """Восстановить БД из копии через SQLite backup API.

    Часы останавливаются на время восстановления и запускаются снова, если
    работали до него. При сбое текущая база возвращается из страховочной копии.
    """
    if not backup_path.exists():
        raise AppError(f"Резервная копия не найдена: {backup_path.name}")
    from app.database import session as db_session

    is_main = db_path.resolve() == DB_PATH.resolve()
    was_running = bool(clock is not None and clock._thread
                       and clock._thread.is_alive())
    if clock is not None:
        clock.stop()
    safety = db_path.with_name(db_path.name + ".restore-safety")
    restored = False
    try:
        if is_main:
            db_session.engine.dispose()  # закрыть соединения перед заменой
        if db_path.exists():
            _copy_sqlite(db_path, safety)
        _copy_sqlite(backup_path, db_path)
        if is_main:
            db_session.engine.dispose()  # переоткрыть соединения после restore
        restored = True
    except Exception as exc:
        if safety.exists():
            try:
                if is_main:
                    db_session.engine.dispose()
                _copy_sqlite(safety, db_path)
            except Exception:
                pass
        raise AppError(f"Не удалось восстановить базу: {exc}") from exc
    finally:
        if restored:
            safety.unlink(missing_ok=True)
        if was_running:
            clock.start()


def auto_backup_if_due(db_path: Path = DB_PATH,
                       backup_dir: Path = BACKUP_DIR) -> Path | None:
    """Автокопия при запуске: не чаще раза в сутки. None — копия не нужна."""
    if not db_path.exists():
        return None
    backups = list_backups(backup_dir)
    if backups:
        age = time.time() - backups[0].stat().st_mtime
        if age < AUTO_BACKUP_INTERVAL_SECONDS:
            return None
    return create_backup(db_path, backup_dir)
