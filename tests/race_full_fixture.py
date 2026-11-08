"""Synthetic 17-race history with 14 FIT/export rides and three API-only rides.

Mirrors the diagnosed workflow's size and source mix, not the Owner's records.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

from fit_fixture import make_fit
from test_rideworks_export import csv_bytes, row as export_row
from test_race_sections import image
from rideworks import race_results as race
from rideworks.race_matching import batch_matches
from rideworks.strava_api import apply_observations


def seed_history(store):
    words = ['Amber', 'Birch', 'Cedar', 'Dawn', 'Elm', 'Fern', 'Grove', 'Hazel',
             'Iris', 'Juniper', 'Kestrel', 'Linden', 'Maple', 'North', 'Orchid', 'Pine', 'Quartz']
    rows, starts = [], []
    for index, word in enumerate(words):
        start = datetime(2024, 3, 1, 11, 10, tzinfo=timezone.utc) + timedelta(days=index)
        rows.append(dict(date=start.date().isoformat(), start_time='11:10',
                         event=f'Stage {index % 5 + 1} {word}Circuit {word}Trail', race_group='0-200',
                         finish=index + 1, avg_watts=160 + index, race_score=180 + index,
                         race_score_change=index % 7 - 3))
        starts.append(start + timedelta(seconds=13 + 16 * index))
    rows[14]['event'] = 'MeridianCircuit by Lumen'
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'synthetic.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('activities.csv', csv_bytes([
                export_row(str(i + 1), filename=f'activities/{i}.fit', title=row['event'],
                           date=starts[i].replace(tzinfo=None).isoformat())
                for i, row in enumerate(rows[:14])]))
            for i, start in enumerate(starts[:14]):
                seconds = int((start - datetime(1989, 12, 31, tzinfo=timezone.utc)).total_seconds())
                archive.writestr(f'activities/{i}.fit', make_fit(
                    avg_power=230 + i, session_start_time=seconds, session_timestamp=seconds + 2))
        result = store.import_strava_export(path)
        assert not result['failures'], result['failures']
    apply_observations(store, [dict(id=100 + i, name=f'Zwift - Race: {row["event"]} (E)', start_date=start.isoformat(),
                                  type='Ride', sport_type='VirtualRide', elapsed_time=1200)
                              for i, (row, start) in enumerate(zip(rows[14:], starts[14:]))],
                       'synthetic', int(starts[-1].timestamp()) + 3600)
    # Deliberately differ from the stored title in one long word, as in the
    # privately checked live import. Both names here are invented.
    rows[14]['event'] = 'MeridiagCircuit by Lumen'
    return rows


def stage(store, rows):
    with patch.object(race, 'configuration', return_value=('', 'gpt-6-luna', 10_000_000)):
        return race.stage_import(store, image(1525, 1864), 'UTC',
                                 extractor=lambda *_: (rows, None))


def items(store, rows):
    decisions = batch_matches(rows, 'UTC', race.matching_activities(store))
    return [dict(values=dict(row), group='different', action='confirm', replace=False,
                 shown_activity=decision['activity_id'],
                 shown_revision=race.result_revision(*race.result_state(store, decision['activity_id'])))
            for row, decision in zip(rows, decisions)]


def seed_restorations(store, rows):
    old = stage(store, rows[:11])
    race.commit_rows(store, old, items(store, rows[:11]), overlap_choices={}, list_acknowledged=True)
    for item in items(store, rows[:11]):
        race.remove_result(store, item['shown_activity'], item['shown_revision'])
