"use client";

import React from "react";
import {
  FileText,
  Clock,
  Share2,
  CheckCircle2,
  LayoutTemplate,
  Globe,
  ThumbsUp,
  MessageSquare,
  Repeat2,
  Send,
  Edit3,
  X,
  RotateCcw,
} from "lucide-react";
import PromptControls from "./PromptControls";
import LinkedInCard from "./LinkedInCard";
import QualityInspector from "./QualityInspector";
import AgentPipeline from "../AgentPipeline";
import AgentTerminal from "../AgentTerminal";
import type { CompanyAccount, UserInfo } from "../layout/AppHeader";
import type { FactCheckReport, SafetyReport, TerminalLog, KnowledgeGap } from "@/lib/types";

interface StudioProps {
  knowledgeGap?: KnowledgeGap | null;
  promptQuery: string;
  setPromptQuery: (val: string) => void;
  linkUrl: string;
  setLinkUrl: (url: string) => void;
  skills: any[];
  selectedSkillIds: string[];
  setSelectedSkillIds: (ids: string[]) => void;
  isGenerating: boolean;
  onGenerate: () => void;
  onStop: () => void;
  activeAgent: string | null;
  agentSteps: string[];
  draftContent: string;
  draftHashtags: string[];
  draftCta: string;
  selectedCompany: CompanyAccount | null;
  userInfo: UserInfo | null;
  factCheck: FactCheckReport | null;
  safetyReport: SafetyReport | null;
  checkpointConfig: any;
  userFeedback: string;
  setUserFeedback: (feedback: string) => void;
  onSubmitFeedback: (isApproved: boolean) => void;
  isSubmittingFeedback: boolean;
  onSaveDraft?: () => void;
  onSchedule: () => void;
  onPublish: () => void;
  onEdit: () => void;
  isPublishing?: boolean;
  terminalLogs: TerminalLog[];
  taskStatus: string | null;
  clearLogs: () => void;
  editingPost?: any | null;
  editInstruction?: string;
  setEditInstruction?: (val: string) => void;
  onCancelEdit?: () => void;
  onResetStudio?: () => void;
}

export default function Studio({
  knowledgeGap,
  promptQuery,
  setPromptQuery,
  linkUrl,
  setLinkUrl,
  skills,
  selectedSkillIds,
  setSelectedSkillIds,
  isGenerating,
  onGenerate,
  onStop,
  activeAgent,
  agentSteps,
  draftContent,
  draftHashtags,
  draftCta,
  selectedCompany,
  userInfo,
  factCheck,
  safetyReport,
  checkpointConfig,
  userFeedback,
  setUserFeedback,
  onSubmitFeedback,
  isSubmittingFeedback,
  onSaveDraft,
  onSchedule,
  onPublish,
  onEdit,
  isPublishing,
  terminalLogs,
  taskStatus,
  clearLogs,
  editingPost,
  editInstruction,
  setEditInstruction,
  onCancelEdit,
  onResetStudio,
}: StudioProps) {
  const hasDraft = Boolean(draftContent.trim());
  const isEditMode = Boolean(editingPost);

  const isPersonal = selectedCompany?.is_personal ?? true;
  const authorName = isPersonal
    ? userInfo?.name || selectedCompany?.name || "Usuario"
    : selectedCompany?.name || "Empresa";
  const authorSubtitle = isPersonal
    ? "Profesional en LinkedIn"
    : "Página de Empresa Oficial";
  const authorAvatar = isPersonal
    ? userInfo?.picture || selectedCompany?.logo_url
    : selectedCompany?.logo_url || userInfo?.picture;

  return (
    <div className="w-full max-w-[116rem] 2xl:max-w-[124rem] 3xl:max-w-[136rem] mx-auto px-3 sm:px-5 lg:px-6 xl:px-8 2xl:px-12 py-4 sm:py-6 2xl:py-8">
      {isEditMode ? (
        <div className="mb-5 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-center justify-between text-xs text-amber-900 shadow-2xs">
          <div className="flex items-center gap-2.5">
            <Edit3 className="h-4 w-4 text-[#2B8385] shrink-0" />
            <div>
              <span className="font-bold">Modo de edición activo:</span>
              <span className="ml-1.5 text-amber-800">
                Optimizando publicación existente ({editingPost?.id ? editingPost.id.slice(0, 8) : "Borrador"})
              </span>
            </div>
          </div>
          {onCancelEdit && (
            <button
              type="button"
              onClick={onCancelEdit}
              className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-md bg-white hover:bg-amber-100 text-amber-900 border border-amber-300 transition-colors cursor-pointer"
            >
              <X className="h-3.5 w-3.5" />
              <span>Salir de edición y nuevo post</span>
            </button>
          )}
        </div>
      ) : hasDraft && (
        <div className="mb-5 bg-white border border-slate-200 rounded-xl px-4 py-2.5 flex items-center justify-between text-xs shadow-2xs">
          <div className="flex items-center gap-2 text-slate-700">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            <span className="font-semibold text-slate-900">Borrador listo</span>
            <span className="text-slate-400 hidden sm:inline">• Puedes revisarlo, programarlo o limpiar para iniciar un nuevo post</span>
          </div>
          {onResetStudio && (
            <button
              type="button"
              onClick={onResetStudio}
              className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors cursor-pointer"
              title="Borrar todo lo generado y volver a un estado limpio"
            >
              <RotateCcw className="h-3.5 w-3.5 text-slate-500" />
              <span>Limpiar y nuevo post</span>
            </button>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6 2xl:gap-8 items-start">
        <aside className="lg:col-span-5 xl:col-span-4 2xl:col-span-4 flex flex-col gap-4 2xl:gap-5 lg:sticky lg:top-20 2xl:top-24 lg:max-h-[calc(100dvh-5.5rem)] lg:overflow-y-auto pr-0 lg:pr-1 custom-scroll">
          <PromptControls
            promptQuery={promptQuery}
            setPromptQuery={setPromptQuery}
            linkUrl={linkUrl}
            setLinkUrl={setLinkUrl}
            skills={skills}
            selectedSkillIds={selectedSkillIds}
            setSelectedSkillIds={setSelectedSkillIds}
            isGenerating={isGenerating}
            onGenerate={onGenerate}
            onStop={onStop}
            editingPost={editingPost}
            editInstruction={editInstruction}
            setEditInstruction={setEditInstruction}
            onCancelEdit={onCancelEdit}
            onResetStudio={onResetStudio}
          />
        </aside>

        <main className="lg:col-span-7 xl:col-span-4 2xl:col-span-5 flex flex-col gap-5 min-w-0">
          {isGenerating && (
            <AgentPipeline
              isEditing={isEditMode}
              agentSteps={agentSteps}
              activeAgent={activeAgent}
              onStop={onStop}
            />
          )}

          {hasDraft ? (
            <LinkedInCard
              content={draftContent}
              hashtags={draftHashtags}
              cta={draftCta}
              selectedCompany={selectedCompany}
              userInfo={userInfo}
              onSaveDraft={onSaveDraft}
              onSchedule={onSchedule}
              onPublish={onPublish}
              onEdit={onEdit}
              onDelete={onResetStudio}
              isPublishing={isPublishing}
              isEditMode={isEditMode}
            />
          ) : !isGenerating ? (
            /* Realistic LinkedIn Preview Canvas Mockup */
            <div className="flex flex-col gap-3 w-full">
              {/* Device & State Bar */}
              <div className="flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs 2xl:text-sm font-bold text-slate-500 uppercase tracking-wider">
                    Previsualización feed LinkedIn
                  </span>
                  <span className="text-[0.6875rem] 2xl:text-xs text-slate-400 font-mono hidden sm:inline">
                    Formato 1:1 oficial
                  </span>
                </div>
                <span className="text-[0.6875rem] 2xl:text-xs font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/80">
                  Paso 2: Previsualización
                </span>
              </div>

              {/* Feed Canvas Viewport Wrapper */}
              <div className="bg-[#E4E7EB] p-3 sm:p-5 2xl:p-7 rounded-xl border border-slate-300/90 shadow-inner">
                {/* LinkedIn Post Card Shell */}
                <article className="bg-white rounded-xl border border-slate-300/80 shadow-[0_2px_12px_rgba(0,0,0,0.06)] overflow-hidden">
                {/* Header: Author */}
                <div className="p-4 pb-3 flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    {authorAvatar ? (
                      <img
                        src={authorAvatar}
                        alt={authorName}
                        className={`w-11 h-11 2xl:w-12 2xl:h-12 object-cover border border-slate-200 shrink-0 ${
                          isPersonal ? "rounded-full" : "rounded-lg"
                        }`}
                      />
                    ) : (
                      <div
                        className={`w-11 h-11 2xl:w-12 2xl:h-12 bg-brand-charcoal text-white font-bold flex items-center justify-center text-sm uppercase shrink-0 ${
                          isPersonal ? "rounded-full" : "rounded-lg"
                        }`}
                      >
                        {authorName.slice(0, 2)}
                      </div>
                    )}
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm 2xl:text-base font-bold text-slate-900 truncate">
                          {authorName}
                        </span>
                        <span className="text-xs text-slate-400 font-normal">• 1.º</span>
                      </div>
                      <span className="text-xs text-slate-500 leading-tight truncate">
                        {authorSubtitle}
                      </span>
                      <div className="flex items-center gap-1 text-[0.6875rem] 2xl:text-xs text-slate-400 mt-0.5">
                        <span>Borrador en preparación</span>
                        <span>•</span>
                        <Globe className="h-3 w-3 text-slate-400" />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Body Mockup / Prompt Invitation */}
                <div className="px-5 py-9 2xl:py-16 border-t border-b border-dashed border-slate-200 bg-slate-50/40 flex flex-col items-center justify-center text-center gap-3 2xl:gap-4 min-h-[220px] 2xl:min-h-[300px]">
                  <div className="w-10 h-10 2xl:w-12 2xl:h-12 rounded-xl bg-white border border-slate-200 flex items-center justify-center text-brand-teal shadow-xs">
                    <LayoutTemplate className="h-5 w-5 2xl:h-6 2xl:w-6 text-brand-teal" />
                  </div>
                  <div className="max-w-md flex flex-col gap-1.5">
                    <h3 className="text-xs 2xl:text-sm font-bold text-brand-charcoal">
                      Lienzo de redacción listo
                    </h3>
                    <p className="text-xs 2xl:text-sm text-slate-500 leading-relaxed">
                      Describe tu idea en el panel izquierdo y pulsa{" "}
                      <span className="font-semibold text-brand-charcoal">"Redactar publicación"</span>{" "}
                      para generar el post optimizado con datos contrastados y directivas de estilo.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center justify-center gap-1.5 mt-1">
                    <span className="text-xs font-mono text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                      Ganchos de apertura
                    </span>
                    <span className="text-xs font-mono text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                      Verificación RAG
                    </span>
                    <span className="text-xs font-mono text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                      Hashtags sectoriales
                    </span>
                  </div>
                </div>

                {/* Social Metrics Bar Mockup */}
                <div className="px-4 py-2 border-b border-slate-100 flex items-center justify-between text-xs text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <div className="flex -space-x-1 items-center">
                      <span className="w-4 h-4 rounded-full bg-[#0A66C2] flex items-center justify-center text-white text-[0.625rem]">
                        👍
                      </span>
                      <span className="w-4 h-4 rounded-full bg-emerald-600 flex items-center justify-center text-white text-[0.625rem]">
                        👏
                      </span>
                      <span className="w-4 h-4 rounded-full bg-rose-500 flex items-center justify-center text-white text-[0.625rem]">
                        ❤️
                      </span>
                    </div>
                    <span className="text-xs text-slate-400 font-medium">Reacciones simuladas</span>
                  </div>
                  <span className="text-xs text-slate-400">0 comentarios • 0 compartidos</span>
                </div>

                {/* Social Actions Mockup */}
                <div className="px-2 py-1 bg-slate-50/50 flex items-center justify-around text-slate-400">
                  <div className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold">
                    <ThumbsUp className="h-4 w-4 text-slate-400" />
                    <span>Recomendar</span>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold">
                    <MessageSquare className="h-4 w-4 text-slate-400" />
                    <span>Comentar</span>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold">
                    <Repeat2 className="h-4 w-4 text-slate-400" />
                    <span>Compartir</span>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold">
                    <Send className="h-4 w-4 text-slate-400" />
                    <span>Enviar</span>
                  </div>
                </div>
              </article>
              </div>
            </div>
          ) : null}

          {/* Collapsible Telemetry / Agent Terminal */}
          <AgentTerminal
            logs={terminalLogs}
            taskStatus={taskStatus}
            onClearLogs={clearLogs}
          />
        </main>

        <aside className="lg:col-span-12 xl:col-span-4 2xl:col-span-3 flex flex-col gap-4 2xl:gap-5">
          <QualityInspector
            factCheck={factCheck}
            safetyReport={safetyReport}
            knowledgeGap={knowledgeGap}
            checkpointConfig={checkpointConfig}
            userFeedback={userFeedback}
            setUserFeedback={setUserFeedback}
            onSubmitFeedback={onSubmitFeedback}
            isSubmittingFeedback={isSubmittingFeedback}
            isEditMode={isEditMode}
            onResetStudio={onResetStudio}
          />
        </aside>
      </div>
    </div>
  );
}
