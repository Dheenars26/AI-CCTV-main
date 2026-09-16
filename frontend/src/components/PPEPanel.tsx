import React from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, Glasses } from 'lucide-react';

export interface WorkerPPE {
  person_id: number;
  status: 'PASS' | 'VIOLATION' | 'UNKNOWN';
  required_equipment: string[];
  detected_equipment: string[];
  missing_equipment: string[];
  confidence: number;
}

interface PPEPanelProps {
  workers: WorkerPPE[];
}

export const PPEPanel: React.FC<PPEPanelProps> = ({ workers }) => {
  if (!workers || workers.length === 0) {
    return (
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center text-slate-400 text-xs font-medium">
        No active workers detected in frame
      </div>
    );
  }

  const allItems = ['helmet', 'vest', 'goggles', 'gloves', 'safety_shoes'];

  const getItemAliases = (item: string): string[] => {
    if (item === 'vest') return ['vest', 'safety_vest', 'safety vest', 'jacket', 'hivis'];
    if (item === 'goggles') return ['goggles', 'glasses', 'safety_glasses', 'safety_glass', 'safety glass', 'glass', 'eyewear', 'spec', 'specs', 'spectacles', 'protective_glasses', 'safety_goggles'];
    return [item];
  };

  const getDisplayLabel = (item: string): string => {
    if (item === 'vest') return 'safety vest';
    if (item === 'goggles') return 'safety glasses';
    return item.replace('_', ' ');
  };

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
        Worker PPE Compliance Status ({workers.length})
      </h3>

      <div className="grid grid-cols-1 gap-2.5">
        {workers.map((worker) => {
          const isPass = worker.status === 'PASS';
          const isViolation = worker.status === 'VIOLATION';

          return (
            <div
              key={worker.person_id}
              className={`p-3.5 rounded-xl border flex flex-col justify-between transition-all shadow-xs ${
                isPass
                  ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
                  : isViolation
                  ? 'bg-rose-50/70 border-rose-200 text-rose-950'
                  : 'bg-amber-50/70 border-amber-200 text-amber-950'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  {isPass ? (
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  ) : isViolation ? (
                    <ShieldAlert className="w-4 h-4 text-rose-600" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                  )}
                  <span className="font-bold text-xs">Worker #{worker.person_id}</span>
                </div>

                <span
                  className={`px-2 py-0.5 text-[10px] font-bold rounded-full border shadow-2xs ${
                    isPass
                      ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                      : isViolation
                      ? 'bg-rose-100 text-rose-800 border-rose-300'
                      : 'bg-amber-100 text-amber-800 border-amber-300'
                  }`}
                >
                  {worker.status}
                </span>
              </div>

              {/* Equipment Grid */}
              <div className="grid grid-cols-3 gap-1.5 mt-1">
                {allItems.map((item) => {
                  const aliases = getItemAliases(item);
                  const isReq = worker.required_equipment?.some((e) => aliases.includes(e.toLowerCase()));
                  const isDet = worker.detected_equipment?.some((e) => aliases.includes(e.toLowerCase()));
                  const isMiss = worker.missing_equipment?.some((e) => aliases.includes(e.toLowerCase()));

                  let badgeColor = 'bg-slate-100 text-slate-500 border-slate-200';
                  let icon = '•';

                  if (isDet) {
                    badgeColor = 'bg-emerald-100/80 text-emerald-800 border-emerald-300 font-semibold';
                    icon = '✓';
                  } else if (isMiss) {
                    badgeColor = 'bg-rose-100 text-rose-800 border-rose-300 font-bold';
                    icon = '✕';
                  } else if (!isReq) {
                    badgeColor = 'bg-slate-100/70 text-slate-400 border-slate-200/70';
                    icon = '-';
                  }

                  return (
                    <div
                      key={item}
                      className={`px-2 py-1 rounded-lg text-[11px] border flex items-center justify-between capitalize ${badgeColor}`}
                    >
                      <span className="flex items-center gap-1 truncate">
                        {item === 'goggles' && <Glasses className="w-3 h-3 inline-block opacity-80" />}
                        {getDisplayLabel(item)}
                      </span>
                      <span className="font-mono text-[10px] ml-1">{icon}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PPEPanel;
