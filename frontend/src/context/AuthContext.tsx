import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, Tenant, Role, TenantMembership } from '../types';
import { getMe, login as apiLogin, register as apiRegister, logout as apiLogout } from '../api/auth';
import { setAuthToken, setActiveTenantHeader, setOnAuthFailed } from '../api/client';

interface AuthContextType {
  user: User | null;
  activeTenant: Tenant | null;
  role: Role | null;
  memberships: TenantMembership[];
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, tenantId?: number) => Promise<void>;
  register: (email: string, password: string, fullName: string, tenantName?: string) => Promise<void>;
  logout: () => Promise<void>;
  switchTenant: (tenantId: number) => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [activeTenant, setActiveTenant] = useState<Tenant | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [memberships, setMemberships] = useState<TenantMembership[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshProfile = useCallback(async () => {
    try {
      const profile = await getMe();
      setUser(profile.user);
      setActiveTenant(profile.active_tenant);
      setRole(profile.role);
      setMemberships(profile.memberships);
      setActiveTenantHeader(profile.active_tenant.id);
    } catch {
      setUser(null);
      setActiveTenant(null);
      setRole(null);
      setMemberships([]);
      setAuthToken(null);
      setActiveTenantHeader(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    setOnAuthFailed(() => {
      setUser(null);
      setActiveTenant(null);
      setRole(null);
      setMemberships([]);
      setAuthToken(null);
      setActiveTenantHeader(null);
    });

    // Check if session can be restored
    refreshProfile();
  }, [refreshProfile]);

  const login = async (email: string, password: string, tenantId?: number) => {
    setIsLoading(true);
    try {
      const res = await apiLogin({ email, password, tenant_id: tenantId });
      setUser(res.user);
      setActiveTenant(res.active_tenant);
      setRole(res.role);
      setActiveTenantHeader(res.active_tenant.id);
      await refreshProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, password: string, fullName: string, tenantName?: string) => {
    setIsLoading(true);
    try {
      const res = await apiRegister({
        email,
        password,
        full_name: fullName,
        tenant_name: tenantName,
      });
      setUser(res.user);
      setActiveTenant(res.active_tenant);
      setRole(res.role);
      setActiveTenantHeader(res.active_tenant.id);
      await refreshProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await apiLogout();
      setUser(null);
      setActiveTenant(null);
      setRole(null);
      setMemberships([]);
      setAuthToken(null);
      setActiveTenantHeader(null);
    } finally {
      setIsLoading(false);
    }
  };

  const switchTenant = async (tenantId: number) => {
    setActiveTenantHeader(tenantId);
    await refreshProfile();
  };

  const value: AuthContextType = {
    user,
    activeTenant,
    role,
    memberships,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
    switchTenant,
    refreshProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
