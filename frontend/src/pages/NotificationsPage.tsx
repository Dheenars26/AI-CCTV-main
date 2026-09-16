import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '../api/notifications';
import {
  Bell,
  Mail,
  Edit3,
  Save,
  X,
  CheckCircle,
  ShieldAlert,
  Send,
  AlertCircle,
  Sparkles
} from 'lucide-react';

export const NotificationsPage: React.FC = () => {
  const queryClient = useQueryClient();

  // State
  const [isEditingEmail, setIsEditingEmail] = useState<boolean>(false);
  const [emailsInput, setEmailsInput] = useState<string>('');
  const [appPasswordInput, setAppPasswordInput] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Fetch notification settings
  const { data: settingsRes, isLoading } = useQuery({
    queryKey: ['notification-settings'],
    queryFn: () => notificationsApi.getSettings(),
  });

  const settings = settingsRes?.data;

  // Synchronize local input state with server data
  useEffect(() => {
    if (settings?.recipient_emails) {
      setEmailsInput(settings.recipient_emails.join(', '));
    }
  }, [settings]);

  // Mutation to update notification settings
  const updateMutation = useMutation({
    mutationFn: (payload: { recipient_emails?: string[]; email_alerts_enabled?: boolean; smtp_password?: string }) => {
      const recipient_emails = payload.recipient_emails !== undefined
        ? payload.recipient_emails
        : settings?.recipient_emails || [];
      const email_alerts_enabled = payload.email_alerts_enabled !== undefined
        ? payload.email_alerts_enabled
        : settings?.email_alerts_enabled ?? true;

      return notificationsApi.updateSettings({
        recipient_emails,
        email_alerts_enabled,
        cooldown_seconds: settings?.cooldown_seconds ?? 60,
        smtp_password: payload.smtp_password,
      });
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['notification-settings'] });
      setIsEditingEmail(false);
      setErrorMessage(null);

      if (variables.smtp_password) {
        setSuccessMessage('Recipient email and App Password updated successfully!');
        setAppPasswordInput('');
      } else if (variables.recipient_emails !== undefined) {
        setSuccessMessage('Recipient email address updated successfully!');
      } else if (variables.email_alerts_enabled !== undefined) {
        setSuccessMessage(
          variables.email_alerts_enabled
            ? 'Automatic email alerts on detection ENABLED.'
            : 'Automatic email alerts on detection DISABLED.'
        );
      } else {
        setSuccessMessage('Notification settings saved successfully!');
      }

      setTimeout(() => setSuccessMessage(null), 5000);
    },
    onError: (err: any) => {
      const msg = err.response?.data?.error?.message || err.message || 'Failed to save settings.';
      setErrorMessage(msg);
      setTimeout(() => setErrorMessage(null), 6000);
    }
  });

  // Test email mutation
  const testEmailMutation = useMutation({
    mutationFn: () => notificationsApi.sendTestEmail(),
    onSuccess: (res) => {
      const recipient = res.data?.recipient || 'configured email';
      setErrorMessage(null);
      setSuccessMessage(`Test alert email sent successfully to ${recipient}!`);
      setTimeout(() => setSuccessMessage(null), 6000);
    },
    onError: (err: any) => {
      const msg = err.response?.data?.error?.message || err.message || 'Failed to send test email.';
      setErrorMessage(msg);
      setTimeout(() => setErrorMessage(null), 7000);
    }
  });

  // Handle Save Recipient Emails
  const handleSaveEmail = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanList = emailsInput
      .split(',')
      .map((em) => em.trim())
      .filter((em) => em.length > 0);

    if (cleanList.length === 0) {
      setErrorMessage('Please enter at least one recipient email address.');
      setTimeout(() => setErrorMessage(null), 4000);
      return;
    }

    updateMutation.mutate({
      recipient_emails: cleanList,
      smtp_password: appPasswordInput.trim() || undefined,
    });
  };

  // Toggle automatic email alerts on detection
  const handleToggleDetectionAlerts = () => {
    const nextState = !settings?.email_alerts_enabled;
    updateMutation.mutate({ email_alerts_enabled: nextState });
  };

  const isAlertsActive = settings?.email_alerts_enabled ?? true;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card flex items-center justify-between">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center border border-blue-100 shadow-xs">
            <Bell className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Email Notifications
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Configure recipient email and manage automatic email alerts when detections occur.
            </p>
          </div>
        </div>

        {/* Global Status Pill */}
        <div className="flex items-center gap-2">
          <span
            className={`px-3 py-1.5 text-xs font-semibold rounded-full border flex items-center gap-1.5 transition-all shadow-xs ${
              isAlertsActive
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-rose-50 text-rose-700 border-rose-200'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isAlertsActive ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
              }`}
            />
            {isAlertsActive ? 'DETECTION ALERTS ACTIVE' : 'ALERTS DISABLED'}
          </span>
        </div>
      </div>

      {/* Global Success / Error Banners */}
      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs flex items-center gap-2.5 animate-fade-in shadow-xs font-medium">
          <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs flex items-center gap-2.5 animate-fade-in shadow-xs font-medium">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Notification Card */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-card space-y-6">
        {/* Section 1: Recipient Email Edit */}
        <div>
          <div className="flex items-center justify-between pb-3.5 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Mail className="w-4 h-4 text-blue-600" />
              <h3 className="font-bold text-sm text-slate-800">Alert Recipient Email</h3>
            </div>

            {!isEditingEmail && (
              <button
                type="button"
                onClick={() => setIsEditingEmail(true)}
                className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-xl border border-slate-200 shadow-xs transition-colors flex items-center gap-1.5 text-xs font-medium"
              >
                <Edit3 className="w-3.5 h-3.5 text-blue-600" /> Edit Email
              </button>
            )}
          </div>

          {isLoading ? (
            <div className="p-6 text-xs text-slate-400 text-center animate-pulse">
              Loading notification settings...
            </div>
          ) : isEditingEmail ? (
            <form onSubmit={handleSaveEmail} className="space-y-4 pt-4 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1.5">
                  Recipient Email Address
                </label>
                <input
                  type="text"
                  value={emailsInput}
                  onChange={(e) => setEmailsInput(e.target.value)}
                  placeholder="e.g. security@company.com, admin@company.com"
                  required
                  autoFocus
                  className="w-full bg-white border border-slate-300 rounded-xl p-3 text-slate-900 font-mono focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none text-sm transition-all shadow-xs"
                />
                <p className="text-[11px] text-slate-500 mt-1.5">
                  Enter the email address where alerts should be delivered. Separate multiple addresses with commas.
                </p>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1.5 flex items-center justify-between">
                  <span>Google App Password (16 Characters)</span>
                  <span className="text-slate-400 font-normal">Optional</span>
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={appPasswordInput}
                    onChange={(e) => setAppPasswordInput(e.target.value)}
                    placeholder="Enter 16-char App Password (e.g. abcd efgh ijkl mnop)"
                    className="w-full bg-white border border-slate-300 rounded-xl p-3 pr-16 text-slate-900 font-mono focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none text-sm tracking-wider transition-all shadow-xs"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-800 text-xs px-2 py-1 font-semibold"
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
                <p className="text-[11px] text-slate-500 mt-1.5 flex items-center gap-1">
                  <span>Generate at:</span>
                  <a
                    href="https://myaccount.google.com/apppasswords"
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 hover:underline font-mono font-medium"
                  >
                    myaccount.google.com/apppasswords
                  </a>
                </p>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsEditingEmail(false);
                    if (settings?.recipient_emails) {
                      setEmailsInput(settings.recipient_emails.join(', '));
                    }
                  }}
                  className="px-4 py-2 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-xl border border-slate-200 transition-colors flex items-center gap-1.5 text-xs font-medium shadow-xs"
                >
                  <X className="w-3.5 h-3.5" /> Cancel
                </button>

                <button
                  type="submit"
                  disabled={updateMutation.isPending}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl shadow-xs transition-all flex items-center gap-1.5 text-xs disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          ) : (
            <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
              <div>
                <span className="text-slate-500 uppercase tracking-wider text-[10px] block font-bold">
                  Configured Email Address
                </span>
                <p className="text-blue-600 font-mono font-bold text-sm mt-1">
                  {settings?.recipient_emails && settings.recipient_emails.length > 0
                    ? settings.recipient_emails.join(', ')
                    : 'No email configured'}
                </p>
              </div>

              <span className="text-xs text-slate-600 font-mono bg-white px-3 py-1 rounded-lg border border-slate-200 shadow-xs">
                {settings?.recipient_emails?.length || 0} recipient{settings?.recipient_emails?.length === 1 ? '' : 's'}
              </span>
            </div>
          )}
        </div>

        {/* Section 2: Send Email on Detection Trigger */}
        <div className="pt-2">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-emerald-600" />
                <h4 className="font-bold text-sm text-slate-900">
                  Send Email When Alert Detected
                </h4>
              </div>
              <p className="text-xs text-slate-500 max-w-xl leading-relaxed">
                Automatically dispatches an email notification with attached evidence snapshot whenever{' '}
                <span className="text-slate-800 font-semibold">Fire, Smoke, Missing Safety Vest, or Missing Safety Glasses</span> are detected by AI surveillance.
              </p>
            </div>

            <div className="flex items-center gap-3 self-end sm:self-center flex-shrink-0">
              <button
                type="button"
                onClick={handleToggleDetectionAlerts}
                disabled={updateMutation.isPending}
                className={`px-4 py-2 rounded-xl text-xs font-semibold border transition-all flex items-center gap-2 shadow-xs ${
                  isAlertsActive
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                    : 'bg-slate-100 text-slate-600 border-slate-300 hover:bg-slate-200'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    isAlertsActive ? 'bg-emerald-500' : 'bg-slate-400'
                  }`}
                />
                {isAlertsActive ? 'SEND ON DETECTION: ACTIVE' : 'SEND ON DETECTION: PAUSED'}
              </button>
            </div>
          </div>
        </div>

        {/* Section 3: Test Email Action */}
        <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
          <div className="text-xs text-slate-500 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
            <span>Verify your email inbox by sending a test alert.</span>
          </div>

          <button
            type="button"
            onClick={() => testEmailMutation.mutate()}
            disabled={testEmailMutation.isPending}
            className="px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 font-semibold rounded-xl text-xs flex items-center gap-2 transition-all shadow-xs disabled:opacity-50"
          >
            <Send className={`w-3.5 h-3.5 ${testEmailMutation.isPending ? 'animate-spin' : ''}`} />
            {testEmailMutation.isPending ? 'Sending Test Email...' : 'Send Test Email'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default NotificationsPage;
