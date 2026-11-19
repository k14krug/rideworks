"""Serve disposable data for the SEG-02 browser clipboard check."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root), str(root / 'tests')]

from rideworks.segments import Effort, save_effort
from rideworks.strava_api import apply_observations, normalize
from rideworks.web import create_server
from test_segment_history_import import SegmentHistoryTests, ACTIVITY, EFFORT, SEGMENT, Response


def main():
    fixture = SegmentHistoryTests()
    fixture.setUp()
    try:
        fixture.watch()
        other = fixture.attempt(effort=EFFORT - 200, segment=SEGMENT + 1)
        other['segment']['name'] = 'Synthetic Second Loop'
        fixture.http.responses.append(Response(fixture.detail(ACTIVITY, other)))
        assert fixture.add(effort=EFFORT - 200)[0] == 303
        apply_observations(fixture.store, [normalize(fixture.listing(ACTIVITY))], 321, fixture.now)

        with fixture.store.connection:
            for row in fixture.api_rows(101):
                effort = Effort(str(row['id']), str(SEGMENT), 'Synthetic Watched Loop',
                                row['start_date'], row['elapsed_time'])
                save_effort(fixture.store, str(ACTIVITY), effort)
        fixture.http.responses.append(Response(fixture.api_rows(103)[101:103]))

        with create_server(fixture.store.data_dir, port=18774, settings_factory=lambda root: fixture.settings) as server:
            print('Synthetic Dev ready on http://127.0.0.1:18774', flush=True)
            server.serve_forever()
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    main()
