import ipaddress
import os
import re
import socket
from pathlib import PurePosixPath
from typing import Optional
from urllib.parse import urlparse

from backend.core.config import settings

_SAFE_PATH_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SAFE_RELATIVE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]{1,255}$")


def sanitize_path_component(value: Optional[str]) -> Optional[str]:
    """Return a safe single path component (folder/id style), or None when invalid."""
    if value is None:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    if any(sep in candidate for sep in (os.sep, os.altsep) if sep):
        return None
    if candidate in {".", ".."} or ".." in candidate:
        return None
    if not _SAFE_PATH_COMPONENT_RE.fullmatch(candidate):
        return None
    return candidate


def sanitize_relative_segment(value: Optional[str]) -> Optional[str]:
    """Return a safe relative-path segment (filename/folder), or None when invalid."""
    if value is None:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    if any(sep in candidate for sep in ("/", "\\", os.sep, os.altsep) if sep):
        return None
    if candidate in {".", ".."} or ".." in candidate:
        return None
    if not _SAFE_RELATIVE_SEGMENT_RE.fullmatch(candidate):
        return None
    return candidate


def ensure_within_base_dir(path: str, base_dir: str) -> str:
    """Resolve a path and ensure it stays inside a base directory."""
    base_root = os.path.realpath(base_dir)
    resolved = os.path.realpath(path)
    try:
        if os.path.commonpath([resolved, base_root]) != base_root:
            raise ValueError("Resolved path escapes configured base directory.")
    except ValueError as exc:
        raise ValueError("Invalid path: cannot resolve against configured base directory.") from exc
    return resolved


def ensure_within_data_dir(path: str) -> str:
    """Resolve a path and ensure it stays inside DATA_DIR."""
    return ensure_within_base_dir(path, settings.DATA_DIR)


def safe_data_path(*parts: str) -> str:
    """Build a safe path rooted at DATA_DIR from trusted path components."""
    safe_parts: list[str] = []
    for part in parts:
        safe_part = sanitize_path_component(part)
        if not safe_part:
            raise ValueError("Invalid path component.")
        safe_parts.append(safe_part)

    return ensure_within_data_dir(os.path.join(settings.DATA_DIR, *safe_parts))


def data_url_to_local_path(url: Optional[str]) -> Optional[str]:
    """Convert a /data/... URL to a validated local DATA_DIR path."""
    raw = str(url or "").strip()
    if not raw.startswith("/data/"):
        return None

    relative = raw[len("/data/"):].lstrip("/")
    if not relative:
        return None

    posix_path = PurePosixPath(relative)
    if posix_path.is_absolute():
        return None

    safe_parts: list[str] = []
    for part in posix_path.parts:
        safe_part = sanitize_relative_segment(part)
        if not safe_part:
            return None
        safe_parts.append(safe_part)

    if not safe_parts:
        return None

    return ensure_within_data_dir(os.path.join(settings.DATA_DIR, *safe_parts))


def local_path_to_data_url(path: str) -> str:
    """Convert a local DATA_DIR path to canonical /data/... URL."""
    resolved = ensure_within_data_dir(path)
    data_root = os.path.realpath(settings.DATA_DIR)
    rel = os.path.relpath(resolved, data_root).replace("\\", "/")
    return f"/data/{rel}"


def assert_within_data_dir(path: str) -> str:
    """Sanitizer helper for taint-tracking static analysers (e.g. CodeQL).

    Functionally equivalent to ``ensure_within_data_dir`` but raises on
    violation rather than returning a bool. Use this at every path-sink to
    mark a previously user-influenced value as verified-safe for downstream
    filesystem operations.
    """
    return ensure_within_data_dir(path)


def assert_within_base_dir(path: str, base_dir: str) -> str:
    """Sanitizer helper: same as ``ensure_within_base_dir`` but raises on
    violation. See :func:`assert_within_data_dir` for rationale."""
    return ensure_within_base_dir(path, base_dir)


def _resolve_host_ips(host: str) -> list[ipaddress._BaseAddress]:
    """Resolve a hostname to its IP addresses (best-effort DNS lookup).

    Returns an empty list on failure. Used for SSRF checks before connecting.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError, ValueError):
        return []
    ips: list[ipaddress._BaseAddress] = []
    for info in infos:
        try:
            sockaddr = info[4]
            ips.append(ipaddress.ip_address(sockaddr[0]))
        except (KeyError, ValueError):
            continue
    return ips


def _ip_is_disallowed(ip: ipaddress._BaseAddress) -> bool:
    """Return True if the IP must not be contacted via user-supplied URLs."""
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def validate_provider_url(
    url: Optional[str],
    *,
    allow_private: Optional[bool] = None,
    max_length: Optional[int] = None,
) -> str:
    """Validate a user-supplied provider URL to prevent SSRF.

    Only ``http`` and ``https`` schemes are accepted. By default, hosts that
    resolve to loopback, RFC1918, link-local, multicast, or reserved IPs are
    rejected — set ``ALLOW_PRIVATE_NETWORK_MODELS=true`` to allow them
    (required for local Ollama / Automatic1111 setups).

    Returns the normalized URL on success. Raises ValueError on rejection.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    normalized = url.strip()
    if not normalized:
        raise ValueError("URL must be a non-empty string.")

    max_len = max_length if max_length is not None else settings.MAX_PROVIDER_URL_LENGTH
    if len(normalized) > max_len:
        raise ValueError(f"URL exceeds maximum length of {max_len} characters.")

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL scheme must be http or https.")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname.")

    if allow_private is None:
        allow_private = settings.ALLOW_PRIVATE_NETWORK_MODELS

    if not allow_private:
        ips = _resolve_host_ips(parsed.hostname)
        # When the host is a literal IP, getaddrinfo returns it as-is.
        # When it is unresolvable, treat as suspicious and reject.
        if not ips:
            raise ValueError("Could not resolve hostname.")
        for ip in ips:
            if _ip_is_disallowed(ip):
                raise ValueError(
                    "URL points to a private/loopback address. Set "
                    "ALLOW_PRIVATE_NETWORK_MODELS=true to allow local providers."
                )

    return normalized
