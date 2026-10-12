import React from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";

interface Props {
  timeSeries: Array<{
    time: number;
    active_pid: string;
    modeled_temperature: number;
    renewable_availability: number;
  }>;
}

export const TelemetryChart: React.FC<Props> = ({ timeSeries }) => {
  const formattedData = timeSeries.map((t) => ({
    time: t.time,
    temperature: t.modeled_temperature,
    renewablePct: Math.round(t.renewable_availability * 100),
  }));

  return (
    <div className="w-full bg-white dark:bg-slate-900 p-4 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
      <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-3">
        Thermal Dynamics & Renewable Availability Profile
      </h3>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={formattedData}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="time" unit="s" />
            <YAxis yAxisId="temp" domain={[20, 90]} unit="°C" />
            <YAxis yAxisId="ren" orientation="right" domain={[0, 100]} unit="%" />
            <Tooltip />
            <Legend />
            <Line yAxisId="temp" type="monotone" dataKey="temperature" name="Modeled Temp (°C)" stroke="#ef4444" strokeWidth={2} dot={false} />
            <Line yAxisId="ren" type="monotone" dataKey="renewablePct" name="Renewable Green Energy (%)" stroke="#10b981" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};