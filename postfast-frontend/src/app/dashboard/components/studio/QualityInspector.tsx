"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  RotateCw,
  Send,
  Info,
  Check,
  XCircle,
  Clock,
  Trash2,
} from "lucide-react";
import type { FactCheckReport, SafetyReport, KnowledgeGap } from "@/lib/types";

interface QualityInspectorProps {
  factCheck: FactCheckReport | null;
  safetyReport: SafetyReport | null;
  knowledgeGap?: KnowledgeGap | null;
  checkpointConfig: any;
  userFeedback: string;
  setUserFeedback: (feedback: string) => void;
  onSubmitFeedback: (isApproved: boolean) => void;
  isSubmittingFeedback: boolean;
  isEditMode?: boolean;
  onResetStudio?: () => void;
}

export default function QualityInspector({
  factCheck,
  safetyReport,
  knowledgeGap,
  checkpointConfig,
  userFeedback,
  setUserFeedback,
  onSubmitFeedback,
  isSubmittingFeedback,
  isEditMode,
  onResetStudio,
}: QualityInspectorProps) {
  const [activeAccordion, setActiveAccordion] = useState<"fact" | "safety" | "feedback">("fact");

  const hasAudited = Boolean(factCheck || safetyReport);
  const isFactCheckPassed = factCheck ? factCheck.overall_pass : null;
  const isSafetyApproved = safetyReport ? safetyReport.approved : null;
  const isPendingReview = !!checkpointConfig;

  // Calculate composite quality score (0 - 100)
  const calculateScore = () => {
    if (!hasAudited) return null;
    let score = 70;
    if (factCheck) {
      score += factCheck.overall_pass ? 15 : -15;
    }
    if (safetyReport) {
      score += safetyReport.approved ? 15 : -15;
    }
    return Math.min(100, Math.max(30, score));
  };

  const qualityScore = calculateScore();

  return (
    <div className="flex flex-col gap-4 w-full">
      {/* Overall Quality Score Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-teal-light text-brand-teal flex items-center justify-center font-bold text-xs border border-brand-teal-border">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs 2xl:text-sm font-bold text-brand-charcoal uppercase tracking-wider">
                Control de calidad
              </span>
              <span className="text-xs text-slate-400">
                {hasAudited ? "Auditoría factual y cumplimiento normativo" : "Pendiente de ejecución del pipeline"}
              </span>
            </div>
          </div>

          <div className="flex items-baseline gap-1 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
            {qualityScore !== null ? (
              <>
                <span className="text-lg 2xl:text-xl font-extrabold text-brand-charcoal">{qualityScore}</span>
                <span className="text-[0.6875rem] 2xl:text-xs font-bold text-slate-400">/ 100</span>
              </>
            ) : (
              <span className="text-xs 2xl:text-sm font-bold text-slate-400 font-mono">-- / 100</span>
            )}
          </div>
        </div>

        {/* Verification Badges Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-100">
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200/80 min-w-0">
            {isFactCheckPassed === true ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
            ) : isFactCheckPassed === false ? (
              <AlertTriangle className="h-3.5 w-3.5 text-rose-500 shrink-0" />
            ) : (
              <Clock className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            )}
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-bold text-slate-700 truncate">Verificación CRAG</span>
              <span className="text-[0.6875rem] 2xl:text-xs text-slate-400">
                {factCheck ? (isFactCheckPassed ? "Datos contrastados" : "Discrepancias") : "En espera de post"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200/80 min-w-0">
            {isSafetyApproved === true ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
            ) : isSafetyApproved === false ? (
              <AlertTriangle className="h-3.5 w-3.5 text-rose-500 shrink-0" />
            ) : (
              <Clock className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            )}
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-bold text-slate-700 truncate">Seguridad de marca</span>
              <span className="text-[0.6875rem] 2xl:text-xs text-slate-400">
                {safetyReport ? (isSafetyApproved ? "Do's & Don'ts OK" : "Infracción detectada") : "En espera de post"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {knowledgeGap && knowledgeGap.has_gap && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-3.5 flex flex-col gap-1.5 shadow-2xs text-amber-950">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
            <span className="text-xs font-bold uppercase tracking-wider text-amber-900">
              Vacío de información documental detectado
            </span>
          </div>
          <p className="text-xs leading-relaxed text-amber-900">
            {knowledgeGap.user_message || knowledgeGap.missing_info}
          </p>
        </div>
      )}

      {/* Informational Guidance when no audit has run yet */}
      {!hasAudited && !isPendingReview && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col gap-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <FileCheck className="h-4 w-4 text-brand-teal" />
              <h3 className="text-xs 2xl:text-sm font-bold uppercase tracking-wider text-brand-charcoal">
                Pipeline de gobernanza
              </h3>
            </div>
            <span className="text-[0.6875rem] 2xl:text-xs font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/80">
              Paso 3: Auditoría
            </span>
          </div>

          <div className="flex flex-col gap-2.5 2xl:gap-3.5 text-xs 2xl:text-sm">
            <div className="flex items-start gap-2.5 p-2.5 2xl:p-3.5 rounded-lg bg-slate-50 border border-slate-200/60">
              <FileCheck className="h-4 w-4 2xl:h-4.5 2xl:w-4.5 text-brand-teal shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-slate-800 text-xs 2xl:text-sm">Contraste factual RAG</span>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                  Verifica que afirmaciones numéricas o estratégicas provengan directamente de tus documentos indexados.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2.5 p-2.5 2xl:p-3.5 rounded-lg bg-slate-50 border border-slate-200/60">
              <ShieldCheck className="h-4 w-4 2xl:h-4.5 2xl:w-4.5 text-brand-teal shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-slate-800 text-xs 2xl:text-sm">Filtro de directivas (Do's y Don'ts)</span>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                  Evalúa las restricciones de tono y terminología de tu empresa para evitar riesgos de reputación.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2.5 p-2.5 2xl:p-3.5 rounded-lg bg-slate-50 border border-slate-200/60">
              <CheckCircle2 className="h-4 w-4 2xl:h-4.5 2xl:w-4.5 text-brand-teal shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-slate-800 text-xs 2xl:text-sm">Aprobación humana (HITL)</span>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                  El orquestador detendrá el flujo para que revises el borrador antes de cualquier publicación.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Human In The Loop (HITL) Checkpoint Banner */}
      {isPendingReview && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
            <span className="text-xs font-bold text-amber-900 uppercase tracking-wider">
              Revisión requerida (HITL)
            </span>
          </div>
          <p className="text-xs text-amber-800 leading-relaxed">
            {isEditMode
              ? "Valida las mejoras aplicadas a la publicación. Puedes solicitar nuevos ajustes o aprobar para guardar definitivamente en el Histórico."
              : "El flujo agéntico se ha pausado para que valides el borrador. Puedes solicitar ajustes de redacción o aprobar el contenido directamente."}
          </p>
          <div className="flex flex-col gap-2">
            <textarea
              value={userFeedback}
              onChange={(e) => setUserFeedback(e.target.value)}
              placeholder="Instrucciones de mejora (ej: hazlo más directo, enfatiza el dato de crecimiento, acorta el primer párrafo)..."
              className="w-full text-xs p-2.5 rounded-lg border border-amber-300 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 min-h-[70px]"
            />
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 pt-1">
              {onResetStudio ? (
                <button
                  type="button"
                  onClick={onResetStudio}
                  className="flex items-center justify-center gap-1.5 px-2.5 py-1.5 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-lg text-xs font-semibold shadow-xs cursor-pointer shrink-0"
                  title="Descartar borrador y empezar de nuevo con un estado limpio"
                >
                  <Trash2 className="h-3 w-3 text-rose-500 shrink-0" />
                  <span>Descartar</span>
                </button>
              ) : <div />}
              <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
                <button
                  onClick={() => onSubmitFeedback(false)}
                  disabled={isSubmittingFeedback || !userFeedback.trim()}
                  className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-2.5 sm:px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 rounded-lg text-xs font-semibold shadow-xs disabled:opacity-40 cursor-pointer whitespace-nowrap"
                >
                  <RotateCw className="h-3 w-3 shrink-0" />
                  <span>Ajustar</span>
                </button>
                <button
                  onClick={() => onSubmitFeedback(true)}
                  disabled={isSubmittingFeedback}
                  className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow-xs disabled:opacity-40 cursor-pointer whitespace-nowrap"
                >
                  <Check className="h-3 w-3 shrink-0" />
                  <span>{isEditMode ? "Aprobar cambios" : "Aprobar"}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Accordion 1: Fact Check Claims Breakdown */}
      {factCheck && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
          <button
            onClick={() => setActiveAccordion(activeAccordion === "fact" ? ("" as any) : "fact")}
            className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-slate-50 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <FileCheck className="h-4 w-4 text-brand-teal" />
              <span className="text-xs font-bold text-brand-charcoal">
                Evidencia factual ({factCheck.claims.length} afirmaciones)
              </span>
            </div>
            {activeAccordion === "fact" ? (
              <ChevronUp className="h-3.5 w-3.5 text-slate-400" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
            )}
          </button>

          {activeAccordion === "fact" && (
            <div className="px-4 pb-4 pt-1 flex flex-col gap-2 border-t border-slate-100 max-h-64 overflow-y-auto custom-scroll">
              <p className="text-[11px] text-slate-500 leading-normal">{factCheck.summary}</p>
              {factCheck.claims.length === 0 ? (
                <span className="text-xs text-slate-400 italic py-2 text-center">
                  No se detectaron datos numéricos o citas específicas sujetas a verificación.
                </span>
              ) : (
                factCheck.claims.map((c, i) => {
                  const isReallyVerified = Boolean(c.verified && c.source && c.source !== "no_source_found");
                  return (
                    <div
                      key={i}
                      className={`p-2.5 rounded-lg border text-xs leading-normal flex flex-col gap-1 ${
                        isReallyVerified
                          ? "bg-emerald-50/60 border-emerald-200/80 text-emerald-900"
                          : "bg-rose-50/60 border-rose-200/80 text-rose-900"
                      }`}
                    >
                      <div className="flex items-start gap-1.5 font-semibold">
                        {isReallyVerified ? (
                          <Check className="h-3.5 w-3.5 text-emerald-600 shrink-0 mt-0.5" />
                        ) : (
                          <AlertTriangle className="h-3.5 w-3.5 text-rose-500 shrink-0 mt-0.5" />
                        )}
                        <span>"{c.claim}"</span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 mt-0.5 font-mono">
                        <span>{isReallyVerified ? "Dato verificado" : "Sin evidencia"}</span>
                        <span>
                          Fuente: {c.source === "no_source_found" ? "No encontrada en RAG" : c.source}
                        </span>
                      </div>
                      {!isReallyVerified && c.correction && (
                        <p className="text-[11px] text-rose-700 font-sans mt-0.5 leading-snug">
                          {c.correction}
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      )}

      {/* Accordion 2: Brand Safety & Guidelines */}
      {safetyReport && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
          <button
            onClick={() => setActiveAccordion(activeAccordion === "safety" ? ("" as any) : "safety")}
            className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-slate-50 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-brand-teal" />
              <span className="text-xs font-bold text-brand-charcoal">
                Gobernanza de marca y cumplimiento
              </span>
            </div>
            {activeAccordion === "safety" ? (
              <ChevronUp className="h-3.5 w-3.5 text-slate-400" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
            )}
          </button>

          {activeAccordion === "safety" && (
            <div className="px-4 pb-4 pt-1 flex flex-col gap-2.5 border-t border-slate-100 max-h-64 overflow-y-auto custom-scroll">
              {safetyReport.issues.length === 0 ? (
                <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-800 text-xs flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  <span>El contenido cumple con todas las directivas de marca y tono establecidas.</span>
                </div>
              ) : (
                safetyReport.issues.map((issue, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2"
                  >
                    <AlertTriangle className="h-4 w-4 text-rose-500 shrink-0 mt-0.5" />
                    <span>{issue}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
