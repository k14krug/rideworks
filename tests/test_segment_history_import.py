"""Synthetic evidence for bounded API and reviewed clipboard history imports."""
from datetime import timedelta
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

from rideworks.segment_import import parse_paste
from rideworks.segments import tracked_counts
from rideworks.segments_page import sorted_efforts
from rideworks import store as store_module
from test_rideworks_segments import ACTIVITY, EFFORT, ORIGIN, Response, SEGMENT
import test_rideworks_segments as fixtures


class SegmentHistoryTests(unittest.TestCase):
    setUp = fixtures.SegmentTests.setUp
    client = fixtures.SegmentTests.client
    observation = fixtures.SegmentTests.observation
    count = fixtures.SegmentTests.count
    attempt = fixtures.SegmentTests.attempt
    detail = fixtures.SegmentTests.detail
    listing = fixtures.SegmentTests.listing
    add = fixtures.SegmentTests.add
    sync = fixtures.SegmentTests.sync

    def import_post(self, action, fields, origin=ORIGIN):
        fields = {'nonce': self.settings.nonce} | fields
        return self.app.post('/segments/history/'+action, urlencode(fields).encode(), origin)

    def watch(self):
        self.http.responses.append(Response(self.detail(ACTIVITY, self.attempt())))
        self.assertEqual(self.add()[0], 303)

    def preview(self, method, paste=''):
        result = self.import_post('preview', {'segment':str(SEGMENT), 'method':method, 'paste':paste})
        self.assertEqual(result[:2], (303, {'Location':'/segments?preview=1'}))
        return self.app.get('/segments?preview=1')[2].decode()

    def save(self, **decisions):
        preview = self.settings.current_history_preview()
        result = self.import_post('save', {'preview':preview['token']} | decisions)
        self.assertEqual(result[0], 303)
        return self.settings.segment_history_notice

    def api_rows(self, count):
        rows = []
        for i in range(count):
            stamp = self.start + timedelta(hours=i)
            rows.append(self.attempt(activity=ACTIVITY, effort=EFFORT-1-i,
                                     start_date=stamp.isoformat(),
                                     start_date_local=stamp.isoformat().replace('+00:00', 'Z')))
        return rows

    def test_api_preview_splits_capped_history_deduplicates_boundary_and_saves_once(self):
        self.watch()
        rows = self.api_rows(140)
        self.http.responses.extend(map(Response, [rows[40:], rows[:91], rows[90:]]))
        self.assertEqual(self.import_post('preview',{},origin=None)[0], 403)
        with self.settings.operation:
            self.assertEqual(self.import_post('preview',{'segment':str(SEGMENT),'paste':'','method':'api'})[0], 409)
        html = self.preview('api')
        self.assertIn('140 validated efforts', html)
        self.assertEqual(self.count('strava_saved_efforts'), 1)
        q = [parse_qs(urlsplit(r.full_url).query) for r in self.http.requests[1:]]
        self.assertTrue(all(r['per_page']==['100'] for r in q))
        self.assertIn('end_date_local', q[1])
        self.assertIn('start_date_local', q[2])
        self.assertIn('Saved 140', self.save())
        self.assertEqual(self.count('strava_saved_efforts'), 141)
        self.http.responses.append(Response(rows[:70]))
        self.assertIn('70 already saved · 0 to save', self.preview('api'))
        self.assertEqual(len(self.http.requests), 5)

    def test_api_five_read_budget_and_invalid_bounded_response(self):
        self.watch()
        rows = self.api_rows(650)
        calls = []

        class Client:
            rate = {}
            def segment_efforts(inner, token, segment_id, **kwargs):
                calls.append(kwargs)
                return [r for r in rows
                        if kwargs.get('start_date_local', '') <= r['start_date_local']
                        <= kwargs.get('end_date_local', 'Z')][-100:]

        self.settings.client_factory = lambda creds: Client()
        self.assertIn('date windows were left unverified', self.preview('api'))
        self.assertEqual(len(calls), 5)
        self.assertEqual(self.count('strava_saved_efforts'), 1)
        self.settings.client_factory = self.client
        self.http.responses.extend(map(Response, [rows[:100], rows[400:401], rows[60:61]]))
        html = self.preview('api')
        self.assertIn('could not be verified against its date bounds', html)
        self.assertIn('100 validated efforts', html)
        self.assertEqual(len(self.http.requests), 4)

    def test_api_404_offers_paste_and_429_preserves_verified_partial_results(self):
        self.watch()
        self.http.responses.append(HTTPError('https://www.strava.com', 404, '', {}, io.BytesIO()))
        self.assertIn('Try Paste My Results', self.preview('api'))
        rows = self.api_rows(100)
        self.http.responses.extend([Response(rows), HTTPError('https://www.strava.com', 429, '', {}, io.BytesIO())])
        self.assertIn('Further reads stopped.', self.preview('api'))
        self.assertIn('Saved 100', self.save())
        self.assertEqual(self.count('strava_saved_efforts'), 101)
        self.assertEqual(len(self.http.requests), 4)

    def test_paste_fragments_large_batch_and_normalized_replay(self):
        self.watch()
        fragment = f'| 9 | [Rider](https://www.strava.com/athletes/1) | [May 3, 2020](https://www.strava.com/activities/{ACTIVITY}) | 25 mph | 180 Wsvg | 4:01 |'
        block = '\n\n'.join([fragment, '| :-: | :--- | :-- | :-- | :-- | :-- |',
                             '2020-05-04\t5:05', 'not a valid result',
                             *[f'2020-06-{i:02d}\t6:00' for i in range(1,26)]])
        html = self.preview('paste', block)
        self.assertIn('27 readable rows', html)
        self.assertIn('1 unparsed', html)
        self.assertIn('0 unique ride links', html)
        self.assertEqual(self.count('strava_pasted_efforts'), 0)
        self.assertIn('Saved 27', self.save())
        reformat = block.replace('| 9 |', '| 3 |').replace('180 Wsvg','—')
        self.assertIn('This batch was already reviewed.', self.preview('paste', reformat))
        self.assertEqual(self.count('strava_pasted_efforts'), 27)
        self.assertEqual(len(self.http.requests), 1)
        self.assertEqual(len(parse_paste(block)[0]), 27)

    def test_browser_plain_text_groups_multiline_rows_without_inventing_links(self):
        block = ('Rank Name Date Speed HR Power Time\n'
                 '1\tRider\tMar 9, 2024\t21.5 mph\t146 bpm\n'
                 '191 Wsvg\n34:24\n\n'
                 '2 Rider Mar 10, 2024\n35:05\n'
                 '3 Rider Mar 11, 2024 20 mph\n\n'
                 '4 Rider Mar 12, 2024\n—\n36:05')
        rows, invalid = parse_paste(block)
        self.assertEqual([(r.calendar_day, r.displayed_seconds, r.external_activity_id) for r in rows],
                         [('2024-03-09', 2064, None), ('2024-03-10', 2105, None), ('2024-03-12', 2165, None)])
        self.assertEqual(invalid, [(8, '3 Rider Mar 11, 2024 20 mph')])
        self.watch()
        self.assertIn('3 readable rows · 0 unique ride links · 1 unparsed', self.preview('paste', block))
        self.assertIn('Saved 3', self.save())

    def test_failed_paste_retains_draft_and_shows_actionable_result(self):
        self.watch()
        html = self.preview('paste', '</textarea><script>unsafe</script>')
        self.assertIn('Nothing imported.', html)
        self.assertIn(f'name="segment" value="{SEGMENT}"', html)
        self.assertIn('&lt;/textarea&gt;&lt;script&gt;unsafe&lt;/script&gt;</textarea>', html)
        self.assertNotIn('<button>Save history</button>', html)
        self.assertEqual(self.count('strava_pasted_efforts'), 0)
        self.settings.configured = lambda: None
        result = self.import_post('preview', {'segment': str(SEGMENT), 'method': 'api', 'paste': 'Draft text'})
        self.assertEqual(result[:2], (303, {'Location': f'/segments?import={SEGMENT}#segment-import'}))
        html = self.app.get(result[1]['Location'])[2].decode()
        self.assertIn('Connect Strava in Settings or try Paste My Results.', html)
        self.assertIn(f'name="segment" value="{SEGMENT}"', html)
        self.assertIn('>Draft text</textarea>', html)

    def test_paste_overlap_defaults_and_explicit_same_ride_multiplicity(self):
        self.watch()
        day = (self.start+timedelta(seconds=5)).date().isoformat()
        row=f'| [{day}](https://www.strava.com/activities/{ACTIVITY}) | 6:15 |'
        self.preview('paste', row+'\n2030-01-01\t1:00')
        self.assertIn('1 possible duplicates skipped', self.save())
        html = self.preview('paste', '\n'.join([row,row,'2030-01-02\t1:01']))
        self.assertIn('2 possible duplicates skipped by default', html)
        self.assertIn('Saved 3', self.save(r0='keep',r1='keep'))
        self.assertEqual(self.count('strava_saved_efforts'), 1)
        self.assertEqual(self.count('strava_pasted_efforts'), 4)

    def test_later_sync_retains_both_until_explicit_match_and_counts_distinct(self):
        self.watch()
        source = self.listing(100)
        day = (self.start+timedelta(seconds=5)).date().isoformat()
        self.preview('paste', f'| [{day}](https://www.strava.com/activities/100) | 235 W | 151 bpm | 6:15 |')
        self.assertIn('Saved 1', self.save())
        self.http.responses.extend([Response([source]), Response(self.detail(
            100, self.attempt(activity=100, effort=11, average_watts=237, device_watts=True)))])
        self.assertEqual(json.loads(self.sync(home=True)[2])['status'],'complete')
        ride = self.store.connection.execute("SELECT activity_id FROM strava_api_activities WHERE external_id='100'").fetchone()[0]
        self.assertEqual(tracked_counts(self.store,[ride]), {ride:1})
        html = self.app.get(f'/segments?ride={ride}')[2].decode()
        self.assertIn('2 saved', html)
        self.assertIn('Review possible API match', html)
        pid = self.store.connection.execute('SELECT paste_id FROM strava_pasted_efforts').fetchone()[0]
        self.assertEqual(self.import_post('match',{'paste_id':str(pid),'effort':'api:11'})[0],303)
        html = self.app.get(f'/segments?ride={ride}')[2].decode()
        self.assertIn('1 saved', html)
        self.assertIn('Strava API and My Results paste', html)
        metric = self.store.connection.execute(
            "SELECT avg_power, avg_hr, device_watts, power_source, hr_source FROM strava_segment_history WHERE effort_id='11'"
        ).fetchone()
        self.assertEqual(tuple(metric), (237, 151, 1, 'api', 'paste'))
        self.assertEqual(self.count('strava_pasted_efforts'),1)
        self.assertEqual(self.count('strava_saved_efforts'),2)

    def test_effort_metrics_add_detail_and_replay_fills_missing_only(self):
        row = self.attempt(average_watts=215.5, average_heartrate='broken', device_watts=False)
        self.http.responses.append(Response(self.detail(ACTIVITY, row)))
        self.assertEqual(self.add()[0], 303)
        replay = self.attempt(average_watts=999, average_heartrate=145.2, device_watts=True)
        self.http.responses.append(Response([replay]))
        self.assertIn('New metrics are available for 1 saved efforts.', self.preview('api'))
        self.assertIn('Added metrics to 1 saved efforts.', self.save())
        self.http.responses.append(Response([self.attempt(average_watts=-1, average_heartrate=False)]))
        self.assertNotIn('<button>Save history</button>', self.preview('api'))
        self.assertEqual(tuple(self.store.connection.execute(
            'SELECT avg_power, avg_hr, device_watts FROM strava_saved_efforts').fetchone()), (215.5, 145.2, 0))

    def test_paste_metrics_replay_enriches_unique_rows_preserves_known_and_ignores_bad_optional(self):
        self.watch()
        self.preview('paste', '2024-03-09\t210 W\t5:02\n2024-03-10\t5:03\n2024-03-10\t5:03')
        self.save()
        replay = ('1 Rider Mar 9, 2024\n150 bpm\n275 Wsvg\n5:02\n'
                  '2 Rider Mar 10, 2024\ninvalid W\n—\n5:03\n'
                  '3 Rider Mar 10, 2024\n225 W\n5:03')
        html = self.preview('paste', replay)
        self.assertIn('3 readable rows', html)
        self.assertIn('New metrics are available for 1 saved efforts.', html)
        self.assertIn('Added metrics to 1 saved efforts.', self.save())
        saved = self.store.connection.execute(
            'SELECT avg_power, avg_hr FROM strava_pasted_efforts ORDER BY paste_id').fetchall()
        self.assertEqual([tuple(row) for row in saved], [(210, 150), (None, None), (None, None)])

    def test_v17_upgrade_preserves_saved_api_and_confirmed_and_unmatched_paste(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(store_module, 'MIGRATION_18', ''):
                with store_module.Store(folder) as old:
                    self.assertEqual(old.connection.execute('PRAGMA user_version').fetchone()[0], 17)
                    old.connection.executescript("""
                        INSERT INTO strava_watched_segments VALUES ('1','2','Watch');
                        INSERT INTO strava_saved_efforts VALUES ('3','1','4','2024-01-01T12:00:00+00:00',60);
                        INSERT INTO strava_paste_batches VALUES ('batch','1');
                        INSERT INTO strava_pasted_efforts VALUES (1,'batch','4','2024-01-01',60,'3');
                        INSERT INTO strava_pasted_efforts VALUES (2,'batch',NULL,'2024-02-01',90,NULL);
                    """)
            with store_module.Store(folder) as upgraded:
                self.assertEqual(upgraded.connection.execute('PRAGMA user_version').fetchone()[0], 18)
                rows = upgraded.connection.execute(
                    'SELECT effort_id, paste_id, seconds, source, avg_power, avg_hr FROM strava_segment_history ORDER BY paste_id'
                ).fetchall()
                self.assertEqual([tuple(row) for row in rows], [('3', 1, 60, 'both', None, None),
                                                               (None, 2, 90, 'paste', None, None)])
                self.assertEqual(upgraded.connection.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_date_sort_uses_the_displayed_day_for_timestamps_and_pasted_dates(self):
        api = {'start_time': '2024-03-10T01:00:00+00:00', 'calendar_day': None}
        paste = {'start_time': None, 'calendar_day': '2024-03-10'}
        efforts = [api, paste]
        self.assertEqual(sorted_efforts(efforts, 'date', 'desc', ZoneInfo('America/Los_Angeles')), [paste, api])
        self.assertEqual(sorted_efforts(efforts, 'date', 'desc', ZoneInfo('UTC')), [api, paste])
