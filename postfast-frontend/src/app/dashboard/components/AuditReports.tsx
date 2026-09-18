import { CheckCircle, UserCheck, Check, AlertCircle, ShieldAlert } from "lucide-react";
import type { FactCheckReport, SafetyReport } from "@/lib/types";

/** Tarjeta del reporte de verificación factual (CRAG). */
export function FactCheckCard({ report }: { report: FactCheckReport }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col gap-4">
      <h3 className="font-bold text-slate-800 flex items-center justify-between border-b border-slate-100 pb-3 text-sm">
        <span className="flex items-center gap-2">
          <CheckCircle className="h-4.5 w-4.5 text-brand-teal" />
          REPORTE DE VERIFICACIÓN (CRAG)
        </span>
        {(report as any).evaluated === false ? (
          <span className="text-[10px] px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full border border-amber-200 font-bold uppercase tracking-wider">
            No verificado
          </span>
        ) : report.overall_pass ? (
          <span className="text-[10px] px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full border border-emerald-200 font-bold uppercase tracking-wider">
            Verídico
          </span>
        ) : (
          <span className="text-[10px] px-2 py-0.5 bg-rose-100 text-rose-800 rounded-full border border-rose-200 font-bold uppercase tracking-wider">
            Alucinaciones
          </span>
        )}
      </h3>

      <p className="text-xs text-slate-500 leading-normal">{report.summary}</p>

      <div className="flex flex-col gap-2 max-h-48 overflow-y-auto pr-1">
        {report.claims.length === 0 ? (
          <div className="text-xs text-slate-400 italic p-2 bg-slate-50 rounded-lg text-center">No se extrajeron claims de datos específicos.</div>
        ) : (
          report.claims.map((claim, idx) => (
            <div key={idx} className={`p-3 rounded-lg border text-xs leading-normal flex flex-col gap-1.5 ${
              claim.verified
                ? "bg-emerald-50 border-emerald-100 text-emerald-800"
                : "bg-rose-50 border-rose-100 text-rose-800"
            }`}>
              <div className="flex items-start justify-between gap-2">
                <span className="font-bold flex items-center gap-1.5">
                  {claim.verified ? <Check className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
                  "{claim.claim}"
                </span>
              </div>
              {!claim.verified && claim.correction && (
                <div className="bg-rose-100/50 p-2 rounded border border-rose-200 mt-1">
                  <span className="font-bold uppercase text-[9px] text-rose-600 block mb-0.5">Corrección Vectorial:</span>
                  "{claim.correction}"
                </div>
              )}
              <div className="text-[10px] text-slate-500 flex justify-end gap-1">
                <span>Fuente RAG:</span>
                <span className="font-mono font-bold text-slate-600">{claim.source}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/** Tarjeta de la auditoría de compliance de marca (Safety Guard). */
export function SafetyGuardCard({ report }: { report: SafetyReport }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col gap-4">
      <h3 className="font-bold text-slate-800 flex items-center justify-between border-b border-slate-100 pb-3 text-sm">
        <span className="flex items-center gap-2">
          <UserCheck className="h-4.5 w-4.5 text-brand-teal" />
          AUDITORÍA DE CUMPLIMIENTO DE MARCA
        </span>
        {(report as any).evaluated === false ? (
          <span className="text-[10px] px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full border border-amber-200 font-bold uppercase tracking-wider">
            No auditado
          </span>
        ) : report.approved ? (
          <span className="text-[10px] px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full border border-emerald-200 font-bold uppercase tracking-wider">
            Aprobado
          </span>
        ) : (
          <span className="text-[10px] px-2 py-0.5 bg-rose-100 text-rose-800 rounded-full border border-rose-200 font-bold uppercase tracking-wider">
            Rechazado
          </span>
        )}
      </h3>

      {report.issues.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] font-bold text-rose-600 uppercase tracking-wider">Infracciones detectadas:</span>
          {report.issues.map((issue, idx) => (
            <div key={idx} className="flex gap-2 items-start text-xs text-rose-800 bg-rose-50 border border-rose-100 p-2 rounded-lg leading-normal">
              <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5 text-rose-500" />
              <span>{issue}</span>
            </div>
          ))}
        </div>
      )}

      {report.suggestions.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] font-bold text-emerald-600 uppercase tracking-wider">Recomendaciones del agente de marca:</span>
          {report.suggestions.map((sug, idx) => (
            <div key={idx} className="flex gap-2 items-start text-xs text-slate-700 bg-slate-50 border border-slate-200 p-2 rounded-lg leading-normal">
              <CheckCircle className="h-4 w-4 shrink-0 mt-0.5 text-brand-teal" />
              <span>{sug}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
