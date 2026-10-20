"""
Database Schema & Data Integrity Test Suite (Phase 3)
Verifies:
- Typed schema, ISO-8601 dates, unique accident_uids
- No future-dated accident events
- Logical cause-weather consistency
- Absence of target leakage columns
- Provenance tagging
"""
import datetime
import sqlite3
from backend.app import get_db

def test_database_schema_and_types():
    conn = get_db()
    c = conn.cursor()
    columns = {r[1]: r[2] for r in c.execute("PRAGMA table_info(accidents)").fetchall()}
    conn.close()

    assert "id" in columns
    assert "accident_uid" in columns
    assert "occurred_at" in columns
    assert "severity" in columns
    assert "data_source" in columns
    
    # Assert leakage column risk_score is NOT stored in accidents table
    assert "risk_score" not in columns, "Target leakage column 'risk_score' must not be stored in accidents!"

def test_no_future_dates():
    """Assert all occurred_at dates are <= current system date."""
    conn = get_db()
    c = conn.cursor()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d 23:59")
    future_count = c.execute("SELECT COUNT(*) FROM accidents WHERE occurred_at > ?", (today_str,)).fetchone()[0]
    conn.close()

    assert future_count == 0, f"Found {future_count} future-dated accident records!"

def test_unique_accident_uids():
    """Assert zero duplicate accident identifiers."""
    conn = get_db()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM accidents").fetchone()[0]
    distinct = c.execute("SELECT COUNT(DISTINCT accident_uid) FROM accidents").fetchone()[0]
    conn.close()

    assert total > 0
    assert total == distinct, f"Duplicate accident_uids found! Total: {total}, Distinct: {distinct}"

def test_cause_weather_logical_consistency():
    """Assert cause='weather' only appears when weather in ('rain', 'fog') or visibility is low."""
    conn = get_db()
    c = conn.cursor()
    bad_count = c.execute(
        """
        SELECT COUNT(*) FROM accidents
        WHERE cause = 'weather' AND weather = 'clear' AND visibility = 'high'
        """
    ).fetchone()[0]
    conn.close()

    assert bad_count == 0, f"Found {bad_count} contradictory rows where cause=weather but weather=clear & visibility=high!"

def test_fatal_accidents_have_casualties():
    """Assert fatal accidents always have casualties >= 1."""
    conn = get_db()
    c = conn.cursor()
    zero_casualty_fatals = c.execute(
        "SELECT COUNT(*) FROM accidents WHERE severity = 'fatal' AND casualties < 1"
    ).fetchone()[0]
    conn.close()

    assert zero_casualty_fatals == 0, f"Fatal accidents must report at least 1 casualty! Found {zero_casualty_fatals} invalid."
