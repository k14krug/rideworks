"""Synthetic analytical persistence/cohort/UI cases; no personal fixtures."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fit_fixture import make_fit
from test_rideworks_export import csv_bytes, row
from rideworks.analysis import analyze_activity
from rideworks.errors import IntegrityError
from rideworks.performance import classification, performance_history, rebuild_performance
from rideworks.store import Store
from rideworks.web import Application


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'data')
        self.addCleanup(self.store.close)
        self.app = Application(self.store.data_dir)

    def native(self, watts=120, count=1200, *, activity_id=None, marker=150):
        path = self.root / 'synthetic.fit'
        path.write_bytes(make_fit(powers=[watts]*count, heart_rates=[100]*count,
                                  timestamps=range(1100000000,1100000000+count), max_hr=marker))
        return self.store.import_file(path, activity_id=activity_id)

    def csv(self, kind='Virtual Ride', title='Synthetic <ride> & name'):
        # Enrich the most recently supplied file through established byte identity.
        source = self.store.connection.execute('SELECT * FROM sources ORDER BY imported_at DESC LIMIT 1').fetchone()
        r = row('1', 'activities/synthetic.fit' if source else '', title=title)
        r[2] = kind
        path = self.root / 'export.zip'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('activities.csv', csv_bytes([r]))
            if source:
                z.writestr('activities/synthetic.fit', (self.store.data_dir/source['stored_path']).read_bytes())
        report = self.store.import_strava_export(path)
        self.assertEqual(report['failures'], [])

    def result(self):
        return performance_history(self.store)['results'][0]

    def test_virtual_native_result_preserves_context_and_exact_analysis(self):
        imported = self.native()
        self.csv()
        before = self.store.get_source(imported['source_id'])
        report = rebuild_performance(self.store)
        self.assertEqual((report['evaluated'],report['virtual_candidates'],report['eligible']),(1,1,1))
        result = self.result()
        self.assertEqual(result['rounded_watts'],120)
        self.assertEqual(result['source_id'],imported['source_id'])
        self.assertEqual(result['extraction_id'],imported['extraction_id'])
        self.assertEqual(result['classification']['basis'],'latest_strava_type')
        self.assertEqual(len(result['classification']['source_ids']),1)
        best = analyze_activity(self.store, imported['activity_id'])['best_20_minute_power']
        for key in ('average_watts','rounded_watts','start_record_index','end_exclusive_record_index',
                    'start_timestamp','end_exclusive_timestamp','eligible_window_count'):
            self.assertEqual(result[key],best[key])
        self.assertEqual(self.store.get_source(imported['source_id']),before)
        saved = self.store.connection.execute('SELECT result_json FROM performance_history').fetchone()[0]
        self.assertNotIn('"records"', saved)

    def test_outdoor_and_noncycling_never_load_native_records(self):
        self.native()
        for kind, reason in [('Ride','outdoor_ride_excluded'),('Run','non_virtual_activity')]:
            self.csv(kind)
            with patch.object(self.store,'get_source',side_effect=AssertionError('excluded stream read')):
                report = rebuild_performance(self.store)
            self.assertEqual(report['eligible'],0)
            self.assertEqual(self.result()['reason'],reason)
            self.assertEqual(performance_history(self.store)['points'],[])

    def test_csv_summary_alone_is_never_native_power(self):
        self.csv()
        report = rebuild_performance(self.store)
        self.assertEqual(report['eligible'],0)
        self.assertEqual(self.result()['reason'],'no_native_file_source')

    def test_native_virtual_fallback_and_conflicting_evidence(self):
        first = self.native()
        rebuild_performance(self.store)
        self.assertEqual(self.result()['classification']['basis'],'native_session')
        self.assertTrue(self.result()['eligible'])
        second = self.native(activity_id=first['activity_id'],marker=151)
        self.store.connection.execute("UPDATE sessions SET sub_sport='generic' WHERE extraction_id=?",(second['extraction_id'],))
        rebuild_performance(self.store)
        self.assertEqual(self.result()['reason'],'ambiguous_classification')
        self.csv('Ride')
        rebuild_performance(self.store)
        self.assertEqual(self.result()['reason'],'outdoor_ride_excluded')

    def test_latest_nonempty_csv_type_identity_is_retained(self):
        self.native()
        self.csv('Ride'); self.csv('Virtual Ride')
        latest = self.store.connection.execute('SELECT source_id FROM strava_export_sources ORDER BY imported_at DESC LIMIT 1').fetchone()[0]
        self.csv('')
        cohort = classification(self.store.activity_history()[0])
        self.assertEqual(cohort['activity_type'],'Virtual Ride')
        self.assertEqual(cohort['source_ids'],[latest])

    def test_multiple_eligible_sources_excluded_one_eligible_plus_short_allowed(self):
        first = self.native()
        self.native(activity_id=first['activity_id'],count=1199,marker=151)
        self.assertEqual(rebuild_performance(self.store)['eligible'],1)
        self.native(activity_id=first['activity_id'],marker=152)
        self.assertEqual(rebuild_performance(self.store)['eligible'],0)
        self.assertEqual(self.result()['reason'],'multiple_eligible_native_sources')

    def test_short_missing_power_and_no_power_have_explicit_reasons(self):
        first = self.native(count=1199)
        rebuild_performance(self.store)
        self.assertEqual(self.result()['reason'],'activity_shorter_than_required')
        self.store.connection.execute('UPDATE records SET power=NULL WHERE extraction_id=?',(first['extraction_id'],))
        self.store.connection.execute('UPDATE extractions SET power_present=0 WHERE extraction_id=?',(first['extraction_id'],))
        rebuild_performance(self.store)
        self.assertEqual(self.result()['reason'],'no_native_power')

    def test_unknown_native_timezone_is_not_guessed(self):
        first = self.native()
        self.store.connection.execute("UPDATE records SET timestamp=substr(timestamp,1,19) WHERE extraction_id=?",(first['extraction_id'],))
        rebuild_performance(self.store)
        self.assertEqual(self.result()['reason'],'native_timestamp_timezone_unknown')

    def test_rebuild_idempotence_and_restart(self):
        self.native(); self.csv()
        report = rebuild_performance(self.store)
        before = self.result(); before.pop('calculated_at')
        self.assertEqual(rebuild_performance(self.store), report)
        after = self.result(); after.pop('calculated_at')
        self.assertEqual(before,after)
        with Store(self.store.data_dir) as restarted:
            self.assertEqual(performance_history(restarted)['points'],performance_history(self.store)['points'])
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM performance_history').fetchone()[0],1)

    def test_reextraction_and_added_source_and_changed_classification_invalidate(self):
        first = self.native(); self.csv()
        rebuild_performance(self.store)
        self.store.reextract(first['source_id'])
        self.assertEqual(performance_history(self.store)['points'],[])
        rebuild_performance(self.store)
        self.csv('Ride')
        self.assertEqual(performance_history(self.store)['points'],[])
        self.assertEqual(performance_history(self.store)['stale'],1)
        self.csv('Virtual Ride'); rebuild_performance(self.store)
        self.native(activity_id=first['activity_id'],marker=151)
        self.assertEqual(performance_history(self.store)['points'],[])

    def test_fatal_rebuild_failure_retains_prior_complete_history(self):
        first=self.native(); rebuild_performance(self.store)
        before=[tuple(r) for r in self.store.connection.execute('SELECT * FROM performance_history')]
        for bad in ('not-a-time',):
            self.store.connection.execute('UPDATE records SET timestamp=? WHERE extraction_id=? AND record_index=0',(bad,first['extraction_id']))
            with self.assertRaises(IntegrityError): rebuild_performance(self.store)
        self.assertEqual([tuple(r) for r in self.store.connection.execute('SELECT * FROM performance_history')],before)

    def test_corrupt_record_count_is_fatal(self):
        first=self.native()
        self.store.connection.execute('DELETE FROM records WHERE extraction_id=? AND record_index=0',(first['extraction_id'],))
        with self.assertRaises(IntegrityError): rebuild_performance(self.store)

    def test_missing_extraction_is_corruption_not_normal_ineligibility(self):
        first=self.native()
        self.store.connection.execute('DELETE FROM extractions WHERE extraction_id=?',(first['extraction_id'],))
        with self.assertRaises(IntegrityError): rebuild_performance(self.store)
        with self.assertRaises(IntegrityError): performance_history(self.store)

    def test_independent_segmentation_oracle_matches_direct_window_calculation(self):
        from tools.verify_rideworks_performance import independent_best
        from tools.verify_rideworks_analysis import independent_best_20
        from test_rideworks_analysis import records_for
        cases=[records_for([0]*1201), records_for([100]*1200+[200]*1200),
               records_for([120]*1200+[None]+[120]*1200),
               records_for([120]*2400,list(range(1200))+list(range(1201,2401))),
               records_for([100]*1200+[100]*1200,list(range(1200))*2)]
        for records in cases:
            self.assertEqual(independent_best(records),independent_best_20(records))

    def test_unknown_activity_date_remains_supplied_in_performance_payload(self):
        self.native(); self.csv()
        self.store.connection.execute('UPDATE sessions SET start_time=NULL')
        rebuild_performance(self.store)
        points=performance_history(self.store)['points']
        self.assertEqual(points[0]['date_day'],'2024-01-02')
        self.assertFalse(points[0]['absolute_time'])

    def test_missing_longitudinal_date_retains_result_without_plot(self):
        self.native()
        self.store.connection.execute('UPDATE sessions SET start_time=NULL')
        rebuild_performance(self.store)
        history=performance_history(self.store)
        self.assertTrue(history['results'][0]['eligible'])
        self.assertEqual(history['missing_dates'],1)
        self.assertEqual(history['points'],[])

    def test_performance_routes_payload_escaping_and_metadata_only(self):
        self.native(); self.csv(); rebuild_performance(self.store)
        statements=[]; self.store.connection.set_trace_callback(statements.append)
        history=performance_history(self.store)
        self.assertFalse(any('FROM records' in s for s in statements))
        with patch.object(Store,'get_source',side_effect=AssertionError('UI read native stream')):
            status,_,body=self.app.get('/performance')
        self.assertEqual(status,200)
        html=body.decode()
        self.assertIn('href="/performance" class="active" aria-current="page"',html)
        self.assertIn('href="/" class="active" aria-current="page"',self.app.get('/')[2].decode())
        self.assertIn('\\u003c',html)
        self.assertIn('data-view="rolling" aria-pressed="true"',html)
        self.assertIn('Monthly best',html)
        self.assertIn('Yearly best',html)
        self.assertIn('Future Performance candidates',html)
        self.assertNotIn('data-mode=',html)
        self.assertNotIn('performance-modes',html)
        self.assertIn('data-range="1yr" aria-pressed="true"',html)
        self.assertIn('Current 42-day best',html)
        self.assertIn('Best in last 12 months',html)
        self.assertIn('id="performance-view"',html)
        payload=html.split('<script id="performance-points" type="application/json">')[1].split('</script>')[0]
        points=json.loads(payload)
        self.assertEqual(points,history['points'])
        self.assertNotIn('native_records',payload)
        self.assertNotIn(str(self.root),html)

    def test_unbuilt_and_ineligible_empty_states(self):
        self.assertIn('has not been rebuilt',self.app.get('/performance')[2].decode())
        self.csv('Ride'); rebuild_performance(self.store)
        self.assertIn('No current ride result qualifies',self.app.get('/performance')[2].decode())

    def test_xml_tcx_and_gpx_use_same_native_method(self):
        for fmt in ('TCX','GPX'):
            with self.subTest(fmt=fmt):
                base=datetime(2024,1,2,tzinfo=timezone.utc)
                times=[(base+timedelta(seconds=i)).isoformat() for i in range(1201)]
                if fmt=='TCX':
                    track=''.join(f'<Trackpoint><Time>{t}</Time><Extensions><ae:TPX><ae:Watts>120</ae:Watts></ae:TPX></Extensions></Trackpoint>' for t in times)
                    xml=f'<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2" xmlns:ae="http://www.garmin.com/xmlschemas/ActivityExtension/v2"><Activities><Activity Sport="Biking"><Id>{times[0]}</Id><Lap StartTime="{times[0]}"><Track>{track}</Track></Lap></Activity></Activities></TrainingCenterDatabase>'
                else:
                    track=''.join(f'<trkpt><time>{t}</time><extensions><power>120</power></extensions></trkpt>' for t in times)
                    xml=f'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><type>cycling</type><trkseg>{track}</trkseg></trk></gpx>'
                path=self.root/f'synthetic.{fmt.lower()}'; path.write_text(xml)
                imported=self.store.import_file(path)
                # Export observation establishes Virtual Ride for the XML Activity.
                csvrow=row('2' if fmt=='TCX' else '3',f'activities/{path.name}')
                export=self.root/'xml-export.zip'
                with zipfile.ZipFile(export,'w') as z:
                    z.writestr('activities.csv',csv_bytes([csvrow])); z.writestr(f'activities/{path.name}',path.read_bytes())
                self.assertEqual(self.store.import_strava_export(export)['failures'],[])
                rebuild_performance(self.store)
                result=next(r for r in performance_history(self.store)['results'] if r['activity_id']==imported['activity_id'])
                self.assertTrue(result['eligible'])
                self.assertEqual(result['rounded_watts'],120)
                self.assertEqual(result['start_record_index'],0)
                self.assertEqual(result['eligible_window_count'],2)

    def test_schema3_migration_preserves_evidence_and_failed_ddl_rolls_back(self):
        from rideworks import store as module
        root=self.root/'schema3'
        with patch('rideworks.store.MIGRATION_4',''):
            with Store(root) as old:
                self.assertEqual(old.connection.execute('PRAGMA user_version').fetchone()[0],3)
        broken=module.MIGRATION_4.replace('PRAGMA user_version = 4;','INSERT INTO nonexistent VALUES (1);')
        with patch('rideworks.store.MIGRATION_4',broken),self.assertRaises(sqlite3.Error): Store(root)
        with sqlite3.connect(root/'rideworks.sqlite3') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],3)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='performance_history'").fetchone()[0],0)
        with Store(root) as updated:
            self.assertEqual(updated.connection.execute('PRAGMA user_version').fetchone()[0],8)


if __name__=='__main__': unittest.main()
