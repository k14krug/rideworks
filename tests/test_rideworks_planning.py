"""Independent date-pattern, evidence honesty, persistence and HTTP checks."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import urlencode

from fit_fixture import make_fit
from rideworks.planning import (HARD, activity_context, classify_activity, confirm_intent,
    plan, project, set_classification, set_feedback, stimulus)
from rideworks.history import presentation
from rideworks.store import Store
from rideworks.training_state import ride_results
from rideworks.web import Application

NOW=datetime(2026,10,10,18,tzinfo=timezone.utc)
TODAY=NOW.date()


def actual(offset,category,identity='sample'):
    day=TODAY+timedelta(days=offset)
    return dict(activity_id=identity,day=day.isoformat(),start_time=day.isoformat()+'T12:00:00+00:00',
                classification=dict(category=category,hard=category in HARD,confidence='rider confirmed'))


class RotationTests(TestCase):
    def check(self,data,history=()):
        days=data['days'];hard=[r for r in days if r['hard']]
        self.assertEqual(len(hard),3)
        self.assertEqual([r['hard_number'] for r in hard],[1,2,3])
        self.assertTrue(days[-1]['hard']);self.assertEqual(days[0]['day'],TODAY.isoformat())
        self.assertEqual([r['day'] for r in days],[(TODAY+timedelta(days=i)).isoformat() for i in range(len(days))])
        actual_dates={r['day'] for r in history if r['classification']['hard']}
        for r in hard:
            end=date.fromisoformat(r['day']);begin=end-timedelta(days=6)
            contributing=actual_dates|{h['day'] for h in hard if h['day']<=r['day']}
            count=sum(begin.isoformat()<=d<=end.isoformat() for d in contributing)
            if r['frequency_exception']:
                self.assertEqual(r,data['next_ride']);self.assertGreaterEqual(count,3)
                self.assertIn('above the usual two',r['reason'])
            else:self.assertLessEqual(count,2)
        self.assertTrue(all(r['category'] in ('Race','Threshold','VO2','Easy','Recovery','Z2 endurance') for r in days))

    def test_starting_on_quality_day_exact_hard_offsets_and_unfixed_horizon(self):
        data=project([],TODAY)
        self.check(data)
        self.assertEqual([(r['offset'],r['category']) for r in data['days'] if r['hard']],[(0,'Threshold'),(3,'Race'),(7,'VO2')])
        self.assertEqual(len(data['days']),8)

    def test_race_yesterday_recovery_low_z2_and_no_mandatory_third_recovery(self):
        history=[actual(-1,'Race')];data=project(history,TODAY);self.check(data,history)
        self.assertEqual([r['category'] for r in data['days'][:3]],['Recovery','Easy','Threshold'])
        self.assertEqual(data['days'][0]['power'],'~90–100 W')
        self.assertEqual((data['days'][1]['duration'],data['days'][1]['power']),('45–75 min','~105–120 W'))

    def test_vo2_and_threshold_second_dates_differ(self):
        for kind,power in [('VO2','~100–110 W'),('Threshold','~105–120 W')]:
            history=[actual(-1,kind)];data=project(history,TODAY);self.check(data,history)
            self.assertEqual(data['days'][1]['power'],power)
            self.assertEqual(data['days'][2]['category'],'Race')

    def test_completed_hard_today_is_actual_context_not_upcoming_one(self):
        history=[actual(0,'Race')];data=project(history,TODAY);self.check(data,history)
        self.assertFalse(data['days'][0]['hard']);self.assertEqual(len(data['today_actual']),1)
        self.assertEqual([r['offset'] for r in data['days'] if r['hard']],[3,7,10])
        self.assertEqual(len(data['days']),11)

    def test_completed_easy_today_avoids_second_hard_and_three_are_future(self):
        history=[actual(0,'Easy')];data=project(history,TODAY);self.check(data,history)
        self.assertFalse(data['days'][0]['hard']);self.assertEqual(data['days'][1]['category'],'Threshold')

    def test_two_hard_dates_in_week_and_actual_excess_are_respected(self):
        for offsets in [(-5,-2),(-5,-3,-1)]:
            history=[actual(n,'Race',str(n)) for n in offsets]
            data=project(history,TODAY);self.check(data,history)
            first=next(r for r in data['days'] if r['hard'])
            self.assertGreaterEqual(first['offset'],2)

    def test_skipped_past_quality_recomputed_without_phantom_hard(self):
        history=[actual(-4,'Race')]
        yesterday=project(history,TODAY-timedelta(days=1))
        self.assertTrue(yesterday['days'][0]['hard'])
        today=project(history,TODAY);self.check(today,history)
        self.assertTrue(today['days'][0]['hard']);self.assertEqual(today['latest_hard'],history[0])

    def test_unplanned_race_resets_recovery_and_structured_rotation(self):
        history=[actual(-4,'Threshold')]
        before=project(history,TODAY)
        after=project(history+[actual(-1,'Race','unexpected')],TODAY)
        self.assertEqual(before['days'][0]['category'],'Race')
        self.assertEqual(after['days'][0]['category'],'Recovery')
        self.assertEqual(next(r['category'] for r in after['days'] if r['hard']),'VO2')
        self.check(after,history+[actual(-1,'Race','unexpected')])

    def test_heavy_legs_today_only_and_no_asserted_normal_legs(self):
        data=project([],TODAY,legs='heavy');self.check(data)
        self.assertEqual(data['days'][0]['category'],'Recovery')
        self.assertFalse(data['days'][0]['hard']);self.assertTrue(data['days'][1]['hard'])
        second=project([actual(-2,'Race')],TODAY,legs='heavy')
        self.assertEqual(second['days'][0]['power'],'~90–100 W')
        unknown=project([],TODAY);self.assertIn('if legs feel normal',unknown['days'][0]['reason'])

    def test_stale_and_uncertain_are_provisional_with_complete_conditional_horizon(self):
        for kwargs in [dict(fresh=False),dict(unknown_dates=1)]:
            data=project([],TODAY,**kwargs);self.check(data)
            self.assertTrue(data['provisional']);self.assertEqual(data['days'][0]['category'],'Easy')
        data=project([actual(-1,'Uncertain')],TODAY)
        self.assertTrue(data['provisional']);self.assertIn('uncertain',data['days'][0]['reason'])

    def test_defensive_failure_and_determinism(self):
        with self.assertRaises(ValueError):project([],TODAY,limit=3)
        self.assertEqual(project([actual(-2,'Race')],TODAY),project([actual(-2,'Race')],TODAY))

    def test_owner_before_ride_third_in_seven_is_conditional_exception(self):
        history=[actual(-6,'Race','race'),actual(-3,'VO2','intervals')]
        data=project(history,TODAY);self.check(data,history)
        self.assertEqual(data['next_ride']['category'],'Race')
        self.assertEqual(data['next_ride']['day'],TODAY.isoformat())
        self.assertTrue(data['next_ride']['frequency_exception'])
        self.assertEqual(data['next_ride']['hard_dates_in_window'],3)
        self.assertFalse(any(r['frequency_exception'] for r in data['days'][1:]))
        self.assertIn('supported recovery',data['next_ride']['reason'])
        heavy=project(history,TODAY,legs='heavy');self.assertEqual(heavy['next_ride']['category'],'Recovery')
        stale=project(history,TODAY,fresh=False);self.assertEqual(stale['next_ride']['category'],'Easy')

    def test_unknown_old_race_is_context_and_not_a_new_recovery_timer(self):
        history=[actual(-6,'Uncertain','race'),actual(-3,'VO2','intervals')]
        history[0]['classification']['title_hint']='Race'
        data=project(history,TODAY)
        self.assertTrue(data['next_ride']['hard']);self.assertTrue(data['provisional'])
        self.assertEqual(len(data['recent_uncertain']),1)
        history.append(actual(-1,'Uncertain','unknown-recent'))
        self.assertEqual(project(history,TODAY)['next_ride']['category'],'Easy')

    def test_owner_post_ride_next_advances_and_today_stays_completed_context(self):
        history=[actual(-6,'Race','race'),actual(-3,'VO2','intervals'),actual(0,'Recovery','completed')]
        data=project(history,TODAY);self.check(data,history)
        self.assertEqual(data['next_ride']['day'],(TODAY+timedelta(days=1)).isoformat())
        self.assertEqual(data['next_ride']['category'],'Race')
        self.assertEqual(len(data['today_actual']),1)
        self.assertEqual(len([r for r in data['days'] if r['hard']]),3)
        heavy=project(history,TODAY,legs='heavy')
        self.assertEqual(heavy['next_ride']['category'],'Recovery')
        self.assertGreater(next(r['offset'] for r in heavy['days'] if r['hard']),1)

    def test_frequency_exception_requires_classified_recovery_on_completed_today(self):
        history=[actual(-5,'Race','race'),actual(-2,'VO2','intervals')]
        uncertain=project(history+[actual(0,'Uncertain','today')],TODAY)
        self.assertFalse(uncertain['next_ride']['frequency_exception'])
        easy=project(history+[actual(0,'Recovery','today')],TODAY)
        self.assertTrue(easy['next_ride']['frequency_exception'])

    def test_third_date_exception_does_not_escalate_actual_excess_to_fourth(self):
        history=[actual(-6,'Race','a'),actual(-4,'Threshold','b'),actual(-3,'VO2','c')]
        data=project(history,TODAY)
        self.assertEqual(data['next_ride']['category'],'Z2 endurance')
        self.assertFalse(data['next_ride']['frequency_exception'])


class ClassificationTests(TestCase):
    def test_repeated_observed_bouts_vs_sustained_and_easy(self):
        powers=[100]*600+([240]*30+[90]*15)*13+[100]*600
        result=stimulus(list(range(len(powers))),powers,200)
        self.assertEqual((result['category'],result['short_bouts']),('VO2',13))
        self.assertEqual(stimulus(list(range(1200)),[185]*1200,200)['category'],'Threshold')
        for watts,kind in [(95,'Recovery'),(105,'Easy'),(120,'Z2 endurance')]:
            self.assertEqual(stimulus(list(range(1200)),[watts]*1200,200)['category'],kind)

    def test_gaps_nulls_duplicate_timestamps_and_short_efforts_do_not_bridge(self):
        self.assertEqual(stimulus(list(range(400))+list(range(401,800)),[200]*799,200)['category'],'Uncertain')
        powers=[200]*1200;powers[400]=None;powers[800]=None
        self.assertEqual(stimulus(list(range(1200)),powers,200)['category'],'Uncertain')
        self.assertEqual(stimulus([1]*1200,[200]*1200,200)['category'],'Uncertain')
        self.assertEqual(stimulus(list(range(600)),[200]*600,None)['category'],'Uncertain')
        powers=([240]*15+[90]*45)*10
        self.assertNotEqual(stimulus(list(range(600)),powers,200)['category'],'VO2')


class StorePlanningTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=Store(self.root/'store')
        self.source=self.root/'sample.fit';self.source.write_bytes(make_fit(powers=[120]*1200,heart_rates=[120]*1200,timestamps=[1100000000+i for i in range(1200)],elapsed=1200,timer=1200,session_timestamp=1100001200,event_timestamps=(1100000000,1100001200)))
        self.imported=self.store.import_fit(self.source)
        self.identity=self.imported['activity_id']
        self.snapshot=self.store.activity_history(self.identity)[0]
    def tearDown(self):
        self.store.close();self.temp.cleanup()
    def sync(self,when=NOW):
        self.store.connection.execute('INSERT OR REPLACE INTO strava_sync_state VALUES(1,?,?)',('synthetic',int(when.timestamp())))
    def state(self):return plan(self.store,'UTC',as_of=NOW)

    def test_fresh_sync_assumed_prior_rest_today_unfinished_and_no_source_change(self):
        before=list(self.store.connection.iterdump());self.sync()
        data=self.state()
        self.assertTrue(data['fresh']);self.assertEqual(len(data['recent_days']),6)
        self.assertTrue(all('assumed rest' in d['state'] for d in data['recent_days']))
        self.assertEqual(data['days'][0]['status'],'recommendation')
        self.assertFalse(data['today_actual'])
        self.store.connection.execute('DELETE FROM strava_sync_state')
        stale=self.state();self.assertFalse(stale['fresh'])
        self.assertTrue(all('does not establish rest' in d['state'] for d in stale['recent_days']))
        self.assertEqual(self.store.activity_history(self.identity),[self.snapshot])
        self.assertEqual(self.source.read_bytes(),make_fit(powers=[120]*1200,heart_rates=[120]*1200,timestamps=[1100000000+i for i in range(1200)],elapsed=1200,timer=1200,session_timestamp=1100001200,event_timestamps=(1100000000,1100001200)))

    def test_old_sync_only_supports_completed_dates_before_checkpoint(self):
        self.sync(NOW-timedelta(days=2));data=self.state()
        self.assertFalse(data['fresh'])
        self.assertIn('assumed rest',data['recent_days'][0]['state'])
        self.assertIn('does not establish rest',data['recent_days'][-1]['state'])

    def test_midnight_date_boundaries_and_timezone_heavy_feedback(self):
        when=datetime(2026,1,1,1,tzinfo=timezone.utc)
        set_feedback(self.store,'America/Los_Angeles','heavy',as_of=when)
        west=plan(self.store,'America/Los_Angeles',as_of=when)
        east=plan(self.store,'Asia/Tokyo',as_of=when)
        self.assertEqual(west['today'],'2025-12-31');self.assertEqual(east['today'],'2026-01-01')
        self.assertEqual(west['legs'],'heavy');self.assertEqual(east['legs'],'unknown')
        next_day=plan(self.store,'America/Los_Angeles',as_of=when+timedelta(days=1))
        self.assertEqual(next_day['legs'],'unknown')
        with self.assertRaises(ValueError):plan(self.store,'UTC',as_of=datetime(2026,1,1))

    def test_manual_correction_separate_and_reset_reverts_to_evidence(self):
        rides,_=ride_results(self.store,'UTC',as_of=NOW);r=rides[0];row=presentation(self.snapshot)
        inferred=classify_activity(self.store,self.snapshot,row,r)
        set_classification(self.store,self.identity,'Race',as_of=NOW)
        corrected=classify_activity(self.store,self.snapshot,row,r)
        self.assertEqual((corrected['category'],corrected['confidence']),('Race','rider confirmed'))
        set_classification(self.store,self.identity,'automatic')
        self.assertEqual(classify_activity(self.store,self.snapshot,row,r),inferred)
        self.assertEqual(self.store.activity_history(self.identity)[0],self.snapshot)
        for bad in ('Rest','VO2max','',None):
            with self.assertRaises(ValueError):set_classification(self.store,self.identity,bad)

    def test_title_alone_never_proves_race_vo2_or_hr_hardness(self):
        rides,_=ride_results(self.store,'UTC',as_of=NOW);r=rides[0]
        for title in ('Race championship','VO2 max 30/15','Threshold workout'):
            row=presentation(self.snapshot)|dict(title=title)
            unavailable=r|dict(power=dict(observed_seconds=0),selected=dict(stress=400))
            outcome=classify_activity(self.store,self.snapshot,row,unavailable)
            self.assertFalse(outcome['hard']);self.assertEqual(outcome['category'],'Uncertain')

    def test_retained_explicit_ride_race_metadata_is_source_reported(self):
        from rideworks.strava_api import apply_observations, normalize
        item=normalize(dict(id=999,name='Synthetic source category',type='Ride',sport_type='VirtualRide',
                            start_date='2026-10-09T12:00:00Z',elapsed_time=2400,moving_time=2400,workout_type=11))
        apply_observations(self.store,[item],42,int(NOW.timestamp()))
        identity=self.store.connection.execute("SELECT activity_id FROM strava_api_activities WHERE external_id='999'").fetchone()[0]
        c=activity_context(self.store,identity,as_of=NOW)['classification']
        self.assertEqual((c['category'],c['confidence'],c['hard']),('Race','source reported',True))
        self.assertIsNotNone(c['race_metadata_source'])
        set_classification(self.store,identity,'Easy')
        self.assertEqual(activity_context(self.store,identity,as_of=NOW)['classification']['category'],'Easy')

    def test_noncycling_activity_does_not_gain_cycling_intent_or_category(self):
        self.store.connection.execute("UPDATE sessions SET sport='running',sub_sport=NULL")
        context=activity_context(self.store,self.identity,as_of=NOW)
        self.assertFalse(context['cycling']);self.assertIsNone(context['intent'])
        with self.assertRaises(ValueError):set_classification(self.store,self.identity,'Race')

    def test_intent_snapshot_before_ride_only_and_not_implicit(self):
        self.assertIsNone(activity_context(self.store,self.identity,as_of=NOW)['intent'])
        data=self.state();confirm_intent(self.store,'UTC',as_of=NOW,expected_day=data['today'],expected_category=data['days'][0]['category'])
        intent=self.store.connection.execute('SELECT * FROM planning_intents').fetchone()
        snapshot=json.loads(intent['recommendation_json']);self.assertEqual(snapshot['version'],'rolling-advisor-v2')
        self.assertIsNone(activity_context(self.store,self.identity,as_of=NOW)['intent'])
        with self.assertRaises(ValueError):confirm_intent(self.store,'UTC',as_of=NOW,expected_day='2026-10-09',expected_category='Race')
        # Deliberate synthetic future ride on the same local date after confirmation.
        self.store.connection.execute('UPDATE sessions SET start_time=?',((NOW+timedelta(minutes=5)).isoformat(),))
        context=activity_context(self.store,self.identity,as_of=NOW+timedelta(hours=1))
        self.assertIsNotNone(context['intent'])
        with self.assertRaises(ValueError):confirm_intent(self.store,'UTC',as_of=NOW+timedelta(hours=1),expected_day=data['today'],expected_category='Easy')

    def test_persistence_and_atomic_migration(self):
        set_feedback(self.store,'UTC','heavy',as_of=NOW);set_classification(self.store,self.identity,'Race')
        with Store(self.store.data_dir) as reopened:
            self.assertEqual(reopened.connection.execute('PRAGMA user_version').fetchone()[0],11)
            self.assertEqual(plan(reopened,'UTC',as_of=NOW)['legs'],'heavy')
        import rideworks.store as module
        root=self.root/'broken';root.mkdir()
        db=sqlite3.connect(root/'rideworks.sqlite3');db.executescript(module.SCHEMA)
        for migration in range(2,9):db.executescript(getattr(module,f'MIGRATION_{migration}'))
        db.close()
        with patch.object(module,'MIGRATION_9',module.MIGRATION_9.replace('PRAGMA user_version = 9;','INSERT INTO nonexistent VALUES(1);')):
            with self.assertRaises(sqlite3.OperationalError):Store(root)
        db=sqlite3.connect(root/'rideworks.sqlite3')
        self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],8)
        self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='planning_feedback'").fetchone());db.close()

    def test_http_home_plan_parity_and_safe_actions(self):
        app=Application(self.store.data_dir)
        with patch('rideworks.dashboard.datetime') as clock,patch('rideworks.planning.datetime') as planner_clock:
            clock.now.return_value=NOW;clock.fromisoformat.side_effect=datetime.fromisoformat
            clock.fromtimestamp.side_effect=datetime.fromtimestamp
            planner_clock.now.return_value=NOW;planner_clock.fromisoformat.side_effect=datetime.fromisoformat
            planner_clock.fromtimestamp.side_effect=datetime.fromtimestamp
            home=app.get('/?home_tz=UTC')[2].decode();page=app.get('/plan?plan_tz=UTC')[2].decode()
        import re
        for cls in ('recommended-type','recommended-target','recommended-reason'):
            pattern=r'class="'+cls+r'">(.*?)</'
            self.assertEqual(re.search(pattern,home).group(1),re.search(pattern,page).group(1))
        self.assertIn('href="/plan"',home);self.assertIn('Hard day #3',page)
        self.assertIn('No recorded intent',app.get('/activities/'+self.identity)[2].decode())
        body=urlencode(dict(nonce=app.settings.nonce,tz='UTC',day=datetime.now(timezone.utc).date().isoformat(),legs='heavy')).encode()
        self.assertEqual(app.post('/plan/feedback',body,'https://attacker.invalid')[0],403)
        self.assertEqual(app.post('/plan/feedback',body,'http://127.0.0.1:8765')[0],303)
        self.assertEqual(app.post('/plan/feedback',body+b'&legs=normal','http://127.0.0.1:8765')[0],400)
        bad=body.replace(b'heavy',b'Rest');self.assertEqual(app.post('/plan/feedback',bad,'http://127.0.0.1:8765')[0],400)
        self.assertEqual(app.get('/static/planning.js')[0],200)

    def test_revisit_after_new_sync_advances_home_plan_and_current_review(self):
        from rideworks.strava_api import apply_observations,normalize
        app=Application(self.store.data_dir);self.sync()
        self.store.connection.execute("UPDATE strava_sync_state SET athlete_id='42'")
        with patch('rideworks.dashboard.datetime') as clock,patch('rideworks.planning.datetime') as planner_clock:
            clock.now.return_value=NOW;clock.fromisoformat.side_effect=datetime.fromisoformat
            clock.fromtimestamp.side_effect=datetime.fromtimestamp
            planner_clock.now.return_value=NOW;planner_clock.fromisoformat.side_effect=datetime.fromisoformat
            planner_clock.fromtimestamp.side_effect=datetime.fromtimestamp
            before=app.get('/?home_tz=UTC')[2].decode()
            self.assertIn('data-next-day="2026-10-10"',before)
            self.assertNotIn('Completed today',before)
            item=normalize(dict(id=1000,name='Synthetic recovery',type='Ride',sport_type='VirtualRide',
                start_date='2026-10-10T17:00:00Z',moving_time=2400,elapsed_time=2400,average_watts=94))
            apply_observations(self.store,[item],42,int(NOW.timestamp()))
            identity=self.store.connection.execute("SELECT activity_id FROM strava_api_activities WHERE external_id='1000'").fetchone()[0]
            set_classification(self.store,identity,'Recovery',as_of=NOW)
            home=app.get('/?home_tz=UTC')[2].decode()
            page=app.get('/plan?plan_tz=UTC')[2].decode()
            review=app.get('/activities/'+identity+'?plan_tz=UTC')[2].decode()
            for html in (home,page,review):self.assertIn('data-next-day="2026-10-11"',html)
            self.assertNotIn('Completed today',home);self.assertNotIn('Review completed ride',home)
            self.assertIn('Today’s completed activity',page)
            self.assertIn('/activities/'+identity,page)
            self.assertIn('No recorded intent',review)
            self.assertIn('activity-plan-context',review)
            self.assertIn('Detailed RideWorks review unavailable',review)
            self.assertLess(review.index('id="power-curve-panel"'),review.index('activity-plan-context'))
            self.assertLess(review.index('activity-plan-context'),review.index('id="bests"'))
            historic=app.get('/activities/'+self.identity+'?plan_tz=UTC')[2].decode()
            self.assertIn('Current next ride',historic)
