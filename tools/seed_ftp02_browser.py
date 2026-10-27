"""Create a new, disposable synthetic Store for verify_ftp02_browser.js."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'tests')]

from fit_fixture import make_fit
from ftp_fixture import seed_ftp
from rideworks.performance import rebuild_performance
from rideworks.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='New disposable directory; must not already exist')
    args = parser.parse_args()
    args.directory.mkdir(parents=True)
    start = int(datetime(2024, 11, 8, 11, 33, 20, tzinfo=timezone.utc).timestamp())
    ride = args.directory / 'synthetic.fit'
    ride.write_bytes(make_fit(
        powers=[200] * 1200, heart_rates=[143] * 1200,
        timestamps=range(start, start + 1200), elapsed=1200, timer=1200,
        event_timestamps=(start, start + 1200), session_timestamp=start + 1200,
    ))
    with Store(args.directory / 'store') as store:
        seed_ftp(store, [('2024-01-01', 180), ('2024-11-01', 200)])
        store.import_fit(ride)
        rebuild_performance(store)
    print('Synthetic Store initialized')


if __name__ == '__main__':
    main()
