# Architecture

Surfaceguard is a local-first, single-organization-at-a-time assessment tool. The React client uses JSON REST endpoints from FastAPI. FastAPI routers validate requests and delegate discovery and assessment to a service module. SQLAlchemy stores organizations, scans, assets, observations, findings, and scan changes. PostgreSQL is used by Compose; SQLite is the default for a quick backend-only development run.

```text
React + Vite -> FastAPI routers -> scope / scanner / risk services -> SQLAlchemy -> PostgreSQL or SQLite
```

The scanner starts with the organization root and a single passive Certificate Transparency query. Candidate names are normalized and checked with DNS label boundaries. DNS records are persisted even when addresses are private, but network checks reject non-global IPs by default. HTTP connects directly to a previously approved IP, uses the original hostname for TLS SNI and verification, limits reads, and does not follow redirects. Scans are queued with FastAPI background tasks; they are not durable across process restarts.

No login, tenant authorization, scheduled task queue, or independent ownership challenge exists yet. Keep the service bound to localhost and do not expose it to an untrusted network.