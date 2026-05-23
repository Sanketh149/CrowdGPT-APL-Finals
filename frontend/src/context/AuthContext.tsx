import React, { createContext, useContext, useEffect, useState } from "react";
import type { AuthState, User } from "../types";

interface AuthContextValue extends AuthState {
  logout: () => Promise<void>;
  refetch: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  error: null,
  logout: async () => {},
  refetch: async () => {},
});

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true, error: null });

  const fetchMe = async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const res = await fetch(`${API_URL}/auth/me`, { credentials: "include" });
      if (res.ok) {
        const user: User = await res.json();
        setState({ user, loading: false, error: null });
      } else {
        setState({ user: null, loading: false, error: null });
      }
    } catch {
      setState({ user: null, loading: false, error: null });
    }
  };

  const logout = async () => {
    await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
    setState({ user: null, loading: false, error: null });
    window.location.href = "/login";
  };

  useEffect(() => { fetchMe(); }, []);

  return (
    <AuthContext.Provider value={{ ...state, logout, refetch: fetchMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
