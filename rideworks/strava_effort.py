"""Presentation of current Strava Relative Effort evidence, independent of models."""
import json
import math
from html import escape


def score(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    band = (0 if value < 20 else 1 if value < 40 else 2 if value < 70
            else 3 if value < 110 else 4)
    labels = ('Very Light', 'Light', 'Moderate', 'High', 'Very High')
    slugs = ('very-light', 'light', 'moderate', 'high', 'very-high')
    text = str(value)
    if text.endswith('.0'):
        text = text[:-2]
    return dict(value=text, category=labels[band], slug=slugs[band])


def for_store(store):
    """Use only each activity's current associated API observation."""
    result = {}
    ambiguous = set()
    for row in store.connection.execute('''
        SELECT a.activity_id, s.evidence_json FROM strava_api_activities a
        JOIN strava_api_sources s ON s.source_id=a.current_source_id
        AND s.activity_id=a.activity_id AND s.external_id=a.external_id
    '''):
        identity = row['activity_id']
        if identity in result:
            ambiguous.add(identity)
        else:
            result[identity] = score(json.loads(row['evidence_json']).get('suffer_score'))
    for identity in ambiguous:
        result[identity] = None
    return result


def description(rating):
    return (f'Strava Relative Effort: {rating["value"]}, {rating["category"]}' if rating
            else 'Strava Relative Effort unavailable')


def chip(rating):
    slug = rating['slug'] if rating else 'unavailable'
    value = escape(rating['value']) if rating else '—'
    label = escape(description(rating), quote=True)
    return f'<span class="effort-score effort-{slug}" title="{label}" aria-label="{label}">{value}</span>'


def card(rating):
    label = escape(rating['category']) if rating else 'Unavailable'
    return (f'<section class="panel relative-effort-card"><div class="relative-effort-heading">'
            f'<h2>Relative Effort</h2><span>Strava</span></div>'
            f'<div class="relative-effort-overall">{chip(rating)}<span>{label}</span></div>'
            f'<p class="relative-effort-context">Strava activity score</p></section>')
