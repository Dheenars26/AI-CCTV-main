import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Video, Camera, Shield, AlertTriangle, Eye, Bell, Activity, Settings, X } from 'lucide-react';

const navigation = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Live Monitoring', path: '/monitoring', icon: Video },
  { name: 'Camera List', path: '/cameras', icon: Camera },
  { name: 'Notifications', path: '/notifications', icon: Bell },
  { name: 'Detection History', path: '/detections', icon: Eye },
  { name: 'Safety Zones', path: '/zones', icon: Shield },
  { name: 'System Status', path: '/system', icon: Activity },
  { name: 'Settings', path: '/settings', icon: Settings },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen = false, onClose }) => {
  const navContent = (
    <div className="flex flex-col justify-between h-full space-y-4">
      <nav className="space-y-1">
        {navigation.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => onClose?.()}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-medium tracking-wide transition-all ${
                  isActive
                    ? 'bg-blue-50/90 text-blue-700 font-semibold border border-blue-200/80 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`w-4 h-4 transition-colors ${isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
                  <span>{item.name}</span>
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Connection & Telemetry Footer */}
      <div className="bg-slate-50 p-3 rounded-xl text-[11px] text-slate-500 space-y-1 border border-slate-200/70">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-semibold text-slate-700">API Server Online</span>
        </div>
        <p className="font-mono text-[10px] text-slate-400 pl-4">127.0.0.1:8000</p>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden lg:flex w-64 bg-white border-r border-slate-200/80 p-3.5 flex-col justify-between min-h-[calc(100vh-4rem)] sticky top-16 shadow-[1px_0_4px_rgba(0,0,0,0.02)] shrink-0">
        {navContent}
      </aside>

      {/* Mobile Drawer Overlay & Sidebar */}
      {isOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity duration-200"
            onClick={onClose}
          />
          <aside className="fixed inset-y-0 left-0 w-72 max-w-[82vw] bg-white p-4 flex flex-col justify-between shadow-2xl z-50 animate-in slide-in-from-left duration-200">
            <div className="flex items-center justify-between pb-3 mb-2 border-b border-slate-200/80">
              <span className="font-bold text-sm text-slate-800 tracking-tight">Navigation Menu</span>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
                aria-label="Close menu"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {navContent}
            </div>
          </aside>
        </div>
      )}
    </>
  );
};
