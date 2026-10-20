import { createContext, useCallback, useContext, useEffect, useMemo, useState, ReactNode } from 'react';
import { apiGet, apiPost, tokenStore } from '../services/api';
import type { TokenResponse, UserBrief } from '../types';

interface AuthContextValue {
  user: UserBrief | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<UserBrief>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserBrief | null>(() => {
    const raw = localStorage.getItem('mpis_user');
    return raw ? (JSON.parse(raw) as UserBrief) : null;
  });
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    if (!tokenStore.access) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await apiGet<UserBrief>('/auth/me');
      setUser(me);
      localStorage.setItem('mpis_user', JSON.stringify(me));
    } catch {
      setUser(null);
      tokenStore.clear();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiPost<TokenResponse>('/auth/login', { email, password });
    tokenStore.set({ access_token: res.access_token, refresh_token: res.refresh_token });
    setUser(res.user);
    localStorage.setItem('mpis_user', JSON.stringify(res.user));
    return res.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiPost('/auth/logout', { refresh_token: tokenStore.refresh });
    } catch {
      /* best-effort */
    }
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, logout, refreshUser }),
    [user, loading, login, logout, refreshUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

/** UX-only role helper — the backend enforces authorization on every call. */
export function hasRole(user: UserBrief | null, ...roles: string[]): boolean {
  return !!user && roles.includes(user.role);
}
