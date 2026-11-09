"""Валюта D&D: внутренняя единица — целая медная монета (CP).

SP=10 CP, EP=50 CP, GP=100 CP, PP=1000 CP. Никакой арифметики с плавающей точкой.
"""
import re

from app.core.exceptions import AppError

DENOMINATIONS = (("PP", 1000), ("GP", 100), ("EP", 50), ("SP", 10), ("CP", 1))
_VALUE = {code: value for code, value in DENOMINATIONS}
# Для отображения используем привычные D&D деньги: золото/серебро/медь
DISPLAY = (("GP", 100), ("SP", 10), ("CP", 1))


def format_copper(total: int) -> str:
    """1055 -> «1 GP 5 SP 5 CP»."""
    if not isinstance(total, int):
        raise AppError("Сумма должна быть целым числом медных монет")
    sign = "-" if total < 0 else ""
    rest = abs(total)
    parts = []
    for code, value in DISPLAY:
        amount, rest = divmod(rest, value)
        if amount:
            parts.append(f"{amount} {code}")
    return sign + " ".join(parts) if parts else f"{sign}0 CP"


def parse_money(text: str) -> int:
    """Разобрать строку вида «2 gp 50 sp» или «250» (медные) в целые CP."""
    if not isinstance(text, str):
        raise AppError("Сумма должна быть строкой вида «2 gp 50 sp»")
    text = text.strip().lower().replace("ё", "е")
    if not text:
        return 0
    tokens = re.findall(r"(\d+)\s*([a-z]*)", text)
    leftover = re.sub(r"\d+\s*[a-z]*", "", text).strip()
    if leftover or not tokens:
        raise AppError(f"Некорректная сумма: «{text}»")
    total = 0
    for digits, code in tokens:
        amount = int(digits)
        if code:
            value = _VALUE.get(code.upper())
            if value is None:
                raise AppError(f"Неизвестная валюта: «{code}»")
            amount *= value
        total += amount
    return total
