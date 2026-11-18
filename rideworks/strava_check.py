"""One-page Strava detection, cached in the server for this store."""
from concurrent.futures import Future, TimeoutError
import sqlite3
from threading import Lock
import time

from .strava import ApiClient, ApiError, AuthenticationError, OperationBusyError, PAGE_SIZE, TokenFile, activity_page, refreshed_connection
from .strava_api import SyncError, activity_type, sync_window
from .store import Store


class RecentRideCheck:
    def __init__(self, data_dir, client_factory):
        self.data_dir = data_dir
        self.client_factory = client_factory
        self.lock = Lock()
        self.generation = 0
        self.cached = None
        self.flight = None

    def invalidate(self):
        with self.lock:
            self.generation += 1
            self.cached = None
            self.flight = None

    def key(self):
        token = TokenFile(self.data_dir).path.stat()
        with Store(self.data_dir) as store:
            row = store.connection.execute(
                'SELECT athlete_id, successful_at FROM strava_sync_state WHERE singleton=1'
            ).fetchone()
        return token.st_ino, token.st_mtime_ns, tuple(row) if row else None

    def check(self, credentials, *, busy):
        if not credentials:
            return 'disconnected'
        try:
            key = self.key()
        except FileNotFoundError:
            return 'disconnected'
        except (OSError, sqlite3.Error):
            return 'unavailable'
        with self.lock:
            if busy():
                return 'busy'
            generation = self.generation
            if self.cached and self.cached[0] == key and self.cached[1] > time.monotonic():
                return self.cached[2]
            flight = self.flight
            if flight is None:
                self.flight = flight = Future()
                leader = True
            else:
                leader = False
        if not leader:
            try:
                result_key, status = flight.result(timeout=12)
                current_key = self.key()
            except (TimeoutError, OSError, sqlite3.Error):
                return 'unavailable'
            with self.lock:
                return status if generation == self.generation and current_key == result_key else 'superseded'

        result_key, status = key, 'unavailable'
        try:
            client = ApiClient(credentials, timeout=5) if self.client_factory is ApiClient else self.client_factory(credentials)
            tokens = TokenFile(self.data_dir)
            now = int(time.time())
            with tokens.lock():
                if busy() or self.key() != key:
                    status = 'superseded'
                    return 'superseded'
                current = refreshed_connection(tokens, client, now=now)
                result_key = self.key()
            with Store(self.data_dir) as store:
                window = sync_window(store, current['athlete_id'], now)
            rows = activity_page(client, current, window, 1)
            ids = {str(r['id']) for r in rows if activity_type(r) in ('Ride', 'Virtual Ride')}
            with Store(self.data_dir) as store:
                for identity in tuple(ids):
                    found = store.connection.execute(
                        'SELECT 1 FROM strava_api_activities WHERE external_id=? '
                        'UNION ALL SELECT 1 FROM strava_export_sources WHERE external_id=? LIMIT 1',
                        (identity, identity),
                    ).fetchone()
                    if found:
                        ids.remove(identity)
            status = 'new' if ids else 'incomplete' if len(rows) == PAGE_SIZE else 'clear'
        except OperationBusyError:
            status = 'busy'
        except AuthenticationError:
            status = 'authorization'
        except ApiError as error:
            status = 'rate_limited' if error.status == 429 else 'unavailable'
        except (SyncError, OSError, sqlite3.Error):
            status = 'unavailable'
        finally:
            try:
                current_key = self.key()
            except (OSError, sqlite3.Error):
                current_key = None
            with self.lock:
                if generation != self.generation or (current_key != result_key and status != 'authorization'):
                    status = 'superseded'
                if status not in ('busy', 'superseded'):
                    self.cached = (result_key, time.monotonic() + 300, status)
                if self.flight is flight:
                    self.flight = None
                flight.set_result((result_key, status))
        return status
