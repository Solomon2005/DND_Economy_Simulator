"""Тесты резервного копирования и восстановления на реальной SQLite."""
import os
import sqlite3
import time

import pytest

from app.core.exceptions import AppError
from app.services.backup_service import (
    AUTO_BACKUP_INTERVAL_SECONDS,
    auto_backup_if_due,
    create_backup,
    list_backups,
    restore_backup,
)


def _make_db(path):
    con = sqlite3.connect(path)
    try:
        con.execute("create table items (id integer primary key, name text)")
        con.execute("insert into items (name) values ('первый')")
        con.commit()
    finally:
        con.close()


def _names(path):
    con = sqlite3.connect(path)
    try:
        return [row[0] for row in con.execute(
            "select name from items order by id")]
    finally:
        con.close()


def _integrity(path):
    con = sqlite3.connect(path)
    try:
        return con.execute("pragma integrity_check").fetchone()[0]
    finally:
        con.close()


class _AliveThread:
    def is_alive(self):
        return True


class _FakeClock:
    def __init__(self):
        self._thread = _AliveThread()
        self.stopped = False
        self.started = False

    def stop(self):
        self.stopped = True
        self._thread = None

    def start(self):
        self.started = True
        self._thread = _AliveThread()


def test_create_and_list_backup(tmp_path):
    db = tmp_path / "campaign.db"
    _make_db(db)
    backup_dir = tmp_path / "backups"

    path = create_backup(db, backup_dir)
    assert path.exists()
    assert _integrity(path) == "ok"
    assert _names(path) == ["первый"]
    assert list_backups(backup_dir) == [path]


def test_restore_replaces_database(tmp_path):
    db = tmp_path / "campaign.db"
    _make_db(db)
    backup_dir = tmp_path / "backups"
    path = create_backup(db, backup_dir)

    con = sqlite3.connect(db)
    con.execute("insert into items (name) values ('второй')")
    con.commit()
    con.close()
    assert _names(db) == ["первый", "второй"]

    restore_backup(path, db)
    assert _names(db) == ["первый"]
    assert _integrity(db) == "ok"


def test_restore_missing_backup_is_rejected(tmp_path):
    with pytest.raises(AppError):
        restore_backup(tmp_path / "missing.db", tmp_path / "campaign.db")


def test_failed_restore_keeps_original_database(tmp_path):
    db = tmp_path / "campaign.db"
    _make_db(db)
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"not a sqlite database")

    with pytest.raises(AppError):
        restore_backup(broken, db)

    assert _names(db) == ["первый"]
    assert _integrity(db) == "ok"


def test_restore_stops_and_restarts_clock(tmp_path):
    db = tmp_path / "campaign.db"
    _make_db(db)
    path = create_backup(db, tmp_path / "backups")

    clock = _FakeClock()
    restore_backup(path, db, clock=clock)
    assert clock.stopped is True
    assert clock.started is True


def test_failed_restore_restarts_clock(tmp_path):
    db = tmp_path / "campaign.db"
    _make_db(db)
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"not a sqlite database")

    clock = _FakeClock()
    with pytest.raises(AppError):
        restore_backup(broken, db, clock=clock)
    assert clock.stopped is True
    assert clock.started is True


def test_restore_disposes_engine_for_main_db(tmp_path, monkeypatch):
    from app.database import session as db_session
    from app.services import backup_service

    db = tmp_path / "campaign.db"
    _make_db(db)
    path = create_backup(db, tmp_path / "backups")

    class FakeEngine:
        def __init__(self):
            self.calls = 0

        def dispose(self):
            self.calls += 1

    fake_engine = FakeEngine()
    monkeypatch.setattr(db_session, "engine", fake_engine)
    monkeypatch.setattr(backup_service, "DB_PATH", db)
    restore_backup(path, db)
    assert fake_engine.calls == 2


def test_backup_names_do_not_collide(tmp_path):
    db = tmp_path / "campaign.db"
    _make_db(db)
    backup_dir = tmp_path / "backups"
    first = create_backup(db, backup_dir)
    second = create_backup(db, backup_dir)
    assert first != second
    assert len(list_backups(backup_dir)) == 2


def test_auto_backup_skips_when_recent(tmp_path):
    db = tmp_path / "campaign.db"
    _make_db(db)
    backup_dir = tmp_path / "backups"
    create_backup(db, backup_dir)  # свежая копия
    assert auto_backup_if_due(db, backup_dir) is None
    assert len(list_backups(backup_dir)) == 1


def test_auto_backup_creates_when_stale(tmp_path):
    db = tmp_path / "campaign.db"
    _make_db(db)
    backup_dir = tmp_path / "backups"
    old = create_backup(db, backup_dir)
    stale = time.time() - AUTO_BACKUP_INTERVAL_SECONDS - 60
    os.utime(old, (stale, stale))
    created = auto_backup_if_due(db, backup_dir)
    assert created is not None and created.exists()
    assert len(list_backups(backup_dir)) == 2


def test_auto_backup_creates_first_copy(tmp_path):
    db = tmp_path / "campaign.db"
    _make_db(db)
    assert auto_backup_if_due(db, tmp_path / "backups") is not None


def test_auto_backup_no_database(tmp_path):
    assert auto_backup_if_due(tmp_path / "missing.db", tmp_path / "b") is None
