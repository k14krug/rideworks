"""Synthetic screenshot tiling, reconciliation, and atomicity tests."""

import io
import json
import re
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from uuid import uuid4

from PIL import Image, ImageChops, ImageDraw

from rideworks import race_results as race
from rideworks.race_cost import estimate_cost
from rideworks.race_reconcile import observations, reconcile
from rideworks.race_sections import crop_image, plan_sections
from rideworks.store import Store
from rideworks.web import Application
from test_race_results import FakeOpener, FakeResponse, USER_PROMPT, result


SECTION_ELIGIBILITY = '''This image is one horizontal section of a larger Zwift Racing Profile RACE RESULTS screenshot. Neighboring sections overlap. Extract rows visible in THIS section only; do not infer or reconstruct missing pixels.

SECTION BOUNDARIES
- Top edge: {TOP_EDGE_TYPE}.
- Bottom edge: {BOTTOM_EDGE_TYPE}.
  TOP_EDGE_TYPE / BOTTOM_EDGE_TYPE must each be "original screenshot edge" or "internal crop boundary", determined from the section's original-image pixel coordinates (not by the model).

WHICH ROWS TO EXTRACT
- At an INTERNAL CROP BOUNDARY, do not extract a race row that is cut off by that edge. A row must be visibly complete within this section, including its row beginning, the FINISH cell, the DATE/Time cell area, and the beginning of its blue event title. The row's bottom/content must also be visible. Such cut rows should appear in another overlapping section.
- A wrapped blue race title belongs to ONE physical table row. Join its visible lines into one event title. A continuation such as "Loop" at the top of a section is NOT a new race when the beginning of the title/row is outside this section. Do not make a row out of the smaller black route subtitle.
- If an edge is an ORIGINAL SCREENSHOT EDGE (not an internal crop boundary), apply the original screenshot's policy for a partially visible but identifiable row; do not discard it solely because the uploaded image itself was cropped.
- A complete interior row may have individual unreadable or dashed values. Extract the row and set only the unreadable fields to null. Do not treat null DATE or null watts alone as proof that a row is a crop fragment.
- Do not turn headers, separators, continuation lines, other columns or duplicate renderings into additional races. Return rows in top-to-bottom order.
- If no complete eligible race rows are visible in this section, return {"races": []} in the required schema. Do not guess missing rows.'''


def image(width=768, height=939):
    screenshot = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(screenshot)
    for index in range(17):
        y = 50 + index * 52
        draw.text((10, y), f'Synthetic row {index + 1} - event', fill='black')
        draw.text((250, y + 12), 'wrapped title', fill='blue')
        draw.line((10, y + 45, 50 if index == 5 else width - 10, y + 45), fill='gray')
    output = io.BytesIO()
    screenshot.save(output, format='PNG')
    return output.getvalue()


def usage():
    return {'input_tokens': 1000, 'output_tokens': 100, 'service_tier': 'default',
            'input_tokens_details': {'cached_tokens': 200, 'cache_write_tokens': 100},
            'output_tokens_details': {'reasoning_tokens': 80}}


class SectionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = Store(self.root / 'store')
        self.addCleanup(self.store.close)
        self.app = Application(self.root / 'store')
        self.app.settings.port = 8766
        patcher = patch('rideworks.race_results.configuration', return_value=('', 'gpt-6-luna', 10_000_000))
        patcher.start()
        self.addCleanup(patcher.stop)

    def staged(self, outputs, payload=None):
        iterator = iter(outputs)
        return race.stage_import(self.store, payload or image(), 'UTC',
                                 extractor=lambda *_: (next(iterator), usage()))

    def item(self, row, identity, *, group='different', corrected=False):
        return {'values': dict(row), 'group': group, 'corrected': corrected, 'action': 'confirm',
                'replace': False, 'shown_activity': identity, 'shown_revision': 'new'}

    def activity(self, row):
        identity = str(uuid4())
        self.store.connection.execute('INSERT INTO activities VALUES (?,?)', (identity, 'synthetic'))
        return {'activity_id': identity, 'start_time': row['date'] + 'T' + row['start_time'] + ':00+00:00',
                'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
                'title': row['event'], 'match_watts': None, 'match_watts_source': None}

    def test_api_receives_exact_section_prompt_and_actual_boundary_metadata(self):
        requests = []
        api = {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': '{"races": []}'}]}]}
        opener = FakeOpener(api)

        def capture(request, timeout):
            requests.append(json.loads(request.data))
            return FakeResponse(api)

        with patch.object(opener, 'open', side_effect=capture), \
                patch('rideworks.race_results.build_opener', return_value=opener), \
                patch('rideworks.race_results.configuration', return_value=('synthetic-key', 'gpt-6-luna', 10_000_000)):
            identity = race.stage_import(self.store, image(height=1800), 'UTC')
            full = race.stage_import(self.store, image(height=400), 'UTC', mode='full')
            single = race.stage_import(self.store, image(height=400), 'UTC')
        bounds = plan_sections(768, 1800)
        self.assertEqual(len(bounds), 4)
        permissive = '- Include a row when enough of its information is readable to identify the race, even if the row border is partially cropped.\n'
        common = USER_PROMPT.replace(permissive, '')
        for request, (top, bottom) in zip(requests[:4], bounds):
            text = request['input'][0]['content'][0]['text']
            expected = (common + '\n\n' + SECTION_ELIGIBILITY
                        .replace('{TOP_EDGE_TYPE}', 'original screenshot edge' if top == 0 else 'internal crop boundary')
                        .replace('{BOTTOM_EDGE_TYPE}', 'original screenshot edge' if bottom == 1800 else 'internal crop boundary'))
            self.assertEqual(text, expected)
            self.assertNotIn(permissive.strip(), text)
            self.assertEqual(request['text']['format']['schema'], race.SCHEMA)
        self.assertEqual(requests[4]['input'][0]['content'][0]['text'], USER_PROMPT)
        single_text = requests[5]['input'][0]['content'][0]['text']
        self.assertIn('Top edge: original screenshot edge.', single_text)
        self.assertIn('Bottom edge: original screenshot edge.', single_text)
        source = race.load_import(self.store, identity)
        self.assertEqual(source['prompt_version'], race.SECTION_PROMPT_VERSION)
        self.assertEqual(race.load_import(self.store, single)['prompt_version'], race.SECTION_PROMPT_VERSION)
        self.assertEqual(race.load_import(self.store, full)['prompt_version'], race.PROMPT_VERSION)
        sections = self.store.connection.execute(
            'SELECT top,bottom,image_height,prompt_version FROM race_import_sections WHERE import_id=? ORDER BY section_index',
            (identity,)).fetchall()
        self.assertEqual([(row['top'], row['bottom']) for row in sections], bounds)
        self.assertTrue(all(row['image_height'] == 1800 and row['prompt_version'] == race.SECTION_PROMPT_VERSION
                            for row in sections))
        page = self.app.get('/race-results/review/' + identity)[2]
        self.assertNotIn(b'This earlier extraction may contain incorrect values', page)

    def test_wrapped_title_fragment_is_retained_and_explicitly_reconciled(self):
        screenshot = Image.new('RGB', (768, 939), 'white')
        draw = ImageDraw.Draw(screenshot)
        draw.text((10, 323), '4 2024-11-08 11:33', fill='black')
        draw.text((250, 323), 'Stage 4 Loop de', fill='blue')
        draw.text((250, 347), 'Loop', fill='blue')
        draw.text((10, 410), 'complete row, unreadable date', fill='black')
        output = io.BytesIO()
        screenshot.save(output, format='PNG')
        bounds = plan_sections(768, 939)
        self.assertEqual(bounds[1][0], 339)
        first_crop = Image.open(io.BytesIO(crop_image(output.getvalue(), *bounds[0])))
        second_crop = Image.open(io.BytesIO(crop_image(output.getvalue(), *bounds[1])))
        self.assertIsNotNone(ImageChops.difference(first_crop.crop((245, 320, 400, 339)),
                                                  Image.new('RGB', (155, 19), 'white')).getbbox())
        self.assertIsNotNone(ImageChops.difference(second_crop.crop((245, 0, 400, 28)),
                                                  Image.new('RGB', (155, 28), 'white')).getbbox())
        complete = result(event='Stage 4 Loop de Loop')
        unreadable = result(date=None, event='Stage 5 Brickfield')
        fragment = result(date=None, event='Loop', avg_watts=None, race_score=None)
        identity = self.staged([[complete, unreadable], [fragment]], output.getvalue())
        source = race.load_import(self.store, identity)
        observed, sections, all_complete = observations(self.store, source)
        self.assertTrue(all_complete)
        self.assertEqual([item['row'] for item in observed], [complete, unreadable, fragment])
        page = self.app.get('/race-results/review/' + identity)[2]
        self.assertIn(b'These two extractions may be the same race', page)
        self.assertNotIn(b'Possible section-boundary fragment', page)
        self.assertIn(b'Loop', page)
        corrected = dict(unreadable, date='2024-11-09')
        activities = [self.activity(complete), self.activity(corrected)]
        draft = [self.item(complete, activities[0]['activity_id']),
                 self.item(unreadable, activities[1]['activity_id']),
                 self.item(fragment, '', group='')]
        with patch('rideworks.race_results.matching_activities', return_value=activities):
            with self.assertRaisesRegex(race.RaceError, 'explicitly mark'):
                race.commit_rows(self.store, identity, draft, visible_count=2, visible_confirmed=True)
            self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
            draft[2]['group'] = '1'
            draft[0]['corrected'] = True
            with self.assertRaisesRegex(race.RaceError, 'valid date'):
                race.commit_rows(self.store, identity, draft, visible_count=2, visible_confirmed=True)
            self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
            draft[1]['values'] = corrected
            self.assertEqual(race.commit_rows(self.store, identity, draft, visible_count=2, visible_confirmed=True)['added'], 2)
        self.assertEqual([item['row'] for item in observations(self.store, source)[0]], [complete, unreadable, fragment])
        saved = self.store.connection.execute('SELECT decisions_json FROM race_import_reconciliations WHERE import_id=?',
                                              (identity,)).fetchone()
        self.assertEqual(json.loads(saved[0])['groups'][0]['observations'], [1, 3])

    def test_plan_covers_seams_and_crop_pixels_without_counting_rows(self):
        for width, height in ((768, 939), (1000, 1800), (40, 100)):
            bounds = plan_sections(width, height)
            self.assertEqual(bounds[0][0], 0)
            self.assertEqual(bounds[-1][1], height)
            for left, right in zip(bounds, bounds[1:]):
                self.assertGreaterEqual(left[1] - right[0], 180)
                self.assertLessEqual(left[1] - left[0], 600)
        payload = image()
        sections = plan_sections(768, 939)
        first, second = [Image.open(io.BytesIO(crop_image(payload, *bounds))) for bounds in sections]
        overlap = sections[0][1] - sections[1][0]
        a = first.crop((0, sections[1][0], 768, sections[0][1]))
        b = second.crop((0, 0, 768, overlap))
        self.assertIsNone(ImageChops.difference(a, b).getbbox())
        with self.assertRaisesRegex(race.RaceError, 'too many sections'):
            plan_sections(768, 100_000)

    def test_clipped_bottom_and_heading_line_do_not_define_row_counts(self):
        source = Image.new('RGB', (768, 920), 'white')
        draw = ImageDraw.Draw(source)
        draw.line((10, 10, 750, 10), fill='black')
        for index in range(17):
            y = 60 + index * 52
            draw.text((20, y), f'Synthetic row {index + 1}', fill='black')
            draw.text((250, y + 12), 'wrapped title', fill='blue')
            draw.line((10, y + 45, 750, y + 45), fill='gray')
        payload = io.BytesIO()
        source.save(payload, format='PNG')
        bounds = plan_sections(768, 920)
        self.assertTrue(any(top <= 570 and bottom >= 620 for top, bottom in bounds))
        outputs = [[result(date=f'2024-11-{day:02d}') for day in range(1, 10)],
                   [result(date=f'2024-11-{day:02d}') for day in range(9, 18)]]
        identity = self.staged(outputs, payload.getvalue())
        observed, sections, complete = observations(self.store, race.load_import(self.store, identity))
        self.assertTrue(complete)
        self.assertEqual(len(observed), 18)
        draft = [self.item(item['row'], '') for item in observed]
        with self.assertRaisesRegex(race.RaceError, '18 distinct races'):
            reconcile(observed, sections, complete, draft, 17, True)
        draft[9]['group'] = '9'
        self.assertEqual(len(reconcile(observed, sections, complete, draft, 17, True)), 17)

    def test_explicit_grouping_retains_observations_and_corrected_values(self):
        first = result(date='2024-11-07', event='Synthetic Stage One')
        second = result(date='2024-11-08', event='Synthetic Stage Four')
        disputed = dict(second, race_score=199)
        third = result(date='2024-11-09', event='Synthetic Stage Five')
        identity = self.staged([[first, second], [disputed, third]])
        source = race.load_import(self.store, identity)
        observed, sections, complete = observations(self.store, source)
        self.assertTrue(complete)
        self.assertEqual([o['row'] for o in observed], [first, second, disputed, third])
        self.assertEqual([s['status'] for s in sections], ['completed', 'completed'])
        self.assertEqual(self.app.get(f'/race-results/section/{identity}/1')[0], 200)
        page = self.app.get('/race-results/review/' + identity)[2]
        self.assertIn(b'These two extractions may be the same race', page)
        self.assertIn(b'Compare screenshot crops', page)
        self.assertIn(b'value="confirm" disabled', page)

        activities = [self.activity(row) for row in (first, second, third)]
        draft = [self.item(first, activities[0]['activity_id']),
                 self.item(second, activities[1]['activity_id']),
                 self.item(disputed, '', group='2'),
                 self.item(third, activities[2]['activity_id'])]
        with self.assertRaisesRegex(race.RaceError, 'conflicting values'):
            reconcile(observed, sections, complete, draft, 3, True)
        draft[1]['corrected'] = True
        self.assertEqual(reconcile(observed, sections, complete, draft, 3, True), [[0], [1, 2], [3]])
        with patch('rideworks.race_results.matching_activities', return_value=activities):
            self.assertEqual(race.commit_rows(self.store, identity, draft, visible_count=3, visible_confirmed=True)['added'], 3)
        saved = self.store.connection.execute('SELECT decisions_json FROM race_import_reconciliations').fetchone()
        recorded = json.loads(saved[0])
        self.assertEqual(recorded['groups'][1]['observations'], [2, 3])
        self.assertEqual(recorded['groups'][1]['values'], second)
        self.assertEqual([o['row'] for o in observations(self.store, source)[0]], [first, second, disputed, third])

    def test_identical_distinct_rows_are_never_silently_removed(self):
        row = result()
        identity = self.staged([[row], [row]])
        observed, sections, complete = observations(self.store, race.load_import(self.store, identity))
        ride = self.activity(row)
        draft = [self.item(row, ride['activity_id']), self.item(row, ride['activity_id'])]
        self.assertEqual(reconcile(observed, sections, complete, draft, 2, True), [[0], [1]])
        with patch('rideworks.race_results.matching_activities', return_value=[ride]):
            with self.assertRaisesRegex(race.RaceError, 'same activity'):
                race.commit_rows(self.store, identity, draft, visible_count=2, visible_confirmed=True)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)

    def test_http_review_requires_acknowledgment_and_commits_provenance(self):
        first = result(date='2024-11-07', event='Synthetic Stage One')
        second = result(date='2024-11-08', event='Synthetic Stage Four')
        disputed = dict(second, race_score=199)
        third = result(date='2024-11-09', event='Synthetic Stage Five')
        identity = self.staged([[first, second], [disputed, third]])
        activities = [self.activity(row) for row in (first, second, third)]
        fields = {'nonce': self.app.settings.nonce, 'timezone': 'UTC', 'operation': 'preview',
                  'overlap.1.2': 'same'}
        for index, row in enumerate((first, second, disputed, third)):
            fields.update({f'{index}.{key}': '' if value is None else str(value) for key, value in row.items()})
            fields[f'{index}.shown_activity'] = ''
            fields[f'{index}.shown_revision'] = 'new'
        route = '/race-results/review/' + identity
        with patch('rideworks.race_page.matching_activities', return_value=activities):
            status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'The extractions disagree', page)
        self.assertIn(b'value="confirm" disabled', page)
        self.assertIn(b'I checked these races against my screenshot', page)
        verification = re.search(rb'name="verify\.1\.2" value="([0-9a-f]{64})"', page)
        self.assertIsNotNone(verification)
        fields['operation'] = 'confirm'
        for index, activity in zip((0, 1, 3), activities):
            fields[f'{index}.shown_activity'] = activity['activity_id']
        with patch('rideworks.race_results.matching_activities', return_value=activities):
            self.assertEqual(self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')[0], 400)
            self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
            fields['list_acknowledged'] = 'yes'
            self.assertEqual(self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')[0], 400)
            fields['verify.1.2'] = verification.group(1).decode()
            status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'Added 3', page)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_import_reconciliations').fetchone()[0], 1)

    def test_unresolved_count_bad_group_or_missing_match_is_atomic(self):
        first = result(date='2024-11-07', event='Synthetic Stage One')
        second = result(date='2024-11-08', event='Synthetic Stage Four')
        identity = self.staged([[first], [second]])
        first_ride = self.activity(first)
        second_ride = self.activity(second)
        draft = [self.item(first, first_ride['activity_id']), self.item(second, second_ride['activity_id'])]
        cases = [(draft, 1, True), (draft, 2, False),
                 ([draft[0], dict(draft[1], group='')], 2, True),
                 ([dict(draft[0], group='1'), draft[1]], 2, True)]
        with patch('rideworks.race_results.matching_activities', return_value=[first_ride, second_ride]):
            for current, count, confirmed in cases:
                with self.subTest(count=count, confirmed=confirmed, groups=[x['group'] for x in current]):
                    with self.assertRaises(race.RaceError):
                        race.commit_rows(self.store, identity, current, visible_count=count, visible_confirmed=confirmed)
        with patch('rideworks.race_results.matching_activities', return_value=[first_ride]):
            with self.assertRaisesRegex(race.RaceError, 'Observation 2'):
                race.commit_rows(self.store, identity, draft, visible_count=2, visible_confirmed=True)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_import_reconciliations').fetchone()[0], 0)

    def test_failed_section_preserves_attempts_and_blocks_all_writes(self):
        calls = 0

        def extractor(*_):
            nonlocal calls
            calls += 1
            if calls == 1:
                return [result()], usage()
            raise race.RaceError('Synthetic failed section.', request_id='request-123')

        identity = race.stage_import(self.store, image(height=1800), 'UTC', extractor=extractor)
        observed, sections, complete = observations(self.store, race.load_import(self.store, identity))
        self.assertFalse(complete)
        self.assertEqual([s['status'] for s in sections], ['completed', 'failed', 'planned', 'planned'])
        self.assertEqual(sections[1]['request_id'], 'request-123')
        attempts = [{'model': s['model'], 'service_tier': 'default',
                     'usage': json.loads(s['usage_json']) if s['usage_json'] else None}
                    for s in sections if s['status'] != 'planned']
        self.assertEqual(estimate_cost(attempts)['state'], 'partial')
        with self.assertRaisesRegex(race.RaceError, 'section failed'):
            race.commit_rows(self.store, identity, [self.item(result(), '')], visible_count=1, visible_confirmed=True)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
        self.assertEqual(len(observed), 1)

    def test_malformed_response_retains_usage_and_request_identifier(self):
        response = {'status': 'completed', 'service_tier': 'default',
                    'usage': usage(), 'output': [{'type': 'message', 'content': [
                        {'type': 'output_text', 'text': '{invalid'}]}]}
        opener = FakeOpener(response)
        original_open = opener.open

        def open_with_headers(*args, **kwargs):
            returned = original_open(*args, **kwargs)
            returned.headers = {'x-request-id': 'request-abc'}
            return returned

        opener.open = open_with_headers
        with self.assertRaises(race.RaceError) as raised:
            race.extract(image(), 'image/png', 'synthetic-key', 'gpt-6-luna', opener=opener)
        self.assertEqual(raised.exception.usage['input_tokens'], 1000)
        self.assertEqual(raised.exception.request_id, 'request-abc')
        self.assertEqual(raised.exception.output, '{invalid')

    def test_failed_http_response_retains_reported_usage_without_exposing_error_body(self):
        body = json.dumps({'usage': usage(), 'service_tier': 'default',
                           'error': {'message': 'private detail'}}).encode()
        opener = FakeOpener({})
        error = HTTPError('https://api.openai.com', 429, 'private',
                          {'x-request-id': 'request-429'}, io.BytesIO(body))
        with patch.object(opener, 'open', side_effect=error):
            with self.assertRaises(race.RaceError) as raised:
                race.extract(image(), 'image/png', 'synthetic-key', 'gpt-6-luna', opener=opener)
        self.assertEqual(raised.exception.request_id, 'request-429')
        self.assertEqual(raised.exception.usage['input_tokens'], 1000)
        self.assertNotIn('private detail', str(raised.exception))
        estimate = estimate_cost([{'model': 'gpt-6-luna', 'service_tier': 'default',
                                   'usage': raised.exception.usage}])
        self.assertEqual(estimate['state'], 'complete')
        self.assertGreater(estimate['amount_usd'], 0)

    def test_failed_malformed_section_keeps_raw_response_and_usage(self):
        identity = race.stage_import(self.store, image(height=400), 'UTC',
            extractor=lambda *_: ([{'bad': 'row'}], usage()))
        section = self.store.connection.execute('SELECT * FROM race_import_sections WHERE import_id=?', (identity,)).fetchone()
        self.assertEqual(section['status'], 'failed')
        self.assertEqual(json.loads(section['output_json']), {'races': [{'bad': 'row'}]})
        self.assertEqual(json.loads(section['usage_json'])['input_tokens'], 1000)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)

    def test_schema14_rollback_preserves_legacy_import(self):
        identity = self.staged([[result()]], image(height=400))
        original = race.screenshot(self.store, identity)[1]
        self.store.connection.executescript('DROP TABLE race_import_reconciliations; DROP TABLE race_import_sections; PRAGMA user_version=13;')
        from rideworks import store as module
        broken = module.MIGRATION_14.replace('PRAGMA user_version = 14;', 'INSERT INTO missing VALUES(1);')
        with patch.object(module, 'MIGRATION_14', broken), self.assertRaises(sqlite3.Error):
            Store(self.store.data_dir)
        self.assertEqual(self.store.connection.execute('PRAGMA user_version').fetchone()[0], 13)
        self.assertIsNone(self.store.connection.execute("SELECT name FROM sqlite_master WHERE name='race_import_sections'").fetchone())
        with Store(self.store.data_dir) as upgraded:
            self.assertEqual(upgraded.connection.execute('PRAGMA user_version').fetchone()[0], 14)
            self.assertEqual(race.screenshot(upgraded, identity)[1], original)
            old, sections, complete = observations(upgraded, race.load_import(upgraded, identity))
            self.assertTrue(complete)
            self.assertTrue(old[0]['legacy'])
            self.assertEqual(sections, [])
            activity = self.activity(result())
            with patch('rideworks.race_results.matching_activities', return_value=[activity]):
                item = self.item(result(), activity['activity_id'])
                self.assertEqual(race.commit_rows(upgraded, identity, [item],
                                                  visible_count=1, visible_confirmed=True)['added'], 1)


if __name__ == '__main__':
    unittest.main()
