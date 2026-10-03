import { describe, it, expect } from 'vitest';
import { formatLatency, formatRelativeTime, formatDate } from '../utils/formatters';

describe('Formatters utility', () => {
  it('formats latency values correctly', () => {
    expect(formatLatency(undefined)).toBe('—');
    expect(formatLatency(null)).toBe('—');
    expect(formatLatency(0.4)).toBe('400µs');
    expect(formatLatency(42.56)).toBe('42.6ms');
    expect(formatLatency(150.0)).toBe('150.0ms');
  });

  it('formats date and relative times without throwing', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatRelativeTime(null)).toBe('—');

    const pastDate = new Date(Date.now() - 1000 * 60 * 5).toISOString(); // 5 mins ago
    expect(formatRelativeTime(pastDate)).toContain('5m ago');

    const futureDate = new Date(Date.now() + 1000 * 60 * 30).toISOString(); // in 30 mins
    expect(formatRelativeTime(futureDate)).toContain('in 30m');
  });
});
