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
from uuid import uuid4
import zipfile

from PIL import Image, ImageDraw

from fit_fixture import make_fit
from test_rideworks_export import csv_bytes, row as export_row
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
- `start_time`: Convert the displayed 12-hour AM/PM time to 24-hour HH:MM. Do not infer a timezone.
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
    row = {'date': '2024-11-08', 'start_time': '11:33', 'event': 'Synthetic Stage Four',
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
        path = self.root / 'synthetic-export.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('activities.csv', csv_bytes([
                export_row(filename='activities/synthetic.fit', title='Synthetic Stage Four')]))
            archive.writestr('activities/synthetic.fit', make_fit(avg_power=233))
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.import_strava_export(path)['failures'], [])
            self.activity_id = store.connection.execute('SELECT activity_id FROM activities').fetchone()[0]

    def stage(self, rows=None, zone='UTC'):
        with Store(self.app.data_dir) as store:
            return race.stage_import(store, self.image, zone,
                extractor=lambda *_: (rows if rows is not None else [result()], {'input_tokens': 123, 'output_tokens': 45}), mode='full')

    def item(self, row=None, *, activity=None, replace=False, shown=None):
        identity = activity or self.activity_id
        return {'values': row or result(), 'activity_id': identity, 'action': 'confirm', 'group': 'different',
                'replace': replace, 'shown_activity': identity, 'shown_revision': shown or 'new'}

    def commit_rows(self, store, identity, rows, **kwargs):
        return race.commit_rows(store, identity, rows, visible_count=len(rows), visible_confirmed=True, **kwargs)

    def review_fields(self, *, operation='preview'):
        fields = {'nonce': self.app.settings.nonce, 'timezone': 'UTC', 'operation': operation,
                  'list_acknowledged': 'yes',
                  '0.shown_activity': '', '0.shown_revision': 'new'}
        fields.update({f'0.{key}': '' if value is None else str(value) for key, value in result().items()})
        return fields

    def test_api_request_schema_and_response_are_offline(self):
        rows = [result(event='Synthetic Stage Four Wrapped Title', race_score_change=0),
                result(race_group='160-270', race_score=None, race_score_change=None, avg_watts=175),
                result(race_score_change=-5)]
        api = {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps({'races': rows})}]}],
            'service_tier': 'default',
            'usage': {'input_tokens': 123, 'output_tokens': 45, 'total_tokens': 168,
                      'input_tokens_details': {'cached_tokens': 23, 'cache_write_tokens': 10},
                      'output_tokens_details': {'reasoning_tokens': 20}}}
        opener = FakeOpener(api)
        returned, usage = race.extract(self.image, 'image/png', 'synthetic-key', 'gpt-6-luna', opener=opener)
        request = json.loads(opener.request.data)
        self.assertEqual(returned, rows)
        self.assertEqual(request['model'], 'gpt-6-luna')
        self.assertEqual(usage['input_tokens'], 123)
        self.assertEqual(usage['input_tokens_details'], {'cached_tokens': 23, 'cache_write_tokens': 10})
        self.assertEqual(usage['output_tokens_details'], {'reasoning_tokens': 20})
        self.assertEqual(usage['service_tier'], 'default')
        self.assertEqual(opener.timeout, 60)
        self.assertEqual(opener.request.full_url, 'https://api.openai.com/v1/responses')
        self.assertFalse(request['store'])
        self.assertEqual(request['service_tier'], 'default')
        self.assertTrue(request['text']['format']['strict'])
        self.assertEqual(request['text']['format']['schema'], race.SCHEMA)
        self.assertEqual(request['input'][0]['content'][0]['text'], USER_PROMPT)
        self.assertIn('HH:MM', race.SCHEMA['properties']['races']['items']['properties']['start_time']['description'])
        self.assertIn('data:image/png;base64,', request['input'][0]['content'][1]['image_url'])

    def test_default_model_and_explicit_override(self):
        with patch('rideworks.race_results._dotenv'):
            self.assertEqual(race.configuration({})[1], 'gpt-6-luna')
            self.assertEqual(race.configuration({'RIDEWORKS_RACE_MODEL': 'diagnostic-model'})[1], 'diagnostic-model')

    def test_review_displays_estimated_cost_and_unavailable_usage(self):
        usage = {'input_tokens': 123, 'output_tokens': 45, 'service_tier': 'default',
                 'input_tokens_details': {'cached_tokens': 23, 'cache_write_tokens': 10},
                 'output_tokens_details': {'reasoning_tokens': 20}}
        with Store(self.app.data_dir) as store:
            identity = race.stage_import(store, self.image, 'UTC',
                                         extractor=lambda *_: ([result()], usage), mode='full')
        page = self.app.get('/race-results/review/' + identity)[2]
        self.assertIn(b'Estimated API cost: $0.00003298', page)
        self.assertIn(b'not the amount billed', page)
        page = self.app.get('/race-results/review/' + self.stage())[2]
        self.assertIn(b'Estimated API cost: unavailable', page)

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
        self.assertNotIn(b'Source observation', page)
        with Store(self.app.data_dir) as store:
            self.assertEqual(json.loads(race.load_import(store, identity)['rows_json']), [raw])

    def test_review_normalizes_edits_without_overwriting_raw_import(self):
        raw = result()
        identity = self.stage([raw])
        fields = self.review_fields()
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
        for text in ('Review Race Import', 'Import all 2 races', 'Race avg W', 'Screenshot timezone'):
            self.assertIn(text, body.decode())

    def test_api_failure_leaves_history_unchanged_and_sanitized(self):
        body = (b'--synthetic\r\nContent-Disposition: form-data; name="nonce"\r\n\r\n'
                + self.app.settings.nonce.encode() + b'\r\n--synthetic\r\nContent-Disposition: form-data; name="timezone"\r\n\r\nUTC\r\n'
                b'--synthetic\r\nContent-Disposition: form-data; name="mode"\r\n\r\nfull\r\n'
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
                b'--synthetic\r\nContent-Disposition: form-data; name="mode"\r\n\r\nfull\r\n'
                b'--synthetic\r\nContent-Disposition: form-data; name="image"; filename="synthetic.png"\r\n'
                b'Content-Type: image/png\r\n\r\n' + self.image + b'\r\n--synthetic--\r\n')
        with patch('rideworks.race_results.configuration', return_value=('synthetic-key', 'gpt-6-luna', 10_000_000)), \
                patch('rideworks.race_results.extract', return_value=([result()], {'total_tokens': 200})):
            response = self.app.race_extract_post(body, 'multipart/form-data; boundary=synthetic', 'http://localhost:8766')
        self.assertEqual(response[0], 303)
        route = response[1]['Location']
        identity = route.rsplit('/', 1)[-1]
        fields = self.review_fields()
        status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'Matched', page)
        fields['operation'] = 'confirm'
        status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 400)
        self.assertIn(b'Review changes', page)
        fields['0.shown_activity'] = self.activity_id
        status, _, page = self.app.post(route, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'Added 1', page)
        with patch('rideworks.race_results.configuration', return_value=('synthetic-key', 'gpt-6-luna', 10_000_000)), \
                patch('rideworks.race_results.extract', return_value=([result()], None)):
            again = self.app.race_extract_post(body, 'multipart/form-data; boundary=synthetic', 'http://localhost:8766')
        self.assertEqual(again[0], 303)
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_imports').fetchone()[0], 2)
            self.assertEqual(store.connection.execute('SELECT COUNT(DISTINCT image_path) FROM race_imports').fetchone()[0], 1)
            previous = race.result_revision(*race.result_state(store, self.activity_id))
            self.assertEqual(self.commit_rows(store, again[1]['Location'].rsplit('/', 1)[-1],
                                              [self.item(shown=previous)])['unchanged'], 1)
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
            self.assertEqual(self.commit_rows(store, identity, [self.item()])['added'], 1)
            previous = race.result_revision(*race.result_state(store, self.activity_id))
            unchanged = self.item(shown=previous)
            self.assertEqual(self.commit_rows(store, identity, [unchanged])['unchanged'], 1)
            edited = self.item(result(avg_watts=199), shown=previous)
            with self.assertRaisesRegex(race.RaceError, 'replacement'):
                self.commit_rows(store, identity, [edited])
            edited['replace'] = True
            self.assertEqual(self.commit_rows(store, identity, [edited])['replaced'], 1)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_result_history').fetchone()[0], 2)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM activities').fetchone()[0], 1)
            self.assertEqual(store.get_activity(self.activity_id), before)
            invalid = self.item(activity='00000000-0000-0000-0000-000000000000')
            with self.assertRaisesRegex(race.RaceError, 'Manual activity selection'):
                self.commit_rows(store, identity, [invalid])
        self.assertIn('Zwift-reported average: 199 W', self.app.get('/activities/' + self.activity_id)[2].decode())
        self.assertIn('/activities/' + self.activity_id, self.app.get('/race-results')[2].decode())

    def test_timezone_replacement_preserves_prior_provenance(self):
        identity = self.stage()
        with Store(self.app.data_dir) as store:
            self.commit_rows(store, identity, [self.item()])
            changed = self.item(result(start_time='03:33'), shown=race.result_revision(*race.result_state(store, self.activity_id)))
            with self.assertRaisesRegex(race.RaceError, 'replacement'):
                self.commit_rows(store, identity, [changed], timezone_name='America/Los_Angeles')
            changed['replace'] = True
            self.commit_rows(store, identity, [changed], timezone_name='America/Los_Angeles')
            self.assertEqual(store.connection.execute('SELECT display_timezone FROM race_imports').fetchone()[0], 'UTC')
            self.assertEqual([r[0] for r in store.connection.execute('SELECT display_timezone FROM race_result_history ORDER BY rowid')],
                             ['UTC', 'America/Los_Angeles'])

    def test_removal_requires_confirmation_preserves_evidence_and_restoration_approval(self):
        identity = self.stage([result(avg_watts=0, race_score=0)])
        with Store(self.app.data_dir) as store:
            before = store.get_activity(self.activity_id)
            self.commit_rows(store, identity, [self.item(result(avg_watts=0, race_score=0))])
        html = self.app.get('/activities')[2].decode()
        self.assertIn('class="row-race-score">0</span>', html)
        self.assertIn('class="row-race-power" title="Zwift screenshot race average">0 W</span>', html)
        route = '/race-results/remove/' + self.activity_id
        status, _, page = self.app.get(route)
        self.assertEqual(status, 200)
        self.assertIn(b'Synthetic Stage Four', page)
        self.assertIn(b'The activity, FIT data, source screenshot and result history will be retained.', page)
        with Store(self.app.data_dir) as store:
            current, removed = race.result_state(store, self.activity_id)
            shown = race.result_revision(current, removed)
        form = urlencode({'nonce': self.app.settings.nonce, 'revision': shown}).encode()
        self.assertEqual(self.app.post(route, form, 'http://untrusted.invalid')[0], 403)
        self.assertEqual(self.app.post(route, form, 'http://localhost:8766')[0], 303)
        self.assertEqual(self.app.get(route)[0], 404)
        self.assertNotIn('Zwift-reported average', self.app.get('/activities/' + self.activity_id)[2].decode())
        self.assertNotIn('/activities/' + self.activity_id, self.app.get('/race-results')[2].decode())
        self.assertIn('class="row-race-score">—</span>', self.app.get('/activities')[2].decode())
        self.assertEqual(self.app.get('/race-results/image/' + identity)[2], self.image)
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.get_activity(self.activity_id), before)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_result_history').fetchone()[0], 1)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_result_removals').fetchone()[0], 1)
            current, removed = race.result_state(store, self.activity_id)
            item = self.item(result(avg_watts=0, race_score=0), shown=race.result_revision(current, removed))
            with self.assertRaisesRegex(race.RaceError, 'restoration approval'):
                self.commit_rows(store, identity, [item])
            item['replace'] = True
            self.assertEqual(self.commit_rows(store, identity, [item])['added'], 1)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_result_removals').fetchone()[0], 1)

    def test_removal_rejects_stale_revision(self):
        identity = self.stage()
        with Store(self.app.data_dir) as store:
            self.commit_rows(store, identity, [self.item()])
            current, removed = race.result_state(store, self.activity_id)
            stale = race.result_revision(current, removed)
            updated = json.dumps(result(avg_watts=199))
            store.connection.execute('UPDATE race_results SET values_json=? WHERE activity_id=?', (updated, self.activity_id))
        form = urlencode({'nonce': self.app.settings.nonce, 'revision': stale}).encode()
        status, _, page = self.app.post('/race-results/remove/' + self.activity_id, form, 'http://localhost:8766')
        self.assertEqual(status, 400)
        self.assertIn(b'The race result changed', page)
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_result_removals').fetchone()[0], 0)

    def test_multiple_rows_are_atomic_and_revision_is_checked(self):
        identity = self.stage([result(), result(event='Another synthetic race')])
        first = self.item()
        invalid = self.item(result(event='Another synthetic race'), activity='missing')
        with Store(self.app.data_dir) as store:
            with self.assertRaises(race.RaceError):
                self.commit_rows(store, identity, [first, invalid])
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
            with self.assertRaisesRegex(race.RaceError, 'skipping is not permitted'):
                self.commit_rows(store, identity, [first, dict(invalid, action='skip')])

    def test_batch_is_revalidated_inside_transaction_without_partial_writes(self):
        rows = [result(date=f'2024-11-{day:02d}') for day in range(1, 18)]
        identity = self.stage(rows)
        with Store(self.app.data_dir) as store:
            activities = []
            items = []
            for index, row in enumerate(rows):
                activity_id = str(uuid4())
                store.connection.execute('INSERT INTO activities VALUES (?,?)', (activity_id, 'synthetic'))
                activities.append({'activity_id': activity_id, 'start_time': f"{row['date']}T11:33:00+00:00",
                                   'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
                                   'title': 'Synthetic Stage Four', 'match_watts': None, 'match_watts_source': None})
                items.append(self.item(row, activity=activity_id))
            seen_transaction = []

            def matching_in_transaction(current):
                seen_transaction.append(current.connection.in_transaction)
                return activities[:-1]

            with patch('rideworks.race_results.matching_activities', side_effect=matching_in_transaction):
                with self.assertRaisesRegex(race.RaceError, 'Observation 17'):
                    self.commit_rows(store, identity, items)
            self.assertEqual(seen_transaction, [True])
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_result_history').fetchone()[0], 0)

            with patch('rideworks.race_results.matching_activities', return_value=activities):
                self.assertEqual(self.commit_rows(store, identity, items)['added'], 17)
                self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 17)

    def test_manual_id_and_skip_form_fields_are_rejected(self):
        identity = self.stage()
        fields = self.review_fields(operation='confirm')
        fields['0.shown_activity'] = self.activity_id
        for field, value in (('0.manual', self.activity_id), ('0.activity', self.activity_id), ('0.action', 'skip')):
            with self.subTest(field=field):
                forged = dict(fields, **{field: value})
                response = self.app.post('/race-results/review/' + identity, urlencode(forged).encode(), 'http://localhost:8766')
                self.assertEqual(response[0], 400)
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 0)

    def test_existing_wrong_attachment_blocks_batch_until_removed(self):
        identity = self.stage()
        wrong_id = str(uuid4())
        with Store(self.app.data_dir) as store:
            store.connection.execute('INSERT INTO activities VALUES (?,?)', (wrong_id, 'synthetic'))
            previous = result(event='Synthetic Stage One')
            store.connection.execute('INSERT INTO race_results VALUES (?,?,?,?,?)',
                                     (wrong_id, identity, json.dumps(previous), 'UTC', 'synthetic'))
        status, _, page = self.app.post('/race-results/review/' + identity, urlencode(self.review_fields()).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'Possible existing attachment', page)
        self.assertIn(wrong_id.encode(), page)
        self.assertIn(b'value="confirm" disabled', page)
        with Store(self.app.data_dir) as store:
            with self.assertRaisesRegex(race.RaceError, 'prior association'):
                self.commit_rows(store, identity, [self.item()])
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0], 1)
            race.remove_result(store, wrong_id, race.result_revision(*race.result_state(store, wrong_id)))
            self.assertEqual(self.commit_rows(store, identity, [self.item()])['added'], 1)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM race_result_removals').fetchone()[0], 1)

    def test_safe_matching_requires_timezone_unique_virtual_and_title(self):
        row = result(start_time='12:00')
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
            fields = self.review_fields()
            fields['0.start_time'] = '11:23'
            status, _, page = self.app.post('/race-results/review/' + identity, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'2024-11-08 11:33', page)
        self.assertIn(f'name="0.shown_activity" value="{self.activity_id}"'.encode(), page)
        self.assertIn(b'Automatically matched:', page)
        self.assertNotIn(b'Enter activity ID', page)

    def test_selected_activity_outside_race_date_still_shows_its_date(self):
        identity = self.stage()
        fields = self.review_fields()
        activity = {'activity_id': self.activity_id, 'start_time': '2024-11-09T11:33:00+00:00',
                    'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
                    'title': 'Synthetic Stage Four', 'match_watts': 233, 'match_watts_source': 'FIT session'}
        with patch('rideworks.race_page.matching_activities', return_value=[activity]):
            status, _, page = self.app.post('/race-results/review/' + identity, urlencode(fields).encode(), 'http://localhost:8766')
        self.assertEqual(status, 200)
        self.assertIn(b'2024-11-09 11:33', page)
        self.assertIn(b'diagnostic only', page)
        self.assertIn(b'Activity match unavailable', page)
        self.assertIn(b'name="0.shown_activity" value=""', page)

    def test_form_discloses_api_and_requires_origin(self):
        status, _, body = self.app.get('/race-results/import')
        self.assertEqual(status, 200)
        self.assertIn('sends the screenshot to OpenAI and incurs API charges', body.decode())
        self.assertIn(b'value="America/Los_Angeles"', body)
        response = self.app.race_extract_post(b'', 'multipart/form-data; boundary=a', 'https://untrusted.invalid')
        self.assertEqual(response[0], 403)

    def test_invalid_integer_keeps_review_edits_for_correction(self):
        identity = self.stage()
        fields = self.review_fields(operation='confirm')
        fields['0.shown_activity'] = self.activity_id
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
            store.connection.executescript('DROP TABLE race_import_reconciliations; DROP TABLE race_import_sections; DROP TABLE race_result_removals; DROP TABLE race_result_history; DROP TABLE race_results; DROP TABLE race_imports; PRAGMA user_version=11;')
        from rideworks import store as module
        with patch.object(module, 'MIGRATION_12', module.MIGRATION_12.replace('PRAGMA user_version = 12;', 'INSERT INTO missing VALUES(1);')):
            with self.assertRaises(sqlite3.Error):
                Store(self.app.data_dir)
        with sqlite3.connect(self.app.data_dir / 'rideworks.sqlite3') as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 11)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='race_imports'").fetchone())
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('PRAGMA user_version').fetchone()[0], 14)

    def test_removal_migration_rolls_back_without_losing_existing_evidence(self):
        identity = self.stage()
        with Store(self.app.data_dir) as store:
            self.commit_rows(store, identity, [self.item()])
            before = tuple(store.connection.execute('SELECT * FROM race_results').fetchone())
            history = [tuple(row) for row in store.connection.execute('SELECT * FROM race_result_history')]
            store.connection.executescript('DROP TABLE race_import_reconciliations; DROP TABLE race_import_sections; DROP TABLE race_result_removals; PRAGMA user_version=12;')
        from rideworks import store as module
        broken = module.MIGRATION_13.replace('PRAGMA user_version = 13;', 'INSERT INTO missing VALUES(1);')
        with patch.object(module, 'MIGRATION_13', broken), self.assertRaises(sqlite3.Error):
            Store(self.app.data_dir)
        with sqlite3.connect(self.app.data_dir / 'rideworks.sqlite3') as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 12)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='race_result_removals'").fetchone())
            self.assertEqual(connection.execute('SELECT * FROM race_results').fetchone(), before)
            self.assertEqual(connection.execute('SELECT * FROM race_result_history').fetchall(), history)
        with Store(self.app.data_dir) as store:
            self.assertEqual(store.connection.execute('PRAGMA user_version').fetchone()[0], 14)
            self.assertEqual(tuple(store.connection.execute('SELECT * FROM race_results').fetchone()), before)
            self.assertEqual(race.screenshot(store, identity)[1], self.image)


if __name__ == '__main__':
    unittest.main()
