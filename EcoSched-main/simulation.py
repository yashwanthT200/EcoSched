"""
EcoSched Simulation Engine.

Simulates CPU execution traces, environmental interactions (renewables & thermals),
and generates execution intervals, per-process results, and aggregate metrics.
Supports independent Python execution without FastAPI.
"""

from typing import List, Dict, Optional, Any, Tuple
from models import (
    SimulationRequest,
    SimulationResponse,
    ComparisonRequest,
    ComparisonResponse,
    ComparisonSummaryRow,
    ExecutionInterval,
    SimulationDecisionLog,
    TimeSeriesPoint,
    AlgorithmType,
    WorkloadType,
    ThermalConfig,
    EnergyConfig,
    RenewableProfile,
    EcoSchedConfig,
    ProcessInput
)
from scheduler_engine import (
    ProcessControlBlock,
    ThermalSimulator,
    EcoSchedPolicy
)
from metrics import (
    calculate_process_metrics,
    calculate_system_metrics
)


def _record_time_series_ticks(
    time_series: List[TimeSeriesPoint],
    start_time: float,
    end_time: float,
    active_pid: str,
    thermal_sim: ThermalSimulator,
    renewable_profile: RenewableProfile
):
    """Record granular time-series sample points for frontend charting."""
    t = start_time
    # Record at start
    time_series.append(
        TimeSeriesPoint(
            time=round(t, 2),
            active_pid=active_pid,
            modeled_temperature=round(thermal_sim.current_temp, 2),
            renewable_availability=round(renewable_profile.get_availability(t), 2)
        )
    )
    # If interval is long, record intermediate integer ticks
    next_tick = int(start_time) + 1.0
    while next_tick < end_time - 1e-6:
        time_series.append(
            TimeSeriesPoint(
                time=round(next_tick, 2),
                active_pid=active_pid,
                modeled_temperature=round(thermal_sim.current_temp, 2),
                renewable_availability=round(renewable_profile.get_availability(next_tick), 2)
            )
        )
        next_tick += 1.0


def _merge_intervals(raw_intervals: List[ExecutionInterval]) -> List[ExecutionInterval]:
    """Merge contiguous intervals of the same process if reasons and conditions align."""
    if not raw_intervals:
        return []

    merged: List[ExecutionInterval] = []
    current = raw_intervals[0].model_copy()

    for nxt in raw_intervals[1:]:
        # Merge if same pid, adjacent timestamps, and similar reason
        if (
            nxt.pid == current.pid
            and abs(nxt.start - current.end) < 1e-6
            and nxt.reason == current.reason
            and nxt.cpu_intensity == current.cpu_intensity
        ):
            current.end = nxt.end
            current.modeled_temp_end = nxt.modeled_temp_end
        else:
            merged.append(current)
            current = nxt.model_copy()
    merged.append(current)
    return merged


def simulate_fcfs(
    pcbs: List[ProcessControlBlock],
    thermal_config: ThermalConfig,
    renewable_profile: RenewableProfile
) -> Tuple[List[ExecutionInterval], List[SimulationDecisionLog], List[TimeSeriesPoint], float]:
    """First-Come, First-Served (FCFS) Non-Preemptive Simulation."""
    thermal_sim = ThermalSimulator(thermal_config)
    intervals: List[ExecutionInterval] = []
    decision_logs: List[SimulationDecisionLog] = []
    time_series: List[TimeSeriesPoint] = []

    unstarted = sorted(pcbs, key=lambda x: (x.arrival_time, x.pid))
    ready_queue: List[ProcessControlBlock] = []
    current_time = 0.0

    while unstarted or ready_queue:
        # Check newly arrived
        while unstarted and unstarted[0].arrival_time <= current_time + 1e-9:
            ready_queue.append(unstarted.pop(0))

        if not ready_queue:
            # CPU is idle until next arrival
            next_arr = unstarted[0].arrival_time
            dur = next_arr - current_time
            t_start, t_end = thermal_sim.update(dur, is_active=False, cpu_intensity=0.0)
            ren = renewable_profile.get_availability(current_time)

            intervals.append(
                ExecutionInterval(
                    pid="IDLE",
                    start=round(current_time, 3),
                    end=round(next_arr, 3),
                    reason="No processes in ready queue; CPU idling",
                    workload_type=None,
                    cpu_intensity=0.0,
                    modeled_temp_start=round(t_start, 2),
                    modeled_temp_end=round(t_end, 2),
                    renewable_availability=round(ren, 2)
                )
            )
            _record_time_series_ticks(time_series, current_time, next_arr, "IDLE", thermal_sim, renewable_profile)
            current_time = next_arr
            continue

        # Sort ready queue by arrival time (tie-break by PID)
        ready_queue.sort(key=lambda x: (x.arrival_time, x.pid))
        selected = ready_queue.pop(0)

        if selected.first_start_time is None:
            selected.first_start_time = current_time

        dur = selected.remaining_time
        t_start, t_end = thermal_sim.update(dur, is_active=True, cpu_intensity=selected.cpu_intensity)
        ren = renewable_profile.get_availability(current_time)

        intervals.append(
            ExecutionInterval(
                pid=selected.pid,
                start=round(current_time, 3),
                end=round(current_time + dur, 3),
                reason=f"Earliest arrival time ({selected.arrival_time:.1f}) in ready queue",
                workload_type=selected.workload_type.value,
                cpu_intensity=round(selected.cpu_intensity, 2),
                modeled_temp_start=round(t_start, 2),
                modeled_temp_end=round(t_end, 2),
                renewable_availability=round(ren, 2)
            )
        )
        decision_logs.append(
            SimulationDecisionLog(
                time=round(current_time, 3),
                selected_pid=selected.pid,
                reason="Earliest arrival time (FCFS)",
                context={"arrival_time": selected.arrival_time, "burst_time": selected.burst_time}
            )
        )
        _record_time_series_ticks(time_series, current_time, current_time + dur, selected.pid, thermal_sim, renewable_profile)

        current_time += dur
        selected.remaining_time = 0.0
        selected.completion_time = current_time

    return intervals, decision_logs, time_series, thermal_sim.peak_temp


def simulate_sjf(
    pcbs: List[ProcessControlBlock],
    thermal_config: ThermalConfig,
    renewable_profile: RenewableProfile
) -> Tuple[List[ExecutionInterval], List[SimulationDecisionLog], List[TimeSeriesPoint], float]:
    """Shortest Job First (SJF) Non-Preemptive Simulation."""
    thermal_sim = ThermalSimulator(thermal_config)
    intervals: List[ExecutionInterval] = []
    decision_logs: List[SimulationDecisionLog] = []
    time_series: List[TimeSeriesPoint] = []

    unstarted = sorted(pcbs, key=lambda x: (x.arrival_time, x.pid))
    ready_queue: List[ProcessControlBlock] = []
    current_time = 0.0

    while unstarted or ready_queue:
        while unstarted and unstarted[0].arrival_time <= current_time + 1e-9:
            ready_queue.append(unstarted.pop(0))

        if not ready_queue:
            next_arr = unstarted[0].arrival_time
            dur = next_arr - current_time
            t_start, t_end = thermal_sim.update(dur, is_active=False, cpu_intensity=0.0)
            ren = renewable_profile.get_availability(current_time)

            intervals.append(
                ExecutionInterval(
                    pid="IDLE",
                    start=round(current_time, 3),
                    end=round(next_arr, 3),
                    reason="No processes in ready queue; CPU idling",
                    workload_type=None,
                    cpu_intensity=0.0,
                    modeled_temp_start=round(t_start, 2),
                    modeled_temp_end=round(t_end, 2),
                    renewable_availability=round(ren, 2)
                )
            )
            _record_time_series_ticks(time_series, current_time, next_arr, "IDLE", thermal_sim, renewable_profile)
            current_time = next_arr
            continue

        # Sort ready queue by burst time (tie-break by arrival time, then PID)
        ready_queue.sort(key=lambda x: (x.burst_time, x.arrival_time, x.pid))
        selected = ready_queue.pop(0)

        if selected.first_start_time is None:
            selected.first_start_time = current_time

        dur = selected.remaining_time
        t_start, t_end = thermal_sim.update(dur, is_active=True, cpu_intensity=selected.cpu_intensity)
        ren = renewable_profile.get_availability(current_time)

        intervals.append(
            ExecutionInterval(
                pid=selected.pid,
                start=round(current_time, 3),
                end=round(current_time + dur, 3),
                reason=f"Shortest burst time ({selected.burst_time:.1f}) in ready queue",
                workload_type=selected.workload_type.value,
                cpu_intensity=round(selected.cpu_intensity, 2),
                modeled_temp_start=round(t_start, 2),
                modeled_temp_end=round(t_end, 2),
                renewable_availability=round(ren, 2)
            )
        )
        decision_logs.append(
            SimulationDecisionLog(
                time=round(current_time, 3),
                selected_pid=selected.pid,
                reason="Shortest burst time (SJF)",
                context={"burst_time": selected.burst_time, "arrival_time": selected.arrival_time}
            )
        )
        _record_time_series_ticks(time_series, current_time, current_time + dur, selected.pid, thermal_sim, renewable_profile)

        current_time += dur
        selected.remaining_time = 0.0
        selected.completion_time = current_time

    return intervals, decision_logs, time_series, thermal_sim.peak_temp


def simulate_round_robin(
    pcbs: List[ProcessControlBlock],
    time_quantum: int,
    thermal_config: ThermalConfig,
    renewable_profile: RenewableProfile
) -> Tuple[List[ExecutionInterval], List[SimulationDecisionLog], List[TimeSeriesPoint], float]:
    """Round Robin Preemptive Simulation."""
    thermal_sim = ThermalSimulator(thermal_config)
    raw_intervals: List[ExecutionInterval] = []
    decision_logs: List[SimulationDecisionLog] = []
    time_series: List[TimeSeriesPoint] = []

    unstarted = sorted(pcbs, key=lambda x: (x.arrival_time, x.pid))
    ready_queue: List[ProcessControlBlock] = []
    current_time = 0.0

    while unstarted or ready_queue:
        # Admit all newly arrived processes up to current time
        while unstarted and unstarted[0].arrival_time <= current_time + 1e-9:
            ready_queue.append(unstarted.pop(0))

        if not ready_queue:
            next_arr = unstarted[0].arrival_time
            dur = next_arr - current_time
            t_start, t_end = thermal_sim.update(dur, is_active=False, cpu_intensity=0.0)
            ren = renewable_profile.get_availability(current_time)

            raw_intervals.append(
                ExecutionInterval(
                    pid="IDLE",
                    start=round(current_time, 3),
                    end=round(next_arr, 3),
                    reason="No processes in ready queue; CPU idling",
                    workload_type=None,
                    cpu_intensity=0.0,
                    modeled_temp_start=round(t_start, 2),
                    modeled_temp_end=round(t_end, 2),
                    renewable_availability=round(ren, 2)
                )
            )
            _record_time_series_ticks(time_series, current_time, next_arr, "IDLE", thermal_sim, renewable_profile)
            current_time = next_arr
            continue

        selected = ready_queue.pop(0)

        if selected.first_start_time is None:
            selected.first_start_time = current_time

        run_dur = min(float(time_quantum), selected.remaining_time)
        t_start, t_end = thermal_sim.update(run_dur, is_active=True, cpu_intensity=selected.cpu_intensity)
        ren = renewable_profile.get_availability(current_time)

        raw_intervals.append(
            ExecutionInterval(
                pid=selected.pid,
                start=round(current_time, 3),
                end=round(current_time + run_dur, 3),
                reason=f"Round Robin quantum slice (q={time_quantum})",
                workload_type=selected.workload_type.value,
                cpu_intensity=round(selected.cpu_intensity, 2),
                modeled_temp_start=round(t_start, 2),
                modeled_temp_end=round(t_end, 2),
                renewable_availability=round(ren, 2)
            )
        )
        decision_logs.append(
            SimulationDecisionLog(
                time=round(current_time, 3),
                selected_pid=selected.pid,
                reason=f"Round Robin dispatch (quantum={time_quantum})",
                context={"remaining_before": round(selected.remaining_time, 2), "duration": round(run_dur, 2)}
            )
        )
        _record_time_series_ticks(time_series, current_time, current_time + run_dur, selected.pid, thermal_sim, renewable_profile)

        old_time = current_time
        current_time += run_dur
        selected.remaining_time -= run_dur

        # Admit any processes that arrived strictly during this execution slice
        while unstarted and unstarted[0].arrival_time <= current_time + 1e-9:
            ready_queue.append(unstarted.pop(0))

        if selected.remaining_time <= 1e-9:
            selected.completion_time = current_time
        else:
            ready_queue.append(selected)

    return raw_intervals, decision_logs, time_series, thermal_sim.peak_temp


def simulate_priority(
    pcbs: List[ProcessControlBlock],
    preemptive: bool,
    thermal_config: ThermalConfig,
    renewable_profile: RenewableProfile
) -> Tuple[List[ExecutionInterval], List[SimulationDecisionLog], List[TimeSeriesPoint], float]:
    """Priority Scheduling Simulation.
    
    Convention: Lower numeric value = higher priority (e.g. Priority 1 > Priority 3).
    Supports preemptive and non-preemptive modes.
    """
    thermal_sim = ThermalSimulator(thermal_config)
    raw_intervals: List[ExecutionInterval] = []
    decision_logs: List[SimulationDecisionLog] = []
    time_series: List[TimeSeriesPoint] = []

    unstarted = sorted(pcbs, key=lambda x: (x.arrival_time, x.pid))
    ready_queue: List[ProcessControlBlock] = []
    current_time = 0.0

    if not preemptive:
        # Non-preemptive priority
        while unstarted or ready_queue:
            while unstarted and unstarted[0].arrival_time <= current_time + 1e-9:
                ready_queue.append(unstarted.pop(0))

            if not ready_queue:
                next_arr = unstarted[0].arrival_time
                dur = next_arr - current_time
                t_start, t_end = thermal_sim.update(dur, is_active=False, cpu_intensity=0.0)
                ren = renewable_profile.get_availability(current_time)

                raw_intervals.append(
                    ExecutionInterval(
                        pid="IDLE",
                        start=round(current_time, 3),
                        end=round(next_arr, 3),
                        reason="No processes in ready queue; CPU idling",
                        workload_type=None,
                        cpu_intensity=0.0,
                        modeled_temp_start=round(t_start, 2),
                        modeled_temp_end=round(t_end, 2),
                        renewable_availability=round(ren, 2)
                    )
                )
                _record_time_series_ticks(time_series, current_time, next_arr, "IDLE", thermal_sim, renewable_profile)
                current_time = next_arr
                continue

            # Highest priority (lowest numeric value)
            ready_queue.sort(key=lambda x: (x.priority, x.arrival_time, x.pid))
            selected = ready_queue.pop(0)

            if selected.first_start_time is None:
                selected.first_start_time = current_time

            dur = selected.remaining_time
            t_start, t_end = thermal_sim.update(dur, is_active=True, cpu_intensity=selected.cpu_intensity)
            ren = renewable_profile.get_availability(current_time)

            raw_intervals.append(
                ExecutionInterval(
                    pid=selected.pid,
                    start=round(current_time, 3),
                    end=round(current_time + dur, 3),
                    reason=f"Highest priority ({selected.priority}) in ready queue [Non-preemptive]",
                    workload_type=selected.workload_type.value,
                    cpu_intensity=round(selected.cpu_intensity, 2),
                    modeled_temp_start=round(t_start, 2),
                    modeled_temp_end=round(t_end, 2),
                    renewable_availability=round(ren, 2)
                )
            )
            decision_logs.append(
                SimulationDecisionLog(
                    time=round(current_time, 3),
                    selected_pid=selected.pid,
                    reason=f"Priority {selected.priority} selected (Non-preemptive)",
                    context={"priority": selected.priority, "burst_time": selected.burst_time}
                )
            )
            _record_time_series_ticks(time_series, current_time, current_time + dur, selected.pid, thermal_sim, renewable_profile)

            current_time += dur
            selected.remaining_time = 0.0
            selected.completion_time = current_time

        return raw_intervals, decision_logs, time_series, thermal_sim.peak_temp

    else:
        # Preemptive priority: event-driven / tick-based simulation
        while unstarted or ready_queue:
            while unstarted and unstarted[0].arrival_time <= current_time + 1e-9:
                ready_queue.append(unstarted.pop(0))

            if not ready_queue:
                next_arr = unstarted[0].arrival_time
                dur = next_arr - current_time
                t_start, t_end = thermal_sim.update(dur, is_active=False, cpu_intensity=0.0)
                ren = renewable_profile.get_availability(current_time)

                raw_intervals.append(
                    ExecutionInterval(
                        pid="IDLE",
                        start=round(current_time, 3),
                        end=round(next_arr, 3),
                        reason="No processes in ready queue; CPU idling",
                        workload_type=None,
                        cpu_intensity=0.0,
                        modeled_temp_start=round(t_start, 2),
                        modeled_temp_end=round(t_end, 2),
                        renewable_availability=round(ren, 2)
                    )
                )
                _record_time_series_ticks(time_series, current_time, next_arr, "IDLE", thermal_sim, renewable_profile)
                current_time = next_arr
                continue

            ready_queue.sort(key=lambda x: (x.priority, x.arrival_time, x.pid))
            selected = ready_queue[0]

            if selected.first_start_time is None:
                selected.first_start_time = current_time

            # Determine maximum slice before next event (next arrival or task completion)
            step_dur = selected.remaining_time
            if unstarted:
                next_arrival_time = unstarted[0].arrival_time
                if next_arrival_time > current_time:
                    step_dur = min(step_dur, next_arrival_time - current_time)

            step_dur = max(0.5, min(step_dur, 1.0)) if step_dur > 1.0 else step_dur

            t_start, t_end = thermal_sim.update(step_dur, is_active=True, cpu_intensity=selected.cpu_intensity)
            ren = renewable_profile.get_availability(current_time)

            raw_intervals.append(
                ExecutionInterval(
                    pid=selected.pid,
                    start=round(current_time, 3),
                    end=round(current_time + step_dur, 3),
                    reason=f"Priority {selected.priority} executing [Preemptive]",
                    workload_type=selected.workload_type.value,
                    cpu_intensity=round(selected.cpu_intensity, 2),
                    modeled_temp_start=round(t_start, 2),
                    modeled_temp_end=round(t_end, 2),
                    renewable_availability=round(ren, 2)
                )
            )
            decision_logs.append(
                SimulationDecisionLog(
                    time=round(current_time, 3),
                    selected_pid=selected.pid,
                    reason=f"Preemptive Priority {selected.priority} step",
                    context={"priority": selected.priority, "remaining": round(selected.remaining_time, 2)}
                )
            )
            _record_time_series_ticks(time_series, current_time, current_time + step_dur, selected.pid, thermal_sim, renewable_profile)

            current_time += step_dur
            selected.remaining_time -= step_dur

            while unstarted and unstarted[0].arrival_time <= current_time + 1e-9:
                ready_queue.append(unstarted.pop(0))

            if selected.remaining_time <= 1e-9:
                selected.completion_time = current_time
                ready_queue.remove(selected)

        return _merge_intervals(raw_intervals), decision_logs, time_series, thermal_sim.peak_temp


def simulate_ecosched(
    pcbs: List[ProcessControlBlock],
    ecosched_config: EcoSchedConfig,
    thermal_config: ThermalConfig,
    renewable_profile: RenewableProfile
) -> Tuple[List[ExecutionInterval], List[SimulationDecisionLog], List[TimeSeriesPoint], float]:
    """EcoSched Adaptive Simulation Engine.
    
    Dynamically balances:
    - Urgency and deadline slack
    - Time-varying renewable energy availability
    - Thermal modeling and protection
    - Aging and maximum consecutive deferral limits to guarantee starvation-freedom
    - Adaptive time quantum
    """
    thermal_sim = ThermalSimulator(thermal_config)
    raw_intervals: List[ExecutionInterval] = []
    decision_logs: List[SimulationDecisionLog] = []
    time_series: List[TimeSeriesPoint] = []

    unstarted = sorted(pcbs, key=lambda x: (x.arrival_time, x.pid))
    ready_pool: List[ProcessControlBlock] = []
    current_time = 0.0

    while unstarted or ready_pool:
        # 1. Admit all processes arriving up to current_time
        while unstarted and unstarted[0].arrival_time <= current_time + 1e-9:
            ready_pool.append(unstarted.pop(0))

        if not ready_pool:
            # Idle until next arrival
            next_arr = unstarted[0].arrival_time
            dur = next_arr - current_time
            t_start, t_end = thermal_sim.update(dur, is_active=False, cpu_intensity=0.0)
            ren = renewable_profile.get_availability(current_time)

            raw_intervals.append(
                ExecutionInterval(
                    pid="IDLE",
                    start=round(current_time, 3),
                    end=round(next_arr, 3),
                    reason="No processes in ready pool; CPU idling",
                    workload_type=None,
                    cpu_intensity=0.0,
                    modeled_temp_start=round(t_start, 2),
                    modeled_temp_end=round(t_end, 2),
                    renewable_availability=round(ren, 2)
                )
            )
            _record_time_series_ticks(time_series, current_time, next_arr, "IDLE", thermal_sim, renewable_profile)
            current_time = next_arr
            continue

        current_temp = thermal_sim.current_temp
        renewable_avail = renewable_profile.get_availability(current_time)

        # 2. Check Thermal Protection Guard (T >= Critical Threshold)
        if current_temp >= thermal_config.critical_temperature:
            # Look for urgent tasks that MUST run to avoid deadline misses
            urgent_candidates = [
                p for p in ready_pool
                if p.workload_type == WorkloadType.CRITICAL or (p.slack_at(current_time) is not None and p.slack_at(current_time) <= ecosched_config.min_slack_for_deferral)
            ]

            if not urgent_candidates:
                # Can we run a low CPU intensity task to stay cool?
                cool_candidates = [p for p in ready_pool if p.cpu_intensity <= 0.35]
                if not cool_candidates:
                    # Enforce a thermal cooldown idle cycle
                    cooldown_dur = 1.0
                    t_start, t_end = thermal_sim.update(cooldown_dur, is_active=False, cpu_intensity=0.0)
                    raw_intervals.append(
                        ExecutionInterval(
                            pid="IDLE",
                            start=round(current_time, 3),
                            end=round(current_time + cooldown_dur, 3),
                            reason=f"Thermal guard activated: cooldown cycle enforced at {current_temp:.1f}°C (critical={thermal_config.critical_temperature:.1f}°C)",
                            workload_type=None,
                            cpu_intensity=0.0,
                            modeled_temp_start=round(t_start, 2),
                            modeled_temp_end=round(t_end, 2),
                            renewable_availability=round(renewable_avail, 2)
                        )
                    )
                    decision_logs.append(
                        SimulationDecisionLog(
                            time=round(current_time, 3),
                            selected_pid="IDLE",
                            reason=f"Thermal guard cooldown cycle at {current_temp:.1f}°C",
                            context={"current_temp": current_temp, "critical_temp": thermal_config.critical_temperature}
                        )
                    )
                    _record_time_series_ticks(time_series, current_time, current_time + cooldown_dur, "IDLE", thermal_sim, renewable_profile)
                    current_time += cooldown_dur
                    continue

        # 3. Renewable Deferral & Candidate Selection
        active_candidates: List[Tuple[ProcessControlBlock, float, Dict[str, Any], str]] = []
        deferred_tasks: List[ProcessControlBlock] = []

        for pcb in ready_pool:
            can_defer, defer_reason = EcoSchedPolicy.can_defer_flexible(
                pcb, current_time, renewable_avail, ecosched_config
            )
            if can_defer:
                deferred_tasks.append(pcb)
            else:
                score, details, reason = EcoSchedPolicy.evaluate_process(
                    pcb, current_time, current_temp, renewable_avail, thermal_config, ecosched_config
                )
                active_candidates.append((pcb, score, details, reason))

        # If ALL ready processes are deferred flexible tasks:
        if not active_candidates and deferred_tasks:
            # Idle for green energy arrival (or until deferral limit/slack threshold)
            for dp in deferred_tasks:
                dp.consecutive_deferrals += 1

            idle_dur = 1.0
            t_start, t_end = thermal_sim.update(idle_dur, is_active=False, cpu_intensity=0.0)
            raw_intervals.append(
                ExecutionInterval(
                    pid="IDLE",
                    start=round(current_time, 3),
                    end=round(current_time + idle_dur, 3),
                    reason=f"Flexible workload deferred due to low renewable availability (ren={renewable_avail:.2f})",
                    workload_type=None,
                    cpu_intensity=0.0,
                    modeled_temp_start=round(t_start, 2),
                    modeled_temp_end=round(t_end, 2),
                    renewable_availability=round(renewable_avail, 2)
                )
            )
            decision_logs.append(
                SimulationDecisionLog(
                    time=round(current_time, 3),
                    selected_pid="IDLE",
                    reason=f"All ready tasks deferred due to scarce green energy ({renewable_avail:.2f})",
                    context={"deferred_count": len(deferred_tasks), "renewable": renewable_avail}
                )
            )
            _record_time_series_ticks(time_series, current_time, current_time + idle_dur, "IDLE", thermal_sim, renewable_profile)
            current_time += idle_dur
            continue

        # If we have active candidates, pick the highest score!
        # Tie breaking:
        # 1. Total score descending
        # 2. Workload type (critical > normal > flexible)
        # 3. Base priority ascending (lower number = higher)
        # 4. Arrival time ascending
        # 5. PID ascending
        type_weight = {WorkloadType.CRITICAL: 3, WorkloadType.NORMAL: 2, WorkloadType.FLEXIBLE: 1}
        active_candidates.sort(
            key=lambda item: (
                -item[1],
                -type_weight[item[0].workload_type],
                item[0].priority,
                item[0].arrival_time,
                item[0].pid
            )
        )

        selected_pcb, best_score, score_details, explanation = active_candidates[0]

        # Selected process resets its consecutive deferrals counter
        selected_pcb.consecutive_deferrals = 0

        if selected_pcb.first_start_time is None:
            selected_pcb.first_start_time = current_time

        # 4. Compute Adaptive Quantum
        quantum = EcoSchedPolicy.compute_adaptive_quantum(
            selected_pcb, current_time, current_temp, renewable_avail, thermal_config, ecosched_config
        )
        run_dur = min(float(quantum), selected_pcb.remaining_time)

        # Context switch overhead check (if configured)
        if ecosched_config.context_switch_cost > 0.0 and raw_intervals and raw_intervals[-1].pid != selected_pcb.pid:
            cs_cost = ecosched_config.context_switch_cost
            t_start, t_end = thermal_sim.update(cs_cost, is_active=False, cpu_intensity=0.0)
            raw_intervals.append(
                ExecutionInterval(
                    pid="IDLE",
                    start=round(current_time, 3),
                    end=round(current_time + cs_cost, 3),
                    reason="Context switch dispatch overhead",
                    workload_type=None,
                    cpu_intensity=0.0,
                    modeled_temp_start=round(t_start, 2),
                    modeled_temp_end=round(t_end, 2),
                    renewable_availability=round(renewable_avail, 2)
                )
            )
            current_time += cs_cost

        # Execute selected task
        t_start, t_end = thermal_sim.update(run_dur, is_active=True, cpu_intensity=selected_pcb.cpu_intensity)

        raw_intervals.append(
            ExecutionInterval(
                pid=selected_pcb.pid,
                start=round(current_time, 3),
                end=round(current_time + run_dur, 3),
                reason=explanation,
                workload_type=selected_pcb.workload_type.value,
                cpu_intensity=round(selected_pcb.cpu_intensity, 2),
                modeled_temp_start=round(t_start, 2),
                modeled_temp_end=round(t_end, 2),
                renewable_availability=round(renewable_avail, 2)
            )
        )
        decision_logs.append(
            SimulationDecisionLog(
                time=round(current_time, 3),
                selected_pid=selected_pcb.pid,
                score=round(best_score, 2),
                reason=explanation,
                context={
                    "quantum": quantum,
                    "score_breakdown": score_details,
                    "modeled_temp": round(current_temp, 2),
                    "renewable": round(renewable_avail, 2)
                }
            )
        )
        _record_time_series_ticks(time_series, current_time, current_time + run_dur, selected_pcb.pid, thermal_sim, renewable_profile)

        current_time += run_dur
        selected_pcb.remaining_time -= run_dur

        if selected_pcb.remaining_time <= 1e-9:
            selected_pcb.completion_time = current_time
            ready_pool.remove(selected_pcb)

    return raw_intervals, decision_logs, time_series, thermal_sim.peak_temp


def run_simulation(request: SimulationRequest) -> SimulationResponse:
    """Execute a single simulation with the requested algorithm and configuration."""
    processes_info = {
        p.pid: {
            "name": p.name,
            "arrival_time": p.arrival_time,
            "burst_time": p.burst_time,
            "priority": p.priority,
            "workload_type": p.workload_type.value,
            "cpu_intensity": p.cpu_intensity,
            "deadline": p.deadline
        }
        for p in request.processes
    }

    # Instantiate fresh PCB copies for the simulation run
    pcbs = [ProcessControlBlock(p) for p in request.processes]

    thermal_cfg = request.thermal_config or ThermalConfig()
    renewable_prof = request.renewable_profile or RenewableProfile()
    energy_cfg = request.energy_config or EnergyConfig()
    ecosched_cfg = request.ecosched_config or EcoSchedConfig()

    alg = request.algorithm
    display_names = {
        AlgorithmType.FCFS: "First Come First Serve (FCFS)",
        AlgorithmType.SJF: "Shortest Job First (SJF)",
        AlgorithmType.ROUND_ROBIN: "Round Robin (RR)",
        AlgorithmType.PRIORITY: f"Priority Scheduling ({'Preemptive' if request.priority_preemptive else 'Non-Preemptive'})",
        AlgorithmType.ECOSCHED: "EcoSched (Renewable & Thermal Aware)"
    }

    params: Dict[str, Any] = {}

    if alg == AlgorithmType.FCFS:
        intervals, decision_logs, time_series, peak_temp = simulate_fcfs(
            pcbs, thermal_cfg, renewable_prof
        )
    elif alg == AlgorithmType.SJF:
        intervals, decision_logs, time_series, peak_temp = simulate_sjf(
            pcbs, thermal_cfg, renewable_prof
        )
    elif alg == AlgorithmType.ROUND_ROBIN:
        q = request.time_quantum or 2
        params["time_quantum"] = q
        intervals, decision_logs, time_series, peak_temp = simulate_round_robin(
            pcbs, q, thermal_cfg, renewable_prof
        )
    elif alg == AlgorithmType.PRIORITY:
        params["preemptive"] = request.priority_preemptive
        intervals, decision_logs, time_series, peak_temp = simulate_priority(
            pcbs, request.priority_preemptive, thermal_cfg, renewable_prof
        )
    elif alg == AlgorithmType.ECOSCHED:
        params["base_quantum"] = ecosched_cfg.base_quantum
        params["weights"] = {
            "urgency": ecosched_cfg.weight_urgency,
            "renewable": ecosched_cfg.weight_renewable,
            "aging": ecosched_cfg.weight_aging,
            "thermal": ecosched_cfg.weight_thermal
        }
        intervals, decision_logs, time_series, peak_temp = simulate_ecosched(
            pcbs, ecosched_cfg, thermal_cfg, renewable_prof
        )
    else:
        raise ValueError(f"Unsupported algorithm: {alg}")

    # Compute makespan from intervals
    makespan = intervals[-1].end if intervals else 0.0

    # Fill completion times from PCB tracking
    for pcb in pcbs:
        if pcb.pid in processes_info:
            processes_info[pcb.pid]["completion_time"] = pcb.completion_time or makespan

    proc_metrics = calculate_process_metrics(processes_info, intervals)
    sys_metrics = calculate_system_metrics(proc_metrics, intervals, energy_cfg, makespan, peak_temp)

    return SimulationResponse(
        algorithm=alg.value,
        algorithm_display_name=display_names[alg],
        parameters=params,
        intervals=intervals,
        process_metrics=proc_metrics,
        system_metrics=sys_metrics,
        decision_log=decision_logs,
        time_series=time_series
    )


def run_comparison(request: ComparisonRequest) -> ComparisonResponse:
    """Run all 5 algorithms against the same workload and environment."""
    algorithms_to_run = [
        (AlgorithmType.FCFS, False),
        (AlgorithmType.SJF, False),
        (AlgorithmType.ROUND_ROBIN, False),
        (AlgorithmType.PRIORITY, request.priority_preemptive),
        (AlgorithmType.ECOSCHED, False),
    ]

    results: Dict[str, SimulationResponse] = {}
    summary_table: List[ComparisonSummaryRow] = []

    for alg, is_preemptive in algorithms_to_run:
        sim_req = SimulationRequest(
            processes=request.processes,
            algorithm=alg,
            time_quantum=request.time_quantum,
            priority_preemptive=is_preemptive,
            renewable_profile=request.renewable_profile,
            thermal_config=request.thermal_config,
            energy_config=request.energy_config,
            ecosched_config=request.ecosched_config
        )
        sim_res = run_simulation(sim_req)
        results[alg.value] = sim_res

        sys = sim_res.system_metrics
        summary_table.append(
            ComparisonSummaryRow(
                algorithm=alg.value,
                display_name=sim_res.algorithm_display_name,
                avg_waiting_time=sys.average_waiting_time,
                avg_turnaround_time=sys.average_turnaround_time,
                avg_response_time=sys.average_response_time,
                throughput=sys.throughput,
                makespan=sys.makespan,
                cpu_utilization=sys.cpu_utilization,
                context_switches=sys.context_switches,
                deadline_success_rate=sys.deadline_success_rate,
                peak_temperature=sys.peak_modeled_temperature,
                grid_energy_proxy=sys.estimated_grid_energy_proxy,
                renewable_utilization_percent=sys.renewable_utilization_percent
            )
        )

    # Workload summary
    total_burst = sum(p.burst_time for p in request.processes)
    workload_summary = {
        "process_count": len(request.processes),
        "total_burst_time": round(total_burst, 2),
        "critical_count": sum(1 for p in request.processes if p.workload_type == WorkloadType.CRITICAL),
        "normal_count": sum(1 for p in request.processes if p.workload_type == WorkloadType.NORMAL),
        "flexible_count": sum(1 for p in request.processes if p.workload_type == WorkloadType.FLEXIBLE),
        "deadlines_specified": sum(1 for p in request.processes if p.deadline is not None),
    }

    return ComparisonResponse(
        results=results,
        summary_table=summary_table,
        workload_summary=workload_summary
    )
