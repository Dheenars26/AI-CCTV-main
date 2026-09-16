import React, { useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alertsApi } from '../api/alerts';
import { camerasApi } from '../api/cameras';
import { SeverityBadge } from '../components/SeverityBadge';
import { StatusBadge } from '../components/StatusBadge';
import { PermissionGuard } from '../components/PermissionGuard';
import { useAuth } from '../context/AuthContext';
import {
  ArrowLeft, Flame, Wind, ShieldAlert, CheckCircle, MapPin,
  ClipboardList, ShieldCheck, UserCheck, Clock, FileText, X, Send, Wrench, Maximize2, Download
} from 'lucide-react';
import { resolveApiUrl } from '../config/apiConfig';

interface SopStep {
  step: number;
  title: string;
  desc: string;
}

const getSopGuidelines = (className: string): SopStep[] => {
  const c = (className || '').toLowerCase();
  if (c.includes('fire')) {
    return [
      { step: 1, title: 'Sound Emergency Alarm', desc: 'Trigger local building alarm or notify facility safety officer immediately.' },
      { step: 2, title: 'Deploy Fire Suppression', desc: 'Deploy nearest Class ABC dry chemical / CO2 extinguisher if safe to approach.' },
      { step: 3, title: 'Evacuate Surveillance Zone', desc: 'Ensure all personnel evacuate along designated emergency egress routes.' },
      { step: 4, title: 'Emergency Services Notification', desc: 'Call local emergency services (Fire Department) if threat exceeds incipient stage.' }
    ];
  }
  if (c.includes('smoke')) {
    return [
      { step: 1, title: 'Investigate Smoke Ingress', desc: 'Inspect source with protective respirator; assess heat or electrical overheating.' },
      { step: 2, title: 'HVAC Exhaust Damper Control', desc: 'Activate ventilation purge fans to extract hazardous fumes and smoke.' },
      { step: 3, title: 'Isolate Power & Machinery', desc: 'Shut off power breakers connected to machinery in the affected camera zone.' }
    ];
  }
  return [
    { step: 1, title: 'Halt Unsafe Activity', desc: 'Order worker to step back from hazardous machinery or restricted safety perimeter.' },
    { step: 2, title: 'Provide Required Equipment', desc: 'Issue high-visibility reflective vest and safety eye protection.' },
    { step: 3, title: 'Verify Compliance', desc: 'Ensure safety gear is properly worn and fastened before authorizing work resumption.' }
  ];
};

const getRemedyPresets = (className: string) => {
  const c = (className || '').toLowerCase();
  if (c.includes('fire')) {
    return [
      { id: 'EXTINGUISHER_DEPLOYED', label: 'Fire Extinguisher Deployed & Hazard Suppressed' },
      { id: 'EVACUATION_FIRE_DEPT', label: 'Area Evacuated & Fire Department Dispatched' },
      { id: 'PERMITTED_HOT_WORK', label: 'Permitted Hot Work / Controlled Flame Confirmed' },
      { id: 'FALSE_ALARM_GLARE', label: 'False Alarm (Camera Light / Optical Glare)' },
      { id: 'OTHER_ACTION', label: 'Other Corrective Action Taken' },
    ];
  }
  if (c.includes('smoke')) {
    return [
      { id: 'VENTILATION_ACTIVATED', label: 'Ventilation Damper Activated & Fumes Cleared' },
      { id: 'SOURCE_ISOLATED', label: 'Machine / Electrical Source Isolated' },
      { id: 'FALSE_ALARM_STEAM', label: 'False Alarm (Steam or Dust Particle Cloud)' },
      { id: 'OTHER_ACTION', label: 'Other Corrective Action Taken' },
    ];
  }
  return [
    { id: 'GEAR_ISSUED', label: 'Safety Vest / Glasses Issued & Equipped' },
    { id: 'WORKER_RELOCATED', label: 'Worker Removed from Hazardous Restricted Zone' },
    { id: 'SAFETY_WARNING', label: 'Formal Workplace Safety Warning Issued' },
    { id: 'FALSE_ALARM_OBSTRUCTION', label: 'False Alarm (Temporary Gear Visual Occlusion)' },
    { id: 'OTHER_ACTION', label: 'Other Corrective Action Taken' },
  ];
};

export const AlertDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [isRemedyFormOpen, setIsRemedyFormOpen] = useState<boolean>(false);
  const [isSnapshotExpanded, setIsSnapshotExpanded] = useState<boolean>(false);
  const [selectedRemedy, setSelectedRemedy] = useState<string>('');
  const [remedyNotes, setRemedyNotes] = useState<string>('');

  const { data: alertRes, isLoading } = useQuery({
    queryKey: ['alert', id],
    queryFn: async () => {
      try {
        return await alertsApi.get(id!);
      } catch (err) {
        // Fallback: if single alert lookup failed, check recent alerts
        try {
          const recent = await alertsApi.list({ limit: 5 });
          if (recent?.data && recent.data.length > 0) {
            const match = recent.data.find(
              (a: any) => String(a.id) === String(id) || String(a.alert_id) === String(id)
            ) || recent.data[0];
            return { data: match, success: true, status: 200 } as any;
          }
        } catch {
          // Ignore secondary failure and throw primary error
        }
        throw err;
      }
    },
    enabled: !!id,
    retry: 1,
  });

  const { data: camerasRes } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => camerasApi.list(),
  });

  const cameraMap = useMemo(() => {
    const map: Record<number, any> = {};
    (camerasRes?.data || []).forEach((c: any) => {
      map[c.id] = c;
    });
    return map;
  }, [camerasRes]);

  const acknowledgeMutation = useMutation({
    mutationFn: () => alertsApi.acknowledge(id!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alert', id] })
  });

  const resolveMutation = useMutation({
    mutationFn: (remedyData?: { remedial_action?: string; remedy_notes?: string; resolved_by?: string }) =>
      alertsApi.resolve(id!, remedyData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert', id] });
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['navbar-notifications'] });
      queryClient.invalidateQueries({ queryKey: ['system-stats'] });
      setIsRemedyFormOpen(false);
    }
  });

  const alert = alertRes?.data;
  const threatClass = alert?.class_name || 'fire';
  const sopSteps = getSopGuidelines(threatClass);
  const presets = getRemedyPresets(threatClass);

  const isResolved = alert?.state === 'RESOLVED' || alert?.status === 'RESOLVED' || alert?.state === 'CLEARED';

  const handleConfirmRemedy = (e: React.FormEvent) => {
    e.preventDefault();
    const actionLabel = presets.find(p => p.id === selectedRemedy)?.label || selectedRemedy || 'Corrective Remedial Action Executed';
    resolveMutation.mutate({
      remedial_action: actionLabel,
      remedy_notes: remedyNotes.trim() || undefined,
      resolved_by: user?.full_name || user?.username || 'Security Officer'
    });
  };

  if (isLoading) {
    return (
      <div className="p-12 text-center text-slate-400 bg-white rounded-2xl border border-slate-200/80 shadow-card">
        Loading notification inspection metadata...
      </div>
    );
  }

  if (!alert) {
    return (
      <div className="max-w-2xl mx-auto my-8 p-8 text-center bg-white rounded-2xl border border-slate-200/90 shadow-card space-y-5">
        <div className="w-14 h-14 bg-rose-50 text-rose-600 rounded-2xl flex items-center justify-center mx-auto border border-rose-100 shadow-xs">
          <ShieldAlert className="w-7 h-7 text-rose-500" />
        </div>
        <div>
          <h3 className="text-base font-bold text-slate-900 tracking-tight">
            Notification Event Record Not Found
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1.5 leading-relaxed">
            The requested security incident event record (<span className="font-mono font-semibold text-slate-700">{id}</span>) may have been resolved, cleared, or purged by automatic retention policies.
          </p>
        </div>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Link
            to="/notifications"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5"
          >
            <ArrowLeft className="w-4 h-4" /> View All Notifications
          </Link>
          <Link
            to="/monitoring"
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-medium border border-slate-200 transition-colors"
          >
            Live Surveillance
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card">
        <div className="flex items-center gap-3.5">
          <Link
            to="/notifications"
            className="p-2.5 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-xl border border-slate-200 shadow-xs transition-colors"
            title="Back to Notifications"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${isResolved ? 'bg-emerald-500' : 'bg-rose-500 animate-pulse'}`}></span>
              Notification Inspection: {alert.alert_id || alert.id}
            </h2>
            <p className="text-xs text-slate-500 font-mono mt-0.5">
              Triggered: {new Date(alert.triggered_at || alert.start_time || '').toLocaleString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <StatusBadge status={alert.state || alert.status || 'NEW'} />
          <SeverityBadge severity={alert.severity || alert.state || (alert.class_name === 'fire' ? 'CRITICAL' : 'WARNING')} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Snapshot Evidence & SOP Guidelines */}
        <div className="lg:col-span-2 space-y-6">
          {/* Snapshot Evidence Preview */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card space-y-3">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center justify-between">
              <span>Detection Frame Snapshot Evidence</span>
              <span className="text-slate-400 font-normal lowercase text-[11px]">High-Res AI Captured Frame</span>
            </h3>
            <div
              onClick={() => {
                if (alert.snapshot_url) setIsSnapshotExpanded(true);
              }}
              className={`w-full aspect-video bg-slate-950 rounded-xl overflow-hidden flex items-center justify-center border border-slate-800/80 shadow-inner relative group ${
                alert.snapshot_url ? 'cursor-pointer' : ''
              }`}
              title={alert.snapshot_url ? 'Click to inspect full resolution evidence' : undefined}
            >
              {alert.snapshot_url ? (
                <>
                  <img
                    src={resolveApiUrl(alert.snapshot_url)}
                    alt="Alert Snapshot Evidence"
                    className="w-full h-full object-contain group-hover:scale-[1.02] transition-transform duration-200"
                  />
                  <div className="absolute bottom-2 right-2 bg-slate-900/80 backdrop-blur-xs text-white p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity border border-slate-700 pointer-events-none flex items-center gap-1 text-[11px] font-medium">
                    <Maximize2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Expand</span>
                  </div>
                </>
              ) : (
                <div className="text-center text-slate-400 text-xs">
                  <ShieldAlert className="w-10 h-10 text-slate-600 mx-auto mb-2" />
                  No JPEG Evidence Frame Attached to Alert Payload
                </div>
              )}
            </div>
          </div>

          {/* SOP Remediation Action Plan (Standard Operating Procedures) */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                  <ClipboardList className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Standard Operating Procedure (SOP) Remedy Guidelines
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Mandatory response protocol for verified {threatClass.toUpperCase()} threats
                  </p>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 uppercase">
                Action Protocol
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {sopSteps.map((step) => (
                <div key={step.step} className="p-3 bg-slate-50 rounded-xl border border-slate-200/70 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-blue-600 text-white font-bold text-[10px] flex items-center justify-center">
                      {step.step}
                    </span>
                    <h4 className="text-xs font-bold text-slate-800">{step.title}</h4>
                  </div>
                  <p className="text-[11px] text-slate-500 pl-7 leading-relaxed">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Threat Diagnostics & Action Remedy Controls */}
        <div className="space-y-6">
          {/* Threat Metadata */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card space-y-4">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Threat Diagnostics
            </h3>
            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">Classification:</span>
                <span className="font-bold text-slate-900 uppercase flex items-center gap-1.5">
                  {alert.class_name === 'fire' ? (
                    <span className="text-rose-600 flex items-center gap-1">
                      <Flame className="w-4 h-4 text-rose-600" />
                      Fire
                    </span>
                  ) : (
                    <span className="text-amber-600 flex items-center gap-1">
                      <Wind className="w-4 h-4 text-amber-600" />
                      Smoke
                    </span>
                  )}
                </span>
              </div>

              <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">AI Confidence:</span>
                <span className="font-mono text-blue-600 font-bold text-sm">
                  {Math.round((alert.max_confidence || alert.latest_confidence || alert.confidence || 0) * 100)}%
                </span>
              </div>

              <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">Camera Source:</span>
                <span className="text-slate-900 font-semibold">{alert.camera_name || cameraMap[alert.camera_id]?.name || `Camera #${alert.camera_id}`}</span>
              </div>

              <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">Camera Location:</span>
                <span className="text-slate-900 font-semibold flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                  <span>{alert.camera_location || alert.location || cameraMap[alert.camera_id]?.location || 'Unassigned'}</span>
                </span>
              </div>

              <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">Alert Status:</span>
                <span className="font-semibold text-slate-800">{alert.state || alert.status || 'NEW'}</span>
              </div>
            </div>

            {/* Action Controls & Remedy Execution */}
            <PermissionGuard permission="alerts:write">
              <div className="pt-2 space-y-2.5">
                {!isResolved && (
                  <>
                    {(alert.status === 'NEW' || alert.state === 'ALERT_SENT' || alert.state === 'ACTIVE' || alert.state === 'CONFIRMED') && !isRemedyFormOpen && (
                      <button
                        onClick={() => acknowledgeMutation.mutate()}
                        disabled={acknowledgeMutation.isPending}
                        className="w-full py-2.5 bg-amber-50 hover:bg-amber-100 active:bg-amber-200 text-amber-800 font-semibold rounded-xl text-xs border border-amber-200 shadow-xs transition-colors"
                      >
                        {acknowledgeMutation.isPending ? 'Acknowledging...' : 'Acknowledge Threat Event'}
                      </button>
                    )}

                    {!isRemedyFormOpen ? (
                      <button
                        onClick={() => {
                          setIsRemedyFormOpen(true);
                          if (!selectedRemedy) setSelectedRemedy(presets[0]?.id || '');
                        }}
                        className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-semibold rounded-xl text-xs shadow-xs transition-colors flex items-center justify-center gap-1.5"
                      >
                        <Wrench className="w-3.5 h-3.5" />
                        <span>Apply Action Remedy & Resolve</span>
                      </button>
                    ) : (
                      /* Inline Action Remedy Form */
                      <form onSubmit={handleConfirmRemedy} className="p-4 bg-slate-50 rounded-xl border border-emerald-200 shadow-xs space-y-3.5 text-xs animate-fade-in">
                        <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                          <span className="font-bold text-slate-900 flex items-center gap-1.5">
                            <Wrench className="w-3.5 h-3.5 text-emerald-600" /> Log Action Remedy
                          </span>
                          <button
                            type="button"
                            onClick={() => setIsRemedyFormOpen(false)}
                            className="text-slate-400 hover:text-slate-600"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>

                        <div>
                          <label className="block text-slate-700 font-semibold mb-1.5">Remedial Action Taken:</label>
                          <select
                            value={selectedRemedy}
                            onChange={(e) => setSelectedRemedy(e.target.value)}
                            className="w-full bg-white border border-slate-300 rounded-lg p-2 font-medium text-slate-800 text-xs focus:ring-1 focus:ring-emerald-500 focus:outline-none"
                            required
                          >
                            {presets.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.label}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <label className="block text-slate-700 font-semibold mb-1">Operator Remedy Notes (Optional):</label>
                          <textarea
                            rows={2}
                            value={remedyNotes}
                            onChange={(e) => setRemedyNotes(e.target.value)}
                            placeholder="e.g. Officer John deployed CO2 extinguisher. Area secured and ventilated."
                            className="w-full bg-white border border-slate-300 rounded-lg p-2 text-slate-800 text-xs focus:ring-1 focus:ring-emerald-500 focus:outline-none"
                          />
                        </div>

                        <div className="flex gap-2 pt-1">
                          <button
                            type="button"
                            onClick={() => setIsRemedyFormOpen(false)}
                            className="flex-1 py-2 bg-white hover:bg-slate-100 text-slate-700 rounded-lg border border-slate-300 font-semibold"
                          >
                            Cancel
                          </button>
                          <button
                            type="submit"
                            disabled={resolveMutation.isPending}
                            className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold flex items-center justify-center gap-1 shadow-xs"
                          >
                            <Send className="w-3.5 h-3.5" />
                            <span>{resolveMutation.isPending ? 'Resolving...' : 'Confirm & Clear'}</span>
                          </button>
                        </div>
                      </form>
                    )}
                  </>
                )}
              </div>
            </PermissionGuard>
          </div>

          {/* Remediation Audit Record (Visible When Resolved) */}
          {isResolved && (
            <div className="bg-emerald-50/70 p-5 rounded-2xl border border-emerald-200 shadow-card space-y-3.5">
              <div className="flex items-center gap-2 text-emerald-800 font-bold text-xs">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Incident Remediated & Resolved</span>
              </div>

              <div className="space-y-2 text-xs text-slate-700">
                <div className="p-2.5 bg-white rounded-xl border border-emerald-100">
                  <span className="text-slate-400 text-[10px] uppercase font-bold block">Action Taken</span>
                  <p className="font-semibold text-emerald-900 mt-0.5">
                    {alert.remedial_action || 'Incident Verified & Resolved'}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 bg-white rounded-xl border border-emerald-100">
                    <span className="text-slate-400 text-[10px] uppercase font-bold block flex items-center gap-1">
                      <UserCheck className="w-3 h-3 text-slate-400" /> Resolved By
                    </span>
                    <p className="font-mono text-[11px] text-slate-800 font-medium mt-0.5 truncate">
                      {alert.resolved_by || user?.username || 'Security Officer'}
                    </p>
                  </div>

                  <div className="p-2.5 bg-white rounded-xl border border-emerald-100">
                    <span className="text-slate-400 text-[10px] uppercase font-bold block flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-400" /> Cleared At
                    </span>
                    <p className="font-mono text-[11px] text-slate-800 font-medium mt-0.5 truncate">
                      {alert.cleared_time ? new Date(alert.cleared_time).toLocaleTimeString() : 'Recent'}
                    </p>
                  </div>
                </div>

                {alert.remedy_notes && (
                  <div className="p-2.5 bg-white rounded-xl border border-emerald-100">
                    <span className="text-slate-400 text-[10px] uppercase font-bold block flex items-center gap-1">
                      <FileText className="w-3 h-3 text-slate-400" /> Remedy Notes
                    </span>
                    <p className="text-slate-600 text-[11px] mt-0.5 italic">
                      "{alert.remedy_notes}"
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Responsive High-Resolution Evidence Lightbox Modal */}
      {isSnapshotExpanded && alert.snapshot_url && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-xs z-50 flex items-center justify-center p-3 sm:p-5 overflow-y-auto">
          <div className="bg-slate-900 rounded-2xl max-w-4xl w-full border border-slate-700 shadow-2xl overflow-hidden flex flex-col max-h-[92vh] sm:max-h-[88vh] my-auto animate-in fade-in zoom-in-95 duration-150">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800 bg-slate-950/80 shrink-0">
              <div className="flex items-center gap-2.5 text-white">
                <div className="w-7 h-7 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center border border-blue-500/30">
                  <ShieldAlert className="w-3.5 h-3.5" />
                </div>
                <div>
                  <span className="font-bold text-xs sm:text-sm">High-Resolution AI Snapshot Evidence</span>
                  <span className="text-slate-400 text-[11px] font-mono block">
                    Alert ID: {alert.alert_id || alert.id} • {alert.class_name?.toUpperCase()}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsSnapshotExpanded(false)}
                className="text-slate-400 hover:text-white p-1.5 rounded-xl hover:bg-slate-800 transition-colors"
                title="Close viewer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Media Viewport */}
            <div className="flex-1 min-h-0 bg-black flex items-center justify-center p-2 sm:p-4 overflow-hidden">
              <img
                src={resolveApiUrl(alert.snapshot_url)}
                alt="High-Res Evidence Frame"
                className="max-w-full max-h-[68vh] object-contain rounded-xl"
              />
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between shrink-0 text-xs">
              <span className="text-slate-400 font-mono text-[11px]">
                Confidence: {Math.round((alert.max_confidence || alert.latest_confidence || alert.confidence || 0) * 100)}%
              </span>
              <a
                href={resolveApiUrl(alert.snapshot_url)}
                download={`alert_${alert.alert_id || alert.id}_evidence.jpg`}
                target="_blank"
                rel="noreferrer"
                className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <Download className="w-3.5 h-3.5" /> Download Full JPEG
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AlertDetailPage;
