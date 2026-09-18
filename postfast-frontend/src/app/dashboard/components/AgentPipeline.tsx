import { Sparkles, Loader2, XCircle, Building, Edit3, Wand2, CheckCircle, ShieldAlert, Check } from "lucide-react";

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
 * Visualizador del pipeline agéntico: fases planificadas visibles desde el inicio
 * como círculos vacíos -> se rellenan al activarse -> check al completarse.
 */
export default function AgentPipeline({ isEditing, agentSteps, activeAgent, onStop }: AgentPipelineProps) {
  // Plan de fases según el flujo real:
  // - Edición rápida: solo el editor (los validadores se omiten).
  // - Ciclo de feedback HITL: editor + validadores (sin writer).
  // - Generación normal: writer + validadores.
  let plannedSteps = isEditing
    ? ["Content Editor"]
    : ["Content Writer", "Fact Checker", "Safety Guard"];
  if (!isEditing && agentSteps.includes("Content Editor") && !agentSteps.includes("Content Writer")) {
    plannedSteps = ["Content Editor", "Fact Checker", "Safety Guard"];
  }
  // Fases observadas (en orden real) + planificadas aún no vistas.
  const displaySteps = [...agentSteps, ...plannedSteps.filter((s) => !agentSteps.includes(s))];

  return (
    <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col gap-6 items-center">
      <div className="flex flex-col items-center text-center gap-2">
        <div className="relative flex items-center justify-center w-16 h-16 bg-brand-teal/10 rounded-full text-brand-teal animate-pulse">
          <Sparkles className="w-8 h-8 animate-spin" style={{ animationDuration: "8s" }} />
          <div className="absolute inset-0 border-2 border-brand-teal rounded-full animate-ping opacity-20"></div>
        </div>
        <h3 className="text-base font-bold text-slate-800 mt-2">Generación Agéntica en Progreso</h3>
        <p className="text-xs text-slate-500 max-w-md">
          El Orquestador está coordinando a los agentes autónomos de AIPost para redactar y verificar tu publicación.
        </p>
      </div>

      <div
        className="w-full max-w-2xl grid gap-4 relative mt-2"
        style={{ gridTemplateColumns: `repeat(${displaySteps.length}, minmax(0, 1fr))` }}
      >
        {displaySteps.length > 1 && (
          <div className="absolute top-5 left-6 right-6 h-0.5 bg-slate-100 z-0"></div>
        )}

        {displaySteps.map((step, i) => {
          const isActive = step === activeAgent;
          const isDone = !isActive && agentSteps.includes(step);
          const StepIcon =
            step.includes("Profiler") ? Building :
            step.includes("Editor") ? Edit3 :
            step.includes("Writer") ? Wand2 :
            step.includes("Fact") ? CheckCircle :
            step.includes("Safety") ? ShieldAlert : Sparkles;
          return (
            <div key={step} className="flex flex-col items-center text-center gap-2 z-10">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 ${
                isActive
                  ? "bg-brand-teal text-white border-brand-teal shadow-md shadow-brand-teal/20 scale-110 animate-pulse"
                  : isDone
                  ? "bg-emerald-500 text-white border-emerald-500 shadow-sm"
                  : "bg-white text-slate-300 border-slate-200"
              }`}>
                {isDone ? <Check className="w-4.5 h-4.5" /> : <StepIcon className="w-4.5 h-4.5" />}
              </div>
              <div className="flex flex-col gap-0.5">
                <span className={`text-[10px] font-bold ${
                  isActive ? "text-brand-teal" : isDone ? "text-emerald-600" : "text-slate-400"
                }`}>{i + 1}. {step}</span>
                <span className="text-[8px] text-slate-400">
                  {isActive ? "En ejecución..." : isDone ? "Completado" : "Pendiente"}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="w-full max-w-md bg-slate-50 border border-slate-200 rounded-xl p-3 flex gap-3 items-center mt-2 animate-pulse">
        <Loader2 className="w-4 h-4 animate-spin text-brand-teal shrink-0" />
        <span className="text-xs font-semibold text-slate-600">
          {activeAgent
            ? `${activeAgent} está trabajando en tu publicación...`
            : "Conectando con el orquestador y arrancando los agentes..."}
        </span>
      </div>

      <button
        onClick={onStop}
        className="flex items-center gap-1.5 px-5 py-2.5 bg-rose-50 hover:bg-rose-100 text-rose-700 hover:text-rose-800 border border-rose-200 rounded-xl text-xs font-bold shadow-sm transition-colors cursor-pointer"
      >
        <XCircle className="w-4.5 h-4.5" />
        Detener
      </button>
    </section>
  );
}
