"""Tests for ``/health``, ``/metrics``, and the ``X-Request-ID`` middleware.

These endpoints don't touch the database, but they do go through the
application's lifespan (which initialises ``FastAPICache``). We therefore
still use the shared ``make_client`` fixture so the lifespan runs with an
in-memory cache backend, matching the production code path without
requiring Redis.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient


class TestHealth:
    def test_health_returns_expected_shape(
        self, make_client: Callable[[], TestClient]
    ) -> None:
        client = make_client()
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}


class TestMetrics:
    def test_metrics_endpoint_exposes_prometheus_output(
        self, make_client: Callable[[], TestClient]
    ) -> None:
        client = make_client()
        # Make at least one instrumented request so a counter is emitted.
        client.get("/health")

        resp = client.get("/metrics")
        assert resp.status_code == 200
        # prometheus-fastapi-instrumentator serves the default
        # ``text/plain; version=0.0.4`` Prometheus exposition format.
        content_type = resp.headers.get("content-type", "")
        assert content_type.startswith("text/plain"), content_type

        body = resp.text
        # The instrumentator exposes at least ``http_requests_total`` or
        # its configured equivalent (``http_request_duration_seconds`` also
        # always lands). Assert on the family name that exists in both
        # default builds.
        assert (
            "http_request_duration_seconds" in body
            or "http_requests_total" in body
        ), body[:500]


class TestRequestIdMiddleware:
    """``RequestContextMiddleware`` echoes or generates an ``X-Request-ID``."""

    def test_generates_new_request_id_when_absent(
        self, make_client: Callable[[], TestClient]
    ) -> None:
        client = make_client()
        resp = client.get("/health")
        assert resp.status_code == 200
        rid = resp.headers.get("x-request-id")
        assert rid is not None
        # The middleware uses ``uuid.uuid4().hex`` → 32 lowercase hex chars.
        assert len(rid) == 32
        assert all(c in "0123456789abcdef" for c in rid)

    def test_echoes_client_supplied_request_id(
        self, make_client: Callable[[], TestClient]
    ) -> None:
        client = make_client()
        supplied = "trace-abc-123"
        resp = client.get("/health", headers={"X-Request-ID": supplied})
        assert resp.status_code == 200
        assert resp.headers.get("x-request-id") == supplied

    def test_two_requests_get_independent_ids(
        self, make_client: Callable[[], TestClient]
    ) -> None:
        client = make_client()
        first = client.get("/health").headers["x-request-id"]
        second = client.get("/health").headers["x-request-id"]
        assert first != second, "request ids should not collide between calls"
