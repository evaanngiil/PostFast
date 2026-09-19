"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal, Loader2, Copy, Check, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import type { TerminalLog } from "@/lib/types";

interface AgentTerminalProps {
  logs: TerminalLog[];
  taskStatus: string | null;
  onClearLogs?: () => void;
}

/**
 * Consola de telemetría y ejecución en tiempo real (Supabase Broadcast),
 * con auto-scroll, formato monospace y utilidades de copiado/limpieza.
 */
export default function AgentTerminal({ logs, taskStatus, onClearLogs }: AgentTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(logs.length === 0 && !taskStatus);

  // Auto-expandir cuando inicia una tarea o llegan logs
  useEffect(() => {
    if (taskStatus || logs.length > 0) {
      setIsCollapsed(false);
    }
  }, [taskStatus, logs.length]);

  // Auto-scroll al recibir nuevos logs
  useEffect(() => {
    if (!isCollapsed && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, isCollapsed]);

  const handleCopyLogs = async () => {
    const rawText = logs.map((l) => `[${l.time}] ${l.sender}: ${l.msg}`).join("\n");
    try {
      await navigator.clipboard.writeText(rawText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden font-mono text-xs shadow-xs">
      {/* Console Bar Header */}
      <div
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="px-4 py-2.5 bg-slate-950 border-b border-slate-800 flex items-center justify-between text-slate-400 cursor-pointer select-none hover:bg-slate-900/60 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-brand-teal" />
          <span className="font-bold text-[11px] uppercase tracking-wider text-slate-300">
            Telemetría de Orquestación
          </span>
          {taskStatus ? (
            <span className="flex items-center gap-1.5 text-[10px] text-brand-teal bg-brand-teal/10 px-2 py-0.5 rounded border border-brand-teal/20">
              <Loader2 className="h-2.5 w-2.5 animate-spin" />
              <span>{taskStatus}</span>
            </span>
          ) : logs.length === 0 ? (
            <span className="text-[10px] text-slate-500 font-normal hidden sm:inline">
              • En espera
            </span>
          ) : (
            <span className="text-[10px] text-slate-500 font-mono">
              ({logs.length} eventos)
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {logs.length > 0 && (
            <>
              <button
                onClick={handleCopyLogs}
                className="p-1 hover:text-slate-200 transition-colors"
                title="Copiar registros al portapapeles"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
              {onClearLogs && (
                <button
                  onClick={onClearLogs}
                  className="p-1 hover:text-rose-400 transition-colors"
                  title="Limpiar consola"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </>
          )}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 hover:text-slate-200 transition-colors"
            title={isCollapsed ? "Expandir consola" : "Colapsar consola"}
          >
            {isCollapsed ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Log Feed */}
      {!isCollapsed && (
        <div
          ref={containerRef}
          className="p-3.5 flex flex-col gap-1.5 h-44 overflow-y-auto leading-relaxed scroll-smooth text-[11px]"
        >
          {logs.length === 0 ? (
            <span className="text-slate-600 italic">
              Sin eventos en cola. Los registros de ejecución de agentes se transmitirán aquí en tiempo real.
            </span>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="text-slate-600 shrink-0">[{log.time}]</span>
                <span className="text-brand-teal font-bold shrink-0">{log.sender}:</span>
                <span
                  className={
                    log.type === "success"
                      ? "text-emerald-400"
                      : log.type === "error"
                      ? "text-rose-400 font-semibold"
                      : log.type === "warn"
                      ? "text-amber-400"
                      : "text-slate-300"
                  }
                >
                  {log.msg}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
