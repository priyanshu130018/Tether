import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Server, 
  Database, 
  Cpu, 
  Activity, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle,
  ShieldCheck, 
  BarChart2, 
  RefreshCw,
  Loader2
} from 'lucide-react';
import { getSystemHealth } from '../api/system';
import { getWorkers } from '../api/workers';
import { Button } from '../components/ui/Button';

export const SystemStatusPage: React.FC = () => {
  const { 
    data: health, 
    isLoading: isHealthLoading, 
    isFetching: isHealthFetching, 
    isError: isHealthError,
    error: healthError,
    refetch: refetchHealth 
  } = useQuery({
    queryKey: ['system-health'],
    queryFn: getSystemHealth,
    refetchInterval: 10000,
  });

  const { data: workers = [], isFetching: isWorkersFetching } = useQuery({
    queryKey: ['workers'],
    queryFn: getWorkers,
    refetchInterval: 10000,
  });

  const formatUptime = (seconds?: number): string => {
    if (!seconds && seconds !== 0) return '—';
    const d = Math.floor(seconds / (3600 * 24));
    const h = Math.floor((seconds % (3600 * 24)) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
  };

  const status = isHealthError
    ? 'error'
    : isHealthLoading
    ? 'checking'
    : health?.status === 'healthy'
    ? 'healthy'
    : health?.status === 'degraded'
    ? 'degraded'
    : 'unhealthy';

  const statusConfig = {
    checking: {
      title: 'Checking System Status...',
      description: 'Contacting API and infrastructure dependencies...',
      icon: <Loader2 className="h-6 w-6 text-sky-400 animate-spin shrink-0" />,
      bannerStyle: 'bg-slate-900 border-slate-700 text-slate-200',
    },
    healthy: {
      title: 'All Core Systems Operational',
      description: 'API, PostgreSQL cluster, Redis broker, and Celery worker mesh are responding normally.',
      icon: <CheckCircle2 className="h-6 w-6 text-emerald-400 shrink-0" />,
      bannerStyle: 'bg-emerald-950/20 border-emerald-900/50 text-emerald-200',
    },
    degraded: {
      title: 'Degraded Infrastructure Status',
      description: 'One or more subsystem dependencies are experiencing latency or connectivity degradation.',
      icon: <AlertTriangle className="h-6 w-6 text-amber-400 shrink-0" />,
      bannerStyle: 'bg-amber-950/20 border-amber-900/50 text-amber-200',
    },
    unhealthy: {
      title: 'Critical Infrastructure Outage',
      description: 'Primary database or broker dependencies are unreachable. Automated checks cannot run.',
      icon: <XCircle className="h-6 w-6 text-rose-400 shrink-0" />,
      bannerStyle: 'bg-rose-950/20 border-rose-900/50 text-rose-200',
    },
    error: {
      title: 'Failed to Fetch Health Status',
      description: (healthError as any)?.message || 'The API server did not return a valid health response.',
      icon: <XCircle className="h-6 w-6 text-rose-400 shrink-0" />,
      bannerStyle: 'bg-rose-950/20 border-rose-900/50 text-rose-200',
    },
  }[status];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2.5">
            <Activity className="h-5 w-5 text-emerald-400" />
            System Observability & Infrastructure
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time health status, cluster worker telemetry, and platform diagnostics.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="/metrics"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium rounded-lg inline-flex items-center gap-1.5 transition"
          >
            <BarChart2 className="h-3.5 w-3.5 text-indigo-400" />
            Prometheus Metrics
          </a>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refetchHealth()}
            isLoading={isHealthFetching || isWorkersFetching}
            leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Main Status Banner */}
      <div className={`p-4 rounded-xl border ${statusConfig.bannerStyle} flex items-center justify-between`}>
        <div className="flex items-center gap-3">
          {statusConfig.icon}
          <div>
            <h3 className="font-semibold text-sm text-slate-100">
              {statusConfig.title}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {statusConfig.description}
            </p>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-3 text-xs">
          <span className="px-2.5 py-1 bg-slate-950/60 rounded border border-slate-800 font-mono text-slate-300">
            Environment: {health?.environment || '—'}
          </span>
          <span className="px-2.5 py-1 bg-slate-950/60 rounded border border-slate-800 font-mono text-slate-300">
            Version: {health?.version || '—'}
          </span>
        </div>
      </div>

      {/* Component Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* API Server */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">FastAPI Service</span>
            <Server className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${isHealthError ? 'bg-rose-400' : isHealthLoading ? 'bg-sky-400 animate-pulse' : 'bg-emerald-400'}`} />
            <span className="text-base font-bold text-slate-100">
              {isHealthError ? 'Unreachable' : isHealthLoading ? 'Checking...' : 'Healthy'}
            </span>
          </div>
          <div className="text-xs text-slate-400 flex items-center justify-between pt-2 border-t border-slate-800">
            <span>Uptime</span>
            <span className="font-mono text-slate-200">{formatUptime(health?.uptime_seconds)}</span>
          </div>
        </div>

        {/* Database */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">PostgreSQL (Neon)</span>
            <Database className="h-4 w-4 text-sky-400" />
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isHealthLoading
                  ? 'bg-sky-400 animate-pulse'
                  : health?.database === 'healthy'
                  ? 'bg-emerald-400'
                  : 'bg-rose-400'
              }`}
            />
            <span className="text-base font-bold text-slate-100 capitalize">
              {isHealthLoading ? 'Checking...' : health?.database || 'Unhealthy'}
            </span>
          </div>
          <div className="text-xs text-slate-400 flex items-center justify-between pt-2 border-t border-slate-800">
            <span>Pool Mode</span>
            <span className="text-slate-300">Active (Pre-ping)</span>
          </div>
        </div>

        {/* Redis */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Redis Broker (Upstash)</span>
            <Activity className="h-4 w-4 text-rose-400" />
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isHealthLoading
                  ? 'bg-sky-400 animate-pulse'
                  : health?.redis === 'healthy'
                  ? 'bg-emerald-400'
                  : 'bg-rose-400'
              }`}
            />
            <span className="text-base font-bold text-slate-100 capitalize">
              {isHealthLoading ? 'Checking...' : health?.redis || 'Unhealthy'}
            </span>
          </div>
          <div className="text-xs text-slate-400 flex items-center justify-between pt-2 border-t border-slate-800">
            <span>Locking & Rate Limit</span>
            <span className="text-slate-300">
              {health?.redis === 'healthy' ? 'Operational' : 'Fallback Mode'}
            </span>
          </div>
        </div>

        {/* Celery Cluster */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Worker Mesh</span>
            <Cpu className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${workers.length > 0 ? 'bg-emerald-400' : 'bg-slate-500'}`} />
            <span className="text-base font-bold text-slate-100">
              {workers.length} Active {workers.length === 1 ? 'Node' : 'Nodes'}
            </span>
          </div>
          <div className="text-xs text-slate-400 flex items-center justify-between pt-2 border-t border-slate-800">
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
            <div className="font-semibold text-slate-300 mb-1">Reverse Proxy & Ingress</div>
            <p className="text-slate-400 leading-relaxed">Nginx edge container providing HTTP routing, rate limiting, gzip compression, and security headers.</p>
          </div>
          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
            <div className="font-semibold text-slate-300 mb-1">Multi-Tenant Boundary</div>
            <p className="text-slate-400 leading-relaxed">PostgreSQL tenant-scoped foreign keys, IDOR 404 shields, and cross-tenant worker isolation.</p>
          </div>
          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
            <div className="font-semibold text-slate-300 mb-1">Task Reliability & Retries</div>
            <p className="text-slate-400 leading-relaxed">Celery `acks_late=True`, `task_reject_on_worker_lost=True`, and exponential backoff retry queues.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
