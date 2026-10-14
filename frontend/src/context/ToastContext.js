import { createContext, useContext } from "react";

/* Context only; the provider is ToastProvider.jsx (keeps Fast Refresh happy). */
export const ToastContext = createContext(() => {});

/** toast("Saved") or toast("Failed", "danger"). */
export function useToast() {
  return useContext(ToastContext);
}
