"""Synthetic evidence for bounded API and reviewed clipboard history imports."""
from datetime import timedelta
import io
import json
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit

from rideworks.segment_import import parse_paste
from rideworks.segments import tracked_counts
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
        return self.settings.segment_notice

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
        self.preview('paste', f'| [{day}](https://www.strava.com/activities/100) | 6:15 |')
        self.assertIn('Saved 1', self.save())
        self.http.responses.extend([Response([source]), Response(self.detail(100, self.attempt(activity=100,effort=11)))])
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
        self.assertEqual(self.count('strava_pasted_efforts'),1)
        self.assertEqual(self.count('strava_saved_efforts'),2)
