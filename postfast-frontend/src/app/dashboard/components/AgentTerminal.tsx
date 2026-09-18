import { useEffect, useRef } from "react";
import { Terminal, Loader2 } from "lucide-react";
import type { TerminalLog } from "@/lib/types";

interface AgentTerminalProps {
  logs: TerminalLog[];
  taskStatus: string | null;
}

/**
 * Terminal en tiempo real de los broadcasts de Supabase. Altura fija con
 * scroll interno y auto-scroll al final: el layout no se desplaza al llegar logs.
 */
export default function AgentTerminal({ logs, taskStatus }: AgentTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll: desplaza SOLO el contenedor interno del terminal.
  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  return (
    <section className="bg-slate-950 border border-slate-800 rounded-2xl p-5 flex flex-col gap-3 font-mono">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2 text-xs font-bold text-slate-400">
          <Terminal className="h-4.5 w-4.5 text-brand-teal" />
          TERMINAL DE AGENTES (SUPABASE BROADCAST)
        </div>
        <div className="flex items-center gap-2 text-xs text-brand-teal">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Grafo en ejecución ({taskStatus})...
        </div>
      </div>

      <div ref={containerRef} className="flex flex-col gap-2 h-56 overflow-y-auto pr-2 text-xs leading-relaxed font-semibold scroll-smooth">
        {logs.map((log, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-slate-600">[{log.time}]</span>
            <span className="text-brand-teal font-bold shrink-0">{log.sender}:</span>
            <span className={
              log.type === "success" ? "text-emerald-400" :
              log.type === "error" ? "text-rose-400" :
              log.type === "warn" ? "text-amber-400" : "text-slate-300"
            }>
              {log.msg}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
