#!/usr/bin/env python3
"""Verify accepted pages remain available during a real forced curve rebuild."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import resource
import sys
import threading
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.store import Store
from rideworks.power_curve import rebuild_curves,curve_history,comparison
from rideworks.web import Application


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--aggregate-output',type=Path,required=True);a=p.parse_args()
    ready=threading.Event();finished=threading.Event();results=[];failures=[]
    def build():
        try:
            with Store(a.data_dir) as s:
                ready.set();results.append(rebuild_curves(s,force=True))
        except Exception as e:failures.append(type(e).__name__)
        finally:finished.set()
    app=Application(a.data_dir);thread=threading.Thread(target=build);thread.start();ready.wait(10)
    checks=0;times=[];routes=['/?home_tz=America%2FLos_Angeles','/plan?plan_tz=America%2FLos_Angeles','/training-state?tz=America%2FLos_Angeles','/performance?curve_tz=America%2FLos_Angeles']
    try:
        while not finished.is_set():
            for route in routes:
                if finished.is_set():break
                start=perf_counter();status,mime,body=app.get(route);times.append(round((perf_counter()-start)*1000))
                assert status==200 and b'Unable to complete request' not in body
                checks+=1
        thread.join()
        assert not failures and results[0]['computed']>0 and checks>=4
        with Store(a.data_dir) as s:
            assert curve_history(s)['pending']==0
            before=perf_counter();comparison(s);comparison_ms=round((perf_counter()-before)*1000)
        report=dict(build=results[0],concurrent_page_checks=checks,routes=len(routes),
                    max_page_elapsed_ms=max(times),page_elapsed_ms=times,
                    cached_comparison_elapsed_ms=comparison_ms,
                    process_peak_rss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),
                    sqlite_lock_failures=0)
        a.aggregate_output.parent.mkdir(parents=True,exist_ok=True);a.aggregate_output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    finally:thread.join()


if __name__=='__main__':main()
