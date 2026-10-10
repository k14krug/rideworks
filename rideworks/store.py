"""SQLite source-centered evidence and immutable original artifacts."""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import gzip
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zlib
from uuid import uuid4

from .errors import IntegrityError, RideWorksError
from .fit import MAPPING_VERSION, PARSER_VERSION, decode_fit, packaging_for
from . import xml_activity

SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS activities (
    activity_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    kind TEXT NOT NULL,
    association_basis TEXT NOT NULL,
    original_basename TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    packaging TEXT NOT NULL CHECK(packaging IN ('plain', 'gzip')),
    content_format TEXT NOT NULL,
    stored_path TEXT NOT NULL UNIQUE,
    imported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sources_activity ON sources(activity_id);
CREATE TABLE IF NOT EXISTS extractions (
    extraction_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL UNIQUE REFERENCES sources(source_id),
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    extracted_at TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    power_present INTEGER NOT NULL,
    heart_rate_present INTEGER NOT NULL,
    power_origin TEXT NOT NULL,
    heart_rate_origin TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    extraction_id TEXT PRIMARY KEY REFERENCES extractions(extraction_id) ON DELETE CASCADE,
    start_time TEXT,
    timestamp TEXT,
    sport TEXT,
    sub_sport TEXT,
    total_elapsed_time REAL,
    total_timer_time REAL,
    total_distance REAL,
    total_ascent INTEGER,
    avg_power INTEGER,
    max_power INTEGER,
    avg_heart_rate INTEGER,
    max_heart_rate INTEGER,
    avg_cadence INTEGER
);
CREATE TABLE IF NOT EXISTS records (
    extraction_id TEXT NOT NULL REFERENCES extractions(extraction_id) ON DELETE CASCADE,
    record_index INTEGER NOT NULL,
    source_order INTEGER NOT NULL,
    timestamp TEXT,
    power INTEGER,
    heart_rate INTEGER,
    PRIMARY KEY(extraction_id, record_index)
);
CREATE TABLE IF NOT EXISTS laps (
    extraction_id TEXT NOT NULL REFERENCES extractions(extraction_id) ON DELETE CASCADE,
    source_order INTEGER NOT NULL,
    start_time TEXT,
    timestamp TEXT,
    total_elapsed_time REAL,
    total_timer_time REAL,
    PRIMARY KEY(extraction_id, source_order)
);
CREATE TABLE IF NOT EXISTS events (
    extraction_id TEXT NOT NULL REFERENCES extractions(extraction_id) ON DELETE CASCADE,
    source_order INTEGER NOT NULL,
    timestamp TEXT,
    event TEXT,
    event_type TEXT,
    timer_trigger TEXT,
    PRIMARY KEY(extraction_id, source_order)
);
PRAGMA user_version = 1;
COMMIT;
"""

# Additive, atomic migration: accepted Phase 1 tables and IDs stay intact.
MIGRATION_2 = """
BEGIN IMMEDIATE;
CREATE TABLE export_snapshots (
    sha256 TEXT PRIMARY KEY,
    byte_size INTEGER NOT NULL,
    stored_path TEXT NOT NULL UNIQUE,
    imported_at TEXT NOT NULL
);
CREATE TABLE strava_export_sources (
    source_id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    external_id TEXT NOT NULL,
    row_sha256 TEXT NOT NULL,
    association_basis TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    title TEXT,
    activity_type TEXT,
    sport_type TEXT,
    date_text TEXT,
    filename TEXT,
    evidence_json TEXT NOT NULL,
    UNIQUE(external_id, row_sha256)
);
CREATE INDEX strava_sources_activity ON strava_export_sources(activity_id);
CREATE INDEX strava_sources_external ON strava_export_sources(external_id);
CREATE TABLE export_row_locations (
    snapshot_sha256 TEXT NOT NULL REFERENCES export_snapshots(sha256),
    row_index INTEGER NOT NULL,
    source_id TEXT NOT NULL REFERENCES strava_export_sources(source_id),
    PRIMARY KEY(snapshot_sha256, row_index)
);
CREATE TABLE xml_context (
    extraction_id TEXT PRIMARY KEY REFERENCES extractions(extraction_id) ON DELETE CASCADE,
    context_json TEXT NOT NULL
);
PRAGMA user_version = 2;
COMMIT;
"""

MIGRATION_3 = """
BEGIN IMMEDIATE;
CREATE TABLE fit_lap_timestamps (
    extraction_id TEXT NOT NULL,
    source_order INTEGER NOT NULL,
    field_name TEXT NOT NULL CHECK(field_name = 'timestamp'),
    raw_integer INTEGER NOT NULL CHECK(typeof(raw_integer) = 'integer'),
    status TEXT NOT NULL CHECK(status = 'present_uninterpreted_non_absolute'),
    PRIMARY KEY(extraction_id, source_order),
    FOREIGN KEY(extraction_id, source_order)
        REFERENCES laps(extraction_id, source_order) ON DELETE CASCADE
);
PRAGMA user_version = 3;
COMMIT;
"""

SUMMARY_UNITS = {
    "total_elapsed_time": "s", "total_timer_time": "s", "total_distance": "m",
    "total_ascent": "m", "avg_power": "W", "max_power": "W",
    "avg_heart_rate": "bpm", "max_heart_rate": "bpm", "avg_cadence": "rpm",
}

MIGRATION_4 = """
BEGIN IMMEDIATE;
CREATE TABLE performance_history (
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    duration_seconds INTEGER NOT NULL,
    policy TEXT NOT NULL,
    method TEXT NOT NULL,
    source_id TEXT REFERENCES sources(source_id),
    extraction_id TEXT REFERENCES extractions(extraction_id) ON DELETE CASCADE,
    input_signature TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY(activity_id, duration_seconds, policy)
);
PRAGMA user_version = 4;
COMMIT;
"""

MIGRATION_5 = """
BEGIN IMMEDIATE;
CREATE TABLE strava_api_sources (
    source_id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    external_id TEXT NOT NULL,
    observation_sha256 TEXT NOT NULL,
    association_basis TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    UNIQUE(external_id, observation_sha256)
);
CREATE INDEX api_sources_activity ON strava_api_sources(activity_id);
CREATE TABLE strava_api_activities (
    external_id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    current_source_id TEXT NOT NULL UNIQUE REFERENCES strava_api_sources(source_id)
);
CREATE TABLE strava_sync_state (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    athlete_id TEXT NOT NULL,
    successful_at INTEGER NOT NULL
);
PRAGMA user_version = 5;
COMMIT;
"""


MIGRATION_6 = """
BEGIN IMMEDIATE;
CREATE TABLE strava_stream_sources (
    source_id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    external_id TEXT NOT NULL REFERENCES strava_api_activities(external_id),
    summary_source_id TEXT NOT NULL REFERENCES strava_api_sources(source_id),
    observation_sha256 TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    requested_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    UNIQUE(external_id, summary_source_id, observation_sha256)
);
CREATE INDEX stream_sources_activity ON strava_stream_sources(activity_id);
CREATE TABLE strava_stream_current (
    external_id TEXT PRIMARY KEY REFERENCES strava_api_activities(external_id),
    source_id TEXT NOT NULL UNIQUE REFERENCES strava_stream_sources(source_id)
);
CREATE TABLE strava_stream_attempts (
    external_id TEXT PRIMARY KEY REFERENCES strava_api_activities(external_id),
    attempted_at TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK(outcome IN ('fetched','unavailable','failed')),
    reason TEXT NOT NULL
);
PRAGMA user_version = 6;
COMMIT;
"""


MIGRATION_7 = """
BEGIN IMMEDIATE;
CREATE TABLE annual_mileage_goals (
    year INTEGER PRIMARY KEY CHECK(year BETWEEN 1 AND 9999),
    target_miles TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
PRAGMA user_version = 7;
COMMIT;
"""


MIGRATION_8 = """
BEGIN IMMEDIATE;
CREATE TABLE training_stress_cache (
    activity_id TEXT PRIMARY KEY REFERENCES activities(activity_id),
    input_signature TEXT NOT NULL,
    result_json TEXT NOT NULL
);
PRAGMA user_version = 8;
COMMIT;
"""


def resolve_data_dir(data_dir=None) -> Path:
    """Resolve once; default does not depend on the working directory."""
    selected = data_dir if data_dir is not None else os.environ.get("RIDEWORKS_DATA_DIR", "~/.rideworks")
    return Path(selected).expanduser().resolve()


def _now():
    return datetime.now(timezone.utc).isoformat()


def artifact_integrity(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Store:
    def __init__(self, data_dir=None):
        self.data_dir = resolve_data_dir(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.originals = self.data_dir / "originals"
        self.originals.mkdir(exist_ok=True, mode=0o700)
        self.staging = self.data_dir / ".staging"
        self.staging.mkdir(exist_ok=True, mode=0o700)
        self.connection = sqlite3.connect(self.data_dir / "rideworks.sqlite3", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA synchronous = FULL")
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2, 3, 4, 5, 6, 7, 8):
            self.close()
            raise RideWorksError(f"Unsupported RideWorks schema version: {version}")
        try:
            if version == 0:
                self.connection.executescript(SCHEMA)
                version = 1
            if version == 1:
                self.connection.executescript(MIGRATION_2)
                version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 2:
                self.connection.executescript(MIGRATION_3)
                version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 3:
                self.connection.executescript(MIGRATION_4)
                version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version == 4:
                self.connection.executescript(MIGRATION_5)
                version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version == 5:
                self.connection.executescript(MIGRATION_6)
                version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version == 6:
                self.connection.executescript(MIGRATION_7)
                version = 7
            if version == 7:
                self.connection.executescript(MIGRATION_8)
            _sync_directory(self.data_dir)
        except BaseException:
            self.connection.rollback()
            self.close()
            raise

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _transaction(self, *, write=False):
        # A performance rebuild holds one write snapshot while using existing
        # read boundaries. Only the outer transaction commits or rolls back.
        if self.connection.in_transaction:
            yield
            return
        # Serialize import/re-extraction and file placement across store instances.
        self.connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _verify(self, source):
        path = self.data_dir / source["stored_path"]
        try:
            actual = artifact_integrity(path)
        except OSError as exc:
            raise IntegrityError("Established original artifact is missing or unreadable") from exc
        if actual != (source["sha256"], source["byte_size"]):
            raise IntegrityError("Established original artifact hash/size mismatch")
        return path

    def _persist_extraction(self, source_id, digest, parsed, *, xml=None):
        extraction_id = str(uuid4())
        count = len(parsed.records)
        power = sum(r.power is not None for r in parsed.records)
        hr = sum(r.heart_rate is not None for r in parsed.records)
        self.connection.execute(
            "INSERT INTO extractions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (extraction_id, source_id, "ElementTree" if xml else "fitdecode",
             xml_activity.PARSER_VERSION if xml else PARSER_VERSION,
             xml_activity.MAPPING_VERSION if xml else MAPPING_VERSION,
             _now(), digest, count, power, hr, "unknown", "unknown"),
        )
        self._insert_rows("sessions", extraction_id, [parsed.session])
        self._insert_rows("records", extraction_id, parsed.records)
        self._insert_rows("laps", extraction_id, parsed.laps)
        self._insert_rows("fit_lap_timestamps", extraction_id, parsed.uninterpreted_lap_timestamps)
        self._insert_rows("events", extraction_id, parsed.events)
        if xml is not None:
            self.connection.execute("INSERT INTO xml_context VALUES (?, ?)",
                                    (extraction_id, json.dumps(xml.context, sort_keys=True)))
        return extraction_id

    def _insert_rows(self, table, extraction_id, rows):
        if not rows:
            return
        # table/column names come exclusively from the internal typed classes.
        columns = list(asdict(rows[0]))
        names = ", ".join(["extraction_id", *columns])
        placeholders = ", ".join("?" for _ in range(len(columns) + 1))
        self.connection.executemany(
            f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
            [(extraction_id, *asdict(row).values()) for row in rows],
        )

    def import_fit(self, input_path) -> dict:
        """Accepted direct FIT import behavior; never interpret XML as FIT."""
        return self.import_file(input_path, fit_only=True)

    def import_file(self, input_path, *, activity_id=None, association_basis="direct_import",
                    artifact_bytes=None, fit_only=False) -> dict:
        input_path = Path(input_path)
        staged = None
        created_original = None
        try:
            with self._transaction(write=True):
                with tempfile.NamedTemporaryFile(dir=self.staging, delete=False) as target:
                    staged = Path(target.name)
                    digest, size = hashlib.sha256(), 0
                    with (input_path.open("rb") if artifact_bytes is None else io.BytesIO(artifact_bytes)) as supplied:
                        for block in iter(lambda: supplied.read(1024 * 1024), b""):
                            target.write(block)
                            digest.update(block)
                            size += len(block)
                    target.flush()
                    os.fsync(target.fileno())
                digest = digest.hexdigest()
                existing = self.connection.execute(
                    "SELECT * FROM sources WHERE sha256 = ?", (digest,),
                ).fetchone()
                if existing is not None:
                    if activity_id is not None and existing["activity_id"] != activity_id:
                        raise RideWorksError("Exact artifact belongs to a different established Activity; unresolved")
                    self._verify(existing)
                    extraction = self.connection.execute(
                        "SELECT extraction_id FROM extractions WHERE source_id = ?",
                        (existing["source_id"],),
                    ).fetchone()
                    if extraction is None:
                        raise IntegrityError("Established Source has no current extraction")
                    return self._result("already_imported", existing["activity_id"],
                                        existing["source_id"], extraction[0])
                packaging = packaging_for(staged)
                xml = None
                if fit_only or self._is_fit(staged, packaging):
                    parsed = decode_fit(staged, packaging)
                    content_format = "FIT"
                else:
                    xml = xml_activity.decode_xml(staged, packaging)
                    parsed, content_format = xml.parsed, xml.content_format
                extension = content_format.lower() + (".gz" if packaging == "gzip" else "")
                relative = f"originals/{digest}.{extension}"
                destination = self.data_dir / relative
                try:
                    # Exclusive creation; never replace an established original.
                    os.link(staged, destination)
                    created_original = destination
                    _sync_directory(self.originals)
                except FileExistsError:
                    # A crash may have left an unreferenced original. Reuse only
                    # identical verified bytes; never silently overwrite it.
                    if artifact_integrity(destination) != (digest, size):
                        raise IntegrityError("Existing original path has conflicting bytes")
                if artifact_integrity(destination) != (digest, size):
                    raise IntegrityError("Stored original failed integrity verification")
                source_id, created = str(uuid4()), _now()
                if activity_id is None:
                    activity_id = str(uuid4())
                    self.connection.execute("INSERT INTO activities VALUES (?, ?)", (activity_id, created))
                elif self.connection.execute("SELECT 1 FROM activities WHERE activity_id = ?", (activity_id,)).fetchone() is None:
                    raise RideWorksError("Target Activity not found")
                self.connection.execute(
                    "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (source_id, activity_id, "file_" + content_format.lower(), association_basis, input_path.name,
                     size, digest, packaging, content_format, relative, created),
                )
                extraction_id = self._persist_extraction(source_id, digest, parsed, xml=xml)
                result = self._result("imported", activity_id, source_id, extraction_id)
            return result
        except BaseException:
            if created_original is not None:
                # Rollback has occurred. Reacquire the write lock before checking
                # references so another process cannot establish a Source here.
                with self._transaction(write=True):
                    referenced = self.connection.execute(
                        "SELECT 1 FROM sources WHERE stored_path = ?", (relative,),
                    ).fetchone()
                    if referenced is None:
                        created_original.unlink(missing_ok=True)
                        _sync_directory(self.originals)
            raise
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    @staticmethod
    def _is_fit(path, packaging):
        opener = gzip.open if packaging == "gzip" else open
        try:
            with opener(path, "rb") as stream:
                return stream.read(12)[8:12] == b".FIT"
        except (OSError, EOFError, zlib.error) as exc:
            raise RideWorksError("Invalid compressed activity artifact") from exc

    def reextract(self, source_id) -> dict:
        with self._transaction(write=True):
            source = self.connection.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,)).fetchone()
            if source is None:
                raise RideWorksError("Source not found")
            path = self._verify(source)
            xml = None
            if source["content_format"] == "FIT":
                parsed = decode_fit(path, source["packaging"])
            else:
                xml = xml_activity.decode_xml(path, source["packaging"])
                parsed = xml.parsed
            self.connection.execute("DELETE FROM extractions WHERE source_id = ?", (source_id,))
            extraction_id = self._persist_extraction(source_id, source["sha256"], parsed, xml=xml)
            return self._result("reextracted", source["activity_id"], source_id, extraction_id)

    def _result(self, status, activity_id, source_id, extraction_id):
        return dict(status=status, activity_id=activity_id, source_id=source_id,
                    extraction_id=extraction_id, data_dir=str(self.data_dir))

    def _source_evidence(self, source):
        extraction = self.connection.execute(
            "SELECT * FROM extractions WHERE source_id = ?", (source["source_id"],),
        ).fetchone()
        if extraction is None:
            raise IntegrityError("Source has no current extraction")
        key = extraction["extraction_id"]
        summary = dict(self.connection.execute("SELECT * FROM sessions WHERE extraction_id = ?", (key,)).fetchone())
        availability = {}
        for signal in ("power", "heart_rate"):
            present, total = extraction[f"{signal}_present"], extraction["record_count"]
            availability[signal] = dict(
                status="observed_absent" if present == 0 else "present" if present == total else "present_with_missing",
                total=total, present=present, missing=total - present,
                origin=extraction[f"{signal}_origin"],
            )
        evidence = dict(source=dict(source), extraction=dict(extraction), summary=summary,
                        availability=availability)
        for table, order in (("records", "record_index"), ("laps", "source_order"), ("events", "source_order")):
            evidence[table] = [dict(row) for row in self.connection.execute(
                f"SELECT * FROM {table} WHERE extraction_id = ? ORDER BY {order}", (key,),
            )]
        context = self.connection.execute("SELECT context_json FROM xml_context WHERE extraction_id = ?", (key,)).fetchone()
        if context is not None:
            evidence["xml_context"] = json.loads(context[0])
        uninterpreted = [dict(row) for row in self.connection.execute(
            "SELECT * FROM fit_lap_timestamps WHERE extraction_id = ? ORDER BY source_order", (key,))]
        if uninterpreted:
            evidence["fit_lap_timestamps"] = uninterpreted
        return evidence

    def get_activity(self, activity_id) -> dict:
        """Consistent snapshot including every Source's current typed evidence."""
        with self._transaction():
            activity = self.connection.execute("SELECT * FROM activities WHERE activity_id = ?", (activity_id,)).fetchone()
            if activity is None:
                raise RideWorksError("Activity not found")
            sources = self.connection.execute(
                "SELECT * FROM sources WHERE activity_id = ? ORDER BY imported_at, source_id", (activity_id,),
            ).fetchall()
            csv_sources = self.connection.execute(
                "SELECT * FROM strava_export_sources WHERE activity_id = ? ORDER BY imported_at, source_id",
                (activity_id,),
            ).fetchall()
            return dict(activity=dict(activity), sources=[self._source_evidence(s) for s in sources]
                        + [self._csv_evidence(s) for s in csv_sources] + self._api_sources(activity_id))

    def list_activities(self) -> list[dict]:
        """List only activities with one current Phase 1 FIT Source/session.

        No source ranking or new evidence-selection policy. Ambiguous activities
        are omitted rather than choosing among multiple FIT Sources.
        """
        with self._transaction():
            return [dict(row) for row in self.connection.execute("""
                SELECT a.activity_id, s.start_time, s.sport, s.sub_sport,
                       s.total_distance, s.total_elapsed_time
                FROM activities a
                JOIN sources f ON f.activity_id = a.activity_id
                JOIN extractions e ON e.source_id = f.source_id
                JOIN sessions s ON s.extraction_id = e.extraction_id
                WHERE f.kind = 'file_fit' AND f.content_format = 'FIT'
                  AND (SELECT count(*) FROM sources c
                       WHERE c.activity_id = a.activity_id
                       AND c.kind = 'file_fit' AND c.content_format = 'FIT') = 1
                ORDER BY s.start_time DESC, a.activity_id
            """)]

    def get_source(self, source_id) -> dict:
        with self._transaction():
            source = self.connection.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,)).fetchone()
            if source is not None:
                return self._source_evidence(source)
            source = self.connection.execute("SELECT * FROM strava_export_sources WHERE source_id = ?", (source_id,)).fetchone()
            if source is None:
                source = self.connection.execute('SELECT s.*, a.current_source_id=s.source_id AS is_current FROM strava_api_sources s JOIN strava_api_activities a ON a.external_id=s.external_id WHERE s.source_id=?', (source_id,)).fetchone()
                if source is not None:
                    return self._api_evidence(source)
                raise RideWorksError("Source not found")
            return self._csv_evidence(source)

    def _api_evidence(self, row):
        from .strava_api import activity_type
        values = json.loads(row['evidence_json'])
        source = {key: row[key] for key in ('source_id', 'activity_id', 'external_id',
                  'observation_sha256', 'association_basis', 'imported_at', 'is_current')}
        source.update(kind='strava_api', content_format='API JSON', packaging='observation')
        return dict(source=source, extraction=dict(mapping_version=row['mapping_version']),
                    summary=dict(title=values.get('name'), activity_type=activity_type(values),
                                 sport_type=values.get('sport_type'), date_parsed=values['start_date'],
                                 total_elapsed_time=values.get('elapsed_time'), total_distance=values.get('distance'),
                                 values=values),
                    availability={signal: dict(status='unavailable', origin='Strava API summary',
                                      reason='API summaries are not native streams') for signal in ('power','heart_rate')},
                    records=None, laps=[], events=[], native_power_stream_exists=False)

    def _api_sources(self, activity_id=None):
        where = ' WHERE s.activity_id=?' if activity_id is not None else ''
        return [self._api_evidence(row) for row in self.connection.execute('''
            SELECT s.*, a.current_source_id=s.source_id AS is_current
            FROM strava_api_sources s JOIN strava_api_activities a ON a.external_id=s.external_id
        '''+where+' ORDER BY s.imported_at, s.source_id', (activity_id,) if activity_id else ())]

    def strava_stream_evidence(self, activity_id):
        # Separate typed evidence: never enter the file/native Performance signature.
        from .strava_streams import evidence
        return evidence(self, activity_id)

    def inspect(self, activity_id) -> dict:
        snapshot = self.get_activity(activity_id)
        compact_sources = []
        for evidence in snapshot["sources"]:
            compact = {k: evidence[k] for k in ("source", "extraction", "summary", "availability")}
            compact["lap_count"] = len(evidence["laps"])
            compact["event_count"] = len(evidence["events"])
            if "xml_context" in evidence:
                compact["xml_context"] = evidence["xml_context"]
            if "fit_lap_timestamps" in evidence:
                compact["fit_lap_timestamps"] = evidence["fit_lap_timestamps"]
            compact_sources.append(compact)
        timezone_label = ("UTC" if all(e["source"]["content_format"] == "FIT" for e in snapshot["sources"])
                          else "explicit offsets retained/normalized; absent offsets unknown")
        if any("fit_lap_timestamps" in evidence for evidence in snapshot["sources"]):
            timezone_label += "; uninterpreted FIT lap integers have no established timebase"
        return dict(activity=snapshot["activity"], sources=compact_sources,
                    summary_units=SUMMARY_UNITS, timestamp_timezone=timezone_label,
                    strava_stream_sources=[{k: observation[k] for k in ('source_id', 'summary_source_id', 'retrieved_at', 'mapping_version', 'requested', 'metadata', 'is_current')}
                                           for observation in self.strava_stream_evidence(activity_id)])

    def preserve_export_snapshot(self, payload):
        """One exact CSV snapshot per byte identity, not one copy per row."""
        digest = hashlib.sha256(payload).hexdigest()
        relative = f'originals/{digest}.csv'
        created = False
        staged = None
        try:
            with self._transaction(write=True):
                existing = self.connection.execute('SELECT * FROM export_snapshots WHERE sha256 = ?', (digest,)).fetchone()
                if existing is not None:
                    self._verify(existing)
                    return digest
                with tempfile.NamedTemporaryFile(dir=self.staging, delete=False) as stream:
                    staged = Path(stream.name)
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                destination = self.data_dir / relative
                try:
                    os.link(staged, destination)
                    created = True
                    _sync_directory(self.originals)
                except FileExistsError:
                    pass
                if artifact_integrity(destination) != (digest, len(payload)):
                    raise IntegrityError('CSV snapshot original hash/size mismatch')
                self.connection.execute('INSERT INTO export_snapshots VALUES (?, ?, ?, ?)',
                                        (digest, len(payload), relative, _now()))
            return digest
        except BaseException:
            if created:
                with self._transaction(write=True):
                    if self.connection.execute('SELECT 1 FROM export_snapshots WHERE sha256 = ?', (digest,)).fetchone() is None:
                        (self.data_dir / relative).unlink(missing_ok=True)
                        _sync_directory(self.originals)
            raise
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def attach_export_row(self, snapshot_sha256, row_index, row, artifact_sha256=None):
        """Resolve only established external/file identities, then retain row evidence.

        File decode/persistence is separate so bad files do not erase valid CSV
        observations. Conflicting established identities produce no association.
        """
        from .strava_export import AssociationError
        with self._transaction(write=True):
            external = self.connection.execute(
                'SELECT DISTINCT activity_id FROM strava_export_sources WHERE external_id = ?',
                (row['external_id'],),
            ).fetchall()
            file_source = self.connection.execute('SELECT * FROM sources WHERE sha256 = ?',
                                                  (artifact_sha256,)).fetchone() if artifact_sha256 else None
            candidates = {r[0] for r in external}
            if file_source is not None:
                self._verify(file_source)
                candidates.add(file_source['activity_id'])
            if len(candidates) > 1:
                raise AssociationError('Conflicting established external/artifact identities')
            existing = self.connection.execute(
                'SELECT * FROM strava_export_sources WHERE external_id = ? AND row_sha256 = ?',
                (row['external_id'], row['row_sha256']),
            ).fetchone()
            created = not candidates
            activity_id = next(iter(candidates)) if candidates else str(uuid4())
            # Never infer a merge from time, distance, sport or name similarity.
            if created:
                self.connection.execute('INSERT INTO activities VALUES (?, ?)', (activity_id, _now()))
            if existing is None:
                source_id = str(uuid4())
                basis = ('established_strava_external_id' if external else
                         'exact_artifact_and_explicit_csv_reference' if file_source is not None else
                         'strava_export_row_identity')
                self.connection.execute('INSERT INTO strava_export_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                        (source_id, activity_id, row['external_id'], row['row_sha256'], basis, _now(),
                                         row['title'], row['activity_type'], row['sport_type'], row['date_text'],
                                         row['filename'], json.dumps(row['evidence'], sort_keys=True, ensure_ascii=True)))
            else:
                source_id = existing['source_id']
            self.connection.execute('INSERT OR IGNORE INTO export_row_locations VALUES (?, ?, ?)',
                                    (snapshot_sha256, row_index, source_id))
            return dict(activity_id=activity_id, source_id=source_id, activity_created=created,
                        csv_source_created=existing is None)

    def _csv_evidence(self, row):
        source = {key: row[key] for key in ('source_id', 'activity_id', 'external_id', 'row_sha256',
                                          'association_basis', 'imported_at')}
        source.update(kind='strava_export', content_format='CSV', packaging='plain')
        locations = [dict(location) for location in self.connection.execute('''
            SELECT l.snapshot_sha256, l.row_index, s.byte_size, s.stored_path
            FROM export_row_locations l JOIN export_snapshots s ON s.sha256 = l.snapshot_sha256
            WHERE l.source_id = ? ORDER BY s.imported_at, l.row_index
        ''', (row['source_id'],))]
        source['snapshot_rows'] = locations
        evidence = json.loads(row['evidence_json'])
        return dict(source=source,
                    extraction=dict(mapping_version='strava-export-v1', row_sha256=row['row_sha256']),
                    summary=dict(title=row['title'], activity_type=row['activity_type'], sport_type=row['sport_type'],
                                 date_text=row['date_text'], filename=row['filename'], **evidence),
                    availability={signal: dict(status='unavailable', origin='unknown',
                                                reason='CSV metadata is not a native stream')
                                  for signal in ('power', 'heart_rate')},
                    records=None, laps=[], events=[])

    def activity_history(self, activity_id=None):
        """Source-aware metadata for all Activities, without loading native records.

        This boundary does not rank sources, choose titles or compute historical
        metrics. Summary values retain their source-specific semantics/units.
        """
        with self._transaction():
            where = ' WHERE activity_id = ?' if activity_id is not None else ''
            args = (activity_id,) if activity_id is not None else ()
            activities = {row['activity_id']: dict(activity=dict(row), sources=[])
                          for row in self.connection.execute('SELECT * FROM activities' + where + ' ORDER BY created_at, activity_id', args)}
            for row in self.connection.execute('SELECT * FROM strava_export_sources' + where + ' ORDER BY imported_at, source_id', args):
                evidence = self._csv_evidence(row)
                activities[row['activity_id']]['sources'].append({k: evidence[k] for k in
                    ('source', 'extraction', 'summary', 'availability')} | {'native_power_stream_exists': False})
            for evidence in self._api_sources(activity_id):
                activities[evidence['source']['activity_id']]['sources'].append(evidence)
            file_where = ' WHERE f.activity_id = ?' if activity_id is not None else ''
            for row in self.connection.execute('''
                SELECT f.*, e.extraction_id, e.parser_name, e.parser_version, e.mapping_version,
                       e.record_count, e.power_present, e.heart_rate_present
                FROM sources f JOIN extractions e ON e.source_id = f.source_id
            ''' + file_where + ' ORDER BY f.imported_at, f.source_id', args):
                source = {key: row[key] for key in ('source_id', 'activity_id', 'kind', 'association_basis',
                          'original_basename', 'byte_size', 'sha256', 'packaging', 'content_format', 'stored_path', 'imported_at')}
                extraction = {key: row[key] for key in ('extraction_id', 'parser_name', 'parser_version',
                              'mapping_version', 'record_count', 'power_present', 'heart_rate_present')}
                summary = dict(self.connection.execute('SELECT * FROM sessions WHERE extraction_id = ?',
                                                        (row['extraction_id'],)).fetchone())
                context = self.connection.execute('SELECT context_json FROM xml_context WHERE extraction_id = ?',
                                                   (row['extraction_id'],)).fetchone()
                evidence = dict(source=source, extraction=extraction, summary=summary,
                                native_power_stream_exists=row['power_present'] > 0,
                                availability={signal: dict(present=row[f'{signal}_present'], total=row['record_count'],
                                              status='observed_absent' if row[f'{signal}_present'] == 0 else
                                              'present' if row[f'{signal}_present'] == row['record_count'] else 'present_with_missing',
                                              origin='unknown') for signal in ('power', 'heart_rate')})
                if context is not None:
                    evidence['xml_context'] = json.loads(context[0])
                activities[row['activity_id']]['sources'].append(evidence)
            return list(activities.values())

    def import_strava_export(self, path):
        from .strava_export import import_export
        return import_export(self, path)
