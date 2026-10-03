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
import { Button } from '../components/ui/Button';
import { IconButton } from '../components/ui/IconButton';
import { useToast } from '../components/ui/Toast';
import { formatDate } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';

export const NotificationChannelsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { role, activeTenant } = useAuth();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [channelToDelete, setChannelToDelete] = useState<number | null>(null);
  const [testingChannelId, setTestingChannelId] = useState<number | null>(null);

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
      toast.success('Notification channel created successfully.');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err.message || 'Failed to create channel.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNotificationChannel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationChannels'] });
      setChannelToDelete(null);
      toast.success('Channel deleted successfully.');
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to delete channel.');
    },
  });

  const testMutation = useMutation({
    mutationFn: (id: number) => testNotificationChannel(id),
    onMutate: (id) => {
      setTestingChannelId(id);
    },
    onSuccess: (res, channelId) => {
      setTestingChannelId(null);
      if (res.success) {
        toast.success(`Channel #${channelId} test passed: ${res.message || 'Notification sent successfully'}`);
      } else {
        toast.error(`Channel #${channelId} test failed: ${res.message || 'Delivery failed'}`);
      }
    },
    onError: (err: any, channelId) => {
      setTestingChannelId(null);
      toast.error(`Channel #${channelId} test failed: ${err?.response?.data?.detail || err.message}`);
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
          <h1 className="text-xl font-bold text-slate-100">Notification Channels</h1>
          <p className="text-xs text-slate-400 mt-1">
            Configure SMTP email, Slack webhooks, and generic endpoints for instant outage and recovery alerts.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
            isLoading={isFetching}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
          {canManageChannels && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setCreateModalOpen(true)}
              leftIcon={<PlusCircle className="w-3.5 h-3.5" />}
            >
              Add Channel
            </Button>
          )}
        </div>
      </div>

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
                className="rounded-xl border border-slate-800 bg-slate-900 p-4 flex flex-col justify-between space-y-4"
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
                          ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800'
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

                <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs font-mono">
                  <span className="text-slate-500 text-[10px]">{formatDate(chan.created_at)}</span>
                  <div className="flex items-center gap-2">
                    {canManageChannels && (
                      <>
                        <Button
                          variant="secondary"
                          size="xs"
                          onClick={() => testMutation.mutate(chan.id)}
                          isLoading={testingChannelId === chan.id}
                          leftIcon={<Send className="w-3 h-3 text-emerald-400" />}
                        >
                          Test
                        </Button>
                        <IconButton
                          variant="danger"
                          size="xs"
                          onClick={() => setChannelToDelete(chan.id)}
                          icon={<Trash2 className="w-3.5 h-3.5" />}
                          aria-label="Delete channel"
                          title="Delete channel"
                        />
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
        <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
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
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
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
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-medium">Port</label>
                  <input
                    type="number"
                    value={smtpPort}
                    onChange={(e) => setSmtpPort(parseInt(e.target.value, 10) || 587)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
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
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-medium">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
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
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
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
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
                />
              </div>
              <div>
                <label className="block text-slate-300 mb-1 font-medium">Authorization Header (Optional)</label>
                <input
                  type="text"
                  placeholder="Bearer your-secret-token"
                  value={authHeader}
                  onChange={(e) => setAuthHeader(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-xs"
                />
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={createMutation.isPending}
            >
              Create Channel
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={channelToDelete !== null}
        onClose={() => setChannelToDelete(null)}
        title="Confirm Channel Deletion"
        maxWidth="sm"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-300">
            Are you sure you want to delete this notification channel? It will be removed from all alert routing policies.
          </p>
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setChannelToDelete(null)}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => channelToDelete && deleteMutation.mutate(channelToDelete)}
              isLoading={deleteMutation.isPending}
            >
              Confirm Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
