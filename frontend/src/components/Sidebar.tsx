import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Video, Camera, Shield, AlertTriangle, Eye, Bell, Activity, Settings } from 'lucide-react';

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



export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-white border-r border-slate-200/80 p-3.5 flex flex-col justify-between min-h-[calc(100vh-4rem)] sticky top-16 shadow-[1px_0_4px_rgba(0,0,0,0.02)]">
      <nav className="space-y-1">
        {navigation.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
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
    </aside>
  );
};
