import hashlib
import http.client
import json
import logging
import socket
import ssl
import threading
import time
from datetime import datetime, timezone

import dns.exception
import dns.resolver
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Asset, Finding, Observation, Organization, Scan, ScanChange, utc_now
from app.services.risk import calculate_risk
from app.services.scope import is_in_scope, is_permitted_ip

logger = logging.getLogger(__name__)
_request_rate_lock = threading.Lock()
_ct_rate_lock = threading.Lock()
_last_request_at = 0.0
_last_ct_request_at = 0.0
DNS_TYPES = ("A", "AAAA", "CNAME", "MX", "NS", "TXT", "CAA")
SECURITY_HEADERS = ("strict-transport-security", "content-security-policy", "x-content-type-options", "referrer-policy", "permissions-policy", "x-frame-options")
DOC_PATHS = ("/openapi.json", "/swagger.json", "/api-docs", "/swagger/v1/swagger.json")


def resolve_host(hostname: str) -> tuple[list[str], list[dict], list[str]]:
    addresses: set[str] = set()
    records: list[dict] = []
    errors: list[str] = []
    resolver = dns.resolver.Resolver()
    deadline = time.monotonic() + settings.request_timeout_seconds
    for record_type in DNS_TYPES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            errors.append("DNS lookup budget exhausted.")
            break
        resolver.timeout = min(1.0, remaining)
        resolver.lifetime = remaining
        try:
            answer = resolver.resolve(hostname, record_type, raise_on_no_answer=False)
            if answer.rrset is None:
                continue
            for record in answer:
                value = record.to_text().strip('"')
                records.append({"hostname": hostname, "type": record_type, "value": value, "ttl": answer.rrset.ttl})
                if record_type in ("A", "AAAA"):
                    addresses.add(value)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            continue
        except (dns.exception.DNSException, OSError) as exc:
            errors.append(f"{record_type}: {type(exc).__name__}")
    return sorted(addresses), records, errors


def discover_ct(root_domain: str) -> tuple[list[str], str | None]:
    global _last_ct_request_at
    with _ct_rate_lock:
        now = time.monotonic()
        if now - _last_ct_request_at < settings.ct_min_interval_seconds:
            return [], "Certificate transparency lookup skipped by the local rate limit."
        _last_ct_request_at = now
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds, follow_redirects=False) as client:
            with client.stream("GET", "https://crt.sh/", params={"q": f"%.{root_domain}", "output": "json"}, headers={"User-Agent": "Surfaceguard/0.1 (authorized asset inventory)"}) as response:
                if response.status_code != 200:
                    return [], f"Certificate transparency source returned HTTP {response.status_code}."
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > settings.max_response_bytes * 16:
                        return [], "Certificate transparency response exceeded its size limit."
                    chunks.append(chunk)
        rows = json.loads(b"".join(chunks))
        names = set()
        for row in rows:
            for name in str(row.get("name_value", "")).splitlines():
                candidate = name.strip().lower().lstrip("*.").rstrip(".")
                if candidate and is_in_scope(candidate, root_domain):
                    names.add(candidate)
        return sorted(names), None
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.info("Certificate transparency lookup unavailable: %s", type(exc).__name__)
        return [], f"Certificate transparency lookup unavailable ({type(exc).__name__})."


def _http_observation(hostname: str, approved_ips: list[str]) -> dict:
    observation = {"state": "skipped", "reason": "No approved public address was available."}
    if not any(is_permitted_ip(address, settings.allow_private_targets) for address in approved_ips):
        return observation

    # Resolve again immediately before the request; refuse changed or private answers.
    current_ips, _, _ = resolve_host(hostname)
    approved = {ip for ip in approved_ips if is_permitted_ip(ip, settings.allow_private_targets)}
    current = {ip for ip in current_ips if is_permitted_ip(ip, settings.allow_private_targets)}
    if not current or not current.issubset(approved):
        return {"state": "skipped", "reason": "DNS answers changed or no longer meet the network policy."}

    for address in sorted(approved):
        result = _https_get(hostname, address, "/")
        if result.get("state") == "completed":
            result["http_redirect"] = _http_redirect_observation(hostname, address)
            return result
    return {"state": "failed", "reason": "ConnectionError"}


def _wait_for_request_slot() -> None:
    global _last_request_at
    with _request_rate_lock:
        wait = settings.request_interval_seconds - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def _http_redirect_observation(hostname: str, address: str) -> dict:
    _wait_for_request_slot()
    try:
        with socket.create_connection((address, 80), timeout=settings.request_timeout_seconds) as connection:
            request = f"HEAD / HTTP/1.1\r\nHost: {hostname}\r\nUser-Agent: Surfaceguard/0.1 (authorized security assessment)\r\nConnection: close\r\n\r\n"
            connection.sendall(request.encode("ascii"))
            response = http.client.HTTPResponse(connection)
            response.begin()
            location = response.getheader("location", "")[:512]
            return {"state": "completed", "status_code": response.status, "redirects_to_https": location.lower().startswith("https://"), "redirect_host": location.split("/", 3)[2] if location.lower().startswith("https://") else ""}
    except (http.client.HTTPException, OSError) as exc:
        return {"state": "failed", "reason": type(exc).__name__}


def _https_get(hostname: str, address: str, path: str, capture_body: bool = False) -> dict:
    _wait_for_request_slot()
    started = time.monotonic()
    context = ssl.create_default_context()
    try:
        with socket.create_connection((address, 443), timeout=settings.request_timeout_seconds) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=hostname) as tls_socket:
                request = f"GET {path} HTTP/1.1\r\nHost: {hostname}\r\nUser-Agent: Surfaceguard/0.1 (authorized security assessment)\r\nConnection: close\r\n\r\n"
                tls_socket.sendall(request.encode("ascii"))
                response = http.client.HTTPResponse(tls_socket)
                response.begin()
                body = response.read(settings.max_response_bytes + 1)
                return {
                    "state": "completed",
                    "status_code": response.status,
                    "https_available": True,
                    "response_ms": round((time.monotonic() - started) * 1000),
                    "content_type": response.getheader("content-type", "")[:120],
                    "headers": {name: response.getheader(name) is not None for name in SECURITY_HEADERS},
                    "redirect_not_followed": response.status in (301, 302, 303, 307, 308),
                    "server_header_present": response.getheader("server") is not None,
                    "body_size_limited": len(body) > settings.max_response_bytes,
                    **({"body": body[:settings.max_response_bytes].decode("utf-8", errors="replace")} if capture_body else {}),
                }
    except (httpx.HTTPError, http.client.HTTPException, OSError, ssl.SSLError) as exc:
        return {"state": "failed", "reason": type(exc).__name__}


def _api_document(hostname: str, approved_ips: list[str]) -> dict | None:
    if "api" not in hostname.split("."):
        return None
    addresses = [ip for ip in approved_ips if is_permitted_ip(ip, settings.allow_private_targets)]
    if not addresses:
        return {"state": "skipped", "reason": "No permitted address was available for API documentation checks."}
    completed_checks = 0
    for path in DOC_PATHS:
        for address in addresses:
            result = _https_get(hostname, address, path, capture_body=True)
            if result.get("state") != "completed":
                continue
            completed_checks += 1
            if result.get("status_code") != 200 or result.get("body_size_limited"):
                continue
            if "json" not in result.get("content_type", "").lower():
                continue
            try:
                document = json.loads(result["body"])
            except (ValueError, TypeError, RecursionError):
                continue
            if not isinstance(document, dict) or not isinstance(document.get("paths"), dict) or not (document.get("openapi") or document.get("swagger")):
                continue
            methods = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}
            method_count = sum(1 for item in document["paths"].values() if isinstance(item, dict) for method in item if method.lower() in methods)
            components = document.get("components")
            security_schemes = components.get("securitySchemes") if isinstance(components, dict) else None
            return {
                "state": "completed",
                "public": True,
                "url": f"https://{hostname}{path}",
                "title": str(document.get("info", {}).get("title", ""))[:160] if isinstance(document.get("info"), dict) else "",
                "version": str(document.get("info", {}).get("version", ""))[:80] if isinstance(document.get("info"), dict) else "",
                "path_count": len(document["paths"]),
                "method_count": method_count,
                "authentication_schemes_documented": bool(security_schemes or document.get("securityDefinitions")),
            }
    if completed_checks == 0:
        return {"state": "failed", "reason": "No documentation endpoint returned a response."}
    return {"state": "completed", "outcome": "not_found", "public": False, "checked_paths": list(DOC_PATHS)}


def _record_change(db: Session, scan: Scan, asset: Asset, kind: str, details: dict) -> None:
    db.add(ScanChange(organization_id=scan.organization_id, scan_id=scan.id, asset_id=asset.id, hostname=asset.hostname, kind=kind, details=details))


def _tls_observation(hostname: str, approved_ips: list[str]) -> dict:
    candidates = [ip for ip in approved_ips if is_permitted_ip(ip, settings.allow_private_targets)]
    if not candidates:
        return {"state": "skipped", "reason": "No approved public address was available."}
    try:
        current_ips, _, _ = resolve_host(hostname)
        if not set(current_ips).intersection(candidates):
            return {"state": "skipped", "reason": "DNS answers changed before TLS inspection."}
        context = ssl.create_default_context()
        with socket.create_connection((candidates[0], 443), timeout=settings.request_timeout_seconds) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=hostname) as tls_socket:
                certificate = tls_socket.getpeercert()
                expires = datetime.strptime(certificate["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                return {
                    "state": "completed",
                    "valid": True,
                    "expires_at": expires.isoformat(),
                    "days_until_expiry": (expires - utc_now()).days,
                    "issuer": ", ".join(part[0][1] for part in certificate.get("issuer", []) if part),
                    "tls_version": tls_socket.version(),
                    "hostname_match": True,
                }
    except (OSError, ssl.SSLError, KeyError, ValueError) as exc:
        return {"state": "failed", "reason": type(exc).__name__}


def _add_finding(db: Session, scan: Scan, asset: Asset, title: str, category: str, severity: str, description: str, evidence: dict, recommendation: str) -> None:
    fingerprint = hashlib.sha256(f"{asset.id}:{category}:{title}".encode()).hexdigest()
    existing = db.scalar(select(Finding).where(Finding.fingerprint == fingerprint, Finding.status != "Resolved"))
    if existing:
        existing.scan_id = scan.id
        existing.last_observed_at = utc_now()
        existing.evidence = evidence
        existing.description = description
        existing.severity = severity
        return
    db.add(Finding(organization_id=scan.organization_id, asset_id=asset.id, scan_id=scan.id, fingerprint=fingerprint, title=title, category=category, severity=severity, description=description, evidence=evidence, recommendation=recommendation))


def execute_scan(db: Session, scan_id: int) -> None:
    scan = db.get(Scan, scan_id)
    if not scan:
        return
    try:
        scan.status = "running"
        db.commit()
        organization = db.get(Organization, scan.organization_id)
        previous_scan = db.scalar(select(Scan).where(Scan.organization_id == organization.id, Scan.id != scan.id, Scan.status.in_(["completed", "completed_with_warnings"])).order_by(Scan.started_at.desc()).limit(1))
        hostnames, ct_error = discover_ct(organization.root_domain)
        hostnames = list(dict.fromkeys([organization.root_domain, *hostnames]))[: settings.max_hosts_per_scan]
        scan_errors = [ct_error] if ct_error else []
        newly_seen = 0
        for hostname in hostnames:
            if not is_in_scope(hostname, organization.root_domain):
                continue
            ips, records, dns_errors = resolve_host(hostname)
            existing_asset = db.scalar(select(Asset).where(Asset.organization_id == organization.id, Asset.hostname == hostname))
            asset = existing_asset or Asset(organization_id=organization.id, hostname=hostname)
            if not existing_asset:
                db.add(asset)
                db.flush()
                newly_seen += 1
                _record_change(db, scan, asset, "new_asset", {"source": "certificate-transparency" if hostname != organization.root_domain else "authorized-root"})
            asset.last_seen = utc_now()
            asset.latest_scan_id = scan.id
            asset.status = "Active"
            asset.missed_scans = 0
            asset.ips = ips
            asset.discovery_sources = list(dict.fromkeys([*(asset.discovery_sources or []), "root-domain" if hostname == organization.root_domain else "certificate-transparency"]))
            if "api" in hostname.split("."):
                asset.asset_type = "API"
            elif hostname == organization.root_domain or hostname.startswith("www."):
                asset.asset_type = "Website"
            else:
                asset.asset_type = "Unknown"
            db.add(Observation(asset_id=asset.id, scan_id=scan.id, kind="dns", value={"records": records, "errors": dns_errors}))
            if previous_scan:
                previous_dns = db.scalar(select(Observation).where(Observation.asset_id == asset.id, Observation.scan_id == previous_scan.id, Observation.kind == "dns").order_by(Observation.id.desc()).limit(1))
                if previous_dns:
                    old_records = {(item["type"], item["value"]) for item in previous_dns.value.get("records", [])}
                    new_records = {(item["type"], item["value"]) for item in records}
                    added_records = sorted(new_records - old_records)
                    removed_records = sorted(old_records - new_records)
                    if added_records or removed_records:
                        _record_change(db, scan, asset, "dns_records_changed", {"added": added_records, "removed": removed_records})
            if dns_errors:
                scan_errors.append(f"{hostname}: DNS lookup had errors.")
            http_result = _http_observation(hostname, ips)
            if http_result.get("state") == "completed" and http_result.get("content_type", "").lower().startswith("text/html"):
                asset.asset_type = "Website"
            tls_result = _tls_observation(hostname, ips)
            db.add(Observation(asset_id=asset.id, scan_id=scan.id, kind="http", value=http_result))
            db.add(Observation(asset_id=asset.id, scan_id=scan.id, kind="tls", value=tls_result))
            if previous_scan:
                for kind, current in (("http", http_result), ("tls", tls_result)):
                    previous_observation = db.scalar(select(Observation).where(Observation.asset_id == asset.id, Observation.scan_id == previous_scan.id, Observation.kind == kind).order_by(Observation.id.desc()).limit(1))
                    if previous_observation:
                        old_value = {key: value for key, value in previous_observation.value.items() if key != "response_ms"}
                        new_value = {key: value for key, value in current.items() if key != "response_ms"}
                        if old_value != new_value:
                            _record_change(db, scan, asset, f"{kind}_observation_changed", {"previous": old_value, "current": new_value})
            api_doc = _api_document(hostname, ips)
            if api_doc is not None:
                db.add(Observation(asset_id=asset.id, scan_id=scan.id, kind="api_documentation", value=api_doc))
                if api_doc.get("public"):
                    asset.asset_type = "API"
                    _add_finding(db, scan, asset, "Public API documentation observed", "API documentation exposure", "Informational", "A limited safe GET request found an OpenAPI document publicly accessible. Public documentation is an exposure observation and does not establish that API operations are unauthenticated.", api_doc, "Confirm that public API documentation is intentional and does not disclose sensitive internal design details.")
            if http_result.get("state") == "completed":
                absent = [name for name, present in http_result["headers"].items() if not present]
                if absent:
                    _add_finding(db, scan, asset, "HTTP security headers are missing", "HTTP security headers", "Low", "One or more recommended browser security headers were not observed. This is a configuration observation, not proof of exploitability.", {"missing_headers": absent, "status_code": http_result["status_code"]}, "Review the application context and configure appropriate response headers.")
            if tls_result.get("state") == "completed" and tls_result.get("days_until_expiry", 999) <= 30:
                severity = "High" if tls_result["days_until_expiry"] <= 0 else "Medium"
                _add_finding(db, scan, asset, "TLS certificate expired or nearing expiry", "TLS configuration", severity, "The observed TLS certificate is expired or expires within 30 days.", {"expires_at": tls_result["expires_at"], "days_until_expiry": tls_result["days_until_expiry"]}, "Renew the certificate and confirm automated renewal is functioning.")
            active_findings = db.scalars(select(Finding).where(Finding.asset_id == asset.id, Finding.status.in_(["Open", "Acknowledged"]))).all()
            max_severity = max(({"Critical": 95, "High": 75, "Medium": 55, "Low": 30, "Informational": 10}.get(item.severity, 0) for item in active_findings), default=0)
            risk = calculate_risk(max_severity, 80 if ips else 0, 80 if active_findings else 40, 50)
            asset.risk_score = risk["score"]
            asset.risk_details = risk
        for unseen_asset in db.scalars(select(Asset).where(Asset.organization_id == organization.id, Asset.latest_scan_id != scan.id)).all():
            unseen_asset.missed_scans += 1
            unseen_asset.status = "Inactive" if unseen_asset.missed_scans >= 3 else "Not observed in latest scan"
            _record_change(db, scan, unseen_asset, "asset_not_observed", {"consecutive_missed_scans": unseen_asset.missed_scans, "status": unseen_asset.status})
        scan.assets_found = newly_seen
        db.flush()
        scan.findings_found = len(db.scalars(select(Finding).where(Finding.scan_id == scan.id)).all())
        scan.status = "completed_with_warnings" if scan_errors else "completed"
        scan.error = "\n".join(scan_errors[:20]) if scan_errors else None
        scan.finished_at = utc_now()
        db.commit()
    except Exception as exc:
        db.rollback()
        failed_scan = db.get(Scan, scan_id)
        if failed_scan:
            failed_scan.status = "failed"
            failed_scan.error = type(exc).__name__
            failed_scan.finished_at = utc_now()
            db.commit()
        logger.exception("Scan %s failed", scan_id)