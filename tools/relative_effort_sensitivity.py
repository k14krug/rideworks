#!/usr/bin/env python3
"""Read-only-model sensitivity study for Relative Effort's mixed source population.

Compares the accepted relative-effort-v1 grouping with narrower historical
comparison cohorts. Does NOT change the production classification or its
training-stress inputs. Output is aggregate-only, without rider identifiers.
Run with a disposable copy of the private RideWorks data directory: Store
initialization may perform normal housekeeping/migration.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rideworks.relative_effort import LABELS, VERSION, classify
from rideworks.training_state import FTP_CALENDAR, ride_results
from rideworks.store import Store

METHODS = ("power", "session_power", "hr")
INDEX = {label: index for index, label in enumerate(LABELS)}


def _cohort(method, mode):
    if method not in METHODS:
        return None
    if mode == "family":
        # Measured/estimated-session power share the same watts-based stress
        # family; HR-derived stress is separate.
        return "power_based" if method in ("power", "session_power") else "hr"
    if mode == "exact":
        return method
    raise ValueError("Unsupported sensitivity mode")


def evaluate(rides):
    """Assess eligibility and label sensitivity without exposing activity data.

    Both alternatives use the ORIGINAL classify() implementation, including
    42-day calendar boundaries, minimum six rides, ties, and load-first rules.
    Only the comparison population differs. This is not an endorsement of an
    alternative model.
    """
    rides = list(rides)
    baseline = classify(rides)
    input_methods = Counter((r.get("selected") or {}).get("method") or "none"
                            for r in rides)
    baseline_labels = Counter(v["category"] if v["status"] == "available"
                              else "Not rated" for v in baseline.values())
    result = {
        "model": VERSION, "comparison_days": 42,
        "cohort_policy": "all eligible prior cycling rides",
        "input_rides": len(rides), "input_methods": dict(sorted(input_methods.items())),
        "baseline_labels": dict(sorted(baseline_labels.items())),
        "alternatives": {},
    }
    for mode in ("family", "exact"):
        groups = defaultdict(list)
        for ride in rides:
            key = _cohort((ride.get("selected") or {}).get("method"), mode)
            if key is not None:
                groups[key].append(ride)
        alternate = {}
        for cohort in groups.values():
            alternate.update(classify(cohort))

        counters = Counter()
        transitions = Counter()
        by_method = defaultdict(Counter)
        for ride in rides:
            activity_id = ride["activity_id"]
            old = baseline[activity_id]
            if old["status"] != "available":
                continue
            counters["baseline_rated"] += 1
            method = (ride.get("selected") or {}).get("method") or "none"
            new = alternate.get(activity_id)
            if new is None or new["status"] != "available":
                counters["alternate_not_rated"] += 1
                by_method[method]["alternate_not_rated"] += 1
                continue
            counters["both_rated"] += 1
            by_method[method]["both_rated"] += 1
            delta = INDEX[new["category"]] - INDEX[old["category"]]
            transitions[(old["category"], new["category"])] += 1
            if delta:
                counters["changed"] += 1
                by_method[method]["changed"] += 1
                counters["higher" if delta > 0 else "lower"] += 1
            if abs(delta) >= 2:
                counters["two_or_more_bands"] += 1
                by_method[method]["two_or_more_bands"] += 1
            if abs(delta) >= 3:
                counters["three_or_more_bands"] += 1
        result["alternatives"][mode] = {
            "cohorts": {key: len(value) for key, value in sorted(groups.items())},
            "baseline_rated": counters["baseline_rated"],
            "alternate_not_rated": counters["alternate_not_rated"],
            "both_rated": counters["both_rated"],
            "changed": counters["changed"],
            "higher": counters["higher"], "lower": counters["lower"],
            "two_or_more_bands": counters["two_or_more_bands"],
            "three_or_more_bands": counters["three_or_more_bands"],
            "by_method": {key: dict(sorted(value.items()))
                          for key, value in sorted(by_method.items())},
            "transitions": {
                before + " -> " + after: count
                for (before, after), count in sorted(transitions.items())
            },
        }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True,
                        help="DISPOSABLE private RideWorks data copy, never the live store")
    parser.add_argument("--as-of", required=True,
                        help="fixed aware ISO timestamp, e.g. 2026-10-29T12:00:00-07:00")
    args = parser.parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        parser.error("--as-of must have an explicit UTC offset")
    if not (args.data_dir / "rideworks.sqlite3").is_file():
        parser.error("--data-dir must contain an existing rideworks.sqlite3")
    # Never commit the private data directory, its detailed logs, or a row-level
    # report. With cache_writes supplied, ride_results does not flush caches.
    with Store(args.data_dir) as store:
        rides, _ = ride_results(store, FTP_CALENDAR, as_of=as_of, cache_writes=[])
        output = evaluate(rides)
        output["as_of"] = as_of.isoformat()
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
