# OPS-02 implementation and verification

Implemented on `task/ops-02-nginx-runtime` from refreshed `main` at `16934bd`,
including the Owner's HTTP-only correction in the Analyst's JIT and issue #35.
Ready for **HARD — Analyst review**. Owner deployment acceptance follows;
the task remains `in_progress` and is not authorized to merge or close yet.

## Result

RideWorks supports same-host nginx on the Owner's private HTTP home LAN using
one explicit `PUBLIC_ORIGIN`, such as `http://rideworks.lan` or
`http://192.168.1.20:8080`. HTTPS remains optional; no TLS setup is required.
The Python server still binds only to `127.0.0.1`.

- Startup reads `RUN_PORT`, `DEBUG`, `RIDEWORKS_DATA_DIR` and optional
  `PUBLIC_ORIGIN`. Port precedence is CLI > exported/systemd environment >
  repository `.env` > 8766. Old Flask-named runtime keys are ignored. Boolean
  diagnostics retain method/status/timing only. The desktop launcher still
  explicitly selects 8766.
- Public origin validation accepts HTTP/HTTPS DNS names, IPv4 and bracketed
  IPv6 with optional valid port. Paths (including a trailing slash), userinfo,
  queries, fragments, wildcards, control characters and malformed hosts/ports
  are rejected without echoing the input. Names are lowercase and default
  external ports are omitted from the canonical origin.
- `HTTPAccess` shares the trusted configuration across Host validation,
  Settings/Plan Origin checks and browser OAuth. Only the configured public
  Host or existing loopback hosts are accepted. Host is case-insensitive;
  default external ports 80/443 may be explicit or omitted. The POST Origin
  must exactly match the canonical configured origin or an existing local
  origin. Missing/duplicate/unexpected headers are rejected. Existing nonce,
  action/input constraints and OAuth state checks remain in place.
- Forwarded headers never authorize requests or choose callback addresses.
  Browser Strava Connect uses the configured origin plus `/strava/callback`,
  or its existing loopback callback if omitted. CLI OAuth remains loopback.
  Existing token files are unaffected by choosing a public origin.
- `.env.example` and README document HTTP nginx Host forwarding (preserving
  external ports), `RUN_PORT` consistency and a systemd `ExecStart` with no
  `--port`. Setup/timeout/error notices show the configured callback domain.

## Verification

```bash
DEBUG=0 PYTHONPATH=tests .venv/bin/python -m unittest \
  test_rideworks_config test_rideworks_proxy test_rideworks_strava_settings \
  test_rideworks_planning test_rideworks_web test_rideworks_launcher
DEBUG=0 .venv/bin/python -m unittest discover -s tests
git diff --check
```

**93 focused tests passed; all 474 regression tests passed.** The focused set
includes 23 configuration tests and 12 live ephemeral-loopback HTTP proxy tests.
The integration requests use nginx-like Host/Origin headers, synthetic FIT/export
fixtures, disposable stores and fake Strava responses, never the Owner's store
or real Strava service.

| Scenario | Verified behavior |
| --- | --- |
| HTTP hostname, external 80, internal ephemeral port | Home, Activities, both Performance modes, Training State, Plan, Settings and Activity Review return 200; direct local access retained. |
| HTTP LAN IPv4, external 80/8080; bracketed IPv6 | Correct Host accepted; absent/wrong external port rejected; public Settings/Plan submissions succeed. |
| Exact HTTP and local POST Origin + nonce | Annual goal, heavy-legs feedback and classification actions succeed; invalid nonce, replayed Settings nonce and invalid classification rejected. |
| Foreign/suffix/malformed/missing/duplicate Host or Origin | 403, no goals/classifications/feedback/intents written, no OAuth request begun; forwarded headers grant no access. |
| Optional HTTPS, default 443/custom 8443 | Exact configured host/origin supported without replacing HTTP coverage. |
| Public/local OAuth | Trusted callback URL, fake successful token exchange, private 0600 token storage, clean redirect, one-use/wrong-state rejection and safe diagnostics. |
| Origin configuration with existing connection | Token bytes preserved and no fake network calls made simply by startup/page viewing. |
| Configuration | Export/file/default/CLI precedence, boolean syntax, malformed origins, legacy-key isolation, no environment mutation and invalid config before bind/store initialization. |

The first uncontrolled full-suite run had three CLI subprocess errors because
this tool shell exports a non-boolean `DEBUG` value. The documented run supplies
`DEBUG=0` only to test processes and passes all 474 tests. Invalid selected
`DEBUG` still fails startup; neither live environment files nor secrets were
edited to make tests pass.

## Deployment limits and remaining review

The Owner's private nginx instance, systemd service and actual LAN URL were
**not directly exercised or reconfigured**. No real Strava authorization or sync
was attempted. No production database, originals, token sidecars or live `.env`
were changed; no migration, model/calculation or framework changes are included.

[Strava's official authentication documentation](https://developers.strava.com/docs/authentication/)
requires the redirect URI to agree with the registered callback domain and
explicitly permits localhost/127.0.0.1. It does not establish acceptance of
every private LAN hostname/IP. Fake OAuth verifies application behavior only;
the Owner must confirm provider acceptance of their selected callback domain.
A real provider rejection is a separate narrow blocker, not a requirement to
use HTTPS or permission to bypass provider checks. Current connections need
no forced reauthorization.

Analyst review should assess the bounded configuration/Host/Origin/OAuth
changes. After that gate, the Owner confirms their deployed HTTP nginx URL,
Settings/Plan actions and Strava behavior before final acceptance.
