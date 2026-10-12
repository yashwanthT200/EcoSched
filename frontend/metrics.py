"""
EcoSched Metrics Calculation Engine.

Calculates standard OS scheduling metrics, thermal statistics,
and energy proxy estimations from simulation execution traces.
"""

from typing import List, Optional, Dict
from models import (
    ProcessMetricResult,
    SystemMetrics,
    ExecutionInterval,
    EnergyConfig
)


def calculate_process_metrics(
    processes_info: Dict[str, dict],
    intervals: List[ExecutionInterval]
) -> List[ProcessMetricResult]:
    """Calculate per-process scheduling metrics from execution history.
    
    Standard Formulas:
    - Turnaround Time = Completion Time - Arrival Time
    - Waiting Time = Turnaround Time - Burst Time
    - Response Time = First Start Time - Arrival Time
    """
    results: List[ProcessMetricResult] = []

    # Map intervals to PIDs
    pid_intervals_count: Dict[str, int] = {}
    first_starts: Dict[str, float] = {}
    completion_times: Dict[str, float] = {}

    for interval in intervals:
        pid = interval.pid
        if pid == "IDLE":
            continue

        pid_intervals_count[pid] = pid_intervals_count.get(pid, 0) + 1

        if pid not in first_starts:
            first_starts[pid] = interval.start
        completion_times[pid] = max(completion_times.get(pid, 0.0), interval.end)

    for pid, info in processes_info.items():
        arrival = float(info["arrival_time"])
        burst = float(info["burst_time"])
        completion = completion_times.get(pid, info.get("completion_time", arrival + burst))
        first_start = first_starts.get(pid, arrival)

        turnaround = max(0.0, completion - arrival)
        waiting = max(0.0, turnaround - burst)
        response = max(0.0, first_start - arrival)

        deadline = info.get("deadline")
        deadline_met: Optional[bool] = None
        if deadline is not None:
            deadline_met = completion <= (deadline + 1e-9)

        results.append(
            ProcessMetricResult(
                pid=pid,
                name=info.get("name", pid),
                arrival_time=round(arrival, 3),
                burst_time=round(burst, 3),
                priority=info.get("priority", 3),
                workload_type=info.get("workload_type", "normal"),
                completion_time=round(completion, 3),
                turnaround_time=round(turnaround, 3),
                waiting_time=round(waiting, 3),
                response_time=round(response, 3),
                deadline=round(deadline, 3) if deadline is not None else None,
                deadline_met=deadline_met,
                execution_intervals_count=pid_intervals_count.get(pid, 0)
            )
        )

    # Sort results deterministically by PID
    results.sort(key=lambda x: x.pid)
    return results


def calculate_system_metrics(
    process_metrics: List[ProcessMetricResult],
    intervals: List[ExecutionInterval],
    energy_config: EnergyConfig,
    makespan: float,
    peak_temp: float
) -> SystemMetrics:
    """Calculate system-level metrics, context switches, utilization, and energy proxy.
    
    Definitions:
    - Makespan: Time at which the entire workload finishes execution.
    - CPU Utilization: Total active process execution time divided by makespan (%).
    - Context Switches: Count of transitions between different running processes.
    - Throughput: Completed processes per unit time (N / makespan).
    - Energy Proxy: Modeled grid-energy and total-energy based on CPU intensity and renewable availability.
    """
    n = len(process_metrics)
    if n == 0:
        return SystemMetrics(
            average_waiting_time=0.0,
            average_turnaround_time=0.0,
            average_response_time=0.0,
            throughput=0.0,
            makespan=0.0,
            cpu_utilization=0.0,
            context_switches=0,
            deadline_success_rate=None,
            max_waiting_time=0.0,
            peak_modeled_temperature=round(peak_temp, 2),
            estimated_grid_energy_proxy=0.0,
            estimated_total_energy_proxy=0.0,
            estimated_renewable_energy_proxy=0.0,
            renewable_utilization_percent=0.0,
        )

    avg_wait = sum(p.waiting_time for p in process_metrics) / n
    avg_turnaround = sum(p.turnaround_time for p in process_metrics) / n
    avg_response = sum(p.response_time for p in process_metrics) / n
    max_wait = max(p.waiting_time for p in process_metrics)

    throughput = (n / makespan) if makespan > 0 else 0.0

    # CPU active duration & context switch counting
    total_active_time = 0.0
    context_switches = 0
    prev_pid: Optional[str] = None

    for interval in intervals:
        dur = max(0.0, interval.end - interval.start)
        if interval.pid != "IDLE":
            total_active_time += dur
            if prev_pid is not None and prev_pid != interval.pid:
                context_switches += 1
            prev_pid = interval.pid

    cpu_utilization = (total_active_time / makespan * 100.0) if makespan > 0 else 0.0
    cpu_utilization = min(100.0, max(0.0, cpu_utilization))

    # Deadline success rate
    deadlines_present = [p for p in process_metrics if p.deadline is not None]
    if deadlines_present:
        met_count = sum(1 for p in deadlines_present if p.deadline_met is True)
        deadline_success_rate = round((met_count / len(deadlines_present)) * 100.0, 2)
    else:
        deadline_success_rate = None

    # Energy calculations
    # P_active = P_idle + (P_max - P_idle) * cpu_intensity
    # E_total = sum(P * dt)
    # E_grid = sum(P * (1 - R) * dt)
    # E_renewable = sum(P * R * dt)
    total_energy_proxy = 0.0
    grid_energy_proxy = 0.0
    renewable_energy_proxy = 0.0

    idle_power = energy_config.idle_power_watts
    max_power = energy_config.max_active_power_watts
    active_power_range = max_power - idle_power

    for interval in intervals:
        dt = max(0.0, interval.end - interval.start)
        if dt <= 0:
            continue

        intensity = interval.cpu_intensity if interval.cpu_intensity is not None else 0.0
        if interval.pid == "IDLE":
            power = idle_power
        else:
            power = idle_power + (active_power_range * intensity)

        r_avail = interval.renewable_availability if interval.renewable_availability is not None else 0.5
        r_avail = max(0.0, min(1.0, r_avail))

        interval_total_energy = power * dt
        interval_grid_energy = power * (1.0 - r_avail) * dt
        interval_renewable_energy = power * r_avail * dt

        total_energy_proxy += interval_total_energy
        grid_energy_proxy += interval_grid_energy
        renewable_energy_proxy += interval_renewable_energy

    ren_util_pct = (renewable_energy_proxy / total_energy_proxy * 100.0) if total_energy_proxy > 0 else 0.0

    return SystemMetrics(
        average_waiting_time=round(avg_wait, 3),
        average_turnaround_time=round(avg_turnaround, 3),
        average_response_time=round(avg_response, 3),
        throughput=round(throughput, 4),
        makespan=round(makespan, 3),
        cpu_utilization=round(cpu_utilization, 2),
        context_switches=context_switches,
        deadline_success_rate=deadline_success_rate,
        max_waiting_time=round(max_wait, 3),
        peak_modeled_temperature=round(peak_temp, 2),
        estimated_grid_energy_proxy=round(grid_energy_proxy, 2),
        estimated_total_energy_proxy=round(total_energy_proxy, 2),
        estimated_renewable_energy_proxy=round(renewable_energy_proxy, 2),
        renewable_utilization_percent=round(ren_util_pct, 2),
    )
