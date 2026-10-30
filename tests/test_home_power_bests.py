"""Bounded Home power bests use only current observed Virtual Ride profiles."""
from datetime import datetime, timedelta, timezone
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fit_fixture import make_fit
from rideworks.home import training_overview
from rideworks.power_curve import curve_history, envelope, recent_bests, rebuild_curves
from rideworks.store import Store
import test_rideworks_power_curve as curve_tests

AS_OF = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)


class HomePowerBestsTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.store = Store(self.root/'data'); self.addCleanup(self.store.close)

    def api(self, identity, powers, when, **kwargs):
        return curve_tests.CurveSourceTests.api(self, identity, powers, when=when, **kwargs)

    def native(self, when, activity_id):
        epoch = datetime(1989, 12, 31, tzinfo=timezone.utc)
        start = int((when-epoch).total_seconds()); path = self.root/'synthetic.fit'
        path.write_bytes(make_fit(powers=[130]*60, heart_rates=[100]*60, timestamps=range(start,start+60),
            elapsed=59, timer=59, session_start_time=start, session_timestamp=start+59,
            event_timestamps=(start,start+59)))
        return self.store.import_file(path, activity_id=activity_id)

    def test_exact_anchors_independent_winners_and_ties(self):
        ids = [self.api(1, [400]*5+[100]*1195, AS_OF-timedelta(days=5)),
               self.api(2, [300]*60+[100]*1140, AS_OF-timedelta(days=4)),
               self.api(3, [200]*300+[100]*900, AS_OF-timedelta(days=3)),
               self.api(4, [150]*1200, AS_OF-timedelta(days=2)),
               self.api(5, [150]*1200, AS_OF-timedelta(days=1))]
        rebuild_curves(self.store)
        result = recent_bests(self.store, AS_OF)
        self.assertEqual({d:p['rounded_watts'] for d,p in result['points'].items()}, {5:400,60:300,300:200,1200:150})
        self.assertEqual([result['points'][d]['activity']['activity_id'] for d in (5,60,300,1200)], ids[:4])
        expected = envelope(curve_history(self.store)['profiles'],start=AS_OF-timedelta(days=90),end=AS_OF)
        self.assertEqual(result['points'], {p['duration_seconds']:p for p in expected['points'] if p['duration_seconds'] in (5,60,300,1200)})
        self.assertEqual(result['pending'], 0)

    def test_utc_edges_dst_outdoor_and_unknown_date(self):
        start=AS_OF-timedelta(days=90)
        included = self.api(1, [100]*60, start)
        self.api(2, [999]*60, start-timedelta(microseconds=1))
        self.api(3, [999]*60, AS_OF)
        self.api(4, [999]*60, AS_OF+timedelta(days=1))
        self.api(5, [999]*60, AS_OF-timedelta(days=1), metadata={'sport_type':'Ride'})
        self.api(6, [120]*60, AS_OF.astimezone(ZoneInfo('America/Los_Angeles'))-timedelta(hours=3))
        rebuild_curves(self.store)
        result=recent_bests(self.store, AS_OF.astimezone(ZoneInfo('America/Los_Angeles')))
        self.assertEqual(result['points'][5]['rounded_watts'], 120)
        self.assertEqual(result['validated'], 2)
        self.assertIn(included, {p['activity']['activity_id'] for p in curve_history(self.store)['profiles']})
        # A selected file with an offset-unknown start overrides the absolute API date.
        self.native(AS_OF-timedelta(days=1),included)
        self.store.connection.execute('UPDATE sessions SET start_time=? WHERE extraction_id=(SELECT extraction_id FROM extractions WHERE source_id=(SELECT source_id FROM sources WHERE activity_id=?))', ('2026-10-31T12:00:00',included))
        self.assertEqual(recent_bests(self.store,AS_OF)['validated'], 1)
        with self.assertRaises(ValueError): recent_bests(self.store, AS_OF.replace(tzinfo=None))

    def test_selected_file_date_precedence_and_stale_or_missing(self):
        identity=self.api(1,[300]*60,AS_OF-timedelta(days=1))
        self.native(AS_OF-timedelta(days=200),identity)
        other=self.api(2,[120]*60,AS_OF-timedelta(days=200))
        self.native(AS_OF-timedelta(days=2),other)
        rebuild_curves(self.store)
        result=recent_bests(self.store,AS_OF)
        self.assertEqual(result['points'][5]['rounded_watts'],130)
        self.assertEqual(result['validated'],1)
        self.store.connection.execute('DELETE FROM power_curve_profiles WHERE activity_id=?',(other,))
        self.assertEqual(recent_bests(self.store,AS_OF)['pending'],1)
        rebuild_curves(self.store)
        self.store.connection.execute('UPDATE sessions SET avg_power=123 WHERE extraction_id=(SELECT extraction_id FROM extractions WHERE source_id=(SELECT source_id FROM sources WHERE activity_id=?))',(other,))
        result=recent_bests(self.store,AS_OF)
        self.assertEqual(result['pending'],1);self.assertEqual(result['points'],{})

    def test_api_date_takes_precedence_over_csv_and_csv_only_is_considered(self):
        export=self.root/'export'; export.mkdir()
        with (export/'activities.csv').open('w', newline='') as stream:
            writer=csv.writer(stream)
            writer.writerow(['Activity ID','Activity Name','Activity Type','Activity Date','Filename'])
            writer.writerow(['1','Synthetic old CSV','Virtual Ride',(AS_OF-timedelta(days=200)).isoformat(),''])
            writer.writerow(['2','Synthetic recent CSV','Virtual Ride',(AS_OF-timedelta(days=1)).isoformat(),''])
            writer.writerow(['3','Synthetic CSV only','Virtual Ride',(AS_OF-timedelta(days=2)).isoformat(),''])
            writer.writerow(['4','Synthetic missing date','Virtual Ride','',''])
            writer.writerow(['5','Synthetic unknown offset','Virtual Ride',(AS_OF-timedelta(days=2)).replace(tzinfo=None).isoformat(),''])
        self.store.import_strava_export(export)
        first=self.api(1,[140]*60,AS_OF-timedelta(days=1))
        self.api(2,[900]*60,AS_OF-timedelta(days=200))
        rebuild_curves(self.store)
        result=recent_bests(self.store,AS_OF)
        self.assertEqual(result['points'][5]['activity']['activity_id'],first)
        self.assertEqual(result['points'][5]['rounded_watts'],140)
        self.assertEqual(result['validated'],2)  # recent API plus CSV-only activity
        self.assertEqual(result['pending'],0)

    def test_conflicting_file_starts_follow_existing_presentation_precedence(self):
        identity=self.api(1,[100]*60,AS_OF-timedelta(days=1))
        self.native(AS_OF-timedelta(days=200),identity)
        self.native(AS_OF-timedelta(days=1),identity)
        rebuild_curves(self.store)
        # A later file or API date does not override the first selected file.
        self.assertEqual(recent_bests(self.store,AS_OF)['validated'],0)

    def test_read_only_bounded_signatures_and_zero(self):
        current=self.api(1,[0]*60,AS_OF-timedelta(days=1))
        for i in range(2,22): self.api(i,[200]*60,AS_OF-timedelta(days=100+i))
        rebuild_curves(self.store)
        from rideworks import power_curve
        original=power_curve.signature
        with patch.object(power_curve,'signature',wraps=original) as signatures, patch.object(power_curve,'mmp',side_effect=AssertionError('raw recomputation')), patch.object(self.store,'get_source',side_effect=AssertionError('raw read')), patch.object(power_curve,'rebuild_curves',side_effect=AssertionError('rebuild')):
            before=self.store.connection.total_changes
            result=recent_bests(self.store,AS_OF)
            self.assertEqual(self.store.connection.total_changes,before)
        self.assertEqual(signatures.call_count,1)
        self.assertEqual(result['validated'],1);self.assertEqual(result['points'][5]['rounded_watts'],0)
        self.assertEqual(result['points'][5]['activity']['activity_id'],current)

    def test_pending_and_unavailable_are_visible_in_overview(self):
        data=dict(today='2026-11-01',last7=dict(miles=0,distance_unavailable=0),prior7=dict(miles=0,distance_unavailable=0))
        bests=dict(points={5:dict(rounded_watts=0)},pending=1)
        html=training_overview(data,dict(days=[]),dict(value=None),bests)
        self.assertIn('0 W',html);self.assertIn('Update needed',html)
        self.assertIn('Some recent power profiles need an update',html)
        self.assertIn('Qualifying observed Virtual Ride power',html)
        self.assertNotIn('home-overview-metric',html)

    def test_partial_coverage_retains_valid_bests_and_warns(self):
        valid=self.api(1,[120]*60,AS_OF-timedelta(days=2))
        stale=self.api(2,[400]*60,AS_OF-timedelta(days=1))
        rebuild_curves(self.store)
        self.store.connection.execute('DELETE FROM power_curve_profiles WHERE activity_id=?',(stale,))
        result=recent_bests(self.store,AS_OF)
        self.assertEqual(result['points'][5]['activity']['activity_id'],valid)
        self.assertEqual(result['pending'],1)
        data=dict(today='2026-11-01',last7=dict(miles=0,distance_unavailable=0),prior7=dict(miles=0,distance_unavailable=0))
        html=training_overview(data,dict(days=[]),dict(value=None),result)
        self.assertIn('120 W',html)
        self.assertIn('Update needed',html)
        self.assertIn('bests may be incomplete',html)

    def test_wrong_cached_method_or_grid_is_pending(self):
        identity=self.api(1,[120]*60,AS_OF-timedelta(days=1))
        rebuild_curves(self.store)
        self.store.connection.execute('UPDATE power_curve_profiles SET method=? WHERE activity_id=?',('obsolete',identity))
        self.assertEqual(recent_bests(self.store,AS_OF)['pending'],1)
        rebuild_curves(self.store,force=True)
        self.store.connection.execute("UPDATE power_curve_profiles SET result_json=json_set(result_json,'$.grid','obsolete') WHERE activity_id=?",(identity,))
        result=recent_bests(self.store,AS_OF)
        self.assertEqual(result['pending'],1)
        self.assertEqual(result['points'],{})
