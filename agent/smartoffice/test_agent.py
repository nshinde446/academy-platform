"""Pure-logic tests for the SmartOffice agent — no DB / pyodbc needed.

Run from this folder:  python -m pytest test_agent.py -q
The DB read is exercised through a fake cursor/connection, so the row-mapping
and watermark logic are covered without SQL Server.
"""

import configparser
from datetime import datetime

import smartoffice_agent as agent


class _FakeCursor:
    def __init__(self, columns, records):
        self.description = [(c,) for c in columns]
        self._records = records
        self.executed = None

    def execute(self, sql, *params):
        self.executed = (sql, params)

    def fetchall(self):
        return self._records


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def close(self):
        pass


def _cfg(**source):
    cfg = configparser.ConfigParser()
    base = {
        "table": "dbo.DeviceLogs",
        "employee_code_column": "EmployeeCode",
        "timestamp_column": "LogDate",
        "id_column": "Id",
        "serial_column": "SerialNumber",
        "direction_column": "PunchDirection",
        "batch_size": "500",
    }
    base.update(source)
    cfg["source"] = base
    return cfg


def test_fetch_maps_rows_and_advances_id_cursor():
    cols = ["EmployeeCode", "LogDate", "SerialNumber", "PunchDirection", "_cursor"]
    records = [
        ("2001", datetime(2026, 5, 28, 9, 55, 0), "SNA", "in", 10),
        ("2002", datetime(2026, 5, 28, 9, 56, 0), "SNA", "out", 11),
    ]
    conn = _FakeConn(_FakeCursor(cols, records))
    rows, new_wm = agent.fetch_new_rows(conn, _cfg(), {"cursor": 9})

    assert rows[0] == {
        "EmployeeCode": "2001", "LogDate": "2026-05-28 09:55:00",
        "SerialNumber": "SNA", "PunchDirection": "in",
    }
    assert new_wm["cursor"] == 11          # advanced to the max id in the batch
    # The query filtered on the incoming cursor value.
    assert conn._cursor.executed[1] == (500, 9)


def test_fetch_timestamp_cursor_when_no_id_column():
    cols = ["EmployeeCode", "LogDate", "_cursor"]
    records = [("2003", datetime(2026, 5, 28, 10, 0, 0), datetime(2026, 5, 28, 10, 0, 0))]
    conn = _FakeConn(_FakeCursor(cols, records))
    rows, new_wm = agent.fetch_new_rows(
        conn, _cfg(id_column="", serial_column="", direction_column=""), {}
    )
    assert rows == [{"EmployeeCode": "2003", "LogDate": "2026-05-28 10:00:00"}]
    assert new_wm["cursor"] == "2026-05-28 10:00:00"
    # Default lower bound when there's no saved watermark yet.
    assert conn._cursor.executed[1] == (500, "1900-01-01 00:00:00")


def test_watermark_round_trip(tmp_path):
    p = str(tmp_path / "wm.json")
    agent.write_watermark(p, {"cursor": 42})
    assert agent.read_watermark(p) == {"cursor": 42}
    # Missing/garbage file reads as empty, not a crash.
    assert agent.read_watermark(str(tmp_path / "nope.json")) == {}


def test_build_conn_str_prefers_raw_string():
    cfg = configparser.ConfigParser()
    cfg["sql"] = {"odbc_connection_string": "DRIVER=x;SERVER=y;"}
    assert agent.build_conn_str(cfg) == "DRIVER=x;SERVER=y;"
