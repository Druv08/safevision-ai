import { useCallback, useRef, useState } from "react";
import { LuCircleCheck, LuCircleAlert, LuX } from "react-icons/lu";
import { ToastContext } from "../context/ToastContext";

const TTL_MS = 4500;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const toast = useCallback((message, tone = "ok") => {
    const id = ++nextId.current;
    setToasts((t) => [...t.slice(-3), { id, message, tone }]);
    setTimeout(() => dismiss(id), TTL_MS);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div aria-live="polite" className="fixed z-[70] bottom-4 right-4 left-4 sm:left-auto flex flex-col gap-2 sm:w-96 pointer-events-none">
        {toasts.map((t) => {
          const Icon = t.tone === "ok" ? LuCircleCheck : LuCircleAlert;
          return (
            <div key={t.id} role="status" className={`tone-${t.tone} card pointer-events-auto flex items-start gap-3 px-4 py-3 text-sm animate-fade-up`}>
              <Icon className="mt-0.5 flex-shrink-0 text-base" style={{ color: "var(--tone)" }} aria-hidden="true" />
              <p className="flex-1 text-fg">{t.message}</p>
              <button onClick={() => dismiss(t.id)} aria-label="Dismiss notification" className="text-muted hover:text-fg">
                <LuX />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
