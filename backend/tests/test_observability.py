import os
import subprocess
import json

import pytest
import yaml
from httpx import AsyncClient


INFRA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "infra")


# ─── Test 1: Metrics endpoint returns Prometheus-format metrics ────────────

async def test_metrics_endpoint(client: AsyncClient, seed_data):
    await client.get("/health")
    await client.get("/health")

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "api_requests_total" in text
    assert "api_request_duration_seconds_total" in text


# ─── Test 2: Health endpoint returns healthy ───────────────────────────────

async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


# ─── Test 3: Metrics track request counts ──────────────────────────────────

async def test_metrics_track_requests(client: AsyncClient, seed_data):
    for _ in range(3):
        await client.get("/health")

    resp = await client.get("/metrics")
    text = resp.text
    assert "api_requests_total" in text
    for line in text.splitlines():
        if 'endpoint="/health"' in line and "api_requests_total" in line:
            count = int(float(line.split()[-1]))
            assert count >= 3
            break


# ─── Test 4: Backup script is valid bash ───────────────────────────────────

def test_backup_script_valid():
    backup_path = os.path.join(INFRA_DIR, "backup", "backup.sh")
    assert os.path.exists(backup_path)

    with open(backup_path) as f:
        content = f.read()
    assert "#!/usr/bin/env bash" in content
    assert "pg_dump" in content
    assert "S3_BUCKET" in content
    assert "TIMESTAMP" in content


# ─── Test 5: Restore test script is valid bash ─────────────────────────────

def test_restore_script_valid():
    restore_path = os.path.join(INFRA_DIR, "backup", "restore_test.sh")
    assert os.path.exists(restore_path)

    with open(restore_path) as f:
        content = f.read()
    assert "#!/usr/bin/env bash" in content
    assert "pg_restore" in content
    assert "Restore validation PASSED" in content


# ─── Test 6: Prometheus config is valid YAML ───────────────────────────────

def test_prometheus_config_valid():
    prom_path = os.path.join(INFRA_DIR, "monitoring", "prometheus.yml")
    assert os.path.exists(prom_path)

    with open(prom_path) as f:
        config = yaml.safe_load(f)

    assert "scrape_configs" in config
    job_names = [sc["job_name"] for sc in config["scrape_configs"]]
    assert "fastapi" in job_names
    assert "postgresql" in job_names
    assert "redis" in job_names
    assert "celery" in job_names


# ─── Test 7: Alert rules are valid YAML with expected alerts ──────────────

def test_alert_rules_valid():
    rules_path = os.path.join(INFRA_DIR, "monitoring", "alert_rules.yml")
    assert os.path.exists(rules_path)

    with open(rules_path) as f:
        config = yaml.safe_load(f)

    assert "groups" in config
    group = config["groups"][0]
    assert group["name"] == "academic_platform"
    alert_names = [r["alert"] for r in group["rules"]]
    assert "HighQueueLag" in alert_names
    assert "HighAPILatency" in alert_names
    assert "FailedJobs" in alert_names
    assert "DBConnectionExhaustion" in alert_names


# ─── Test 8: Grafana dashboards are valid JSON ────────────────────────────

def test_grafana_dashboards_valid():
    dashboards_dir = os.path.join(INFRA_DIR, "monitoring", "grafana", "dashboards")
    assert os.path.exists(dashboards_dir)

    expected = [
        "platform_overview.json",
        "academic_operations.json",
        "ai_usage.json",
        "plugin_health.json",
    ]

    for name in expected:
        path = os.path.join(dashboards_dir, name)
        assert os.path.exists(path), f"Dashboard {name} not found"
        with open(path) as f:
            dashboard = json.load(f)
        assert "dashboard" in dashboard
        assert "panels" in dashboard["dashboard"]
        assert len(dashboard["dashboard"]["panels"]) > 0


# ─── Test 9: CI workflow is valid YAML ─────────────────────────────────────

def test_ci_workflow_valid():
    ci_path = os.path.join(INFRA_DIR, "..", ".github", "workflows", "ci.yml")
    assert os.path.exists(ci_path)

    with open(ci_path) as f:
        config = yaml.safe_load(f)

    assert "jobs" in config
    assert "backend-tests" in config["jobs"]
    assert "frontend-tests" in config["jobs"]

    backend_steps = config["jobs"]["backend-tests"]["steps"]
    step_names = [s.get("name", "") for s in backend_steps]
    assert any("Security scan backend" in n for n in step_names)

    frontend_steps = config["jobs"]["frontend-tests"]["steps"]
    step_names = [s.get("name", "") for s in frontend_steps]
    assert any("Security scan frontend" in n for n in step_names)


# ─── Test 10: Metrics track error status codes ────────────────────────────

async def test_metrics_track_errors(client: AsyncClient, seed_data):
    await client.get("/api/v1/nonexistent-endpoint")

    resp = await client.get("/metrics")
    text = resp.text
    assert "api_requests_by_status" in text
