import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Radio,
  PlusCircle,
  Send,
  Trash2,
  Mail,
  MessageSquare,
  Webhook,
  CheckCircle2,
  XCircle,
  RefreshCw,
  EyeOff,
} from 'lucide-react';
import {
  getNotificationChannels,
  createNotificationChannel,
  deleteNotificationChannel,
  testNotificationChannel,
} from '../api/notifications';
import { ChannelType, NotificationChannelCreate } from '../types';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorState } from '../components/ErrorState';
import { EmptyState } from '../components/EmptyState';
import { Modal } from '../components/Modal';
import { formatDate } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';

export const NotificationChannelsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { role, activeTenant } = useAuth();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ channelId: number; success: boolean; message: string } | null>(null);

  const canManageChannels = role === 'OWNER' || role === 'ADMIN';

  // Form State
  const [name, setName] = useState('');
  const [type, setType] = useState<ChannelType>('SLACK');
  const [enabled, setEnabled] = useState(true);

  // Email Config
  const [smtpHost, setSmtpHost] = useState('');
  const [smtpPort, setSmtpPort] = useState(587);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fromEmail, setFromEmail] = useState('');
  const [toEmails, setToEmails] = useState('');

  // Slack / Webhook Config
  const [webhookUrl, setWebhookUrl] = useState('');
  const [authHeader, setAuthHeader] = useState('');

  const {
    data: channels,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['notificationChannels', activeTenant?.id],
    queryFn: () => getNotificationChannels(),
  });

  const createMutation = useMutation({
    mutationFn: (data: NotificationChannelCreate) => createNotificationChannel(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationChannels'] });
      setCreateModalOpen(false);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNotificationChannel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notificationChannels'] }),
  });

  const testMutation = useMutation({
    mutationFn: (id: number) => testNotificationChannel(id),
    onSuccess: (res, channelId) => {
      setTestResult({
        channelId,
        success: res.success,
        message: res.message || (res.success ? 'Notification sent successfully' : 'Delivery failed'),
      });
    },
    onError: (err: any, channelId) => {
      setTestResult({
        channelId,
        success: false,
        message: err.message || 'Test delivery request failed',
      });
    },
  });

  const resetForm = () => {
    setName('');
    setType('SLACK');
    setEnabled(true);
    setSmtpHost('');
    setSmtpPort(587);
    setUsername('');
    setPassword('');
    setFromEmail('');
    setToEmails('');
    setWebhookUrl('');
    setAuthHeader('');
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const config: Record<string, any> = {};

    if (type === 'EMAIL') {
      config.smtp_host = smtpHost;
      config.smtp_port = smtpPort;
      if (username) config.username = username;
      if (password) config.password = password;
      if (fromEmail) config.from_email = fromEmail;
      config.to_emails = toEmails;
    } else if (type === 'SLACK') {
      config.webhook_url = webhookUrl;
    } else if (type === 'WEBHOOK') {
      config.url = webhookUrl;
      if (authHeader) {
        config.headers = { Authorization: authHeader };
      }
    }

    createMutation.mutate({
      name: name.trim(),
      type,
      enabled,
      configuration: config,
    });
  };

  if (error) {
    return <ErrorState message="Failed to load notification channels." onRetry={refetch} />;
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Notification Channels</h1>
          <p className="text-sm text-slate-400 mt-1 font-mono">
            Configure SMTP email, Slack webhooks, and generic endpoints for instant outage and recovery alerts.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            type="button"
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          {canManageChannels && (
            <button
              onClick={() => setCreateModalOpen(true)}
              type="button"
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Add Channel</span>
            </button>
          )}
        </div>
      </div>

      {/* Test Result Toast Banner */}
      {testResult && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between text-xs font-mono backdrop-blur-sm ${
            testResult.success
              ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
              : 'bg-rose-950/40 border-rose-800 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-2.5">
            {testResult.success ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <XCircle className="w-4 h-4 text-rose-400" />
            )}
            <span>
              <strong>Channel #{testResult.channelId} Test:</strong> {testResult.message}
            </span>
          </div>
          <button
            onClick={() => setTestResult(null)}
            className="text-slate-400 hover:text-slate-200 text-xs underline ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Channels Grid / List */}
      {isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : !channels || channels.length === 0 ? (
        <EmptyState
          title="No notification channels configured"
          description="Create your first Slack, Email, or Webhook destination to receive outage and recovery alerts."
          icon={Radio}
          actionText={canManageChannels ? 'Add Notification Channel' : undefined}
          onAction={canManageChannels ? () => setCreateModalOpen(true) : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {channels.map((chan) => {
            const isEmail = chan.type === 'EMAIL';
            const isSlack = chan.type === 'SLACK';
            const Icon = isEmail ? Mail : isSlack ? MessageSquare : Webhook;

            return (
              <div
                key={chan.id}
                className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 backdrop-blur-sm flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-lg bg-slate-800 text-emerald-400 border border-slate-700">
                        <Icon className="w-4 h-4" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-100">{chan.name}</h3>
                        <span className="text-[10px] font-mono text-slate-500 uppercase">{chan.type}</span>
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                        chan.enabled
                          ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
                          : 'bg-slate-800 text-slate-500 border-slate-700'
                      }`}
                    >
                      {chan.enabled ? 'ACTIVE' : 'DISABLED'}
                    </span>
                  </div>

                  {/* Masked Configuration Details */}
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono space-y-1 text-slate-400">
                    <div className="flex items-center gap-1.5 text-slate-500 text-[10px] font-bold uppercase mb-1">
                      <EyeOff className="w-3 h-3" />
                      <span>Secured Parameters</span>
                    </div>
                    {isEmail && (
                      <>
                        <div>Host: <span className="text-slate-200">{chan.configuration.smtp_host}:{chan.configuration.smtp_port || 587}</span></div>
                        <div>To: <span className="text-slate-200">{chan.configuration.to_emails}</span></div>
                        <div>Password: <span className="text-slate-500">{chan.configuration.password || '********'}</span></div>
                      </>
                    )}
                    {isSlack && (
                      <div>Webhook: <span className="text-slate-200">{chan.configuration.webhook_url}</span></div>
                    )}
                    {chan.type === 'WEBHOOK' && (
                      <div>URL: <span className="text-slate-200">{chan.configuration.url}</span></div>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs font-mono">
                  <span className="text-slate-500 text-[10px]">{formatDate(chan.created_at)}</span>
                  <div className="flex items-center gap-2">
                    {canManageChannels && (
                      <>
                        <button
                          onClick={() => testMutation.mutate(chan.id)}
                          disabled={testMutation.isPending}
                          type="button"
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-slate-700 transition-colors"
                          title="Send test notification"
                        >
                          <Send className="w-3 h-3" />
                          <span>{testMutation.isPending ? 'Sending...' : 'Test'}</span>
                        </button>
                        <button
                          onClick={() => deleteMutation.mutate(chan.id)}
                          type="button"
                          className="p-1 rounded bg-slate-800 hover:bg-rose-950/60 text-slate-400 hover:text-rose-400 border border-slate-700 transition-colors"
                          title="Delete channel"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Channel Modal */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Add Notification Channel"
        maxWidth="md"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs font-mono">
          <div>
            <label className="block text-slate-300 mb-1 font-medium">Channel Name *</label>
            <input
              type="text"
              placeholder="e.g. Primary SRE Slack"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-slate-300 mb-1 font-medium">Channel Type *</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as ChannelType)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="SLACK">Slack Incoming Webhook</option>
              <option value="EMAIL">SMTP Email</option>
              <option value="WEBHOOK">Generic HTTP Webhook</option>
            </select>
          </div>

          {/* Type Specific Fields */}
          {type === 'SLACK' && (
            <div>
              <label className="block text-slate-300 mb-1 font-medium">Slack Webhook URL *</label>
              <input
                type="url"
                placeholder="https://hooks.slack.com/services/T00/B00/XXXXX"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                required
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>
          )}

          {type === 'EMAIL' && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                <div className="col-span-2">
                  <label className="block text-slate-300 mb-1 font-medium">SMTP Host *</label>
                  <input
                    type="text"
                    placeholder="smtp.mailgun.org"
                    value={smtpHost}
                    onChange={(e) => setSmtpHost(e.target.value)}
                    required
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-medium">Port</label>
                  <input
                    type="number"
                    value={smtpPort}
                    onChange={(e) => setSmtpPort(parseInt(e.target.value, 10))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-300 mb-1 font-medium">Username</label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-medium">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-slate-300 mb-1 font-medium">Recipients (To Emails) *</label>
                <input
                  type="text"
                  placeholder="alerts@domain.com, ops@domain.com"
                  value={toEmails}
                  onChange={(e) => setToEmails(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>
          )}

          {type === 'WEBHOOK' && (
            <div className="space-y-3">
              <div>
                <label className="block text-slate-300 mb-1 font-medium">Webhook URL *</label>
                <input
                  type="url"
                  placeholder="https://api.mycompany.com/alerts"
                  value={webhookUrl}
                  onChange={(e) => setWebhookUrl(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-slate-300 mb-1 font-medium">Authorization Header (Optional)</label>
                <input
                  type="text"
                  placeholder="Bearer your-secret-token"
                  value={authHeader}
                  onChange={(e) => setAuthHeader(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              onClick={() => setCreateModalOpen(false)}
              type="button"
              className="px-3.5 py-1.5 rounded-lg border border-slate-800 text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-colors"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Channel'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
