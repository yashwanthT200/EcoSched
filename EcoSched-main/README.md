# EcoSched: Renewable-Aware CPU Scheduler for Green Computing
## Operating System CPU Scheduler, Simulation Engine & REST API

An operating systems simulation engine and REST API evaluating green computing scheduling policies. EcoSched integrates time-varying renewable energy availability, modeled thermal dissipation, deadline slack urgency, and starvation-prevention aging against classical scheduling algorithms (**FCFS**, **SJF**, **Round Robin**, and **Priority Scheduling**).

---

## 1. Quick Start (Windows PowerShell)

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- PowerShell 5.1+ or PowerShell 7+

### Step 1: Open PowerShell and Navigate to the Project Directory
```powershell
Set-Location -Path ".\EcoSched"
```

### Step 2: Install Dependencies
```powershell
& "C:\Users\yashw\AppData\Local\Python\bin\pip.exe" install -r requirements.txt
```
*(If Python is in your default system `PATH`, you can simply run `pip install -r requirements.txt`)*

### Step 3: Run the Automated Pytest Suite
```powershell
& "C:\Users\yashw\AppData\Local\Python\bin\python.exe" -m pytest -v
```
All 33 unit and integration tests will execute and verify algorithm ordering, preemption, thermal guards, starvation aging, metric mathematics, and API validation.

### Step 4: Run the Standalone CLI Demo
```powershell
& "C:\Users\yashw\AppData\Local\Python\bin\python.exe" demo_live.py
```
This runs a multi-algorithm comparison across an identical workload without requiring an active browser or web server.

### Step 5: Start the FastAPI Backend Server
```powershell
& "C:\Users\yashw\AppData\Local\Python\bin\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Once started:
- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive Swagger Documentation**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`

---

## 2. System Architecture

The backend is built with clean separation of concerns:

```
EcoSched/
├── config.py             # Default constants, weights, and thermal/energy thresholds
├── models.py             # Pydantic validation schemas for requests and responses
├── scheduler_engine.py   # PCB state, ThermalSimulator, and EcoSchedPolicy decision math
├── simulation.py         # Discrete-event execution loops for all 5 algorithms
├── metrics.py            # Standard OS metrics, context switch counting, and energy proxies
├── main.py               # FastAPI application with CORS and endpoint routers
├── demo_live.py          # Standalone CLI simulation script
├── requirements.txt      # Dependency specification
├── README.md             # This comprehensive engineering guide
└── tests/
    ├── conftest.py       # Shared pytest fixtures
    ├── test_algorithms.py# Conventional algorithm ordering & preemption tests
    ├── test_ecosched.py  # EcoSched urgency, green bonus, deferral, and thermal guard tests
    ├── test_metrics.py   # Standard formula checks & energy proxy conservation
    └── test_api.py       # Endpoint status, CORS, and request validation error tests
```

---

## 3. Supported Scheduling Algorithms

All algorithms accept the identical workload format and return consistent execution intervals and performance metrics.

| Algorithm | Type | Description | Key Parameters |
| :--- | :--- | :--- | :--- |
| **FCFS** | Non-preemptive | First-Come, First-Served based on arrival time. | None |
| **SJF** | Non-preemptive | Shortest Job First based on burst time. | None |
| **Round Robin** | Preemptive | FIFO queue with fixed time-slice quantum. | `time_quantum` (default: 2) |
| **Priority** | Configurable | Lower numeric value = higher priority. | `priority_preemptive` (`true` / `false`) |
| **EcoSched** | Preemptive / Adaptive | Composite policy balancing green energy, thermals, deadlines, and aging. | `ecosched_config`, `renewable_profile`, `thermal_config` |

---

## 4. The EcoSched Adaptive Policy

EcoSched selects which process to execute using a dynamically computed scheduling score:

$$\text{score} = w_{urgency} \cdot U_p(t) + \text{renewable\_bonus} + \text{aging\_bonus} - \text{thermal\_penalty}$$

### A. Workload Urgency ($U_p(t)$)
1. **Base Workload Weight**:
   - `critical`: Base urgency = $5.0$
   - `normal`: Base urgency = $2.0$
   - `flexible`: Base urgency = $1.0$
2. **Base Priority Factor**:
   - $\text{prio\_factor} = \max(0, (5 - \text{priority}) \times 0.2)$
3. **Deadline Urgency**:
   - $\text{slack} = \text{deadline} - (\text{current\_time} + \text{remaining\_time})$
   - If $\text{slack} \le 0$: Extreme emergency ($+25.0 + 2.0 \cdot |\text{slack}|$)
   - If $0 < \text{slack} \le 4$: High urgency ($+15.0 \cdot \frac{4 - \text{slack}}{4}$)
   - If $4 < \text{slack} \le 12$: Moderate urgency ($+5.0 \cdot \frac{12 - \text{slack}}{8}$)
   - If no deadline: $0.0$

### B. Renewable-Aware Scheduling & Deferral
- $R(t) \in [0.0, 1.0]$ represents the green energy availability fraction at time $t$.
- **Surplus Green Energy** ($R(t) \ge R_{high}$, default $0.70$):
  - Flexible workloads receive a bonus: $\text{bonus} = w_{renewable} \cdot R(t) \cdot (1.0 + \text{cpu\_intensity})$.
- **Scarce Green Energy** ($R(t) < R_{low}$, default $0.35$):
  - Flexible workloads are eligible for **deferral** if $\text{slack} > \text{min\_slack\_for\_deferral}$.
  - **Critical and urgent tasks are NEVER deferred** to optimize the energy metric.
  - To prevent starvation, tasks can only be deferred up to `max_consecutive_deferrals` (default 3). Once reached, execution is forced.

### C. Modeled Thermal Dissipation & Thermal Guard
- Modeled temperature $T(t)$ follows Newton's cooling law and activity-based heating:
  $$\Delta T = \left( h \cdot \text{cpu\_intensity} - c \cdot (T(t) - T_{amb}) \right) \Delta t$$
- If $T(t) > T_{warn}$ ($65^\circ\text{C}$):
  - $\text{thermal\_penalty} = w_{thermal} \cdot \text{cpu\_intensity} \cdot \frac{T - T_{warn}}{T_{crit} - T_{warn}}$
- **Thermal Guard Protection** ($T(t) \ge T_{crit}$, $80^\circ\text{C}$):
  - If an urgent/critical task is ready, it runs to prevent deadline violation.
  - Otherwise, low CPU-intensity tasks ($\le 0.35$) are prioritized.
  - If only high-intensity non-urgent tasks exist, EcoSched enforces a 1-tick **cooldown idle cycle** to allow the system to cool down safely.

### D. Aging & Starvation Freedom
- $\text{aging\_bonus} = w_{aging} \cdot \frac{\text{waiting\_time}(t)}{\text{aging\_threshold}}$
- Accumulated waiting time progressively increases priority, guaranteeing that even lower-priority flexible tasks are scheduled.

### E. Adaptive Time Quantum
Instead of a rigid quantum, EcoSched tunes duration $Q$:
- **Safe thermals & High Renewables**: $Q = Q_{max}$ ($4$ ticks) for flexible batch jobs to minimize context-switch overhead and exploit clean energy.
- **Thermal Warning or Tight Slack**: $Q = Q_{min}$ ($1$ tick) for immediate cooling checks and prompt responsiveness.
- **Standard conditions**: $Q = Q_{base}$ ($2$ ticks).

---

## 5. Energy and Thermal Modeling Notes

> [!NOTE]
> **Academic Integrity & Engineering Honesty**:
> - Modeled temperature ($^\circ\text{C}$) and energy proxies are **simulated research proxies** calculated from workload CPU intensity, activity duration, and renewable availability fractions.
> - They do not reflect physical motherboard telemetry or hardware watt-meter readings.
> - EcoSched does not guarantee winning every metric: for instance, deferring jobs to consume green energy may increase average waiting time or makespan. The goal is to provide a transparent, reproducible evaluation of the trade-offs between responsiveness and green computing.

---

## 6. REST API Reference for Frontend Integration

### Base URL: `http://127.0.0.1:8000`

### 1. Health Check
- **Endpoint**: `GET /health`
- **Response**:
```json
{
  "status": "healthy",
  "service": "EcoSched API",
  "version": "1.0.0"
}
```

---

### 2. Get Algorithms Metadata
- **Endpoint**: `GET /api/algorithms`
- **Response**: Returns supported algorithms, descriptions, and configurable parameter schemas.

---

### 3. Get Workload & Environmental Presets
- **Endpoint**: `GET /api/examples`
- **Response**: Pre-built workloads (`balanced_mix`, `green_surge`, `thermal_stress`), renewable profiles (`diurnal_solar`, `constant_green`, `scarce_grid`), and thermal profiles (`standard_datacenter`, `hot_edge_gateway`). The frontend can use these to populate dropdown preset selectors.

---

### 4. Run Single Simulation
- **Endpoint**: `POST /api/simulate`
- **Payload Example**:
```json
{
  "processes": [
    {
      "pid": "P1",
      "name": "Auth Service",
      "arrival_time": 0.0,
      "burst_time": 4.0,
      "priority": 1,
      "workload_type": "critical",
      "cpu_intensity": 0.4,
      "deadline": 10.0
    },
    {
      "pid": "P2",
      "name": "Image Rendering Task",
      "arrival_time": 1.0,
      "burst_time": 6.0,
      "priority": 4,
      "workload_type": "flexible",
      "cpu_intensity": 0.85,
      "deadline": 25.0
    }
  ],
  "algorithm": "ecosched",
  "time_quantum": 2,
  "renewable_profile": {
    "intervals": [
      {"start_time": 0.0, "end_time": 5.0, "availability": 0.25},
      {"start_time": 5.0, "end_time": 15.0, "availability": 0.85}
    ],
    "default_availability": 0.40
  }
}
```

- **PowerShell Request**:
```powershell
$body = @{
    processes = @(
        @{ pid = "P1"; arrival_time = 0.0; burst_time = 4.0; workload_type = "critical"; priority = 1 },
        @{ pid = "P2"; arrival_time = 1.0; burst_time = 6.0; workload_type = "flexible"; priority = 4 }
    )
    algorithm = "ecosched"
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/simulate" -Method Post -Body $body -ContentType "application/json"
```

- **Key Response Fields**:
  - `intervals`: Array of objects (`pid`, `start`, `end`, `reason`, `modeled_temp_start`, `modeled_temp_end`, `renewable_availability`). **Directly bind this array to render your Gantt Chart!**
  - `process_metrics`: Array of objects with per-process `completion_time`, `turnaround_time`, `waiting_time`, `response_time`, `deadline_met`, `execution_intervals_count`.
  - `system_metrics`: Aggregate metrics (`average_waiting_time`, `average_turnaround_time`, `average_response_time`, `throughput`, `makespan`, `cpu_utilization`, `context_switches`, `deadline_success_rate`, `estimated_grid_energy_proxy`, `renewable_utilization_percent`, `peak_modeled_temperature`).
  - `time_series`: Array of snapshots (`time`, `active_pid`, `modeled_temperature`, `renewable_availability`) for plotting thermal and green-energy line charts.
  - `decision_log`: Full audit trail of each scheduling dispatch decision.

---

### 5. Multi-Algorithm Side-by-Side Comparison
- **Endpoint**: `POST /api/compare`
- **Description**: Runs **FCFS**, **SJF**, **Round Robin**, **Priority Scheduling**, and **EcoSched** against the exact same workload and environment.
- **Payload Example**:
```json
{
  "processes": [
    {"pid": "P1", "arrival_time": 0.0, "burst_time": 4.0, "priority": 1, "workload_type": "critical"},
    {"pid": "P2", "arrival_time": 1.0, "burst_time": 5.0, "priority": 2, "workload_type": "normal"},
    {"pid": "P3", "arrival_time": 2.0, "burst_time": 6.0, "priority": 4, "workload_type": "flexible"}
  ],
  "time_quantum": 2,
  "priority_preemptive": false
}
```

- **PowerShell Request**:
```powershell
$body = @{
    processes = @(
        @{ pid = "P1"; arrival_time = 0.0; burst_time = 4.0; priority = 1; workload_type = "critical" },
        @{ pid = "P2"; arrival_time = 1.0; burst_time = 5.0; priority = 2; workload_type = "normal" },
        @{ pid = "P3"; arrival_time = 2.0; burst_time = 6.0; priority = 4; workload_type = "flexible" }
    )
    time_quantum = 2
} | ConvertTo-Json -Depth 5

$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/compare" -Method Post -Body $body -ContentType "application/json"
$response.summary_table | Format-Table algorithm, display_name, avg_waiting_time, grid_energy_proxy, peak_temperature
```

- **Key Response Fields**:
  - `summary_table`: Array of rows (one per algorithm) with comparable metrics (`avg_waiting_time`, `avg_turnaround_time`, `makespan`, `throughput`, `cpu_utilization`, `context_switches`, `grid_energy_proxy`, `renewable_utilization_percent`, `peak_temperature`).
  - `results`: Map containing the full `SimulationResponse` (with Gantt intervals) for each algorithm (`fcfs`, `sjf`, `round_robin`, `priority`, `ecosched`).
  - `workload_summary`: Counts of critical, normal, flexible tasks and total burst time.

---

## 7. Connecting the Frontend

1. **CORS is Pre-Configured**: The backend permits requests from any origin (`allow_origins=["*"]`), so your teammate can run a React, Vue, Svelte, or vanilla JS frontend on `http://localhost:3000` or `http://localhost:5173` without encountering CORS errors.
2. **Standard HTTP Error Codes**:
   - `422 Unprocessable Entity`: Input validation failed (e.g. negative time, duplicate PID, empty workload). The `detail` field contains the specific reason.
   - `200 OK`: Successful simulation or comparison.
3. **Gantt Chart Mapping**:
   Each item in `intervals` has:
   ```typescript
   interface ExecutionInterval {
     pid: string;                  // "P1", "P2", or "IDLE"
     start: number;                // e.g. 0.0
     end: number;                  // e.g. 2.0
     reason: string;               // e.g. "Critical task priority"
     workload_type?: string;       // "critical", "normal", "flexible", or null
     cpu_intensity?: number;       // 0.0 to 1.0
     modeled_temp_start?: number;  // °C
     modeled_temp_end?: number;    // °C
     renewable_availability?: number; // 0.0 to 1.0
   }
   ```
   Filter intervals where `pid !== "IDLE"` to color processes, or render `"IDLE"` blocks in grey to visualize idle cooling and green-deferral cycles.

---

## 8. Verification and Test Results

The backend has been verified with Pytest:
- **Total Tests**: 33 passed, 0 failed.
- **Coverage**:
  - FCFS, SJF, Round Robin, and Priority execution ordering and preemption.
  - EcoSched urgency calculation, deadline slack, renewable bonus, and flexible deferral.
  - Starvation prevention via aging bonus and consecutive deferral limits.
  - Modeled thermal dissipation, thermal guard cooldown cycles, and critical task deadline overrides.
  - Context switch counts, idle intervals, throughput, and CPU utilization formulas.
  - Full API integration, input validation (duplicate PID, empty workload, negative times), and CORS response headers.
