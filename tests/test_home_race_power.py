"""Synthetic Home race evidence and presentation regression coverage."""
import json
import re
import tempfile
from pathlib import Path
from unittest import TestCase

from rideworks.home import home_page, recent_race_watts
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize


class HomeRacePowerTests(TestCase):
    def test_active_removed_missing_null_zero_and_bounded_lookup(self):
        with tempfile.TemporaryDirectory() as temporary, Store(Path(temporary)) as store:
            items = [normalize(dict(id=i, name=f'Synthetic <ride {i}>', type='Ride', sport_type='Ride',
                                    start_date=f'2026-10-{i:02}T12:00:00Z', elapsed_time=1200,
                                    distance=1609.344, average_watts=222)) for i in range(1, 7)]
            apply_observations(store, items, 42, 1790000000)
            ids = {int(row['external_id']): row['activity_id'] for row in store.connection.execute(
                'SELECT external_id, activity_id FROM strava_api_activities')}
            store.connection.execute('INSERT INTO race_imports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                ('import', 'zwift_racing_profile_screenshot', 'synthetic', 1, 'image/png', 'synthetic',
                 '2026-10-01', None, 'synthetic', 'v1', 'v1', '[]', None))
            for i, watts in ((1, 169), (3, 300), (4, None), (5, 0), (6, 777)):
                store.connection.execute('INSERT INTO race_results VALUES (?,?,?,?,?)',
                    (ids[i], 'import', json.dumps({'avg_watts': watts}), None, '2026-10-01'))
            store.connection.execute('INSERT INTO race_result_removals SELECT ?, activity_id, import_id, values_json, display_timezone, accepted_at, ? FROM race_results WHERE activity_id=?',
                                     ('removal', '2026-10-02', ids[3]))
            store.connection.execute('DELETE FROM race_results WHERE activity_id=?', (ids[3],))
            statements = []
            store.connection.set_trace_callback(statements.append)
            values = recent_race_watts(store, [{'activity_id': ids[i]} for i in range(1, 6)])
            queries = [s for s in statements if 'FROM race_results' in s]
            self.assertEqual(len(queries), 1)
            self.assertIn(' WHERE activity_id IN (', queries[0])
            self.assertNotIn(ids[6], values)
            self.assertEqual(values, {ids[1]: 169, ids[4]: None, ids[5]: 0})
            statements.clear()
            self.assertEqual(recent_race_watts(store, []), {})
            self.assertFalse(statements)
            html = home_page(store, 'home_tz=UTC')
            self.assertLess(html.index('<th>Avg Pwr</th>'), html.index('<th>Race Avg W</th>'))
            for i, expected in ((1, '169 W'), (2, '—'), (3, '—'), (4, '—'), (5, '0 W')):
                row = re.search(r'<tr class="home-recent-row" data-activity-id="' + re.escape(ids[i]) + r'">(.*?)</tr>', html).group(1)
                self.assertIn('class="home-avg-power">222 W</td>', row)
                self.assertIn('class="home-race-power" title="Zwift screenshot race average">' + expected + '</td>', row)
                self.assertIn('href="/activities/' + ids[i] + '"', row)
                self.assertIn(f'Synthetic &lt;ride {i}&gt;', row)
