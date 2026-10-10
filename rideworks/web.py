"""Small loopback-only browser boundary; no retired application imports."""

from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from time import perf_counter
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from .analysis import analyze_activity
from .errors import RideWorksError
from .history import SORTS, browse, presentation
from .recent_context import recent_context
from .store import Store, resolve_data_dir
from .settings import Settings
from .performance import POLICY, performance_history

STATIC = Path(__file__).with_name('static')
ASSETS = {'training_state.js': 'text/javascript', 'home.js': 'text/javascript', 'style.css': 'text/css', 'review.js': 'text/javascript', 'performance.js': 'text/javascript', 'mark.svg': 'image/svg+xml', 'settings.js': 'text/javascript'}


def duration(seconds):
    if seconds is None:
        return 'Unavailable'
    total = int(float(seconds) + 0.5)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f'{hours}:{minutes:02}:{secs:02}' if hours else f'{minutes}:{secs:02}'


def distance(metres):
    return 'Unavailable' if metres is None else f'{metres / 1609.344:.2f} mi'


def ascent(metres):
    return 'Unavailable' if metres is None else f'{int(metres / 0.3048 + 0.5):,} ft'


def sensor(value, unit):
    return 'Unavailable' if value is None else f'{value} {unit}'


def label(summary):
    if summary.get('sub_sport') == 'virtual_activity':
        return 'Virtual Ride'
    if summary.get('sport') == 'cycling':
        return 'Ride'
    return (summary.get('sport') or 'Activity').replace('_', ' ').title()


def activity_title(summary):
    """Explicit fallback only: source type plus fixed English UTC source date.

    No current FIT source-name evidence is persisted by Phase 1. This does not
    establish a durable title/reconciliation policy or claim an original name.
    """
    timestamp = summary.get('start_time')
    if timestamp is None:
        return f'{label(summary)} — date unavailable'
    date = datetime.fromisoformat(timestamp).astimezone(timezone.utc)
    month = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[date.month - 1]
    return f'{label(summary)} — {month} {date.day}, {date.year}'


def icon(name):
    paths = {
        'duration': '<circle cx="12" cy="13" r="8"/><path d="M12 9v5l3 2M9 2h6M12 2v3"/>',
        'distance': '<path d="m6 3-3 18M18 3l3 18M12 3v3m0 4v4m0 4v3"/>',
        'power': '<path d="m14 2-9 12h6l-1 8 9-13h-6Z"/>',
        'heart': '<path d="M20 5c-3-3-6-1-8 1-2-2-5-4-8-1-5 5 3 11 8 15 5-4 13-10 8-15Z"/>',
        'summary': '<rect x="4" y="5" width="16" height="16" rx="2"/><path d="M8 3v4m8-4v4M4 10h16"/>',
    }
    return f'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>'


def local_time(timestamp, *, compact=False):
    if timestamp is None:
        return 'Date unavailable'
    # A labeled UTC fallback stays understandable without JavaScript.
    compact_attr = ' data-compact-time' if compact else ''
    return (f'<time datetime="{escape(timestamp, quote=True)}" data-local-time{compact_attr}>'
            f'{escape(timestamp)} (UTC source time)</time>')


def shell(title, content, *, active='activities'):
    def nav_state(name):
        return ' class="active" aria-current="page"' if active == name else ''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · RideWorks</title><link rel="icon" href="/static/mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="/static/style.css"><script src="/static/review.js" defer></script><script src="/static/settings.js" defer></script></head>
<body><div class="app-header"><a class="brand" href="/" aria-label="RideWorks Home"><img src="/static/mark.svg" alt="" width="44" height="28"><span>RideWorks</span></a></div>
<aside class="sidebar"><nav aria-label="Main"><a href="/"{nav_state('home')}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 11 9-8 9 8M5 10v11h5v-7h4v7h5V10"/></svg>Home</a><a href="/activities"{nav_state('activities')}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3v17h17M6 15l5-6 4 3 5-6"/></svg>Activities</a><a href="/performance"{nav_state('performance')}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3v17h17M6 16l4-5 4 2 6-9"/></svg>Performance</a><a href="/training-state"{nav_state('training')}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20h18M4 14l4-3 4 5 4-10 4 4"/></svg>Training State</a><a href="/settings"{nav_state('settings')}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4v16M12 4v16M19 4v16M2 8h6m1 8h6m1-7h6"/></svg>Settings</a></nav></aside>
<main>{content}</main></body></html>'''


def browser_time(row, *, compact=False):
    if row['absolute_time']:
        return local_time(row['start_time'], compact=compact)
    if row['start_time']:
        return f"{escape(row['start_time'].replace('T', ' '))} · timezone unknown"
    return escape(row['date_text']) + ' · source date text · timezone unknown' if row['date_text'] else 'Date unavailable'


def activities_page(store, query_string=''):
    result = browse(store, query_string)
    rows, query = result['rows'], result['query']
    def options(choices, current):
        return ''.join(f'<option value="{escape(value, quote=True)}"{" selected" if value == current else ""}>{escape(text)}</option>'
                       for value, text in choices)
    controls = f'''<form class="history-filters panel" action="/activities" method="get" aria-label="Filter activities">
<input type="hidden" name="tz" value="{escape(query.timezone_name, quote=True)}">
<label class="search-filter">Title search<input type="search" name="q" value="{escape(query.q, quote=True)}" placeholder="Search activity names" maxlength="200"></label>
<label>Activity type<select name="type">{options([('cycling', 'Cycling'), ('all', 'All activities')] + [(t, t) for t in result['type_choices']], query.activity_type)}</select></label>
<label>From<input type="date" name="from" value="{query.after}"></label>
<label>To<input type="date" name="to" value="{query.before}"></label>
<label>Sort<select name="sort">{options(list(SORTS.items()), query.sort)}</select></label>
<div class="filter-actions"><button type="submit">Apply</button><a href="/activities">Reset</a></div>
</form><p class="date-filter-note">Dates and filters use your local timezone. Timezone-unknown source dates stay as supplied.</p><noscript>Enable JavaScript to use your browser's local dates for absolute timestamps.</noscript>'''
    if query.message:
        controls += f'<p class="query-message" role="status">{escape(query.message)}</p>'
    if not result['total']:
        body = '''<section class="panel empty"><h2>Import your first ride</h2><p>Preserve a FIT or FIT.GZ file with the RideWorks import command, then reload this page.</p>
<pre>python -m rideworks --data-dir &lt;data-dir&gt; import-fit &lt;activity.fit.gz&gt;</pre><p>Use the same data directory when starting the server.</p></section>'''
    elif not rows:
        body = '<section class="panel empty"><h2>No matching activities</h2><p>Try a different title, type or date range.</p><p><a href="/activities">Reset filters</a></p></section>'
    else:
        items = []
        for row in rows:
            origin = f'<p class="title-origin">{escape(row["title_origin"])}</p>' if row['title_source'] is None else ''
            types = row['activity_type'] + (f" · {row['subtype']}" if row['subtype'] and row['subtype'] != row['activity_type'] else '')
            duration_context = row['duration_source']['context'] if row['duration_source'] else 'Duration unavailable'
            distance_context = row['distance_source']['context'] if row['distance_source'] else 'Distance unavailable'
            items.append(f'''<li><a class="activity-row" href="/activities/{escape(row['activity_id'])}"><div class="row-identity"><h2>{escape(row['title'])}</h2>{origin}</div><div class="row-date">{browser_time(row, compact=True)}</div><span class="row-type">{escape(types)}</span><div class="list-metrics"><span title="{escape(distance_context, quote=True)}">{distance(row['distance'])}</span><span title="{escape(duration_context, quote=True)}">{duration(row['duration'])}</span><span class="open-ride" aria-hidden="true">→</span></div></a></li>''')
        columns = '<div class="activity-columns" aria-hidden="true"><span>Title</span><span>Date</span><span>Type</span><div class="list-metrics"><span>Distance</span><span>Duration</span><span></span></div></div>'
        body = columns + '<ul class="activity-list panel">' + ''.join(items) + '</ul>'
    count = result['count']
    first = result['start'] + 1 if count else 0
    last = result['start'] + len(rows)
    context = f'<p class="result-count" role="status">{first:,}–{last:,} of {count:,} matching activities · {result["total"]:,} in history</p>'
    previous = f'<a rel="prev" href="{escape(query.url(result["page"] - 1), quote=True)}">← Previous</a>' if result['page'] > 1 else '<span aria-disabled="true">← Previous</span>'
    following = f'<a rel="next" href="{escape(query.url(result["page"] + 1), quote=True)}">Next →</a>' if result['page'] < result['pages'] else '<span aria-disabled="true">Next →</span>'
    navigation = f'<nav class="pagination" aria-label="Activity pages">{previous}<span>Page {result["page"]} of {result["pages"]}</span>{following}</nav>'
    return shell('Activities', '<header><h1>Activities</h1></header>' + controls + context + body + navigation)


def metric(name, value, symbol):
    missing = ' class="metric-unavailable"' if value == 'Unavailable' else ''
    return f'<div class="metric"><div>{icon(symbol)}<span>{escape(name)}</span></div><strong{missing}>{escape(value)}</strong></div>'


def detail_rows(rows):
    return '<dl>' + ''.join(f'<div><dt>{escape(str(k))}</dt><dd>{escape(str(v)) if v is not None else "Unavailable"}</dd></div>' for k, v in rows) + '</dl>'


def chart_payload(analysis):
    """Whitelist display evidence only; preserve every native row/value/order."""
    return [{key: record[key] for key in ('record_index', 'timestamp', 'power', 'heart_rate')}
            for record in analysis['native_records']]


def recent_context_panel(context):
    if context is None:
        return ''
    current, prior = context['current'], context['prior']
    values = ''
    if current:
        prior_value = sensor(prior['rounded_watts'], 'W') if prior else 'Unavailable'
        values = f'''<div class="recent-values"><div><span>This ride</span><strong id="recent-current-watts">{sensor(current['rounded_watts'], 'W')}</strong></div><div><span>Prior 42-day best</span><strong id="recent-prior-watts">{prior_value}</strong></div></div>'''
    contribution = ''
    difference = ''
    if prior:
        delta = current['rounded_watts'] - prior['rounded_watts']
        direction = 'above' if delta > 0 else 'below'
        comparison = f'{abs(delta)} W {direction}' if delta else 'Same displayed watts'
        difference = f'<p class="recent-difference" id="recent-difference">{comparison}</p>'
        contribution = f'''<p class="recent-contribution">{browser_time(prior, compact=True)} · {escape(prior['title'])}</p><a id="recent-prior-activity" class="recent-open" href="/activities/{escape(prior['activity_id'], quote=True)}">Open prior ride</a>'''
    messages = {
        'performance_rebuild_required': 'Performance update incomplete; retry the update or Sync now.',
        'outdoor_ride_excluded': 'Outdoor Ride power is excluded from Performance history.',
        'non_virtual_activity': 'Only eligible Virtual Ride power contributes to Performance history.',
        'activity_date_unavailable': 'Activity start is unavailable; the exact prior window cannot be established.',
        'activity_timezone_unknown': 'Activity timezone is unknown; the exact prior window cannot be established.',
        'no_qualifying_prior_result': 'No qualifying prior result in the preceding six weeks.',
    }
    note = 'Performance history · Virtual Ride power evidence' if prior else messages.get(context['reason'], 'This ride has no eligible current Performance result.')
    rows = [('Policy', context['policy']), ('Method', context['method']),
            ('Duration (seconds)', context['duration_seconds']), ('Current Activity ID', context['activity_id']),
            ('Prior window start (exclusive)', context['window_start']),
            ('Prior window end (exclusive)', context['window_end']),
            ('Unavailable reason', context['reason']), ('Pending Performance Activities', context['pending_history'])]
    for name, point in [('Current', current), ('Prior', prior)]:
        if point:
            rows += [(f'{name} Activity ID', point['activity_id']), (f'{name} raw average (W)', point['average_watts'])]
            if point.get('api_evidence'):
                api=point['api_evidence']
                rows += [(f'{name} evidence kind',api['evidence_kind']),
                         (f'{name} API stream Source ID',api['stream_source_id']),
                         (f'{name} API summary Source ID',api['summary_source_id']),
                         (f'{name} API stream mapping',api['mapping_version']),
                         (f'{name} API stream digest',api['observation_sha256'])]
            else:
                rows += [(f'{name} evidence kind','File-backed power'),(f'{name} Source ID',point['source_id']),
                         (f'{name} extraction ID',point['extraction_id'])]
    return f'''<section class="recent-context" aria-labelledby="recent-context-title" data-recent-status="{'available' if prior else 'unavailable'}"><div class="recent-heading"><h3 id="recent-context-title">Compared with previous 6 weeks</h3><a id="recent-performance" href="/performance">View Performance</a></div>{values}{difference}{contribution}<p class="recent-note">{escape(note)}</p><details id="recent-context-details"><summary>Comparison details</summary>{detail_rows(rows)}<p>The prior window is (Activity start − 42 days, Activity start), with both endpoints excluded. The current Activity is excluded from its own baseline. Only current Performance-eligible results with absolute Activity times participate. Highest raw watts win; exact ties use earliest Activity start, then Activity ID. The displayed watt difference subtracts the two displayed whole-watt values; raw averages remain above for inspection and baseline selection. No source summaries or older period bests substitute.</p></details></section>'''


def review_page(analysis, metadata=None, recent=None, streams=None):
    summary = analysis['source_summary']['values']
    source, extraction = analysis['source'], analysis['extraction']
    best = analysis['best_20_minute_power']
    activity_id = analysis['activity']['activity_id']
    title = metadata['title'] if metadata else activity_title(summary)
    title_origin = metadata['title_origin'] if metadata else 'Derived title'
    subtype = (summary.get('sub_sport') or summary.get('sport') or 'Type unavailable').replace('_', ' ').title()
    cards = ''.join(metric(name, value, symbol) for name, value, symbol in [
        ('Elapsed duration', duration(summary.get('total_elapsed_time')), 'duration'),
        ('Distance', distance(summary.get('total_distance')), 'distance'),
        ('Average power', sensor(summary.get('avg_power'), 'W'), 'power'),
        ('Average heart rate', sensor(summary.get('avg_heart_rate'), 'bpm'), 'heart'),
    ])
    summary_rows = [
        ('Elapsed duration', duration(summary.get('total_elapsed_time'))),
        ('Timer duration', duration(summary.get('total_timer_time'))),
        ('Distance', distance(summary.get('total_distance'))),
        ('Ascent', ascent(summary.get('total_ascent'))),
        ('Average power', sensor(summary.get('avg_power'), 'W')),
        ('Maximum power', sensor(summary.get('max_power'), 'W')),
        ('Average heart rate', sensor(summary.get('avg_heart_rate'), 'bpm')),
        ('Maximum heart rate', sensor(summary.get('max_heart_rate'), 'bpm')),
        ('Average cadence', sensor(summary.get('avg_cadence'), 'rpm')),
    ]
    source_rows = [('Activity ID', activity_id), ('Displayed title', title),
                   ('Title origin', 'Derived fallback; source activity name unavailable'),
                   ('Title basis', 'FIT activity type + source start date (UTC); fixed English month names'),
                   ('Source ID', source['source_id']),
                   ('Original basename', source['original_basename']), ('Artifact SHA-256', source['sha256']),
                   ('Artifact byte size', source['byte_size']), ('Packaging', source['packaging']),
                   ('Content format', source['content_format']),
                   ('Parser', extraction['parser_name']), ('Parser version', extraction['parser_version']),
                   ('Mapping version', extraction['mapping_version']),
                   ('Current extraction ID', extraction['extraction_id']),
                   ('Source start time (UTC)', summary.get('start_time'))]
    if metadata and metadata['title_source']:
        title_source = metadata['title_source']['source']
        api_title = title_source['kind']=='strava_api'
        source_rows[2:4] = [('Title origin', 'Source-supplied Strava API evidence' if api_title else 'Source-supplied Strava-export evidence'),
                            ('Title Source ID', title_source['source_id']),
                            ('Title display policy', 'Current non-empty API title preferred over export title; observations retained' if api_title else 'Latest non-empty imported Strava-export title; observations retained')]
    if metadata and metadata['type_source'] and metadata['type_source']['source']['kind'] in ('strava_export','strava_api'):
        source_rows += [('Displayed type origin', 'Strava API source evidence' if metadata['type_source']['source']['kind']=='strava_api' else 'Strava-export source evidence'),
                        ('Type Source ID', metadata['type_source']['source']['source_id'])]
    if metadata:
        for e in metadata['sources']:
            if e['source']['kind'] in ('strava_export','strava_api'):
                origin = 'Strava API' if e['source']['kind']=='strava_api' else 'Strava export'
                source_rows += [(origin+' title observation', e['summary'].get('title')),
                                (origin+' observation Source ID', e['source']['source_id'])]
                if e['source']['kind']=='strava_api':
                    source_rows += [('API retrieved at (UTC)',e['source']['imported_at']),
                                    ('Current API observation',bool(e['source']['is_current'])),
                                    ('API mapping',e['extraction']['mapping_version'])]
    for signal, name in [('power', 'Power'), ('heart_rate', 'Heart rate')]:
        a = analysis['availability'][signal]
        source_rows.extend([(f'{name} availability', a['status']),
                            (f'{name} samples', f"{a['present']} present / {a['missing']} missing / {a['total']} total"),
                            (f'{name} origin', a['origin'])])
    best_rows = [('Origin', 'RideWorks-calculated'), ('Method/version', best['method']),
                 ('Status', best['status']), ('Unavailable reason', best['reason'])] if not best['eligible'] else [
        ('Origin', 'RideWorks-calculated'), ('Method/version', best['method']),
        ('Native samples in window', best['sample_count']),
        ('Record indices (start inclusive / end exclusive)', f"{best['start_record_index']} / {best['end_exclusive_record_index']}"),
        ('Window start (UTC)', best['start_timestamp']), ('Window end, exclusive (UTC)', best['end_exclusive_timestamp']),
        ('Unrounded average', sensor(best['average_watts'], 'W')), ('Eligible windows', best['eligible_window_count'])]
    window_text = 'No eligible complete 20-minute window.'
    if best['eligible']:
        start = summary.get('start_time')
        if start is not None:
            offset = (datetime.fromisoformat(best['start_timestamp']) - datetime.fromisoformat(start)).total_seconds()
            window_text = f"{duration(offset)}–{duration(offset + best['duration_seconds'])} elapsed · {best['sample_count']:,} native samples"
        else:
            window_text = f"{best['sample_count']:,} native samples · window timestamps in calculation details"
    records = chart_payload(analysis)
    # Avoid closing the JSON script element with any source text. Never embed
    # private file/store paths, coordinates, or a raw application snapshot.
    payload = json.dumps(records, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c').replace('&', '\\u0026')
    type_text = metadata['activity_type'] if metadata and metadata['type_source'] and metadata['type_source']['source']['kind'] in ('strava_export','strava_api') else (summary.get('sport') or 'Unavailable').replace('_', ' ').title()
    if metadata and metadata['subtype']:
        subtype = metadata['subtype']
    return shell(title, f'''<header><div class="breadcrumb"><a href="/activities">Activities</a><span>/</span>Ride details</div><div class="ride-heading"><h1>{escape(title)}</h1><span class="title-origin">{escape(title_origin)}</span></div><p class="ride-meta">{local_time(summary.get('start_time'))}<span class="meta-separator">·</span>Type: {escape(type_text)}<span class="meta-separator">·</span>Subtype: {escape(subtype)}<span class="meta-separator">·</span>FIT source</p></header>
<section class="metrics" aria-label="FIT session source summary">{cards}</section>
<div class="review-layout"><div class="review-main"><section class="panel chart-panel" aria-labelledby="chart-title">
<div class="panel-heading"><h2 id="chart-title">Ride power &amp; heart rate</h2><div class="legend"><span><i class="power-swatch"></i>Power · W</span><span><i class="hr-swatch"></i>Heart rate · bpm</span></div></div>
<div id="ride-chart" data-record-count="{len(records)}" data-start-time="{escape(summary.get('start_time') or '', quote=True)}"><svg id="chart-svg" role="img" aria-label="Native power and heart rate over elapsed ride time" aria-describedby="chart-help"></svg></div>
<div id="sample-readout" role="status" aria-live="polite">Move over the chart to inspect power and heart rate.</div>
<div class="chart-footer"><span>{len(records):,} recorded samples · elapsed time</span><span id="chart-help">Focus chart + arrow keys to inspect</span></div>
<noscript>Enable JavaScript to review the native chart and display dates in your local timezone.</noscript></section>
<section class="panel best-panel"><div><h2>{icon('power')}Best 20-minute power</h2><p>RideWorks-calculated</p></div><strong class="best-value">{sensor(best['rounded_watts'], 'W')}</strong><p class="window-context">{escape(window_text)}</p>
<details><summary>Calculation details</summary>{detail_rows(best_rows)}<p>Complete 1,200-sample windows with one-second timestamps and no missing power. Earliest window wins a tie; whole watts round half up. No repaired or estimated samples.</p></details>{recent_context_panel(recent)}</section>
<details class="panel provenance"><summary>Source &amp; provenance</summary><p>Ride summary values are FIT session source evidence. Sensor origins remain unknown; presence does not establish measurement origin.</p>{detail_rows(source_rows)}</details></div>
<aside class="panel ride-summary"><h2>{icon('summary')}Ride summary</h2><p class="source-caption">FIT session source evidence</p>{detail_rows(summary_rows)}</aside></div>
<script id="native-records" type="application/json">{payload}</script>{stream_details(streams or [])}''')


def stream_details(observations):
    parts=[]
    for observation in observations:
        rows=[('Source ID',observation['source_id']),('Related API summary Source',observation['summary_source_id']),
              ('Retrieved at (UTC)',observation['retrieved_at']),('Mapping',observation['mapping_version']),
              ('Current stream observation',bool(observation['is_current'])),
              ('Requested types',', '.join(observation['requested'])),('Summary start_date',observation['start_date'])]
        for key,metadata in observation['metadata'].items():
            rows += [(key+' '+field,value) for field,value in metadata.items()]
        parts.append('<details class="panel provenance stream-provenance"><summary>Strava API stream evidence</summary>'
                     '<p>Additional API source evidence; not a native-file extraction. Signal presence does not establish measured origin.</p>'
                     +detail_rows(rows)+'</details>')
    return ''.join(parts)


def stream_chart(observation):
    streams=observation['streams'];offsets=streams['time']['data']
    power=streams.get('watts',{}).get('data',[None]*len(offsets))
    hr=streams.get('heartrate',{}).get('data',[None]*len(offsets))
    samples=[dict(sample_index=i,time_offset=t,power=power[i],heart_rate=hr[i]) for i,t in enumerate(offsets)]
    payload=json.dumps(samples,allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    return f'''<section class="panel chart-panel" aria-labelledby="chart-title">
<h2 id="chart-title">Ride power &amp; heart rate</h2><p class="source-caption">Strava API stream evidence</p>
<div class="legend"><span><i class="power-swatch"></i>Power · W</span><span><i class="hr-swatch"></i>Heart rate · bpm</span></div>
<div id="ride-chart" data-api-sample-count="{len(samples)}" data-start-time="{escape(observation['start_date'],quote=True)}"><svg id="chart-svg" role="img" aria-label="Strava API power and heart rate at returned elapsed time offsets" aria-describedby="chart-help"></svg></div>
<div id="sample-readout" role="status" aria-live="polite">Move over the chart to inspect returned Strava samples.</div>
<div class="chart-footer"><span>{len(samples):,} returned samples · elapsed time</span><span id="chart-help">Focus chart + arrow keys to inspect</span></div>
<p class="source-caption">Returned time offsets are used directly. Missing values and gaps longer than one second break the lines; no intermediate samples are invented. Performance eligibility follows the versioned evidence policy.</p>
<details><summary>Time mapping</summary><p>For local date/time inspection, the related Strava summary start_date plus the returned time offset supplies a presentation timestamp. Original offsets and source metadata are retained separately.</p></details>
<noscript>Enable JavaScript to review the Strava stream chart.</noscript></section>
<script id="api-stream-samples" type="application/json">{payload}</script>'''


def api_review_page(row, observation, observations, source_details, recent=None):
    from .strava_streams import review_best20
    summary_source = next(e for e in row['sources'] if e['source']['kind']=='strava_api' and e['source']['is_current'])
    summary = summary_source['summary']['values']
    cards = ''.join(metric(name, value, symbol) for name, value, symbol in [
        ('Elapsed duration', duration(summary.get('elapsed_time')), 'duration'),
        ('Distance', distance(summary.get('distance')), 'distance'),
        ('Average power', sensor(summary.get('average_watts'), 'W'), 'power'),
        ('Average heart rate', sensor(summary.get('average_heartrate'), 'bpm'), 'heart'),
    ])
    summary_rows = [
        ('Elapsed duration', duration(summary.get('elapsed_time'))),
        ('Moving duration', duration(summary.get('moving_time'))),
        ('Distance', distance(summary.get('distance'))),
        ('Ascent', ascent(summary.get('total_elevation_gain'))),
        ('Average power', sensor(summary.get('average_watts'), 'W')),
        ('Maximum power', sensor(summary.get('max_watts'), 'W')),
        ('Average heart rate', sensor(summary.get('average_heartrate'), 'bpm')),
        ('Maximum heart rate', sensor(summary.get('max_heartrate'), 'bpm')),
        ('Average cadence', sensor(summary.get('average_cadence'), 'rpm')),
        ('Energy', sensor(summary.get('kilojoules'), 'kJ')),
    ]
    best = review_best20(observation)
    reasons = {
        'watts_stream_missing': 'No Strava watts stream is available.',
        'time_missing': 'No Strava time stream is available.',
        'signal_time_pairing_ambiguous': 'Watts and time cannot be paired without assumptions.',
        'activity_shorter_than_required': 'Fewer than 1,200 returned samples; a complete 20-minute window is unavailable.',
        'no_complete_one_second_window': 'No complete window of 1,200 consecutive one-second offsets.',
        'incomplete_power': 'Every complete one-second window contains missing power.',
    }
    window_text = reasons.get(best['reason'], '')
    if best['status']=='available':
        window_text = f"{duration(best['start_offset'])}–{duration(best['end_exclusive_offset'])} elapsed · {best['sample_count']:,} returned samples"
    best_rows = [('Origin', 'RideWorks-calculated from Strava API stream evidence'),
                 ('Method/version', best['method']), ('Stream Source ID', best['source_id']),
                 ('Related API summary Source ID', best['summary_source_id']),
                 ('Retrieved at (UTC)', observation['retrieved_at']), ('Stream mapping', observation['mapping_version']),
                 ('Status', best['status']), ('Unavailable reason', best['reason']),
                 ('Samples in window', best['sample_count']),
                 ('Returned-offset start (inclusive, seconds)', best['start_offset']),
                 ('Returned-offset end (exclusive, seconds)', best['end_exclusive_offset']),
                 ('Unrounded average', sensor(best['average_watts'], 'W')),
                 ('Eligible windows', best['eligible_window_count'])]
    eligible=bool(recent and recent.get('current') and recent['current'].get('eligible',True))
    reason=(recent or {}).get('reason')
    eligibility_note='Performance-eligible evidence · '+POLICY if eligible else 'Excluded from Performance history.'
    if not eligible and reason:
        eligibility_note += ' '+{
            'api_device_watts_not_confirmed':'Strava does not confirm device power.',
            'api_power_stream_unavailable':'No eligible API watts/time stream.',
            'api_stream_not_high_resolution':'API sampling resolution is not high.',
            'api_stream_not_full_length':'The API stream is not full length.',
            'api_stream_summary_not_current':'The stream does not match the current summary observation.',
            'outdoor_ride_excluded':'Outdoor Ride power is excluded.',
            'non_virtual_activity':'Only Virtual Rides qualify.',
            'performance_rebuild_required':'Performance update incomplete; retry the update or Sync now.',
        }.get(reason,'The returned evidence does not meet the Performance policy.')
    best_rows += [('Performance policy',POLICY),('Performance eligibility reason',None if eligible else reason)]
    return shell(row['title'], f'''<header><div class="breadcrumb"><a href="/activities">Activities</a><span>/</span>Ride details</div><div class="ride-heading"><h1>{escape(row['title'])}</h1><span class="title-origin">{escape(row['title_origin'])}</span></div><p class="ride-meta">{browser_time(row,compact=True)}<span class="meta-separator">·</span>Type: {escape(row['activity_type'])}<span class="meta-separator">·</span>Subtype: {escape(row['subtype'] or 'Unavailable')}<span class="meta-separator">·</span>Strava API source</p></header>
<section aria-label="Strava API summary evidence"><p class="source-caption">Strava API summary evidence · supplied averages</p><div class="metrics">{cards}</div></section>
<div class="review-layout"><div class="review-main">{stream_chart(observation)}
<section class="panel best-panel api-best20" data-best20-status="{best['status']}"><div><h2>{icon('power')}Best 20-minute power</h2><p>RideWorks-calculated from Strava API stream evidence</p></div><strong class="best-value">{sensor(best['rounded_watts'],'W')}</strong><p class="window-context">{escape(window_text)}</p>
<p class="source-caption">{escape(eligibility_note)}</p>
<details><summary>Calculation details</summary>{detail_rows(best_rows)}<p>Exactly 1,200 complete power samples at consecutive one-second returned offsets. Zero watts count. Highest raw average wins; exact ties choose the earliest window; displayed watts round half up. No interpolation or repaired samples.</p></details>{recent_context_panel(recent) if eligible else ''}</section>
{stream_details(observations)}<section class="thin-sources" aria-label="Associated source evidence">{source_details}</section></div>
<aside class="panel ride-summary"><h2>{icon('summary')}Ride summary</h2><p class="source-caption">Strava API summary evidence</p>{detail_rows(summary_rows)}<details><summary>Summary source</summary>{detail_rows([('Source ID',summary_source['source']['source_id']),('Retrieved at (UTC)',summary_source['source']['imported_at']),('Mapping',summary_source['extraction']['mapping_version'])])}<p>Values are supplied by Strava; averages are not calculated from the retained API stream. Stream observations retain their own related summary Source.</p></details></aside></div>''')


def thin_review_page(row, streams=None, stream_reason=None, recent=None):
    observations=streams or []
    current=next((s for s in reversed(observations) if s['is_current']),None)
    api_only=all(e['source']['kind']=='strava_api' for e in row['sources'])
    rich_api=bool(api_only and current and current['chart_unavailable_reason'] is None)
    sources = []
    for evidence in row['sources']:
        source, summary = evidence['source'], evidence['summary']
        csv = source['kind'] == 'strava_export'
        api = source['kind']=='strava_api'
        name = 'Strava API metadata' if api else 'Strava-export metadata' if csv else f"{source['content_format']} source evidence"
        values = [('Source ID', source['source_id'])]
        if api:
            values += [('Retrieved at (UTC)',source['imported_at']),('Current observation',bool(source['is_current'])),
                       ('Mapping',evidence['extraction']['mapping_version']),('Association basis',source['association_basis'])]
            units={'distance':'m','elapsed_time':'s','moving_time':'s','total_elevation_gain':'m',
                   'average_watts':'W','weighted_average_watts':'W','max_watts':'W','kilojoules':'kJ',
                   'average_heartrate':'bpm','max_heartrate':'bpm','average_cadence':'rpm','utc_offset':'s'}
            values += [(key.replace('_',' ').capitalize()+(f' ({units[key]})' if key in units else ''),value)
                       for key,value in summary['values'].items() if key!='id']
            note = 'Strava API summaries are supplied source evidence, retained separately from stream evidence and RideWorks calculations.'
        elif csv:
            values += [('Title', summary.get('title')), ('Activity type', summary.get('activity_type')),
                       ('Sport type', summary.get('sport_type')), ('Source date text', summary.get('date_text'))]
            values += [(f"{f['column']} (column {f['column_index'] + 1}; {f['unit'].replace('source_unspecified', 'units unspecified')})", f['raw_value'] or None)
                       for f in summary.get('fields', []) if f['status'] != 'missing']
            note = 'CSV summaries are source metadata. Where units are unspecified, values are shown as supplied. Native streams are unavailable from this source.'
        else:
            values += [('Source start time', summary.get('start_time')),
                       ('Elapsed duration', duration(summary.get('total_elapsed_time'))),
                       ('Timer duration', duration(summary.get('total_timer_time'))),
                       ('Distance', distance(summary.get('total_distance')))]
            extraction = evidence['extraction']
            values += [('Parser', extraction['parser_name']), ('Parser version', extraction['parser_version']),
                       ('Mapping version', extraction['mapping_version']), ('Native records preserved', extraction['record_count'])]
            for signal, label_text in [('power', 'Power'), ('heart_rate', 'Heart rate')]:
                a = evidence['availability'][signal]
                values += [(f'{label_text} availability', a['status']), (f'{label_text} origin', a['origin'])]
            for i, lap in enumerate(evidence.get('xml_context', {}).get('lap_summaries', []), 1):
                values += [(f'Lap {i} source duration', duration(lap.get('total_time_seconds'))),
                           (f'Lap {i} source distance', distance(lap.get('distance_m'))),
                           (f'Lap {i} average power', sensor(lap.get('avg_power'), 'W')),
                           (f'Lap {i} maximum power', sensor(lap.get('max_power'), 'W')),
                           (f'Lap {i} average heart rate', sensor(lap.get('avg_heart_rate'), 'bpm')),
                           (f'Lap {i} maximum heart rate', sensor(lap.get('max_heart_rate'), 'bpm'))]
            note = 'Native source evidence is preserved. Detailed RideWorks review is not yet supported for this evidence. Signal presence does not establish measurement origin.'
        sources.append(f'<details class="panel provenance"{"" if rich_api else " open"}><summary>{escape(name)}</summary><p>{escape(note)}</p>{detail_rows(values)}</details>')
    if rich_api:
        return api_review_page(row,current,observations,''.join(sources),recent)
    else:
        from .strava_streams import REASONS
        explanation=REASONS.get((current or {}).get('chart_unavailable_reason') or stream_reason or 'not_fetched','Stream review is unavailable.')
        reason_note=f'<p>{escape(explanation)}</p>' if all(e['source']['kind']=='strava_api' for e in row['sources']) else ''
        intro=f'<section class="panel review-unavailable"><h2>Detailed RideWorks review unavailable</h2><p>This activity does not currently have a single supported FIT analysis source. Available source evidence is shown below; no charts or best-20 result are substituted.</p>{reason_note}</section>'
    return shell(row['title'], f'''<header><div class="breadcrumb"><a href="/activities">Activities</a><span>/</span>Activity details</div><h1>{escape(row['title'])}</h1><p class="title-origin">{escape(row['title_origin'])}</p><p class="ride-meta">{browser_time(row,compact=bool(api_only and current and current['chart_unavailable_reason'] is None))} · Type: {escape(row['activity_type'])} · Subtype: {escape(row['subtype'] or 'Unavailable')}</p></header>
{intro}{stream_details(observations)}
<section class="thin-sources" aria-label="Associated source evidence">{''.join(sources)}</section>''')


def performance_page(store):
    from .performance import performance_history
    from .performance_view import performance_view
    history = performance_history(store)
    points = history['points']
    view = performance_view(points)
    def safe_json(value):
        return json.dumps(value, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    def summary_card(key, label):
        index = view['summaries'][key]
        if index is None:
            return f'<article class="performance-card" data-summary="{key}"><h2>{label}</h2><strong>Unavailable</strong><p>No qualifying result in this period</p></article>'
        point = points[index]
        age = view['ages_days'].get(str(index))
        freshness = f"{age} days ago" if age is not None else 'Timezone unknown'
        return f'''<article class="performance-card" data-summary="{key}" data-point-index="{index}"><h2>{label}</h2>
<strong>{point['rounded_watts']} <span>W</span></strong><p class="performance-card-date">{browser_time(point, compact=True)}</p>
<a href="/activities/{point['activity_id']}" title="{escape(point['title'], quote=True)}">{escape(point['title'])}</a><p class="performance-freshness">{freshness}</p></article>'''
    if points:
        cards = ''.join(summary_card(key, label) for key, label in [('current','Current 42-day best'),
                        ('latest','Latest eligible ride'),('year','Best in last 12 months'),('lifetime','Lifetime best')])
        chart = f'''<div class="performance-workspace">
<section class="performance-summary" aria-label="Performance power summaries">{cards}</section>
<section class="panel performance-chart-panel">
<div class="performance-controls">
<div class="performance-control-group"><span>Range</span><div class="performance-ranges" role="group" aria-label="Range"><button type="button" data-range="3mo">3 mo</button><button type="button" data-range="6mo">6 mo</button><button type="button" data-range="1yr" aria-pressed="true">1 yr</button><button type="button" data-range="3yr">3 yr</button><button type="button" data-range="all">All</button></div></div>
<div class="performance-control-group"><span>View</span><div class="performance-views" role="group" aria-label="View"><button type="button" data-view="rolling" aria-pressed="true">Rolling 42-day</button><button type="button" data-view="monthly">Monthly best</button><button type="button" data-view="yearly">Yearly best</button></div></div>
<div class="performance-control-group"><span>Evidence</span><div class="performance-evidence-control" role="group" aria-label="Chart evidence"><button type="button" data-evidence="trend" aria-pressed="true">Trend only</button><button type="button" data-evidence="rides">Trend + rides</button></div></div>
</div>
<div class="performance-chart-heading"><div><h2 id="performance-chart-title">Rolling 42-day best</h2><p id="performance-chart-caption">Strongest qualifying ride in each trailing 42-day window</p></div><span id="performance-visible-count"></span></div>
<svg id="performance-chart" role="img" tabindex="0" aria-label="20-minute power history in watts. Arrow keys inspect results; Enter opens the selected Activity."></svg>
<p id="performance-chart-empty" hidden>No eligible evidence in this period. Choose a longer range.</p>
<div class="performance-selection"><p id="performance-selection-label">Selected result</p><div id="performance-readout" aria-live="polite"><time id="performance-date"></time><a id="performance-activity"></a><strong id="performance-watts"></strong></div>
<details id="performance-point-details"><summary>Selected result provenance</summary><dl id="performance-point-context"></dl></details></div>
<p class="chart-footer" id="performance-chart-help">Hover or use arrow keys to inspect. Click a result or press Enter to open the Activity.</p>
<noscript>Enable JavaScript to view the chart and use Performance modes.</noscript></section>
<details class="panel performance-evidence"><summary>Eligible ride results <span id="performance-evidence-count"></span></summary>
<div class="performance-evidence-table"><table><thead><tr><th>Date</th><th>Activity</th><th>Best 20 min</th></tr></thead><tbody id="performance-rides"></tbody></table></div>
<div class="performance-evidence-pages"><button type="button" id="performance-rides-prev">Previous</button><span id="performance-rides-page"></span><button type="button" id="performance-rides-next">Next</button></div></details></div>'''
    else:
        message = ('Performance history has not been rebuilt yet.' if history['current'] == 0 else
                   'No current ride result qualifies for the 20-minute Performance history.')
        chart = f'<section class="panel empty"><h2>20-minute power history</h2><p>{message}</p></section>'
    notices = []
    if history['pending']:
        notices.append(f"{history['pending']:,} Activities need a performance rebuild; changed inputs are not plotted.")
    if history['missing_dates']:
        notices.append(f"{history['missing_dates']:,} eligible results lack a supported Activity date and are not plotted.")
    if view['unknown_timezones']:
        notices.append(f"{view['unknown_timezones']:,} results have source dates with unknown timezones: available in period views, unavailable for exact timed-window summaries.")
    return shell('Performance', f'''<header><h1>Performance</h1><p class="performance-count">20-minute power · {len(points):,} eligible ride results · Virtual Ride power evidence</p></header>{chart}
<p class="performance-notice">{escape(' '.join(notices))}</p>
<details class="panel performance-policy"><summary>Eligibility &amp; method</summary>
<p>Virtual Ride file-backed power has precedence. When no file-backed power evidence exists, current Strava API time/watts streams may qualify if device watts are confirmed, both streams are high resolution and full length, and valid timing/power supports a complete window. Power presence alone does not establish measured origin. Outdoor Ride power remains excluded.</p>
<p>RideWorks calculates the highest average over exactly 1,200 samples with consecutive one-second timestamps or returned offsets and complete power. Zero watts count; missing power, gaps and duplicate or backward timing invalidate affected windows. No interpolation, resampling or repair occurs. Exact ties choose the earliest window; display rounds whole watts half up.</p>
<p>The trend retains the strongest qualifying result in the trailing 42 days, changing when a ride enters or leaves the window. A result expires exactly 42 days after its Activity start. Gaps mean there is no qualifying result; the line is demonstrated evidence rather than an estimated daily performance series. Time ranges end at the page's current time; monthly and yearly bests use displayed calendar periods and only rides within the selected range. Period-best lines connect consecutive calendar periods at the contributing ride dates, with point markers. Missing periods have no mark and break the line. Raw values choose the best; exact ties retain the earliest Activity.</p>
<p>Method: best-average-power-v1 · Policy: {POLICY}. One eligible file Source controls each file-backed Activity result; multiple eligible file Sources are ambiguous and excluded. API evidence cannot bypass ineligible file-backed power. API results retain stream/summary provenance and returned-offset window bounds. CSV and summary averages never substitute for sample power. Ineligible or missing results are not plotted as zero.</p>
</details>
<details class="panel performance-future"><summary>Future Performance candidates</summary><p>Possible future direction includes additional performance durations and broader power history, FTP and historical athlete context, richer recent-versus-historical comparisons, and explainable performance or training-state signals. These are candidates, not implemented features or delivery commitments.</p></details>
<script id="performance-points" type="application/json">{safe_json(points)}</script><script id="performance-view" type="application/json">{safe_json(view)}</script><script src="/static/performance.js" defer></script>''', active='performance')


class Application:
    """Local routes; each evidence request gets a short-lived Store snapshot."""
    def __init__(self, data_dir=None, *, settings_factory=Settings):
        self.data_dir = resolve_data_dir(data_dir)
        self.settings = settings_factory(self.data_dir)
        with Store(self.data_dir):
            pass

    def get(self, target):
        url = urlsplit(target)
        path = url.path
        if self.legacy_browser_target(target):
            return 303, 'text/plain', b''
        if path.startswith('/static/'):
            name = path.removeprefix('/static/')
            if name in ASSETS:
                return 200, ASSETS[name], (STATIC / name).read_bytes()
        with Store(self.data_dir) as store:
            if path == '/settings':
                return 200, 'text/html', self.page(store, shell('Settings', self.settings.content(local_time,url.query), active='settings'))
            if path == '/':
                from .home import home_page
                return 200, 'text/html', self.page(store, home_page(store,url.query))
            if path == '/activities':
                return 200, 'text/html', self.page(store, activities_page(store, url.query))
            if path == '/training-state':
                from .training_state_page import training_page
                return 200, 'text/html', self.page(store, training_page(store,url.query))
            if path == '/performance':
                return 200, 'text/html', self.page(store, performance_page(store))
            if path.startswith('/activities/'):
                activity_id = path.removeprefix('/activities/')
                try:
                    # Stable UUID routes; never interpolate a route into SQL.
                    if str(UUID(activity_id)) != activity_id:
                        raise ValueError
                except ValueError:
                    return self.not_found()
                with store._transaction():
                    snapshots = store.activity_history(activity_id)
                    if not snapshots:
                        return self.not_found()
                    metadata = presentation(snapshots[0])
                    streams=store.strava_stream_evidence(activity_id)
                    failure=store.connection.execute('''SELECT reason FROM strava_stream_attempts t JOIN strava_api_activities a ON a.external_id=t.external_id WHERE a.activity_id=?''',(activity_id,)).fetchone()
                    stream_reason=failure[0] if failure else None
                    fit_sources = [e for e in snapshots[0]['sources'] if e['source']['kind'] == 'file_fit']
                    if len(fit_sources) != 1:
                        return 200, 'text/html', self.page(store, thin_review_page(metadata,streams,stream_reason,recent_context(store,activity_id)))
                    try:
                        analysis = analyze_activity(store, activity_id)
                    except RideWorksError:
                        html = thin_review_page(metadata,streams,stream_reason)
                    else:
                        html = review_page(analysis, metadata, recent_context(store, activity_id),streams)
                    return 200, 'text/html', self.page(store, html)
        return self.not_found()

    def page(self, store, html):
        pending = performance_history(store)['pending']
        if pending:
            noun = 'Activity needs' if pending == 1 else 'Activities need'
            banner = f'''<section class="performance-update" role="status" aria-label="Performance update incomplete">
<div><strong>Performance update incomplete</strong><p>{pending:,} {noun} an update. New or changed evidence is not yet reflected in Performance. Your ride data is retained.</p></div>
<form method="post" data-settings-action action="/settings/performance/rebuild"><input type="hidden" name="nonce" value="{self.settings.nonce}"><button type="submit">Retry Performance update</button></form></section>'''
            html = html.replace('<main>', '<main>'+banner, 1)
        return html.encode()

    @staticmethod
    def legacy_browser_target(target):
        url = urlsplit(target)
        if url.path != '/' or not url.query:
            return None
        try:
            values = parse_qs(url.query,max_num_fields=20,keep_blank_values=True)
        except ValueError:
            return '/activities?'+url.query
        if set(values) & {'q','type','from','to','sort','page','tz'}:
            return '/activities?'+url.query
        return None

    @staticmethod
    def not_found():
        return 404, 'text/html', shell('Activity not found', '<header><h1>Activity not found</h1><p>Return to <a href="/activities">Activities</a> to open an imported ride.</p></header>').encode()


def create_server(data_dir=None, port=8765, *, debug=False, settings_factory=Settings):
    app = Application(data_dir, settings_factory=settings_factory)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond('GET')

        def do_POST(self):
            self.respond('POST')

        def respond(self, method):
            started = perf_counter()
            headers = {}
            try:
                allowed_hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
                if self.headers.get('Host') not in allowed_hosts:
                    status, content_type, body = 403, 'text/plain', b'Invalid local host.'
                elif method == 'POST':
                    size = self.headers.get('Content-Length', '')
                    if not size.isascii() or not size.isdecimal() or not 0 < int(size) <= 1024:
                        status, content_type, body = 413, 'text/plain', b'Invalid Settings action size.'
                    elif self.headers.get_content_type() != 'application/x-www-form-urlencoded':
                        status, content_type, body = 415, 'text/plain', b'Use the Settings form.'
                    else:
                        status, headers, body = app.settings.post(urlsplit(self.path).path, self.rfile.read(int(size)), self.headers.get('Origin'))
                        content_type = 'text/plain'
                elif urlsplit(self.path).path == '/strava/callback':
                    status, headers, body = app.settings.callback(urlsplit(self.path).query)
                    content_type = 'text/plain'
                else:
                    status, content_type, body = app.get(self.path)
                    if status == 303:
                        headers['Location'] = app.legacy_browser_target(self.path)
            except Exception as exc:
                # Never log URLs, bodies, private paths, SQL or exception text.
                print(f'RideWorks request failed ({type(exc).__name__})', flush=True)
                if urlsplit(self.path).path == '/strava/callback':
                    app.settings.notice = 'Authorization could not complete. Reconnect from Settings.'
                    status, headers, body = app.settings.redirect()
                    content_type = 'text/plain'
                else:
                    status, content_type, body = 500, 'text/html', shell('Unable to complete request', '<h1>Unable to complete request</h1><p>Reload RideWorks and try again.</p>').encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type + ('; charset=utf-8' if content_type.startswith('text/') else ''))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer' if urlsplit(self.path).path == '/strava/callback' else 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self' https://www.strava.com; frame-ancestors 'none'")
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)
            if debug:
                print(f'RideWorks request: {method} {status} ({(perf_counter() - started) * 1000:.1f} ms)', flush=True)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    app.settings.port = server.server_port
    return server


def serve(data_dir=None, port=8765, *, debug=False):
    with create_server(data_dir, port, debug=debug) as server:
        print(f'RideWorks: http://127.0.0.1:{server.server_port}/ (Ctrl+C to stop)', flush=True)
        if debug:
            print('Request diagnostics enabled (FLASK_DEBUG); no debugger or reloader.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\nRideWorks stopped.', flush=True)
