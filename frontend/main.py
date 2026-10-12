"""
EcoSched FastAPI Application.

Provides RESTful endpoints for:
- Health check
- Available algorithms metadata
- Workload and environmental presets
- Single algorithm simulation
- Comparative multi-algorithm execution across identical workloads
"""

from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import (
    SimulationRequest,
    SimulationResponse,
    ComparisonRequest,
    ComparisonResponse,
    ProcessInput,
    WorkloadType,
    RenewableProfile,
    RenewableInterval,
    ThermalConfig,
    EnergyConfig,
    EcoSchedConfig
)
from simulation import run_simulation, run_comparison
from config import get_default_config_dict

app = FastAPI(
    title="EcoSched API",
    description=(
        "Renewable-Aware and Thermal-Guarded CPU Scheduling Simulator. "
        "Evaluates FCFS, SJF, Round Robin, Priority Scheduling, and EcoSched "
        "on performance, deadline adherence, thermal safety, and grid-energy proxy."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local and decoupled frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"], summary="Health check endpoint")
def health_check() -> Dict[str, str]:
    """Return health status of the EcoSched backend service."""
    return {
        "status": "healthy",
        "service": "EcoSched API",
        "version": "1.0.0"
    }


@app.get("/api/algorithms", tags=["Metadata"], summary="List supported algorithms")
def get_algorithms() -> Dict[str, Any]:
    """Return list of supported scheduling algorithms and parameter specifications."""
    return {
        "algorithms": [
            {
                "id": "fcfs",
                "name": "First Come First Serve",
                "type": "Non-preemptive",
                "description": "Executes processes strictly in arrival order until completion.",
                "parameters": {}
            },
            {
                "id": "sjf",
                "name": "Shortest Job First",
                "type": "Non-preemptive",
                "description": "Selects the ready process with the smallest execution burst time.",
                "parameters": {}
            },
            {
                "id": "round_robin",
                "name": "Round Robin",
                "type": "Preemptive",
                "description": "Time-sliced scheduling where each process runs up to a fixed quantum.",
                "parameters": {
                    "time_quantum": {
                        "type": "integer",
                        "default": 2,
                        "min": 1,
                        "description": "Fixed time slice allocated per dispatch"
                    }
                }
            },
            {
                "id": "priority",
                "name": "Priority Scheduling",
                "type": "Configurable (Preemptive / Non-preemptive)",
                "description": "Selects process with best priority (lower numeric value = higher priority).",
                "parameters": {
                    "priority_preemptive": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether a newly arrived higher-priority task preempts the running process"
                    }
                }
            },
            {
                "id": "ecosched",
                "name": "EcoSched (Adaptive Green Policy)",
                "type": "Preemptive / Adaptive",
                "description": (
                    "Dynamically adapts scheduling score and quantum based on workload urgency, "
                    "renewable energy availability, thermal modeled conditions, and starvation aging."
                ),
                "parameters": {
                    "ecosched_config": {
                        "weights": ["weight_urgency", "weight_renewable", "weight_aging", "weight_thermal"],
                        "thresholds": ["renewable_high_threshold", "renewable_low_threshold", "min_slack_for_deferral", "max_consecutive_deferrals"],
                        "quantums": ["base_quantum", "min_quantum", "max_quantum"]
                    }
                }
            }
        ],
        "default_configurations": get_default_config_dict()
    }


@app.get("/api/examples", tags=["Metadata"], summary="Presets for frontend workloads and environments")
def get_example_presets() -> Dict[str, Any]:
    """Provide realistic workloads and environmental profiles for frontend demos and evaluation."""
    return {
        "workloads": {
            "balanced_mix": {
                "name": "Balanced College Lab Workload",
                "description": "A realistic mix of interactive critical services, standard batch jobs, and flexible analytics tasks.",
                "processes": [
                    {
                        "pid": "P1",
                        "name": "Auth Service",
                        "arrival_time": 0.0,
                        "burst_time": 4.0,
                        "priority": 1,
                        "workload_type": "critical",
                        "cpu_intensity": 0.4,
                        "deadline": 10.0
                    },
                    {
                        "pid": "P2",
                        "name": "Web Server Worker",
                        "arrival_time": 1.0,
                        "burst_time": 5.0,
                        "priority": 2,
                        "workload_type": "normal",
                        "cpu_intensity": 0.6,
                        "deadline": 18.0
                    },
                    {
                        "pid": "P3",
                        "name": "Image Rendering Task",
                        "arrival_time": 2.0,
                        "burst_time": 6.0,
                        "priority": 4,
                        "workload_type": "flexible",
                        "cpu_intensity": 0.9,
                        "deadline": 30.0
                    },
                    {
                        "pid": "P4",
                        "name": "Database Backup",
                        "arrival_time": 4.0,
                        "burst_time": 4.0,
                        "priority": 5,
                        "workload_type": "flexible",
                        "cpu_intensity": 0.5,
                        "deadline": 35.0
                    },
                    {
                        "pid": "P5",
                        "name": "Urgent Health Monitor",
                        "arrival_time": 6.0,
                        "burst_time": 3.0,
                        "priority": 1,
                        "workload_type": "critical",
                        "cpu_intensity": 0.3,
                        "deadline": 12.0
                    }
                ]
            },
            "green_surge": {
                "name": "Solar Surge Opportunity",
                "description": "High renewable availability from t=5 to t=15 permits flexible compute to burst efficiently.",
                "processes": [
                    {
                        "pid": "P1",
                        "name": "Baseline Daemon",
                        "arrival_time": 0.0,
                        "burst_time": 3.0,
                        "priority": 3,
                        "workload_type": "normal",
                        "cpu_intensity": 0.4
                    },
                    {
                        "pid": "P2",
                        "name": "Heavy Model Training",
                        "arrival_time": 1.0,
                        "burst_time": 8.0,
                        "priority": 4,
                        "workload_type": "flexible",
                        "cpu_intensity": 0.85,
                        "deadline": 25.0
                    },
                    {
                        "pid": "P3",
                        "name": "Data Analytics Batch",
                        "arrival_time": 3.0,
                        "burst_time": 6.0,
                        "priority": 5,
                        "workload_type": "flexible",
                        "cpu_intensity": 0.75,
                        "deadline": 30.0
                    },
                    {
                        "pid": "P4",
                        "name": "Security Scan",
                        "arrival_time": 8.0,
                        "burst_time": 4.0,
                        "priority": 2,
                        "workload_type": "critical",
                        "cpu_intensity": 0.5,
                        "deadline": 16.0
                    }
                ]
            },
            "thermal_stress": {
                "name": "Thermal Stress & Protection",
                "description": "Continuous high-intensity workloads that test temperature escalation and thermal protection guards.",
                "processes": [
                    {
                        "pid": "P1",
                        "name": "Crypto Hash Worker",
                        "arrival_time": 0.0,
                        "burst_time": 8.0,
                        "priority": 3,
                        "workload_type": "flexible",
                        "cpu_intensity": 1.0
                    },
                    {
                        "pid": "P2",
                        "name": "Video Transcoder",
                        "arrival_time": 2.0,
                        "burst_time": 7.0,
                        "priority": 3,
                        "workload_type": "flexible",
                        "cpu_intensity": 0.95
                    },
                    {
                        "pid": "P3",
                        "name": "Telemetry Reporter",
                        "arrival_time": 4.0,
                        "burst_time": 3.0,
                        "priority": 1,
                        "workload_type": "critical",
                        "cpu_intensity": 0.2,
                        "deadline": 15.0
                    }
                ]
            }
        },
        "renewable_profiles": {
            "diurnal_solar": {
                "name": "Diurnal Solar Curve",
                "intervals": [
                    {"start_time": 0.0, "end_time": 5.0, "availability": 0.20},
                    {"start_time": 5.0, "end_time": 15.0, "availability": 0.85},
                    {"start_time": 15.0, "end_time": 30.0, "availability": 0.30}
                ],
                "default_availability": 0.30
            },
            "constant_green": {
                "name": "High Constant Hydro/Wind",
                "intervals": [],
                "default_availability": 0.90
            },
            "scarce_grid": {
                "name": "Fossil-Heavy Low Renewable",
                "intervals": [],
                "default_availability": 0.15
            }
        },
        "thermal_profiles": {
            "standard_datacenter": {
                "ambient_temperature": 35.0,
                "heating_coefficient": 4.0,
                "cooling_coefficient": 0.25,
                "warning_temperature": 65.0,
                "critical_temperature": 80.0
            },
            "hot_edge_gateway": {
                "ambient_temperature": 45.0,
                "heating_coefficient": 5.0,
                "cooling_coefficient": 0.18,
                "warning_temperature": 68.0,
                "critical_temperature": 82.0
            }
        }
    }


@app.post("/api/simulate", response_model=SimulationResponse, tags=["Simulation"], summary="Run single algorithm simulation")
def simulate(request: SimulationRequest) -> SimulationResponse:
    """Execute a single CPU scheduling simulation with specified algorithm, processes, and environment."""
    try:
        return run_simulation(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Simulation error: {str(e)}")


@app.post("/api/compare", response_model=ComparisonResponse, tags=["Simulation"], summary="Run multi-algorithm comparison")
def compare(request: ComparisonRequest) -> ComparisonResponse:
    """Execute FCFS, SJF, Round Robin, Priority, and EcoSched against identical workload and environment."""
    try:
        return run_comparison(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Comparison error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
