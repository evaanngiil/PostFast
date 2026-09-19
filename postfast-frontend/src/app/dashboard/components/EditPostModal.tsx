"use client";

import React, { useState, useEffect } from "react";
import { Edit3, X, Save, Sparkles, AlertCircle } from "lucide-react";
import type { CompanyAccount } from "./layout/AppHeader";

interface EditPostModalProps {
  isOpen: boolean;
  onClose: () => void;
  post: any;
  companies: CompanyAccount[];
  onSaveManual: (updatedContent: string) => Promise<void> | void;
  onUpdateWithAI: (updatedContent: string, instructions: string) => Promise<void> | void;
}

export default function EditPostModal({
  isOpen,
  onClose,
  post,
  companies,
  onSaveManual,
  onUpdateWithAI,
}: EditPostModalProps) {
  const [content, setContent] = useState("");
  const [instructions, setInstructions] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isImproving, setIsImproving] = useState(false);

  useEffect(() => {
    if (post) {
      setContent(post.content || "");
      setInstructions("");
    }
  }, [post]);

  if (!isOpen || !post) return null;

  const orgName =
    companies.find((c) => c.urn === post.account_id)?.name || post.account_id || "LinkedIn";

  const handleManualSave = async () => {
    if (!content.trim() || isSaving) return;
    setIsSaving(true);
    try {
      await onSaveManual(content);
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  const handleAIImprove = async () => {
    if (isImproving) return;
    setIsImproving(true);
    try {
      await onUpdateWithAI(content, instructions);
      onClose();
    } finally {
      setIsImproving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl overflow-hidden border border-slate-200 flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-[#383132] text-white">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#2B8385]/30 border border-[#2B8385]/50 flex items-center justify-center text-[#45B6B8]">
              <Edit3 className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-white">Editar publicación</h3>
              <p className="text-[11px] text-slate-300">
                Modifica el texto directamente o solicita mejoras asistidas por IA
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-md hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-6 flex flex-col gap-5 overflow-y-auto bg-slate-50/50 flex-1">
          <div className="flex items-center justify-between bg-white px-4 py-2.5 rounded-lg border border-slate-200 shadow-2xs">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Organización:
              </span>
              <span className="text-xs font-bold text-[#383132]">{orgName}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Estado:
              </span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
                  post.status === "published"
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : post.status === "scheduled"
                    ? "bg-blue-50 text-blue-700 border border-blue-200"
                    : "bg-amber-50 text-amber-700 border border-amber-200"
                }`}
              >
                {post.status === "published"
                  ? "Publicado"
                  : post.status === "scheduled"
                  ? "Programado"
                  : "Borrador"}
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-[#383132] flex items-center gap-1.5">
                <span>Contenido de la publicación</span>
              </label>
              <span className="text-[11px] font-mono text-slate-500">
                {content.length} caracteres | {content.trim().split(/\s+/).filter(Boolean).length} palabras
              </span>
            </div>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={8}
              placeholder="Escribe o modifica el texto de la publicación..."
              className="w-full text-xs font-sans p-3 rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#2B8385] focus:border-[#2B8385] leading-relaxed shadow-2xs resize-y"
            />
          </div>

          <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-2xs flex flex-col gap-2.5">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[#2B8385]" />
              <label className="text-xs font-bold text-[#383132]">
                Instrucciones para optimización con IA (opcional)
              </label>
            </div>
            <p className="text-[11px] text-slate-500 leading-normal">
              Si prefieres que los agentes reescriban o ajusten el post, introduce las directivas de mejora aquí.
            </p>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={2}
              placeholder="Ej: Haz la apertura más impactante, acorta el último párrafo y refuerza la llamada a la acción..."
              className="w-full text-xs p-2.5 rounded-lg border border-slate-200 bg-slate-50/50 text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#2B8385]"
            />
          </div>
        </div>

        <div className="px-6 py-4 border-t border-slate-200 bg-white flex flex-col sm:flex-row items-center justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            className="w-full sm:w-auto px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
          >
            Cancelar
          </button>
          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <button
              type="button"
              onClick={handleAIImprove}
              disabled={isImproving || !content.trim()}
              className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-[#383132] border border-slate-300 rounded-lg text-xs font-bold transition-colors cursor-pointer disabled:opacity-50"
            >
              <Sparkles className="h-3.5 w-3.5 text-[#2B8385]" />
              <span>{isImproving ? "Enviando a agentes..." : "Mejorar con IA"}</span>
            </button>
            <button
              type="button"
              onClick={handleManualSave}
              disabled={isSaving || !content.trim()}
              className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-4 py-2 bg-[#2B8385] hover:bg-[#1E6062] text-white rounded-lg text-xs font-bold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
            >
              <Save className="h-3.5 w-3.5" />
              <span>{isSaving ? "Guardando..." : "Guardar cambios"}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
