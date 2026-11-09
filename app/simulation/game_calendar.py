"""Игровой календарь: 12 месяцев по 30 дней, 24 часа в сутках.

game_hour — целое число часов с начала кампании.
"""

MONTHS = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)
HOURS_PER_DAY = 24
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12


def format_game_date(game_hour: int) -> str:
    """0 -> «Январь, День 1, 00:00»."""
    day_of_year = game_hour // HOURS_PER_DAY
    month = (day_of_year // DAYS_PER_MONTH) % MONTHS_PER_YEAR
    day = (day_of_year % DAYS_PER_MONTH) + 1
    hour = game_hour % HOURS_PER_DAY
    return f"{MONTHS[month]}, День {day}, {hour:02d}:00"


def season_for_hour(game_hour: int) -> str:
    """Сезон по месяцу: spring|summer|autumn|winter."""
    month = ((game_hour // HOURS_PER_DAY) // DAYS_PER_MONTH) % MONTHS_PER_YEAR
    if month in (2, 3, 4):        # март–май
        return "spring"
    if month in (5, 6, 7):        # июнь–август
        return "summer"
    if month in (8, 9, 10):       # сентябрь–ноябрь
        return "autumn"
    return "winter"               # декабрь–февраль


# Сезонные множители производства (если включено season_production)
SEASON_PRODUCTION_FACTOR = {
    "spring": 1.0,
    "summer": 1.1,
    "autumn": 1.0,
    "winter": 0.7,
}

# Русские названия из старых данных и ручного ввода приводим к ключам
_SEASON_ALIASES = {
    "spring": "spring", "весна": "spring",
    "summer": "summer", "лето": "summer",
    "autumn": "autumn", "осень": "autumn",
    "winter": "winter", "зима": "winter",
}


def normalize_season(value: str) -> str:
    """Канонический ключ сезона; пустая строка для неизвестного значения."""
    return _SEASON_ALIASES.get((value or "").strip().lower(), "")


def season_allows(restriction: str, season: str) -> bool:
    """Разрешён ли маршрут в данном сезоне (пустое ограничение — всегда).

    Сравнение нечувствительно к регистру и понимает русские названия
    («Зима»), чтобы старые данные не отключали маршрут молча.
    """
    if not restriction:
        return True
    return normalize_season(restriction) == normalize_season(season)


def crosses_day_boundary(old_hour: int, new_hour: int) -> bool:
    """Пересечена ли граница суток (для суточной отчётности)."""
    return old_hour // HOURS_PER_DAY != new_hour // HOURS_PER_DAY
