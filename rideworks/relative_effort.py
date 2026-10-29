"""History-relative workout load and intensity labels; presentation only.

A ride is compared with scored cycling rides in the *previous* 42 calendar
days in RideWorks' approved athlete-history timezone. This never alters
Training State stress, FTP, the original observations or planning categories.
"""
from collections import deque
from datetime import date, timedelta
from html import escape
import math

from .training_state import FTP_CALENDAR, ride_results

WINDOW_DAYS = 42
MIN_COMPARISONS = 6
VERSION = 'relative-effort-v1'
LABELS = ('Very Light', 'Light', 'Moderate', 'High', 'Very High')
SLUGS = ('very-light', 'light', 'moderate', 'high', 'very-high')
REASONS = {
    'noncycling': 'Only cycling activities are classified.',
    'date_unknown': 'The ride date or timezone is not sufficiently established.',
    'stress_unavailable': 'A supported whole-workout training-stress estimate is unavailable.',
    'partial_only': 'Only partial training stress is available; a whole-workout category would be misleading.',
    'active_duration_unavailable': 'Supported active duration is unavailable for an intensity comparison.',
    'insufficient_history': 'Fewer than six comparable scored rides in the preceding 42 days.',
}


def _valid(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


def _duration(ride):
    """Use the exact duration basis of the selected stress, not elapsed time."""
    status = ride['selected']['status']
    if status in ('calculated', 'corrected_estimate'):
        intervals = ride['power'].get('intervals', ())
        if not intervals or any(not _valid(i.get('seconds')) for i in intervals):
            return None
        return math.fsum(i['seconds'] for i in intervals)
    if status == 'session_estimate':
        return ride['session_power'].get('duration_seconds')
    if status == 'hr_estimate':
        return ride['hr'].get('active_seconds')
    return None


def _rating_input(ride):
    if ride.get('timezone_unknown') or not ride.get('day'):
        return None, 'date_unknown'
    selected = ride['selected']
    if selected['status'] == 'partial':
        return None, 'partial_only'
    if selected['status'] not in ('calculated', 'corrected_estimate', 'session_estimate', 'hr_estimate'):
        return None, 'stress_unavailable'
    stress = selected.get('stress')
    if not _valid(stress):
        return None, 'stress_unavailable'
    seconds = _duration(ride)
    if not _valid(seconds) or seconds <= 0:
        return None, 'active_duration_unavailable'
    return dict(stress=stress, stress_per_hour=3600*stress/seconds,
                method=selected['method'], evidence_status=selected['status'],
                duration_seconds=seconds), None


def _percentile(value, previous):
    """Empirical midrank: equal results share the middle of their tied positions."""
    n = len(previous)
    return (sum(p < value for p in previous) +
            .5 * sum(p == value for p in previous))/n


def _band(percentile):
    if percentile < .2:
        return 0
    if percentile < .4:
        return 1
    if percentile < .6:
        return 2
    if percentile < .8:
        return 3
    return 4


def classify(rides):
    """One shared classification for all historical rides; same-day rides excluded.

    No future ride, later import date, or present-day FTP is used as the baseline.
    Ratings are recalculable when historical source/model evidence changes.
    """
    output = {}
    dated = []
    for ride in rides:
        activity_id = ride['activity_id']
        metrics, reason = _rating_input(ride)
        if reason:
            output[activity_id] = dict(status='unavailable', reason=reason, comparisons=0, version=VERSION)
        else:
            dated.append((date.fromisoformat(ride['day']), activity_id, metrics))
    dated.sort(key=lambda item: (item[0], item[1]))
    window = deque()
    cursor = 0
    while cursor < len(dated):
        day = dated[cursor][0]
        while window and window[0][0] < day - timedelta(days=WINDOW_DAYS):
            window.popleft()
        end = cursor
        while end < len(dated) and dated[end][0] == day:
            end += 1
        # Classify the whole calendar day *before* adding any of its rides.
        prior = [entry[2] for entry in window]
        for _, activity_id, item in dated[cursor:end]:
            n = len(prior)
            if n < MIN_COMPARISONS:
                output[activity_id] = dict(status='unavailable',
                    reason='insufficient_history', comparisons=n, version=VERSION)
                continue
            load_pct = _percentile(item['stress'], [e['stress'] for e in prior])
            intensity_pct = _percentile(item['stress_per_hour'], [e['stress_per_hour'] for e in prior])
            load, intensity = _band(load_pct), _band(intensity_pct)
            # Start with accumulated load. Very high intensity can raise the
            # overall rating only one band, avoiding double-counted intensity.
            overall = min(4, load + (1 if intensity - load >= 2 else 0))
            output[activity_id] = dict(
                status='available', category=LABELS[overall], slug=SLUGS[overall],
                load_category=LABELS[load], load_slug=SLUGS[load],
                intensity_category=LABELS[intensity], intensity_slug=SLUGS[intensity],
                load_percentile=load_pct, intensity_percentile=intensity_pct,
                comparisons=n, stress=item['stress'], stress_per_hour=item['stress_per_hour'],
                duration_seconds=item['duration_seconds'],
                method=item['method'], evidence_status=item['evidence_status'],
                version=VERSION)
        window.extend(dated[cursor:end])
        cursor = end
    return output


def for_store(store, *, cache_writes=None):
    """Build ratings once for the page, using existing versioned stress evidence."""
    # Use one fixed athlete-history calendar on both screens; browser timezone,
    # pagination and selected date filters must not change historical ratings.
    rides, _ = ride_results(store, FTP_CALENDAR, cache_writes=cache_writes)
    return classify(rides)


def chip(rating):
    if rating and rating.get('status') == 'available':
        label, slug = rating['category'], rating['slug']
        title = (f'Relative to {rating["comparisons"]} rides in the previous '
                 f'{WINDOW_DAYS} days · {rating["evidence_status"]}')
    else:
        label, slug = 'Not rated', 'unavailable'
        title = REASONS.get((rating or {}).get('reason'), REASONS['noncycling'])
    return (f'<span class="effort-pill effort-{slug}" title="{escape(title, quote=True)}">'
            f'{escape(label)}</span>')


def card(rating):
    """Short, quiet desktop sidebar card; details expand on demand."""
    if rating and rating.get('status') == 'available':
        label, slug = rating['category'], rating['slug']
        sub = f'Compared with {rating["comparisons"]} rides'
        parts = (
            ('Training load', rating['load_category'], rating['load_slug']),
            ('Intensity', rating['intensity_category'], rating['intensity_slug']))
        rows = ''.join(
            f'<div class="effort-component"><div class="effort-component-label">'
            f'<span>{name}</span><span class="effort-pill effort-{part_slug}">{escape(value)}</span></div>'
            f'<div class="effort-meter" aria-hidden="true">'
            f'<span class="effort-meter-fill effort-{part_slug}"></span></div></div>'
            for name, value, part_slug in parts)
        note = ('Training load is selected modeled stress; intensity is stress '
                'per supported active hour. Estimates depend on source quality.')
        evidence = (f'<p>Current ride: {rating["stress"]:.1f} modeled stress points '
                    f'over {rating["duration_seconds"]/3600:.2f} supported hours. '
                    f'Intensity: {rating["stress_per_hour"]:.1f} stress points/hour. '
                    f'Selected method: {escape(rating["method"])} '
                    f'({escape(rating["evidence_status"])}).</p>')
    else:
        label, slug = 'Not rated', 'unavailable'
        reason = (rating or {}).get('reason', 'noncycling')
        sub = REASONS.get(reason, REASONS['noncycling'])
        if reason == 'insufficient_history':
            sub = (f'Only {rating["comparisons"]} comparison rides; '
                   f'at least {MIN_COMPARISONS} are needed.')
        rows = ''
        note = 'A rating is shown only when comparable historical evidence is available.'
        evidence = ''
    explanation = (
        f'<p>{escape(note)}</p>{evidence}'
        f'<p>Categories use empirical percentile bands (20% each) from the '
        f'preceding 42 calendar days. Load sets the baseline rating; when '
        f'intensity is at least two bands higher, overall effort rises one '
        f'band. Ties use their midpoint. Same-day rides are excluded. '
        f'Incomplete or partial-only load is not treated as zero.</p>')
    return (f'<section class="panel relative-effort-card" aria-labelledby="relative-effort-title">'
            f'<div class="relative-effort-heading"><h2 id="relative-effort-title">Relative Effort</h2>'
            f'<span>Previous 42 days</span></div>'
            f'<div class="relative-effort-overall effort-{slug}">'
            f'<span class="relative-effort-accent" aria-hidden="true"></span>'
            f'<div><strong>{escape(label)}</strong><small>Overall effort</small></div></div>'
            f'<div class="relative-effort-components">{rows}</div>'
            f'<div class="relative-effort-footer"><span class="relative-effort-context">{escape(sub)}</span>'
            f'<details><summary>How this is rated</summary>{explanation}</details></div></section>')
