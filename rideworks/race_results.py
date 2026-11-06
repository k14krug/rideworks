"""Screenshot-derived race evidence, kept separate from activity measurements."""

import base64
from datetime import date, datetime, timezone
import hashlib
import io
import json
import os
import re
import socket
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4
import warnings
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PIL import Image, UnidentifiedImageError

from .config import _dotenv, repository_root
from .history import presentation
from .store import artifact_integrity, _sync_directory

FIELDS = ('date', 'start_time', 'event', 'race_group', 'finish', 'avg_watts', 'race_score', 'race_score_change')
INTEGER_FIELDS = frozenset(('finish', 'avg_watts', 'race_score', 'race_score_change'))
PROMPT_VERSION = 'zrp-races-v1'
SCHEMA_VERSION = 'zrp-races-v1'
SOURCE_TYPE = 'zwift_racing_profile_screenshot'
PROMPT = (
    'Read the Zwift Racing Profile screenshot. Extract every fully visible race-result table row, '
    'in screen order, into the supplied JSON schema. Extract date and clock time, full event title '
    '(join wrapped lines, exclude the route subtitle), race-group badge, finishing position, top '
    'integer watts from WATTS/W/kg, score and signed score change. Ignore route, distance, time/gap, '
    'watts/kg, and 20m/5m/1m/15s columns. Up arrow is positive, down arrow negative, explicit zero '
    'is zero, dash is null. Missing or unreadable values are null; do not guess, duplicate, merge '
    'or manufacture rows. Do not read the promo/series cards above the table as races.'
)
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['races'],
    'properties': {'races': {
        'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': list(FIELDS),
            'properties': {key: {'type': ['integer' if key in INTEGER_FIELDS else 'string', 'null']}
                           for key in FIELDS},
        },
    }},
}
FORMATS = {'PNG': ('image/png', '.png'), 'JPEG': ('image/jpeg', '.jpg'), 'WEBP': ('image/webp', '.webp')}
DEFAULT_LIMIT = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_ROWS = 100


class RaceError(ValueError):
    """A recoverable race import error safe to display in the browser."""


def configuration(environ=None):
    env = os.environ if environ is None else environ
    keys = frozenset(('OPENAI_API_KEY', 'RIDEWORKS_RACE_MODEL', 'RIDEWORKS_RACE_MAX_BYTES'))
    selected = {key: env[key] for key in keys if key in env}
    _dotenv(repository_root(), selected, keys)
    key = selected.get('OPENAI_API_KEY', '').strip()
    model = selected.get('RIDEWORKS_RACE_MODEL', 'gpt-4o-mini').strip()
    limit = selected.get('RIDEWORKS_RACE_MAX_BYTES', str(DEFAULT_LIMIT)).strip()
    if not model or len(model) > 100 or not re.fullmatch(r'[A-Za-z0-9._:-]+', model):
        raise RaceError('Invalid race extraction model configuration.')
    if not limit.isascii() or not limit.isdecimal() or not 1 <= int(limit) <= 12 * 1024 * 1024:
        raise RaceError('RIDEWORKS_RACE_MAX_BYTES must be between 1 and 12582912.')
    return key, model, int(limit)


def validate_image(payload, limit):
    if not payload or len(payload) > limit:
        raise RaceError('Choose an image within the configured upload size limit.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as image:
                fmt = image.format
                width, height = image.size
                if fmt not in FORMATS or not width or not height or width * height > MAX_PIXELS:
                    raise RaceError('Choose a PNG, JPEG or WebP image under the image dimension limit.')
                image.verify()
            with Image.open(io.BytesIO(payload)) as image:
                image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise RaceError('The image is malformed or too large to decode.') from exc
    return FORMATS[fmt]


def validate_timezone(value):
    if not value:
        return None
    try:
        return ZoneInfo(value).key
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise RaceError('Enter a valid IANA screenshot display timezone, or leave it unknown.') from exc


def validate_shape(data):
    if not isinstance(data, dict) or set(data) != {'races'} or not isinstance(data['races'], list):
        raise RaceError('The extraction response does not match the race schema.')
    if len(data['races']) > MAX_ROWS:
        raise RaceError('The extraction returned too many rows; use a smaller screenshot.')
    for row in data['races']:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise RaceError('The extraction response contains an invalid race row.')
        for key, value in row.items():
            if value is not None and (type(value) is not int if key in INTEGER_FIELDS else not isinstance(value, str)):
                raise RaceError('The extraction response contains an invalid field type.')
    return data['races']


def row_errors(row):
    errors = []
    try:
        if row['date'] is not None and date.fromisoformat(row['date']).isoformat() != row['date']:
            raise ValueError
    except ValueError:
        errors.append('Date must be YYYY-MM-DD.')
    if row['start_time'] is not None and not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', row['start_time']):
        errors.append('Start time must be HH:MM.')
    if row['event'] is not None and (not row['event'].strip() or len(row['event']) > 250):
        errors.append('Event must be 1–250 characters, or unknown.')
    if row['race_group'] is not None and not re.fullmatch(r'\d{1,5}\s*[-–]\s*\d{1,5}', row['race_group']):
        errors.append('Race group must be a visible range, such as 0-210, or unknown.')
    for key in ('finish', 'avg_watts', 'race_score'):
        if row[key] is not None and (type(row[key]) is not int or row[key] < 0 or row[key] > 1_000_000):
            errors.append(f'{key.replace("_", " ").title()} must be a nonnegative whole number.')
    if row['race_score_change'] is not None and (
        type(row['race_score_change']) is not int or abs(row['race_score_change']) > 1_000_000
    ):
        errors.append('Score change must be a signed whole number within the supported range.')
    return errors


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def extract(payload, image_type, key, model, *, opener=None):
    if not key:
        raise RaceError('Configure OPENAI_API_KEY locally before extracting a screenshot.')
    request_data = {
        'model': model, 'store': False,
        'input': [{'role': 'user', 'content': [
            {'type': 'input_text', 'text': PROMPT},
            {'type': 'input_image', 'image_url': f'data:{image_type};base64,{base64.b64encode(payload).decode("ascii")}',
             'detail': 'high'},
        ]}],
        'text': {'format': {'type': 'json_schema', 'name': 'zrp_races', 'strict': True, 'schema': SCHEMA}},
    }
    request = Request('https://api.openai.com/v1/responses', data=json.dumps(request_data).encode(),
                      headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, method='POST')
    try:
        with (opener or build_opener(_NoRedirect())).open(request, timeout=60) as response:
            response_body = response.read(2_000_001)
        if len(response_body) > 2_000_000:
            raise RaceError('The extraction response was too large.')
        data = json.loads(response_body)
        if not isinstance(data, dict) or data.get('status') != 'completed':
            raise RaceError('Extraction was incomplete. Try again or use a smaller image.')
        texts = []
        for item in data.get('output', []):
            if item.get('type') == 'message':
                for content in item.get('content', []):
                    if content.get('type') == 'refusal':
                        raise RaceError('The extraction service declined this image.')
                    if content.get('type') == 'output_text':
                        texts.append(content.get('text'))
        if len(texts) != 1 or not isinstance(texts[0], str):
            raise RaceError('The extraction service returned no usable race data.')
        rows = validate_shape(json.loads(texts[0]))
        usage = data.get('usage')
        if not isinstance(usage, dict):
            usage = None
        else:
            usage = {k: v for k, v in usage.items() if k in ('input_tokens', 'output_tokens', 'total_tokens', 'cost')
                     and type(v) in (int, float) and v >= 0}
        return rows, usage
    except HTTPError as exc:
        raise RaceError(f'OpenAI extraction failed (HTTP {exc.code}). Check configuration and try again.') from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise RaceError('OpenAI extraction could not be reached or timed out. Try again.') from exc
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        if isinstance(exc, RaceError):
            raise
        raise RaceError('The extraction service returned invalid JSON or an invalid response.') from exc


def archive_image(store, payload, suffix):
    digest = hashlib.sha256(payload).hexdigest()
    directory = store.originals / 'race-screenshots'
    directory.mkdir(mode=0o700, exist_ok=True)
    _sync_directory(store.originals)
    path = directory / (digest + suffix)
    with tempfile.NamedTemporaryFile(dir=store.staging, delete=False) as out:
        staged = out.name
        try:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        except OSError:
            os.unlink(staged)
            raise
    try:
        try:
            os.link(staged, path)
            _sync_directory(directory)
        except FileExistsError:
            pass
        if path.is_symlink() or artifact_integrity(path) != (digest, len(payload)):
            raise RaceError('Stored screenshot integrity check failed.')
    finally:
        os.unlink(staged)
    return digest, str(path.relative_to(store.data_dir))


def stage_import(store, payload, timezone_name, *, extractor=None):
    key, model, limit = configuration()
    image_type, suffix = validate_image(payload, limit)
    timezone_name = validate_timezone(timezone_name)
    rows, usage = (extractor or extract)(payload, image_type, key, model)
    validate_shape({'races': rows})
    digest, path = archive_image(store, payload, suffix)
    identity = str(uuid4())
    with store._transaction(write=True):
        store.connection.execute('INSERT INTO race_imports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (identity, SOURCE_TYPE, digest, len(payload), image_type, path, datetime.now(timezone.utc).isoformat(),
             timezone_name, model, PROMPT_VERSION, SCHEMA_VERSION, json.dumps(rows), json.dumps(usage) if usage else None))
    return identity


def load_import(store, identity):
    row = store.connection.execute('SELECT * FROM race_imports WHERE import_id=?', (identity,)).fetchone()
    return dict(row) if row else None


def screenshot(store, identity):
    source = load_import(store, identity)
    if source is None:
        raise RaceError('Screenshot import was not found.')
    path = store.data_dir / source['image_path']
    if path.is_symlink() or artifact_integrity(path) != (source['image_sha256'], source['image_size']):
        raise RaceError('Stored screenshot is missing or failed integrity verification.')
    return source['image_type'], path.read_bytes()


def matching_activities(store):
    from .dashboard import average_power
    result = []
    for snapshot in store.activity_history():
        activity = presentation(snapshot)
        value, source = average_power(activity)
        activity['match_watts'] = value
        activity['match_watts_source'] = source['context'] if source else None
        result.append(activity)
    return result


def candidates(store, row, timezone_name, *, activities=None):
    if not row.get('date'):
        return []
    zone = ZoneInfo(timezone_name) if timezone_name else None
    found = []
    activities = activities if activities is not None else matching_activities(store)
    for activity in activities:
        stamp = activity['start_time']
        if not stamp:
            continue
        parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        if activity['absolute_time']:
            if zone is None:
                continue
            parsed = parsed.astimezone(zone)
        if parsed.date().isoformat() != row['date']:
            continue
        kind = ' '.join(filter(None, (activity['activity_type'], activity['subtype']))).casefold()
        virtual = 'virtual' in kind or 'zwift' in activity['title'].casefold()
        found.append({'id': activity['activity_id'], 'title': activity['title'],
                      'time': parsed.strftime('%H:%M'), 'virtual': virtual,
                      'type': activity['activity_type'], 'absolute': activity['absolute_time'],
                      'watts': activity['match_watts'], 'watts_source': activity['match_watts_source']})
    return found


def suggested_match(row, timezone_name, choices):
    if not timezone_name or not row.get('start_time') or not row.get('event') or len(choices) != 1:
        return None
    try:
        local = datetime.fromisoformat(f"{row['date']}T{row['start_time']}")
        zone = ZoneInfo(timezone_name)
        if local.replace(tzinfo=zone, fold=0).utcoffset() != local.replace(tzinfo=zone, fold=1).utcoffset():
            return None
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        return None
    choice = choices[0]
    words = lambda text: {word for word in re.findall(r'[a-z0-9]+', text.casefold())
                          if len(word) > 3 and word not in {'zwift', 'race', 'ride'}}
    if choice['absolute'] and choice['virtual'] and choice['time'] == row['start_time'] and words(row['event']) & words(choice['title']):
        return choice['id']
    return None


def revision(values_json, timezone_name=None):
    return hashlib.sha256(json.dumps([values_json, timezone_name]).encode('utf-8')).hexdigest() if values_json is not None else 'new'


_DEFAULT_ZONE = object()


def commit_rows(store, import_id, rows, *, timezone_name=_DEFAULT_ZONE):
    source = load_import(store, import_id)
    if source is None:
        raise RaceError('Screenshot import was not found.')
    timezone_name = source['display_timezone'] if timezone_name is _DEFAULT_ZONE else validate_timezone(timezone_name)
    original_rows = json.loads(source['rows_json'])
    if len(rows) != len(original_rows):
        raise RaceError('The review no longer matches the extracted rows. Reload the review.')
    counts = {'added': 0, 'unchanged': 0, 'replaced': 0, 'skipped': 0}
    selected_ids = set()
    with store._transaction(write=True):
        for item in rows:
            if item['action'] == 'skip':
                counts['skipped'] += 1
                continue
            if item['action'] != 'confirm':
                raise RaceError('Choose confirm or skip for every row.')
            row, activity_id = item['values'], item['activity_id']
            errors = row_errors(row)
            if errors:
                raise RaceError('Correct invalid rows before confirming: ' + ' '.join(errors))
            validate_shape({'races': [row]})
            if not activity_id or not store.connection.execute('SELECT 1 FROM activities WHERE activity_id=?', (activity_id,)).fetchone():
                raise RaceError('Every confirmed row must be linked to an existing activity.')
            if activity_id in selected_ids:
                raise RaceError('Two confirmed rows cannot use the same activity.')
            selected_ids.add(activity_id)
            encoded = json.dumps(row, sort_keys=True, ensure_ascii=False)
            current = store.connection.execute('SELECT values_json, display_timezone FROM race_results WHERE activity_id=?', (activity_id,)).fetchone()
            current_revision = revision(current['values_json'], current['display_timezone']) if current else 'new'
            if item['shown_activity'] != activity_id or item['shown_revision'] != current_revision:
                raise RaceError('Activity selection or saved result changed. Review changes before confirming.')
            if current and json.loads(current['values_json']) == row and current['display_timezone'] == timezone_name:
                counts['unchanged'] += 1
                continue
            if current and not item['replace']:
                raise RaceError('A changed result needs explicit replacement approval.')
            now = datetime.now(timezone.utc).isoformat()
            store.connection.execute('INSERT INTO race_result_history VALUES (?,?,?,?,?,?)',
                                     (str(uuid4()), activity_id, import_id, encoded, timezone_name, now))
            store.connection.execute('''INSERT INTO race_results VALUES (?,?,?,?,?)
                ON CONFLICT(activity_id) DO UPDATE SET import_id=excluded.import_id,
                values_json=excluded.values_json, display_timezone=excluded.display_timezone,
                accepted_at=excluded.accepted_at''',
                (activity_id, import_id, encoded, timezone_name, now))
            counts['replaced' if current else 'added'] += 1
    return counts
