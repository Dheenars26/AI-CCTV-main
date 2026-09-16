import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole } from '../types/api';
import { authApi, LoginPayload } from '../api/auth';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (payload: { email?: string; full_name?: string }) => Promise<void>;
  refreshUser: () => Promise<void>;
  hasRole: (roles: UserRole | UserRole[]) => boolean;
  hasPermission: (permission: string) => boolean;
}

// Role Permissions mapping (matches backend permissions.py)
const ROLE_PERMISSIONS: Record<UserRole, string[]> = {
  ADMIN: ['*'],
  MANAGER: [
    'cameras:read', 'cameras:write', 'cameras:status',
    'dvr:read', 'dvr:create', 'dvr:update', 'dvr:delete', 'dvr:health_read',
    'alerts:read', 'alerts:write',
    'evidence:read', 'evidence:purge',
    'reports:read',
    'system:status', 'system:logs',
    'notifications:read', 'notifications:write'
  ],
  OPERATOR: [
    'cameras:read', 'cameras:write', 'cameras:status',
    'dvr:read', 'dvr:health_read',
    'alerts:read', 'alerts:write',
    'detections:read', 'evidence:read',
    'notifications:read', 'notifications:write'
  ],
  VIEWER: [
    'cameras:read', 'cameras:status',
    'dvr:read',
    'detections:read',
    'system:status',
    'notifications:read'
  ]
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(() => !!localStorage.getItem('access_token'));

  const fetchProfile = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    // Safety timeout: Never let gateway authentication hang longer than 2.5s
    const timeoutId = setTimeout(() => {
      setIsLoading(false);
    }, 2500);

    try {
      const res = await authApi.getMe();
      if (res.success && res.data) {
        const u = res.data;
        setUser({ ...u, role: ((u.role || 'VIEWER') as string).toUpperCase() as UserRole });
      } else {
        setUser(null);
        localStorage.removeItem('access_token');
      }
    } catch {
      setUser(null);
      localStorage.removeItem('access_token');
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      fetchProfile();
    } else {
      setIsLoading(false);
    }

    const handleAuthLogout = () => {
      setUser(null);
      localStorage.removeItem('access_token');
      setIsLoading(false);
    };

    window.addEventListener('auth_logout', handleAuthLogout);
    return () => window.removeEventListener('auth_logout', handleAuthLogout);
  }, []);

  const login = async (payload: LoginPayload) => {
    try {
      const res = await authApi.login(payload);
      if (res.success && res.data) {
        localStorage.setItem('access_token', res.data.access_token);
        const u = res.data.user;
        setUser({ ...u, role: ((u.role || 'VIEWER') as string).toUpperCase() as UserRole });
        setIsLoading(false);
      } else {
        throw new Error('Authentication response payload invalid.');
      }
    } catch (err) {
      setUser(null);
      localStorage.removeItem('access_token');
      setIsLoading(false);
      throw err;
    }
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore network failure on logout
    } finally {
      setUser(null);
      localStorage.removeItem('access_token');
    }
  };

  const updateProfile = async (payload: { email?: string; full_name?: string }) => {
    const res = await authApi.updateMe(payload);
    if (res.success && res.data) {
      const u = res.data;
      setUser({ ...u, role: ((u.role || 'VIEWER') as string).toUpperCase() as UserRole });
    }
  };

  const hasRole = (roles: UserRole | UserRole[]): boolean => {
    if (!user) return false;
    const roleList = Array.isArray(roles) ? roles : [roles];
    return roleList.includes(user.role);
  };

  const hasPermission = (permission: string): boolean => {
    if (!user) return false;
    const perms = ROLE_PERMISSIONS[user.role] || [];
    if (perms.includes('*')) return true;
    return perms.includes(permission);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        updateProfile,
        refreshUser: fetchProfile,
        hasRole,
        hasPermission
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
