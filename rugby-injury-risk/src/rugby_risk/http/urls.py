from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonicalize_url(url: str, params: dict[str, str] | None = None) -> str:
    """Sort query params, drop fragment and `utm_*` tracking params, lowercase scheme/host."""
    parts = urlsplit(url)
    query = [*parse_qsl(parts.query, keep_blank_values=True), *(params or {}).items()]
    kept = sorted((k, v) for k, v in query if not k.lower().startswith("utm_"))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(kept), ""))
