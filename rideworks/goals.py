"""Only the rider-entered annual cycling mileage target, explicitly in miles."""
from datetime import datetime, timezone
from decimal import Decimal
import re
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = 'America/Los_Angeles'


def browser_zone(name):
    if not isinstance(name, str) or not name or len(name) > 128:
        raise ValueError('A valid browser timezone is required.')
    try:
        return ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError('A valid browser timezone is required.') from None


def target_miles(text):
    if not isinstance(text, str) or len(text) > 32 or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', text):
        raise ValueError('Enter a number greater than zero and at most 100,000 miles.')
    value = Decimal(text)
    if not 0 < value <= 100_000:
        raise ValueError('Enter a number greater than zero and at most 100,000 miles.')
    return value


def query_zone(query, key='tz'):
    try:
        values = parse_qs(query, keep_blank_values=True, max_num_fields=20).get(key, [DEFAULT_TIMEZONE])
        return browser_zone(values[0]) if len(values) == 1 else None
    except ValueError:
        return None


def annual_goal(store, year):
    row = store.connection.execute('SELECT * FROM annual_mileage_goals WHERE year=?', (year,)).fetchone()
    return dict(row) if row else None


def set_annual_goal(store, year, text):
    value = target_miles(text) if text is not None else None
    if type(year) is not int or not 1 <= year <= 9999:
        raise ValueError('Invalid goal year.')
    with store._transaction(write=True):
        if value is None:
            store.connection.execute('DELETE FROM annual_mileage_goals WHERE year=?', (year,))
        else:
            store.connection.execute('''INSERT INTO annual_mileage_goals VALUES (?,?,?)
                ON CONFLICT(year) DO UPDATE SET target_miles=excluded.target_miles, updated_at=excluded.updated_at''',
                (year, str(value), datetime.now(timezone.utc).isoformat()))
