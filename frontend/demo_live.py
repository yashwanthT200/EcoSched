"""
EcoSched Live CLI Demonstration.

Executes a side-by-side comparison of all 5 scheduling algorithms
against a sample mixed workload and prints a clear comparative summary table.
"""

from models import (
    ComparisonRequest,
    ProcessInput,
    WorkloadType,
    RenewableProfile,
    RenewableInterval,
    ThermalConfig,
    EcoSchedConfig
)
from simulation import run_comparison


def main():
    print("=" * 80)
    print("  EcoSched: Renewable-Aware CPU Scheduler for Green Computing")
    print("  Side-by-Side Algorithm Evaluation Demo")
    print("=" * 80)

    workload = [
        ProcessInput(
            pid="P1",
            name="Auth Service",
            arrival_time=0.0,
            burst_time=4.0,
            priority=1,
            workload_type=WorkloadType.CRITICAL,
            cpu_intensity=0.4,
            deadline=10.0
        ),
        ProcessInput(
            pid="P2",
            name="Web Server Worker",
            arrival_time=1.0,
            burst_time=5.0,
            priority=2,
            workload_type=WorkloadType.NORMAL,
            cpu_intensity=0.6,
            deadline=18.0
        ),
        ProcessInput(
            pid="P3",
            name="Image Rendering Task",
            arrival_time=2.0,
            burst_time=6.0,
            priority=4,
            workload_type=WorkloadType.FLEXIBLE,
            cpu_intensity=0.9,
            deadline=30.0
        ),
        ProcessInput(
            pid="P4",
            name="Database Backup",
            arrival_time=4.0,
            burst_time=4.0,
            priority=5,
            workload_type=WorkloadType.FLEXIBLE,
            cpu_intensity=0.5,
            deadline=35.0
        ),
        ProcessInput(
            pid="P5",
            name="Urgent Health Monitor",
            arrival_time=6.0,
            burst_time=3.0,
            priority=1,
            workload_type=WorkloadType.CRITICAL,
            cpu_intensity=0.3,
            deadline=12.0
        )
    ]

    # Time-varying renewable energy: surges mid-run between t=6 and t=20
    renewable_profile = RenewableProfile(
        intervals=[
            RenewableInterval(start_time=0.0, end_time=6.0, availability=0.25),
            RenewableInterval(start_time=6.0, end_time=20.0, availability=0.85),
            RenewableInterval(start_time=20.0, end_time=40.0, availability=0.35)
        ],
        default_availability=0.30
    )

    thermal_config = ThermalConfig(
        ambient_temperature=35.0,
        heating_coefficient=4.0,
        cooling_coefficient=0.25,
        warning_temperature=65.0,
        critical_temperature=80.0
    )

    req = ComparisonRequest(
        processes=workload,
        time_quantum=2,
        priority_preemptive=False,
        renewable_profile=renewable_profile,
        thermal_config=thermal_config,
        ecosched_config=EcoSchedConfig()
    )

    print("\nRunning multi-algorithm simulation across identical inputs...\n")
    comparison = run_comparison(req)

    print(f"{'Algorithm':<28} | {'Avg Wait':<9} | {'Avg Turn':<9} | {'Makespan':<9} | {'Grid Energy':<12} | {'Ren Util %':<11} | {'Peak Temp':<10}")
    print("-" * 105)

    for row in comparison.summary_table:
        print(
            f"{row.display_name:<28} | "
            f"{row.avg_waiting_time:<9.2f} | "
            f"{row.avg_turnaround_time:<9.2f} | "
            f"{row.makespan:<9.1f} | "
            f"{row.grid_energy_proxy:<12.1f} | "
            f"{row.renewable_utilization_percent:<10.1f}% | "
            f"{row.peak_temperature:<8.1f}°C"
        )

    print("-" * 105)
    print("\nEcoSched Gantt Intervals & Decision Explanations:")
    for interval in comparison.results["ecosched"].intervals:
        print(f"  [{interval.start:4.1f} -> {interval.end:4.1f}] PID: {interval.pid:<6} | Reason: {interval.reason}")

    print("\n[OK] Demonstration completed successfully.")


if __name__ == "__main__":
    main()
