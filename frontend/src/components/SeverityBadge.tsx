import React from 'react';

interface SeverityBadgeProps {
  severity?: "CRITICAL" | "WARNING" | "INFO" | string | null;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity }) => {
  const norm = (severity || 'CRITICAL').toUpperCase();

  let styles = "bg-slate-100 text-slate-700 border-slate-200";
  if (norm === 'CRITICAL' || norm === 'FIRE' || norm === 'ALERT_SENT') {
    styles = "bg-rose-50 text-rose-700 border-rose-300 animate-pulse-fast shadow-xs";
  } else if (norm === 'WARNING' || norm === 'SMOKE' || norm === 'POSSIBLE' || norm === 'CONFIRMED') {
    styles = "bg-amber-50 text-amber-800 border-amber-300 shadow-xs";
  } else if (norm === 'INFO' || norm === 'CLEARED' || norm === 'NORMAL') {
    styles = "bg-blue-50 text-blue-700 border-blue-200 shadow-xs";
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider border ${styles}`}>
      {norm}
    </span>
  );
};
