import React from "react";
import type { ExecutionInterval } from "../services/api";

interface Props {
  intervals: ExecutionInterval[];
  makespan: number;
}

export const getWorkloadColor = (pid: string, type?: string) => {
  if (pid === "IDLE") return "bg-slate-300 dark:bg-slate-700 text-slate-700 dark:text-slate-300 border-dashed";
  switch (type) {
    case "critical":
      return "bg-rose-500 text-white shadow-rose-200";
    case "normal":
      return "bg-blue-500 text-white shadow-blue-200";
    case "flexible":
      return "bg-emerald-500 text-white shadow-emerald-200";
    default:
      return "bg-indigo-500 text-white";
  }
};

export const GanttChart: React.FC<Props> = ({ intervals, makespan }) => {
  if (!intervals || intervals.length === 0 || makespan <= 0) return null;

  return (
    <div className="w-full bg-white dark:bg-slate-900 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
      <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-3">
        CPU Execution Timeline (Gantt Chart)
      </h3>

      <div className="relative h-16 w-full bg-slate-100 dark:bg-slate-800 rounded-lg overflow-hidden flex items-center">
        {intervals.map((item, idx) => {
          const duration = item.end - item.start;
          const widthPct = (duration / makespan) * 100;
          const colorClass = getWorkloadColor(item.pid, item.workload_type);

          return (
            <div
              key={idx}
              style={{ width: `${widthPct}%` }}
              title={`[${item.start}s -> ${item.end}s] ${item.pid} | Reason: ${item.reason}`}
              className={`h-12 border-r border-white/20 flex flex-col justify-center items-center text-xs font-bold transition-all hover:opacity-90 cursor-pointer ${colorClass}`}
            >
              <span>{item.pid}</span>
              <span className="text-[10px] opacity-80">{duration.toFixed(1)}s</span>
            </div>
          );
        })}
      </div>

      <div className="flex justify-between text-xs text-slate-400 mt-2 px-1">
        <span>0.0s</span>
        <span>{(makespan / 2).toFixed(1)}s</span>
        <span>{makespan.toFixed(1)}s</span>
      </div>

      <div className="flex gap-4 mt-4 text-xs font-medium text-slate-600 dark:text-slate-300">
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-rose-500"></span> Critical</div>
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-blue-500"></span> Normal</div>
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-emerald-500"></span> Flexible</div>
        <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-slate-400"></span> Cooling / Idle</div>
      </div>
    </div>
  );
};