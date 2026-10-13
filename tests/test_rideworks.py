import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fit_fixture import make_fit
from rideworks import IntegrityError, InvalidFitError, Store, resolve_data_dir
from rideworks.fit import MAPPING_VERSION, PARSER_VERSION


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / 'activity.fit'
        self.input.write_bytes((Path(__file__).parent / "fixtures" / "single_activity.fit").read_bytes())
        self.store = Store(self.root / 'data')
        self.addCleanup(self.store.close)

    def evidence(self):
        result = self.store.import_fit(self.input)
        return result, self.store.get_source(result['source_id'])

    def assert_empty(self):
        for table in ('activities', 'sources', 'extractions', 'sessions', 'records', 'laps', 'events'):
            self.assertEqual(self.store.connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)
        self.assertEqual(list(self.store.originals.iterdir()), [])
        self.assertEqual(list(self.store.staging.iterdir()), [])

    def test_identity_integrity_and_restart(self):
        result, evidence = self.evidence()
        source = evidence['source']
        self.assertEqual(result['status'], 'imported')
        self.assertEqual(source['association_basis'], 'direct_import')
        self.assertEqual(source['kind'], 'file_fit')
        self.assertEqual(source['content_format'], 'FIT')
        self.assertEqual(source['packaging'], 'plain')
        self.assertEqual(len({result['activity_id'], result['source_id'], source['sha256']}), 3)
        self.assertEqual(source['sha256'], hashlib.sha256(self.input.read_bytes()).hexdigest())
        self.assertEqual(source['byte_size'], self.input.stat().st_size)
        self.assertEqual((self.store.data_dir / source['stored_path']).read_bytes(), self.input.read_bytes())
        with Store(self.store.data_dir) as reopened:
            repeat = reopened.import_fit(self.input)
            self.assertEqual(repeat['status'], 'already_imported')
            for key in ('activity_id', 'source_id', 'extraction_id'):
                self.assertEqual(repeat[key], result[key])
            self.assertEqual(reopened.get_activity(result['activity_id'])['sources'][0], evidence)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM activities').fetchone()[0], 1)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM sources').fetchone()[0], 1)

    def test_new_process_retrieves_compact_inspect(self):
        result, _ = self.evidence()
        output = subprocess.check_output(
            [sys.executable, '-m', 'rideworks', '--data-dir', str(self.store.data_dir),
             'inspect', result['activity_id']], text=True)
        view = json.loads(output)
        self.assertEqual(view['activity']['activity_id'], result['activity_id'])
        self.assertEqual(view['sources'][0]['extraction']['record_count'], 3)
        self.assertNotIn('records', view['sources'][0])
        self.assertNotIn('position_lat', output)

    def test_typed_summary_values_and_missingness(self):
        _, evidence = self.evidence()
        summary = evidence['summary']
        self.assertEqual(summary['max_heart_rate'], 150)
        self.assertIsNone(summary['avg_power'])
        self.assertIsNone(summary['total_distance'])
        self.assertEqual(summary['sport'], 'cycling')
        self.assertEqual(summary['total_elapsed_time'], 2.0)
        self.assertEqual(summary['total_timer_time'], 1.0)
        self.assertEqual(evidence['extraction']['parser_version'], PARSER_VERSION)
        self.assertEqual(evidence['extraction']['mapping_version'], MAPPING_VERSION)
        self.assertEqual(evidence['extraction']['artifact_sha256'], evidence['source']['sha256'])

    def test_zero_missing_order_and_duplicate_timestamps(self):
        _, evidence = self.evidence()
        records = evidence['records']
        self.assertEqual([r['record_index'] for r in records], [0, 1, 2])
        self.assertEqual([r['power'] for r in records], [0, None, 180])
        self.assertEqual([r['heart_rate'] for r in records], [100, None, 110])
        self.assertEqual(records[0]['timestamp'], records[1]['timestamp'])
        self.assertTrue(records[0]['timestamp'].endswith('+00:00'))
        self.assertLess(records[0]['source_order'], records[1]['source_order'])
        for signal in ('power', 'heart_rate'):
            self.assertEqual(evidence['availability'][signal],
                             dict(status='present_with_missing', total=3, present=2, missing=1, origin='unknown'))

    def test_absent_and_complete_signals(self):
        self.input.write_bytes(make_fit(powers=(None, None, None), heart_rates=(100, 101, 102), max_hr=None))
        _, evidence = self.evidence()
        self.assertEqual(evidence['availability']['power']['status'], 'observed_absent')
        self.assertEqual(evidence['availability']['power']['missing'], 3)
        self.assertEqual(evidence['availability']['heart_rate']['status'], 'present')
        self.assertIsNone(evidence['summary']['max_heart_rate'])

    def test_missing_and_backward_timestamps_survive(self):
        self.input.write_bytes(make_fit(timestamps=(1100000002, None, 1100000000)))
        _, evidence = self.evidence()
        records = evidence['records']
        self.assertIsNone(records[1]['timestamp'])
        self.assertGreater(records[0]['timestamp'], records[2]['timestamp'])

    def test_laps_events_and_timer_detail(self):
        _, evidence = self.evidence()
        lap = evidence['laps'][0]
        self.assertEqual(lap['total_elapsed_time'], 2.0)
        self.assertEqual(lap['total_timer_time'], 1.0)
        self.assertLess(lap['start_time'], lap['timestamp'])
        events = evidence['events']
        self.assertEqual([e['event_type'] for e in events], ['start', 'stop_all'])
        self.assertEqual([e['event'] for e in events], ['timer', 'timer'])
        self.assertEqual(events[0]['timer_trigger'], 'manual')
        self.assertLess(events[0]['source_order'], events[1]['source_order'])

    def test_gzip_preserved_and_filename_not_authoritative(self):
        artifact = gzip.compress(make_fit(), mtime=0)
        self.input = self.root / 'misleading.bin'
        self.input.write_bytes(artifact)
        _, evidence = self.evidence()
        self.assertEqual(evidence['source']['packaging'], 'gzip')
        self.assertEqual((self.store.data_dir / evidence['source']['stored_path']).read_bytes(), artifact)

    def test_different_byte_packaging_is_separate_activity(self):
        first, _ = self.evidence()
        self.input.write_bytes(gzip.compress(make_fit(), mtime=0))
        second, _ = self.evidence()
        self.assertNotEqual(first['activity_id'], second['activity_id'])
        self.assertNotEqual(first['source_id'], second['source_id'])

    def test_repeat_and_reextract_refuse_missing_original(self):
        result, evidence = self.evidence()
        (self.store.data_dir / evidence['source']['stored_path']).unlink()
        for operation in (lambda: self.store.import_fit(self.input), lambda: self.store.reextract(result['source_id'])):
            with self.assertRaisesRegex(IntegrityError, 'missing'):
                operation()
        self.assertEqual(self.store.get_source(result['source_id']), evidence)

    def test_repeat_refuses_corrupted_original_without_repair(self):
        result, evidence = self.evidence()
        original = self.store.data_dir / evidence['source']['stored_path']
        original.write_bytes(b'corrupt')
        with self.assertRaisesRegex(IntegrityError, 'mismatch'):
            self.store.import_fit(self.input)
        self.assertEqual(original.read_bytes(), b'corrupt')
        self.assertEqual(self.store.get_source(result['source_id']), evidence)

    def test_invalid_artifacts_and_crc_do_not_complete(self):
        valid = make_fit()
        for artifact in (b'not FIT', b'\x1f\x8bgarbage', gzip.compress(b'not FIT'),
                         valid[:-1], valid[:-2] + b'\x00\x00'):
            with self.subTest(artifact=artifact[:4]):
                self.input.write_bytes(artifact)
                with self.assertRaises(InvalidFitError):
                    self.store.import_fit(self.input)
                self.assert_empty()

    def test_ambiguous_sessions_and_non_activity_rejected(self):
        for artifact in (make_fit(sessions=2), make_fit(sessions=0),
                         make_fit(num_sessions=2), make_fit(file_type=5), make_fit() + make_fit()):
            self.input.write_bytes(artifact)
            with self.assertRaises(InvalidFitError):
                self.store.import_fit(self.input)
            self.assert_empty()

    def test_missing_file_id_rejected_without_completed_import(self):
        self.input.write_bytes(make_fit(file_ids=0))
        with self.assertRaisesRegex(InvalidFitError, 'file_id'):
            self.store.import_fit(self.input)
        self.assert_empty()

    def test_multiple_file_ids_rejected_without_completed_import(self):
        self.input.write_bytes(make_fit(file_ids=2))
        with self.assertRaisesRegex(InvalidFitError, 'file_id'):
            self.store.import_fit(self.input)
        self.assert_empty()

    def test_unresolved_device_relative_time_rejected(self):
        self.input.write_bytes(make_fit(timestamps=(100, 101, 102)))
        with self.assertRaisesRegex(InvalidFitError, 'absolute UTC'):
            self.store.import_fit(self.input)
        self.assert_empty()

    def test_integer_lap_timestamp_is_present_uninterpreted_and_reextracts_exactly(self):
        for raw in (0, 73):
            with self.subTest(raw=raw):
                self.input.write_bytes(make_fit(lap_timestamp=raw))
                imported, evidence = self.evidence()
                lap = evidence['laps'][0]
                self.assertIsNone(lap['timestamp'])
                self.assertIsNotNone(lap['start_time'])
                item = evidence['fit_lap_timestamps'][0]
                self.assertEqual(item, dict(extraction_id=imported['extraction_id'],
                    source_order=lap['source_order'], field_name='timestamp', raw_integer=raw,
                    status='present_uninterpreted_non_absolute'))
                self.assertIs(type(item['raw_integer']), int)
                self.assertEqual(evidence['extraction']['mapping_version'], 'fit-v2')
                self.assertEqual(self.store.inspect(imported['activity_id'])['sources'][0]['fit_lap_timestamps'], [item])
                self.assertIn('no established timebase', self.store.inspect(imported['activity_id'])['timestamp_timezone'])
                original = (self.store.data_dir/evidence['source']['stored_path']).read_bytes()
                self.assertEqual(original, self.input.read_bytes())
                self.input.unlink()
                rebuilt = self.store.reextract(imported['source_id'])
                after = self.store.get_source(imported['source_id'])
                self.assertNotEqual(rebuilt['extraction_id'], imported['extraction_id'])
                self.assertEqual([{k:v for k,v in r.items() if k != 'extraction_id'} for r in after['fit_lap_timestamps']],
                                 [{k:v for k,v in r.items() if k != 'extraction_id'} for r in evidence['fit_lap_timestamps']])
                self.assertIsNone(after['laps'][0]['timestamp'])
                self.assertEqual(self.store.connection.execute(
                    'SELECT COUNT(*) FROM fit_lap_timestamps WHERE extraction_id = ?',
                    (imported['extraction_id'],)).fetchone()[0], 0)

    def test_absolute_and_missing_lap_timestamps_have_no_uninterpreted_integer(self):
        for timestamp in (1100000002, None):
            self.input.write_bytes(make_fit(lap_timestamp=timestamp))
            _, evidence = self.evidence()
            self.assertNotIn('fit_lap_timestamps', evidence)
            self.assertEqual(evidence['laps'][0]['timestamp'] is None, timestamp is None)
            if timestamp is not None:
                self.assertTrue(evidence['laps'][0]['timestamp'].endswith('+00:00'))

    def test_lap_integer_exception_does_not_relax_other_fit_timing(self):
        cases = [dict(timestamps=(100,101,102)), dict(session_timestamp=100),
                 dict(session_start_time=100), dict(event_timestamps=(100,1100000002)),
                 dict(lap_start_time=100)]
        for fields in cases:
            with self.subTest(fields=fields):
                self.input.write_bytes(make_fit(lap_timestamp=73, **fields))
                with self.assertRaisesRegex(InvalidFitError, 'absolute UTC'):
                    self.store.import_fit(self.input)
                self.assert_empty()

    def test_failed_reextract_preserves_uninterpreted_lap_evidence(self):
        self.input.write_bytes(make_fit(lap_timestamp=73))
        imported, before = self.evidence()
        self.store.connection.execute("""CREATE TRIGGER fail_record BEFORE INSERT ON records
            BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.reextract(imported['source_id'])
        self.assertEqual(self.store.get_source(imported['source_id']), before)

    def test_uninterpreted_lap_does_not_change_absolute_native_best20(self):
        from rideworks.analysis import analyze_activity
        self.input.write_bytes(make_fit(lap_timestamp=73, powers=(100,)*1200,
            heart_rates=(110,)*1200, timestamps=tuple(range(1100000000,1100001200))))
        imported, evidence = self.evidence()
        analysis = analyze_activity(self.store, imported['activity_id'])
        self.assertEqual(analysis['best_20_minute_power']['average_watts'], 100)
        self.assertEqual(analysis['best_20_minute_power']['method'], 'best-average-power-v1')
        self.assertEqual(analysis['native_records'], evidence['records'])
        self.assertEqual(len(evidence['fit_lap_timestamps']), 1)

    def test_conflicting_unused_speed_fields_do_not_reject_typed_fit_evidence(self):
        self.input.write_bytes(make_fit(conflicting_unused_speed=True))
        _, evidence = self.evidence()
        self.assertEqual(len(evidence['records']), 3)
        self.assertEqual(evidence['summary']['sport'], 'cycling')
        self.assertNotIn('enhanced_avg_speed', evidence['summary'])

    def test_conflicting_extracted_field_still_rejects_the_fit_mapping(self):
        from rideworks.fit import _values
        frame = SimpleNamespace(name='session', fields=[
            SimpleNamespace(name='avg_power', value=100),
            SimpleNamespace(name='avg_power', value=200)])
        with self.assertRaisesRegex(InvalidFitError, 'Conflicting decoded FIT field: avg_power'):
            _values(frame)

    def test_database_failure_rolls_back_metadata_and_original(self):
        self.store.connection.execute("""CREATE TRIGGER fail_record BEFORE INSERT ON records
            BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.import_fit(self.input)
        self.assert_empty()

    def test_failed_reextract_preserves_complete_previous_revision(self):
        result, evidence = self.evidence()
        self.store.connection.execute("""CREATE TRIGGER fail_record BEFORE INSERT ON records
            BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.reextract(result['source_id'])
        self.assertEqual(self.store.get_source(result['source_id']), evidence)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM extractions').fetchone()[0], 1)

    def test_failed_decoder_reextract_preserves_previous_revision(self):
        result, evidence = self.evidence()
        with patch('rideworks.store.decode_fit', side_effect=InvalidFitError('injected decoder failure')):
            with self.assertRaises(InvalidFitError):
                self.store.reextract(result['source_id'])
        self.assertEqual(self.store.get_source(result['source_id']), evidence)

    def test_successful_reextract_uses_only_original_and_changes_revision(self):
        result, evidence = self.evidence()
        self.input.unlink()
        rebuilt = self.store.reextract(result['source_id'])
        self.assertEqual(rebuilt['activity_id'], result['activity_id'])
        self.assertEqual(rebuilt['source_id'], result['source_id'])
        self.assertNotEqual(rebuilt['extraction_id'], result['extraction_id'])
        updated = self.store.get_source(result['source_id'])
        self.assertEqual(updated['source'], evidence['source'])
        self.assertEqual([r['power'] for r in updated['records']], [0, None, 180])
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM extractions').fetchone()[0], 1)

    def test_unreferenced_original_reused_but_conflicting_bytes_rejected(self):
        digest = hashlib.sha256(self.input.read_bytes()).hexdigest()
        original = self.store.originals / (digest + '.fit')
        original.write_bytes(b'bad')
        with self.assertRaises(IntegrityError):
            self.store.import_fit(self.input)
        self.assertEqual(original.read_bytes(), b'bad')
        original.write_bytes(self.input.read_bytes())
        result, _ = self.evidence()
        self.assertEqual(result['status'], 'imported')


class DataDirectoryTests(unittest.TestCase):
    def test_precedence_and_cwd_independence(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {'RIDEWORKS_DATA_DIR': temporary}):
                self.assertEqual(resolve_data_dir(), Path(temporary))
                self.assertEqual(resolve_data_dir('/tmp/explicit-rideworks'), Path('/tmp/explicit-rideworks'))
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(resolve_data_dir(), Path(__file__).resolve().parents[1] / 'data')


if __name__ == '__main__':
    unittest.main()
