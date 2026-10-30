"""Generated browser fixtures; no personal source titles or location data."""
import copy
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, quote, urlsplit
from uuid import UUID
import zipfile

from fit_fixture import make_fit
from test_rideworks_export import csv_bytes, row, HEADERS, TCX, GPX
from rideworks.history import PAGE_SIZE, browse, presentation
from rideworks.store import Store
from rideworks.web import Application


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'store')
        self.addCleanup(self.store.close)
        self.app = Application(self.store.data_dir)

    def export(self, rows, files=None, columns=HEADERS):
        path = self.root / 'export.zip'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('activities.csv', csv_bytes(rows, columns))
            for name, content in (files or {}).items():
                z.writestr(name, content)
        self.assertEqual(self.store.import_strava_export(path)['failures'], [])

    def html(self, route='/activities'):
        status, kind, body = self.app.get(route)
        self.assertEqual((status, kind), (200, 'text/html'))
        return body.decode()

    def many(self):
        rows = []
        for i in range(75):
            r = row(str(i + 1), title=f'Synthetic {i:02}', date=(datetime(2024, 1, 1) + timedelta(days=i)).isoformat())
            r[2] = ('Run', 'Ride', 'Virtual Ride')[i % 3]
            rows.append(r)
        self.export(rows)

    def test_default_bounded_newest_cycling_and_deterministic_pages(self):
        self.many()
        first = browse(self.store)
        second = browse(self.store, 'page=2')
        self.assertEqual((first['count'], first['total'], first['pages']), (50, 75, 2))
        self.assertEqual(len(first['rows']), PAGE_SIZE)
        self.assertEqual(len(second['rows']), 20)
        self.assertEqual(first['rows'][0]['title'], 'Synthetic 74')
        self.assertTrue(all(r['activity_type'] in ('Ride', 'Virtual Ride') for r in first['rows']))
        ids = lambda result: [r['activity_id'] for r in result['rows']]
        self.assertFalse(set(ids(first)) & set(ids(second)))
        self.assertEqual(ids(second), ids(browse(self.store, 'page=2')))
        self.assertEqual(len(browse(self.store, 'page=9999')['rows']), 20)
        self.assertEqual(browse(self.store, 'page=9999')['page'], 2)
        html = self.html()
        self.assertEqual(html.count('class="activity-row"'), PAGE_SIZE)
        self.assertIn('1–30 of 50 matching activities · 75 in history', html)
        self.assertIn('rel="next"', html)
        self.assertNotIn('rel="prev"', html)
        self.assertIn('rel="prev"', self.html('/activities?page=2'))

    def test_all_and_individual_types_include_noncycling(self):
        self.many()
        self.assertEqual(browse(self.store, 'type=all')['count'], 75)
        for kind in ('Ride', 'Virtual Ride', 'Run'):
            self.assertEqual(browse(self.store, 'type=' + quote(kind))['count'], 25)

    def test_compact_list_uses_home_columns_and_power_evidence(self):
        path = self.root / 'synthetic.fit'
        path.write_bytes(make_fit(avg_power=123))
        self.store.import_fit(path)
        html = self.html()
        headings = re.search(r'<div class="activity-columns".*?</div>', html).group()
        self.assertEqual(re.findall(r'<span>(.*?)</span>', headings),
                         ['Date', 'Effort', 'Ride', 'Distance', 'Duration', 'Avg Pwr'])
        self.assertIn('class="row-power" title="FIT session">123 W', html)
        self.assertIn('Strava Relative Effort unavailable', html)
        self.assertLess(html.index('class="row-effort"'), html.index('class="row-identity"'))

    def test_casefold_partial_literal_punctuation_and_search_old_observations(self):
        self.export([row(title='A&B <sun> 100%_Hill')])
        for q in ('a&b', '<SUN>', '100%_', 'hill'):
            self.assertEqual(browse(self.store, 'q=' + quote(q))['count'], 1)
        self.export([row(title='Renamed synthetic')])
        result = browse(self.store, 'q=' + quote('100%_'))
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['rows'][0]['title'], 'Renamed synthetic')
        self.assertEqual(len(self.store.activity_history()[0]['sources']), 2)

    def test_one_sided_two_sided_dates_and_unknown_timezone_day(self):
        self.export([row('1', date='2024-01-01T23:59:00'), row('2', date='2024-01-02T00:01:00'),
                     row('3', date='2024-01-03T00:00:00'), row('4', date='unparsed source date')])
        for query, count in [('from=2024-01-02', 2), ('to=2024-01-02', 2),
                             ('from=2024-01-02&to=2024-01-02', 1)]:
            self.assertEqual(browse(self.store, query)['count'], count)
        html = self.html('/activities?from=2024-01-01&to=2024-01-01')
        self.assertIn('2024-01-01 23:59:00 · timezone unknown', html)
        self.assertNotIn('data-local-time', html)

    def test_sort_missing_last_zero_is_known_and_stable_ties(self):
        self.export([row(str(i)) for i in range(1, 5)])
        metadata = self.store.activity_history()
        for snapshot, value in zip(metadata, (10, 0, None, 10)):
            source = copy.deepcopy(snapshot['sources'][0])
            source['source'].update(kind='file_fit', content_format='FIT')
            source['summary'] = dict(total_elapsed_time=value, total_distance=value)
            snapshot['sources'].append(source)
        with patch.object(self.store, 'activity_history', return_value=metadata):
            for sort in ('duration', 'distance'):
                result = browse(self.store, 'sort=' + sort)
                self.assertEqual([r[sort] for r in result['rows']], [10, 10, 0, None])
                self.assertLess(result['rows'][0]['activity_id'], result['rows'][1]['activity_id'])
        self.many()
        oldest = browse(self.store, 'sort=oldest')
        known_days = [r['date_day'] for r in oldest['rows'] if r['date_day']]
        self.assertEqual(known_days, sorted(known_days))

    def test_pagination_preserves_all_get_state(self):
        self.many()
        html = self.html('/activities?q=SYNTHETIC&type=all&from=2024-01-01&to=2024-12-31&sort=oldest&tz=America%2FLos_Angeles')
        link = unescape(re.search(r'rel="next" href="([^"]+)"', html).group(1))
        self.assertEqual(parse_qs(urlsplit(link).query), dict(q=['SYNTHETIC'], type=['all'],
            **{'from':['2024-01-01'], 'to':['2024-12-31']}, sort=['oldest'], page=['2'], tz=['America/Los_Angeles']))
        self.assertIn('value="SYNTHETIC"', self.html(link))
        self.assertIn('rel="prev"', self.html(link))

    def test_invalid_inputs_safe_and_no_match_state(self):
        self.export([row()])
        for q in ('page=-1', 'page=x', 'page=' + '9' * 1000, 'page=0', 'sort=DROP+TABLE',
                  'type=unknown', 'from=bogus', 'to=2024-99-99',
                  'from=2025-01-01&to=2024-01-01'):
            self.assertIn('Activities', self.html('/activities?' + q))
        self.assertEqual(self.app.get('/activities?'+'&'.join('x=1' for _ in range(21)))[0],400)
        self.assertIn('No matching activities', self.html('/activities?q=absent'))
        self.assertIn('0–0 of 0', self.html('/activities?q=absent'))

    def test_title_escaping_type_subtype_and_latest_nonempty_policy(self):
        columns = HEADERS + ['Sport Type']
        self.export([row(title='<script>alert("x")</script> & Ride') + ['IndoorCycling']], columns=columns)
        html = self.html()
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert', html)
        self.assertIn('Virtual Ride · IndoorCycling', html)
        self.assertEqual(browse(self.store, 'type=IndoorCycling')['count'], 1)
        self.export([row(title='   ') + ['IndoorCycling']], columns=columns)
        self.assertEqual(browse(self.store)['rows'][0]['title'], '<script>alert("x")</script> & Ride')

    def test_list_metadata_does_not_read_native_streams_or_private_context(self):
        self.export([row(filename='activities/a.fit')], {'activities/a.fit': make_fit()})
        statements = []
        self.store.connection.set_trace_callback(statements.append)
        with patch.object(Store, 'get_activity', side_effect=AssertionError('native snapshot loaded')):
            browse(self.store)
            html = self.html()
        self.assertFalse(any(re.search(r'\b(?:FROM|JOIN) records\b', sql, re.I) for sql in statements))
        for private in ('stored_path', 'sha256', str(self.store.data_dir), 'irrelevant description', 'latitude', 'longitude', 'native-records'):
            self.assertNotIn(private, html)

    def test_enriched_rich_fit_source_title_keeps_native_best20(self):
        data = make_fit(powers=(120,)*1200, heart_rates=(100,)*1200,
                        timestamps=tuple(1100000000+i for i in range(1200)), elapsed=1200, timer=1199)
        path = self.root / 'seed.fit'; path.write_bytes(data)
        seeded = self.store.import_fit(path)
        self.export([row(filename='activities/a.fit', title='Synthetic enriched title')], {'activities/a.fit':data})
        html = self.html('/activities/' + seeded['activity_id'])
        self.assertIn('<h1>Synthetic enriched title</h1>', html)
        self.assertIn('Source-supplied Strava-export evidence', html)
        self.assertIn('FIT session source evidence', html)
        self.assertIn('120 W', html)
        self.assertIn('native-records', html)
        self.assertNotIn('Derived title', html)
        self.assertEqual(len(self.store.activity_history()), 1)

    def test_gpx_tcx_and_csv_only_stable_routes_and_honest_thin_review(self):
        self.export([row('1', 'activities/a.gpx'), row('2', 'activities/b.tcx'), row('3')],
                    {'activities/a.gpx': GPX, 'activities/b.tcx': TCX})
        for snapshot in self.store.activity_history():
            activity_id = snapshot['activity']['activity_id']
            html = self.html('/activities/' + activity_id)
            self.assertIn('Detailed RideWorks review unavailable', html)
            self.assertIn('Strava-export metadata', html)
            self.assertIn('Native streams are unavailable from this source', html)
            self.assertNotIn('id="native-records"', html)
            self.assertNotIn('best-average-power-v1', html)
            self.assertIn('/activities/' + activity_id, self.html())
        tcx = next(s for s in self.store.activity_history() if any(e['source']['content_format']=='TCX' for e in s['sources']))
        displayed = presentation(tcx)
        self.assertEqual((displayed['duration'], displayed['distance']), (60.5,100))
        self.assertEqual(displayed['duration_source']['context'], 'TCX single lap')

    def test_derived_fallback_is_explicit_and_metadata_unchanged(self):
        self.export([row(title='')])
        snapshot = self.store.activity_history()[0]
        original = copy.deepcopy(snapshot)
        display = presentation(snapshot)
        self.assertEqual(snapshot, original)
        self.assertIn('Derived title', self.html())
        self.assertEqual(display['title'], 'Virtual Ride — Jan 2, 2024')
        self.assertIsNone(display['distance'])  # CSV units are unspecified, not metres.

    def test_specific_history_snapshot_and_missing_uuid_routes(self):
        self.export([row('1'), row('2')])
        activity_id = self.store.activity_history()[0]['activity']['activity_id']
        self.assertEqual(len(self.store.activity_history(activity_id)), 1)
        self.assertEqual(self.store.activity_history(str(UUID(int=0))), [])
        for route in ('/activities/not-an-id', '/activities/' + str(UUID(int=0)), '/activities/../../'):
            self.assertEqual(self.app.get(route)[0], 404)

    def test_absolute_file_date_uses_browser_day_and_csv_unparsed_text_is_preserved(self):
        self.export([row('1', 'activities/a.tcx', date='2024-01-03T00:00:00'),
                     row('2', date='original date text')], {'activities/a.tcx': TCX})
        result = browse(self.store, 'from=2024-01-01&to=2024-01-01&tz=America%2FLos_Angeles')
        self.assertEqual(result['count'], 1)
        self.assertTrue(result['rows'][0]['absolute_time'])
        self.assertEqual(result['rows'][0]['date_day'], '2024-01-01')
        self.assertIn('data-local-time', self.html('/activities?from=2024-01-01&to=2024-01-01&tz=America%2FLos_Angeles'))
        self.assertEqual(browse(self.store, 'from=2024-01-02&to=2024-01-02&tz=America%2FLos_Angeles')['count'], 0)
        self.assertEqual(browse(self.store, 'from=2024-01-02&to=2024-01-02&tz=UTC')['count'], 1)
        self.assertIn('original date text · source date text', self.html())

    def test_local_date_filter_uses_historical_dst_and_both_sides_of_midnight(self):
        stamps = ['2024-03-10T07:59:59+00:00', '2024-03-10T08:00:00+00:00',
                  '2024-07-01T06:59:59+00:00', '2024-07-01T07:00:00+00:00',
                  '2024-11-03T06:59:59+00:00', '2024-11-03T07:00:00+00:00']
        self.export([row(str(i), title=f'Synthetic boundary {i}', date=s) for i,s in enumerate(stamps,1)])
        for day, titles in [('2024-03-09', ['Synthetic boundary 1']), ('2024-03-10', ['Synthetic boundary 2']),
                            ('2024-06-30', ['Synthetic boundary 3']), ('2024-07-01', ['Synthetic boundary 4']),
                            ('2024-11-02', ['Synthetic boundary 5']), ('2024-11-03', ['Synthetic boundary 6'])]:
            result=browse(self.store, f'from={day}&to={day}&tz=America%2FLos_Angeles')
            self.assertEqual([r['title'] for r in result['rows']], titles)
        self.assertEqual(browse(self.store, 'from=2024-07-01&to=2024-07-01&tz=Asia%2FTokyo')['count'],2)

    def test_unknown_source_day_does_not_shift_with_browser_timezone(self):
        self.export([row(date='2024-07-01T00:01:00')])
        before=copy.deepcopy(self.store.activity_history())
        for zone in ('America/Los_Angeles', 'Asia/Tokyo', 'UTC'):
            result=browse(self.store, 'from=2024-07-01&to=2024-07-01&tz='+quote(zone))
            self.assertEqual(result['count'],1)
            self.assertFalse(result['rows'][0]['absolute_time'])
            self.assertEqual(result['rows'][0]['date_day'],'2024-07-01')
        self.assertEqual(self.store.activity_history(),before)

    def test_invalid_explicit_timezone_never_guesses_absolute_filter_day(self):
        self.export([row('1',date='2024-01-02T03:00:00+00:00'), row('2',date='2024-01-02T03:00:00')])
        for zone in ('', '../UTC', '/etc/passwd', 'NoSuch/Timezone', '<script>'):
            query='from=2024-01-02&to=2024-01-02&tz='+quote(zone)
            self.assertEqual(browse(self.store,query)['count'],1)
            self.assertEqual(self.app.get('/activities?'+query)[0],400)
        self.assertEqual(browse(self.store,'from=2024-01-02&to=2024-01-02&tz=UTC')['count'],2)

    def test_date_is_dedicated_sibling_region_with_local_time_hook(self):
        self.export([row('1', 'activities/a.tcx')], {'activities/a.tcx':TCX})
        html=self.html('/activities?tz=America%2FLos_Angeles')
        identity=re.search(r'<div class="row-identity">(.*?)</div>',html,re.S).group(1)
        date_region=re.search(r'<div class="row-date">(.*?)</div>',html,re.S).group(1)
        self.assertNotIn('<time',identity)
        self.assertIn('Synthetic ride',identity)
        self.assertIn('data-local-time data-compact-time',date_region)
        self.assertIn('<span>Date</span>',html)
        self.assertIn('name="tz" value="America/Los_Angeles"',html)
        self.assertNotIn('absolute start times use UTC',html)

    def test_multiple_fit_sources_remain_inspectable_without_guessing_selection(self):
        paths = [self.root / 'a.fit', self.root / 'b.fit']
        results = []
        for p, power in zip(paths, (100, 110)):
            p.write_bytes(make_fit(powers=(power,)*3))
            results.append(self.store.import_fit(p))
        activity_id = results[0]['activity_id']
        with self.store.connection:
            self.store.connection.execute('UPDATE sources SET activity_id=? WHERE source_id=?',
                                          (activity_id, results[1]['source_id']))
        with patch('rideworks.web.analyze_activity', side_effect=AssertionError('ambiguous analysis')):
            html = self.html('/activities/' + activity_id)
        self.assertIn('Detailed RideWorks review unavailable', html)
        self.assertIn(results[0]['source_id'], html)
        self.assertIn(results[1]['source_id'], html)
        self.assertNotIn('id="native-records"', html)


if __name__ == '__main__':
    unittest.main()
