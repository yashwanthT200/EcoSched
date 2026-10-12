"""
Tests for scheduling metrics, deadline validation, context switch counting,
and energy proxy estimations.
"""

from models import (
    ProcessInput,
    AlgorithmType,
    WorkloadType,
    SimulationRequest,
    RenewableProfile,
    EnergyConfig
)
from simulation import run_simulation


def test_standard_scheduling_formulas():
    """Verify standard formulas:
    - Turnaround = Completion - Arrival
    - Waiting = Turnaround - Burst
    - Response = First Start - Arrival
    """
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=4.0),
        ProcessInput(pid="P2", arrival_time=1.0, burst_time=3.0),
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.FCFS)
    res = run_simulation(req)

    # P1 runs [0, 4]:
    # Completion = 4.0, Turnaround = 4 - 0 = 4.0, Waiting = 4 - 4 = 0.0, Response = 0 - 0 = 0.0
    # P2 runs [4, 7]:
    # Completion = 7.0, Turnaround = 7 - 1 = 6.0, Waiting = 6 - 3 = 3.0, Response = 4 - 1 = 3.0
    p1 = next(p for p in res.process_metrics if p.pid == "P1")
    p2 = next(p for p in res.process_metrics if p.pid == "P2")

    assert p1.completion_time == 4.0
    assert p1.turnaround_time == 4.0
    assert p1.waiting_time == 0.0
    assert p1.response_time == 0.0

    assert p2.completion_time == 7.0
    assert p2.turnaround_time == 6.0
    assert p2.waiting_time == 3.0
    assert p2.response_time == 3.0

    sys = res.system_metrics
    assert sys.average_waiting_time == (0.0 + 3.0) / 2.0
    assert sys.average_turnaround_time == (4.0 + 6.0) / 2.0
    assert sys.average_response_time == (0.0 + 3.0) / 2.0
    assert sys.makespan == 7.0
    assert sys.throughput == round(2.0 / 7.0, 4)


def test_deadline_met_and_missed_tracking():
    """Verify deadline success tracking correctly identifies met and missed deadlines."""
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=3.0, deadline=4.0),   # Met (completes at 3 <= 4)
        ProcessInput(pid="P2", arrival_time=0.0, burst_time=5.0, deadline=6.0),   # Missed (completes at 8 > 6)
        ProcessInput(pid="P3", arrival_time=0.0, burst_time=2.0, deadline=None),  # No deadline
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.FCFS)
    res = run_simulation(req)

    p1 = next(p for p in res.process_metrics if p.pid == "P1")
    p2 = next(p for p in res.process_metrics if p.pid == "P2")
    p3 = next(p for p in res.process_metrics if p.pid == "P3")

    assert p1.deadline_met is True
    assert p2.deadline_met is False
    assert p3.deadline_met is None

    # Out of 2 deadlines, 1 succeeded = 50.0%
    assert res.system_metrics.deadline_success_rate == 50.0


def test_context_switch_counting():
    """Verify context switches are correctly counted across process switches."""
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=2.0),
        ProcessInput(pid="P2", arrival_time=0.0, burst_time=2.0),
        ProcessInput(pid="P3", arrival_time=0.0, burst_time=2.0),
    ]
    # Under Round Robin with quantum 1:
    # Sequence: P1(1), P2(1), P3(1), P1(1), P2(1), P3(1)
    # Transitions: P1->P2 (+1), P2->P3 (+1), P3->P1 (+1), P1->P2 (+1), P2->P3 (+1) => total 5 switches
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.ROUND_ROBIN, time_quantum=1)
    res = run_simulation(req)

    assert res.system_metrics.context_switches == 5


def test_energy_proxy_mathematics():
    """Verify energy proxy conservation: Total energy = Grid energy + Renewable energy."""
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=6.0, cpu_intensity=0.8),
    ]
    # 70% renewable
    req = SimulationRequest(
        processes=procs,
        algorithm=AlgorithmType.FCFS,
        renewable_profile=RenewableProfile(default_availability=0.70),
        energy_config=EnergyConfig(idle_power_watts=10.0, max_active_power_watts=60.0)
    )
    res = run_simulation(req)

    sys = res.system_metrics
    # Power = 10 + (60 - 10) * 0.8 = 50W.
    # Total energy = 50W * 6s = 300.0.
    # Renewable energy = 300 * 0.7 = 210.0.
    # Grid energy = 300 * 0.3 = 90.0.
    assert abs(sys.estimated_total_energy_proxy - 300.0) < 1.0
    assert abs(sys.estimated_renewable_energy_proxy - 210.0) < 1.0
    assert abs(sys.estimated_grid_energy_proxy - 90.0) < 1.0
    assert abs(sys.renewable_utilization_percent - 70.0) < 0.1


def test_reproducibility():
    """Verify running the simulation multiple times with identical inputs yields identical results."""
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=4.0, workload_type=WorkloadType.CRITICAL),
        ProcessInput(pid="P2", arrival_time=1.0, burst_time=6.0, workload_type=WorkloadType.FLEXIBLE),
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.ECOSCHED)
    res1 = run_simulation(req)
    res2 = run_simulation(req)

    assert res1.system_metrics == res2.system_metrics
    assert [i.model_dump() for i in res1.intervals] == [i.model_dump() for i in res2.intervals]
