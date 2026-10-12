"""Narrow, read-only browser presentation; no canonical Activity values.

Title/type use latest applicable Strava observations. Date prefers a directly
supplied file session start, then current API absolute start, then parsed CSV date. Summary uses the first file
with an understood session value (or a single TCX lap); unspecified CSV units
are never guessed. Ties are stable by Source ID. All alternatives stay in Store.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import ceil
from urllib.parse import parse_qs, urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .goals import DEFAULT_TIMEZONE

PAGE_SIZE = 30
SORTS = {'newest': 'Newest first', 'oldest': 'Oldest first',
         'duration': 'Longest duration', 'distance': 'Longest distance'}


def _date(value):
    if not value:
        return None
    try:
        # Strava supplies RFC 3339 UTC 'Z'; Python 3.10 needs an explicit offset.
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def _file_type(summary):
    if summary.get('sub_sport') == 'virtual_activity':
        return 'Virtual Ride'
    sport = summary.get('sport')
    if sport and sport.casefold() in ('cycling', 'biking'):
        return 'Ride'
    return (sport or 'Activity').replace('_', ' ').title()


def presentation(snapshot):
    """Metadata only, with each selected value's source and semantic context."""
    evidence = sorted(snapshot['sources'], key=lambda e: (e['source']['imported_at'], e['source']['source_id']))
    csv = [e for e in evidence if e['source']['kind'] == 'strava_export']
    api = [e for e in evidence if e['source']['kind']=='strava_api' and e['source']['is_current']]
    observations = list(reversed(api)) + list(reversed(csv))
    files = [e for e in evidence if e['source']['kind'] not in ('strava_export','strava_api')]
    title_evidence = next((e for e in observations if (e['summary'].get('title') or '').strip()), None)
    type_evidence = next((e for e in observations if e['summary'].get('activity_type')), None)
    type_summary = type_evidence['summary'] if type_evidence else (files[0]['summary'] if files else {})
    activity_type = type_summary.get('activity_type') or _file_type(type_summary)
    subtype = type_summary.get('sport_type') or type_summary.get('sub_sport')
    subtype = subtype.replace('_', ' ').title() if subtype and not type_evidence else subtype
    row = dict(activity_id=snapshot['activity']['activity_id'], sources=evidence,
               activity_type=activity_type, subtype=subtype, title_source=title_evidence,
               type_source=type_evidence or (files[0] if files else None),
               search_titles=[e['summary']['title'].casefold() for e in csv + [e for e in evidence if e['source']['kind']=='strava_api'] if e['summary'].get('title')],
               start_time=None, date_text=None, date_key=None, date_day=None, date_source=None,
               absolute_time=False, duration=None, distance=None, duration_source=None, distance_source=None)
    # Session start is directly supported, unlike an inferred first record time.
    candidates = [(e, e['summary'].get('start_time')) for e in files]
    candidates += [(e, e['summary'].get('date_parsed')) for e in reversed(api)]
    candidates += [(e, e['summary'].get('date_parsed')) for e in reversed(csv)]
    for source, value in candidates:
        stamp = _date(value)
        if stamp is None:
            continue
        absolute = stamp.tzinfo is not None
        if absolute:
            stamp = stamp.astimezone(timezone.utc)
        row.update(start_time=stamp.isoformat(), date_key=stamp.replace(tzinfo=None).isoformat(),
                   date_day=stamp.date().isoformat(), date_source=source, absolute_time=absolute)
        break
    if row['start_time'] is None:
        row['date_text'] = next((e['summary']['date_text'] for e in reversed(csv) if e['summary'].get('date_text')), None)
    for output, field in [('duration', 'total_elapsed_time'), ('distance', 'total_distance')]:
        for source in files + list(reversed(api)):
            value, context = source['summary'].get(field), f"{source['source']['content_format']} session"
            if source['source']['kind']=='strava_api':
                context = 'Strava API summary'
            if value is None and source['source']['content_format'] == 'TCX':
                laps = source.get('xml_context', {}).get('lap_summaries', [])
                if len(laps) == 1:
                    value = laps[0].get('total_time_seconds' if output == 'duration' else 'distance_m')
                    context = 'TCX single lap'
            if value is not None:
                row[output] = value
                row[output + '_source'] = dict(source_id=source['source']['source_id'], context=context)
                break
    if title_evidence:
        row['title'] = title_evidence['summary']['title']
        row['title_origin'] = 'Strava API source title' if title_evidence['source']['kind']=='strava_api' else 'Strava-export source title'
    else:
        stamp = _date(row['start_time'])
        if stamp:
            month = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[stamp.month - 1]
            suffix = f'{month} {stamp.day}, {stamp.year}'
        else:
            suffix = 'date unavailable'
        row['title'] = f'{activity_type} — {suffix}'
        row['title_origin'] = 'Derived title · source activity name unavailable'
    return row


@dataclass(frozen=True)
class BrowserQuery:
    page: int = 1
    q: str = ''
    activity_type: str = 'cycling'
    after: str = ''
    before: str = ''
    sort: str = 'newest'
    timezone_name: str = DEFAULT_TIMEZONE
    message: str = ''

    @classmethod
    def parse(cls, query_string, type_choices):
        messages = []
        try:
            params = parse_qs(query_string, keep_blank_values=True, max_num_fields=20)
        except ValueError:
            params = {}
            messages.append('Too many filters; showing defaults.')
        def value(key, default=''):
            return params.get(key, [default])[-1]
        raw_page = value('page', '1')
        page = int(raw_page) if raw_page.isascii() and raw_page.isdigit() and len(raw_page) <= 6 else 1
        if page < 1 or str(page) != raw_page:
            page = 1
            messages.append('Invalid page; showing page 1.')
        kind = value('type', 'cycling')
        if kind not in ['cycling', 'all', *type_choices]:
            kind = 'cycling'
            messages.append('Unknown type; showing cycling.')
        sort = value('sort', 'newest')
        if sort not in SORTS:
            sort = 'newest'
            messages.append('Unknown sort; showing newest first.')
        after, before = value('from'), value('to')
        dates = []
        for text in (after, before):
            try:
                if text and (len(text) != 10 or date.fromisoformat(text).isoformat() != text):
                    raise ValueError
                dates.append(text)
            except ValueError:
                dates.append('')
                messages.append('Invalid date ignored.')
        after, before = dates
        if after and before and after > before:
            after = before = ''
            messages.append('From must be on or before To; date range ignored.')
        search = value('q').strip()
        if len(search) > 200:
            search = search[:200]
            messages.append('Search limited to 200 characters.')
        timezone_name = value('tz', DEFAULT_TIMEZONE)
        if timezone_name:
            try:
                if len(timezone_name) > 128:
                    raise ValueError
                ZoneInfo(timezone_name)
            except (ValueError, ZoneInfoNotFoundError):
                timezone_name = ''
                messages.append('Browser timezone unavailable; enable JavaScript to set local dates.')
        if (after or before) and not timezone_name:
            messages.append('Local date filtering for absolute timestamps needs your browser timezone; enable JavaScript.')
        return cls(page, search, kind, after, before, sort, timezone_name, ' '.join(messages))

    def url(self, page):
        return '/activities?' + urlencode({'q': self.q, 'type': self.activity_type, 'from': self.after,
                                 'to': self.before, 'sort': self.sort, 'page': page, 'tz': self.timezone_name})


def browse(store, query_string=''):
    rows = [presentation(snapshot) for snapshot in store.activity_history()]
    choices = sorted({value for row in rows for value in (row['activity_type'], row['subtype']) if value})
    query = BrowserQuery.parse(query_string, choices)
    browser_zone = ZoneInfo(query.timezone_name) if query.timezone_name else None
    filtered = []
    for row in rows:
        if query.activity_type == 'cycling' and row['activity_type'].casefold() not in ('ride', 'virtual ride', 'cycling', 'biking'):
            continue
        if query.activity_type not in ('cycling', 'all') and query.activity_type not in (row['activity_type'], row['subtype']):
            continue
        if query.q and not any(query.q.casefold() in title for title in row['search_titles']):
            continue
        if row['absolute_time']:
            # Presentation/filter day only. Never alter the persisted instant or
            # apply this browser timezone to offset-unknown source evidence.
            row['date_day'] = (_date(row['start_time']).astimezone(browser_zone).date().isoformat()
                               if browser_zone is not None else None)
        if (query.after or query.before) and row['date_day'] is None:
            continue
        if query.after and row['date_day'] < query.after:
            continue
        if query.before and row['date_day'] > query.before:
            continue
        filtered.append(row)
    key = {'newest': 'date_key', 'oldest': 'date_key', 'duration': 'duration', 'distance': 'distance'}[query.sort]
    # Sort only known values, then append missing ones. Legitimate zero is known.
    known = sorted((r for r in filtered if r[key] is not None), key=lambda r: r['activity_id'])
    known.sort(key=lambda r: r[key], reverse=query.sort != 'oldest')
    missing = sorted((r for r in filtered if r[key] is None), key=lambda r: r['activity_id'])
    ordered = known + missing
    pages = max(1, ceil(len(ordered) / PAGE_SIZE))
    page = min(query.page, pages)
    start = (page - 1) * PAGE_SIZE
    return dict(rows=ordered[start:start + PAGE_SIZE], total=len(rows), count=len(ordered),
                page=page, pages=pages, start=start, query=query, type_choices=choices)
