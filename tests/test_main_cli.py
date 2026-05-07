"""Tests for src/utils/cli.py — date parsing + startup validation."""
from unittest.mock import MagicMock

import pytest

from src.config.settings import Settings
from src.utils.cli import parse_date, validate_startup


def test_parse_date_returns_bangkok_aware():
    d = parse_date("2024-05-06")
    assert d.year == 2024 and d.month == 5 and d.day == 6
    assert d.tzinfo is not None
    assert str(d.tzinfo) == "Asia/Bangkok"


def test_parse_date_rejects_bad_format():
    with pytest.raises(ValueError):
        parse_date("06/05/2024")


def test_parse_date_rejects_garbage():
    with pytest.raises(ValueError):
        parse_date("not-a-date")


def test_validate_startup_passes_when_all_accessible():
    s = Settings()
    s.CALENDAR_FILE_ID = "calA"
    s.FOLDER_EMAIL_ARCHIVES = "fA"
    s.FOLDER_KNOWLEDGE_BASE = "fB"
    s.FOLDER_PROGRAM_MGMT = "fC"

    drive = MagicMock()
    drive.check_access.return_value = (True, "ok-name")

    validate_startup(s, drive)
    assert drive.check_access.call_count == 4


def test_validate_startup_collects_all_failures():
    s = Settings()
    s.CALENDAR_FILE_ID = "calA"
    s.FOLDER_EMAIL_ARCHIVES = ""
    s.FOLDER_KNOWLEDGE_BASE = "fB"
    s.FOLDER_PROGRAM_MGMT = "fC"

    drive = MagicMock()
    drive.check_access.side_effect = [
        (True, "calendar"),
        (False, "id is empty"),
        (False, "403 forbidden"),
        (True, "program"),
    ]

    with pytest.raises(RuntimeError) as exc:
        validate_startup(s, drive)
    msg = str(exc.value)
    assert "FOLDER_EMAIL_ARCHIVES" in msg
    assert "FOLDER_KNOWLEDGE_BASE" in msg
    assert "FOLDER_PROGRAM_MGMT" not in msg  # this one passed
    assert "CALENDAR_FILE_ID" not in msg     # this one passed
