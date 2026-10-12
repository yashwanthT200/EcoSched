"""
EcoSched Configuration Module.

Defines default parameters and configurable thresholds for:
- Thermal modeling
- Energy estimation proxy
- EcoSched adaptive scoring weights
- Adaptive quantum parameters
"""

from typing import Dict, Any


class ThermalDefaults:
    """Default parameters for the modeled thermal environment.
    
    Note: Modeled temperature is a simulated metric for scheduling research,
    not actual hardware thermal telemetry.
    """
    AMBIENT_TEMP: float = 35.0         # Baseline ambient temperature in °C
    HEATING_COEFF: float = 4.0         # Temperature rise per unit time at 1.0 CPU intensity
    COOLING_COEFF: float = 0.25        # Newton's law cooling rate per unit time
    WARNING_TEMP: float = 65.0         # Threshold where thermal penalties begin
    CRITICAL_TEMP: float = 80.0        # Threshold where thermal protection activates
    COOLDOWN_TICKS: int = 2            # Minimum idle cooling ticks when guard triggers


class EnergyDefaults:
    """Default parameters for the estimated grid-energy proxy model.
    
    Note: This is an estimated proxy based on workload activity and renewable
    availability fractions, not physical hardware power meter readings.
    """
    IDLE_POWER_WATTS: float = 12.0     # Baseline proxy idle system power
    MAX_ACTIVE_POWER_WATTS: float = 65.0  # Peak proxy power at 1.0 CPU intensity


class EcoSchedDefaults:
    """Default weights and tuning parameters for the EcoSched policy."""
    # Adaptive score weights
    WEIGHT_URGENCY: float = 2.0
    WEIGHT_RENEWABLE: float = 2.5
    WEIGHT_AGING: float = 1.5
    WEIGHT_THERMAL: float = 2.0

    # Renewable thresholds
    RENEWABLE_HIGH_THRESHOLD: float = 0.70   # Favorable renewable threshold (bonus applies)
    RENEWABLE_LOW_THRESHOLD: float = 0.35    # Scarce renewable threshold (deferral eligible)

    # Deferral & Starvation Prevention
    MIN_SLACK_FOR_DEFERRAL: float = 4.0      # Minimum slack required to allow deferral
    MAX_CONSECUTIVE_DEFERRALS: int = 3       # Maximum deferrals before forced execution
    AGING_THRESHOLD_TICKS: float = 8.0       # Waiting duration baseline for aging bonus

    # Adaptive Quantum limits
    BASE_QUANTUM: int = 2
    MIN_QUANTUM: int = 1
    MAX_QUANTUM: int = 4

    # Context switch overhead (in simulated time units)
    CONTEXT_SWITCH_COST: float = 0.0


def get_default_config_dict() -> Dict[str, Any]:
    """Return dictionary of all default parameters for documentation and API presets."""
    return {
        "thermal": {
            "ambient_temperature": ThermalDefaults.AMBIENT_TEMP,
            "heating_coefficient": ThermalDefaults.HEATING_COEFF,
            "cooling_coefficient": ThermalDefaults.COOLING_COEFF,
            "warning_temperature": ThermalDefaults.WARNING_TEMP,
            "critical_temperature": ThermalDefaults.CRITICAL_TEMP,
        },
        "energy": {
            "idle_power_watts": EnergyDefaults.IDLE_POWER_WATTS,
            "max_active_power_watts": EnergyDefaults.MAX_ACTIVE_POWER_WATTS,
        },
        "ecosched": {
            "weight_urgency": EcoSchedDefaults.WEIGHT_URGENCY,
            "weight_renewable": EcoSchedDefaults.WEIGHT_RENEWABLE,
            "weight_aging": EcoSchedDefaults.WEIGHT_AGING,
            "weight_thermal": EcoSchedDefaults.WEIGHT_THERMAL,
            "renewable_high_threshold": EcoSchedDefaults.RENEWABLE_HIGH_THRESHOLD,
            "renewable_low_threshold": EcoSchedDefaults.RENEWABLE_LOW_THRESHOLD,
            "min_slack_for_deferral": EcoSchedDefaults.MIN_SLACK_FOR_DEFERRAL,
            "max_consecutive_deferrals": EcoSchedDefaults.MAX_CONSECUTIVE_DEFERRALS,
            "aging_threshold_ticks": EcoSchedDefaults.AGING_THRESHOLD_TICKS,
            "base_quantum": EcoSchedDefaults.BASE_QUANTUM,
            "min_quantum": EcoSchedDefaults.MIN_QUANTUM,
            "max_quantum": EcoSchedDefaults.MAX_QUANTUM,
            "context_switch_cost": EcoSchedDefaults.CONTEXT_SWITCH_COST,
        }
    }
