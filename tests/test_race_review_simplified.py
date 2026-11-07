"""Synthetic race-first review and overlap decision tests."""

import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from rideworks import race_results as race
from rideworks.race_reconcile import overlap_candidates, overlap_groups
from rideworks.race_results import RaceError
from rideworks.store import Store
from rideworks.web import Application
from test_race_results import result
from test_race_sections import image


class OverlapReviewTests(unittest.TestCase):
    def test_only_plausible_cross_section_pair_requires_a_decision(self):
        sections = [{'top': 0, 'bottom': 600}, {'top': 339, 'bottom': 939}]
        races = [result(date=f'2026-09-{day:02d}', event=f'Synthetic Route {day}')
                 for day in range(10, 27)]
        repeated = result(date='2026-09-27', event='Stage 3 Electric Break')
        observed = ([{'section': 0, 'row': row} for row in races + [repeated]] +
                    [{'section': 1, 'row': dict(repeated)}])
        pairs = overlap_candidates(observed, sections)
        self.assertEqual(pairs, [(17, 18)])
        with self.assertRaisesRegex(RaceError, 'possible overlap'):
            overlap_groups(observed, sections, {})
        groups, unresolved = overlap_groups(observed, sections, {(17, 18): 'same'})
        self.assertEqual(len(groups), 18)
        self.assertEqual(groups[-1], [17, 18])
        self.assertFalse(unresolved)
        groups, _ = overlap_groups(observed, sections, {(17, 18): 'different'})
        self.assertEqual(len(groups), 19)

    def test_wrapped_title_fragment_is_a_candidate_without_date(self):
        sections = [{'top': 0, 'bottom': 600}, {'top': 339, 'bottom': 939}]
        observed = [{'section': 0, 'row': result(event='Stage 4 Loop de Loop')},
                    {'section': 1, 'row': result(date=None, event='Loop')}]
        self.assertEqual(overlap_candidates(observed, sections), [(0, 1)])

    def test_equivalent_date_formats_are_considered_for_overlap(self):
        sections = [{'top': 0, 'bottom': 600}, {'top': 339, 'bottom': 939}]
        observed = [{'section': 0, 'row': result(date='9/27/2026', event='Stage 3 Electric Break', finish=None)},
                    {'section': 1, 'row': result(date='2026-09-27', event='Stage 3 Electric Break', finish=None)}]
        self.assertEqual(overlap_candidates(observed, sections), [(0, 1)])


class RaceListIntegrationTests(unittest.TestCase):
    def test_conflicting_overlap_needs_value_bound_pair_verification(self):
        for field, changed in (('race_score', 199), ('race_score_change', -4),
                               ('date', '2026-09-26'), ('avg_watts', 199)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp, Store(Path(temp)) as store:
                app = Application(Path(temp))
                app.settings.port = 8766
                first = result(date='2026-09-27', event='Stage 3 Electric Break',
                               race_score=184, race_score_change=2, avg_watts=175)
                second = dict(first, **{field: changed})
                outputs = iter([[first], [second]])
                with patch('rideworks.race_results.configuration', return_value=('', 'gpt-6-luna', 10_000_000)):
                    identity = race.stage_import(store, image(), 'UTC', extractor=lambda *_: (next(outputs), None))
                activity_id = str(uuid4())
                store.connection.execute('INSERT INTO activities VALUES (?,?)', (activity_id, 'synthetic'))
                activities = [{'activity_id': activity_id, 'start_time': first['date'] + 'T' + first['start_time'] + ':00+00:00',
                               'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
                               'title': first['event'], 'match_watts': None, 'match_watts_source': None}]
                fields = {'nonce': app.settings.nonce, 'timezone': 'UTC', 'operation': 'confirm',
                          'list_acknowledged': 'yes', 'overlap.0.1': 'same'}
                for index, row in enumerate((first, second)):
                    fields.update({f'{index}.{key}': '' if value is None else str(value) for key, value in row.items()})
                    fields[f'{index}.shown_activity'] = activity_id if index == 0 else ''
                    fields[f'{index}.shown_revision'] = 'new'
                route = '/race-results/review/' + identity
                with patch('rideworks.race_page.matching_activities', return_value=activities), \
                        patch('rideworks.race_results.matching_activities', return_value=activities):
                    status, _, page = app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
                    self.assertEqual(status, 400)
                    self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
                    fields['operation'] = 'preview'
                    status, _, page = app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
                    self.assertEqual(status, 200)
                    self.assertIn(str(first[field]).encode(), page)
                    self.assertIn(str(second[field]).encode(), page)
                    token = re.search(rb'name="verify\.0\.1" value="([0-9a-f]{64})"', page)
                    self.assertIsNotNone(token)
                    fields['verify.0.1'] = token.group(1).decode()
                    fields['operation'] = 'confirm'
                    fields['overlap.0.1'] = 'different'
                    self.assertEqual(app.post(route, urlencode(fields).encode(), 'http://localhost:8766')[0], 400)
                    fields['overlap.0.1'] = 'same'
                    fields['0.avg_watts'] = '201'
                    self.assertEqual(app.post(route, urlencode(fields).encode(), 'http://localhost:8766')[0], 400)
                    self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
                    fields['0.avg_watts'] = str(first['avg_watts'])
                    self.assertEqual(app.post(route, urlencode(fields).encode(), 'http://localhost:8766')[0], 200)
                self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)
                self.assertEqual(json.loads(race.load_import(store, identity)['rows_json']), [first, second])
                record = store.connection.execute('SELECT decisions_json FROM race_import_reconciliations').fetchone()
                self.assertEqual(json.loads(record[0])['overlap_verifications'][0]['observations'], [1, 2])

    def test_seventeen_races_one_overlap_acknowledgment_and_atomic_commit(self):
        with tempfile.TemporaryDirectory() as temp, Store(Path(temp)) as store:
            app = Application(Path(temp))
            app.settings.port = 8766
            rows = [result(date=f'2026-09-{day:02d}', event=f'Synthetic Route {day}')
                    for day in range(1, 9)]
            rows.append(result(date='2026-09-27', event='Stage 3 Electric Break'))
            rows.extend(result(date=f'2026-09-{day:02d}', event=f'Synthetic Route {day}')
                        for day in range(9, 17))
            outputs = iter([rows[:9], rows[8:]])
            with patch('rideworks.race_results.configuration', return_value=('', 'gpt-6-luna', 10_000_000)):
                identity = race.stage_import(store, image(), 'UTC', extractor=lambda *_: (next(outputs), None))
            activities = []
            for row in rows:
                activity_id = str(uuid4())
                store.connection.execute('INSERT INTO activities VALUES (?,?)', (activity_id, 'synthetic'))
                activities.append({'activity_id': activity_id, 'start_time': row['date'] + 'T' + row['start_time'] + ':00+00:00',
                                   'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
                                   'title': row['event'], 'match_watts': None, 'match_watts_source': None})
            observed = rows[:9] + rows[8:]
            fields = {'nonce': app.settings.nonce, 'timezone': 'UTC', 'operation': 'preview'}
            for index, row in enumerate(observed):
                fields.update({f'{index}.{key}': '' if value is None else str(value) for key, value in row.items()})
                activity_index = index if index < 9 else index - 1
                fields[f'{index}.shown_activity'] = '' if index == 9 else activities[activity_index]['activity_id']
                fields[f'{index}.shown_revision'] = 'new'
            route = '/race-results/review/' + identity
            with patch('rideworks.race_page.matching_activities', return_value=activities), \
                    patch('rideworks.race_results.matching_activities', return_value=activities):
                page = app.get(route)[2]
                self.assertEqual(page.count(b'These two extractions may be the same race'), 1)
                self.assertNotIn(b'Source observation', page)
                self.assertNotIn(b'Number of visible physical race rows', page)
                self.assertNotIn(b'Possible section-boundary fragment', page)
                self.assertIn(b'Technical details', page)
                self.assertEqual(page.count(b'class="race-candidate-row"'), 18)
                fields.update({'operation': 'confirm', 'list_acknowledged': 'yes'})
                self.assertEqual(app.post(route, urlencode(fields).encode(), 'http://localhost:8766')[0], 400)
                self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
                fields['overlap.8.9'] = 'same'
                fields['operation'] = 'preview'
                status, _, page = app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
                self.assertEqual(status, 200)
                self.assertEqual(page.count(b'class="race-candidate-row"'), 17)
                self.assertIn(b'17 races identified', page)
                self.assertIn(b'value="confirm" disabled', page)
                fields['operation'] = 'confirm'
                fields.pop('list_acknowledged')
                self.assertEqual(app.post(route, urlencode(fields).encode(), 'http://localhost:8766')[0], 400)
                self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
                fields['list_acknowledged'] = 'yes'
                fields['16.date'] = '2026-10-10'
                self.assertEqual(app.post(route, urlencode(fields).encode(), 'http://localhost:8766')[0], 400)
                self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
                fields['16.date'] = observed[16]['date']
                status, _, page = app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
                self.assertEqual(status, 200)
                self.assertIn(b'Added 17', page)
            saved = store.connection.execute('SELECT visible_count, decisions_json FROM race_import_reconciliations').fetchone()
            provenance = json.loads(saved['decisions_json'])
            self.assertEqual(saved['visible_count'], 17)
            self.assertEqual(provenance['count_type'], 'derived_distinct_races')
            self.assertEqual(provenance['overlap_decisions'], [{'observations': [9, 10], 'decision': 'same'}])
            self.assertEqual(provenance['groups'][8]['observations'], [9, 10])
