import React, { useState, useEffect } from "react";
import { fetchPresets, fetchDatasetsInfo, runSimulation, runComparison } from "./services/api";
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
  FileText,
  Database,
  CheckCircle2
} from "lucide-react";

export default function App() {
  const [presets, setPresets] = useState<any>(null);
  const [datasetsInfo, setDatasetsInfo] = useState<any>(null);
  const [selectedWorkloadPreset, setSelectedWorkloadPreset] = useState("spec_cpu_benchmarks");
  const [selectedRenewableProfile, setSelectedRenewableProfile] = useState("caiso_real_solar_24h");

  const [processes, setProcesses] = useState<ProcessInput[]>([]);
  const [algorithm, setAlgorithm] = useState("ecosched");
  const [timeQuantum, setTimeQuantum] = useState(2);
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);
  const [comparisonResult, setComparisonResult] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"charts" | "leaderboard" | "decisions" | "datasets">("charts");

  // Custom task form state
  const [newPid, setNewPid] = useState("P99");
  const [newName, setNewName] = useState("Custom Realtime Task");
  const [newArrival, setNewArrival] = useState(2.0);
  const [newBurst, setNewBurst] = useState(3.0);
  const [newPriority, setNewPriority] = useState(2);
  const [newType, setNewType] = useState<"critical" | "normal" | "flexible">("normal");
  const [newIntensity, setNewIntensity] = useState(0.6);

  // Helper to resolve renewable profile object for backend
  const getRenewableProfilePayload = (profileKey: string, presetsData: any) => {
    return presetsData?.renewable_profiles?.[profileKey] 
      || presetsData?.solar_profiles?.[profileKey]
      || { profile_name: profileKey, name: profileKey };
  };

  // Fetch presets and initial simulation on load
  useEffect(() => {
    async function initData() {
      try {
        setLoading(true);
        const data = await fetchPresets();
        setPresets(data);

        // Fetch datasets citation info
        fetchDatasetsInfo().then(info => setDatasetsInfo(info)).catch(() => {});

        const initialProcs = data?.workloads?.spec_cpu_benchmarks?.processes 
          || data?.workloads?.balanced_mix?.processes 
          || [];

        setProcesses(initialProcs);

        const profileObj = getRenewableProfilePayload("caiso_real_solar_24h", data);

        const simRes = await runSimulation({ 
          processes: initialProcs, 
          algorithm: "ecosched", 
          time_quantum: 2,
          renewable_profile: profileObj
        });
        setSimulationResult(simRes);

        const compRes = await runComparison({ 
          processes: initialProcs, 
          time_quantum: 2,
          renewable_profile: profileObj
        });
        setComparisonResult(compRes);
      } catch (err: any) {
        console.error("Initialization failed:", err);
      } finally {
        setLoading(false);
      }
    }
    initData();
  }, []);

  const executeSimulationAndComparison = async (procs: ProcessInput[], algo: string, profileKey: string, quantum: number) => {
    setLoading(true);
    try {
      const profileObj = getRenewableProfilePayload(profileKey, presets);

      const simRes = await runSimulation({ 
        processes: procs, 
        algorithm: algo, 
        time_quantum: quantum,
        renewable_profile: profileObj 
      });
      setSimulationResult(simRes);

      const compRes = await runComparison({ 
        processes: procs, 
        time_quantum: quantum,
        renewable_profile: profileObj 
      });
      setComparisonResult(compRes);
    } catch (err: any) {
      alert(err?.message || "Simulation failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleWorkloadPresetChange = async (presetKey: string) => {
    setSelectedWorkloadPreset(presetKey);
    const targetProcs = presets?.workloads?.[presetKey]?.processes;
    if (targetProcs) {
      setProcesses(targetProcs);
      await executeSimulationAndComparison(targetProcs, algorithm, selectedRenewableProfile, timeQuantum);
    }
  };

  const handleRenewableProfileChange = async (profileKey: string) => {
    setSelectedRenewableProfile(profileKey);
    await executeSimulationAndComparison(processes, algorithm, profileKey, timeQuantum);
  };

  const handleSimulate = async () => {
    setLoading(true);
    try {
      const profileObj = getRenewableProfilePayload(selectedRenewableProfile, presets);
      const res = await runSimulation({ 
        processes, 
        algorithm, 
        time_quantum: timeQuantum,
        renewable_profile: profileObj 
      });
      setSimulationResult(res);
      setActiveTab("charts");
    } catch (err: any) {
      alert(err?.message || "Simulation failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleCompareAll = async () => {
    setLoading(true);
    try {
      const profileObj = getRenewableProfilePayload(selectedRenewableProfile, presets);
      const res = await runComparison({ 
        processes, 
        time_quantum: timeQuantum,
        renewable_profile: profileObj 
      });
      setComparisonResult(res);
      if (res.results?.ecosched) {
        setSimulationResult(res.results.ecosched);
      }
      setActiveTab("leaderboard");
    } catch (err: any) {
      alert(err?.message || "Comparison failed.");
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
    setNewPid(`P${processes.length + 100}`);
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
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-teal-200 bg-clip-text text-transparent">
                  EcoSched Engine
                </h1>
                <span className="px-2.5 py-0.5 bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 rounded-full text-[11px] font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  Real Traces Active
                </span>
              </div>
              <p className="text-xs text-slate-400">CAISO Solar Trace & SPEC CPU / Google Cluster Benchmarks</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <button
            onClick={handleSimulate}
            disabled={loading}
            className="flex-1 md:flex-none px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium rounded-xl border border-slate-700 transition flex items-center justify-center gap-2 text-sm shadow-sm disabled:opacity-50"
          >
            <Activity className="w-4 h-4 text-emerald-400" />
            {loading ? "Running..." : "Simulate Selected"}
          </button>
          <button
            onClick={handleCompareAll}
            disabled={loading}
            className="flex-1 md:flex-none px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold rounded-xl transition shadow-lg shadow-emerald-950/40 flex items-center justify-center gap-2 text-sm disabled:opacity-50"
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
        
        {/* Sidebar Controls */}
        <div className="lg:col-span-4 space-y-6">
          
          {/* Real Dataset Preset Selector */}
          <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-4">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-400" />
              Real Data Presets
            </h2>

            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Workload Benchmark</label>
                <select
                  value={selectedWorkloadPreset}
                  onChange={(e) => handleWorkloadPresetChange(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  <option value="spec_cpu_benchmarks">SPEC CPU & OS Benchmarks (Real Data)</option>
                  <option value="google_cluster_trace">Google Borg Cluster Trace</option>
                  <option value="balanced_mix">Balanced Standard Mix</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Renewable Energy Profile</label>
                <select
                  value={selectedRenewableProfile}
                  onChange={(e) => handleRenewableProfileChange(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  <option value="caiso_real_solar_24h">CAISO Real 24-Hour Solar Grid Trace</option>
                  <option value="synthetic_solar">Synthetic Bell-Curve Solar</option>
                </select>
              </div>
            </div>
          </div>

          {/* Algorithm Config */}
          <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-4">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Cpu className="w-4 h-4 text-emerald-400" />
              Policy & Parameters
            </h2>
            
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Target Policy</label>
                <select
                  value={algorithm}
                  onChange={(e) => setAlgorithm(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
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
                    className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Workload Queue */}
          <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Workload Queue ({processes.length})
              </h2>
            </div>

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
                  placeholder="PID"
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
                  placeholder="CPU Load"
                  value={newIntensity}
                  onChange={(e) => setNewIntensity(Number(e.target.value))}
                  className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                />
              </div>
              <button
                onClick={handleAddProcess}
                className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-emerald-400 font-semibold rounded-lg text-xs transition border border-slate-700"
              >
                + Append Task to Queue
              </button>
            </div>
          </div>
        </div>

        {/* Main Display Area */}
        <div className="lg:col-span-8 space-y-6">
          
          {/* Navigation Tabs */}
          <div className="flex border-b border-slate-800 gap-2 overflow-x-auto">
            <button
              onClick={() => setActiveTab("charts")}
              className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
                activeTab === "charts"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <BarChart3 className="w-4 h-4" /> Timeline & Telemetry
            </button>
            <button
              onClick={() => setActiveTab("leaderboard")}
              className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
                activeTab === "leaderboard"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Zap className="w-4 h-4" /> Algorithm Leaderboard
            </button>
            <button
              onClick={() => setActiveTab("decisions")}
              className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
                activeTab === "decisions"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <FileText className="w-4 h-4" /> Decision Audit Trail
            </button>
            <button
              onClick={() => setActiveTab("datasets")}
              className={`pb-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
                activeTab === "datasets"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Database className="w-4 h-4" /> Dataset Citations
            </button>
          </div>

          {/* Tab 1: Charts */}
          {activeTab === "charts" && simulationResult && (
            <div className="space-y-6">
              <GanttChart intervals={simulationResult.intervals} makespan={simulationResult.system_metrics.makespan} />
              <TelemetryChart timeSeries={simulationResult.time_series} />
            </div>
          )}

          {/* Tab 2: Leaderboard */}
          {activeTab === "leaderboard" && (
            <div>
              {comparisonResult ? (
                <ComparisonTable rows={comparisonResult.summary_table} />
              ) : (
                <div className="p-12 text-center text-slate-500 border border-slate-800 rounded-2xl bg-slate-900/40">
                  Click <strong>"Compare All Algorithms"</strong> to compute multi-algorithm evaluations.
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Decision Log */}
          {activeTab === "decisions" && simulationResult && (
            <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-3">
              <h3 className="text-sm font-semibold text-slate-200">Explainable Dynamic Score Log</h3>
              <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                {simulationResult.decision_log.map((log, i) => (
                  <div key={i} className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-xl text-xs flex justify-between items-start gap-4">
                    <div>
                      <div className="font-bold text-emerald-400 mb-0.5">
                        t = {log.time}s — Selected Task: {log.selected_pid}
                      </div>
                      <div className="text-slate-300">{log.reason}</div>
                    </div>
                    {log.score !== null && (
                      <div className="px-2.5 py-1 bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 rounded-lg font-mono font-bold">
                        Utility: {log.score}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tab 4: Dataset Citations */}
          {activeTab === "datasets" && (
            <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-4 text-xs">
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Database className="w-4 h-4 text-emerald-400" /> Real-World Benchmark Citations
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2">
                  <div className="font-bold text-emerald-400">California ISO (CAISO) Solar Trace</div>
                  <p className="text-slate-400 leading-relaxed">
                    {datasetsInfo?.datasets?.caiso_real_solar_24h?.citation 
                      || "Real 24-hour solar generation power profile from California ISO open grid telemetry. Captures realistic zero-generation night periods, solar rise, peak noon generation, and rapid evening drop."}
                  </p>
                </div>

                <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2">
                  <div className="font-bold text-emerald-400">SPEC CPU2017 & Linux Benchmarks</div>
                  <p className="text-slate-400 leading-relaxed">
                    {datasetsInfo?.datasets?.spec_cpu_benchmarks?.citation 
                      || "Real execution metrics measured from standard OS benchmarks: FFmpeg H.264 transcoding, GCC kernel compilation, SQLite OLTP transactions, Blender Cycles rendering, and Redis memory cache lookups."}
                  </p>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}