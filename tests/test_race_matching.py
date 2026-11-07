"""Synthetic-only tests for strict automatic race matching."""

from datetime import datetime, timedelta, timezone
import unittest

from rideworks.race_matching import batch_matches, stages, titles_agree


def row(**overrides):
    value = {'date': '2024-09-27', 'start_time': '09:10', 'event': 'Stage 3 - Electric Break',
             'race_group': '0-210', 'finish': 5, 'avg_watts': 177,
             'race_score': 192, 'race_score_change': 4}
    value.update(overrides)
    return value


def activity(identity='a', **overrides):
    value = {'activity_id': identity, 'start_time': '2024-09-27T16:14:00+00:00',
             'absolute_time': True, 'activity_type': 'Virtual Ride', 'subtype': None,
             'title': 'Zwift Race Stage 3 Electric Break', 'match_watts': 150,
             'match_watts_source': 'Synthetic'}
    value.update(overrides)
    return value


class BatchMatchingTests(unittest.TestCase):
    def test_stage_veto_and_fresh_match_after_correction(self):
        ride = activity(title='Zwift Race Stage 4 Electric Break')
        mismatch = batch_matches([row(event='Stage 1 - Electric Break')], 'America/Los_Angeles', [ride])
        self.assertIsNone(mismatch[0]['activity_id'])
        self.assertIn('stage conflicts', mismatch[0]['reason'])
        corrected = batch_matches([row(event='Stage 4 - Electric Break')], 'America/Los_Angeles', [ride])
        self.assertEqual(corrected[0]['activity_id'], 'a')

    def test_wrong_date_then_corrected_date(self):
        wrong = batch_matches([row(date='2024-09-29')], 'America/Los_Angeles', [activity()])
        self.assertIsNone(wrong[0]['activity_id'])
        self.assertEqual(batch_matches([row()], 'America/Los_Angeles', [activity()])[0]['activity_id'], 'a')

    def test_ambiguity_missing_timezone_dst_and_collision_block(self):
        activities = [activity(), activity('b')]
        self.assertIn('Multiple activities', batch_matches([row()], 'America/Los_Angeles', activities)[0]['reason'])
        self.assertIsNone(batch_matches([row()], None, activities)[0]['activity_id'])
        dst = row(date='2024-11-03', start_time='01:30')
        self.assertIn('ambiguous', batch_matches([dst], 'America/Los_Angeles', [activity()])[0]['reason'])
        collisions = batch_matches([row(), row()], 'America/Los_Angeles', [activity()])
        self.assertTrue(all(result['activity_id'] is None for result in collisions))
        self.assertTrue(all('same activity' in result['reason'] for result in collisions))

    def test_sponsor_only_and_unknown_or_nonvirtual_evidence_do_not_match(self):
        self.assertIsNone(batch_matches([row(event='Stage 3 Zwift Racing DURA ACE')],
                                        'America/Los_Angeles', [activity()])[0]['activity_id'])
        self.assertIsNone(batch_matches([row()], 'America/Los_Angeles',
                                        [activity(absolute_time=False)])[0]['activity_id'])
        self.assertIsNone(batch_matches([row()], 'America/Los_Angeles',
                                        [activity(activity_type='Ride', title='Electric Break')])[0]['activity_id'])

    def test_stage_spellings_and_absent_stage(self):
        self.assertEqual(stages('Stage IV and Stage Four'), {4})
        ride = activity(title='Zwift Electric Break')
        self.assertEqual(batch_matches([row()], 'America/Los_Angeles', [ride])[0]['activity_id'], 'a')

    def test_noncycling_and_single_shared_word_are_rejected(self):
        for kind in ('Virtual Run', 'Run', 'Walk', 'Rowing'):
            with self.subTest(kind=kind):
                result = batch_matches([row()], 'America/Los_Angeles', [activity(activity_type=kind)])[0]
                self.assertIsNone(result['activity_id'])
                self.assertEqual(result['issue'], 'type')
        result = batch_matches([row()], 'America/Los_Angeles',
                               [activity(title='Zwift Electric Coffee Social')])[0]
        self.assertIsNone(result['activity_id'])
        self.assertEqual(result['issue'], 'title')
        self.assertTrue(titles_agree('Stage 4 Ocean Lava Clif...', 'Zwift Stage IV Ocean Lava Cliffside Loop'))
        self.assertTrue(titles_agree('Stage 4 Croissant', 'Zwift Stage IV Croissant'))
        self.assertFalse(titles_agree('Stage 4 Croissant', 'Zwift Croissant Coffee Social'))
        typo = row(event='Stage 3 Amher Bridge')
        ride = activity(title='Zwift Stage 3 Amber Bridge')
        self.assertIsNone(batch_matches([typo], 'America/Los_Angeles', [ride])[0]['activity_id'])
        self.assertEqual(batch_matches([dict(typo, event='Stage 3 Amber Bridge')],
                                       'America/Los_Angeles', [ride])[0]['activity_id'], 'a')

    def test_missing_time_title_and_ocr_have_different_explanations(self):
        for race_row, rides, issue in (
                (row(), [], 'missing'),
                (row(), [activity(start_time='2024-09-27T18:00:00+00:00')], 'time'),
                (row(), [activity(title='Zwift Coffee Social')], 'title'),
                (row(avg_watts='unreadable'), [activity()], 'ocr')):
            result = batch_matches([race_row], 'America/Los_Angeles', rides)[0]
            self.assertEqual(result['issue'], issue)
        result = batch_matches([row()], 'America/Los_Angeles', [
            activity('far', start_time='2024-09-27T18:00:00+00:00'), activity('near')])[0]
        self.assertEqual(result['candidates'][0]['id'], 'near')
        self.assertIn('timestamp', batch_matches([row()], 'America/Los_Angeles',
                      [activity(absolute_time=False)])[0]['reason'])

    def test_ten_minute_window_is_unchanged(self):
        for minute, expected in ((20, 'a'), (21, None)):
            result = batch_matches([row()], 'America/Los_Angeles',
                                   [activity(start_time=f'2024-09-27T16:{minute}:00+00:00')])[0]
            self.assertEqual(result['activity_id'], expected)

    def test_seventeen_rows_one_unresolved(self):
        base = datetime(2024, 9, 1, 16, 10, tzinfo=timezone.utc)
        activities = []
        rows = []
        for index in range(17):
            stamp = base + timedelta(days=index)
            activities.append(activity(str(index), start_time=stamp.isoformat(),
                                       title=f'Zwift Race Stage 3 Electric Break {index}'))
            rows.append(row(date=stamp.date().isoformat()))
        rows[-1]['date'] = '2024-09-29'
        decisions = batch_matches(rows, 'America/Los_Angeles', activities)
        self.assertEqual(sum(bool(decision['activity_id']) for decision in decisions), 16)
        self.assertIsNone(decisions[-1]['activity_id'])


if __name__ == '__main__':
    unittest.main()
