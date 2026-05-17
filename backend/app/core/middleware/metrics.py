import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_request_count: dict[str, int] = defaultdict(int)
_request_duration: dict[str, float] = defaultdict(float)
_request_errors: dict[str, int] = defaultdict(int)
_status_counts: dict[str, int] = defaultdict(int)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start

        endpoint = request.url.path
        method = request.method
        status = str(response.status_code)

        key = f"{method}:{endpoint}"
        _request_count[key] += 1
        _request_duration[key] += duration
        _status_counts[f"{key}:{status}"] += 1

        if response.status_code >= 500:
            _request_errors[key] += 1

        return response


def get_metrics_text() -> str:
    lines = []

    lines.append("# HELP api_requests_total Total API requests")
    lines.append("# TYPE api_requests_total counter")
    for key, count in _request_count.items():
        method, endpoint = key.split(":", 1)
        lines.append(
            f'api_requests_total{{method="{method}",endpoint="{endpoint}"}} {count}'
        )

    lines.append("# HELP api_request_duration_seconds_total Total request duration")
    lines.append("# TYPE api_request_duration_seconds_total counter")
    for key, duration in _request_duration.items():
        method, endpoint = key.split(":", 1)
        lines.append(
            f'api_request_duration_seconds_total{{method="{method}",endpoint="{endpoint}"}} {duration:.6f}'
        )

    lines.append("# HELP api_request_errors_total Total 5xx errors")
    lines.append("# TYPE api_request_errors_total counter")
    for key, count in _request_errors.items():
        method, endpoint = key.split(":", 1)
        lines.append(
            f'api_request_errors_total{{method="{method}",endpoint="{endpoint}"}} {count}'
        )

    lines.append("# HELP api_requests_by_status Total requests by status code")
    lines.append("# TYPE api_requests_by_status counter")
    for key, count in _status_counts.items():
        parts = key.split(":")
        method, endpoint, status = parts[0], parts[1], parts[2]
        lines.append(
            f'api_requests_by_status{{method="{method}",endpoint="{endpoint}",status="{status}"}} {count}'
        )

    return "\n".join(lines) + "\n"
