"""Synthetic export tests; no personal fixtures or original account content."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fit_fixture import make_fit
from rideworks import Store, IntegrityError, RideWorksError
from rideworks import store as store_module
from rideworks.strava_export import ExportError

TCX = b'''   <?xml version="1.0"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2" xmlns:ae="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
<Activities><Activity Sport="Biking"><Id>2024-01-02T03:00:00Z</Id>
<Lap StartTime="2024-01-02T03:00:00Z"><TotalTimeSeconds>60.5</TotalTimeSeconds><DistanceMeters>100</DistanceMeters>
<AverageHeartRateBpm><Value>110</Value></AverageHeartRateBpm>
<Track>
<Trackpoint><Time>2024-01-02T03:00:02Z</Time><HeartRateBpm><Value>100</Value></HeartRateBpm><Extensions><ae:TPX><ae:Watts>0</ae:Watts></ae:TPX></Extensions></Trackpoint>
<Trackpoint><Extensions><ae:TPX><ae:Watts>150</ae:Watts></ae:TPX></Extensions></Trackpoint>
<Trackpoint><Time>2024-01-02T03:00:00Z</Time><HeartRateBpm><Value>120</Value></HeartRateBpm></Trackpoint>
<Trackpoint><Time>2024-01-02T03:00:00Z</Time></Trackpoint>
</Track><Extensions><ae:LX><ae:AvgWatts>250</ae:AvgWatts><ae:MaxWatts>300</ae:MaxWatts></ae:LX></Extensions>
</Lap></Activity></Activities></TrainingCenterDatabase>'''
GPX = b'''<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" xmlns:private="urn:private">
<trk><type>cycling</type><extensions><private:avgPower>999</private:avgPower></extensions><trkseg>
<trkpt><time>2024-01-02T03:00:00+01:00</time><extensions><power>0</power><gpxtpx:TrackPointExtension><gpxtpx:hr>100</gpxtpx:hr></gpxtpx:TrackPointExtension><private:power>9999</private:power></extensions></trkpt>
<trkpt><extensions><power>125</power></extensions></trkpt>
<trkpt><time>2024-01-02T03:00:00+01:00</time></trkpt>
</trkseg><trkseg><trkpt><time>2024-01-02T03:10:00</time></trkpt></trkseg></trk></gpx>'''
HEADERS = ['Activity ID', 'Activity Name', 'Activity Type', 'Activity Date', 'Filename',
           'Distance', 'Distance', 'Average Watts', 'Activity Description', 'Activity Private Note']


def csv_bytes(rows, columns=HEADERS):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(columns)
    writer.writerows(rows)
    return stream.getvalue().encode()


def row(external='1', filename='', title='Synthetic ride', date='Jan 2, 2024, 3:00:00 AM'):
    return [external, title, 'Virtual Ride', date, filename, '1.5', '1500', '500',
            'irrelevant description', 'irrelevant private note']


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'data')
        self.addCleanup(self.store.close)

    def export(self, rows, files=None, *, zip_input=True, prefix='', columns=HEADERS):
        payload = csv_bytes(rows, columns)
        files = {'activities.csv': payload, **(files or {})}
        if zip_input:
            path = self.root / 'export.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                for name, content in files.items():
                    archive.writestr(prefix + name, content)
        else:
            path = self.root / 'export'
            path.mkdir(exist_ok=True)
            for name, content in files.items():
                target = path / prefix / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        return path, payload

    def count(self, table):
        return self.store.connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

    def test_csv_only_snapshot_provenance_history_and_no_fake_streams(self):
        path, payload = self.export([row()])
        report = self.store.import_strava_export(path)
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(report['csv_only_activities'], 1)
        self.assertEqual(self.count('sources'), 0)
        self.assertEqual(self.count('records'), 0)
        snapshot = self.store.connection.execute('SELECT * FROM export_snapshots').fetchone()
        self.assertEqual((self.store.data_dir / snapshot['stored_path']).read_bytes(), payload)
        history = self.store.activity_history()
        self.assertEqual(len(history), 1)
        evidence = history[0]['sources'][0]
        self.assertEqual(evidence['source']['kind'], 'strava_export')
        self.assertEqual(evidence['source']['external_id'], '1')
        self.assertEqual(evidence['source']['snapshot_rows'][0]['row_index'], 1)
        self.assertEqual(evidence['summary']['title'], 'Synthetic ride')
        self.assertEqual(evidence['summary']['activity_type'], 'Virtual Ride')
        self.assertEqual(evidence['summary']['date_parsed'], '2024-01-02T03:00:00')
        self.assertEqual(evidence['summary']['date_timezone'], 'unknown')
        self.assertFalse(evidence['native_power_stream_exists'])
        self.assertEqual(evidence['availability']['power']['status'], 'unavailable')
        fields = evidence['summary']['fields']
        self.assertEqual([f['value'] for f in fields if f['column'] == 'Distance'], [1.5, 1500])
        self.assertEqual([f['column_index'] for f in fields if f['column'] == 'Distance'], [5, 6])
        serialized = json.dumps(evidence)
        self.assertNotIn('irrelevant', serialized)
        self.assertNotIn('Activity Description', serialized)
        self.assertEqual(self.store.get_source(evidence['source']['source_id'])['summary'], evidence['summary'])
        self.assertEqual(len(self.store.inspect(history[0]['activity']['activity_id'])['sources']), 1)

    def test_seed_exact_fit_enrichment_idempotency_restart_and_phase1_analysis(self):
        from rideworks.analysis import analyze_activity
        artifact = gzip.compress(make_fit(), mtime=0)
        seed = self.root / 'seed.fit.gz'
        seed.write_bytes(artifact)
        result = self.store.import_fit(seed)
        original = self.store.get_source(result['source_id'])
        path, _ = self.export([row(filename='activities/misleading.bin')], {'activities/misleading.bin': artifact})
        report = self.store.import_strava_export(path)
        self.assertEqual(report['activities_created'], 0)
        self.assertEqual(report['existing_activities_enriched'], 1)
        self.assertEqual(report['artifacts_reused'], 1)
        self.assertEqual(report['format_counts'], {'FIT.GZ': 1})
        self.assertEqual(self.count('activities'), 1)
        self.assertEqual(self.store.get_source(result['source_id']), original)
        self.assertEqual(len(self.store.get_activity(result['activity_id'])['sources']), 2)
        self.assertEqual(len(analyze_activity(self.store, result['activity_id'])['native_records']), 3)
        before = self.store.activity_history()
        with Store(self.store.data_dir) as restarted:
            rerun = restarted.import_strava_export(path)
            self.assertEqual(rerun['activities_created'], 0)
            self.assertEqual(rerun['csv_sources_created'], 0)
            self.assertEqual(rerun['artifacts_reused'], 1)
            self.assertEqual(restarted.activity_history(), before)
        self.assertEqual(self.count('export_snapshots'), 1)
        self.assertEqual(self.count('strava_export_sources'), 1)
        self.assertEqual(len(list(self.store.originals.glob('*.csv'))), 1)

    def test_xml_native_evidence_summaries_gzip_and_reextract(self):
        artifacts = {'activities/one.badname': gzip.compress(TCX, mtime=0), 'activities/two.fit': GPX}
        path, _ = self.export([row('1', 'activities/one.badname'), row('2', 'activities/two.fit')], artifacts)
        report = self.store.import_strava_export(path)
        self.assertEqual(report['failures'], [])
        self.assertEqual(report['format_counts'], {'GPX': 1, 'TCX.GZ': 1})
        files = {source['content_format']: source for source in self.store.connection.execute('SELECT * FROM sources')}
        tcx = self.store.get_source(files['TCX']['source_id'])
        gpx = self.store.get_source(files['GPX']['source_id'])
        self.assertEqual([r['power'] for r in tcx['records']], [0, 150, None, None])
        self.assertEqual([r['heart_rate'] for r in tcx['records']], [100, None, 120, None])
        self.assertIsNone(tcx['records'][1]['timestamp'])
        self.assertGreater(tcx['records'][0]['timestamp'], tcx['records'][2]['timestamp'])
        self.assertEqual(tcx['records'][2]['timestamp'], tcx['records'][3]['timestamp'])
        self.assertEqual(tcx['xml_context']['lap_summaries'][0]['avg_power'], 250)
        self.assertEqual(tcx['xml_context']['lap_summaries'][0]['total_time_seconds'], 60.5)
        self.assertIsNone(tcx['summary']['total_timer_time'])
        self.assertEqual([r['power'] for r in gpx['records']], [0, 125, None, None])
        self.assertEqual(gpx['records'][0]['timestamp'], '2024-01-02T02:00:00+00:00')
        self.assertEqual(gpx['records'][3]['timestamp'], '2024-01-02T03:10:00')
        self.assertIsNone(gpx['summary']['avg_power'])
        self.assertEqual(gpx['xml_context']['segment_start_record_indexes'], [0, 3])
        for source in files.values():
            before = self.store.get_source(source['source_id'])
            self.assertEqual((self.store.data_dir / source['stored_path']).read_bytes(), artifacts['activities/' + source['original_basename']])
            self.assertEqual(before['extraction']['parser_name'], 'ElementTree')
            rebuilt = self.store.reextract(source['source_id'])
            after = self.store.get_source(source['source_id'])
            self.assertNotEqual(rebuilt['extraction_id'], before['extraction']['extraction_id'])
            self.assertEqual(after['xml_context'], before['xml_context'])
            for old, new in zip(before['records'], after['records']):
                self.assertEqual({k:v for k,v in old.items() if k != 'extraction_id'},
                                 {k:v for k,v in new.items() if k != 'extraction_id'})

    def test_gpx_gzip_tcx_plain_and_extracted_root_nested_prefix(self):
        path, _ = self.export([row('1','activities/one'), row('2','activities/two')],
                              {'activities/one': gzip.compress(GPX, mtime=0), 'activities/two': TCX},
                              zip_input=False, prefix='wrapper/')
        self.assertEqual(self.store.import_strava_export(path)['format_counts'], {'GPX.GZ': 1, 'TCX': 1})

    def test_xml_fractional_seconds_preserve_exact_native_timing(self):
        from datetime import datetime
        from rideworks.xml_activity import _timestamp
        for digits in ('1','12','123','1234','12345','123456'):
            with self.subTest(digits=digits):
                parsed = _timestamp('2024-01-02T03:00:00.'+digits+'Z')
                self.assertEqual(datetime.fromisoformat(parsed).microsecond, int(digits.ljust(6,'0')))
                naive = _timestamp('2024-01-02T03:00:00.'+digits)
                self.assertIsNone(datetime.fromisoformat(naive).tzinfo)
        fixture = TCX.replace(b'2024-01-02T03:00:02Z', b'2024-01-02T03:00:00.12Z')
        fixture = fixture.replace(b'2024-01-02T03:00:00Z', b'2024-01-02T03:00:00.39Z')
        path,_ = self.export([row('1','activities/fractional')], {'activities/fractional':fixture})
        report = self.store.import_strava_export(path)
        self.assertEqual(report['failures'],[])
        source_id = self.store.connection.execute('SELECT source_id FROM sources').fetchone()[0]
        records = self.store.get_source(source_id)['records']
        self.assertEqual((datetime.fromisoformat(records[2]['timestamp'])-
                          datetime.fromisoformat(records[0]['timestamp'])).total_seconds(),0.27)
        self.assertIsNone(records[1]['timestamp'])
        self.assertEqual(records[2]['timestamp'],records[3]['timestamp'])
        with self.assertRaises(RideWorksError):
            _timestamp('2024-01-02T03:00:00.1234567Z')

    def test_changed_row_and_file_preserve_versions_and_external_identity(self):
        path, _ = self.export([row(filename='activities/one')], {'activities/one': GPX})
        self.store.import_strava_export(path)
        activity_id = self.store.activity_history()[0]['activity']['activity_id']
        path, _ = self.export([row(filename='activities/one', title='Changed synthetic title')],
                              {'activities/one': GPX.replace(b'>125<', b'>126<')})
        report = self.store.import_strava_export(path)
        self.assertEqual(report['activities_created'], 0)
        self.assertEqual(self.count('activities'), 1)
        self.assertEqual(self.count('strava_export_sources'), 2)
        self.assertEqual(self.count('sources'), 2)
        self.assertEqual(self.count('export_snapshots'), 2)
        self.assertEqual(len(self.store.get_activity(activity_id)['sources']), 4)

    def test_changed_irrelevant_text_keeps_exact_new_snapshot_and_equivalent_source(self):
        path, _ = self.export([row()])
        self.store.import_strava_export(path)
        changed = row()
        changed[-1] = 'different irrelevant private note'
        path, _ = self.export([changed])
        report = self.store.import_strava_export(path)
        self.assertEqual(report['csv_sources_created'], 0)
        self.assertEqual(self.count('export_snapshots'), 2)
        self.assertEqual(self.count('strava_export_sources'), 1)
        self.assertEqual(self.count('export_row_locations'), 2)

    def test_similar_but_different_artifact_is_not_force_merged(self):
        seed = self.root / 'seed.fit'
        seed.write_bytes(make_fit())
        first = self.store.import_fit(seed)
        path, _ = self.export([row(filename='activities/one')],
                              {'activities/one': gzip.compress(make_fit(), mtime=0)})
        self.store.import_strava_export(path)
        self.assertEqual(self.count('activities'), 2)
        self.assertEqual(len(self.store.get_activity(first['activity_id'])['sources']), 1)

    def test_conflicting_external_and_exact_artifact_identity_is_unresolved(self):
        path, _ = self.export([row('1'),row('2','activities/one')], {'activities/one': GPX})
        self.store.import_strava_export(path)
        before = self.store.activity_history()
        path, _ = self.export([row('1','activities/one')], {'activities/one': GPX})
        report = self.store.import_strava_export(path)
        self.assertEqual(len(report['unresolved_associations']), 1)
        self.assertEqual(report['activities_created'], 0)
        self.assertEqual(self.store.activity_history(), before)

    def test_independent_bad_and_missing_files_retain_csv_without_false_sources(self):
        path, _ = self.export([row('1','activities/bad'), row('2','activities/missing'),
                              row('3','activities/good')], {'activities/bad': b'not xml or FIT', 'activities/good': GPX})
        report = self.store.import_strava_export(path)
        self.assertEqual(report['status'], 'completed_with_failures')
        self.assertEqual(len(report['failures']), 2)
        self.assertEqual(report['activities_created'], 3)
        self.assertEqual(report['artifacts_imported'], 1)
        self.assertEqual(self.count('sources'), 1)
        self.assertEqual(self.count('strava_export_sources'), 3)
        self.assertEqual(list(self.store.staging.iterdir()), [])
        self.assertEqual(len(list(self.store.originals.iterdir())), 2)
        self.assertNotIn('not xml', json.dumps(report))

    def test_failed_file_persistence_rolls_back_file_and_extraction_only(self):
        self.store.connection.execute("CREATE TRIGGER fail BEFORE INSERT ON records BEGIN SELECT RAISE(ABORT, 'injected'); END")
        path, _ = self.export([row('1','activities/good')], {'activities/good': GPX})
        report = self.store.import_strava_export(path)
        self.assertEqual(len(report['failures']), 1)
        self.assertEqual(self.count('activities'), 1)
        self.assertEqual(self.count('strava_export_sources'), 1)
        self.assertEqual(self.count('sources'), 0)
        self.assertEqual(self.count('extractions'), 0)
        self.assertEqual(len(list(self.store.originals.iterdir())), 1)
        self.assertEqual(list(self.store.staging.iterdir()), [])

    def test_structural_csv_failures_before_durable_import(self):
        cases = [([row(),row()], HEADERS), ([row(filename='../escape')], HEADERS),
                 ([row('1','activities/one'),row('2','activities/one')], HEADERS),
                 ([row()[:-1]], HEADERS), ([row()], HEADERS[:-1]),
                 ([row()], ['Other ID', *HEADERS[1:]]),
                 ([row()], ['Activity ID', 'Filename', 'Filename', *HEADERS[3:]])]
        for rows, columns in cases:
            with self.subTest(columns=columns, rows=len(rows)):
                path, _ = self.export(rows, columns=columns)
                with self.assertRaises(ExportError):
                    self.store.import_strava_export(path)
                self.assertEqual(self.count('activities'), 0)
                self.assertEqual(self.count('export_snapshots'), 0)
                self.assertEqual(list(self.store.originals.iterdir()), [])

    def test_unsafe_archive_members_rejected_even_if_unreferenced(self):
        for name in ('../escape', '/absolute', 'a/../../escape', 'C:/escape', 'a\\escape', 'a/./file'):
            path, _ = self.export([row()], {name: b'unsafe'})
            with self.subTest(name=name), self.assertRaises(ExportError):
                self.store.import_strava_export(path)
            self.assertEqual(self.count('activities'), 0)
        path, _ = self.export([row()])
        with zipfile.ZipFile(path, 'a') as archive:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = (0o120777 << 16)
            archive.writestr(info, '../outside')
        with self.assertRaises(ExportError):
            self.store.import_strava_export(path)

    def test_extracted_reference_symlink_escape_rejected(self):
        path, _ = self.export([row(filename='activities/one')], zip_input=False)
        (path/'activities').mkdir()
        outside = self.root / 'outside'
        outside.write_bytes(GPX)
        (path/'activities/one').symlink_to(outside)
        with self.assertRaises(ExportError):
            self.store.import_strava_export(path)
        self.assertEqual(self.count('activities'), 0)

    def test_invalid_zip_missing_csv_and_ambiguous_csv(self):
        path = self.root / 'bad.zip'
        path.write_bytes(b'bad')
        with self.assertRaises(ExportError):
            self.store.import_strava_export(path)
        for files in ({'other': b''}, {'activities.csv': csv_bytes([row()]), 'nested/activities.csv': csv_bytes([row()])}):
            with zipfile.ZipFile(path, 'w') as archive:
                for name, content in files.items():
                    archive.writestr(name, content)
            with self.assertRaises(ExportError):
                self.store.import_strava_export(path)

    def test_dtd_and_unknown_namespace_power_not_normalized(self):
        dtd = b'<!DOCTYPE gpx [<!ENTITY x "100">]><gpx><trk><trkseg><trkpt><power>&x;</power></trkpt></trkseg></trk></gpx>'
        path, _ = self.export([row('1','activities/dtd'),row('2','activities/good')],
                              {'activities/dtd': dtd, 'activities/good': GPX.replace(b'<power>125</power>',b'<private:power>125</private:power>')})
        report = self.store.import_strava_export(path)
        self.assertEqual(len(report['failures']), 1)
        source = self.store.connection.execute('SELECT source_id FROM sources').fetchone()[0]
        self.assertEqual([r['power'] for r in self.store.get_source(source)['records']], [0,None,None,None])

    def test_snapshot_repeat_verifies_integrity_without_overwriting(self):
        path, _ = self.export([row()])
        self.store.import_strava_export(path)
        snapshot = self.store.connection.execute('SELECT stored_path FROM export_snapshots').fetchone()[0]
        (self.store.data_dir / snapshot).write_bytes(b'corrupt')
        with self.assertRaises(IntegrityError):
            self.store.import_strava_export(path)
        self.assertEqual((self.store.data_dir / snapshot).read_bytes(), b'corrupt')

    def test_cli_report_and_nonzero_partial_failure(self):
        path, _ = self.export([row('1','activities/bad')], {'activities/bad': b'invalid'})
        run = subprocess.run([sys.executable, '-m', 'rideworks', '--data-dir', str(self.store.data_dir),
                              'import-strava-export', str(path)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(json.loads(run.stdout)['csv_rows_seen'], 1)
        self.assertNotIn('Synthetic ride', run.stdout)
        self.assertNotIn(str(self.root), run.stdout)


class MigrationTests(unittest.TestCase):
    def test_schema2_migrates_additively_preserving_existing_fit_v1_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root/'seed.fit'
            seed.write_bytes(make_fit())
            with patch('rideworks.store.MIGRATION_3', ''):
                with Store(root) as old:
                    imported = old.import_fit(seed)
                    old.connection.execute("UPDATE extractions SET mapping_version='fit-v1'")
                    tables = ('activities','sources','extractions','sessions','records','laps','events')
                    before = {table:[tuple(r) for r in old.connection.execute(f'SELECT * FROM {table}')]
                              for table in tables}
                    self.assertEqual(old.connection.execute('PRAGMA user_version').fetchone()[0],2)
            with Store(root) as migrated:
                self.assertEqual(migrated.connection.execute('PRAGMA user_version').fetchone()[0],8)
                self.assertEqual({table:[tuple(r) for r in migrated.connection.execute(f'SELECT * FROM {table}')]
                                  for table in tables},before)
                self.assertEqual(migrated.get_source(imported['source_id'])['extraction']['mapping_version'],'fit-v1')
                self.assertEqual(migrated.connection.execute('SELECT COUNT(*) FROM fit_lap_timestamps').fetchone()[0],0)

    def test_failed_schema3_migration_keeps_schema2_usable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with sqlite3.connect(root/'rideworks.sqlite3') as connection:
                connection.executescript(store_module.SCHEMA)
                connection.executescript(store_module.MIGRATION_2)
                connection.execute("INSERT INTO activities VALUES ('existing','2024-01-01')")
            broken = store_module.MIGRATION_3.replace('PRAGMA user_version = 3;', 'INSERT INTO nonexistent VALUES (1);')
            with patch('rideworks.store.MIGRATION_3', broken), self.assertRaises(sqlite3.Error):
                Store(root)
            with sqlite3.connect(root/'rideworks.sqlite3') as connection:
                self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],2)
                self.assertEqual(connection.execute('SELECT activity_id FROM activities').fetchone()[0],'existing')
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='fit_lap_timestamps'").fetchone()[0],0)
            with Store(root) as recovered:
                self.assertEqual(recovered.connection.execute('PRAGMA user_version').fetchone()[0],8)

    def test_real_schema1_fixture_migrates_ids_bytes_extraction_and_review(self):
        from rideworks.analysis import analyze_activity
        from rideworks.web import review_page
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with sqlite3.connect(root/'rideworks.sqlite3') as connection:
                connection.executescript(store_module.SCHEMA)
            # Import with migration disabled to exercise the accepted schema-1
            # representation, then reopen through the actual schema-2 migration.
            seed = root/'seed.fit'
            seed.write_bytes(make_fit())
            with patch('rideworks.store.MIGRATION_2', ''):
                with Store(root) as old:
                    imported = old.import_fit(seed)
                    tables = ('activities', 'sources', 'extractions', 'sessions', 'records', 'laps', 'events')
                    before = {table: [tuple(r) for r in old.connection.execute(f'SELECT * FROM {table}')]
                              for table in tables}
                    original_bytes = (root / before['sources'][0][-2]).read_bytes()
                    self.assertEqual(old.connection.execute('PRAGMA user_version').fetchone()[0],1)
            with Store(root) as migrated:
                self.assertEqual(migrated.connection.execute('PRAGMA user_version').fetchone()[0],8)
                after = {table: [tuple(r) for r in migrated.connection.execute(f'SELECT * FROM {table}')]
                         for table in tables}
                self.assertEqual(after, before)
                evidence = migrated.get_source(imported['source_id'])
                self.assertEqual((root / evidence['source']['stored_path']).read_bytes(), original_bytes)
                self.assertEqual(migrated.import_fit(seed)['source_id'], imported['source_id'])
                self.assertEqual(len(analyze_activity(migrated,imported['activity_id'])['native_records']),3)
                self.assertIn('RideWorks',review_page(analyze_activity(migrated,imported['activity_id'])))
                migrated.reextract(imported['source_id'])

    def test_failed_migration_rolls_back_ddl_version_and_old_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with sqlite3.connect(root/'rideworks.sqlite3') as connection:
                connection.executescript(store_module.SCHEMA)
                connection.execute("INSERT INTO activities VALUES ('existing','2024-01-01')")
            broken = store_module.MIGRATION_2.replace('PRAGMA user_version = 2;', 'INSERT INTO nonexistent VALUES (1);')
            with patch('rideworks.store.MIGRATION_2', broken):
                with self.assertRaises(sqlite3.Error):
                    Store(root)
            with sqlite3.connect(root/'rideworks.sqlite3') as connection:
                self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],1)
                self.assertEqual(connection.execute('SELECT activity_id FROM activities').fetchone()[0],'existing')
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='export_snapshots'").fetchone()[0],0)
            with Store(root) as recovered:
                self.assertEqual(recovered.connection.execute('PRAGMA user_version').fetchone()[0],8)


if __name__ == '__main__':
    unittest.main()
