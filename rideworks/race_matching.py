"""Conservative, whole-batch matching of screenshot races to existing rides."""

from collections import Counter
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .race_results import activity_candidate, row_errors


GENERIC_WORDS = frozenset({
    'zwift', 'zracing', 'racing', 'race', 'races', 'ride', 'stage',
    'event', 'virtual', 'dura', 'ace',
})
STAGE_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
    'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10,
}
STAGE = re.compile(
    r'\bstage\s*[-:#.]?\s*(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|viii|vii|iii|vi|iv|ii|ix|x|v|i)\b',
    re.IGNORECASE,
)


def stages(title):
    found = set()
    for token in STAGE.findall(title):
        token = token.casefold()
        found.add(int(token) if token.isdecimal() else STAGE_WORDS[token])
    return found


def distinctive_words(title):
    title = STAGE.sub(' ', title)
    return {word for word in re.findall(r'[a-z0-9]+', title.casefold())
            if len(word) > 3 and not word.isdecimal() and word not in GENERIC_WORDS}


def unambiguous_time(stamp, zone):
    return stamp.replace(tzinfo=zone, fold=0).utcoffset() == stamp.replace(tzinfo=zone, fold=1).utcoffset()


def batch_matches(rows, timezone_name, activities):
    """Return one decision per row; no match is inferred from submitted IDs."""
    try:
        zone = ZoneInfo(timezone_name) if timezone_name else None
    except (ValueError, ZoneInfoNotFoundError):
        zone = None
    choices = [choice for activity in activities
               if (choice := activity_candidate(activity, zone)) is not None]
    decisions = []
    for row in rows:
        decision = {'activity_id': None, 'reason': '', 'candidates': []}
        decisions.append(decision)
        if not zone:
            decision['reason'] = 'A valid screenshot timezone is required.'
            continue
        if row_errors(row) or not all(row.get(key) for key in ('date', 'start_time', 'event')):
            decision['reason'] = 'A valid date, start time and event are required.'
            continue
        try:
            stamp = datetime.fromisoformat(f"{row['date']}T{row['start_time']}")
        except ValueError:
            decision['reason'] = 'The date or start time is invalid.'
            continue
        if not unambiguous_time(stamp, zone):
            decision['reason'] = 'The screenshot time is ambiguous or nonexistent in this timezone.'
            continue
        event_words = distinctive_words(row['event'])
        event_stages = stages(row['event'])
        if not event_words or len(event_stages) > 1:
            decision['reason'] = 'The event title does not provide distinctive, unambiguous evidence.'
            continue
        eligible = []
        stage_conflicts = False
        for choice in choices:
            if abs((date.fromisoformat(choice['date']) - stamp.date()).days) <= 2:
                decision['candidates'].append(choice)
            if choice['date'] != row['date']:
                continue
            if not choice['absolute'] or not choice['virtual']:
                continue
            activity_stamp = datetime.fromisoformat(f"{choice['date']}T{choice['time']}")
            if not unambiguous_time(activity_stamp, zone) or abs((activity_stamp - stamp).total_seconds()) > 600:
                continue
            if not event_words & distinctive_words(choice['title']):
                continue
            activity_stages = stages(choice['title'])
            if len(activity_stages) > 1 or (event_stages and activity_stages and event_stages != activity_stages):
                stage_conflicts = True
                continue
            eligible.append(choice['id'])
        if len(eligible) == 1:
            decision['activity_id'] = eligible[0]
            decision['reason'] = 'Matched automatically.'
        elif len(eligible) > 1:
            decision['reason'] = 'Multiple activities qualify for this race.'
        elif stage_conflicts:
            decision['reason'] = 'The event stage conflicts with a nearby activity.'
        else:
            decision['reason'] = 'No unambiguous activity matches the date, time and event.'
    counts = Counter(d['activity_id'] for d in decisions if d['activity_id'])
    for decision in decisions:
        if decision['activity_id'] and counts[decision['activity_id']] > 1:
            decision['activity_id'] = None
            decision['reason'] = 'Multiple race rows match the same activity.'
    return decisions
