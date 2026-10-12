"""Privacy-safe application boundary, native evidence and HTTP lifecycle checks."""

import copy
from http.client import HTTPConnection
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from fit_fixture import make_fit
from rideworks.analysis import analyze_activity
from rideworks.store import Store
from rideworks.web import Application, activity_title, ascent, chart_payload, create_server, distance, duration, review_page


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name) / 'private-store'
        self.input_path = Path(self.temp.name) / 'synthetic.fit'
        self.input_path.write_bytes(make_fit())
        self.app = Application(self.data_dir)

    def import_activity(self, **kwargs):
        if kwargs:
            self.input_path.write_bytes(make_fit(**kwargs))
        with Store(self.data_dir) as store:
            result = store.import_fit(self.input_path)
            analysis = analyze_activity(store, result['activity_id'])
        return result['activity_id'], analysis

    def html(self, route):
        status, kind, body = self.app.get(route)
        self.assertEqual(kind, 'text/html')
        return status, body.decode()

    def test_empty_list_and_real_navigation(self):
        status, html = self.html('/activities')
        self.assertEqual(status, 200)
        self.assertIn('Import your first ride', html)
        self.assertIn('import-fit', html)
        self.assertIn('RideWorks', html)
        self.assertIn('href="/"', html)
        self.assertIn('href="/performance"', html)
        self.assertIn('href="/settings"', html)
        for fake in ('Dashboard', 'Training Plan', 'Sync', 'AI insights', 'Profile'):
            self.assertNotIn(fake, html)

    def test_list_stable_route_and_missing_route(self):
        activity_id, _ = self.import_activity()
        status, html = self.html('/activities')
        self.assertEqual(status, 200)
        self.assertIn(f'/activities/{activity_id}', html)
        self.assertIn('Virtual Ride', html)
        self.assertIn('data-local-time', html)
        self.assertEqual(self.html(f'/activities/{activity_id}')[0], 200)
        self.assertEqual(self.html('/activities/00000000-0000-0000-0000-000000000000')[0], 404)
        self.assertEqual(self.html('/activities/not-an-id')[0], 404)
        self.assertEqual(self.html('/unknown')[0], 404)

    def test_accepted_analysis_boundary_is_used(self):
        activity_id, analysis = self.import_activity()
        analysis['best_20_minute_power'].update(rounded_watts=321, eligible=True,
            start_timestamp=analysis['source_summary']['values']['start_time'],
            end_exclusive_timestamp='2024-11-08T12:00:00+00:00', sample_count=1200)
        with patch('rideworks.web.analyze_activity', return_value=analysis) as analyze:
            status, html = self.html(f'/activities/{activity_id}')
        self.assertEqual(status, 200)
        analyze.assert_called_once()
        self.assertEqual(analyze.call_args.args[1], activity_id)
        self.assertIn('321 W', html)
        self.assertIn('RideWorks-calculated', html)
        self.assertIn('FIT session source evidence', html)

    def test_payload_preserves_missing_zero_duplicate_gap_backward_order(self):
        _, analysis = self.import_activity(powers=(0, None, 0, 120, 130, 140),
            heart_rates=(None, 100, 0, 110, 111, None),
            timestamps=(1100000000, 1100000000, None, 1100000040, 1100000002, 1100000003))
        original = copy.deepcopy(analysis)
        html = review_page(analysis)
        data = json.loads(re.search(r'<script id="native-records" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(len(data), 6)
        self.assertEqual(data, chart_payload(analysis))
        for record, row in zip(analysis['native_records'], data):
            for key in ('record_index', 'timestamp', 'power', 'heart_rate'):
                self.assertEqual(record[key], row[key])
        self.assertEqual(data[0]['power'], 0)
        self.assertIsNone(data[1]['power'])
        self.assertIsNone(data[2]['timestamp'])
        self.assertEqual(data[0]['timestamp'], data[1]['timestamp'])
        self.assertEqual(analysis, original)

    def test_provenance_privacy_missing_and_distinct_durations(self):
        _, analysis = self.import_activity(elapsed=3600, timer=3599, max_hr=None)
        html = review_page(analysis)
        for value in [analysis['activity']['activity_id'], analysis['source']['source_id'],
                      analysis['extraction']['extraction_id'], analysis['source']['sha256'],
                      analysis['extraction']['parser_name'], analysis['extraction']['parser_version'],
                      analysis['extraction']['mapping_version'], 'best-average-power-v1',
                      'unknown', '2 present / 1 missing / 3 total', 'synthetic.fit']:
            self.assertIn(value, html)
        self.assertIn('<dt>Maximum heart rate</dt><dd>Unavailable</dd>', html)
        self.assertIn('<dt>Elapsed duration</dt><dd>1:00:00</dd>', html)
        self.assertIn('<dt>Timer duration</dt><dd>59:59</dd>', html)
        self.assertNotIn(str(self.data_dir), html)
        self.assertNotIn(str(self.input_path), html)
        self.assertNotIn('stored_path', html)
        self.assertNotIn('latitude', html)
        self.assertNotIn('longitude', html)
        self.assertIn('data-local-time', html)
        self.assertIn('(UTC source time)', html)

    def test_real_best_20_and_source_missing_are_separate(self):
        _, analysis = self.import_activity(powers=(120,) * 1200, heart_rates=(100,) * 1200,
            timestamps=tuple(1100000000 + i for i in range(1200)), elapsed=1200, timer=1199)
        html = review_page(analysis)
        self.assertIn('120 W', html)
        self.assertIn('<dt>Average power</dt><dd>Unavailable</dd>', html)
        self.assertIn('1,200 native samples', html)
        self.assertIn('Window end, exclusive (UTC)', html)

    def test_units_duration_and_source_unchanged(self):
        self.assertEqual(distance(None), 'Unavailable')
        self.assertEqual(distance(1609.344), '1.00 mi')
        self.assertEqual(distance(21575.35), '13.41 mi')
        self.assertEqual(ascent(0.3048), '1 ft')
        self.assertEqual(ascent(256), '840 ft')
        self.assertEqual(ascent(None), 'Unavailable')
        self.assertEqual(duration(3620), '1:00:20')
        self.assertEqual(duration(3621), '1:00:21')
        self.assertEqual(duration(60), '1:00')
        self.assertEqual(duration(0), '0:00')
        self.assertEqual(duration(None), 'Unavailable')
        _, analysis = self.import_activity()
        summary = analysis['source_summary']['values']
        summary.update(total_distance=1609.344, total_ascent=0.3048)
        original = copy.deepcopy(analysis)
        self.assertIn('1.00 mi', review_page(analysis))
        self.assertEqual(analysis, original)

    def test_derived_title_and_type_are_distinct_in_list_and_review(self):
        activity_id, analysis = self.import_activity()
        summary = analysis['source_summary']['values']
        expected = activity_title(summary)
        html = review_page(analysis)
        self.assertIn(f'<h1>{expected}</h1>', html)
        self.assertNotIn('<h1>Virtual Ride</h1>', html)
        self.assertIn('Derived title', html)
        self.assertIn('Cycling / Virtual Activity', html)
        self.assertIn('source activity name unavailable', html)
        self.assertIn('FIT activity type + source start date (UTC)', html)
        self.assertIn(f'<title>{expected} · RideWorks</title>', html)
        self.assertIn(expected, self.html('/activities')[1])
        self.assertIn(activity_id, html)
        self.assertIn('href="/performance"', html)
        for fake in ('Dashboard', 'Training Plan', 'AI Summary',
                     'Compare', 'Normalized power', 'Training load', 'Zone breakdown',
                     'Laps / Intervals', 'Next workout', 'Sync', 'Profile'):
            self.assertNotIn(fake, html)

    def test_title_fallback_is_deterministic_and_does_not_mutate_evidence(self):
        summary = {'sport': 'cycling', 'sub_sport': 'virtual_activity',
                   'start_time': '2026-09-29T18:17:54+00:00'}
        original = copy.deepcopy(summary)
        with patch('rideworks.web.datetime', wraps=__import__('datetime').datetime) as dates:
            self.assertEqual(activity_title(summary), 'Virtual Ride — Sep 29, 2026')
            self.assertEqual(activity_title(summary), 'Virtual Ride — Sep 29, 2026')
            dates.now.assert_not_called()
        self.assertEqual(summary, original)

    def test_title_uses_source_utc_day_across_offsets(self):
        summary = {'sport': 'cycling', 'start_time': '2026-09-29T23:30:00-07:00'}
        self.assertEqual(activity_title(summary), 'Ride — Sep 30, 2026')
        summary['start_time'] = '2026-09-30T06:30:00+00:00'
        self.assertEqual(activity_title(summary), 'Ride — Sep 30, 2026')

    def test_title_missing_date_and_type_stay_explicit(self):
        self.assertEqual(activity_title({'sport': 'cycling'}), 'Ride — date unavailable')
        self.assertEqual(activity_title({}), 'Activity — date unavailable')

    def test_source_text_is_escaped_and_not_executable(self):
        _, analysis = self.import_activity()
        analysis['source']['original_basename'] = '<script>alert(1)</script>.fit'
        html = review_page(analysis)
        self.assertNotIn('<script>alert(1)', html)
        self.assertIn('&lt;script&gt;alert(1)', html)

    def test_assets_are_local_and_path_traversal_is_not_served(self):
        for name, expected in [('style.css', 'text/css'), ('review.js', 'text/javascript'), ('mark.svg', 'image/svg+xml')]:
            status, kind, body = self.app.get('/static/' + name)
            self.assertEqual((status, kind), (200, expected))
            self.assertTrue(body)
        self.assertEqual(self.app.get('/static/../store.py')[0], 404)
        self.assertEqual(self.app.get('/static/%2e%2e/store.py')[0], 404)
        _, analysis = self.import_activity()
        html = review_page(analysis)
        self.assertNotRegex(html, r'(?:src|href)="https?://')
        self.assertNotIn('app', __import__('sys').modules)
        self.assertNotIn('flask', __import__('sys').modules)

    def test_server_loopback_restart_and_http_routes(self):
        activity_id, _ = self.import_activity()
        extraction_before = None
        for restart in range(2):
            server = create_server(self.data_dir, 0)
            self.assertEqual(server.server_address[0], '127.0.0.1')
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                connection.request('GET', f'/activities/{activity_id}')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn('script-src \'self\'', response.getheader('Content-Security-Policy'))
                html = response.read().decode()
                self.assertIn(activity_id, html)
                connection.close()
                with Store(self.data_dir) as store:
                    extraction = analyze_activity(store, activity_id)['extraction']['extraction_id']
                if restart:
                    self.assertEqual(extraction, extraction_before)
                extraction_before = extraction
            finally:
                server.shutdown()
                thread.join()
                server.server_close()


if __name__ == '__main__':
    unittest.main()
