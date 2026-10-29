"""Home presentation contracts, with synthetic source values and fixed clocks."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import re
import tempfile
from unittest import TestCase
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from rideworks.dashboard import dashboard
from rideworks.home import fitness_chart, home_page, power_chart
from rideworks.performance_view import performance_view
from rideworks.store import Store
from rideworks.training_state import daily_series
from rideworks.training_state_page import training_home


def svg(html):
    return ET.fromstring(re.search(r'<svg\b.*?</svg>',html,re.S)[0])


def endpoint(chart):
    return chart.find("g[@class='home-chart-endpoint']")


def fitness(days, today='2026-10-28'):
    return dict(today=today, days=[dict(day=day,fitness=value) for day,value in days])


def point(identity, stamp, watts):
    return dict(activity_id=identity,start_time=stamp,date_key=stamp,absolute_time=True,
                average_watts=watts,rounded_watts=int(watts+.5),title='Synthetic effort')


def performance(points, as_of):
    # Use the accepted presentation service, rather than invent rolling events.
    view=performance_view(points,as_of=as_of)
    start=view['range_starts']['1yr']
    seed=next((s for s in reversed(view['rolling']) if s['at']<=start),None)
    steps=([dict(at=start,index=seed['index'])] if seed else [])+[s for s in view['rolling'] if s['at']>start]
    selected=lambda index: points[index] if index is not None else None
    return dict(range_start=start,range_end=view['as_of'],
                current=selected(view['summaries']['current']),latest=selected(view['summaries']['latest']),
                rolling=[dict(at=s['at'],point=selected(s['index'])) for s in steps])


class FitnessChartTests(TestCase):
    def test_six_calendar_months_exclude_cutoff_and_future_values(self):
        data=fitness([('2026-04-27',999),('2026-04-28',888),('2026-04-29',12.25),
                      ('2026-10-28',36.125),('2026-10-29',777)])
        before=deepcopy(data)
        chart=svg(fitness_chart(data))
        self.assertEqual(data,before)
        self.assertEqual(chart.get('data-range-start'),'2026-04-28')
        self.assertEqual(chart.get('data-range-end'),'2026-10-28')
        self.assertEqual([n.get('data-day') for n in chart.findall("circle[@data-day]")],['2026-04-29','2026-10-28'])
        self.assertLess(float(chart.get('data-y-min')),12.25)
        self.assertGreater(float(chart.get('data-y-max')),36.125)
        self.assertLess(float(chart.get('data-y-max')),40)
        last=endpoint(chart)
        self.assertEqual(last.get('data-value'),'36.125')
        self.assertEqual(last.find('text').text,'36.1')
        self.assertEqual(float(last.find('circle').get('cx')),570)

    def test_month_end_leap_year_cutoff(self):
        chart=svg(fitness_chart(fitness([('2024-02-29',888),('2024-03-01',3)],'2024-08-31')))
        self.assertEqual(chart.get('data-range-start'),'2024-02-29')
        self.assertEqual(len(chart.findall('circle[@data-day]')),1)

    def test_increasing_decreasing_flat_zero_and_short_series_have_finite_scale(self):
        for values in ([5,10,20],[20,10,5],[8,8,8],[0,0,0],[2]):
            with self.subTest(values=values):
                data=fitness([((date(2026,10,26)+timedelta(days=i)).isoformat(),v) for i,v in enumerate(values)])
                chart=svg(fitness_chart(data))
                self.assertLess(float(chart.get('data-y-min')),float(chart.get('data-y-max')))
                self.assertEqual(endpoint(chart).get('data-value'),str(values[-1]))
                self.assertNotRegex(ET.tostring(chart).decode(),r'(?i)nan|infinity')
                for node in chart.findall('circle[@data-day]'):
                    self.assertGreaterEqual(float(node.get('cy')),36)
                    self.assertLessEqual(float(node.get('cy')),156)

    def test_missing_days_and_values_break_paths_without_inventing_zero(self):
        chart=svg(fitness_chart(fitness([('2026-10-20',3),('2026-10-21',None),
                                       ('2026-10-22',5),('2026-10-27',4)])))
        self.assertEqual(len(chart.findall("path[@class='home-power-line']")),3)
        self.assertEqual(len(chart.findall('circle[@data-day]')),3)
        self.assertEqual(endpoint(chart).get('data-day'),'2026-10-27')
        self.assertIn('Latest available: 2026-10-27.',fitness_chart(fitness([('2026-10-27',4)])))

    def test_empty_all_missing_and_out_of_range_have_no_chart_or_zero(self):
        for days in ([],[('2026-10-28',None)],[('2026-01-01',42)]):
            html=fitness_chart(fitness(days))
            self.assertNotIn('<svg',html)
            self.assertIn('No usable Fitness history',html)

    def test_existing_daily_model_values_are_plotted_without_recalculation(self):
        rides=[dict(day='2026-01-01',activity_id='synthetic',selected=dict(stress=80,status='calculated'),power={})]
        days=daily_series(rides,'2026-10-28')
        chart=svg(fitness_chart(dict(days=days,today='2026-10-28')))
        nodes=chart.findall('circle[@data-day]')
        expected={d['day']:d['fitness'] for d in days if d['day']>'2026-04-28'}
        self.assertEqual({n.get('data-day'):float(n.get('data-value')) for n in nodes},expected)

    def test_training_card_uses_selected_zone_and_keeps_provenance_and_link(self):
        data=fitness([('2026-10-28',10.125)])
        data['days'][0]['early_history_provisional']=True
        with patch('rideworks.training_state_page.training_state',return_value=data) as service:
            html=training_home(object(),'Asia/Tokyo')
        service.assert_called_once()
        self.assertEqual(service.call_args.args[1],'Asia/Tokyo')
        self.assertIn('href="/training-state"',html)
        self.assertIn('Early history is provisional',html)
        self.assertIn('not measured physiology or readiness',html)
        self.assertNotIn('Fatigue',html)
        self.assertNotIn('Form',html)


class PerformanceChartTests(TestCase):
    def test_current_rolling_best_is_not_latest_ride_and_window_is_twelve_months(self):
        points=[point('old','2025-10-01T12:00:00+00:00',222),
                point('best','2026-10-10T12:00:00+00:00',208.4),
                point('latest','2026-10-27T12:00:00+00:00',137.2)]
        data=performance(points,datetime(2026,10,28,18,tzinfo=timezone.utc))
        chart=svg(power_chart(data,ZoneInfo('America/Los_Angeles')))
        self.assertEqual(data['current']['activity_id'],'best')
        self.assertEqual(data['latest']['activity_id'],'latest')
        self.assertEqual(chart.get('data-range-start'),'2025-10-28T18:00:00+00:00')
        self.assertEqual(chart.get('data-range-end'),'2026-10-28T18:00:00+00:00')
        self.assertEqual(endpoint(chart).get('data-value'),'208.4')
        self.assertEqual(endpoint(chart).find('text').text,'208 W')
        self.assertEqual(float(endpoint(chart).find('circle').get('cx')),570)
        self.assertIn('href="/activities/best"',power_chart(data,ZoneInfo('UTC')))

    def test_expiry_and_unknown_timezone_do_not_label_a_stale_effort_current(self):
        data=performance([point('expired','2026-09-16T18:00:00+00:00',210)],
                         datetime(2026,10,28,18,tzinfo=timezone.utc))
        html=power_chart(data,ZoneInfo('UTC'))
        self.assertIsNone(endpoint(svg(html)))
        self.assertIn('Current 42-day best unavailable',html)
        unknown=point('unknown','2026-10-28T12:00:00',300)|dict(absolute_time=False)
        html=power_chart(performance([unknown],datetime(2026,10,28,18,tzinfo=timezone.utc)),ZoneInfo('UTC'))
        self.assertNotIn('<svg',html)

    def test_missing_windows_break_rolling_curve(self):
        data=performance([point('a','2026-01-01T12:00:00+00:00',210),
                          point('b','2026-10-27T12:00:00+00:00',180)],
                         datetime(2026,10,28,18,tzinfo=timezone.utc))
        chart=svg(power_chart(data,ZoneInfo('UTC')))
        self.assertEqual(len(chart.findall("path[@class='home-power-line']")),2)
        self.assertEqual(endpoint(chart).find('text').text,'180 W')

    def test_leap_year_window_and_flat_or_absent_power(self):
        as_of=datetime(2024,2,29,18,tzinfo=timezone.utc)
        data=performance([point('a','2024-02-28T12:00:00+00:00',0)],as_of)
        chart=svg(power_chart(data,ZoneInfo('UTC')))
        self.assertEqual(chart.get('data-range-start'),'2023-02-28T18:00:00+00:00')
        self.assertEqual(endpoint(chart).find('text').text,'0 W')
        self.assertNotIn('<svg',power_chart(performance([],as_of),ZoneInfo('UTC')))

    def test_home_keeps_quick_facts_distinct_and_card_links(self):
        with tempfile.TemporaryDirectory() as root,Store(root) as store:
            data=dashboard(store,'UTC',as_of=datetime(2026,10,28,18,tzinfo=timezone.utc))
            data['performance']=performance([point('a','2026-10-10T12:00:00+00:00',208.4),
                                             point('b','2026-10-27T12:00:00+00:00',137.2)],
                                            datetime(2026,10,28,18,tzinfo=timezone.utc))|dict(recent=None)
            for p in (data['performance']['current'],data['performance']['latest']):
                p.update(date_text=None)
            with patch('rideworks.home.dashboard',return_value=data):
                html=home_page(store,'home_tz=UTC')
        for name,watts in (('current',208),('latest',137)):
            fact=re.search('id="home-'+name+'"(.*?)</div>',html,re.S)[1]
            self.assertIn(f'<strong>{watts} W</strong>',fact)
        self.assertIn('href="/performance">View Performance',html)
        self.assertIn('href="/training-state">View Training State',html)
        self.assertLess(html.index('class="panel home-training'),html.index('class="panel home-performance'))
