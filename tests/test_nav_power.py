"""Synthetic checks for the shared Power navigation and existing view URLs."""
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest

from fit_fixture import make_fit
from rideworks.store import Store
from rideworks.web import Application


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_main_nav = False
        self.links = []
        self.ids = {}
        self.tags = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'nav' and attrs.get('aria-label') == 'Main':
            self.in_main_nav = True
        if self.in_main_nav and tag == 'a':
            self.links.append(attrs)
        if 'id' in attrs:
            self.ids[attrs['id']] = attrs
            self.tags[attrs['id']] = tag

    def handle_endtag(self, tag):
        if tag == 'nav' and self.in_main_nav:
            self.in_main_nav = False


class PowerNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        with Store(root / 'data') as store:
            fit = root / 'synthetic.fit'
            fit.write_bytes(make_fit(powers=[120] * 1200, heart_rates=[100] * 1200,
                                     timestamps=range(1100000000, 1100001200)))
            self.activity_id = store.import_file(fit)['activity_id']
        self.app = Application(root / 'data')

    def page(self, route):
        status, _, body = self.app.get(route)
        self.assertEqual(status, 200, route)
        return Page(body.decode())

    def test_links_exist_across_pages_without_false_current_state(self):
        for route in ['/', '/activities', '/activities/' + self.activity_id,
                      '/training-state', '/plan', '/settings', '/performance/ftp']:
            with self.subTest(route=route):
                page = self.page(route)
                links = {a['href']: a for a in page.links}
                self.assertIn('/performance', links)
                self.assertIn('/performance?curve=1', links)
                self.assertNotIn('aria-current', links['/performance'])
                self.assertNotIn('aria-current', links['/performance?curve=1'])
                self.assertEqual(page.ids['power-nav-label']['class'], 'nav-power-heading')
                self.assertEqual(page.tags['power-nav'], 'details')
                self.assertEqual(page.tags['power-nav-label'], 'summary')
                self.assertNotIn('open', page.ids['power-nav'])

    def test_direct_urls_select_the_matching_view_and_current_link(self):
        cases = [('/performance', False), ('/performance?curve=0', False),
                 ('/performance?curve=1', True),
                 ('/performance?curve=1&curve_tz=UTC', True)]
        for route, curve in cases:
            with self.subTest(route=route):
                page = self.page(route)
                links = {a['href']: a for a in page.links}
                selected = '/performance?curve=1' if curve else '/performance'
                other = '/performance' if curve else '/performance?curve=1'
                self.assertEqual(links[selected].get('aria-current'), 'page')
                self.assertNotIn('aria-current', links[other])
                self.assertNotIn('open', page.ids['power-nav'])
                self.assertIn('is-current', page.ids['power-nav']['class'])
                self.assertEqual('hidden' in page.ids['performance-history-mode'], curve)
                self.assertEqual('hidden' in page.ids['power-curve-panel'], not curve)
                self.assertIn('performance-points', page.ids)
                self.assertIn('power-curve-data', page.ids)


if __name__ == '__main__':
    unittest.main()
