import { useCallback, useState } from "react";
import type { ToastMessage } from "@/lib/types";

/** Gestiona la notificación flotante efímera (toast) del dashboard. */
export function useToast() {
  const [toast, setToast] = useState<ToastMessage | null>(null);

  const showToast = useCallback((text: string, type: ToastMessage["type"] = "info") => {
    setToast({ text, type });
    setTimeout(() => {
      setToast((prev) => (prev && prev.text === text ? null : prev));
    }, 5000);
  }, []);

  const clearToast = useCallback(() => setToast(null), []);

  return { toast, showToast, clearToast };
}
