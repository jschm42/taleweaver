"""ASCII HTTP headers that preserve Unicode download filenames (RFC 6266/5987)."""

from urllib.parse import quote


def attachment_disposition(filename: str) -> str:
    return f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
