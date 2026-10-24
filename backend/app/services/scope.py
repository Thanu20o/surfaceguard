import ipaddress
import re


DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_domain(value: str) -> str:
    domain = value.strip().rstrip(".").lower()
    if not domain or len(domain) > 253 or ":" in domain:
        raise ValueError("Enter a valid DNS domain, not an IP address or URL.")
    try:
        ipaddress.ip_address(domain.strip("[]"))
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses are not accepted as authorized root domains.")
    labels = domain.split(".")
    if len(labels) < 2 or any(not DOMAIN_LABEL.fullmatch(label) for label in labels):
        raise ValueError("Enter a valid fully qualified domain name.")
    return domain


def is_in_scope(hostname: str, root_domain: str) -> bool:
    try:
        host = normalize_domain(hostname)
        root = normalize_domain(root_domain)
    except ValueError:
        return False
    return host == root or host.endswith("." + root)


def is_permitted_ip(value: str, allow_private: bool = False) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return allow_private or address.is_global