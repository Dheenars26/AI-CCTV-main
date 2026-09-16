import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '../api/notifications';
import { systemApi } from '../api/system';
import { VerificationSettings } from '../types/api';
import { Settings, Shield, User as UserIcon, ExternalLink, Mail, Edit3, Save, CheckCircle, X, ShieldCheck, Sliders, Flame, Wind, Clock, Info, RotateCcw } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { user, updateProfile } = useAuth();
  const queryClient = useQueryClient();

  const [isEditingEmail, setIsEditingEmail] = useState<boolean>(false);
  const [emailInput, setEmailInput] = useState<string>('');
  const [isEditingAccountEmail, setIsEditingAccountEmail] = useState<boolean>(false);
  const [accountEmailInput, setAccountEmailInput] = useState<string>('');
  const [isSavingAccountEmail, setIsSavingAccountEmail] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: notifSettingsRes, isLoading: isNotifLoading } = useQuery({
    queryKey: ['notification-settings'],
    queryFn: () => notificationsApi.getSettings(),
  });

  const { data: verifSettingsRes, isLoading: isVerifLoading } = useQuery({
    queryKey: ['verification-settings'],
    queryFn: () => systemApi.getVerificationSettings(),
  });

  const notifSettings = notifSettingsRes?.data;
  const verifSettings = verifSettingsRes?.data;

  const [verifForm, setVerifForm] = useState<VerificationSettings>({
    fire_min_confidence: 0.35,
    fire_min_consecutive_frames: 3,
    fire_min_duration_seconds: 0.5,
    smoke_min_confidence: 0.30,
    smoke_min_consecutive_frames: 4,
    smoke_min_duration_seconds: 0.8,
    ppe_verification_frames: 3,
    ppe_verification_duration_seconds: 1.0,
    verification_cooldown_seconds: 30.0,
  });

  useEffect(() => {
    if (verifSettings) {
      setVerifForm(verifSettings);
    }
  }, [verifSettings]);

  const verifMutation = useMutation({
    mutationFn: (payload: Partial<VerificationSettings>) => systemApi.updateVerificationSettings(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['verification-settings'] });
      setSuccessMsg('AI detection verification thresholds updated successfully!');
      setTimeout(() => setSuccessMsg(null), 4000);
    },
    onError: (err: any) => {
      const msg = err.response?.data?.error?.message || err.message || 'Failed to update verification settings.';
      setErrorMsg(msg);
      setTimeout(() => setErrorMsg(null), 6000);
    }
  });

  const handleSaveVerification = (e: React.FormEvent) => {
    e.preventDefault();
    verifMutation.mutate(verifForm);
  };

  const handleResetVerification = () => {
    setVerifForm({
      fire_min_confidence: 0.35,
      fire_min_consecutive_frames: 3,
      fire_min_duration_seconds: 0.5,
      smoke_min_confidence: 0.30,
      smoke_min_consecutive_frames: 4,
      smoke_min_duration_seconds: 0.8,
      ppe_verification_frames: 3,
      ppe_verification_duration_seconds: 1.0,
      verification_cooldown_seconds: 30.0,
    });
  };

  useEffect(() => {
    if (notifSettings?.recipient_emails) {
      setEmailInput(notifSettings.recipient_emails.join(', '));
    }
  }, [notifSettings]);

  useEffect(() => {
    if (user?.email) {
      setAccountEmailInput(user.email);
    }
  }, [user]);

  const emailMutation = useMutation({
    mutationFn: (emails: string[]) =>
      notificationsApi.updateSettings({
        recipient_emails: emails,
        email_alerts_enabled: notifSettings?.email_alerts_enabled ?? true,
        cooldown_seconds: notifSettings?.cooldown_seconds ?? 60,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-settings'] });
      setIsEditingEmail(false);
      setErrorMsg(null);
      setSuccessMsg('Alert recipient email address updated successfully!');
      setTimeout(() => setSuccessMsg(null), 4000);
    },
    onError: (err: any) => {
      const msg = err.response?.data?.error?.message || err.message || 'Failed to update alert recipient email.';
      setErrorMsg(msg);
      setTimeout(() => setErrorMsg(null), 6000);
    }
  });

  const handleSaveEmail = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanList = emailInput
      .split(',')
      .map((em) => em.trim())
      .filter((em) => em.length > 0);
    if (cleanList.length === 0) {
      setErrorMsg('Please enter at least one valid recipient email address.');
      setTimeout(() => setErrorMsg(null), 4000);
      return;
    }
    emailMutation.mutate(cleanList);
  };

  const handleSaveAccountEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = accountEmailInput.trim();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setErrorMsg('Please enter a valid email address.');
      setTimeout(() => setErrorMsg(null), 4000);
      return;
    }
    setIsSavingAccountEmail(true);
    try {
      await updateProfile({ email: cleanEmail });
      setIsEditingAccountEmail(false);
      setErrorMsg(null);
      setSuccessMsg('Account email updated successfully!');
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.message || 'Failed to update account email.';
      setErrorMsg(msg);
      setTimeout(() => setErrorMsg(null), 6000);
    } finally {
      setIsSavingAccountEmail(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card flex items-center justify-between">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 shadow-xs">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Platform Configuration & Account Settings
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Manage user credentials, role permissions, and alert email notification configuration.
            </p>
          </div>
        </div>
      </div>

      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs flex items-center gap-2.5 font-medium shadow-xs animate-fade-in">
          <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs flex items-center gap-2.5 font-medium shadow-xs animate-fade-in">
          <X className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* User Account Details */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-card space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 font-bold text-base shadow-xs">
                {user?.username ? user.username.charAt(0).toUpperCase() : <UserIcon className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-900">{user?.full_name || user?.username}</h3>
                <p className="text-xs text-slate-500 font-mono">Role: {user?.role}</p>
              </div>
            </div>

            {!isEditingAccountEmail && (
              <button
                onClick={() => setIsEditingAccountEmail(true)}
                className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold rounded-xl border border-slate-200 shadow-xs transition-colors flex items-center gap-1.5"
              >
                <Edit3 className="w-3.5 h-3.5 text-blue-600" /> Edit Email
              </button>
            )}
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
              <span className="text-slate-500 font-medium">Username:</span>
              <span className="font-mono text-slate-900 font-semibold">{user?.username}</span>
            </div>

            {isEditingAccountEmail ? (
              <form onSubmit={handleSaveAccountEmail} className="p-3.5 bg-slate-50 rounded-xl space-y-3 border border-blue-200 shadow-xs">
                <label className="block text-slate-700 font-semibold">Account Email Address:</label>
                <input
                  type="email"
                  value={accountEmailInput}
                  onChange={(e) => setAccountEmailInput(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-xl p-2.5 text-slate-900 font-mono focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none shadow-xs text-xs"
                  required
                />
                <div className="flex justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setIsEditingAccountEmail(false)}
                    className="px-3 py-1.5 bg-white hover:bg-slate-100 text-slate-700 rounded-xl text-xs border border-slate-200 shadow-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSavingAccountEmail}
                    className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl text-xs shadow-xs flex items-center gap-1"
                  >
                    <Save className="w-3 h-3" /> {isSavingAccountEmail ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">Account Email:</span>
                <span className="font-mono text-slate-900 font-semibold">{user?.email || 'None'}</span>
              </div>
            )}

            <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-100">
              <span className="text-slate-500 font-medium">Password Encryption:</span>
              <span className="font-mono text-emerald-600 font-semibold flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" /> Argon2id Key Derivation
              </span>
            </div>
          </div>
        </div>

        {/* Alert Notification Recipient Email Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-card space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center border border-blue-100 shadow-xs">
                <Mail className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-900">Fire & Smoke Alert Target</h3>
                <p className="text-xs text-slate-500">Destination address for incident dispatches</p>
              </div>
            </div>

            {!isEditingEmail && (
              <button
                onClick={() => setIsEditingEmail(true)}
                className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold rounded-xl border border-slate-200 shadow-xs transition-colors flex items-center gap-1.5"
              >
                <Edit3 className="w-3.5 h-3.5 text-blue-600" /> Edit Email
              </button>
            )}
          </div>

          {isNotifLoading ? (
            <div className="p-6 text-xs text-slate-400 text-center animate-pulse">Loading email settings...</div>
          ) : isEditingEmail ? (
            <form onSubmit={handleSaveEmail} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Alert Recipient Email Address(es)</label>
                <input
                  type="text"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  placeholder="e.g. admin@domain.com, security@domain.com"
                  className="w-full bg-white border border-slate-300 rounded-xl p-2.5 text-slate-900 font-mono focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none shadow-xs"
                />
                <p className="text-[11px] text-slate-500 mt-1">Separate multiple emails with commas.</p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setIsEditingEmail(false)}
                  className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-xl border border-slate-200 transition-colors flex items-center gap-1 text-xs shadow-xs font-medium"
                >
                  <X className="w-3.5 h-3.5" /> Cancel
                </button>
                <button
                  type="submit"
                  disabled={emailMutation.isPending}
                  className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl shadow-xs transition-all flex items-center gap-1.5 text-xs"
                >
                  <Save className="w-3.5 h-3.5" /> {emailMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          ) : (
            <div className="space-y-3 text-xs bg-slate-50 p-4 rounded-xl font-mono text-slate-700 border border-slate-200/80">
              <div>
                <span className="text-slate-500 uppercase tracking-wider text-[10px] block font-sans font-bold">Active Target Email</span>
                <p className="text-blue-600 font-bold text-sm mt-1 truncate" title={notifSettings?.recipient_emails?.join(', ')}>
                  {notifSettings?.recipient_emails?.join(', ') || 'No recipient configured'}
                </p>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-slate-200 text-[11px]">
                <span className="text-slate-500">Email Alerts Status:</span>
                <span className={`font-semibold ${notifSettings?.email_alerts_enabled ? 'text-emerald-600' : 'text-rose-600'}`}>
                  {notifSettings?.email_alerts_enabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
              <div className="pt-2 border-t border-slate-200 flex justify-end">
                <a
                  href="/notifications"
                  className="text-blue-600 hover:text-blue-700 font-sans text-xs flex items-center gap-1 font-semibold"
                >
                  Configure SMTP Credentials & Test Connection →
                </a>
              </div>
            </div>
          )}
        </div>

        {/* AI Detection Verification & False-Alarm Reduction Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-card space-y-5 md:col-span-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center border border-indigo-100 shadow-xs">
                <Sliders className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                  AI Temporal Verification & False-Alarm Reduction
                  <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 text-[10px] font-bold rounded-full border border-indigo-200 uppercase">
                    Post-Detection Filter
                  </span>
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Set verification thresholds required after raw detection before escalating to a confirmed security incident.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleResetVerification}
                className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-600 text-xs font-semibold rounded-xl border border-slate-200 shadow-xs transition-colors flex items-center gap-1.5"
                title="Reset to recommended defaults"
              >
                <RotateCcw className="w-3.5 h-3.5 text-slate-500" /> Defaults
              </button>
              <button
                type="button"
                onClick={handleSaveVerification}
                disabled={verifMutation.isPending || isVerifLoading}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-xs font-semibold rounded-xl shadow-xs transition-colors flex items-center gap-1.5"
              >
                <Save className="w-3.5 h-3.5" /> {verifMutation.isPending ? 'Saving...' : 'Save Rules'}
              </button>
            </div>
          </div>

          {/* Explanation Banner */}
          <div className="p-3.5 bg-blue-50/70 border border-blue-200/80 rounded-xl text-blue-900 text-xs flex items-start gap-2.5">
            <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              <strong>How Verification Works:</strong> Raw YOLO predictions in video streams can produce transient single-frame spikes from camera glare or dust. The temporal verification state machine tags initial detections as <em>POSSIBLE</em>. An incident alert is only confirmed and dispatched when the threat continuously persists across the configured consecutive frames and minimum duration.
            </p>
          </div>

          <form onSubmit={handleSaveVerification} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Fire Verification Box */}
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 space-y-4">
                <div className="flex items-center gap-2 text-rose-600 font-bold text-xs">
                  <Flame className="w-4 h-4" />
                  <span>Fire Verification</span>
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="text-slate-600 font-medium">Min AI Confidence:</label>
                      <span className="font-mono font-bold text-slate-900">
                        {Math.round(verifForm.fire_min_confidence * 100)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0.10"
                      max="0.80"
                      step="0.05"
                      value={verifForm.fire_min_confidence}
                      onChange={(e) => setVerifForm({ ...verifForm, fire_min_confidence: parseFloat(e.target.value) })}
                      className="w-full accent-rose-600 cursor-pointer"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Consecutive Frames:</label>
                    <input
                      type="number"
                      min="1"
                      max="15"
                      value={verifForm.fire_min_consecutive_frames}
                      onChange={(e) => setVerifForm({ ...verifForm, fire_min_consecutive_frames: parseInt(e.target.value) || 1 })}
                      className="w-full bg-white border border-slate-300 rounded-lg p-2 font-mono text-slate-800 text-xs focus:ring-1 focus:ring-rose-500 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-400 mt-0.5">Consecutive frames required (e.g. 3)</p>
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Min Duration (seconds):</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.1"
                      max="5.0"
                      value={verifForm.fire_min_duration_seconds}
                      onChange={(e) => setVerifForm({ ...verifForm, fire_min_duration_seconds: parseFloat(e.target.value) || 0.1 })}
                      className="w-full bg-white border border-slate-300 rounded-lg p-2 font-mono text-slate-800 text-xs focus:ring-1 focus:ring-rose-500 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-400 mt-0.5">Persistence time (e.g. 0.5s)</p>
                  </div>
                </div>
              </div>

              {/* Smoke Verification Box */}
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 space-y-4">
                <div className="flex items-center gap-2 text-amber-600 font-bold text-xs">
                  <Wind className="w-4 h-4" />
                  <span>Smoke Verification</span>
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="text-slate-600 font-medium">Min AI Confidence:</label>
                      <span className="font-mono font-bold text-slate-900">
                        {Math.round(verifForm.smoke_min_confidence * 100)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0.10"
                      max="0.80"
                      step="0.05"
                      value={verifForm.smoke_min_confidence}
                      onChange={(e) => setVerifForm({ ...verifForm, smoke_min_confidence: parseFloat(e.target.value) })}
                      className="w-full accent-amber-600 cursor-pointer"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Consecutive Frames:</label>
                    <input
                      type="number"
                      min="1"
                      max="15"
                      value={verifForm.smoke_min_consecutive_frames}
                      onChange={(e) => setVerifForm({ ...verifForm, smoke_min_consecutive_frames: parseInt(e.target.value) || 1 })}
                      className="w-full bg-white border border-slate-300 rounded-lg p-2 font-mono text-slate-800 text-xs focus:ring-1 focus:ring-amber-500 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-400 mt-0.5">Consecutive frames required (e.g. 4)</p>
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Min Duration (seconds):</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.1"
                      max="5.0"
                      value={verifForm.smoke_min_duration_seconds}
                      onChange={(e) => setVerifForm({ ...verifForm, smoke_min_duration_seconds: parseFloat(e.target.value) || 0.1 })}
                      className="w-full bg-white border border-slate-300 rounded-lg p-2 font-mono text-slate-800 text-xs focus:ring-1 focus:ring-amber-500 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-400 mt-0.5">Persistence time (e.g. 0.8s)</p>
                  </div>
                </div>
              </div>

              {/* PPE & Alert Suppression Box */}
              <div className="p-4 bg-slate-50/70 rounded-xl border border-slate-200 space-y-4">
                <div className="flex items-center gap-2 text-indigo-600 font-bold text-xs">
                  <Clock className="w-4 h-4" />
                  <span>PPE Safety & Cooldown</span>
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <label className="block text-slate-600 font-medium mb-1">PPE Violation Frames:</label>
                    <input
                      type="number"
                      min="1"
                      max="15"
                      value={verifForm.ppe_verification_frames}
                      onChange={(e) => setVerifForm({ ...verifForm, ppe_verification_frames: parseInt(e.target.value) || 1 })}
                      className="w-full bg-white border border-slate-300 rounded-lg p-2 font-mono text-slate-800 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-400 mt-0.5">Violation frames required (e.g. 3)</p>
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">PPE Violation Duration (s):</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.1"
                      max="5.0"
                      value={verifForm.ppe_verification_duration_seconds}
                      onChange={(e) => setVerifForm({ ...verifForm, ppe_verification_duration_seconds: parseFloat(e.target.value) || 0.1 })}
                      className="w-full bg-white border border-slate-300 rounded-lg p-2 font-mono text-slate-800 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-400 mt-0.5">Violation persistence (e.g. 1.0s)</p>
                  </div>

                  <div>
                    <label className="block text-slate-600 font-medium mb-1">Alert Cooldown (seconds):</label>
                    <input
                      type="number"
                      step="1"
                      min="5"
                      max="180"
                      value={verifForm.verification_cooldown_seconds}
                      onChange={(e) => setVerifForm({ ...verifForm, verification_cooldown_seconds: parseFloat(e.target.value) || 30.0 })}
                      className="w-full bg-white border border-slate-300 rounded-lg p-2 font-mono text-slate-800 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-400 mt-0.5">Suppresses duplicate alerts (e.g. 30s)</p>
                  </div>
                </div>
              </div>
            </div>
          </form>
        </div>

        {/* API Documentation & Decoupled Architecture Integration */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-card space-y-3.5 md:col-span-2">
          <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
            <Shield className="w-4 h-4 text-blue-600" /> Decoupled Headless API Specification
          </h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            This React dashboard is 100% decoupled from the backend. The FastAPI server exposes an open REST + WebSocket contract usable by any client.
          </p>

          <div className="pt-1">
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 text-blue-600 font-semibold text-xs rounded-xl border border-slate-200 shadow-xs transition-colors"
            >
              <ExternalLink className="w-4 h-4" /> Open Swagger OpenAPI Docs (/docs)
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
