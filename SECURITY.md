# Security policy

## Reporting a vulnerability

Open an issue at
[github.com/kelvinasiedu-programmer/sleepwise/issues](https://github.com/kelvinasiedu-programmer/sleepwise/issues).
If the report is sensitive, say so in the issue without details and a private channel can
be arranged. A machine-readable pointer lives at `/.well-known/security.txt` on the live
site (RFC 9116).

## Security posture

SleepWise's primary security control is architectural: **it does not store health data.**
There are no accounts, no sessions, and no database. A request carries the user's inputs,
a response is generated, and nothing identifiable is persisted. The best defense against
a health-data breach is having no health data to breach.

What is actually in place:

| Control | Implementation |
|---|---|
| Encryption in transit | TLS on all traffic (host-enforced), plus HSTS with a 2-year max-age |
| Data at rest | None stored by design; the response cache is in-memory only and never written to disk |
| Content Security Policy | `default-src 'self'`, no third-party scripts, `frame-ancestors 'none'` |
| Other headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` |
| Abuse limits | Per-IP rate limiting (429 on excess) and bounded input sizes (422 on oversized payloads) |
| Logging | Request method, path, status, duration, and a request id only. Medication, supplement, and condition inputs are never logged |
| Supply chain | `pip-audit` and CodeQL run in CI; Dependabot keeps dependencies current |
| Trackers | No analytics or advertising pixels on pages where health information is entered |

## What deliberately does not exist here

These come up in enterprise health-architecture checklists, so for clarity:

- **HIPAA / BAAs.** SleepWise is not a covered entity or business associate and handles
  no protected health information on behalf of one, so HIPAA does not apply. The relevant
  consumer framework is the FTC Health Breach Notification Rule, and the design answer to
  it is data minimization: nothing identifiable is collected or retained. No third party
  receives user health inputs, so there is no data-processing relationship requiring a
  BAA. The optional Sentry hook (off by default) receives software error reports, not
  user inputs.
- **RBAC and session timeouts.** There are no accounts, roles, or sessions. Adding them
  would create the stored health data the design avoids. If accounts are ever introduced,
  RBAC, session expiry, encrypted storage, and audit logging become requirements at that
  point, and this file should be treated as the checklist for that work.
- **Database audit logging.** There is no database. Access logging exists (request ids in
  the structured logs) without recording what a user typed, which is the correct trade
  for an anonymous educational tool: auditability of access, not surveillance of content.

## Scope notes

- The deployed instance runs on Render's free tier behind Cloudflare; platform-level
  controls (DDoS mitigation, TLS termination) are theirs.
- `/docs` (Swagger UI) is exempted from the strict CSP because it loads its assets from a
  CDN. It exposes only the public API schema.
