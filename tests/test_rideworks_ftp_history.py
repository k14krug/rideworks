"""FTP lifecycle, transactional failure/replay and synthetic timeline invariants."""
from pathlib import Path
import sqlite3
import tempfile
from unittest import TestCase
from unittest.mock import patch

from rideworks.store import Store
from rideworks.errors import IntegrityError
from rideworks.ftp_history import snapshot, add_entry, bootstrap, validated_sources
from rideworks.training_state import ftp_on
from ftp_fixture import seed_ftp

SOURCE=Path('data/athlete/strava_ftp_history.csv')
MIRROR=Path('rideworks/data/strava_ftp_history.csv')

class HistoryTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.target=Path(self.temp.name)/'store'

    def test_new_empty_and_existing_empty_upgrade_survive_restart(self):
        for _ in range(2):
            with Store(self.target) as store:self.assertEqual(snapshot(store)['rows'],[])
        with Store(self.target) as store:
            store.connection.executescript('DROP TABLE ftp_history; DROP TABLE ftp_history_state; PRAGMA user_version=10;')
        for _ in range(2):
            with Store(self.target) as store:
                with self.assertRaisesRegex(IntegrityError,'migration needed'):snapshot(store)

    def test_intermediate_insert_dates_watts_stale_collision_and_preservation(self):
        with Store(self.target) as store:
            seed_ftp(store,[('2020-01-01',200),('2020-12-31',250)])
            original=[tuple(r) for r in store.connection.execute('SELECT * FROM ftp_history')]
            for d,w in [('2020-03-01',180),('2020-06-01',270),('2020-09-01',270)]:
                current=snapshot(store);after=add_entry(store,d,w,expected_revision=current['revision'])
                self.assertEqual(ftp_on(after['rows'],d)['value'],w)
            for row in original:self.assertIn(row,[tuple(r) for r in store.connection.execute('SELECT * FROM ftp_history')])
            before=snapshot(store)
            for d,w,revision in [('2020-06-01',300,before['revision']),('2020-05-01',220,0),
                                  ('2020-05-01',True,before['revision']),('2020-05-01',0,before['revision']),
                                  ('2020-5-1',200,before['revision']),('2019-01-01',200,before['revision']),
                                  ('2021-01-01',200,before['revision'])]:
                with self.assertRaises(ValueError):add_entry(store,d,w,expected_revision=revision)
                self.assertEqual(snapshot(store),before)
            self.assertEqual(ftp_on(before['rows'],'2020-05-31')['value'],180)
            self.assertEqual(ftp_on(before['rows'],'2020-06-01')['value'],270)
            self.assertEqual(ftp_on(before['rows'],'2020-12-31')['value'],250)
            self.assertEqual(ftp_on(before['rows'],'2020-09-01',False)['status'],'date_uncertain')
        with Store(self.target) as store:self.assertEqual(snapshot(store),before)

    def test_approved_bootstrap_parity_replay_after_insertion(self):
        pairs=validated_sources(SOURCE,MIRROR)
        result=bootstrap(self.target,SOURCE,MIRROR)
        self.assertTrue(result['imported']);self.assertEqual(len(result['rows']),66)
        self.assertEqual([(r['effective_from_date'],r['ftp_watts']) for r in result['rows']],pairs)
        with Store(self.target) as store:
            changed=add_entry(store,'2020-01-03',211,expected_revision=1)
        replay=bootstrap(self.target,SOURCE,MIRROR)
        self.assertFalse(replay.pop('imported'));self.assertEqual(replay,changed)

    def test_invalid_inputs_do_not_create_target_or_change_schema(self):
        wrong=Path(self.temp.name)/'bad.csv';wrong.write_text('not an approved input')
        with self.assertRaises(IntegrityError):bootstrap(self.target,wrong,MIRROR)
        self.assertFalse(self.target.exists())
        with self.assertRaises(FileNotFoundError):bootstrap(self.target,SOURCE,wrong.parent/'missing')
        self.assertFalse(self.target.exists())

    def test_failure_after_rows_and_marker_rolls_back_and_retries(self):
        with Store(self.target):pass
        with patch('rideworks.ftp_history.snapshot',side_effect=RuntimeError('injected after marker')):
            with self.assertRaises(RuntimeError):bootstrap(self.target,SOURCE,MIRROR)
        with Store(self.target) as store:
            self.assertEqual(snapshot(store)['rows'],[])
            self.assertEqual(snapshot(store)['revision'],0)
            self.assertIsNone(store.connection.execute('SELECT bootstrap_checksum FROM ftp_history_state').fetchone()[0])
        self.assertTrue(bootstrap(self.target,SOURCE,MIRROR)['imported'])

    def test_nonempty_unmarked_target_refuses_merge(self):
        with Store(self.target) as store:seed_ftp(store)
        with self.assertRaisesRegex(IntegrityError,'refusing to merge'):bootstrap(self.target,SOURCE,MIRROR)

    def test_schema_migration_failure_is_atomic_and_initial_identity_survives(self):
        from rideworks import store as module
        with patch.object(module,'MIGRATION_11',module.MIGRATION_11.replace('PRAGMA user_version = 11;','INSERT INTO missing VALUES(1);')):
            with self.assertRaises(sqlite3.Error):Store(self.target)
        with sqlite3.connect(self.target/'rideworks.sqlite3') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],10)
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ftp_history'").fetchone())
        with Store(self.target) as store:self.assertEqual(snapshot(store)['rows'],[])

    def test_insert_revision_and_row_rollback_together(self):
        with Store(self.target) as store:
            seed_ftp(store);before=snapshot(store)
            store.connection.execute("CREATE TRIGGER fail_revision BEFORE UPDATE ON ftp_history_state BEGIN SELECT RAISE(ABORT,'injected'); END")
            with self.assertRaises(sqlite3.IntegrityError):add_entry(store,'2020-01-01',210,expected_revision=before['revision'])
            self.assertEqual(snapshot(store),before)

    def test_history_revision_and_rows_share_snapshot_during_concurrent_commit(self):
        with Store(self.target) as first:
            seed_ftp(first)
            first.connection.execute('PRAGMA journal_mode=WAL')
            with Store(self.target) as second:
                with first._transaction():
                    before=snapshot(first)
                    changed=add_entry(second,'2020-01-01',210,expected_revision=before['revision'])
                    self.assertEqual(snapshot(first),before)
                self.assertEqual(snapshot(first),changed)

    def test_lock_rejection_leaves_rows_revision_unchanged(self):
        with Store(self.target) as first:
            seed_ftp(first);before=snapshot(first)
            with Store(self.target) as second,first._transaction(write=True):
                second.connection.execute('PRAGMA busy_timeout=0')
                with self.assertRaises(sqlite3.OperationalError):
                    add_entry(second,'2020-01-01',210,expected_revision=before['revision'])
            self.assertEqual(snapshot(first),before)
