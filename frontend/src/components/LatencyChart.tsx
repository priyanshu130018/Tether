import React, { useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { LatencyPoint } from '../types';
import { formatDate } from '../utils/formatters';

interface LatencyChartProps {
  data: LatencyPoint[];
  isLoading?: boolean;
  onRangeChange?: (range: string) => void;
  selectedRange?: string;
}

export const LatencyChart: React.FC<LatencyChartProps> = ({
  data,
  isLoading = false,
  onRangeChange,
  selectedRange = '24h',
}) => {
  const [range, setRange] = useState(selectedRange);

  const ranges = ['1h', '6h', '24h', '7d'];

  const handleRange = (r: string) => {
    setRange(r);
    if (onRangeChange) onRangeChange(r);
  };

  const chartData = (data || []).map((point) => ({
    time: point.timestamp,
    latency: point.status === 'down' ? null : point.latency_ms,
    status: point.status,
    statusCode: point.status_code,
  }));

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const p = payload[0].payload;
      return (
        <div className="bg-slate-900 border border-slate-700 p-3 rounded-lg shadow-xl text-xs font-mono">
          <p className="text-slate-400 mb-1">{formatDate(label)}</p>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Status:</span>
            <span className={p.status === 'up' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
              {p.status.toUpperCase()}
            </span>
          </div>
          {p.latency !== null ? (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-slate-400">Latency:</span>
              <span className="text-emerald-400 font-bold">{p.latency.toFixed(1)} ms</span>
            </div>
          ) : (
            <div className="text-rose-400 mt-1">Check Failed / Timeout</div>
          )}
          {p.statusCode && (
            <div className="flex items-center gap-2 mt-1 text-slate-400">
              <span>HTTP Code:</span>
              <span className="text-slate-200">{p.statusCode}</span>
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 backdrop-blur-sm">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Latency & Performance
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">Response time over time in milliseconds</p>
        </div>
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-mono">
          {ranges.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => handleRange(r)}
              className={`px-3 py-1 rounded-md transition-colors ${
                range === r
                  ? 'bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="h-64 w-full">
        {isLoading ? (
          <div className="h-full w-full flex items-center justify-center text-slate-500 text-xs font-mono animate-pulse">
            Loading chart data...
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-full w-full flex items-center justify-center text-slate-500 text-xs font-mono">
            No check results recorded for this time window.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f293d" vertical={false} />
              <XAxis
                dataKey="time"
                tickFormatter={(val) => {
                  try {
                    const d = new Date(val);
                    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
                  } catch {
                    return val;
                  }
                }}
                stroke="#64748b"
                tick={{ fontSize: 11, fontFamily: 'monospace' }}
              />
              <YAxis
                stroke="#64748b"
                tick={{ fontSize: 11, fontFamily: 'monospace' }}
                unit="ms"
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="latency"
                stroke="#10b981"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#latencyGradient)"
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};
