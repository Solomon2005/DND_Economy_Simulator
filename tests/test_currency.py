"""Тесты валюты D&D: целые медные монеты, без float."""
import pytest

from app.core.exceptions import AppError
from app.economy.currency import format_copper, parse_money


def test_denominations():
    assert parse_money("1 pp") == 1000
    assert parse_money("1 gp") == 100
    assert parse_money("1 ep") == 50
    assert parse_money("1 sp") == 10
    assert parse_money("1 cp") == 1


def test_format():
    assert format_copper(1055) == "10 GP 5 SP 5 CP"
    assert format_copper(0) == "0 CP"
    assert format_copper(100) == "1 GP"
    assert format_copper(-210) == "-2 GP 1 SP"


def test_parse_mixed():
    assert parse_money("2 gp 50 sp") == 700   # 200 + 500 CP
    assert parse_money("1gp5sp") == 150  # 100 + 50 CP
    assert parse_money("250") == 250
    assert parse_money("") == 0
    assert parse_money("1 GP 2 EP 3 CP") == 203


def test_parse_invalid():
    with pytest.raises(AppError):
        parse_money("abc")
    with pytest.raises(AppError):
        parse_money("1 zz")
    with pytest.raises(AppError):
        parse_money("1 gp xx")


def test_integer_only():
    # все операции остаются целочисленными
    total = parse_money("3 gp 7 sp")
    assert isinstance(total, int)
    assert total == 370
