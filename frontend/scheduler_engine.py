"""
EcoSched Scheduling Engine.

Implements:
1. FCFS (First Come First Serve - non-preemptive)
2. SJF (Shortest Job First - non-preemptive)
3. Round Robin (configurable time quantum)
4. Priority Scheduling (configurable preemptive or non-preemptive)
5. EcoSched (adaptive, renewable-aware, thermal-guarded, aging-protected)
"""

from typing import List, Dict, Optional, Tuple, Any
from models import (
    ProcessInput,
    WorkloadType,
    ThermalConfig,
    RenewableProfile,
    EcoSchedConfig,
    ExecutionInterval,
    SimulationDecisionLog
)


class ProcessControlBlock:
    """Internal runtime representation of a process."""
    def __init__(self, p: ProcessInput):
        self.pid: str = p.pid
        self.name: str = p.name
        self.arrival_time: float = float(p.arrival_time)
        self.burst_time: float = float(p.burst_time)
        self.remaining_time: float = float(p.burst_time)
        self.priority: int = int(p.priority)
        self.workload_type: WorkloadType = p.workload_type
        self.cpu_intensity: float = float(p.cpu_intensity)
        self.deadline: Optional[float] = float(p.deadline) if p.deadline is not None else None

        # Runtime tracking
        self.first_start_time: Optional[float] = None
        self.completion_time: Optional[float] = None
        self.consecutive_deferrals: int = 0
        self.execution_intervals_count: int = 0

    def waiting_time_at(self, current_time: float) -> float:
        """Calculate total waiting time accumulated up to current_time."""
        executed_time = self.burst_time - self.remaining_time
        return max(0.0, current_time - self.arrival_time - executed_time)

    def slack_at(self, current_time: float) -> Optional[float]:
        """Calculate deadline slack: deadline - (current_time + remaining_time)."""
        if self.deadline is None:
            return None
        return self.deadline - (current_time + self.remaining_time)

    def is_completed(self) -> bool:
        return self.remaining_time <= 1e-9


class ThermalSimulator:
    """Models simulated CPU temperature over time.
    
    Uses Newton's Law of Cooling and activity-based heating:
    dT = (heating_coeff * intensity - cooling_coeff * (T - T_amb)) * dt
    """
    def __init__(self, config: ThermalConfig):
        self.ambient_temp: float = config.ambient_temperature
        self.heating_coeff: float = config.heating_coefficient
        self.cooling_coeff: float = config.cooling_coefficient
        self.warning_temp: float = config.warning_temperature
        self.critical_temp: float = config.critical_temperature
        self.current_temp: float = config.ambient_temperature
        self.peak_temp: float = config.ambient_temperature

    def update(self, duration: float, is_active: bool, cpu_intensity: float) -> Tuple[float, float]:
        """Update temperature over an interval [t, t + duration].
        
        Returns:
            (start_temp, end_temp)
        """
        start_temp = self.current_temp
        if duration <= 0:
            return (start_temp, start_temp)

        # Discrete numerical integration in small sub-steps for stability
        step_dt = min(0.5, duration)
        elapsed = 0.0
        temp = self.current_temp

        while elapsed < duration - 1e-9:
            dt = min(step_dt, duration - elapsed)
            heat = (self.heating_coeff * cpu_intensity * dt) if is_active else 0.0
            cool = self.cooling_coeff * (temp - self.ambient_temp) * dt
            temp = max(self.ambient_temp, temp + heat - cool)
            elapsed += dt

        self.current_temp = temp
        if self.current_temp > self.peak_temp:
            self.peak_temp = self.current_temp

        return (start_temp, self.current_temp)


class EcoSchedPolicy:
    """Core decision-making logic for the EcoSched adaptive algorithm."""

    @staticmethod
    def calculate_urgency_score(pcb: ProcessControlBlock, current_time: float) -> Tuple[float, str]:
        """Calculate workload urgency based on workload type, base priority, and deadline slack."""
        # 1. Base urgency by workload type
        if pcb.workload_type == WorkloadType.CRITICAL:
            base_urgency = 5.0
            type_desc = "Critical workload"
        elif pcb.workload_type == WorkloadType.NORMAL:
            base_urgency = 2.0
            type_desc = "Normal workload"
        else:
            base_urgency = 1.0
            type_desc = "Flexible workload"

        # 2. Base priority bonus (priority 1 gets +0.8, priority 5 gets 0.0)
        prio_adj = max(0.0, (5.0 - pcb.priority) * 0.2)

        # 3. Deadline urgency
        deadline_bonus = 0.0
        deadline_desc = ""
        slack = pcb.slack_at(current_time)

        if slack is not None:
            if slack <= 0.0:
                # Emergency: deadline already at or past the point of failure
                deadline_bonus = 25.0 + abs(slack) * 2.0
                deadline_desc = f", EXTREME URGENCY (slack={slack:.1f})"
            elif slack <= 4.0:
                deadline_bonus = 15.0 * ((4.0 - slack) / 4.0)
                deadline_desc = f", high urgency (slack={slack:.1f})"
            elif slack <= 12.0:
                deadline_bonus = 5.0 * ((12.0 - slack) / 8.0)
                deadline_desc = f", moderate urgency (slack={slack:.1f})"

        total_urgency = base_urgency + prio_adj + deadline_bonus
        summary = f"{type_desc} (prio={pcb.priority}{deadline_desc})"
        return total_urgency, summary

    @staticmethod
    def calculate_renewable_bonus(
        pcb: ProcessControlBlock,
        renewable_avail: float,
        config: EcoSchedConfig
    ) -> Tuple[float, str]:
        """Calculate green energy bonus.
        
        When renewable availability is high, flexible workloads receive a significant bonus
        to prioritize execution during surplus clean energy.
        """
        if renewable_avail >= config.renewable_high_threshold:
            if pcb.workload_type == WorkloadType.FLEXIBLE:
                bonus = config.weight_renewable * renewable_avail * (1.0 + pcb.cpu_intensity)
                return bonus, f"High renewable bonus (+{bonus:.2f}, ren={renewable_avail:.2f})"
            else:
                bonus = 0.4 * config.weight_renewable * renewable_avail
                return bonus, f"Favorable renewable environment (+{bonus:.2f})"
        return 0.0, "Standard renewable condition"

    @staticmethod
    def calculate_aging_bonus(
        pcb: ProcessControlBlock,
        current_time: float,
        config: EcoSchedConfig
    ) -> Tuple[float, str]:
        """Calculate starvation prevention aging bonus based on accumulated waiting time."""
        waiting = pcb.waiting_time_at(current_time)
        norm_waiting = waiting / config.aging_threshold_ticks
        bonus = config.weight_aging * norm_waiting

        desc = f"Aging bonus (+{bonus:.2f}, wait={waiting:.1f})"
        if pcb.consecutive_deferrals > 0:
            desc += f", deferrals={pcb.consecutive_deferrals}"
        return bonus, desc

    @staticmethod
    def calculate_thermal_penalty(
        pcb: ProcessControlBlock,
        current_temp: float,
        thermal_config: ThermalConfig,
        config: EcoSchedConfig
    ) -> Tuple[float, str]:
        """Calculate thermal penalty for CPU-intensive tasks under high modeled temperature."""
        if current_temp > thermal_config.warning_temperature:
            temp_range = thermal_config.critical_temperature - thermal_config.warning_temperature
            ratio = (current_temp - thermal_config.warning_temperature) / max(1.0, temp_range)
            penalty = config.weight_thermal * pcb.cpu_intensity * ratio

            desc = f"Thermal penalty (-{penalty:.2f}, temp={current_temp:.1f}°C, intensity={pcb.cpu_intensity:.2f})"
            return penalty, desc
        return 0.0, "Thermal within safe range"

    @classmethod
    def evaluate_process(
        cls,
        pcb: ProcessControlBlock,
        current_time: float,
        current_temp: float,
        renewable_avail: float,
        thermal_config: ThermalConfig,
        ecosched_config: EcoSchedConfig
    ) -> Tuple[float, Dict[str, Any], str]:
        """Compute the total composite EcoSched score and explanation components.
        
        Formula:
            score = urgency_score + renewable_bonus + aging_bonus - thermal_penalty
        """
        urgency, urg_desc = cls.calculate_urgency_score(pcb, current_time)
        ren_bonus, ren_desc = cls.calculate_renewable_bonus(pcb, renewable_avail, ecosched_config)
        aging_bonus, aging_desc = cls.calculate_aging_bonus(pcb, current_time, ecosched_config)
        thermal_penalty, therm_desc = cls.calculate_thermal_penalty(
            pcb, current_temp, thermal_config, ecosched_config
        )

        total_score = (
            (ecosched_config.weight_urgency * urgency)
            + ren_bonus
            + aging_bonus
            - thermal_penalty
        )

        details = {
            "urgency": urgency,
            "renewable_bonus": ren_bonus,
            "aging_bonus": aging_bonus,
            "thermal_penalty": thermal_penalty,
            "total_score": round(total_score, 3),
            "waiting_time": round(pcb.waiting_time_at(current_time), 2),
            "slack": round(pcb.slack_at(current_time), 2) if pcb.deadline is not None else None,
            "consecutive_deferrals": pcb.consecutive_deferrals,
        }

        # Build composite readable explanation
        reasons = []
        if pcb.workload_type == WorkloadType.CRITICAL:
            reasons.append("Critical task priority")
        elif pcb.deadline is not None and (pcb.slack_at(current_time) or 0) <= 4.0:
            reasons.append(f"Tight deadline (slack={pcb.slack_at(current_time):.1f})")
        
        if ren_bonus > 0.5:
            reasons.append(f"Favorable green energy (ren={renewable_avail:.2f})")
        if aging_bonus > 1.5 or pcb.consecutive_deferrals >= ecosched_config.max_consecutive_deferrals:
            reasons.append(f"Starvation aging guard (wait={details['waiting_time']})")
        if thermal_penalty > 1.0:
            reasons.append(f"Thermal pressure throttled (temp={current_temp:.1f}°C)")

        if not reasons:
            reasons.append(f"Highest scheduling score ({total_score:.2f})")

        explanation = " | ".join(reasons)
        return total_score, details, explanation

    @classmethod
    def can_defer_flexible(
        cls,
        pcb: ProcessControlBlock,
        current_time: float,
        renewable_avail: float,
        ecosched_config: EcoSchedConfig
    ) -> Tuple[bool, str]:
        """Determine if a flexible task should be deferred due to scarce green energy.
        
        Conditions for deferral:
        1. Renewable availability is below renewable_low_threshold.
        2. Task is flexible (critical and normal tasks are never deferred for energy).
        3. Task has sufficient deadline slack (slack > min_slack_for_deferral, or no deadline).
        4. Consecutive deferrals have not reached max_consecutive_deferrals (starvation guard).
        5. Total waiting time has not exceeded 2 * aging_threshold_ticks.
        """
        if pcb.workload_type != WorkloadType.FLEXIBLE:
            return False, "Not a flexible workload; deferral prohibited"

        if renewable_avail >= ecosched_config.renewable_low_threshold:
            return False, "Renewable energy above deferral threshold"

        if pcb.consecutive_deferrals >= ecosched_config.max_consecutive_deferrals:
            return False, f"Maximum deferral limit reached ({pcb.consecutive_deferrals}/{ecosched_config.max_consecutive_deferrals}); forced execution"

        waiting = pcb.waiting_time_at(current_time)
        if waiting > (2.0 * ecosched_config.aging_threshold_ticks):
            return False, f"Aging protection activated (waiting={waiting:.1f}); deferral forbidden"

        if pcb.deadline is not None:
            slack = pcb.slack_at(current_time)
            if slack is None or slack <= ecosched_config.min_slack_for_deferral:
                return False, f"Insufficient deadline slack ({slack:.1f} <= {ecosched_config.min_slack_for_deferral}); must execute"

        slack_info = f", slack={pcb.slack_at(current_time):.1f}" if pcb.deadline is not None else ""
        return True, f"Flexible workload deferred due to low renewable availability (ren={renewable_avail:.2f}{slack_info})"

    @classmethod
    def compute_adaptive_quantum(
        cls,
        pcb: ProcessControlBlock,
        current_time: float,
        current_temp: float,
        renewable_avail: float,
        thermal_config: ThermalConfig,
        ecosched_config: EcoSchedConfig
    ) -> int:
        """Dynamically compute the time quantum for the selected task.
        
        Rules:
        - Thermal pressure (T >= T_warn) or tight deadline slack (<= 3): use min_quantum (1) for rapid responsiveness.
        - High renewable availability and safe thermal conditions: grant max_quantum (e.g. 4) to flexible tasks
          to reduce context switches and maximize throughput during clean energy availability.
        - Otherwise, use base_quantum (e.g. 2).
        - Clamped to [min_quantum, max_quantum] and remaining burst time.
        """
        slack = pcb.slack_at(current_time)
        tight_deadline = slack is not None and slack <= 3.0
        high_thermal = current_temp >= thermal_config.warning_temperature

        if tight_deadline or high_thermal:
            q = ecosched_config.min_quantum
        elif (
            renewable_avail >= ecosched_config.renewable_high_threshold
            and current_temp < thermal_config.warning_temperature
            and pcb.workload_type == WorkloadType.FLEXIBLE
        ):
            q = ecosched_config.max_quantum
        else:
            q = ecosched_config.base_quantum

        # Clamp between min and max quantum, and not exceeding remaining time
        q = max(ecosched_config.min_quantum, min(q, ecosched_config.max_quantum))
        return max(1, min(q, int(pcb.remaining_time)))
