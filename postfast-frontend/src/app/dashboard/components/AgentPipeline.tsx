"use client";

import React from "react";
import {
  Loader2,
  XCircle,
  Building,
  Edit3,
  PenLine,
  FileCheck,
  ShieldCheck,
  Check,
  UserCheck,
  Cpu,
} from "lucide-react";

interface AgentPipelineProps {
  /** Es una edición rápida (solo interviene el Content Editor). */
  isEditing: boolean;
  /** Nodos observados en orden real de ejecución (broadcasts). */
  agentSteps: string[];
  /** Nodo actualmente en ejecución, o null. */
  activeAgent: string | null;
  onStop: () => void;
}

/**
 * Visualizador del pipeline agéntico en estilo de flujo de trabajo corporativo
 * (Linear / Vercel workflow), con indicadores sobrios de ejecución secuencial.
 */
export default function AgentPipeline({
  isEditing,
  agentSteps,
  activeAgent,
  onStop,
}: AgentPipelineProps) {
  // Plan de fases según el flujo real
  let plannedSteps = isEditing
    ? ["Content Editor"]
    : ["Content Writer", "Fact Checker", "Safety Guard"];
  if (!isEditing && agentSteps.includes("Content Editor") && !agentSteps.includes("Content Writer")) {
    plannedSteps = ["Content Editor", "Fact Checker", "Safety Guard"];
  }
  const displaySteps = [...agentSteps, ...plannedSteps.filter((s) => !agentSteps.includes(s))];

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-teal-light text-brand-teal flex items-center justify-center border border-brand-teal-border">
            <Cpu className="h-4 w-4" />
          </div>
          <div className="flex flex-col">
            <h3 className="text-xs font-bold uppercase tracking-wider text-brand-charcoal">
              Pipeline de ejecución agéntica
            </h3>
            <span className="text-[11px] text-slate-400">
              Coordinación secuencial de agentes autónomos y validación
            </span>
          </div>
        </div>

        <button
          onClick={onStop}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
          title="Cancelar ejecución actual"
        >
          <XCircle className="h-3.5 w-3.5 text-rose-600" />
          <span>Cancelar</span>
        </button>
      </div>

      {/* Sequential Steps Bar */}
      <div className="grid gap-3 sm:grid-cols-3 relative">
        {displaySteps.map((step, i) => {
          const isActive = step === activeAgent;
          const isDone = !isActive && agentSteps.includes(step);

          const StepIcon =
            step.includes("Profiler") ? Building :
            step.includes("Editor") ? Edit3 :
            step.includes("Writer") ? PenLine :
            step.includes("Fact") ? FileCheck :
            step.includes("Safety") ? ShieldCheck :
            step.includes("Human") ? UserCheck : Cpu;

          return (
            <div
              key={step}
              className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
                isActive
                  ? "bg-brand-teal-light border-brand-teal-border shadow-xs"
                  : isDone
                  ? "bg-slate-50/80 border-slate-200 text-slate-700"
                  : "bg-white border-slate-200/60 opacity-60"
              }`}
            >
              <div
                className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 text-xs font-bold ${
                  isActive
                    ? "bg-brand-teal text-white"
                    : isDone
                    ? "bg-emerald-600 text-white"
                    : "bg-slate-100 text-slate-400"
                }`}
              >
                {isActive ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : isDone ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <span>{i + 1}</span>
                )}
              </div>

              <div className="flex flex-col min-w-0">
                <span
                  className={`text-xs font-bold truncate ${
                    isActive ? "text-brand-teal-dark" : isDone ? "text-slate-800" : "text-slate-400"
                  }`}
                >
                  {step}
                </span>
                <span className="text-[10px] text-slate-400">
                  {isActive ? "En proceso..." : isDone ? "Completado" : "En espera"}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Active Status Banner */}
      <div className="flex items-center gap-2.5 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-teal shrink-0" />
        <span className="truncate">
          {activeAgent
            ? `Agente activo: ${activeAgent} procesando directivas y fuentes de datos...`
            : "Orquestador inicializando contexto de redacción..."}
        </span>
      </div>
    </div>
  );
}
