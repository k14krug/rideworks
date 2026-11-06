"""Synthetic-only tests for screenshot race import and review."""

import io
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from PIL import Image, ImageDraw

from fit_fixture import make_fit
from rideworks import race_results as race
from rideworks.store import Store
from rideworks.web import Application, create_server


USER_PROMPT = """Read the attached Zwift Racing Profile screenshot and extract race results into the supplied JSON schema.

**Row identification**

- Extract each visible race-result row in top-to-bottom order.
- Only extract rows from the RACE RESULTS table.
- The number in the RACE RESULTS heading represents the total profile results, not necessarily the number visible in the screenshot.
- Include a row when enough of its information is readable to identify the race, even if the row border is partially cropped.
- Never invent additional rows.
**Field extraction**

For each row, extract exactly these eight fields:

- `date`: Convert the displayed M/D/YYYY date to YYYY-MM-DD.
- `start_time`: Convert the displayed 12-hour AM/PM time to 24-hour HH. Do not infer a timezone.
- `event`: Extract the blue event title, joining wrapped lines with spaces. Do not include the smaller route name below it. If the title is truncated with an ellipsis (...), preserve the visible text and ellipsis exactly. Never invent missing title text.
- `race_group`: Extract the gray race-group badge, preserving the displayed range as a string (for example, "0-210", "160-270", or "0-275").
- `finish`: Extract the integer finishing position from the FINISH column.
- `avg_watts`: Extract the upper integer value from the WATTS/W/kg column. Ignore the lower W/kg value.
- `race_score`: Extract the main integer from the SCORE/Change column, above the change indicator.
- `race_score_change`: Extract the numeric change below the score. Green upward arrow means positive, red downward arrow means negative. An explicit zero is 0 regardless of arrow direction.
**Accuracy rules**

- Use null for missing, dashed (--) or unreadable values.
- Do not confuse average watts with 20M, 5M, 1M or 15S power.
- Ignore route, race duration, gap, distance, elevation and W/kg.
- Keep values associated with their original row, even when event titles wrap across multiple lines.
- Never guess, infer missing information, duplicate rows or combine results from different rows.
- Return only the JSON object required by the supplied schema, without explanations, Markdown or extra fields."""


def synthetic_image():
    image = Image.new('RGB', (1000, 1800), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((10, 2), 'FINISH  DATE TIME  EVENT / GROUP  WATTS  20M  SCORE CHANGE', fill='black')
    draw.text((10, 25), '9  2024-11-08 12:00  Synthetic Stage Four', fill='black')
    draw.text((10, 40), 'Wrapped Title  [0-210]  161 W  333 W  184', fill='black')
    draw.text((650, 40), 'UP +0', fill='green')
    draw.text((10, 75), '9  2024-11-08 12:00  Synthetic Stage Four [160-270]  175 W  333 W  -  -', fill='black')
    draw.text((10, 125), '9  2024-11-08 12:00  Synthetic Stage Four [0-210]  161 W  333 W  184', fill='black')
    draw.text((650, 125), 'DOWN -5', fill='red')
    for index in range(3, 33):
        draw.text((10, 25 + index * 50), f'Synthetic race {index + 1}  123 W  score 200  +1', fill='black')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def result(**updates):
    row = {'date': '2024-11-08', 'start_time': '12:00', 'event': 'Synthetic Stage Four',
           'race_group': '0-210', 'finish': 9, 'avg_watts': 161, 'race_score': 184,
           'race_score_change': 1}
    row.update(updates)
    return row


class FakeResponse:
    def __init__(self, value):
        self.payload = json.dumps(value).encode()

    def read(self, size):
        return self.payload[:size]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class FakeOpener:
    def __init__(self, data):
        self.data = data
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request, self.timeout = request, timeout
        return FakeResponse(self.data)


class RaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = synthetic_image()
        self.app = Application(self.root / 'store')
        self.app.settings.port = 8766
        path = self.root / 'synthetic.fit'
        path.write_bytes(make_fit(avg_power=233))
        with Store(self.app.data_dir) as store:
            self.activity_id = store.import_fit(path)['activity_id']

    def stage(self, rows=None, zone='UTC'):
        with Store(self.app.data_dir) as store:
            return race.stage_import(store, self.image, zone,
                extractor=lambda *_: (rows if rows is not None else [result()], {'input_tokens': 123, 'output_tokens': 45}))

    def item(self, row=None, *, activity=None, replace=False, shown=None):
        identity = activity or self.activity_id
        return {'values': row or result(), 'activity_id': identity, 'action': 'confirm',
                'replace': replace, 'shown_activity': identity, 'shown_revision': shown or 'new'}

    def test_api_request_schema_and_response_are_offline(self):
        rows = [result(event='Synthetic Stage Four Wrapped Title', race_score_change=0),
                result(race_group='160-270', race_score=None, race_score_change=None, avg_watts=175),
                result(race_score_change=-5)]
        api = {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps({'races': rows})}]}],
            'usage': {'input_tokens': 123, 'output_tokens': 45, 'total_tokens': 168}}
        opener = FakeOpener(api)
        returned, usage = race.extract(self.image, 'image/png', 'synthetic-key', 'gpt-4o-mini', opener=opener)
        request = json.loads(opener.request.data)
        self.assertEqual(returned, rows)
        self.assertEqual(usage['input_tokens'], 123)
        self.assertEqual(opener.timeout, 60)
        self.assertEqual(opener.request.full_url, 'https://api.openai.com/v1/responses')
        self.assertFalse(request['store'])
        self.assertTrue(request['text']['format']['strict'])
        self.assertEqual(request['text']['format']['schema'], race.SCHEMA)
        self.assertEqual(request['input'][0]['content'][0]['text'], USER_PROMPT)
        self.assertIn('HH:MM', race.SCHEMA['properties']['races']['items']['properties']['start_time']['description'])
        self.assertIn('data:image/png;base64,', request['input'][0]['content'][1]['image_url'])

    def test_normalize_review_dates_and_times_without_changing_evidence(self):
        source = result(date='3/2/2024', start_time='1:07 PM')
        normalized = race.normalize_row(source)
        self.assertEqual((normalized['date'], normalized['start_time']), ('2024-03-02', '13:07'))
        self.assertEqual((source['date'], source['start_time']), ('3/2/2024', '1:07 PM'))
        self.assertEqual(race.normalize_row(result(start_time='12:05 AM'))['start_time'], '00:05')
        self.assertEqual(race.normalize_row(result(start_time='12:05 PM'))['start_time'], '12:05')
        invalid = race.normalize_row(result(date='2/30/2024', start_time='13:45 PM'))
        self.assertEqual((invalid['date'], invalid['start_time']), ('2/30/2024', '13:45 PM'))
        self.assertEqual(len(race.row_errors(invalid)), 2)

    def test_existing_import_is_normalized_for_review_and_matching_only(self):
        raw = result(date='11/8/2024', start_time='11:33 AM')
        identity = self.stage([raw])
        status, _, page = self.app.get('/race-results/review/' + identity)
        self.assertEqual(status, 200)
        self.assertIn(b'value="2024-11-08"', page)
        self.assertIn(b'value="11:33"', page)
        self.assertIn(self.activity_id.encode(), page)
        with Store(self.app.data_dir) as store:
            self.assertEqual(json.loads(race.load_import(store, identity)['rows_json']), [raw])

    def test_review_normalizes_edits_without_overwriting_raw_import(self):
        raw = result()
        identity = self.stage([raw])
        fields = {'nonce': self.app.settings.nonce, 'timezone': 'UTC', 'operation': 'preview',
                  '0.activity': '', '0.manual': '', '0.action': 'skip',
                  '0.shown_activity': '', '0.shown_revision': 'new'}
        fields.update({f'0.{key}': '' if value is None else str(value) for key, value in raw.items()})
        fields['0.date'] = '11/8/2024'
        fields['0.start_time'] = '11:33 AM'
        status, _, page = self.app.post('/race-results/review/' + identity, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'value="2024-11-08"', page)
        self.assertIn(b'value="11:33"', page)
        self.assertIn(self.activity_id.encode(), page)
        with Store(self.app.data_dir) as store:
            self.assertEqual(json.loads(race.load_import(store, identity)['rows_json']), [raw])

    def test_old_extraction_warns_and_unknown_timezone_remains_unknown(self):
        identity = self.stage([result()], zone='')
        with Store(self.app.data_dir) as store:
            store.connection.execute('UPDATE race_imports SET prompt_version=? WHERE import_id=?',
                                     ('zrp-races-v1', identity))
        status, _, page = self.app.get('/race-results/review/' + identity)
        self.assertEqual(status, 200)
        self.assertIn(b'This earlier extraction may contain incorrect values, including watts and scores', page)
        self.assertIn(b'name="timezone" maxlength="100" value=""', page)

    def test_extract_errors_and_shape_are_recoverable(self):
        with self.assertRaisesRegex(race.RaceError, 'OPENAI_API_KEY'):
            race.extract(self.image, 'image/png', '', 'gpt-4o-mini')
        for bad in ({}, {'races': [{}]}, {'races': [result(finish=True)]}, {'races': [result(extra=1)]}):
            with self.assertRaises(race.RaceError):
                race.validate_shape(bad)
        for data in ({'status': 'incomplete'}, {'status': 'completed', 'output': [
            {'type': 'message', 'content': [{'type': 'refusal'}]}]},
            {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{'}]}]}):
            with self.assertRaises(race.RaceError):
                race.extract(self.image, 'image/png', 'synthetic-key', 'gpt-4o-mini', opener=FakeOpener(data))
        opener = FakeOpener({})
        with patch.object(opener, 'open', side_effect=URLError('private details')):
            with self.assertRaisesRegex(race.RaceError, 'timed out'):
                race.extract(self.image, 'image/png', 'synthetic-key', 'gpt-4o-mini', opener=opener)
        with patch.object(opener, 'open', side_effect=TimeoutError()):
            with self.assertRaisesRegex(race.RaceError, 'timed out'):
                race.extract(self.image, 'image/png', 'synthetic-key', 'gpt-4o-mini', opener=opener)
        with patch.object(opener, 'open', side_effect=HTTPError('https://api.openai.com', 429, 'private', {}, None)):
            with self.assertRaisesRegex(race.RaceError, 'HTTP 429'):
                race.extract(self.image, 'image/png', 'synthetic-key', 'gpt-4o-mini', opener=opener)
        self.assertEqual(len(race.validate_shape({'races': [result()] * 100})), 100)
        with self.assertRaisesRegex(race.RaceError, 'too many'):
            race.validate_shape({'races': [result()] * 101})

    def test_images_validate_and_preview_does_not_save_results(self):
        self.assertEqual(race.validate_image(self.image, len(self.image)), ('image/png', '.png'))
        for fmt, expected in (('JPEG', 'image/jpeg'), ('WEBP', 'image/webp')):
            data = io.BytesIO()
            Image.new('RGB', (16, 16), 'white').save(data, format=fmt)
            self.assertEqual(race.validate_image(data.getvalue(), 5000)[0], expected)
        for payload, limit in ((b'not an image', 100), (self.image[:100], len(self.image)), (self.image, 2)):
            with self.assertRaises(race.RaceError):
                race.validate_image(payload, limit)
        identity = self.stage([result(), result(race_score=None, race_score_change=None)])
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
            kind, original = race.screenshot(store, identity)
            self.assertEqual((kind, original), ('image/png', self.image))
            source = race.load_import(store, identity)
            self.assertEqual(source['source_type'], 'zwift_racing_profile_screenshot')
            self.assertEqual(source['prompt_version'], race.PROMPT_VERSION)
            self.assertEqual(source['schema_version'], race.SCHEMA_VERSION)
        status, _, body = self.app.get('/race-results/review/' + identity)
        self.assertEqual(status, 200)
        for text in ('Review Race Import', 'Confirm Import', 'Zwift avg watts', 'Screenshot display timezone'):
            self.assertIn(text, body.decode())

    def test_api_failure_leaves_history_unchanged_and_sanitized(self):
        body = (b'--synthetic\r\nContent-Disposition: form-data; name="nonce"\r\n\r\n'
                + self.app.settings.nonce.encode() + b'\r\n--synthetic\r\nContent-Disposition: form-data; name="timezone"\r\n\r\nUTC\r\n'
                b'--synthetic\r\nContent-Disposition: form-data; name="image"; filename="synthetic.png"\r\n'
                b'Content-Type: image/png\r\n\r\n' + self.image + b'\r\n--synthetic--\r\n')
        with patch('rideworks.race_results.configuration', return_value=('', 'gpt-4o-mini', 10_000_000)):
            status, _, page = self.app.race_extract_post(body, 'multipart/form-data; boundary=synthetic', 'http://localhost:8766')
        self.assertEqual(status, 400)
        self.assertIn(b'OPENAI_API_KEY', page)
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_imports').fetchone()[0], 0)

    def test_untrusted_event_is_escaped(self):
        identity = self.stage([result(event='<script>alert(1)</script>')])
        html = self.app.get('/race-results/review/' + identity)[2].decode()
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)

    def test_http_upload_review_and_reimport(self):
        body = (b'--synthetic\r\nContent-Disposition: form-data; name="nonce"\r\n\r\n'
                + self.app.settings.nonce.encode() + b'\r\n--synthetic\r\nContent-Disposition: form-data; name="timezone"\r\n\r\nUTC\r\n'
                b'--synthetic\r\nContent-Disposition: form-data; name="image"; filename="synthetic.png"\r\n'
                b'Content-Type: image/png\r\n\r\n' + self.image + b'\r\n--synthetic--\r\n')
        with patch('rideworks.race_results.extract', return_value=([result()], {'total_tokens': 200})):
            response = self.app.race_extract_post(body, 'multipart/form-data; boundary=synthetic', 'http://localhost:8766')
        self.assertEqual(response[0], 303)
        route = response[1]['Location']
        identity = route.rsplit('/', 1)[-1]
        fields = {'nonce': self.app.settings.nonce, 'timezone': 'UTC', 'operation': 'preview',
                  '0.activity': '', '0.manual': self.activity_id, '0.action': 'confirm',
                  '0.shown_activity': '', '0.shown_revision': 'new'}
        fields.update({f'0.{key}': '' if value is None else str(value) for key, value in result().items()})
        status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'New', page)
        fields['operation'] = 'confirm'
        status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 400)
        self.assertIn(b'Review changes', page)
        fields.update({'0.manual': '', '0.activity': self.activity_id, '0.shown_activity': self.activity_id})
        status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'Added 1', page)
        with patch('rideworks.race_results.extract', return_value=([result()], None)):
            again = self.app.race_extract_post(body, 'multipart/form-data; boundary=synthetic', 'http://localhost:8766')
        self.assertEqual(again[0], 303)
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_imports').fetchone()[0], 2)
            self.assertEqual(store.connection.execute('SELECT COUNT(DISTINCT image_path) FROM race_imports').fetchone()[0], 1)
            previous = store.connection.execute('SELECT values_json FROM race_results').fetchone()[0]
            self.assertEqual(race.commit_rows(store, again[1]['Location'].rsplit('/', 1)[-1],
                                              [self.item(shown=race.revision(previous, 'UTC'))])['unchanged'], 1)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM activities').fetchone()[0], 1)
        self.assertEqual(self.app.get('/race-results/image/' + identity)[2], self.image)

    def test_http_handler_enforces_origin_type_and_size(self):
        server = create_server(self.app.data_dir, port=0)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        self.addCleanup(connection.close)
        connection.request('POST', '/race-results/extract', b'x', {'Content-Type': 'text/plain',
                           'Origin': f'http://127.0.0.1:{server.server_port}'})
        self.assertEqual(connection.getresponse().status, 415)
        connection.close()
        connection.request('POST', '/race-results/extract', b'x', {'Content-Type': 'multipart/form-data; boundary=a',
                           'Origin': 'http://untrusted.invalid'})
        self.assertEqual(connection.getresponse().status, 403)

    def test_transactional_confirm_reimport_changed_and_no_phantom_rides(self):
        identity = self.stage()
        with Store(self.app.data_dir) as store:
            before = store.get_activity(self.activity_id)
            self.assertEqual(race.commit_rows(store, identity, [self.item()])['added'], 1)
            previous = store.connection.execute('SELECT values_json FROM race_results').fetchone()[0]
            unchanged = self.item(shown=race.revision(previous, 'UTC'))
            self.assertEqual(race.commit_rows(store, identity, [unchanged])['unchanged'], 1)
            edited = self.item(result(avg_watts=199), shown=race.revision(previous, 'UTC'))
            with self.assertRaisesRegex(race.RaceError, 'replacement'):
                race.commit_rows(store, identity, [edited])
            edited['replace'] = True
            self.assertEqual(race.commit_rows(store, identity, [edited])['replaced'], 1)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_result_history').fetchone()[0], 2)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM activities').fetchone()[0], 1)
            self.assertEqual(store.get_activity(self.activity_id), before)
            invalid = self.item(activity='00000000-0000-0000-0000-000000000000')
            with self.assertRaisesRegex(race.RaceError, 'existing activity'):
                race.commit_rows(store, identity, [invalid])
        self.assertIn('Zwift-reported average: 199 W', self.app.get('/activities/' + self.activity_id)[2].decode())
        self.assertIn('/activities/' + self.activity_id, self.app.get('/race-results')[2].decode())

    def test_timezone_replacement_preserves_prior_provenance(self):
        identity = self.stage()
        with Store(self.app.data_dir) as store:
            race.commit_rows(store, identity, [self.item()])
            prior = store.connection.execute('SELECT * FROM race_results').fetchone()
            changed = self.item(shown=race.revision(prior['values_json'], 'UTC'))
            with self.assertRaisesRegex(race.RaceError, 'replacement'):
                race.commit_rows(store, identity, [changed], timezone_name='America/Los_Angeles')
            changed['replace'] = True
            race.commit_rows(store, identity, [changed], timezone_name='America/Los_Angeles')
            self.assertEqual(store.connection.execute('SELECT display_timezone FROM race_imports').fetchone()[0], 'UTC')
            self.assertEqual([r[0] for r in store.connection.execute('SELECT display_timezone FROM race_result_history ORDER BY rowid')],
                             ['UTC', 'America/Los_Angeles'])

    def test_multiple_rows_are_atomic_and_revision_is_checked(self):
        identity = self.stage([result(), result(event='Another synthetic race')])
        first = self.item()
        invalid = self.item(result(event='Another synthetic race'), activity='missing')
        with Store(self.app.data_dir) as store:
            with self.assertRaises(race.RaceError):
                race.commit_rows(store, identity, [first, invalid])
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
            first['shown_activity'] = 'another'
            with self.assertRaisesRegex(race.RaceError, 'Review changes'):
                race.commit_rows(store, identity, [first, {'action': 'skip'}])

    def test_safe_matching_requires_timezone_unique_virtual_and_title(self):
        row = result()
        choice = {'id': 'a', 'title': 'Synthetic Stage Four', 'date': '2024-11-08',
                  'time': '12:00', 'virtual': True, 'absolute': True}
        self.assertEqual(race.suggested_match(row, 'UTC', [choice]), 'a')
        self.assertEqual(race.suggested_match(row, 'UTC', [dict(choice, time='12:10')]), 'a')
        self.assertEqual(race.suggested_match(row, 'UTC', [dict(choice, time='11:50')]), 'a')
        self.assertIsNone(race.suggested_match(row, 'UTC', [dict(choice, time='12:11')]))
        self.assertIsNone(race.suggested_match(row, 'UTC', [dict(choice, time='11:49')]))
        self.assertIsNone(race.suggested_match(row, None, [choice]))
        self.assertIsNone(race.suggested_match(row, 'UTC', [choice, dict(choice, id='b', time='12:09')]))
        self.assertEqual(race.suggested_match(row, 'UTC', [choice, dict(choice, id='b', virtual=False)]), 'a')
        self.assertIsNone(race.suggested_match(row, 'UTC', [dict(choice, time='13:00')]))
        self.assertIsNone(race.suggested_match(row, 'UTC', [dict(choice, virtual=False)]))
        self.assertIsNone(race.suggested_match(row, 'UTC', [dict(choice, absolute=False)]))
        self.assertIsNone(race.suggested_match(row, 'UTC', [dict(choice, date='2024-11-09')]))
        self.assertIsNone(race.suggested_match(row, 'UTC', [dict(choice, title='Different Event')]))
        self.assertIsNone(race.suggested_match(result(event='Stage 4 - 2024'), 'UTC',
                                               [dict(choice, title='Stage 2 - 2024')]))
        dst = result(date='2024-11-03', start_time='01:30')
        self.assertIsNone(race.suggested_match(dst, 'America/Los_Angeles', [dict(choice, date='2024-11-03', time='01:30')]))
        before_dst = result(date='2024-11-03', start_time='00:55')
        self.assertIsNone(race.suggested_match(before_dst, 'America/Los_Angeles',
                                               [dict(choice, date='2024-11-03', time='01:00')]))
        with Store(self.app.data_dir) as store:
            day = result(date='2024-11-08')
            self.assertEqual(len(race.candidates(store, day, 'UTC')), 1)
            self.assertEqual(len(race.candidates(store, day, None)), 0)
            self.assertEqual(race.candidates(store, day, 'America/Los_Angeles')[0]['time'], '03:33')
            activity = race.matching_activities(store)[0]
            duplicate = dict(activity, activity_id='another', start_time='2024-11-08T11:33:00+00:00')
            choices = race.candidates(store, day, 'UTC', activities=[activity, duplicate])
            self.assertEqual(len(choices), 2)
            self.assertIsNone(race.suggested_match(result(start_time='11:33'), 'UTC', choices))
            self.assertEqual(choices[0]['watts'], 233)
            self.assertEqual(choices[0]['date'], '2024-11-08')

    def test_candidate_date_and_qualifying_match_are_preselected_for_confirmation(self):
        identity = self.stage([result(start_time='11:23')])
        activity = {'activity_id': self.activity_id, 'start_time': '2024-11-08T11:33:00+00:00',
                    'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
                    'title': 'Synthetic Stage Four', 'match_watts': 233, 'match_watts_source': 'FIT session'}
        with patch('rideworks.race_page.matching_activities', return_value=[activity]):
            status, _, page = self.app.get('/race-results/review/' + identity)
        self.assertEqual(status, 200)
        self.assertIn(b'2024-11-08 11:33', page)
        self.assertIn(f'<option value="{self.activity_id}" selected>'.encode(), page)
        self.assertIn(b'name="0.action" value="confirm" checked', page)

    def test_selected_activity_outside_race_date_still_shows_its_date(self):
        identity = self.stage()
        fields = {'nonce': self.app.settings.nonce, 'timezone': 'UTC', 'operation': 'preview',
                  '0.activity': '', '0.manual': self.activity_id, '0.action': 'confirm',
                  '0.shown_activity': '', '0.shown_revision': 'new'}
        fields.update({f'0.{key}': '' if value is None else str(value) for key, value in result().items()})
        activity = {'activity_id': self.activity_id, 'start_time': '2024-11-09T11:33:00+00:00',
                    'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
                    'title': 'Synthetic Stage Four', 'match_watts': 233, 'match_watts_source': 'FIT session'}
        with patch('rideworks.race_page.matching_activities', return_value=[activity]):
            status, _, page = self.app.post('/race-results/review/' + identity, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'2024-11-09 11:33', page)
        self.assertIn(f'<option value="{self.activity_id}" selected>'.encode(), page)

    def test_form_discloses_api_and_requires_origin(self):
        status, _, body = self.app.get('/race-results/import')
        self.assertEqual(status, 200)
        self.assertIn('sends the screenshot to OpenAI and incurs API charges', body.decode())
        self.assertIn(b'value="America/Los_Angeles"', body)
        response = self.app.race_extract_post(b'', 'multipart/form-data; boundary=a', 'https://untrusted.invalid')
        self.assertEqual(response[0], 403)

    def test_invalid_integer_keeps_review_edits_for_correction(self):
        identity = self.stage()
        fields = {'nonce': self.app.settings.nonce, 'timezone': 'UTC', 'operation': 'confirm',
                  '0.activity': self.activity_id, '0.manual': '', '0.action': 'confirm',
                  '0.shown_activity': self.activity_id, '0.shown_revision': 'new'}
        fields.update({f'0.{key}': '' if value is None else str(value) for key, value in result().items()})
        fields['0.event'] = 'Corrected synthetic event'
        fields['0.avg_watts'] = '12x'
        status, _, page = self.app.post('/race-results/review/' + identity, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 400)
        self.assertIn(b'Correct invalid rows', page)
        self.assertIn(b'Corrected synthetic event', page)
        self.assertIn(b'value="12x"', page)
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)

    def test_migration_rollback(self):
        with Store(self.app.data_dir) as store:
            store.connection.executescript('DROP TABLE race_result_history; DROP TABLE race_results; DROP TABLE race_imports; PRAGMA user_version=11;')
        from rideworks import store as module
        with patch.object(module, 'MIGRATION_12', module.MIGRATION_12.replace('PRAGMA user_version = 12;', 'INSERT INTO missing VALUES(1);')):
            with self.assertRaises(sqlite3.Error):
                Store(self.app.data_dir)
        with sqlite3.connect(self.app.data_dir / 'rideworks.sqlite3') as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 11)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='race_imports'").fetchone())
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('PRAGMA user_version').fetchone()[0], 12)


if __name__ == '__main__':
    unittest.main()
