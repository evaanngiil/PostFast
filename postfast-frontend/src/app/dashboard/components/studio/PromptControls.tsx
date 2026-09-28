"use client";

import React from "react";
import {
  Link as LinkIcon,
  Check,
  ChevronDown,
  X,
  Layers,
  FileText,
  StopCircle,
  Loader2,
  ArrowRight,
  ShieldCheck,
  Edit3,
  Sparkles,
  RotateCcw,
} from "lucide-react";

interface SkillItem {
  id: string;
  name: string;
  description?: string;
}

const cleanSkillName = (name: string) => (name || "").replace(/\s*\((?:Base|BASE)\)/gi, "").trim();

interface PromptControlsProps {
  promptQuery: string;
  setPromptQuery: (val: string) => void;
  linkUrl: string;
  setLinkUrl: (url: string) => void;
  skills: SkillItem[];
  selectedSkillIds: string[];
  setSelectedSkillIds: (ids: string[]) => void;
  isGenerating: boolean;
  onGenerate: () => void;
  onStop: () => void;
  editingPost?: any | null;
  editInstruction?: string;
  setEditInstruction?: (val: string) => void;
  onCancelEdit?: () => void;
  onResetStudio?: () => void;
}

export default function PromptControls({
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
  editingPost,
  editInstruction,
  setEditInstruction,
  onCancelEdit,
  onResetStudio,
}: PromptControlsProps) {
  const [isSkillOpen, setIsSkillOpen] = React.useState(false);
  const skillDropdownRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (skillDropdownRef.current && !skillDropdownRef.current.contains(e.target as Node)) {
        setIsSkillOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const toggleSkill = (id: string) => {
    if (selectedSkillIds.includes(id)) {
      setSelectedSkillIds(selectedSkillIds.filter((sId) => sId !== id));
    } else {
      setSelectedSkillIds([...selectedSkillIds, id]);
    }
  };

  const isEditMode = Boolean(editingPost);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-xs flex flex-col gap-4 sm:gap-5">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          {isEditMode ? (
            <Edit3 className="h-4 w-4 text-[#2B8385]" />
          ) : (
            <FileText className="h-4 w-4 text-brand-teal" />
          )}
          <h2 className="text-xs font-bold uppercase tracking-wider text-brand-charcoal">
            {isEditMode ? "Modo de edición" : "Parámetros de publicación"}
          </h2>
        </div>
        {isEditMode ? (
          onCancelEdit && (
            <button
              type="button"
              onClick={onCancelEdit}
              className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 transition-colors cursor-pointer"
              title="Salir del modo edición y redactar nuevo post"
            >
              <X className="h-3.5 w-3.5" />
              <span>Nuevo post</span>
            </button>
          )
        ) : (
          <div className="flex items-center gap-2">
            {(promptQuery.trim() || linkUrl.trim()) && onResetStudio && (
              <button
                type="button"
                onClick={onResetStudio}
                className="flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-600 border border-slate-200 transition-colors cursor-pointer"
                title="Limpiar campos y volver al estado inicial"
              >
                <RotateCcw className="h-3 w-3 text-slate-500" />
                <span>Limpiar</span>
              </button>
            )}
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/80">
              Paso 1: Parámetros
            </span>
          </div>
        )}
      </div>

      {isEditMode ? (
        <>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-bold text-slate-700 flex items-center justify-between">
              <span>Publicación original</span>
              <span className="text-[10px] text-slate-400 font-mono">
                {editingPost.content?.length || 0} caracteres
              </span>
            </label>
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 max-h-28 overflow-y-auto leading-relaxed whitespace-pre-wrap">
              {editingPost.content}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="edit-instruction" className="text-xs font-bold text-slate-700 flex items-center justify-between">
              <span>Instrucciones para la IA</span>
              <span className="text-[10px] text-slate-400 font-mono">
                {editInstruction?.length || 0} caracteres
              </span>
            </label>
            <textarea
              id="edit-instruction"
              value={editInstruction || ""}
              onChange={(e) => setEditInstruction && setEditInstruction(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !isGenerating && editInstruction?.trim()) {
                  e.preventDefault();
                  onGenerate();
                }
              }}
              disabled={isGenerating}
              rows={3}
              placeholder="Indica los cambios que debe aplicar el agente de edición..."
              className="w-full text-xs p-3 rounded-lg border border-slate-200 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#2B8385] focus:border-[#2B8385] transition-all resize-none leading-relaxed shadow-2xs"
            />
          </div>
        </>
      ) : (
        <div className="flex flex-col gap-1.5">
          <label htmlFor="prompt-query" className="text-xs font-bold text-slate-700">
            Tema o idea principal
          </label>
          <div className="relative">
            <textarea
              id="prompt-query"
              value={promptQuery}
              onChange={(e) => setPromptQuery(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !isGenerating && promptQuery.trim()) {
                  e.preventDefault();
                  onGenerate();
                }
              }}
              disabled={isGenerating}
              rows={4}
              placeholder="Describe el anuncio, reflexión o noticia que deseas comunicar (ej: Lanzamiento del nuevo producto financiero sostenible para pymes)..."
              className="w-full text-xs sm:text-sm 2xl:text-base p-3 2xl:p-4 rounded-xl border border-slate-200 bg-slate-50/50 text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-teal focus:border-brand-teal transition-all resize-y min-h-[110px] xl:min-h-[130px] 2xl:min-h-[160px] max-h-56 2xl:max-h-72 leading-relaxed"
            />
            {promptQuery && (
              <button
                onClick={() => setPromptQuery("")}
                className="absolute right-2.5 top-2.5 p-1 text-slate-400 hover:text-slate-600 rounded-md transition-colors"
                title="Borrar texto"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400 px-0.5">
            <span>Sé específico para que el motor RAG contraste mejor tus datos</span>
            <div className="flex items-center gap-2">
              <span className="hidden sm:inline-block font-mono bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded text-[0.6875rem] 2xl:text-xs">⌘ + Enter</span>
              <span>{promptQuery.length} caracteres</span>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-1.5 relative" ref={skillDropdownRef}>
        <label className="text-xs font-bold text-slate-700 flex items-center justify-between">
          <span>Habilidades y directivas activas</span>
          <span className="text-[10px] font-normal text-slate-400">
            {selectedSkillIds.length} seleccionada{selectedSkillIds.length === 1 ? "" : "s"}
          </span>
        </label>
        <button
          type="button"
          onClick={() => setIsSkillOpen(!isSkillOpen)}
          disabled={isGenerating}
          className="flex items-center justify-between px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-left text-slate-700 hover:bg-slate-100/70 transition-colors cursor-pointer"
        >
          <span className="truncate">
            {selectedSkillIds.length === 0
              ? "Seleccionar habilidades aplicables..."
              : `${selectedSkillIds.length} directivas aplicadas al pipeline`}
          </span>
          <ChevronDown className="h-3.5 w-3.5 text-slate-400 shrink-0" />
        </button>

        {isSkillOpen && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-xl border border-slate-200 shadow-lg p-2 z-30 flex flex-col gap-1 max-h-48 overflow-y-auto">
            {skills.length === 0 ? (
              <span className="text-xs text-slate-400 italic p-2 text-center">
                No hay habilidades registradas en este espacio.
              </span>
            ) : (
              skills.map((skill) => {
                const isChecked = selectedSkillIds.includes(skill.id);
                return (
                  <button
                    key={skill.id}
                    type="button"
                    onClick={() => toggleSkill(skill.id)}
                    className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs text-left transition-colors cursor-pointer ${
                      isChecked ? "bg-brand-teal-light text-brand-teal font-semibold" : "hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    <span className="truncate">{cleanSkillName(skill.name)}</span>
                    {isChecked && <Check className="h-3.5 w-3.5 text-brand-teal shrink-0 ml-2" />}
                  </button>
                );
              })
            )}
          </div>
        )}

        {/* Active skill chips */}
        {selectedSkillIds.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1 max-h-24 overflow-y-auto custom-scroll">
            {skills
              .filter((s) => selectedSkillIds.includes(s.id))
              .map((skill) => {
                const isBase = skill.name.includes("Guía de Estilo y Generación") || skill.name.toLowerCase().includes("(base)");
                return (
                  <span
                    key={skill.id}
                    className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md border ${
                      isBase
                        ? "bg-brand-teal-light text-brand-teal border-brand-teal-border font-semibold"
                        : "bg-slate-50 text-slate-700 border-slate-200"
                    }`}
                  >
                    {isBase && <ShieldCheck className="h-3 w-3 text-brand-teal shrink-0" />}
                    <span className="font-semibold">{cleanSkillName(skill.name)}</span>
                    <button
                      type="button"
                      onClick={() => toggleSkill(skill.id)}
                      className="text-slate-400 hover:text-slate-600 ml-1 cursor-pointer"
                      title={isBase ? "Desactivar directiva" : "Quitar directiva"}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                );
              })}
          </div>
        )}
      </div>

      {/* Reference URL input (optional) */}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="link-url" className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
          <LinkIcon className="h-3 w-3 text-slate-400" />
          <span>Fuente externa o enlace de referencia</span>
          <span className="text-[10px] font-normal text-slate-400">(Opcional)</span>
        </label>
        <input
          id="link-url"
          type="url"
          value={linkUrl}
          onChange={(e) => setLinkUrl(e.target.value)}
          disabled={isGenerating}
          placeholder="https://empresa.com/articulo-o-comunicado"
          className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 bg-slate-50/50 text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-teal focus:border-brand-teal transition-all"
        />
      </div>

      <div className="pt-2 flex flex-col gap-2">
        {isGenerating ? (
          <button
            type="button"
            onClick={onStop}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-xs font-bold transition-colors cursor-pointer"
          >
            <StopCircle className="h-4 w-4 text-rose-600" />
            <span>Detener ejecución</span>
          </button>
        ) : isEditMode ? (
          <div className="flex flex-col gap-2 w-full">
            <button
              type="button"
              onClick={() => onGenerate()}
              disabled={!editInstruction?.trim()}
              className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold transition-all ${
                !editInstruction?.trim()
                  ? "bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed shadow-none"
                  : "bg-[#2B8385] hover:bg-[#1E6062] text-white shadow-xs cursor-pointer"
              }`}
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Reaplicar mejoras con IA</span>
            </button>
            {onCancelEdit && (
              <button
                type="button"
                onClick={onCancelEdit}
                className="w-full flex items-center justify-center gap-2 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
                <span>Salir de edición y redactar nuevo post</span>
              </button>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => onGenerate()}
            disabled={!promptQuery.trim()}
            className={`w-full flex items-center justify-center gap-2 py-2.5 2xl:py-3.5 rounded-lg 2xl:rounded-xl text-xs sm:text-sm 2xl:text-base font-bold transition-all ${
              !promptQuery.trim()
                ? "bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed shadow-none"
                : "bg-brand-teal hover:bg-brand-teal-dark text-white shadow-xs cursor-pointer"
            }`}
          >
            <span>Redactar publicación</span>
            <kbd
              className={`hidden sm:inline-block text-[0.6875rem] 2xl:text-xs font-mono px-1.5 py-0.5 rounded ${
                !promptQuery.trim()
                  ? "bg-slate-200/80 text-slate-400 border border-slate-300/60"
                  : "bg-white/20 text-white/90"
              }`}
            >
              ⌘ ↵
            </kbd>
            <ArrowRight className="h-3.5 w-3.5 2xl:h-4 2xl:w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
