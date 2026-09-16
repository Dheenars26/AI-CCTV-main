import React from 'react';

interface StatusBadgeProps {
  status?: string | null;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const normalized = (status || 'UNKNOWN').toUpperCase();

  let colorClasses = "bg-slate-100 text-slate-600 border-slate-200";
  let dotColor = "bg-slate-400";

  if (normalized === 'CONNECTED' || normalized === 'ONLINE' || normalized === 'OPERATIONAL') {
    colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200";
    dotColor = "bg-emerald-500 animate-pulse";
  } else if (normalized === 'DISCONNECTED' || normalized === 'OFFLINE' || normalized === 'ERROR') {
    colorClasses = "bg-rose-50 text-rose-700 border-rose-200";
    dotColor = "bg-rose-500";
  } else if (normalized === 'CONNECTING' || normalized === 'RECONNECTING' || normalized === 'DEGRADED') {
    colorClasses = "bg-amber-50 text-amber-800 border-amber-200";
    dotColor = "bg-amber-500 animate-ping";
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${colorClasses} shadow-xs`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      {normalized}
    </span>
  );
};
