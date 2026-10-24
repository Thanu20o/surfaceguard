# Limitations and responsible use

- This is a development portfolio project, not a production SaaS or a complete EASM product.
- There is no authentication or role-based access control. Run only on a trusted local workstation; do not publish the API or frontend to a network.
- The operator attests to authorization when entering a root domain. Ownership is not independently verified.
- Discovery is root-domain DNS plus the public crt.sh endpoint; certificate transparency may be unavailable or rate limited. No brute-force or arbitrary subdomain wordlist is used.
- DNS record and TLS/HTTP observations are limited. This is not a full TLS cryptographic audit, vulnerability scanner, port scanner, or crawler.
- HTTP assessment is HTTPS-only and one root request per host. API documentation paths are checked only when `api` is a hostname label. No API operations are invoked.
- Private/loopback targets are rejected by default. The optional private-target setting should only be used in a controlled local lab and does not create an ownership or authorization boundary.
- Scan tasks use in-process FastAPI background tasks and can be lost on restart. Celery/Redis scheduling is not implemented.
- Scan comparison currently records new assets, missed assets, DNS record changes, and HTTP/TLS observation changes. Automatic finding resolution, asset risk history, and full historical change UI are incomplete.
- PDF reports, notifications, user authentication, organization deletion audit history, and configurable business-impact settings are not implemented.
- API responses are size bounded for read bodies and redirects are not followed. Certificate transparency queries use a limited body cap. All network checks have timeouts.
- In-memory SQLite and mocked scanner tests are used for deterministic tests; a live authorized domain and internet service were not tested as part of this build.

Only assess domains and systems for which you have explicit authorization. Stop a scan if it causes unexpected load or service impact.