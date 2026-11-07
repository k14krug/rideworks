"""Synthetic cross-import identity and atomic correction tests."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from rideworks import race_results as race
from rideworks.race_identity import identity_key, possible_associations
from rideworks.race_matching import batch_matches
from rideworks.store import Store
from rideworks.web import Application
from test_race_sections import image, result


class IdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'store'
        self.store = Store(self.root)
        self.addCleanup(self.store.close)
        self.app = Application(self.root)
        self.app.settings.port = 8766
        config = patch('rideworks.race_results.configuration', return_value=('', 'gpt-6-luna', 10_000_000))
        config.start()
        self.addCleanup(config.stop)

    def stage(self, rows, payload=None):
        return race.stage_import(self.store, payload or image(), 'UTC',
                                 extractor=lambda *_: (rows, None), mode='full')

    def activity(self, row):
        identity = str(uuid4())
        self.store.connection.execute('INSERT INTO activities VALUES (?,?)', (identity, 'synthetic'))
        return {'activity_id': identity, 'start_time': row['date'] + 'T' + row['start_time'] + ':00+00:00',
                'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
                'title': row['event'], 'match_watts': None, 'match_watts_source': None}

    def item(self, row, activity, **extra):
        return {'values': dict(row), 'group': 'different', 'action': 'confirm', 'replace': False,
                'shown_activity': activity['activity_id'], 'shown_revision': 'new', **extra}

    def prior(self, identity, row, activity, *, count=None, members=(1,)):
        self.store.connection.execute('INSERT INTO race_results VALUES (?,?,?,?,?)',
            (activity['activity_id'], identity, json.dumps(row), 'UTC', 'old-accepted'))
        if count is not None:
            provenance = {'timezone': 'UTC', 'groups': [{'activity_id': activity['activity_id'],
                           'values': row, 'observations': list(members)}]}
            self.store.connection.execute('INSERT INTO race_import_reconciliations VALUES (?,?,?,?,?)',
                (str(uuid4()), identity, 'old-recorded', count, json.dumps(provenance)))

    def candidates(self, identity, rows, activities):
        source = race.load_import(self.store, identity)
        groups = [[i] for i in range(len(rows))]
        decisions = batch_matches(rows, 'UTC', activities)
        return possible_associations(self.store, source, groups, rows, decisions, 'UTC', len(rows))

    def commit(self, identity, items, activities):
        with patch('rideworks.race_results.matching_activities', return_value=activities):
            return race.commit_rows(self.store, identity, items, visible_count=len(items), visible_confirmed=True)

    def test_same_screenshot_single_reviewed_row_requires_separate_removal(self):
        old, corrected = result(date='2024-11-06'), result(date='2024-11-08')
        old_import, new_import = self.stage([old]), self.stage([corrected])
        old_ride, new_ride = self.activity(old), self.activity(corrected)
        self.prior(old_import, old, old_ride, count=1)
        candidate = self.candidates(new_import, [corrected], [new_ride])[0][0]
        self.assertTrue(candidate['same_image'])
        self.assertTrue(candidate['proven_same'])
        item = self.item(corrected, new_ride, identity={identity_key(old_ride['activity_id']):
                                                       'different:' + candidate['token']})
        with self.assertRaisesRegex(race.RaceError, 'different activity'):
            self.commit(new_import, [item], [new_ride])
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_result_removals').fetchone()[0], 0)
        race.remove_result(self.store, old_ride['activity_id'],
                           race.result_revision(*race.result_state(self.store, old_ride['activity_id'])))
        with self.assertRaisesRegex(race.RaceError, 'changed'):
            self.commit(new_import, [item], [new_ride])
        item['identity'] = {}
        self.assertEqual(self.commit(new_import, [item], [new_ride])['added'], 1)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_result_removals').fetchone()[0], 1)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM activities').fetchone()[0], 2)

    def test_derived_list_count_does_not_prove_a_single_physical_source_row(self):
        old, corrected = result(date='2024-11-06'), result(date='2024-11-08')
        old_import, new_import = self.stage([old]), self.stage([corrected])
        old_ride, new_ride = self.activity(old), self.activity(corrected)
        self.prior(old_import, old, old_ride, count=1)
        stored = self.store.connection.execute(
            'SELECT reconciliation_id, decisions_json FROM race_import_reconciliations WHERE import_id=?',
            (old_import,)).fetchone()
        provenance = json.loads(stored['decisions_json'])
        provenance['count_type'] = 'derived_distinct_races'
        self.store.connection.execute('UPDATE race_import_reconciliations SET decisions_json=? WHERE reconciliation_id=?',
                                      (json.dumps(provenance), stored['reconciliation_id']))
        candidate = self.candidates(new_import, [corrected], [new_ride])[0][0]
        self.assertFalse(candidate['proven_same'])
        with self.assertRaisesRegex(race.RaceError, 'unresolved'):
            self.commit(new_import, [self.item(corrected, new_ride)], [new_ride])
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)

    def test_different_image_recurring_race_requires_scoped_distinct_choice(self):
        old, new = result(date='2024-11-06'), result(date='2024-11-08')
        old_import = self.stage([old], image(height=400))
        new_import = self.stage([new], image(height=500))
        old_ride, new_ride = self.activity(old), self.activity(new)
        self.prior(old_import, old, old_ride)
        candidate = self.candidates(new_import, [new], [new_ride])[0][0]
        self.assertFalse(candidate['same_image'])
        item = self.item(new, new_ride)
        with self.assertRaisesRegex(race.RaceError, 'unresolved'):
            self.commit(new_import, [item], [new_ride])
        item['identity'] = {identity_key(old_ride['activity_id']): 'same:' + candidate['token']}
        with self.assertRaisesRegex(race.RaceError, 'different activity'):
            self.commit(new_import, [item], [new_ride])
        item['identity'] = {identity_key(old_ride['activity_id']): 'different:' + candidate['token']}
        self.assertEqual(self.commit(new_import, [item], [new_ride])['added'], 1)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 2)
        record = self.store.connection.execute(
            'SELECT decisions_json FROM race_import_reconciliations WHERE import_id=?', (new_import,)).fetchone()
        decision = json.loads(record[0])['identity_decisions'][0]
        self.assertEqual(decision['activity_id'], old_ride['activity_id'])
        self.assertEqual(decision['new_activity_id'], new_ride['activity_id'])
        self.assertEqual(decision['new_observations'], [1])
        self.assertEqual(decision['decision'], 'different')

    def test_candidate_window_and_same_image_ignore_ocr_date(self):
        current = result(date='2024-11-08')
        new_import = self.stage([current], image(height=500))
        new_ride = self.activity(current)
        near = result(date='2024-11-05', start_time='11:43')
        too_far_date = result(date='2024-11-04')
        too_far_time = result(date='2024-11-07', start_time='11:44')
        same_image = result(date='2023-01-01', event='Unrelated transcription', start_time='08:00')
        for row, payload in ((near, image(height=400)), (too_far_date, image(height=401)),
                             (too_far_time, image(height=402)), (same_image, image(height=500))):
            identity, activity = self.stage([row], payload), self.activity(row)
            self.prior(identity, row, activity)
        candidates = self.candidates(new_import, [current], [new_ride])[0]
        self.assertEqual({candidate['values']['date'] for candidate in candidates}, {'2024-11-05', '2023-01-01'})
        self.assertEqual(sum(candidate['same_image'] for candidate in candidates), 1)

    def test_same_hash_multiple_rows_and_legacy_provenance_are_not_assumed_same(self):
        old, new = result(date='2024-11-06'), result(date='2024-11-08')
        old_import, new_import = self.stage([old, new]), self.stage([old, new])
        old_ride, new_ride = self.activity(old), self.activity(new)
        self.prior(old_import, old, old_ride, count=2)
        candidates = self.candidates(new_import, [old, new], [old_ride, new_ride])
        self.assertEqual(candidates[0], [])
        candidate = candidates[1][0]
        self.assertTrue(candidate['same_image'])
        self.assertFalse(candidate['proven_same'])
        items = [self.item(old, old_ride, shown_revision=race.result_revision(*race.result_state(self.store, old_ride['activity_id']))),
                 self.item(new, new_ride, identity={identity_key(old_ride['activity_id']): 'different:' + candidate['token']})]
        self.assertEqual(self.commit(new_import, items, [old_ride, new_ride])['added'], 1)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 2)

    def test_same_import_shared_observation_is_known_same_source_row(self):
        old, new = result(date='2024-11-06'), result(date='2024-11-08')
        other = result(date='2024-11-09', event='Stage 3 Lakeview')
        identity = self.stage([old, other])
        old_ride, new_ride, other_ride = self.activity(old), self.activity(new), self.activity(other)
        self.prior(identity, old, old_ride, count=2, members=(1,))
        candidate = self.candidates(identity, [new, other], [new_ride, other_ride])[0][0]
        self.assertTrue(candidate['proven_same'])
        item = self.item(new, new_ride, identity={identity_key(old_ride['activity_id']):
                                                  'different:' + candidate['token']})
        with self.assertRaisesRegex(race.RaceError, 'different activity'):
            self.commit(identity, [item, self.item(other, other_ride)], [new_ride, other_ride])

    def test_stale_revision_and_missing_image_block_all_writes(self):
        old, first, second = result(date='2024-11-06'), result(date='2024-11-08'), result(date='2024-11-09', event='Stage 3 Lakeview')
        old_import = self.stage([old], image(height=400))
        new_import = self.stage([first, second], image(height=500))
        old_ride, first_ride, second_ride = self.activity(old), self.activity(first), self.activity(second)
        self.prior(old_import, old, old_ride)
        candidate = self.candidates(new_import, [first, second], [first_ride, second_ride])[0][0]
        items = [self.item(first, first_ride, identity={identity_key(old_ride['activity_id']): 'different:' + candidate['token']}),
                 self.item(second, second_ride)]
        self.store.connection.execute('UPDATE race_results SET values_json=? WHERE activity_id=?',
                                      (json.dumps(dict(old, avg_watts=999)), old_ride['activity_id']))
        with self.assertRaisesRegex(race.RaceError, 'changed'):
            self.commit(new_import, items, [first_ride, second_ride])
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)
        candidate = self.candidates(new_import, [first, second], [first_ride, second_ride])[0][0]
        items[0]['identity'] = {identity_key(old_ride['activity_id']): 'different:' + candidate['token']}
        source = race.load_import(self.store, old_import)
        (self.store.data_dir / source['image_path']).unlink()
        with self.assertRaisesRegex(race.RaceError, 'screenshot'):
            self.commit(new_import, items, [first_ride, second_ride])
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)

    def test_distinct_prior_cannot_be_replaced_by_another_row_in_batch(self):
        old, new = result(date='2024-11-06'), result(date='2024-11-08')
        changed_old = dict(old, avg_watts=999)
        old_import = self.stage([old], image(height=400))
        new_import = self.stage([changed_old, new], image(height=500))
        old_ride, new_ride = self.activity(old), self.activity(new)
        self.prior(old_import, old, old_ride)
        candidate = self.candidates(new_import, [changed_old, new], [old_ride, new_ride])[1][0]
        old_revision = race.result_revision(*race.result_state(self.store, old_ride['activity_id']))
        items = [self.item(changed_old, old_ride, shown_revision=old_revision, replace=True),
                 self.item(new, new_ride, identity={identity_key(old_ride['activity_id']): 'different:' + candidate['token']})]
        with self.assertRaisesRegex(race.RaceError, 'would be replaced'):
            self.commit(new_import, items, [old_ride, new_ride])
        saved = self.store.connection.execute('SELECT values_json FROM race_results').fetchone()
        self.assertEqual(json.loads(saved[0]), old)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)

    def test_removed_and_restored_prior_invalidates_earlier_distinct_choice(self):
        old, new = result(date='2024-11-06'), result(date='2024-11-08')
        old_import = self.stage([old], image(height=400))
        new_import = self.stage([new], image(height=500))
        old_ride, new_ride = self.activity(old), self.activity(new)
        self.prior(old_import, old, old_ride)
        candidate = self.candidates(new_import, [new], [new_ride])[0][0]
        item = self.item(new, new_ride, identity={identity_key(old_ride['activity_id']): 'different:' + candidate['token']})
        race.remove_result(self.store, old_ride['activity_id'],
                           race.result_revision(*race.result_state(self.store, old_ride['activity_id'])))
        removed_revision = race.result_revision(*race.result_state(self.store, old_ride['activity_id']))
        restored = self.item(old, old_ride, shown_revision=removed_revision, replace=True)
        self.assertEqual(self.commit(old_import, [restored], [old_ride])['added'], 1)
        with self.assertRaisesRegex(race.RaceError, 'changed'):
            self.commit(new_import, [item], [new_ride])
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)

    def test_http_preview_displays_legacy_pair_and_rejects_unreviewed_commit(self):
        old, new = result(date='2024-11-06'), result(date='2024-11-08')
        old_import, new_import = self.stage([old]), self.stage([new])
        old_ride, new_ride = self.activity(old), self.activity(new)
        self.prior(old_import, old, old_ride)
        fields = {'nonce': self.app.settings.nonce, 'timezone': 'UTC', 'operation': 'preview',
                  'list_acknowledged': 'yes',
                  '0.shown_activity': '', '0.shown_revision': 'new'}
        fields.update({f'0.{key}': '' if value is None else str(value) for key, value in new.items()})
        route = '/race-results/review/' + new_import
        with patch('rideworks.race_page.matching_activities', return_value=[old_ride, new_ride]):
            status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'Possible existing attachment', page)
        self.assertIn(b'Different races', page)
        self.assertIn(b'Previous original screenshot', page)
        self.assertIn(b'value="confirm" disabled', page)
        fields.update({'operation': 'confirm', '0.shown_activity': new_ride['activity_id']})
        with patch('rideworks.race_results.matching_activities', return_value=[old_ride, new_ride]):
            self.assertEqual(self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')[0], 400)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)

    def test_http_distinct_decision_revalidates_and_records_provenance(self):
        old, new = result(date='2024-11-06'), result(date='2024-11-08')
        old_import = self.stage([old], image(height=400))
        new_import = self.stage([new], image(height=500))
        old_ride, new_ride = self.activity(old), self.activity(new)
        self.prior(old_import, old, old_ride)
        candidate = self.candidates(new_import, [new], [new_ride])[0][0]
        fields = {'nonce': self.app.settings.nonce, 'timezone': 'UTC', 'operation': 'preview',
                  'list_acknowledged': 'yes',
                  '0.shown_activity': new_ride['activity_id'], '0.shown_revision': 'new',
                  '0.identity.' + identity_key(old_ride['activity_id']): 'different:' + candidate['token']}
        fields.update({f'0.{key}': '' if value is None else str(value) for key, value in new.items()})
        route = '/race-results/review/' + new_import
        with patch('rideworks.race_page.matching_activities', return_value=[old_ride, new_ride]):
            status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'value="confirm" disabled', page)
        fields['operation'] = 'confirm'
        with patch('rideworks.race_results.matching_activities', return_value=[old_ride, new_ride]):
            status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'Added 1', page)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 2)

    def test_changed_current_source_and_corrupt_screenshot_invalidate_review(self):
        old, new = result(date='2024-11-06'), result(date='2024-11-08')
        old_import = self.stage([old], image(height=400))
        new_import = self.stage([new], image(height=500))
        old_ride, new_ride = self.activity(old), self.activity(new)
        self.prior(old_import, old, old_ride)
        candidate = self.candidates(new_import, [new], [new_ride])[0][0]
        item = self.item(new, new_ride, identity={identity_key(old_ride['activity_id']):
                                                  'different:' + candidate['token']})
        changed = dict(new, avg_watts=999)
        self.store.connection.execute('UPDATE race_import_sections SET output_json=? WHERE import_id=?',
                                      (json.dumps([changed]), new_import))
        self.store.connection.execute('UPDATE race_imports SET rows_json=? WHERE import_id=?',
                                      (json.dumps([changed]), new_import))
        with self.assertRaisesRegex(race.RaceError, 'changed'):
            self.commit(new_import, [item], [new_ride])
        source = race.load_import(self.store, new_import)
        (self.store.data_dir / source['image_path']).write_bytes(b'corrupted')
        with self.assertRaisesRegex(race.RaceError, 'integrity'):
            self.commit(new_import, [item], [new_ride])
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)
