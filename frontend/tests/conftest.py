"""
Pytest configuration and shared fixtures for EcoSched test suite.
"""

import sys
import os
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import (
    ProcessInput,
    WorkloadType,
    RenewableProfile,
    RenewableInterval,
    ThermalConfig,
    EnergyConfig,
    EcoSchedConfig
)


@pytest.fixture
def sample_processes():
    """Basic 3-process workload."""
    return [
        ProcessInput(
            pid="P1",
            name="Job 1",
            arrival_time=0.0,
            burst_time=4.0,
            priority=2,
            workload_type=WorkloadType.NORMAL,
            cpu_intensity=0.5
        ),
        ProcessInput(
            pid="P2",
            name="Job 2",
            arrival_time=1.0,
            burst_time=3.0,
            priority=1,
            workload_type=WorkloadType.CRITICAL,
            cpu_intensity=0.8,
            deadline=6.0
        ),
        ProcessInput(
            pid="P3",
            name="Job 3",
            arrival_time=2.0,
            burst_time=5.0,
            priority=3,
            workload_type=WorkloadType.FLEXIBLE,
            cpu_intensity=0.6,
            deadline=15.0
        ),
    ]


@pytest.fixture
def default_thermal_config():
    return ThermalConfig(
        ambient_temperature=35.0,
        heating_coefficient=4.0,
        cooling_coefficient=0.25,
        warning_temperature=65.0,
        critical_temperature=80.0
    )


@pytest.fixture
def default_energy_config():
    return EnergyConfig(
        idle_power_watts=12.0,
        max_active_power_watts=65.0
    )


@pytest.fixture
def default_ecosched_config():
    return EcoSchedConfig(
        weight_urgency=3.0,
        weight_renewable=2.5,
        weight_aging=1.5,
        weight_thermal=2.0,
        renewable_high_threshold=0.70,
        renewable_low_threshold=0.35,
        min_slack_for_deferral=4.0,
        max_consecutive_deferrals=3,
        aging_threshold_ticks=8.0,
        base_quantum=2,
        min_quantum=1,
        max_quantum=4,
        context_switch_cost=0.0
    )


@pytest.fixture
def fluctuating_renewable_profile():
    return RenewableProfile(
        intervals=[
            RenewableInterval(start_time=0.0, end_time=5.0, availability=0.20),
            RenewableInterval(start_time=5.0, end_time=15.0, availability=0.85),
            RenewableInterval(start_time=15.0, end_time=30.0, availability=0.30),
        ],
        default_availability=0.40
    )
