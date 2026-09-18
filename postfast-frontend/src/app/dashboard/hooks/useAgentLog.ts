import { useCallback, useState } from "react";
import type { TerminalLog, LogType, ToastMessage } from "@/lib/types";

/**
 * Registro de la terminal de agentes (broadcasts). Los logs de tipo error/éxito
 * se elevan además como toast para mejorar la UX.
 */
export function useAgentLog(showToast: (text: string, type?: ToastMessage["type"]) => void) {
  const [logs, setLogs] = useState<TerminalLog[]>([]);

  const addLog = useCallback((sender: string, msg: string, type: LogType = "info") => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { time, sender, msg, type }]);
    if (type === "error") showToast(msg, "error");
    else if (type === "success") showToast(msg, "success");
  }, [showToast]);

  const clearLogs = useCallback(() => setLogs([]), []);

  return { logs, addLog, clearLogs, setLogs };
}
