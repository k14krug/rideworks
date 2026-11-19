"""Serve disposable data for the SEG-02 history and clipboard check."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root), str(root / 'tests')]

from rideworks.segments import Effort, save_effort
from rideworks.segment_import import PastedRow, save_paste
from rideworks.performance import rebuild_performance
from rideworks.strava_api import apply_observations, normalize
from rideworks.web import create_server
from test_segment_history_import import SegmentHistoryTests, ACTIVITY, EFFORT, SEGMENT, Response


def main():
    fixture = SegmentHistoryTests()
    fixture.setUp()
    try:
        fixture.watch()
        other = fixture.attempt(effort=EFFORT - 200, segment=SEGMENT + 1)
        other['segment']['name'] = 'Synthetic West Loop'
        fixture.http.responses.append(Response(fixture.detail(ACTIVITY, other)))
        assert fixture.add(effort=EFFORT - 200)[0] == 303
        rides = (ACTIVITY, ACTIVITY + 2, ACTIVITY + 3)
        observations = [normalize(fixture.listing(ride) | {'name': f'Synthetic Ride {index}'})
                        for index, ride in enumerate(rides)]
        apply_observations(fixture.store, observations, 321, fixture.now)
        rebuild_performance(fixture.store)
        fixture.settings.segment_notice = None

        with fixture.store.connection:
            for index, row in enumerate(fixture.api_rows(101)):
                power = 510.5 if index == 0 else (90 + index * 2 if index % 3 else None)
                hr = 191 if index == 0 else (110 + index // 2 if index % 4 else None)
                effort = Effort(str(row['id']), str(SEGMENT), 'Synthetic Watched Loop',
                                row['start_date'], 120 if index < 2 else 120 + index, power, hr,
                                index % 2 == 0 if power is not None else None)
                save_effort(fixture.store, str(ACTIVITY + 1 if index < 2 else ACTIVITY), effort)
            single = Effort(str(EFFORT - 201), str(SEGMENT + 1), 'Synthetic West Loop',
                            other['start_date'], 200)
            save_effort(fixture.store, str(rides[1]), single)
        pasted = PastedRow(other['start_date'][:10], other['elapsed_time'], str(ACTIVITY))
        other_paste = PastedRow(pasted.calendar_day, 200, str(rides[1]))
        save_paste(fixture.store, str(SEGMENT + 1), [pasted, other_paste], {0: 'keep', 1: 'keep'},
                   {0: {f'api:{other["id"]}'}, 1: {f'api:{single.effort_id}'}})
        api_rows = fixture.api_rows(103)[101:103]
        api_rows[0].update(average_watts=251.5, average_heartrate=153.5, device_watts=False)
        api_rows[1].update(average_watts='invalid', average_heartrate=157)
        fixture.http.responses.extend(Response(api_rows) for _ in range(2))

        with create_server(fixture.store.data_dir, port=18774, settings_factory=lambda root: fixture.settings) as server:
            print('Synthetic Dev ready on http://127.0.0.1:18774', flush=True)
            server.serve_forever()
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    main()
