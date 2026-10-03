export function formatLatency(latencyMs?: number | null): string {
  if (latencyMs === undefined || latencyMs === null) return '—';
  if (latencyMs < 1) return `${(latencyMs * 1000).toFixed(0)}µs`;
  return `${latencyMs.toFixed(1)}ms`;
}

export function formatDate(dateString?: string | null): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return dateString;
  }
}

export function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const isFuture = diffMs < 0;
    const absDiff = Math.abs(diffMs);

    const seconds = Math.floor(absDiff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (seconds < 10) return isFuture ? 'in a few secs' : 'just now';
    if (seconds < 60) return isFuture ? `in ${seconds}s` : `${seconds}s ago`;
    if (minutes < 60) return isFuture ? `in ${minutes}m` : `${minutes}m ago`;
    if (hours < 24) return isFuture ? `in ${hours}h` : `${hours}h ago`;
    return isFuture ? `in ${days}d` : `${days}d ago`;
  } catch {
    return dateString;
  }
}
