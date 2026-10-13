# OPS-02 — nginx public origin and runtime environment names

**Status:** pending; implementation not invoked.  
**Issue:** [#35](https://github.com/k14krug/rideworks/issues/35).  
**Purpose:** Make the existing non-Flask RideWorks HTTP app work behind a same-host nginx reverse proxy and use runtime-neutral environment variable names.

## Requirements Used

- [OPS-01](OPS-01.md) and accepted PR #34: repository-root `data/`, immutable original evidence, existing standard-library HTTP server, loopback binding and normal `serve` command.
- Owner's 2026-10-12 production report and explicit requests: fix HTTP 403 `Invalid local host.` with nginx, support `RUN_PORT` from the systemd `EnvironmentFile`, rename `FLASK_DEBUG` to `DEBUG`, and update `.env.example`.
- [AGENTS.md](../../AGENTS.md): private single-rider application, bounded changes, privacy, tests and review gates.

## Execution Control

**Allowed Invocation:** `/TASK or /AUTOTASK`.

1. **Implementation:** Dex refreshes repository and starts from current `main` on a separate OPS-02 branch/PR. This is *not* a continuation of already merged PR #34.
2. **HARD — Analyst review:** Stop after changed code, focused/full tests, source-neutral reverse-proxy HTTP verification and implementation report. Analyst checks security boundary and application behavior.
3. **HARD — Owner acceptance:** Owner confirms deployed nginx URL, Settings/Plan form actions, and Strava connection behavior. No merge/close before Owner approval.

## Scoped implementation

### 1. Framework-neutral settings

- Replace `FLASK_RUN_PORT` with `RUN_PORT` in `rideworks/config.py`, CLI help, .env.example, documentation and all relevant tests.
- The port precedence remains: explicit `serve --port` > exported/systemd `RUN_PORT` > repository-root `.env` `RUN_PORT` > 8766.
- Replace `FLASK_DEBUG` with `DEBUG`; retain its boolean parsing and safe request diagnostics only. No interactive debugger or reloader.
- Remove misleading old Flask-named keys from active RideWorks configuration; document that systemd's `EnvironmentFile` sets exported process environment. The existing desktop launcher explicitly owns port 8766 and is not silently redirected.
- Preserve existing `RIDEWORKS_DATA_DIR` precedence and Strava credential handling; do not edit any live .env or secrets.

### 2. Explicit trusted public origin

- Add optional `PUBLIC_ORIGIN` for the HTTPS public application origin (scheme, DNS host and optional external port, no path/query/fragment). Validate at startup; reject malformed/untrusted forms and fail safely.
- Continue binding the Python backend to `127.0.0.1` (never automatically `0.0.0.0`).
- Permit exact public `Host` derived from configured `PUBLIC_ORIGIN` in addition to the existing local hosts. Match the expected external host/port with normal default-port semantics; reject other hosts, malformed Host values, and deceptive suffixes. Do not trust `X-Forwarded-Host` or `X-Forwarded-Proto` as independent authorization signals.
- Accept only the exact public `Origin` on Settings and Plan state-changing actions, along with the existing loopback origins; retain nonce/CSRF, input validation and existing action constraints. Reject spoofed Origin values, missing or unexpected origin as before. No blanket allow-all.
- Browser Strava Connect must use the configured public HTTPS callback URL when `PUBLIC_ORIGIN` is provided; otherwise keep current loopback behavior. Construct callback address only from trusted configuration, never untrusted request headers. Preserve CLI-based loopback OAuth and existing state handling. Include a deployment note that Strava's authorized callback domain must agree with the selected public host.
- Do not introduce new sessions, auth providers, web server frameworks or proxy-trust middleware.

### 3. Documentation and deployment

- Update `.env.example` to show `RUN_PORT=8766`, `DEBUG=0`, commented optional `PUBLIC_ORIGIN=https://rideworks.example.com`; keep credentials out of version control.
- Document typical same-host nginx `proxy_pass http://127.0.0.1:<RUN_PORT>` and host forwarding, with port consistency and TLS on nginx.
- Document systemd `ExecStart=.../python -m rideworks serve` **without** `--port` so configured `RUN_PORT` takes effect. Do not imply systemd dynamically expands an env variable in arbitrary command syntax.
- Update README/CLI messages and test names that incorrectly refer to Flask for the current app. Avoid cosmetic rewriting of historical evidence.

## Verification and acceptance evidence

- Unit configuration tests for selected `RUN_PORT`/`DEBUG` from exported environment and `.env`, precedence, invalid syntax, default port, no environment mutation and unrelated legacy values.
- Live ephemeral-loopback HTTP integration tests with normal local host, allowed public host, denied arbitrary/suffix/malformed host, allowed public POST Origin with valid nonce, denied foreign/missing Origin, and existing local POST behavior.
- Test Settings, Plan, dashboard/routes and Strava auth redirect/callback under both public and local configuration, with fake credentials/network. Verify no leaking secrets, paths, activity source data or tokens.
- Test nginx-like upstream `Host` where public HTTPS uses the normal external port, including when it differs from internal `RUN_PORT`.
- Run focused and existing regression tests and make a compact report. Do not run real Strava auth/sync or modify production data as a test.
- Explicitly state what was *not* directly exercised on Owner's private nginx/server deployment.

## Explicit non-goals

- No SQLite migration, original-file rewriting, cycling metric change, Flask or Gunicorn conversion, server bind to public interfaces, broad authentication redesign, Strava historical harvesting, backup subsystem, or Phase 6.
- No changes to already accepted OPS-01 migration beyond the required HTTP/runtime interface.

## Review boundary

If safe handling of public origin or Strava authorization cannot be achieved within the small existing HTTP layer, stop and bring the specific blocker to the Analyst/Owner before broadening scope. Do not replace the restriction with permissive header acceptance just to get an HTTP 200.
