import React from 'react';
import { useAuth } from '../context/AuthContext';
import { ShieldAlert } from 'lucide-react';

interface PermissionGuardProps {
  permission?: string;
  roles?: ("ADMIN" | "MANAGER" | "OPERATOR" | "VIEWER")[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const PermissionGuard: React.FC<PermissionGuardProps> = ({
  permission,
  roles,
  children,
  fallback,
}) => {
  const { hasPermission, hasRole } = useAuth();

  const isPermitted = permission ? hasPermission(permission) : true;
  const isRoleValid = roles ? hasRole(roles) : true;

  if (isPermitted && isRoleValid) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  return (
    <div className="bg-white p-8 rounded-2xl border border-rose-200 text-center space-y-4 max-w-lg mx-auto my-12 shadow-card">
      <div className="w-14 h-14 bg-rose-50 text-rose-600 rounded-2xl flex items-center justify-center mx-auto border border-rose-100 shadow-xs">
        <ShieldAlert className="w-7 h-7" />
      </div>
      <h3 className="text-lg font-bold text-slate-900">Access Restricted</h3>
      <p className="text-xs text-slate-500 leading-relaxed max-w-md mx-auto">
        Your user role does not have permission to view or execute actions on this resource.
      </p>
      <span className="inline-block px-3 py-1 bg-slate-50 text-slate-600 rounded-full text-xs font-mono border border-slate-200">
        Required Permission: {permission || roles?.join(', ')}
      </span>
    </div>
  );
};

export default PermissionGuard;
