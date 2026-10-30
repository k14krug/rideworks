"""Minimal local import, inspection and rebuild commands."""

import argparse
import json
import sqlite3
import sys

from .analysis import analyze_activity, compact_analysis
from .config import startup_config
from .errors import RideWorksError
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rideworks")
    parser.add_argument("--data-dir", help="Data location (overrides RIDEWORKS_DATA_DIR and project-root data/)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("import-fit", help="Preserve and import one FIT/FIT.GZ").add_argument("path")
    commands.add_parser("import-strava-export", help="Import historical activities from a Strava ZIP or extracted root").add_argument("path")
    commands.add_parser("inspect", help="Compact source evidence; no raw streams").add_argument("activity_id")
    commands.add_parser("analyze", help="Source summary and best 20-minute result; no raw streams").add_argument("activity_id")
    commands.add_parser("reextract", help="Rebuild from the preserved original").add_argument("source_id")
    commands.add_parser("rebuild-performance", help="Rebuild durable trusted Virtual Ride best-20 history")
    curves = commands.add_parser('rebuild-power-curves', help='Build current observed power-duration profiles from retained sources')
    curves.add_argument('--force', action='store_true', help='Recalculate unchanged profiles too')
    connect = commands.add_parser('strava-connect', help='Authorize private manual Strava synchronization')
    connect.add_argument('--callback-port', type=int, default=8772, help='Temporary loopback OAuth callback port (default: 8772)')
    commands.add_parser('sync-strava', help='Manually sync recent/new Strava activity metadata')
    commands.add_parser('refresh-strava-effort', help='Refresh at most 30 established cycling summaries from the last 60 days')
    repair=commands.add_parser('repair-strava-summaries', help='Explicit bounded established-ID summary repair (at most eight GPX rides)')
    repair.add_argument('--targets',required=True,help='Private JSON mapping of Strava IDs to established RideWorks Activity IDs')
    commands.add_parser('strava-disconnect', help='Revoke/remove local Strava authorization; retain history')
    serve = commands.add_parser("serve", help="Open the local RideWorks browser application")
    serve.add_argument("--port", type=int, help="Loopback port (overrides RUN_PORT; default: 8766)")
    args = parser.parse_args(argv)
    try:
        config = startup_config(args.data_dir, getattr(args, 'port', None))
        if args.command == "serve":
            from .web import serve as serve_web
            serve_web(config.data_dir, config.port, debug=config.debug, public_origin=config.public_origin)
            return 0
        if args.command in ('strava-connect','sync-strava','strava-disconnect','repair-strava-summaries','refresh-strava-effort'):
            from .config import ConfigurationError, strava_credentials
            from .strava import ApiClient, connect, disconnect, sync
            from .strava_api import SyncError
            try:
                if args.command=='strava-connect' and not 1<=args.callback_port<=65535:
                    raise SyncError('--callback-port must be an integer from 1 to 65535')
                with Store(config.data_dir) as store:
                    try:client=ApiClient(strava_credentials())
                    except ConfigurationError:
                        if args.command!='strava-disconnect':raise
                        client=None
                    if args.command=='repair-strava-summaries':
                        from pathlib import Path
                        from .strava_summary_repair import enrich_summaries
                        try:targets=json.loads(Path(args.targets).read_text())
                        except (OSError,ValueError):raise SyncError('Cannot read the private summary repair target manifest') from None
                        result=enrich_summaries(store,client,targets)
                    elif args.command=='refresh-strava-effort':
                        from .strava_effort_refresh import refresh_recent
                        result=refresh_recent(store,client)
                    else:
                        operation={'strava-connect':connect,'sync-strava':sync,'strava-disconnect':disconnect}[args.command]
                        result=operation(store,client,**({'port':args.callback_port} if args.command=='strava-connect' else {}))
                print(json.dumps(result,indent=2))
                return 0 if result['status'] not in ('stopped','failed') else 1
            except (RideWorksError,OSError,sqlite3.Error) as error:
                report=dict(status='failed',error=str(error) if isinstance(error,RideWorksError) else 'Local Strava operation failed',
                            rate_limits=getattr(error,'rate',{}))
                print(json.dumps(report,indent=2))
                return 1
        with Store(config.data_dir) as store:
            if args.command == "import-fit":
                result = store.import_fit(args.path)
            elif args.command == "import-strava-export":
                result = store.import_strava_export(args.path)
            elif args.command == "inspect":
                result = store.inspect(args.activity_id)
            elif args.command == "analyze":
                result = compact_analysis(analyze_activity(store, args.activity_id))
            elif args.command == "rebuild-performance":
                from .performance import rebuild_performance
                result = rebuild_performance(store)
            elif args.command == 'rebuild-power-curves':
                from .power_curve import rebuild_curves
                result = rebuild_curves(store, force=args.force)
            else:
                result = store.reextract(args.source_id)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        if args.command == "import-strava-export" and result["status"] != "completed":
            return 1
    except (RideWorksError, OSError, sqlite3.Error) as exc:
        print(f"RideWorks: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
