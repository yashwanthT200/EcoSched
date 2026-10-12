"""
Tests specifically for EcoSched's adaptive scheduling policy:
- Urgency and deadline slack
- Renewable-aware bonus and deferral
- Thermal modeling and thermal guard protection
- Starvation prevention via aging and maximum deferral limits
- Adaptive quantum adjustments
- Dynamic explainability decisions
"""

from models import (
    ProcessInput,
    AlgorithmType,
    WorkloadType,
    SimulationRequest,
    RenewableProfile,
    RenewableInterval,
    ThermalConfig,
    EcoSchedConfig
)
from simulation import run_simulation


def test_ecosched_urgency_prioritizes_critical_and_tight_deadlines():
    """Verify EcoSched prioritizes critical tasks and tasks with tight slack over standard tasks."""
    procs = [
        ProcessInput(
            pid="P_NORM",
            arrival_time=0.0,
            burst_time=4.0,
            workload_type=WorkloadType.NORMAL,
            priority=2
        ),
        ProcessInput(
            pid="P_CRIT",
            arrival_time=0.0,
            burst_time=3.0,
            workload_type=WorkloadType.CRITICAL,
            priority=3,
            deadline=4.0  # Tight slack!
        )
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.ECOSCHED)
    res = run_simulation(req)

    # P_CRIT must be selected first despite lower base priority (3 vs 2) because it is critical with tight slack
    first_active = next(i for i in res.intervals if i.pid != "IDLE")
    assert first_active.pid == "P_CRIT"
    assert "Critical task priority" in first_active.reason or "Tight deadline" in first_active.reason


def test_ecosched_renewable_bonus_favors_flexible_in_green_surge():
    """Verify flexible tasks receive scheduling bonus when renewable availability is high."""
    procs = [
        ProcessInput(
            pid="P_NORMAL",
            arrival_time=0.0,
            burst_time=4.0,
            workload_type=WorkloadType.NORMAL,
            priority=2
        ),
        ProcessInput(
            pid="P_FLEX",
            arrival_time=0.0,
            burst_time=4.0,
            workload_type=WorkloadType.FLEXIBLE,
            priority=3,
            cpu_intensity=0.9
        )
    ]
    # Renewable availability is 95% (surplus green energy)
    green_profile = RenewableProfile(default_availability=0.95)
    req = SimulationRequest(
        processes=procs,
        algorithm=AlgorithmType.ECOSCHED,
        renewable_profile=green_profile
    )
    res = run_simulation(req)

    # Under 95% green energy, P_FLEX receives a large renewable bonus:
    # bonus = weight_renewable * 0.95 * (1 + 0.9) = 2.5 * 0.95 * 1.9 = 4.51
    # This boosts P_FLEX ahead of P_NORMAL
    first_interval = next(i for i in res.intervals if i.pid != "IDLE")
    assert first_interval.pid == "P_FLEX"
    assert "Favorable green energy" in first_interval.reason


def test_ecosched_defers_flexible_when_renewables_are_low_and_slack_is_ample():
    """Verify flexible task with ample deadline slack is deferred when renewable energy is scarce."""
    procs = [
        ProcessInput(
            pid="P_FLEX_DEFERRED",
            arrival_time=0.0,
            burst_time=3.0,
            workload_type=WorkloadType.FLEXIBLE,
            deadline=25.0  # Ample slack
        )
    ]
    # Very low renewable energy (10%)
    dirty_profile = RenewableProfile(default_availability=0.10)
    req = SimulationRequest(
        processes=procs,
        algorithm=AlgorithmType.ECOSCHED,
        renewable_profile=dirty_profile
    )
    res = run_simulation(req)

    # First interval must be an IDLE deferral because green energy is scarce and slack is large
    assert res.intervals[0].pid == "IDLE"
    assert "deferred due to low renewable availability" in res.intervals[0].reason


def test_ecosched_never_defers_urgent_or_tight_deadline_tasks():
    """Verify tasks are NOT deferred if slack is tight, even when renewables are scarce."""
    procs = [
        ProcessInput(
            pid="P_URGENT_FLEX",
            arrival_time=0.0,
            burst_time=4.0,
            workload_type=WorkloadType.FLEXIBLE,
            deadline=4.5  # Slack is 4.5 - 4.0 = 0.5 <= min_slack_for_deferral (4.0)
        )
    ]
    dirty_profile = RenewableProfile(default_availability=0.10)
    req = SimulationRequest(
        processes=procs,
        algorithm=AlgorithmType.ECOSCHED,
        renewable_profile=dirty_profile
    )
    res = run_simulation(req)

    # Must start immediately at t=0 without being deferred
    assert res.intervals[0].pid == "P_URGENT_FLEX"
    assert res.intervals[0].start == 0.0


def test_ecosched_starvation_prevention_aging_and_max_deferral():
    """Verify maximum consecutive deferrals prevent indefinite postponement."""
    procs = [
        ProcessInput(
            pid="P_BATCH",
            arrival_time=0.0,
            burst_time=2.0,
            workload_type=WorkloadType.FLEXIBLE,
            deadline=50.0
        )
    ]
    # Max consecutive deferrals = 2
    cfg = EcoSchedConfig(max_consecutive_deferrals=2)
    dirty_profile = RenewableProfile(default_availability=0.10)
    req = SimulationRequest(
        processes=procs,
        algorithm=AlgorithmType.ECOSCHED,
        renewable_profile=dirty_profile,
        ecosched_config=cfg
    )
    res = run_simulation(req)

    # Should defer at most 2 times (t=0..1, t=1..2), then MUST execute at t=2
    idle_count = sum(1 for i in res.intervals if i.pid == "IDLE")
    assert idle_count <= 2

    active_start = next(i for i in res.intervals if i.pid == "P_BATCH").start
    assert active_start == 2.0  # Executed right after max deferrals reached!


def test_ecosched_thermal_protection_guard_and_cooldown():
    """Verify thermal protection guard halts high-intensity tasks and initiates cooling when T >= critical."""
    procs = [
        ProcessInput(
            pid="P_HOT",
            arrival_time=0.0,
            burst_time=10.0,
            workload_type=WorkloadType.FLEXIBLE,
            cpu_intensity=1.0  # Max heating
        )
    ]
    # Start near critical temp
    therm_cfg = ThermalConfig(
        ambient_temperature=35.0,
        heating_coefficient=8.0,  # Fast heating
        cooling_coefficient=0.20,
        warning_temperature=50.0,
        critical_temperature=60.0
    )
    req = SimulationRequest(
        processes=procs,
        algorithm=AlgorithmType.ECOSCHED,
        thermal_config=therm_cfg
    )
    res = run_simulation(req)

    # Check that a thermal guard cooldown interval was recorded
    guard_intervals = [
        i for i in res.intervals
        if "Thermal guard" in i.reason or "cooldown" in i.reason
    ]
    assert len(guard_intervals) > 0, "Thermal guard should have activated during high heating"


def test_ecosched_adaptive_quantum_variation():
    """Verify quantum adapts: longer during high renewables, shorter during thermal pressure."""
    # Under high renewable availability, flexible task gets max_quantum (4)
    procs_green = [
        ProcessInput(
            pid="P_FLEX",
            arrival_time=0.0,
            burst_time=8.0,
            workload_type=WorkloadType.FLEXIBLE,
            cpu_intensity=0.5
        )
    ]
    green_profile = RenewableProfile(default_availability=0.85)
    req_green = SimulationRequest(
        processes=procs_green,
        algorithm=AlgorithmType.ECOSCHED,
        renewable_profile=green_profile,
        ecosched_config=EcoSchedConfig(base_quantum=2, max_quantum=4, min_quantum=1)
    )
    res_green = run_simulation(req_green)

    # First interval should run with quantum of 4
    first_dur = res_green.intervals[0].end - res_green.intervals[0].start
    assert first_dur == 4.0

    # In contrast, with tight deadline, quantum drops to min_quantum (1)
    procs_tight = [
        ProcessInput(
            pid="P_TIGHT",
            arrival_time=0.0,
            burst_time=4.0,
            workload_type=WorkloadType.CRITICAL,
            deadline=2.0
        )
    ]
    req_tight = SimulationRequest(
        processes=procs_tight,
        algorithm=AlgorithmType.ECOSCHED,
        ecosched_config=EcoSchedConfig(base_quantum=2, min_quantum=1)
    )
    res_tight = run_simulation(req_tight)
    first_tight_dur = res_tight.intervals[0].end - res_tight.intervals[0].start
    assert first_tight_dur == 1.0


def test_ecosched_explainable_reasons_in_decision_log():
    """Verify every scheduling decision logs human-readable context and rationale."""
    procs = [
        ProcessInput(
            pid="P1",
            arrival_time=0.0,
            burst_time=3.0,
            workload_type=WorkloadType.CRITICAL,
            deadline=4.0
        ),
        ProcessInput(
            pid="P2",
            arrival_time=0.0,
            burst_time=4.0,
            workload_type=WorkloadType.FLEXIBLE
        ),
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.ECOSCHED)
    res = run_simulation(req)

    assert len(res.decision_log) > 0
    for entry in res.decision_log:
        assert entry.reason is not None and len(entry.reason) > 0
        assert "time" in entry.model_dump()
        assert "selected_pid" in entry.model_dump()
