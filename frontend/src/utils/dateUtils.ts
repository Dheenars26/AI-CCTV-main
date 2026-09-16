/**
 * Safe DateTime utilities for parsing and formatting CCTV incident timestamps.
 * Handles both standard ISO-8601 strings and naive SQLite timestamps without timezone offset.
 */

export const parseSafeDate = (val?: string | number | Date | null): Date => {
  if (!val) return new Date(0);
  if (val instanceof Date) return isNaN(val.getTime()) ? new Date(0) : val;
  if (typeof val === 'number') return new Date(val);
  
  const str = String(val).trim();
  if (!str) return new Date(0);

  // If string is an ISO / SQL datetime without timezone (e.g. "2026-09-15 05:18:24.259" or "2026-09-15T05:18:24"),
  // treat it as UTC by appending 'Z'
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(str)) {
    return new Date(str.replace(' ', 'T') + 'Z');
  }

  const d = new Date(str);
  return isNaN(d.getTime()) ? new Date(0) : d;
};

export const getSafeTimestamp = (item?: any): number => {
  if (!item) return 0;
  const raw = item.triggered_at || item.start_time || item.created_at || item.timestamp;
  return parseSafeDate(raw).getTime();
};

export const formatSafeTime = (val?: string | number | Date | null): string => {
  const d = parseSafeDate(val);
  if (d.getTime() === 0) return '--:--:--';
  return d.toLocaleTimeString();
};

export const formatSafeDateTime = (val?: string | number | Date | null): string => {
  const d = parseSafeDate(val);
  if (d.getTime() === 0) return '--';
  return d.toLocaleString();
};
