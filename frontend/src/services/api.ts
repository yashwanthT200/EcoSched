const API_BASE = "http://127.0.0.1:8000";

export interface ProcessInput {
  pid: string;
  name?: string;
  arrival_time: number;
  burst_time: number;
  priority: number;
  workload_type: "critical" | "normal" | "flexible";
  cpu_intensity: number;
  deadline?: number | null;
}

export interface ExecutionInterval {
  pid: string;
  start: number;
  end: number;
  reason: string;
  workload_type?: string;
  cpu_intensity?: number;
  modeled_temp_start?: number;
  modeled_temp_end?: number;
  renewable_availability?: number;
}

export interface SystemMetrics {
  average_waiting_time: number;
  average_turnaround_time: number;
  average_response_time: number;
  throughput: number;
  makespan: number;
  cpu_utilization: number;
  context_switches: number;
  deadline_success_rate?: number | null;
  peak_modeled_temperature: number;
  estimated_grid_energy_proxy: number;
  estimated_total_energy_proxy: number;
  estimated_renewable_energy_proxy: number;
  renewable_utilization_percent: number;
}

export interface SimulationResponse {
  algorithm: string;
  algorithm_display_name: string;
  intervals: ExecutionInterval[];
  process_metrics: any[];
  system_metrics: SystemMetrics;
  decision_log: any[];
  time_series: Array<{
    time: number;
    active_pid: string;
    modeled_temperature: number;
    renewable_availability: number;
  }>;
}

export interface ComparisonSummaryRow {
  algorithm: string;
  display_name: string;
  avg_waiting_time: number;
  avg_turnaround_time: number;
  makespan: number;
  cpu_utilization: number;
  context_switches: number;
  peak_temperature: number;
  grid_energy_proxy: number;
  renewable_utilization_percent: number;
}

export interface ComparisonResponse {
  results: Record<string, SimulationResponse>;
  summary_table: ComparisonSummaryRow[];
  workload_summary: Record<string, any>;
}

export async function fetchPresets() {
  const res = await fetch(`${API_BASE}/api/examples`);
  if (!res.ok) throw new Error("Failed to load presets");
  return res.json();
}

export async function runSimulation(payload: {
  processes: ProcessInput[];
  algorithm: string;
  time_quantum?: number;
  priority_preemptive?: boolean;
}): Promise<SimulationResponse> {
  const res = await fetch(`${API_BASE}/api/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Simulation failed");
  }
  return res.json();
}

export async function runComparison(payload: {
  processes: ProcessInput[];
  time_quantum?: number;
  priority_preemptive?: boolean;
}): Promise<ComparisonResponse> {
  const res = await fetch(`${API_BASE}/api/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Comparison failed");
  }
  return res.json();
}