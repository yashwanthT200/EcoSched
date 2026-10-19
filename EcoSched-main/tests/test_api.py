"""
Integration and API tests for FastAPI endpoints, request validation, and CORS.
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verify /health returns 200 and healthy service status."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "EcoSched" in data["service"]


def test_get_algorithms_endpoint():
    """Verify /api/algorithms lists all five algorithms and configuration schema."""
    res = client.get("/api/algorithms")
    assert res.status_code == 200
    data = res.json()
    alg_ids = [a["id"] for a in data["algorithms"]]
    assert set(alg_ids) == {"fcfs", "sjf", "round_robin", "priority", "ecosched"}
    assert "default_configurations" in data


def test_get_examples_endpoint():
    """Verify /api/examples returns preset workloads and environment profiles."""
    res = client.get("/api/examples")
    assert res.status_code == 200
    data = res.json()
    assert "balanced_mix" in data["workloads"]
    assert "diurnal_solar" in data["renewable_profiles"]
    assert "standard_datacenter" in data["thermal_profiles"]


def test_post_simulate_success():
    """Verify /api/simulate runs successfully and returns full schema."""
    payload = {
        "processes": [
            {
                "pid": "P1",
                "arrival_time": 0.0,
                "burst_time": 4.0,
                "workload_type": "critical",
                "priority": 1
            },
            {
                "pid": "P2",
                "arrival_time": 1.0,
                "burst_time": 5.0,
                "workload_type": "flexible",
                "priority": 3
            }
        ],
        "algorithm": "ecosched"
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["algorithm"] == "ecosched"
    assert len(data["intervals"]) > 0
    assert len(data["process_metrics"]) == 2
    assert "system_metrics" in data
    assert data["system_metrics"]["makespan"] >= 9.0


def test_post_compare_success():
    """Verify /api/compare executes all five algorithms against identical workload."""
    payload = {
        "processes": [
            {"pid": "P1", "arrival_time": 0.0, "burst_time": 4.0, "priority": 2},
            {"pid": "P2", "arrival_time": 1.0, "burst_time": 3.0, "priority": 1},
            {"pid": "P3", "arrival_time": 2.0, "burst_time": 2.0, "priority": 3},
        ],
        "time_quantum": 2
    }
    res = client.post("/api/compare", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Must contain results for each algorithm
    assert set(data["results"].keys()) == {"fcfs", "sjf", "round_robin", "priority", "ecosched"}
    # Summary table must have 5 rows
    assert len(data["summary_table"]) == 5
    assert data["workload_summary"]["process_count"] == 3


def test_validation_empty_processes():
    """Reject empty process list with clear error."""
    payload = {
        "processes": [],
        "algorithm": "fcfs"
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 422
    assert "at least one process" in str(res.json()).lower()


def test_validation_duplicate_pid():
    """Reject duplicate process IDs."""
    payload = {
        "processes": [
            {"pid": "P1", "arrival_time": 0.0, "burst_time": 2.0},
            {"pid": "P1", "arrival_time": 1.0, "burst_time": 3.0},
        ],
        "algorithm": "fcfs"
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 422
    assert "duplicate" in str(res.json()).lower()


def test_validation_negative_arrival_time():
    """Reject negative arrival time."""
    payload = {
        "processes": [
            {"pid": "P1", "arrival_time": -2.0, "burst_time": 4.0}
        ],
        "algorithm": "fcfs"
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 422


def test_validation_non_positive_burst_time():
    """Reject zero or negative burst time."""
    payload = {
        "processes": [
            {"pid": "P1", "arrival_time": 0.0, "burst_time": 0.0}
        ],
        "algorithm": "fcfs"
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 422


def test_validation_deadline_earlier_than_arrival():
    """Reject deadline set earlier than arrival time."""
    payload = {
        "processes": [
            {"pid": "P1", "arrival_time": 5.0, "burst_time": 3.0, "deadline": 4.0}
        ],
        "algorithm": "fcfs"
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 422
    assert "deadline" in str(res.json()).lower()


def test_validation_invalid_cpu_intensity():
    """Reject CPU intensity outside [0.0, 1.0]."""
    payload = {
        "processes": [
            {"pid": "P1", "arrival_time": 0.0, "burst_time": 3.0, "cpu_intensity": 1.5}
        ],
        "algorithm": "fcfs"
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 422


def test_cors_headers_present():
    """Verify CORS headers allow cross-origin requests for decoupled frontend."""
    headers = {"Origin": "http://localhost:3000"}
    res = client.get("/health", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]


def test_get_datasets_endpoint():
    """Verify /api/datasets returns authentic real-world dataset documentation."""
    res = client.get("/api/datasets")
    assert res.status_code == 200
    data = res.json()
    assert "datasets" in data
    dataset_ids = [d["id"] for d in data["datasets"]]
    assert "caiso_real_solar_24h" in dataset_ids
    assert "spec_cpu_benchmarks" in dataset_ids


def test_real_world_presets_exist():
    """Verify /api/examples returns SPEC CPU and CAISO solar real-world presets."""
    res = client.get("/api/examples")
    assert res.status_code == 200
    data = res.json()
    assert "spec_cpu_benchmarks" in data["workloads"]
    assert "caiso_real_solar_24h" in data["renewable_profiles"]
