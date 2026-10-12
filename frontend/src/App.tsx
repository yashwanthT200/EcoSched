import React, { useState, useEffect } from "react";
import { fetchPresets, runSimulation, runComparison } from "./services/api";
import type { ProcessInput, SimulationResponse, ComparisonResponse } from "./services/api";
import { GanttChart } from "./components/GanttChart";
import { TelemetryChart } from "./components/TelemetryChart";
import { ComparisonTable } from "./components/ComparisonTable";
import { 
  Zap, 
  Thermometer, 
  Leaf, 
  Clock, 
  Cpu, 
  Plus, 
  Trash2, 
  Activity, 
  BarChart3, 
  FileText 
} from "lucide-react";

export default function App() {
  const [processes, setProcesses] = useState<ProcessInput[]>([]);
  const [algorithm, setAlgorithm] = useState("ecosched");
  const [timeQuantum, setTimeQuantum] = useState(2);
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);
  const [comparisonResult, setComparisonResult] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"charts" | "leaderboard" | "decisions">("charts");

  // New process form state
  const [newPid, setNewPid] = useState("P6");
  const [newName, setNewName] = useState("Custom Analytics");
  const [newArrival, setNewArrival] = useState(3.0);
  const [newBurst, setNewBurst] = useState(4.0);
  const [newPriority, setNewPriority] = useState(3);
  const [newType, setNewType] = useState<"critical" | "normal" | "flexible">("flexible");
  const [newIntensity, setNewIntensity] = useState(0.7);

  // Auto-run initial simulation on load
  useEffect(() => {
    fetchPresets().then(async (data) => {
      if (data?.workloads?.balanced_mix?.processes) {
        const initialProcs = data.workloads.balanced_mix.processes;
        setProcesses(initialProcs);
        
        // Auto simulate immediately on boot
        try {
          setLoading(true);
          const simRes = await runSimulation({ processes: initialProcs, algorithm: "ecosched", time_quantum: 2 });
          setSimulationResult(simRes);
          const compRes = await runComparison({ processes: initialProcs, time_quantum: 2 });
          setComparisonResult(compRes);
        } catch (err) {
          console.error("Auto-run failed:", err);
        } finally {
          setLoading(false);
        }
      }
    });
  }, []);

  const handleSimulate = async () => {
    setLoading(true);
    try {
      const res = await runSimulation({ processes, algorithm, time_quantum: timeQuantum });
      setSimulationResult(res);
      setActiveTab("charts");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCompareAll = async () => {
    setLoading(true);
    try {
      const res = await runComparison({ processes, time_quantum: timeQuantum });
      setComparisonResult(res);
      if (res.results.ecosched) {
        setSimulationResult(res.results.ecosched);
      }
      setActiveTab("leaderboard");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddProcess = () => {
    if (processes.some((p) => p.pid === newPid)) {
      alert(`Process ID '${newPid}' already exists!`);
      return;
    }
    const proc: ProcessInput = {
      pid: newPid,
      name: newName,
      arrival_time: Number(newArrival),
      burst_time: Number(newBurst),
      priority: Number(newPriority),
      workload_type: newType,
      cpu_intensity: Number(newIntensity),
    };
    setProcesses([...processes, proc]);
    setNewPid(`P${processes.length + 2}`);
  };

  const handleDeleteProcess = (pid: string) => {
    setProcesses(processes.filter((p) => p.pid !== pid));
  };

  const sys = simulationResult?.system_metrics;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6 w-full font-sans antialiased">
      {/* Header Bar */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400">
              <Leaf className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-teal-200 bg-clip-text text-transparent">
                EcoSched Engine
              </h1>
              <p className="text-xs text-slate-400">Renewable-Aware & Thermal-Guarded CPU Simulator</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <button
            onClick={handleSimulate}
            disabled={loading}
            className="flex-1 md:flex-none px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium rounded-xl border border-slate-700 transition flex items-center justify-center gap-2 text-sm shadow-sm"
          >
            <Activity className="w-4 h-4 text-emerald-400" />
            {loading ? "Running..." : "Simulate Selected"}
          </button>
          <button
            onClick={handleCompareAll}
            disabled={loading}
            className="flex-1 md:flex-none px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold rounded-xl transition shadow-lg shadow-emerald-950/40 flex items-center justify-center gap-2 text-sm"
          >
            <Zap className="w-4 h-4" />
            Compare All Algorithms
          </button>
        </div>
      </header>

      {/* Top Telemetry KPI Cards */}
      {sys && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl flex items-center gap-4">
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl">
              <Leaf className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-slate-400">Renewable Util</div>
              <div className="text-xl font-bold text-slate-100">{sys.renewable_utilization_percent.toFixed(1)}%</div>
            </div>
          </div>

          <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl flex items-center gap-4">
            <div className="p-3 bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 rounded-xl">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-slate-400">Grid Energy Proxy</div>
              <div className="text-xl font-bold text-slate-100">{sys.estimated_grid_energy_proxy.toFixed(1)} Ws</div>
            </div>
          </div>

          <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl flex items-center gap-4">
            <div className={`p-3 rounded-xl border ${sys.peak_modeled_temperature >= 75 ? "bg-rose-500/10 border-rose-500/30 text-rose-400" : "bg-amber-500/10 border-amber-500/20 text-amber-400"}`}>
              <Thermometer className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-slate-400">Peak Temperature</div>
              <div className="text-xl font-bold text-slate-100">{sys.peak_modeled_temperature.toFixed(1)}°C</div>
            </div>
          </div>

          <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl flex items-center gap-4">
            <div className="p-3 bg-purple-500/10 border border-purple-500/20 text-purple-400 rounded-xl">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-slate-400">Avg Wait Time</div>
              <div className="text-xl font-bold text-slate-100">{sys.average_waiting_time.toFixed(2)}s</div>
            </div>
          </div>
        </div>
      )}

      {/* Main Grid: Controls + Visualizations */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Sidebar Controls (4 columns) */}
        <div className="lg:col-span-4 space-y-6">
          
          {/* Algorithm Config */}
          <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-4">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Cpu className="w-4 h-4 text-emerald-400" />
              Algorithm Selector
            </h2>
            
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Target Policy</label>
                <select
                  value={algorithm}
                  onChange={(e) => setAlgorithm(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  <option value="ecosched">EcoSched (Adaptive Green & Thermal)</option>
                  <option value="fcfs">First Come First Serve (FCFS)</option>
                  <option value="sjf">Shortest Job First (SJF)</option>
                  <option value="round_robin">Round Robin</option>
                  <option value="priority">Priority Scheduling</option>
                </select>
              </div>

              {algorithm === "round_robin" && (
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Time Quantum (ticks)</label>
                  <input
                    type="number"
                    min={1}
                    value={timeQuantum}
                    onChange={(e) => setTimeQuantum(Number(e.target.value))}
                    className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Workload Queue & Add Process */}
          <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Workload Queue ({processes.length})
              </h2>
            </div>

            {/* List */}
            <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
              {processes.map((p) => (
                <div
                  key={p.pid}
                  className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-xl text-xs space-y-1.5 hover:border-slate-700 transition"
                >
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-slate-200">{p.pid} — {p.name}</span>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold capitalize ${
                        p.workload_type === "critical" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" :
                        p.workload_type === "normal" ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" :
                        "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                      }`}>
                        {p.workload_type}
                      </span>
                      <button
                        onClick={() => handleDeleteProcess(p.pid)}
                        className="text-slate-500 hover:text-rose-400 transition"
                        title="Remove process"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-slate-400 text-[11px]">
                    <span>Arrival: <strong className="text-slate-300">{p.arrival_time}s</strong></span>
                    <span>Burst: <strong className="text-slate-300">{p.burst_time}s</strong></span>
                    <span>CPU Load: <strong className="text-slate-300">{p.cpu_intensity}</strong></span>
                  </div>
                </div>
              ))}
            </div>

            {/* Add Process Drawer */}
            <div className="pt-3 border-t border-slate-800 space-y-3">
              <div className="text-xs font-semibold text-slate-400 flex items-center gap-1">
                <Plus className="w-3.5 h-3.5 text-emerald-400" /> Add Custom Task
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <input
                  type="text"
                  placeholder="PID (e.g. P6)"
                  value={newPid}
                  onChange={(e) => setNewPid(e.target.value)}
                  className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                />
                <input
                  type="text"
                  placeholder="Task Name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                />
                <input
                  type="number"
                  placeholder="Arrival (s)"
                  value={newArrival}
                  onChange={(e) => setNewArrival(Number(e.target.value))}
                  className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                />
                <input
                  type="number"
                  placeholder="Burst (s)"
                  value={newBurst}
                  onChange={(e) => setNewBurst(Number(e.target.value))}
                  className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                />
                <select
                  value={newType}
                  onChange={(e: any) => setNewType(e.target.value)}
                  className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                >
                  <option value="critical">Critical</option>
                  <option value="normal">Normal</option>
                  <option value="flexible">Flexible</option>
                </select>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="1.0"
                  placeholder="CPU Load (0.1-1.0)"
                  value={newIntensity}
                  onChange={(e) => setNewIntensity(Number(e.target.value))}
                  className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                />
              </div>
              <button
                onClick={handleAddProcess}
                className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-emerald-400 font-semibold rounded-lg text-xs transition border border-slate-700"
              >
                + Append to Queue
              </button>
            </div>
          </div>
        </div>

        {/* Main Display Area (8 columns) */}
        <div className="lg:col-span-8 space-y-6">
          
          {/* Navigation Tabs */}
          <div className="flex border-b border-slate-800 gap-2">
            <button
              onClick={() => setActiveTab("charts")}
              className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
                activeTab === "charts"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <BarChart3 className="w-4 h-4" /> Timeline & Telemetry
            </button>
            <button
              onClick={() => setActiveTab("leaderboard")}
              className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
                activeTab === "leaderboard"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Zap className="w-4 h-4" /> Algorithm Leaderboard
            </button>
            <button
              onClick={() => setActiveTab("decisions")}
              className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
                activeTab === "decisions"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <FileText className="w-4 h-4" /> Decision Audit Trail
            </button>
          </div>

          {/* Tab 1: Charts */}
          {activeTab === "charts" && simulationResult && (
            <div className="space-y-6">
              <GanttChart intervals={simulationResult.intervals} makespan={simulationResult.system_metrics.makespan} />
              <TelemetryChart timeSeries={simulationResult.time_series} />
            </div>
          )}

          {/* Tab 2: Comparison Leaderboard */}
          {activeTab === "leaderboard" && (
            <div>
              {comparisonResult ? (
                <ComparisonTable rows={comparisonResult.summary_table} />
              ) : (
                <div className="p-12 text-center text-slate-500 border border-slate-800 rounded-2xl bg-slate-900/40">
                  Click <strong>"Compare All Algorithms"</strong> at the top to compute evaluations across all 5 policies.
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Decision Audit Trail */}
          {activeTab === "decisions" && simulationResult && (
            <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-3">
              <h3 className="text-sm font-semibold text-slate-200">Explainable Dispatch Log</h3>
              <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                {simulationResult.decision_log.map((log, i) => (
                  <div key={i} className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl text-xs flex justify-between items-start gap-4">
                    <div>
                      <div className="font-bold text-emerald-400 mb-0.5">
                        t = {log.time}s — Selected PID: {log.selected_pid}
                      </div>
                      <div className="text-slate-300">{log.reason}</div>
                    </div>
                    {log.score !== null && (
                      <div className="px-2.5 py-1 bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 rounded-lg font-mono font-bold">
                        Score: {log.score}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}