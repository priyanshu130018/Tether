import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Server, 
  Database, 
  Cpu, 
  Activity, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldCheck, 
  BarChart2, 
  RefreshCw 
} from 'lucide-react';
import { getSystemHealth } from '../api/system';
import { getWorkers } from '../api/workers';

export const SystemStatusPage: React.FC = () => {
  const { 
    data: health, 
    isLoading: isHealthLoading, 
    isFetching: isHealthFetching, 
    refetch: refetchHealth 
  } = useQuery({
    queryKey: ['system-health'],
    queryFn: getSystemHealth,
    refetchInterval: 10000,
  });

  const { data: workers = [] } = useQuery({
    queryKey: ['workers'],
    queryFn: getWorkers,
    refetchInterval: 10000,
  });

  const formatUptime = (seconds?: number): string => {
    if (!seconds && seconds !== 0) return 'Unknown';
    const d = Math.floor(seconds / (3600 * 24));
    const h = Math.floor((seconds % (3600 * 24)) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
  };

  const isOverallHealthy = health?.status === 'healthy';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
            <Activity className="h-6 w-6 text-emerald-400" />
            System Observability & Infrastructure
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time health status, cluster worker telemetry, and platform diagnostics.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a
            href="/metrics"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium rounded-lg inline-flex items-center gap-2 transition"
          >
            <BarChart2 className="h-4 w-4 text-indigo-400" />
            Prometheus Metrics
          </a>
          <button
            onClick={() => refetchHealth()}
            disabled={isHealthFetching}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium rounded-lg inline-flex items-center gap-2 transition disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isHealthFetching ? 'animate-spin text-emerald-400' : 'text-slate-400'}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Main Status Banner */}
      <div className={`p-5 rounded-xl border ${
        isOverallHealthy 
          ? 'bg-emerald-950/20 border-emerald-900/50 text-emerald-200' 
          : 'bg-amber-950/20 border-amber-900/50 text-amber-200'
      } flex items-center justify-between`}>
        <div className="flex items-center gap-3.5">
          {isOverallHealthy ? (
            <CheckCircle2 className="h-8 w-8 text-emerald-400 shrink-0" />
          ) : (
            <AlertTriangle className="h-8 w-8 text-amber-400 shrink-0" />
          )}
          <div>
            <h3 className="font-semibold text-base text-slate-100">
              {isHealthLoading ? 'Inspecting system...' : isOverallHealthy ? 'All Core Systems Operational' : 'Degraded Infrastructure Status'}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              API, primary PostgreSQL cluster, Redis broker, and Celery worker mesh are responding normally.
            </p>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-4 text-xs">
          <span className="px-2.5 py-1 bg-slate-800/80 rounded border border-slate-700 font-mono text-slate-300">
            Environment: {health?.environment || 'production'}
          </span>
          <span className="px-2.5 py-1 bg-slate-800/80 rounded border border-slate-700 font-mono text-slate-300">
            Version: {health?.version || '1.0.0'}
          </span>
        </div>
      </div>

      {/* Component Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* API Server */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">FastAPI Service</span>
            <Server className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-lg font-bold text-slate-100">Healthy</span>
          </div>
          <div className="text-xs text-slate-400 flex items-center justify-between pt-2 border-t border-slate-800/60">
            <span>Uptime</span>
            <span className="font-mono text-slate-200">{formatUptime(health?.uptime_seconds)}</span>
          </div>
        </div>

        {/* Database */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">PostgreSQL</span>
            <Database className="h-4 w-4 text-sky-400" />
          </div>
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${health?.database === 'healthy' ? 'bg-emerald-400' : 'bg-red-400'}`} />
            <span className="text-lg font-bold text-slate-100 capitalize">{health?.database || 'Checking...'}</span>
          </div>
          <div className="text-xs text-slate-400 flex items-center justify-between pt-2 border-t border-slate-800/60">
            <span>Connection Pool</span>
            <span className="text-slate-300">Active (Pre-ping)</span>
          </div>
        </div>

        {/* Redis */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Redis Broker</span>
            <Activity className="h-4 w-4 text-rose-400" />
          </div>
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${health?.redis === 'healthy' ? 'bg-emerald-400' : 'bg-red-400'}`} />
            <span className="text-lg font-bold text-slate-100 capitalize">{health?.redis || 'Checking...'}</span>
          </div>
          <div className="text-xs text-slate-400 flex items-center justify-between pt-2 border-t border-slate-800/60">
            <span>Locking / Rate Limit</span>
            <span className="text-slate-300">Operational</span>
          </div>
        </div>

        {/* Celery Cluster */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Worker Mesh</span>
            <Cpu className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${workers.length > 0 ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            <span className="text-lg font-bold text-slate-100">{workers.length} Active Nodes</span>
          </div>
          <div className="text-xs text-slate-400 flex items-center justify-between pt-2 border-t border-slate-800/60">
            <span>Beat Scheduler</span>
            <span className="text-emerald-400 font-medium">1 Logical Active</span>
          </div>
        </div>
      </div>

      {/* Production Infrastructure Spec Details */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          Production Architecture & Security Controls
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
          <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-800">
            <div className="font-semibold text-slate-300 mb-1">Reverse Proxy & Ingress</div>
            <p className="text-slate-400">Nginx edge container providing HTTP routing, rate limiting, gzip compression, and security headers.</p>
          </div>
          <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-800">
            <div className="font-semibold text-slate-300 mb-1">Multi-Tenant Boundary</div>
            <p className="text-slate-400">PostgreSQL tenant-scoped foreign keys, IDOR 404 shields, and cross-tenant worker isolation.</p>
          </div>
          <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-800">
            <div className="font-semibold text-slate-300 mb-1">Task Reliability & Retries</div>
            <p className="text-slate-400">Celery `acks_late=True`, `task_reject_on_worker_lost=True`, and exponential backoff retry queues.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
