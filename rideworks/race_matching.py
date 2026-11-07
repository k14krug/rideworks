"""Conservative, whole-batch matching of screenshot races to existing rides."""

from collections import Counter
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .race_results import activity_candidate, row_errors


MATCHING_VERSION = 'race-automatic-v2'
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


def titles_agree(event, title):
    """Require the visible event wording, rather than a single shared word.

    A one-word event must have the same distinctive title, while a longer
    event may be contained in a source title with additional route wording.
    Only an explicitly ellipsized final word may match a word prefix.
    """
    event_words, title_words = distinctive_words(event), distinctive_words(title)
    if not event_words or not title_words:
        return False
    missing = event_words - title_words
    if missing and event.rstrip().endswith(('...', '…')):
        tokens = re.findall(r'[a-z0-9]+', event.casefold())
        if tokens and missing == {tokens[-1]} and len(tokens[-1]) >= 4:
            missing = set() if any(word.startswith(tokens[-1]) for word in title_words) else missing
    if missing:
        return False
    return len(event_words) > 1 or event_words == title_words


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
        decision = {'activity_id': None, 'reason': '', 'candidates': [], 'issue': None}
        decisions.append(decision)
        if not zone:
            decision.update(issue='timezone', reason='Set the screenshot timezone to compare activity start times.')
            continue
        errors = row_errors(row)
        if errors or not all(row.get(key) for key in ('date', 'start_time', 'event')):
            decision.update(issue='ocr', reason=' '.join(errors) or 'Check the date, start time and event against the screenshot.')
            continue
        stamp = datetime.fromisoformat(f"{row['date']}T{row['start_time']}")
        if not unambiguous_time(stamp, zone):
            decision.update(issue='timezone', reason='The screenshot time is ambiguous or nonexistent in this timezone.')
            continue
        event_words, event_stages = distinctive_words(row['event']), stages(row['event'])
        if not event_words or len(event_stages) > 1:
            decision.update(issue='ocr', reason='The event title does not provide distinctive, unambiguous evidence.')
            continue
        eligible = []
        rejected = Counter()
        for choice in choices:
            day_delta = (date.fromisoformat(choice['date']) - stamp.date()).days
            activity_stamp = datetime.fromisoformat(f"{choice['date']}T{choice['time']}")
            delta = (activity_stamp - stamp).total_seconds()
            if day_delta:
                issue, reason = 'date', 'Different calendar date; diagnostic only.'
            elif not choice['absolute']:
                issue, reason = 'timezone', 'Activity timestamp has no known UTC offset.'
            elif not choice['virtual']:
                issue, reason = 'type', 'Activity is not a virtual cycling ride.'
            elif not unambiguous_time(activity_stamp, zone) or abs(delta) > 600:
                issue, reason = 'time', 'Start time is outside the ten-minute window or ambiguous.'
            elif (len(stages(choice['title'])) > 1 or
                  (event_stages and stages(choice['title']) and event_stages != stages(choice['title']))):
                issue, reason = 'stage', 'The event stage conflicts with this activity.'
            elif not titles_agree(row['event'], choice['title']):
                issue, reason = 'title', 'The activity title does not identify the visible event.'
            else:
                issue, reason = None, 'Matches date, time, cycling type and event.'
                eligible.append(choice['id'])
            if not day_delta:
                rejected[issue] += 1
            if abs(day_delta) <= 2:
                decision['candidates'].append({**choice, 'reason': reason, 'time_delta_seconds': delta})
        decision['candidates'].sort(key=lambda c: (
            c['date'] != row['date'], abs(c['time_delta_seconds']), c['id']))
        if len(eligible) == 1:
            decision.update(activity_id=eligible[0], reason='Matched automatically.')
        elif len(eligible) > 1:
            decision.update(issue='ambiguous', reason='Multiple activities qualify for this race; automatic matching is ambiguous.')
        elif not rejected:
            decision.update(issue='missing', reason='No activity was found on this date. Check the screenshot date and sync coverage.')
        else:
            issue = next(key for key in ('title', 'stage', 'time', 'type', 'timezone') if rejected[key])
            reasons = {
                'title': 'Nearby cycling activities have different event titles. Compare the screenshot and activity source titles.',
                'stage': 'The event stage conflicts with a nearby activity.',
                'time': 'No cycling activity starts within ten minutes. Check the screenshot time, timezone and activity source timestamp.',
                'type': 'Activities on this date are not eligible virtual cycling rides.',
                'timezone': 'Activity timestamps on this date have unknown offsets; automatic matching is unavailable.',
            }
            decision.update(issue=issue, reason=reasons[issue])
    counts = Counter(d['activity_id'] for d in decisions if d['activity_id'])
    for decision in decisions:
        if decision['activity_id'] and counts[decision['activity_id']] > 1:
            decision.update(activity_id=None, issue='collision', reason='Multiple race rows match the same activity.')
    return decisions
