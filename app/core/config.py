"""Конфигурация приложения: пути, параметры симуляции, настройки DM."""
import json
from pathlib import Path

from app.core.exceptions import AppError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config.json"
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "campaign.db"
BACKUP_DIR = DATA_DIR / "backups"

DEFAULTS = {
    "price_k": 0.06,               # интенсивность реакции цены на спрос/предложение
    "price_min_factor": 0.5,       # нижний предел цены относительно базовой
    "price_max_factor": 3.0,       # верхний предел цены относительно базовой
    "tick_game_hours": 6,          # игровых часов за один тик
    "tick_real_seconds": 2.0,      # реальных секунд на тик при скорости 1x
    "negotiation_max_rounds": 5,
    "default_storage_capacity": 500,
    "player_transaction_mode": "full",   # "full" | "bookkeeping"
    "seasonal_production": True,          # сезонные множители производства
    "record_daily_flows": True,          # производство/потребление пишутся в журнал раз в сутки
    "price_history_days": 90,            # сколько игровых суток хранить историю цен
    "theme": "dark",                     # dark | light
}


def load_config() -> dict:
    """Вернуть настройки: значения по умолчанию, перекрытые config.json."""
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            raise AppError(f"Не удалось прочитать config.json: {exc}") from exc
    else:
        save_config(cfg)
    if cfg.get("theme") not in ("dark", "light"):
        cfg["theme"] = "dark"
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
