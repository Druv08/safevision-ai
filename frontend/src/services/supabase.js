import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const isSupabaseConfigured = Boolean(url && anonKey);

// Dev-only flag: skip sign-in (backend must set AUTH_DISABLED=true too).
export const AUTH_DISABLED_FLAG = import.meta.env.VITE_AUTH_DISABLED === "true";

// Local demo mode: Supabase keys are missing, but this is a dev server or auth
// is explicitly disabled. The app runs with a no-op client instead of crashing.
// A production build without keys (and without VITE_AUTH_DISABLED) still throws.
export const DEMO_MODE = !isSupabaseConfigured && (AUTH_DISABLED_FLAG || import.meta.env.DEV);

if (!isSupabaseConfigured && !DEMO_MODE) {
  throw new Error("VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY must be set (see frontend/.env.example).");
}

if (DEMO_MODE) {
  console.warn(
    "[SafeVision] Supabase keys not set: running in local demo mode (no sign-in, no Supabase features). "
    + "Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in frontend/.env to enable them.",
  );
}

const notConfigured = { message: "Supabase is not configured (local demo mode)." };

// Query builder stand-in: every chained call returns itself and awaiting it
// resolves to an empty result, so Supabase-backed reads show an empty state.
function emptyQuery() {
  const q = {
    then: (resolve, reject) => Promise.resolve({ data: null, error: notConfigured }).then(resolve, reject),
  };
  for (const m of ["select", "insert", "update", "upsert", "delete", "eq", "neq", "in",
                   "order", "limit", "range", "single", "maybeSingle", "match", "filter"]) {
    q[m] = () => q;
  }
  return q;
}

// No-op client with the same shape the app uses: no session, sign-in reports
// that Supabase is not configured, everything else is harmless.
const demoClient = {
  auth: {
    getSession: async () => ({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
    signInWithPassword: async () => ({ data: { session: null, user: null }, error: notConfigured }),
    signOut: async () => ({ error: null }),
  },
  from: () => emptyQuery(),
};

// Browser client: anon key only. The service-role key must never be used here.
export const supabase = isSupabaseConfigured ? createClient(url, anonKey) : demoClient;
