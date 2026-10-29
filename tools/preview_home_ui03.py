#!/usr/bin/env python3
"""Create a disposable synthetic Home preview with three years of mileage."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rideworks.performance import rebuild_performance
from rideworks.power_curve import rebuild_curves
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT/'tools/preview_home.py'), '--data-dir', str(args.data_dir)], check=True)
    with Store(args.data_dir) as store:
        rows = [normalize(dict(id=year*100+month, name='Synthetic annual ride', type='Ride', sport_type='Ride',
                               start_date=f'{year}-{month:02d}-15T12:00:00Z',
                               distance=(45+month*4)*1609.344, elapsed_time=3600))
                for year in (2024, 2025, 2026) for month in range(1, 13 if year < 2026 else 10)]
        apply_observations(store, rows, 999, 1790000000)
        rebuild_performance(store)
        rebuild_curves(store)
    print('Synthetic three-year mileage preview created.')


if __name__ == '__main__':
    main()
