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
PROMPT_VERSION = 'zrp-races-v3'
SECTION_PROMPT_VERSION = 'zrp-races-section-v4'
CURRENT_PROMPT_VERSIONS = frozenset((PROMPT_VERSION, SECTION_PROMPT_VERSION))
SCHEMA_VERSION = 'zrp-races-v2'
SOURCE_TYPE = 'zwift_racing_profile_screenshot'
PROMPT_START = """Read the attached Zwift Racing Profile screenshot and extract race results into the supplied JSON schema.

**Row identification**

- Extract each visible race-result row in top-to-bottom order.
- Only extract rows from the RACE RESULTS table.
- The number in the RACE RESULTS heading represents the total profile results, not necessarily the number visible in the screenshot.
"""
WHOLE_IMAGE_ROW_POLICY = """- Include a row when enough of its information is readable to identify the race, even if the row border is partially cropped.
"""
PROMPT_END = """- Never invent additional rows.
**Field extraction**

For each row, extract exactly these eight fields:

- `date`: Convert the displayed M/D/YYYY date to YYYY-MM-DD.
- `start_time`: Convert the displayed 12-hour AM/PM time to 24-hour HH. Do not infer a timezone.
- `event`: Extract the blue event title, joining wrapped lines with spaces. Do not include the smaller route name below it. If the title is truncated with an ellipsis (...), preserve the visible text and ellipsis exactly. Never invent missing title text.
- `race_group`: Extract the gray race-group badge, preserving the displayed range as a string (for example, "0-210", "160-270", or "0-275").
- `finish`: Extract the integer finishing position from the FINISH column.
- `avg_watts`: Extract the upper integer value from the WATTS/W/kg column. Ignore the lower W/kg value.
- `race_score`: Extract the main integer from the SCORE/Change column, above the change indicator.
- `race_score_change`: Extract the numeric change below the score. Green upward arrow means positive, red downward arrow means negative. An explicit zero is 0 regardless of arrow direction.
**Accuracy rules**

- Use null for missing, dashed (--) or unreadable values.
- Do not confuse average watts with 20M, 5M, 1M or 15S power.
- Ignore route, race duration, gap, distance, elevation and W/kg.
- Keep values associated with their original row, even when event titles wrap across multiple lines.
- Never guess, infer missing information, duplicate rows or combine results from different rows.
- Return only the JSON object required by the supplied schema, without explanations, Markdown or extra fields."""
PROMPT = PROMPT_START + WHOLE_IMAGE_ROW_POLICY + PROMPT_END

SECTION_ELIGIBILITY = '''This image is one horizontal section of a larger Zwift Racing Profile RACE RESULTS screenshot. Neighboring sections overlap. Extract rows visible in THIS section only; do not infer or reconstruct missing pixels.

SECTION BOUNDARIES
- Top edge: {TOP_EDGE_TYPE}.
- Bottom edge: {BOTTOM_EDGE_TYPE}.
  TOP_EDGE_TYPE / BOTTOM_EDGE_TYPE must each be "original screenshot edge" or "internal crop boundary", determined from the section's original-image pixel coordinates (not by the model).

WHICH ROWS TO EXTRACT
- At an INTERNAL CROP BOUNDARY, do not extract a race row that is cut off by that edge. A row must be visibly complete within this section, including its row beginning, the FINISH cell, the DATE/Time cell area, and the beginning of its blue event title. The row's bottom/content must also be visible. Such cut rows should appear in another overlapping section.
- A wrapped blue race title belongs to ONE physical table row. Join its visible lines into one event title. A continuation such as "Loop" at the top of a section is NOT a new race when the beginning of the title/row is outside this section. Do not make a row out of the smaller black route subtitle.
- If an edge is an ORIGINAL SCREENSHOT EDGE (not an internal crop boundary), apply the original screenshot's policy for a partially visible but identifiable row; do not discard it solely because the uploaded image itself was cropped.
- A complete interior row may have individual unreadable or dashed values. Extract the row and set only the unreadable fields to null. Do not treat null DATE or null watts alone as proof that a row is a crop fragment.
- Do not turn headers, separators, continuation lines, other columns or duplicate renderings into additional races. Return rows in top-to-bottom order.
- If no complete eligible race rows are visible in this section, return {"races": []} in the required schema. Do not guess missing rows.'''


def section_prompt(top, bottom, image_height):
    top_edge = 'original screenshot edge' if top == 0 else 'internal crop boundary'
    bottom_edge = 'original screenshot edge' if bottom == image_height else 'internal crop boundary'
    eligibility = SECTION_ELIGIBILITY.replace('{TOP_EDGE_TYPE}', top_edge).replace('{BOTTOM_EDGE_TYPE}', bottom_edge)
    return PROMPT_START + PROMPT_END + '\n\n' + eligibility


SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['races'],
    'properties': {'races': {
        'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': list(FIELDS),
            'properties': {key: {
                'type': ['integer' if key in INTEGER_FIELDS else 'string', 'null'],
                **({'description': '24-hour local clock time as HH:MM; do not infer a timezone.'}
                   if key == 'start_time' else {}),
            } for key in FIELDS},
        },
    }},
}
FORMATS = {'PNG': ('image/png', '.png'), 'JPEG': ('image/jpeg', '.jpg'), 'WEBP': ('image/webp', '.webp')}
DEFAULT_LIMIT = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_ROWS = 100


class RaceError(ValueError):
    """A recoverable race import error safe to display in the browser."""

    def __init__(self, message, *, usage=None, request_id=None, output=None):
        super().__init__(message)
        self.usage = usage
        self.request_id = request_id
        self.output = output


def configuration(environ=None):
    env = os.environ if environ is None else environ
    keys = frozenset(('OPENAI_API_KEY', 'RIDEWORKS_RACE_MODEL', 'RIDEWORKS_RACE_MAX_BYTES'))
    selected = {key: env[key] for key in keys if key in env}
    _dotenv(repository_root(), selected, keys)
    key = selected.get('OPENAI_API_KEY', '').strip()
    model = selected.get('RIDEWORKS_RACE_MODEL', 'gpt-6-luna').strip()
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


def normalize_row(row):
    normalized = dict(row)
    date_value = row.get('date')
    if isinstance(date_value, str):
        match = re.fullmatch(r'([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})', date_value.strip())
        if match:
            month, day, year = map(int, match.groups())
            try:
                normalized['date'] = date(year, month, day).isoformat()
            except ValueError:
                pass
    time_value = row.get('start_time')
    if isinstance(time_value, str):
        match = re.fullmatch(r'([0-9]{1,2}):([0-9]{2})\s*([AaPp][Mm])', time_value.strip())
        if match:
            hour, minute, period = match.groups()
            hour, minute = int(hour), int(minute)
            if 1 <= hour <= 12 and minute < 60:
                hour = hour % 12 + (12 if period.upper() == 'PM' else 0)
                normalized['start_time'] = f'{hour:02d}:{minute:02d}'
    return normalized


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


def api_usage(data):
    if not isinstance(data, dict) or not isinstance(data.get('usage'), dict):
        return None
    usage = data['usage']
    cleaned = {k: v for k, v in usage.items() if k in ('input_tokens', 'output_tokens', 'total_tokens')
               and type(v) is int and v >= 0}
    for name, allowed in (('input_tokens_details', {'cached_tokens', 'cache_write_tokens'}),
                          ('output_tokens_details', {'reasoning_tokens'})):
        details = usage.get(name)
        if isinstance(details, dict):
            cleaned[name] = {k: v for k, v in details.items() if k in allowed and type(v) is int and v >= 0}
    cleaned['service_tier'] = data.get('service_tier')
    return cleaned


def extract(payload, image_type, key, model, prompt=PROMPT, *, opener=None):
    if not key:
        raise RaceError('Configure OPENAI_API_KEY locally before extracting a screenshot.')
    request_data = {
        'model': model, 'store': False, 'service_tier': 'default',
        'input': [{'role': 'user', 'content': [
            {'type': 'input_text', 'text': prompt},
            {'type': 'input_image', 'image_url': f'data:{image_type};base64,{base64.b64encode(payload).decode("ascii")}',
             'detail': 'high'},
        ]}],
        'text': {'format': {'type': 'json_schema', 'name': 'zrp_races', 'strict': True, 'schema': SCHEMA}},
    }
    request = Request('https://api.openai.com/v1/responses', data=json.dumps(request_data).encode(),
                      headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, method='POST')
    usage = None
    request_id = None
    output = None
    try:
        with (opener or build_opener(_NoRedirect())).open(request, timeout=60) as response:
            candidate_id = getattr(response, 'headers', {}).get('x-request-id')
            if isinstance(candidate_id, str) and re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', candidate_id):
                request_id = candidate_id
            response_body = response.read(2_000_001)
        if len(response_body) > 2_000_000:
            raise RaceError('The extraction response was too large.')
        data = json.loads(response_body)
        usage = api_usage(data)
        if isinstance(data, dict) and 'output' in data:
            output = json.dumps(data['output'], ensure_ascii=False)
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
        output = texts[0]
        rows = validate_shape(json.loads(output))
        if request_id:
            usage = usage if usage is not None else {}
            usage['request_id'] = request_id
        return rows, usage
    except HTTPError as exc:
        candidate_id = exc.headers.get('x-request-id') if exc.headers else None
        if isinstance(candidate_id, str) and re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', candidate_id):
            request_id = candidate_id
        try:
            error_body = exc.read(2_000_001)
            if error_body and len(error_body) <= 2_000_000:
                usage = api_usage(json.loads(error_body))
        except (OSError, ValueError):
            usage = None
        raise RaceError(f'OpenAI extraction failed (HTTP {exc.code}). Check configuration and try again.',
                        usage=usage, request_id=request_id) from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise RaceError('OpenAI extraction could not be reached or timed out. Try again.') from exc
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        if isinstance(exc, RaceError):
            raise RaceError(str(exc), usage=usage, request_id=request_id, output=output) from exc
        raise RaceError('The extraction service returned invalid JSON or an invalid response.',
                        usage=usage, request_id=request_id, output=output) from exc


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


def stage_import(store, payload, timezone_name, *, extractor=None, mode='sectioned'):
    from .race_sections import crop_image, image_dimensions, plan_sections

    key, model, limit = configuration()
    image_type, suffix = validate_image(payload, limit)
    timezone_name = validate_timezone(timezone_name)
    if not key and extractor is None:
        raise RaceError('Configure OPENAI_API_KEY locally before extracting a screenshot.')
    if mode not in ('sectioned', 'full'):
        raise RaceError('Choose a valid screenshot extraction mode.')
    width, height = image_dimensions(payload)
    bounds = plan_sections(width, height) if mode == 'sectioned' else [(0, height)]
    prompt_version = SECTION_PROMPT_VERSION if mode == 'sectioned' else PROMPT_VERSION
    digest, path = archive_image(store, payload, suffix)
    identity = str(uuid4())
    with store._transaction(write=True):
        store.connection.execute('INSERT INTO race_imports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (identity, SOURCE_TYPE, digest, len(payload), image_type, path, datetime.now(timezone.utc).isoformat(),
             timezone_name, model, prompt_version, SCHEMA_VERSION, '[]', None))
        for index, (top, bottom) in enumerate(bounds):
            store.connection.execute('''INSERT INTO race_import_sections
                (import_id,section_index,top,bottom,width,image_height,status,model,prompt_version,schema_version)
                VALUES (?,?,?,?,?,?,'planned',?,?,?)''',
                (identity, index, top, bottom, width, height, model, prompt_version, SCHEMA_VERSION))
    all_rows = []
    for index, (top, bottom) in enumerate(bounds):
        with store._transaction(write=True):
            store.connection.execute('UPDATE race_import_sections SET status=? WHERE import_id=? AND section_index=?',
                                     ('running', identity, index))
        try:
            crop = crop_image(payload, top, bottom)
            prompt = section_prompt(top, bottom, height) if mode == 'sectioned' else PROMPT
            rows, usage = (extractor or extract)(crop, 'image/png', key, model, prompt)
            try:
                validate_shape({'races': rows})
            except RaceError as exc:
                raise RaceError(str(exc), usage=usage, output=json.dumps({'races': rows})) from exc
            if len(all_rows) + len(rows) > MAX_ROWS:
                raise RaceError('The extraction returned too many observations. Try a shorter screenshot.',
                                usage=usage, output=json.dumps(rows, ensure_ascii=False))
        except RaceError as exc:
            with store._transaction(write=True):
                store.connection.execute('''UPDATE race_import_sections
                    SET status='failed',output_json=?,usage_json=?,request_id=?,error=?
                    WHERE import_id=? AND section_index=?''',
                    (exc.output, json.dumps(exc.usage) if exc.usage is not None else None,
                     exc.request_id, str(exc), identity, index))
            break
        all_rows.extend(rows)
        request_id = usage.get('request_id') if isinstance(usage, dict) else None
        with store._transaction(write=True):
            store.connection.execute('''UPDATE race_import_sections SET status='completed',
                output_json=?,usage_json=?,request_id=? WHERE import_id=? AND section_index=?''',
                (json.dumps(rows, ensure_ascii=False), json.dumps(usage) if usage is not None else None,
                 request_id, identity, index))
            store.connection.execute('UPDATE race_imports SET rows_json=? WHERE import_id=?',
                                     (json.dumps(all_rows, ensure_ascii=False), identity))
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


def activity_candidate(activity, zone):
    stamp = activity['start_time']
    if not stamp:
        return None
    parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if activity['absolute_time']:
        if zone is None:
            return None
        parsed = parsed.astimezone(zone)
    kind = ' '.join(filter(None, (activity['activity_type'], activity['subtype']))).casefold()
    virtual = 'virtual' in kind or 'zwift' in activity['title'].casefold()
    return {'id': activity['activity_id'], 'title': activity['title'],
            'date': parsed.date().isoformat(), 'time': parsed.strftime('%H:%M'), 'virtual': virtual,
            'type': activity['activity_type'], 'absolute': activity['absolute_time'],
            'watts': activity['match_watts'], 'watts_source': activity['match_watts_source']}


def candidates(store, row, timezone_name, *, activities=None):
    if not row.get('date'):
        return []
    zone = ZoneInfo(timezone_name) if timezone_name else None
    activities = activities if activities is not None else matching_activities(store)
    found = []
    for activity in activities:
        choice = activity_candidate(activity, zone)
        if choice and choice['date'] == row['date']:
            found.append(choice)
    return found


def suggested_match(row, timezone_name, choices):
    if not timezone_name or not row.get('start_time') or not row.get('event'):
        return None
    try:
        local = datetime.fromisoformat(f"{row['date']}T{row['start_time']}")
        zone = ZoneInfo(timezone_name)
        if local.replace(tzinfo=zone, fold=0).utcoffset() != local.replace(tzinfo=zone, fold=1).utcoffset():
            return None
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        return None
    words = lambda text: {word for word in re.findall(r'[a-z0-9]+', text.casefold())
                          if len(word) > 3 and not word.isdigit()
                          and word not in {'zwift', 'race', 'ride', 'stage', 'event', 'virtual'}}
    event_words = words(row['event'])
    matches = []
    for choice in choices:
        if not choice['absolute'] or not choice['virtual'] or choice['date'] != row['date']:
            continue
        if not event_words & words(choice['title']):
            continue
        try:
            activity_time = datetime.fromisoformat(f"{choice['date']}T{choice['time']}")
            if activity_time.replace(tzinfo=zone, fold=0).utcoffset() != activity_time.replace(tzinfo=zone, fold=1).utcoffset():
                continue
        except (ValueError, TypeError):
            continue
        if abs((activity_time - local).total_seconds()) <= 10 * 60:
            matches.append(choice['id'])
    return matches[0] if len(matches) == 1 else None


def revision(values_json, timezone_name=None):
    return hashlib.sha256(json.dumps([values_json, timezone_name]).encode('utf-8')).hexdigest() if values_json is not None else 'new'


def result_state(store, activity_id):
    current = store.connection.execute(
        'SELECT * FROM race_results WHERE activity_id=?', (activity_id,)).fetchone()
    removed = None if current else store.connection.execute(
        'SELECT * FROM race_result_removals WHERE activity_id=? ORDER BY removed_at DESC, removal_id DESC LIMIT 1',
        (activity_id,)).fetchone()
    return current, removed


def result_revision(current, removed):
    if current:
        return revision(json.dumps([current['import_id'], current['accepted_at'], current['values_json']]),
                        current['display_timezone'])
    if removed:
        return revision('removed:' + removed['removal_id'])
    return 'new'


def remove_result(store, activity_id, shown_revision):
    with store._transaction(write=True):
        current, removed = result_state(store, activity_id)
        if not current:
            raise RaceError('The race result is no longer active. Reload Race Results.')
        if result_revision(current, removed) != shown_revision:
            raise RaceError('The race result changed. Review it again before removing it.')
        store.connection.execute(
            'INSERT INTO race_result_removals VALUES (?,?,?,?,?,?,?)',
            (str(uuid4()), activity_id, current['import_id'], current['values_json'],
             current['display_timezone'], current['accepted_at'], _now_iso()))
        store.connection.execute('DELETE FROM race_results WHERE activity_id=?', (activity_id,))


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


_DEFAULT_ZONE = object()


def commit_rows(store, import_id, rows, *, timezone_name=_DEFAULT_ZONE, visible_count=None, visible_confirmed=False):
    from .race_identity import possible_associations, validate_identity_choices
    from .race_matching import batch_matches
    from .race_reconcile import observations, reconcile

    counts = {'added': 0, 'unchanged': 0, 'replaced': 0, 'skipped': 0}
    with store._transaction(write=True):
        source = load_import(store, import_id)
        if source is None:
            raise RaceError('Screenshot import was not found.')
        try:
            screenshot(store, import_id)
        except OSError as exc:
            raise RaceError('Source screenshot is missing or failed integrity verification.') from exc
        timezone_name = source['display_timezone'] if timezone_name is _DEFAULT_ZONE else validate_timezone(timezone_name)
        source_rows, sections, complete = observations(store, source)
        groups = reconcile(source_rows, sections, complete, rows, visible_count, visible_confirmed)
        for item in rows:
            if item['action'] != 'confirm':
                raise RaceError('Every row must be matched automatically; skipping is not permitted.')
        final_rows = [rows[group[0]] for group in groups]
        for item in final_rows:
            row = item['values']
            errors = row_errors(row)
            if errors:
                raise RaceError('Correct invalid rows before confirming: ' + ' '.join(errors))
            validate_shape({'races': [row]})
        decisions = batch_matches([item['values'] for item in final_rows], timezone_name, matching_activities(store))
        failures = [f"Observation {groups[index][0] + 1}: {decision['reason']}" for index, decision in enumerate(decisions)
                    if not decision['activity_id']]
        if failures:
            raise RaceError('Batch blocked: ' + ' '.join(failures))
        candidates = possible_associations(store, source, groups, [item['values'] for item in final_rows],
                                           decisions, timezone_name, visible_count)
        identity_decisions = validate_identity_choices(candidates, final_rows, decisions, timezone_name)
        for item, decision in zip(final_rows, decisions):
            row, activity_id = item['values'], decision['activity_id']
            if item.get('activity_id') and item['activity_id'] != activity_id:
                raise RaceError('Manual activity selection cannot override automatic matching.')
            encoded = json.dumps(row, sort_keys=True, ensure_ascii=False)
            current, removed = result_state(store, activity_id)
            current_revision = result_revision(current, removed)
            if item['shown_activity'] != activity_id or item['shown_revision'] != current_revision:
                raise RaceError('Activity selection or saved result changed. Review changes before confirming.')
            if current and json.loads(current['values_json']) == row and current['display_timezone'] == timezone_name:
                counts['unchanged'] += 1
                continue
            if current and not item['replace']:
                raise RaceError('A changed result needs explicit replacement approval.')
            if removed and not item['replace']:
                raise RaceError('A previously removed result needs explicit restoration approval.')
            now = datetime.now(timezone.utc).isoformat()
            store.connection.execute('INSERT INTO race_result_history VALUES (?,?,?,?,?,?)',
                                     (str(uuid4()), activity_id, import_id, encoded, timezone_name, now))
            store.connection.execute('''INSERT INTO race_results VALUES (?,?,?,?,?)
                ON CONFLICT(activity_id) DO UPDATE SET import_id=excluded.import_id,
                values_json=excluded.values_json, display_timezone=excluded.display_timezone,
                accepted_at=excluded.accepted_at''',
                (activity_id, import_id, encoded, timezone_name, now))
            counts['replaced' if current else 'added'] += 1
        provenance = {'timezone': timezone_name, 'identity_decisions': identity_decisions, 'groups': [
            {'observations': [index + 1 for index in group], 'choices': [rows[index]['group'] for index in group],
             'values': rows[group[0]]['values'], 'activity_id': decision['activity_id'],
             'corrected': bool(rows[group[0]].get('corrected'))}
            for group, decision in zip(groups, decisions)]}
        store.connection.execute('INSERT INTO race_import_reconciliations VALUES (?,?,?,?,?)',
                                 (str(uuid4()), import_id, _now_iso(), visible_count,
                                  json.dumps(provenance, ensure_ascii=False)))
    return counts
