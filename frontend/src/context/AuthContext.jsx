import { createContext, useContext, useEffect, useState } from "react";
import { supabase } from "../services/supabase";

const AuthContext = createContext(null);

export const AUTH_DISABLED = import.meta.env.VITE_AUTH_DISABLED === "true";

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  // RLS lets a user read only their own profile row.
  const userId = session?.user?.id;
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    supabase
      .from("profiles")
      .select("role")
      .eq("id", userId)
      .single()
      .then(({ data }) => { if (!cancelled) setRole(data?.role ?? "viewer"); });
    return () => { cancelled = true; };
  }, [userId]);

  // Dev-only: skip sign-in entirely (backend must set AUTH_DISABLED=true too).
  if (AUTH_DISABLED) {
    const devUser = { id: null, email: "dev@local" };
    return (
      <AuthContext.Provider value={{
        session: { user: devUser }, user: devUser, role: "admin", isAdmin: true, loading: false,
        signIn: async () => ({}), signOut: async () => {},
      }}>{children}</AuthContext.Provider>
    );
  }

  const value = {
    session,
    user: session?.user ?? null,
    role: userId ? role : null,
    isAdmin: Boolean(userId) && role === "admin",
    loading,
    signIn: (email, password) => supabase.auth.signInWithPassword({ email, password }),
    signOut: () => supabase.auth.signOut(),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext);
}
