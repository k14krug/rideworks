"""Source-mode layout and retained-evidence contracts for AR-UI-01."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import unittest

from fit_fixture import make_fit
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize
from rideworks.web import Application


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = []; self.anchors = []; self.open_details = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag == 'a' and attrs.get('href', '').startswith('#'): self.anchors.append(attrs['href'][1:])
        if tag == 'details' and 'open' in attrs: self.open_details.append(attrs)


class ActivityReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.store = Store(self.root/'store')
        self.addCleanup(self.store.close); self.app = Application(self.root/'store')

    def page(self, identity):
        status, kind, body = self.app.get('/activities/'+identity+'?plan_tz=UTC&curve_tz=UTC')
        self.assertEqual((status,kind),(200,'text/html'))
        return body.decode()

    def native(self, *, missing=False):
        path = self.root/'synthetic.fit'
        path.write_bytes(make_fit(powers=(None,None,None) if missing else (0,None,180),
                                 heart_rates=(None,None,None) if missing else (100,None,110),
                                 distance=1609.344, avg_power=None if missing else 120))
        return self.store.import_fit(path)['activity_id']

    def test_rich_structure_keeps_evidence_and_unique_navigable_ids(self):
        identity = self.native(); html = self.page(identity)
        structure = Structure(); structure.feed(html)
        self.assertEqual(len(structure.ids),len(set(structure.ids)))
        self.assertTrue(set(structure.anchors).issubset(structure.ids))
        self.assertLess(html.index('id="ride-chart-section"'),html.index('id="power-curve-panel"'))
        self.assertLess(html.index('id="power-curve-panel"'),html.index('id="bests"'))
        self.assertLess(html.index('id="bests"'),html.index('id="sources"'))
        self.assertLess(html.index('id="sources"'),html.index('<summary>Calculation details'))
        self.assertIn('FIT session source evidence',html)
        self.assertIn('1.00 mi',html); self.assertIn('120 W',html)
        self.assertIn('action="/plan/classification"',html)
        self.assertIn('name="back" value="activity"',html)
        self.assertIn('Current next ride',html)
        self.assertEqual(structure.open_details,[])

    def test_native_missing_and_zero_samples_survive_layout(self):
        html = self.page(self.native())
        data = json.loads(re.search(r'id="native-records" type="application/json">(.*?)</script>',html,re.S)[1])
        self.assertEqual([r['power'] for r in data],[0,None,180])
        self.assertEqual([r['heart_rate'] for r in data],[100,None,110])
        self.assertIn('id="toggle-power" type="checkbox" checked',html)
        self.assertIn('id="toggle-hr" type="checkbox" checked',html)

    def test_metadata_api_summary_is_supplied_without_fake_chart(self):
        apply_observations(self.store,[normalize(dict(id=77,name='Synthetic metadata',type='Ride',sport_type='VirtualRide',
            start_date='2026-10-01T12:00:00Z',distance=1609.344,elapsed_time=1200,average_watts=123))],42,1790000000)
        identity = self.store.connection.execute('SELECT activity_id FROM strava_api_activities').fetchone()[0]
        html = self.page(identity)
        self.assertIn('Strava API summary evidence · supplied averages',html)
        self.assertIn('123 W',html); self.assertIn('1.00 mi',html)
        self.assertIn('Detailed RideWorks review unavailable',html)
        self.assertNotIn('id="native-records"',html); self.assertNotIn('id="api-stream-samples"',html)
        self.assertIn('No supported best-20 result',html)
        self.assertIn('<summary>Strava API metadata',html)

    def test_ambiguous_native_sources_do_not_create_a_canonical_summary(self):
        identity = self.native()
        path = self.root/'other.fit'; path.write_bytes(make_fit(powers=(200,201,202),distance=10000,avg_power=201))
        self.store.import_file(path,activity_id=identity)
        html = self.page(identity)
        self.assertNotIn('id="native-records"',html)
        self.assertEqual(html.count('<summary>FIT source evidence'),2)
        self.assertIn('No single supported summary selected',html)
        self.assertEqual(html.count('class="metric-unavailable"'),4)

    def test_all_missing_signals_keep_explicit_evidence(self):
        html = self.page(self.native(missing=True))
        data = json.loads(re.search(r'id="native-records" type="application/json">(.*?)</script>',html,re.S)[1])
        self.assertTrue(all(r['power'] is None and r['heart_rate'] is None for r in data))
        self.assertIn('Power availability',html); self.assertIn('Heart rate availability',html)
        self.assertIn('No eligible complete 20-minute window',html)


if __name__ == '__main__': unittest.main()
