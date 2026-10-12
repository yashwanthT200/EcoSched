import React from "react";
import type { ComparisonSummaryRow } from "../services/api";

interface Props {
  rows: ComparisonSummaryRow[];
}

export const ComparisonTable: React.FC<Props> = ({ rows }) => {
  return (
    <div className="w-full bg-white dark:bg-slate-900 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-x-auto">
      <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-3">
        Multi-Algorithm Evaluation Summary
      </h3>
      <table className="w-full text-left text-sm border-collapse">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400">
            <th className="py-2 px-3">Algorithm</th>
            <th className="py-2 px-3">Avg Wait (s)</th>
            <th className="py-2 px-3">Avg Turnaround (s)</th>
            <th className="py-2 px-3">Makespan</th>
            <th className="py-2 px-3">Grid Energy Proxy</th>
            <th className="py-2 px-3">Renewable Util %</th>
            <th className="py-2 px-3">Peak Temp (°C)</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((r) => {
            const isEcoSched = r.algorithm === "ecosched";
            return (
              <tr
                key={r.algorithm}
                className={isEcoSched ? "bg-emerald-50/50 dark:bg-emerald-950/20 font-semibold text-emerald-900 dark:text-emerald-300" : "text-slate-700 dark:text-slate-300"}
              >
                <td className="py-2.5 px-3 flex items-center gap-2">
                  {isEcoSched && <span className="px-2 py-0.5 text-[10px] bg-emerald-500 text-white rounded-full">ECO</span>}
                  {r.display_name}
                </td>
                <td className="py-2.5 px-3">{r.avg_waiting_time.toFixed(2)}</td>
                <td className="py-2.5 px-3">{r.avg_turnaround_time.toFixed(2)}</td>
                <td className="py-2.5 px-3">{r.makespan.toFixed(1)}s</td>
                <td className="py-2.5 px-3 font-mono">{r.grid_energy_proxy.toFixed(1)}</td>
                <td className="py-2.5 px-3">{r.renewable_utilization_percent.toFixed(1)}%</td>
                <td className="py-2.5 px-3">
                  <span className={r.peak_temperature >= 80 ? "text-rose-600 font-bold" : ""}>
                    {r.peak_temperature.toFixed(1)}°C
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};