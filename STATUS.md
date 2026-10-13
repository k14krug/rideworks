# STATUS.md

**Product:** RideWorks.
**Current task:** OPS-02 — nginx proxy compatibility and framework-neutral runtime settings.
**State:** ready_for_review.
**Branch:** `task/ops-02-nginx-runtime`; [draft PR #36](https://github.com/k14krug/rideworks/pull/36), [issue #35](https://github.com/k14krug/rideworks/issues/35).
**Scope:** Corrected [OPS-02 JIT](docs/tasks/OPS-02.md): HTTP-only private home-LAN nginx, optional configured HTTP/HTTPS `PUBLIC_ORIGIN`, strict Host/Origin/nonce checks, loopback backend, trusted browser OAuth callback, `RUN_PORT`/`DEBUG` names and deployment docs. No TLS requirement.
**Verification:** 93 focused tests and all 474 regression tests passed, including live ephemeral HTTP LAN Host/Origin and fake OAuth checks. [Implementation report](reports/OPS-02/implementation.md). No production store, credentials or live `.env` changes; actual Owner nginx/provider-domain acceptance untested.
**Next action:** HARD — Analyst review of the HTTP/configuration boundary and verification. Owner confirms deployed HTTP nginx URL, Settings/Plan actions and Strava behavior after technical review; no merge/close yet.
**Last completed task:** OPS-01 migration accepted and merged as [PR #34](https://github.com/k14krug/rideworks/pull/34). Private rollback source remains retained; no cleanup is part of OPS-02.
