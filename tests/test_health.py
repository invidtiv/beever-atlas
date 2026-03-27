"""Tests for FastAPI health endpoint and DependencyHealth registry."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from beever_atlas.infra.health import DependencyHealth, HealthCheckResult


class TestDependencyHealth:
    @pytest.mark.asyncio
    async def test_register_and_check_healthy(self):
        registry = DependencyHealth()

        async def healthy_check():
            pass

        registry.register("test_dep", healthy_check, timeout=5.0)
        result = await registry.check("test_dep")
        assert result.status == "up"
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_check_failing_dependency(self):
        registry = DependencyHealth()

        async def failing_check():
            raise ConnectionError("Connection refused")

        registry.register("bad_dep", failing_check, timeout=5.0)
        result = await registry.check("bad_dep")
        assert result.status == "down"
        assert result.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_check_timeout(self):
        registry = DependencyHealth()

        async def slow_check():
            await asyncio.sleep(10)

        registry.register("slow_dep", slow_check, timeout=0.1)
        result = await registry.check("slow_dep")
        assert result.status == "down"
        assert result.error == "timeout"

    @pytest.mark.asyncio
    async def test_check_unregistered(self):
        registry = DependencyHealth()
        result = await registry.check("unknown")
        assert result.status == "down"
        assert result.error == "not registered"

    @pytest.mark.asyncio
    async def test_check_all(self):
        registry = DependencyHealth()

        async def ok():
            pass

        async def bad():
            raise RuntimeError("fail")

        registry.register("dep_a", ok, timeout=5.0)
        registry.register("dep_b", bad, timeout=5.0)
        results = await registry.check_all()
        assert len(results) == 2
        statuses = {r.name: r.status for r in results}
        assert statuses["dep_a"] == "up"
        assert statuses["dep_b"] == "down"

    def test_overall_status_all_healthy(self):
        registry = DependencyHealth()
        results = [
            HealthCheckResult(name="a", status="up", critical=True),
            HealthCheckResult(name="b", status="up", critical=False),
        ]
        assert registry.overall_status(results) == "healthy"

    def test_overall_status_degraded(self):
        registry = DependencyHealth()
        results = [
            HealthCheckResult(name="a", status="up", critical=True),
            HealthCheckResult(name="b", status="down", critical=False),
        ]
        assert registry.overall_status(results) == "degraded"

    def test_overall_status_unhealthy(self):
        registry = DependencyHealth()
        results = [
            HealthCheckResult(name="a", status="down", critical=True),
            HealthCheckResult(name="b", status="down", critical=False),
        ]
        assert registry.overall_status(results) == "unhealthy"

    def test_overall_status_all_critical_down_is_unhealthy(self):
        registry = DependencyHealth()
        results = [
            HealthCheckResult(name="a", status="down", critical=True),
            HealthCheckResult(name="b", status="up", critical=False),
        ]
        assert registry.overall_status(results) == "unhealthy"

    def test_overall_status_some_critical_down_is_degraded(self):
        registry = DependencyHealth()
        results = [
            HealthCheckResult(name="a", status="down", critical=True),
            HealthCheckResult(name="b", status="up", critical=True),
        ]
        assert registry.overall_status(results) == "degraded"


class TestHealthEndpoint:
    def test_health_endpoint_returns_valid_schema(self):
        """Health endpoint returns valid JSON even when services are down."""
        from beever_atlas.server.app import app

        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "components" in data
        assert "checked_at" in data
        for comp in data["components"].values():
            assert comp["status"] in ("up", "down")
            assert "latency_ms" in comp

    def test_cors_headers_present(self):
        from beever_atlas.server.app import app

        client = TestClient(app)
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in response.headers
