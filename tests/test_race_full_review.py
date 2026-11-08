"""Full-image and restoration regressions derived from the live import findings."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from race_full_fixture import seed_history, seed_restorations, stage, items
from rideworks import race_results as race
from rideworks.store import Store
from rideworks.web import Application


class FullReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name))
        self.addCleanup(self.store.close)
        self.app = Application(Path(temp.name))
        self.app.settings.port = 8766
        self.rows = seed_history(self.store)
        seed_restorations(self.store, self.rows)
        self.identity = stage(self.store, self.rows)
        self.route = '/race-results/review/' + self.identity

    def form(self, page=None):
        page = page or self.app.get(self.route)[2]
        fields = {'nonce': self.app.settings.nonce, 'timezone': 'UTC', 'operation': 'confirm',
                  'list_acknowledged': 'yes'}
        for index, item in enumerate(items(self.store, self.rows)):
            for field, value in item['values'].items():
                fields[f'{index}.{field}'] = '' if value is None else str(value)
            fields[f'{index}.shown_activity'] = item['shown_activity']
            fields[f'{index}.shown_revision'] = item['shown_revision']
        token = re.search(rb'name="confirmation_token" value="([0-9a-f]{64})"', page)
        fields['confirmation_token'] = token.group(1).decode()
        return fields

    def post(self, fields):
        return self.app.post(self.route, urlencode(fields).encode(), 'http://localhost:8766')

    def assert_no_confirmed_changes(self):
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_result_history').fetchone()[0], 11)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_result_removals').fetchone()[0], 11)

    def test_full_default_seventeen_matches_and_explicit_final_restore_action(self):
        page = self.app.get(self.route)[2]
        self.assertIn(b'17 races identified', page)
        self.assertIn(b'17 automatically matched', page)
        self.assertIn(b'0 matching errors', page)
        self.assertIn(b'11 of these have previously been removed and will be restored if you import.', page)
        self.assertIn(b'Import 17 races (restore 11 previously removed)', page)
        self.assertNotIn(b'Restoration approval required', page)
        self.assertIn(b'One character differs in a long event word', page)
        self.assertIn(b'Zwift - Race: MeridianCircuit by Lumen (E)', page)
        self.assertNotIn(b'need attention', page)
        self.assertEqual(page.count(b'class="race-candidate-row"'), 17)
        self.assertNotIn(b'name="restore_displayed"', page)
        self.assertEqual(page.count(b'type="checkbox"'), 1)
        self.assertEqual(page.count(b'<td>Matched\n'), 17)
        self.assertNotIn(b'class="race-overlap"', page)
        self.assertNotIn(b'Approve replacement</label>', page)
        self.assertNotIn(b'.replace"', page)
        sections = self.store.connection.execute('SELECT * FROM race_import_sections WHERE import_id=?', (self.identity,)).fetchall()
        self.assertEqual(len(sections), 1)
        self.assertEqual((sections[0]['top'], sections[0]['bottom']), (0, 1864))
        self.assertEqual(sections[0]['prompt_version'], race.PROMPT_VERSION)
        self.assertIn(b'<option value="full" selected>', self.app.get('/race-results/import')[2])
        fields = self.form(page)
        consent = fields.pop('confirmation_token')
        self.assertEqual(self.post(fields)[0], 400)
        self.assert_no_confirmed_changes()
        fields['confirmation_token'] = 'invalid'
        self.assertEqual(self.post(fields)[0], 400)
        self.assert_no_confirmed_changes()
        fields['confirmation_token'] = consent
        before = self.store.activity_history()
        self.assertEqual(self.post(fields)[0], 200)
        self.assertEqual(self.store.activity_history(), before)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 17)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_result_history').fetchone()[0], 28)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_result_removals').fetchone()[0], 11)
        provenance = json.loads(self.store.connection.execute(
            'SELECT decisions_json FROM race_import_reconciliations WHERE import_id=?', (self.identity,)).fetchone()[0])
        self.assertEqual(len(provenance['import_confirmation']['restorations']), 11)
        self.assertEqual(provenance['import_confirmation']['action'], 'confirm')
        self.assertEqual(provenance['matching_version'], 'race-automatic-v3')
        self.assertTrue(all(group['match_evidence']['time_source_id'] for group in provenance['groups']))
        self.assertEqual(json.loads(race.load_import(self.store, self.identity)['rows_json']), self.rows)
        self.assertEqual(self.post(fields)[0], 400)  # stale consent cannot replay after restoration
        activity_id = fields['0.shown_activity']
        race.remove_result(self.store, activity_id, race.result_revision(*race.result_state(self.store, activity_id)))
        self.assertEqual(self.post(fields)[0], 400)  # nor resurrect a subsequent removal
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 16)

    def test_preview_and_acknowledgment_cannot_restore_without_final_action(self):
        fields = self.form()
        fields['operation'] = 'preview'
        self.assertEqual(self.post(fields)[0], 200)
        self.assert_no_confirmed_changes()
        fields['operation'] = 'confirm'
        fields.pop('list_acknowledged')
        self.assertEqual(self.post(fields)[0], 400)
        self.assert_no_confirmed_changes()

    def test_final_action_binds_nonrestoration_assignments_and_history(self):
        fields = self.form()
        activities = race.matching_activities(self.store)
        first, second = (fields[f'{index}.shown_activity'] for index in (11, 12))
        for activity in activities:
            if activity['activity_id'] in (first, second):
                activity['activity_id'] = second if activity['activity_id'] == first else first
        fields['11.shown_activity'], fields['12.shown_activity'] = second, first
        with patch('rideworks.race_results.matching_activities', return_value=activities):
            status, _, page = self.post(fields)
        self.assertEqual(status, 400)
        self.assertIn(b'displayed import or saved history changed', page)
        self.assert_no_confirmed_changes()
        fields = self.form()
        # History alone changing also invalidates the action, even if current
        # result/tombstone and all eleven restorations are unchanged.
        self.store.connection.execute('INSERT INTO race_result_history VALUES (?,?,?,?,?,?)',
            ('synthetic-revision', first, self.identity, json.dumps(self.rows[11]), 'UTC', 'synthetic'))
        self.assertEqual(self.post(fields)[0], 400)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)

    def test_edited_values_timezone_and_missing_activity_invalidate_consent(self):
        for key, value in (('0.avg_watts', '222'), ('timezone', 'Etc/UTC'), ('16.date', '2024-06-20')):
            with self.subTest(key=key):
                fields = self.form()
                fields[key] = value
                self.assertEqual(self.post(fields)[0], 400)
                self.assert_no_confirmed_changes()

    def test_new_removal_invalidates_scope_without_writes(self):
        fields = self.form()
        old = stage(self.store, self.rows[11:12])
        race.commit_rows(self.store, old, items(self.store, self.rows[11:12]), overlap_choices={}, list_acknowledged=True)
        item = items(self.store, self.rows[11:12])[0]
        race.remove_result(self.store, item['shown_activity'], item['shown_revision'])
        before = list(self.store.connection.execute('SELECT * FROM race_result_history'))
        self.assertEqual(self.post(fields)[0], 400)
        self.assertEqual(list(self.store.connection.execute('SELECT * FROM race_result_history')), before)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)

    def test_bulk_restoration_does_not_approve_replacement_or_another_import(self):
        previous = dict(self.rows[-1], avg_watts=111)
        old = stage(self.store, [previous])
        race.commit_rows(self.store, old, items(self.store, [previous]), overlap_choices={}, list_acknowledged=True)
        fields = self.form()
        self.assertIn(b'1 replacements to approve', self.app.get(self.route)[2])
        self.assertEqual(self.post(fields)[0], 400)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_result_history').fetchone()[0], 12)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_result_removals').fetchone()[0], 11)
        other = stage(self.store, self.rows)
        self.assertEqual(self.app.post('/race-results/review/' + other, urlencode(fields).encode(),
                                      'http://localhost:8766')[0], 400)
        fields['16.replace'] = 'yes'
        self.assertEqual(self.post(fields)[0], 200)
