from urllib.parse import parse_qs, urlencode, urlsplit

DEFAULT_PORTS = {'http': 80, 'https': 443}

def normalize_path(path: str) -> str:
    segments = path.split('/')
    normalized_segments = []
    for segment in segments:
        if segment == '..':
            if normalized_segments:
                normalized_segments.pop()
        elif segment == '.' or segment == '':
            continue
        else:
            normalized_segments.append(segment)

    return '/' + '/'.join(normalized_segments)

def normalize_query(query: str) -> str:
    query_params = parse_qs(query, keep_blank_values=True)
    sorted_params = sorted((key, value) for key, values in query_params.items() for value in values)
    return urlencode(sorted_params)

def normalize_url(url: str) -> str:
    url_parts = urlsplit(url)
    scheme = url_parts.scheme.lower()
    host = url_parts.hostname.lower() if url_parts.hostname else ''
    port = url_parts.port
    if port is not None and port == DEFAULT_PORTS.get(scheme):
        port = None    
    path = normalize_path(url_parts.path)
    query = normalize_query(url_parts.query)
    normalized_url = scheme + '://' + host
    if port:
        normalized_url += ':' + str(port)
    normalized_url += path
    if query:
        normalized_url += '?' + query
    return normalized_url