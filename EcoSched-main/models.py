"""
EcoSched Data Models and Schemas.

Provides Pydantic models for request validation, configuration profiles,
execution traces, and simulation metric responses.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator, field_validator
from config import ThermalDefaults, EnergyDefaults, EcoSchedDefaults


class WorkloadType(str, Enum):
    """Classification of workload urgency and flexibility."""
    CRITICAL = "critical"
    NORMAL = "normal"
    FLEXIBLE = "flexible"


class AlgorithmType(str, Enum):
    """Supported CPU scheduling algorithms."""
    FCFS = "fcfs"
    SJF = "sjf"
    ROUND_ROBIN = "round_robin"
    PRIORITY = "priority"
    ECOSCHED = "ecosched"


class ProcessInput(BaseModel):
    """Specification of an incoming process."""
    pid: str = Field(..., description="Unique process identifier (e.g. 'P1')")
    name: str = Field("", description="Human-readable process name. Defaults to PID if empty.")
    arrival_time: float = Field(..., ge=0.0, description="Arrival time (>= 0)")
    burst_time: float = Field(..., gt=0.0, description="Required execution burst time (> 0)")
    priority: int = Field(3, ge=1, description="Base priority. Lower numeric value = higher priority.")
    workload_type: WorkloadType = Field(WorkloadType.NORMAL, description="Workload type: critical, normal, flexible")
    cpu_intensity: float = Field(0.5, ge=0.0, le=1.0, description="Normalized CPU intensity between 0.0 and 1.0")
    deadline: Optional[float] = Field(None, description="Optional completion deadline (time units)")

    @field_validator("pid")
    @classmethod
    def validate_pid(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Process PID must not be empty or whitespace only.")
        return s

    @model_validator(mode="after")
    def validate_deadline_and_name(self) -> "ProcessInput":
        if not self.name or not self.name.strip():
            self.name = self.pid
        if self.deadline is not None:
            if self.deadline < self.arrival_time:
                raise ValueError(
                    f"Deadline ({self.deadline}) cannot be earlier than arrival time ({self.arrival_time}) for process '{self.pid}'."
                )
        return self


class RenewableInterval(BaseModel):
    """Defines renewable energy availability for a specific time window."""
    start_time: float = Field(..., ge=0.0, description="Start of time interval")
    end_time: float = Field(..., gt=0.0, description="End of time interval")
    availability: float = Field(..., ge=0.0, le=1.0, description="Fraction of green energy [0.0 to 1.0]")

    @model_validator(mode="after")
    def validate_interval(self) -> "RenewableInterval":
        if self.end_time <= self.start_time:
            raise ValueError(f"end_time ({self.end_time}) must be strictly greater than start_time ({self.start_time})")
        return self


class RenewableProfile(BaseModel):
    """Profile specifying time-varying renewable energy availability."""
    intervals: List[RenewableInterval] = Field(default_factory=list, description="Ordered time windows of availability")
    default_availability: float = Field(0.5, ge=0.0, le=1.0, description="Fallback availability when time is outside windows")

    def get_availability(self, time: float) -> float:
        """Query renewable availability at simulated time t."""
        for interval in self.intervals:
            if interval.start_time <= time < interval.end_time:
                return interval.availability
        return self.default_availability


class ThermalConfig(BaseModel):
    """Configuration parameters for the simulated thermal model."""
    ambient_temperature: float = Field(ThermalDefaults.AMBIENT_TEMP, ge=0.0, description="Baseline ambient temperature in °C")
    heating_coefficient: float = Field(ThermalDefaults.HEATING_COEFF, gt=0.0, description="Temperature rise per unit time at 1.0 CPU intensity")
    cooling_coefficient: float = Field(ThermalDefaults.COOLING_COEFF, gt=0.0, description="Newton cooling rate factor per unit time")
    warning_temperature: float = Field(ThermalDefaults.WARNING_TEMP, gt=0.0, description="Temperature (°C) where thermal penalty starts")
    critical_temperature: float = Field(ThermalDefaults.CRITICAL_TEMP, gt=0.0, description="Temperature (°C) where thermal guard activates")

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ThermalConfig":
        if self.warning_temperature <= self.ambient_temperature:
            raise ValueError(f"warning_temperature ({self.warning_temperature}) must be > ambient_temperature ({self.ambient_temperature})")
        if self.critical_temperature <= self.warning_temperature:
            raise ValueError(f"critical_temperature ({self.critical_temperature}) must be > warning_temperature ({self.warning_temperature})")
        return self


class EnergyConfig(BaseModel):
    """Parameters for the estimated grid-energy proxy model."""
    idle_power_watts: float = Field(EnergyDefaults.IDLE_POWER_WATTS, ge=0.0, description="Baseline idle power proxy in Watts")
    max_active_power_watts: float = Field(EnergyDefaults.MAX_ACTIVE_POWER_WATTS, gt=0.0, description="Peak load power proxy in Watts")

    @model_validator(mode="after")
    def validate_power(self) -> "EnergyConfig":
        if self.max_active_power_watts <= self.idle_power_watts:
            raise ValueError(f"max_active_power_watts ({self.max_active_power_watts}) must be > idle_power_watts ({self.idle_power_watts})")
        return self


class EcoSchedConfig(BaseModel):
    """Tuning parameters for the EcoSched adaptive scheduling algorithm."""
    weight_urgency: float = Field(EcoSchedDefaults.WEIGHT_URGENCY, ge=0.0, description="Weight of workload urgency term")
    weight_renewable: float = Field(EcoSchedDefaults.WEIGHT_RENEWABLE, ge=0.0, description="Weight of renewable bonus term")
    weight_aging: float = Field(EcoSchedDefaults.WEIGHT_AGING, ge=0.0, description="Weight of waiting-time aging term")
    weight_thermal: float = Field(EcoSchedDefaults.WEIGHT_THERMAL, ge=0.0, description="Weight of thermal penalty term")

    renewable_high_threshold: float = Field(EcoSchedDefaults.RENEWABLE_HIGH_THRESHOLD, ge=0.0, le=1.0, description="Threshold above which renewable bonus applies")
    renewable_low_threshold: float = Field(EcoSchedDefaults.RENEWABLE_LOW_THRESHOLD, ge=0.0, le=1.0, description="Threshold below which flexible tasks may defer")

    min_slack_for_deferral: float = Field(EcoSchedDefaults.MIN_SLACK_FOR_DEFERRAL, ge=0.0, description="Minimum deadline slack needed to permit deferral")
    max_consecutive_deferrals: int = Field(EcoSchedDefaults.MAX_CONSECUTIVE_DEFERRALS, ge=1, description="Max consecutive deferrals before starvation guard forces run")
    aging_threshold_ticks: float = Field(EcoSchedDefaults.AGING_THRESHOLD_TICKS, gt=0.0, description="Waiting ticks scale for aging bonus normalization")

    base_quantum: int = Field(EcoSchedDefaults.BASE_QUANTUM, ge=1, description="Standard time quantum for EcoSched")
    min_quantum: int = Field(EcoSchedDefaults.MIN_QUANTUM, ge=1, description="Minimum adaptive time quantum")
    max_quantum: int = Field(EcoSchedDefaults.MAX_QUANTUM, ge=1, description="Maximum adaptive time quantum under ideal green conditions")
    context_switch_cost: float = Field(EcoSchedDefaults.CONTEXT_SWITCH_COST, ge=0.0, description="Context switch time overhead")

    @model_validator(mode="after")
    def validate_ecosched(self) -> "EcoSchedConfig":
        if self.renewable_high_threshold <= self.renewable_low_threshold:
            raise ValueError(
                f"renewable_high_threshold ({self.renewable_high_threshold}) must be > renewable_low_threshold ({self.renewable_low_threshold})"
            )
        if self.max_quantum < self.min_quantum:
            raise ValueError(f"max_quantum ({self.max_quantum}) must be >= min_quantum ({self.min_quantum})")
        if self.base_quantum < self.min_quantum or self.base_quantum > self.max_quantum:
            raise ValueError(f"base_quantum ({self.base_quantum}) must be between min_quantum ({self.min_quantum}) and max_quantum ({self.max_quantum})")
        return self


class SimulationRequest(BaseModel):
    """Request payload for running a simulation."""
    processes: List[ProcessInput] = Field(..., description="List of processes to schedule")
    algorithm: AlgorithmType = Field(AlgorithmType.ECOSCHED, description="Algorithm: fcfs, sjf, round_robin, priority, ecosched")
    time_quantum: Optional[int] = Field(2, ge=1, description="Time quantum for Round Robin")
    priority_preemptive: bool = Field(False, description="Priority Scheduling mode: True for preemptive, False for non-preemptive")

    renewable_profile: Optional[RenewableProfile] = Field(default_factory=RenewableProfile, description="Renewable availability timeline")
    thermal_config: Optional[ThermalConfig] = Field(default_factory=ThermalConfig, description="Thermal model parameters")
    energy_config: Optional[EnergyConfig] = Field(default_factory=EnergyConfig, description="Energy proxy parameters")
    ecosched_config: Optional[EcoSchedConfig] = Field(default_factory=EcoSchedConfig, description="EcoSched specific parameters")

    @model_validator(mode="after")
    def validate_request(self) -> "SimulationRequest":
        if not self.processes:
            raise ValueError("Workload must contain at least one process.")

        pids = set()
        for p in self.processes:
            if p.pid in pids:
                raise ValueError(f"Duplicate process ID detected: '{p.pid}'. All PIDs must be unique.")
            pids.add(p.pid)

        if self.algorithm == AlgorithmType.ROUND_ROBIN:
            if self.time_quantum is None or self.time_quantum < 1:
                raise ValueError("Round Robin requires 'time_quantum' >= 1.")

        return self


class ComparisonRequest(BaseModel):
    """Request payload for running all algorithms side-by-side."""
    processes: List[ProcessInput] = Field(..., description="List of processes to schedule across all algorithms")
    time_quantum: int = Field(2, ge=1, description="Time quantum for Round Robin")
    priority_preemptive: bool = Field(False, description="Priority Scheduling mode: True for preemptive, False for non-preemptive")

    renewable_profile: Optional[RenewableProfile] = Field(default_factory=RenewableProfile, description="Renewable availability timeline")
    thermal_config: Optional[ThermalConfig] = Field(default_factory=ThermalConfig, description="Thermal model parameters")
    energy_config: Optional[EnergyConfig] = Field(default_factory=EnergyConfig, description="Energy proxy parameters")
    ecosched_config: Optional[EcoSchedConfig] = Field(default_factory=EcoSchedConfig, description="EcoSched specific parameters")

    @model_validator(mode="after")
    def validate_comparison_request(self) -> "ComparisonRequest":
        if not self.processes:
            raise ValueError("Workload must contain at least one process.")

        pids = set()
        for p in self.processes:
            if p.pid in pids:
                raise ValueError(f"Duplicate process ID detected: '{p.pid}'. All PIDs must be unique.")
            pids.add(p.pid)
        return self


# ------------------ OUTPUT MODELS ------------------

class ExecutionInterval(BaseModel):
    """An atomic interval of CPU execution for Gantt chart rendering."""
    pid: str = Field(..., description="PID of executing process, or 'IDLE'")
    start: float = Field(..., description="Interval start time")
    end: float = Field(..., description="Interval end time")
    reason: str = Field(..., description="Explainable decision or status rationale")
    workload_type: Optional[str] = Field(None, description="Workload type of the running process")
    cpu_intensity: Optional[float] = Field(None, description="CPU intensity during this interval")
    modeled_temp_start: Optional[float] = Field(None, description="Modeled temperature at start (°C)")
    modeled_temp_end: Optional[float] = Field(None, description="Modeled temperature at end (°C)")
    renewable_availability: Optional[float] = Field(None, description="Renewable availability fraction during interval")


class ProcessMetricResult(BaseModel):
    """Per-process performance and scheduling outcomes."""
    pid: str
    name: str
    arrival_time: float
    burst_time: float
    priority: int
    workload_type: str
    completion_time: float
    turnaround_time: float
    waiting_time: float
    response_time: float
    deadline: Optional[float] = None
    deadline_met: Optional[bool] = None
    execution_intervals_count: int


class SystemMetrics(BaseModel):
    """System-wide performance, thermal, and green-energy aggregate metrics."""
    average_waiting_time: float
    average_turnaround_time: float
    average_response_time: float
    throughput: float
    makespan: float
    cpu_utilization: float
    context_switches: int
    deadline_success_rate: Optional[float] = None
    max_waiting_time: float
    peak_modeled_temperature: float
    estimated_grid_energy_proxy: float
    estimated_total_energy_proxy: float
    estimated_renewable_energy_proxy: float
    renewable_utilization_percent: float


class SimulationDecisionLog(BaseModel):
    """Trace entry documenting an explainable scheduling decision point."""
    time: float
    selected_pid: str
    score: Optional[float] = None
    reason: str
    context: Dict[str, Any] = Field(default_factory=dict)


class TimeSeriesPoint(BaseModel):
    """Snapshot of modeled environment at simulated time t."""
    time: float
    active_pid: str
    modeled_temperature: float
    renewable_availability: float


class SimulationResponse(BaseModel):
    """Complete simulation result returned to frontend."""
    algorithm: str
    algorithm_display_name: str
    parameters: Dict[str, Any]
    intervals: List[ExecutionInterval]
    process_metrics: List[ProcessMetricResult]
    system_metrics: SystemMetrics
    decision_log: List[SimulationDecisionLog]
    time_series: List[TimeSeriesPoint]


class ComparisonSummaryRow(BaseModel):
    """Compact metrics row for frontend comparison table."""
    algorithm: str
    display_name: str
    avg_waiting_time: float
    avg_turnaround_time: float
    avg_response_time: float
    throughput: float
    makespan: float
    cpu_utilization: float
    context_switches: int
    deadline_success_rate: Optional[float]
    peak_temperature: float
    grid_energy_proxy: float
    renewable_utilization_percent: float


class ComparisonResponse(BaseModel):
    """Multi-algorithm comparison result for frontend dashboards."""
    results: Dict[str, SimulationResponse]
    summary_table: List[ComparisonSummaryRow]
    workload_summary: Dict[str, Any]
