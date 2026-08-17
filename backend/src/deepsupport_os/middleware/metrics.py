"""Performance metrics collection and reporting."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class MetricsCollector:
    """Collect and report performance metrics."""
    
    def __init__(self):
        self.request_counts: dict[str, int] = defaultdict(int)
        self.response_times: dict[str, list[float]] = defaultdict(list)
        self.status_codes: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.start_time = time.time()
    
    def record_request(self, path: str, method: str, status_code: int, duration: float):
        """Record a request metric."""
        key = f"{method}:{path}"
        
        self.request_counts[key] += 1
        self.response_times[key].append(duration)
        self.status_codes[key][status_code] += 1
        
        # Keep only last 1000 response times per endpoint
        if len(self.response_times[key]) > 1000:
            self.response_times[key] = self.response_times[key][-1000:]
    
    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics summary."""
        metrics = {
            "uptime_seconds": time.time() - self.start_time,
            "endpoints": {},
        }
        
        for key, count in self.request_counts.items():
            response_times = self.response_times[key]
            status_codes = dict(self.status_codes[key])
            
            metrics["endpoints"][key] = {
                "request_count": count,
                "avg_response_time_ms": (
                    sum(response_times) / len(response_times) * 1000
                    if response_times else 0
                ),
                "min_response_time_ms": (
                    min(response_times) * 1000 if response_times else 0
                ),
                "max_response_time_ms": (
                    max(response_times) * 1000 if response_times else 0
                ),
                "p95_response_time_ms": (
                    sorted(response_times)[int(len(response_times) * 0.95)] * 1000
                    if response_times else 0
                ),
                "status_codes": status_codes,
            }
        
        return metrics
    
    def get_summary(self) -> dict[str, Any]:
        """Get a high-level summary of metrics."""
        total_requests = sum(self.request_counts.values())
        
        all_response_times = []
        for times in self.response_times.values():
            all_response_times.extend(times)
        
        return {
            "uptime_seconds": time.time() - self.start_time,
            "total_requests": total_requests,
            "unique_endpoints": len(self.request_counts),
            "avg_response_time_ms": (
                sum(all_response_times) / len(all_response_times) * 1000
                if all_response_times else 0
            ),
            "requests_per_minute": (
                total_requests / ((time.time() - self.start_time) / 60)
                if time.time() > self.start_time else 0
            ),
        }


# Global metrics collector
metrics_collector = MetricsCollector()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        path = request.url.path
        method = request.method
        status_code = response.status_code
        
        metrics_collector.record_request(path, method, status_code, duration)
        
        # Add timing header
        response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"
        
        return response


def get_metrics() -> dict[str, Any]:
    """Get detailed metrics."""
    return metrics_collector.get_metrics()


def get_metrics_summary() -> dict[str, Any]:
    """Get metrics summary."""
    return metrics_collector.get_summary()
