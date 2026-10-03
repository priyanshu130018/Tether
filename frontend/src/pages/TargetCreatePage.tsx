import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, PlusCircle, Server, Shield, Globe } from 'lucide-react';
import { createTarget } from '../api/targets';
import { Protocol, TargetCreate } from '../types';

export const TargetCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [name, setName] = useState('');
  const [hostname, setHostname] = useState('');
  const [protocol, setProtocol] = useState<Protocol>('tcp');
  const [port, setPort] = useState<number | ''>(80);
  const [intervalSeconds, setIntervalSeconds] = useState<number>(60);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(5);
  const [retryCount, setRetryCount] = useState<number>(0);
  const [enabled, setEnabled] = useState<boolean>(true);

  // HTTP / HTTPS dynamic config
  const [httpMethod, setHttpMethod] = useState<string>('GET');
  const [httpPath, setHttpPath] = useState<string>('/');
  const [expectedStatusCodes, setExpectedStatusCodes] = useState<string>('200');
  const [followRedirects, setFollowRedirects] = useState<boolean>(true);
  const [verifySsl, setVerifySsl] = useState<boolean>(true);

  // DNS dynamic config
  const [recordType, setRecordType] = useState<string>('A');
  const [expectedRecords, setExpectedRecords] = useState<string>('');
  const [nameserver, setNameserver] = useState<string>('');

  const [formError, setFormError] = useState<string | null>(null);

  const handleProtocolChange = (p: Protocol) => {
    setProtocol(p);
    if (p === 'http') setPort(80);
    else if (p === 'https') setPort(443);
    else if (p === 'dns') setPort(53);
    else setPort(80);
  };

  const createMutation = useMutation({
    mutationFn: (data: TargetCreate) => createTarget(data),
    onSuccess: (newTarget) => {
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardSummary'] });
      navigate(`/targets/${newTarget.id}`);
    },
    onError: (err: any) => {
      setFormError(err.message || 'Failed to create target');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!name.trim()) {
      setFormError('Target name is required');
      return;
    }
    if (!hostname.trim()) {
      setFormError('Host or domain name is required');
      return;
    }

    const payload: TargetCreate = {
      name: name.trim(),
      hostname: hostname.trim(),
      protocol,
      port: port ? Number(port) : 80,
      interval_seconds: Number(intervalSeconds),
      timeout_seconds: Number(timeoutSeconds),
      retry_count: Number(retryCount),
      enabled,
      config: {},
    };

    if (protocol === 'http' || protocol === 'https') {
      const codes = expectedStatusCodes
        .split(',')
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !isNaN(n));

      payload.config = {
        method: httpMethod,
        path: httpPath.startsWith('/') ? httpPath : `/${httpPath}`,
        expected_status_codes: codes.length > 0 ? codes : [200],
        follow_redirects: followRedirects,
        verify_ssl: verifySsl,
      };
    } else if (protocol === 'dns') {
      const expList = expectedRecords
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      payload.config = {
        record_type: recordType,
        expected_records: expList.length > 0 ? expList : undefined,
        nameserver: nameserver.trim() ? nameserver.trim() : undefined,
      };
    }

    createMutation.mutate(payload);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link
          to="/targets"
          className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Add Monitoring Target</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Configure automated periodic checks across TCP, HTTP, HTTPS, or DNS.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {formError && (
          <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs font-mono">
            {formError}
          </div>
        )}

        {/* General Target Details */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 space-y-4 backdrop-blur-sm">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Server className="w-4 h-4 text-emerald-400" />
            <span>Target Endpoint</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div>
              <label htmlFor="target-name" className="block text-slate-300 mb-1.5 font-medium">
                Target Name *
              </label>
              <input
                id="target-name"
                type="text"
                placeholder="e.g. Primary Production API"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label htmlFor="target-protocol" className="block text-slate-300 mb-1.5 font-medium">
                Protocol *
              </label>
              <select
                id="target-protocol"
                value={protocol}
                onChange={(e) => handleProtocolChange(e.target.value as Protocol)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="tcp">TCP (Socket handshake)</option>
                <option value="http">HTTP (Web probe)</option>
                <option value="https">HTTPS (TLS encrypted web probe)</option>
                <option value="dns">DNS (Domain resolution)</option>
              </select>
            </div>

            <div>
              <label htmlFor="target-host" className="block text-slate-300 mb-1.5 font-medium">
                Host / IP / Domain *
              </label>
              <input
                id="target-host"
                type="text"
                placeholder="e.g. api.example.com or 192.168.1.10"
                value={hostname}
                onChange={(e) => setHostname(e.target.value)}
                required
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label htmlFor="target-port" className="block text-slate-300 mb-1.5 font-medium">
                Port
              </label>
              <input
                id="target-port"
                type="number"
                value={port}
                onChange={(e) => setPort(e.target.value ? parseInt(e.target.value, 10) : '')}
                min={1}
                max={65535}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* Protocol Specific Configuration */}
        {(protocol === 'http' || protocol === 'https') && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 space-y-4 backdrop-blur-sm">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Globe className="w-4 h-4 text-sky-400" />
              <span>HTTP / HTTPS Configuration</span>
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div>
                <label htmlFor="http-method" className="block text-slate-300 mb-1.5 font-medium">
                  HTTP Method
                </label>
                <select
                  id="http-method"
                  value={httpMethod}
                  onChange={(e) => setHttpMethod(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  <option value="GET">GET</option>
                  <option value="HEAD">HEAD</option>
                  <option value="POST">POST</option>
                  <option value="PUT">PUT</option>
                  <option value="DELETE">DELETE</option>
                  <option value="PATCH">PATCH</option>
                  <option value="OPTIONS">OPTIONS</option>
                </select>
              </div>

              <div>
                <label htmlFor="http-path" className="block text-slate-300 mb-1.5 font-medium">
                  Request Path
                </label>
                <input
                  id="http-path"
                  type="text"
                  placeholder="/health"
                  value={httpPath}
                  onChange={(e) => setHttpPath(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label htmlFor="expected-codes" className="block text-slate-300 mb-1.5 font-medium">
                  Expected Status Codes (comma-separated)
                </label>
                <input
                  id="expected-codes"
                  type="text"
                  placeholder="200, 201, 204"
                  value={expectedStatusCodes}
                  onChange={(e) => setExpectedStatusCodes(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex flex-col justify-center space-y-2 pt-2">
                <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={followRedirects}
                    onChange={(e) => setFollowRedirects(e.target.checked)}
                    className="rounded bg-slate-950 border-slate-800 text-emerald-500 focus:ring-0"
                  />
                  <span>Follow HTTP 3xx Redirects</span>
                </label>

                {protocol === 'https' && (
                  <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={verifySsl}
                      onChange={(e) => setVerifySsl(e.target.checked)}
                      className="rounded bg-slate-950 border-slate-800 text-emerald-500 focus:ring-0"
                    />
                    <span>Verify SSL/TLS Certificate</span>
                  </label>
                )}
              </div>
            </div>
          </div>
        )}

        {protocol === 'dns' && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 space-y-4 backdrop-blur-sm">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Globe className="w-4 h-4 text-purple-400" />
              <span>DNS Configuration</span>
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div>
                <label htmlFor="record-type" className="block text-slate-300 mb-1.5 font-medium">
                  Record Type
                </label>
                <select
                  id="record-type"
                  value={recordType}
                  onChange={(e) => setRecordType(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  <option value="A">A (IPv4)</option>
                  <option value="AAAA">AAAA (IPv6)</option>
                  <option value="CNAME">CNAME (Canonical Name)</option>
                  <option value="MX">MX (Mail Exchange)</option>
                  <option value="TXT">TXT (Text)</option>
                  <option value="NS">NS (Name Server)</option>
                </select>
              </div>

              <div>
                <label htmlFor="expected-records" className="block text-slate-300 mb-1.5 font-medium">
                  Expected Records (Optional, comma-separated)
                </label>
                <input
                  id="expected-records"
                  type="text"
                  placeholder="e.g. 93.184.216.34"
                  value={expectedRecords}
                  onChange={(e) => setExpectedRecords(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="md:col-span-2">
                <label htmlFor="nameserver-ip" className="block text-slate-300 mb-1.5 font-medium">
                  Custom Nameserver IP (Optional)
                </label>
                <input
                  id="nameserver-ip"
                  type="text"
                  placeholder="e.g. 1.1.1.1 or 8.8.8.8"
                  value={nameserver}
                  onChange={(e) => setNameserver(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* Scheduling & Execution Policies */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 space-y-4 backdrop-blur-sm">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-400" />
            <span>Scheduling & Retry Policy</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
            <div>
              <label htmlFor="interval-sec" className="block text-slate-300 mb-1.5 font-medium">
                Interval (Seconds)
              </label>
              <input
                id="interval-sec"
                type="number"
                min={10}
                value={intervalSeconds}
                onChange={(e) => setIntervalSeconds(parseInt(e.target.value, 10))}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label htmlFor="timeout-sec" className="block text-slate-300 mb-1.5 font-medium">
                Timeout (Seconds)
              </label>
              <input
                id="timeout-sec"
                type="number"
                step="0.5"
                min={1}
                max={60}
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(parseFloat(e.target.value))}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label htmlFor="retry-count" className="block text-slate-300 mb-1.5 font-medium">
                Retry Count
              </label>
              <input
                id="retry-count"
                type="number"
                min={0}
                max={5}
                value={retryCount}
                onChange={(e) => setRetryCount(parseInt(e.target.value, 10))}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <div className="pt-2">
            <label className="flex items-center gap-2 text-xs font-mono text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="rounded bg-slate-950 border-slate-800 text-emerald-500 focus:ring-0"
              />
              <span>Enable automatic scheduled monitoring immediately</span>
            </label>
          </div>
        </div>

        {/* Submit Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Link
            to="/targets"
            className="px-4 py-2 rounded-lg border border-slate-800 text-xs font-mono font-medium text-slate-300 hover:bg-slate-800 transition-colors"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold shadow-lg shadow-emerald-950/40 transition-colors disabled:opacity-50"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{createMutation.isPending ? 'Creating Target...' : 'Create Target'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
