import React from 'react';
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
  data = [],
  isLoading = false,
  onRangeChange,
  selectedRange = '24h',
}) => {
  const ranges = ['1h', '6h', '24h', '7d'];

  const handleRange = (r: string) => {
    if (onRangeChange) {
      onRangeChange(r);
    }
  };

  const pointsList: LatencyPoint[] = Array.isArray(data)
    ? data
    : (data as any)?.points || [];

  const chartData = pointsList.map((point) => ({
    time: point.timestamp,
    latency: point.status?.toLowerCase() === 'down' ? null : point.latency_ms,
    status: point.status,
    statusCode: point.status_code,
  }));

  // Calculate summary metrics
  const validLatencies = pointsList
    .map((d) => d.latency_ms)
    .filter((l): l is number => typeof l === 'number' && !isNaN(l) && l >= 0);

  const totalChecks = (data as any)?.total_checks ?? pointsList.length;
  const failureCount = pointsList.filter((d) => d.status?.toLowerCase() === 'down').length;
  const avgLatency =
    validLatencies.length > 0
      ? (validLatencies.reduce((a, b) => a + b, 0) / validLatencies.length).toFixed(1)
      : '—';
  const minLatency =
    validLatencies.length > 0 ? Math.min(...validLatencies).toFixed(1) : '—';
  const maxLatency =
    validLatencies.length > 0 ? Math.max(...validLatencies).toFixed(1) : '—';

  const formatXAxisTick = (val: string): string => {
    try {
      const d = new Date(val);
      if (isNaN(d.getTime())) return val;

      if (selectedRange === '1h' || selectedRange === '6h') {
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
      } else if (selectedRange === '24h') {
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
      } else {
        // 7d
        const month = d.toLocaleDateString([], { month: 'short' });
        const day = d.getDate();
        const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        return `${month} ${day}, ${time}`;
      }
    } catch {
      return val;
    }
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const p = payload[0].payload;
      return (
        <div className="bg-slate-900 border border-slate-700 p-3 rounded-lg shadow-xl text-xs font-mono">
          <p className="text-slate-400 mb-1">{formatDate(label)}</p>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Status:</span>
            <span className={p.status === 'up' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
              {p.status ? p.status.toUpperCase() : 'UNKNOWN'}
            </span>
          </div>
          {p.latency !== null && p.latency !== undefined ? (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-slate-400">Latency:</span>
              <span className="text-emerald-400 font-bold">{Number(p.latency).toFixed(1)} ms</span>
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
    <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-5">
      {/* Chart Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">
            Latency & Response Time History
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Probe response duration over selected time window
          </p>
        </div>
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-mono">
          {ranges.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => handleRange(r)}
              className={`px-3 py-1 rounded-md transition-all font-medium ${
                selectedRange === r
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5 p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 text-xs font-mono">
        <div>
          <div className="text-slate-400 text-[11px]">Avg Latency</div>
          <div className="text-sm font-bold text-slate-100 mt-0.5">
            {avgLatency !== '—' ? `${avgLatency} ms` : '—'}
          </div>
        </div>
        <div>
          <div className="text-slate-400 text-[11px]">Min Latency</div>
          <div className="text-sm font-bold text-emerald-400 mt-0.5">
            {minLatency !== '—' ? `${minLatency} ms` : '—'}
          </div>
        </div>
        <div>
          <div className="text-slate-400 text-[11px]">Max Latency</div>
          <div className="text-sm font-bold text-sky-400 mt-0.5">
            {maxLatency !== '—' ? `${maxLatency} ms` : '—'}
          </div>
        </div>
        <div>
          <div className="text-slate-400 text-[11px]">Total Checks</div>
          <div className="text-sm font-bold text-slate-200 mt-0.5">{totalChecks}</div>
        </div>
        <div>
          <div className="text-slate-400 text-[11px]">Outages / Failures</div>
          <div className={`text-sm font-bold mt-0.5 ${failureCount > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
            {failureCount}
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="h-64 w-full">
        {isLoading ? (
          <div className="h-full w-full flex items-center justify-center text-slate-500 text-xs font-mono animate-pulse">
            Loading latency metrics...
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-full w-full flex items-center justify-center text-slate-500 text-xs font-mono">
            No check results recorded in the last {selectedRange}.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis
                dataKey="time"
                tickFormatter={formatXAxisTick}
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
                strokeWidth={1.75}
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
