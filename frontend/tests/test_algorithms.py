"""
Tests for conventional CPU scheduling algorithms (FCFS, SJF, RR, Priority).
"""

from models import (
    ProcessInput,
    AlgorithmType,
    WorkloadType,
    SimulationRequest,
    RenewableProfile,
    ThermalConfig
)
from simulation import run_simulation


def test_fcfs_execution_order():
    """Verify FCFS schedules processes strictly by arrival time."""
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=4.0),
        ProcessInput(pid="P2", arrival_time=2.0, burst_time=2.0),
        ProcessInput(pid="P3", arrival_time=1.0, burst_time=1.0),
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.FCFS)
    res = run_simulation(req)

    # P1 arrives at 0 -> runs [0, 4]
    # At t=4, both P3 (arrived at 1) and P2 (arrived at 2) are ready.
    # P3 arrived before P2, so P3 runs [4, 5], then P2 runs [5, 7].
    active_intervals = [i for i in res.intervals if i.pid != "IDLE"]
    order = [i.pid for i in active_intervals]
    assert order == ["P1", "P3", "P2"]
    assert res.system_metrics.makespan == 7.0


def test_sjf_non_preemptive_selection():
    """Verify non-preemptive SJF picks the shortest job in the ready queue."""
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=6.0),
        ProcessInput(pid="P2", arrival_time=1.0, burst_time=2.0),
        ProcessInput(pid="P3", arrival_time=2.0, burst_time=8.0),
        ProcessInput(pid="P4", arrival_time=3.0, burst_time=3.0),
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.SJF)
    res = run_simulation(req)

    # P1 starts at 0 and runs until 6 (non-preemptive).
    # At t=6, P2 (burst 2), P3 (burst 8), P4 (burst 3) are ready.
    # Shortest is P2 (burst 2) -> runs [6, 8].
    # At t=8, next shortest is P4 (burst 3) -> runs [8, 11].
    # Then P3 (burst 8) -> runs [11, 19].
    active_intervals = [i for i in res.intervals if i.pid != "IDLE"]
    order = [i.pid for i in active_intervals]
    assert order == ["P1", "P2", "P4", "P3"]
    assert res.system_metrics.makespan == 19.0


def test_round_robin_time_quantum_slicing():
    """Verify Round Robin slices tasks by time quantum and rotates the queue."""
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=5.0),
        ProcessInput(pid="P2", arrival_time=0.0, burst_time=3.0),
        ProcessInput(pid="P3", arrival_time=0.0, burst_time=1.0),
    ]
    # Quantum = 2
    req = SimulationRequest(
        processes=procs,
        algorithm=AlgorithmType.ROUND_ROBIN,
        time_quantum=2
    )
    res = run_simulation(req)

    # T=0: P1 (rem 5), P2 (rem 3), P3 (rem 1)
    # [0, 2]: P1 runs 2 -> rem 3. Queue: P2, P3, P1
    # [2, 4]: P2 runs 2 -> rem 1. Queue: P3, P1, P2
    # [4, 5]: P3 runs 1 -> rem 0 (done!). Queue: P1, P2
    # [5, 7]: P1 runs 2 -> rem 1. Queue: P2, P1
    # [7, 8]: P2 runs 1 -> rem 0 (done!). Queue: P1
    # [8, 9]: P1 runs 1 -> rem 0 (done!).
    active_intervals = [i for i in res.intervals if i.pid != "IDLE"]
    sequence = [(i.pid, i.start, i.end) for i in active_intervals]
    expected = [
        ("P1", 0.0, 2.0),
        ("P2", 2.0, 4.0),
        ("P3", 4.0, 5.0),
        ("P1", 5.0, 7.0),
        ("P2", 7.0, 8.0),
        ("P1", 8.0, 9.0),
    ]
    assert sequence == expected
    assert res.system_metrics.makespan == 9.0


def test_priority_non_preemptive():
    """Verify non-preemptive priority selects ready task with best priority."""
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=4.0, priority=3),
        ProcessInput(pid="P2", arrival_time=1.0, burst_time=3.0, priority=1),
        ProcessInput(pid="P3", arrival_time=1.0, burst_time=2.0, priority=2),
    ]
    req = SimulationRequest(
        processes=procs,
        algorithm=AlgorithmType.PRIORITY,
        priority_preemptive=False
    )
    res = run_simulation(req)

    # P1 arrives first at 0 -> runs [0, 4] non-preemptively.
    # At t=4, P2 (priority 1) and P3 (priority 2) are ready.
    # P2 has higher priority (1 < 2) -> runs [4, 7].
    # P3 runs [7, 9].
    active_intervals = [i for i in res.intervals if i.pid != "IDLE"]
    order = [i.pid for i in active_intervals]
    assert order == ["P1", "P2", "P3"]


def test_priority_preemptive():
    """Verify preemptive priority immediately preempts current task when higher priority arrives."""
    procs = [
        ProcessInput(pid="P1", arrival_time=0.0, burst_time=6.0, priority=3),
        ProcessInput(pid="P2", arrival_time=2.0, burst_time=2.0, priority=1),
    ]
    req = SimulationRequest(
        processes=procs,
        algorithm=AlgorithmType.PRIORITY,
        priority_preemptive=True
    )
    res = run_simulation(req)

    # P1 runs from [0, 2].
    # At t=2, P2 arrives with priority 1 (higher than P1's priority 3).
    # P2 preempts P1 and runs [2, 4].
    # At t=4, P2 finishes and P1 resumes [4, 8].
    active = [i for i in res.intervals if i.pid != "IDLE"]
    assert active[0].pid == "P1"
    assert active[0].start == 0.0
    assert active[0].end == 2.0

    assert active[1].pid == "P2"
    assert active[1].start == 2.0
    assert active[1].end == 4.0

    assert active[2].pid == "P1"
    assert active[2].start == 4.0
    assert active[2].end == 8.0


def test_idle_cpu_periods():
    """Verify simulator properly records IDLE periods when ready queue is empty."""
    procs = [
        ProcessInput(pid="P1", arrival_time=3.0, burst_time=2.0),
        ProcessInput(pid="P2", arrival_time=8.0, burst_time=3.0),
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.FCFS)
    res = run_simulation(req)

    # Expected timeline:
    # [0, 3]: IDLE
    # [3, 5]: P1
    # [5, 8]: IDLE
    # [8, 11]: P2
    intervals = [(i.pid, i.start, i.end) for i in res.intervals]
    assert intervals == [
        ("IDLE", 0.0, 3.0),
        ("P1", 3.0, 5.0),
        ("IDLE", 5.0, 8.0),
        ("P2", 8.0, 11.0),
    ]
    assert res.system_metrics.makespan == 11.0
    assert res.system_metrics.cpu_utilization == round((5.0 / 11.0) * 100.0, 2)


def test_simultaneous_arrivals():
    """Verify deterministic tie-breaking when multiple processes arrive simultaneously."""
    procs = [
        ProcessInput(pid="P_B", arrival_time=0.0, burst_time=2.0),
        ProcessInput(pid="P_A", arrival_time=0.0, burst_time=2.0),
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.FCFS)
    res = run_simulation(req)

    order = [i.pid for i in res.intervals if i.pid != "IDLE"]
    assert order == ["P_A", "P_B"]


def test_execution_time_integrity():
    """Verify every process receives exactly its required burst time and no execution occurs before arrival."""
    procs = [
        ProcessInput(pid="P1", arrival_time=2.0, burst_time=4.0),
        ProcessInput(pid="P2", arrival_time=5.0, burst_time=3.5),
        ProcessInput(pid="P3", arrival_time=1.0, burst_time=2.5),
    ]
    req = SimulationRequest(processes=procs, algorithm=AlgorithmType.ROUND_ROBIN, time_quantum=1)
    res = run_simulation(req)

    pid_total_executed = {}
    for interval in res.intervals:
        if interval.pid == "IDLE":
            continue
        pid_total_executed[interval.pid] = pid_total_executed.get(interval.pid, 0.0) + (interval.end - interval.start)
        # Ensure no execution before arrival
        original = next(p for p in procs if p.pid == interval.pid)
        assert interval.start >= original.arrival_time, f"{interval.pid} started at {interval.start} before arrival {original.arrival_time}"

    for p in procs:
        executed = pid_total_executed[p.pid]
        assert abs(executed - p.burst_time) < 1e-6, f"{p.pid} expected burst {p.burst_time}, got {executed}"
