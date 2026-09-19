"use client";

import React from "react";
import {
  SlidersHorizontal,
  Plus,
  Trash2,
  Save,
  FileCode,
  Layers,
} from "lucide-react";

interface SkillItem {
  id: string;
  name: string;
  description?: string;
  markdown_content?: string;
}

interface SkillsViewProps {
  skills: SkillItem[];
  activeWorkspaceSkill: SkillItem | null;
  setActiveWorkspaceSkill: (skill: SkillItem | null) => void;
  workspaceSkillName: string;
  setWorkspaceSkillName: (val: string) => void;
  workspaceSkillDesc: string;
  setWorkspaceSkillDesc: (val: string) => void;
  workspaceSkillMarkdown: string;
  setWorkspaceSkillMarkdown: (val: string) => void;
  handleCreateSkill: () => Promise<void>;
  handleUpdateSkill: (id: string, name: string, description: string, markdown: string) => Promise<void>;
  handleDeleteSkill: (id: string) => Promise<void>;
}

const cleanSkillName = (name: string) => (name || "").replace(/\s*\((?:Base|BASE)\)/gi, "").trim();

export default function SkillsView({
  skills,
  activeWorkspaceSkill,
  setActiveWorkspaceSkill,
  workspaceSkillName,
  setWorkspaceSkillName,
  workspaceSkillDesc,
  setWorkspaceSkillDesc,
  workspaceSkillMarkdown,
  setWorkspaceSkillMarkdown,
  handleCreateSkill,
  handleUpdateSkill,
  handleDeleteSkill,
}: SkillsViewProps) {
  const isBaseSkill =
    Boolean(activeWorkspaceSkill && (activeWorkspaceSkill.name.includes("Guía de Estilo y Generación") || activeWorkspaceSkill.name.toLowerCase().includes("(base)")));

  const handleSelectSkill = (skill: SkillItem) => {
    setActiveWorkspaceSkill(skill);
    setWorkspaceSkillName(cleanSkillName(skill.name));
    setWorkspaceSkillDesc(skill.description || "");
    setWorkspaceSkillMarkdown(skill.markdown_content || "");
  };

  const handleNewSkillClick = () => {
    setActiveWorkspaceSkill(null);
    setWorkspaceSkillName("");
    setWorkspaceSkillDesc("");
    setWorkspaceSkillMarkdown("");
  };

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col gap-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <FileCode className="h-4 w-4 text-brand-teal" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-brand-charcoal">
                {activeWorkspaceSkill ? `Editando: ${cleanSkillName(activeWorkspaceSkill.name)}` : "Nueva habilidad"}
              </h2>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            {/* Skill Name */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-bold text-slate-700">Nombre de la habilidad</label>
              <input
                type="text"
                value={workspaceSkillName}
                onChange={(e) => setWorkspaceSkillName(e.target.value)}
                disabled={isBaseSkill}
                placeholder="Ej: Storytelling para casos de éxito"
                className="text-xs px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-teal disabled:opacity-60"
              />
            </div>

            {/* Description */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-bold text-slate-700">Descripción funcional</label>
              <input
                type="text"
                value={workspaceSkillDesc}
                onChange={(e) => setWorkspaceSkillDesc(e.target.value)}
                disabled={isBaseSkill}
                placeholder="Para qué contexto se debe activar esta habilidad..."
                className="text-xs px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-teal disabled:opacity-60"
              />
            </div>

            {/* Guidelines & Examples */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-700">Instrucciones y ejemplos</label>
              </div>
              <textarea
                value={workspaceSkillMarkdown}
                onChange={(e) => setWorkspaceSkillMarkdown(e.target.value)}
                rows={12}
                placeholder="Escribe aquí las directrices para el redactor, ejemplos de ganchos de apertura (hooks), formato de listas y tono..."
                className="text-xs p-3.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-teal font-mono leading-relaxed resize-y"
              />
            </div>

            {/* Actions Bar */}
            <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
              {activeWorkspaceSkill && !isBaseSkill ? (
                <button
                  onClick={async () => {
                    if (confirm("¿Estás seguro de que deseas eliminar esta habilidad?")) {
                      await handleDeleteSkill(activeWorkspaceSkill.id);
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-rose-600 hover:bg-rose-50 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Eliminar habilidad</span>
                </button>
              ) : (
                <div />
              )}

              <button
                onClick={async () => {
                  if (activeWorkspaceSkill) {
                    await handleUpdateSkill(
                      activeWorkspaceSkill.id,
                      workspaceSkillName,
                      workspaceSkillDesc,
                      workspaceSkillMarkdown
                    );
                  } else {
                    await handleCreateSkill();
                  }
                }}
                disabled={!workspaceSkillName.trim() || !workspaceSkillMarkdown.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-[#2B8385] hover:bg-[#1E6062] text-white rounded-lg text-xs font-bold shadow-xs transition-colors cursor-pointer disabled:opacity-40"
              >
                <Save className="h-3.5 w-3.5" />
                <span>{activeWorkspaceSkill ? "Guardar cambios" : "Crear habilidad"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Skills List (4 cols) */}
        <div className="lg:col-span-4 bg-white rounded-xl border border-slate-300/80 p-5 shadow-xs flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-[#2B8385]" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#383132]">
                Habilidades disponibles ({skills.length})
              </h2>
            </div>
            <button
              onClick={handleNewSkillClick}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2B8385] hover:bg-[#1E6062] text-white rounded-lg text-xs font-bold shadow-xs transition-colors cursor-pointer"
              title="Crear nueva habilidad"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Nueva habilidad</span>
            </button>
          </div>

          <div className="flex flex-col gap-2 max-h-[500px] overflow-y-auto pr-1">
            {skills.map((skill) => {
              const isSelected = activeWorkspaceSkill?.id === skill.id;
              return (
                <button
                  key={skill.id}
                  onClick={() => handleSelectSkill(skill)}
                  className={`flex flex-col p-3 rounded-lg border text-left transition-all cursor-pointer ${
                    isSelected
                      ? "bg-[#EAF4F5] border-[#2B8385] text-[#1E6062] shadow-2xs"
                      : "bg-[#F5F7F8] hover:bg-[#EDEFF1] border-slate-200/90 text-slate-800"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold truncate">{cleanSkillName(skill.name)}</span>
                  </div>
                  {skill.description && (
                    <p className="text-[11px] text-slate-500 line-clamp-2 mt-1 leading-normal">
                      {skill.description}
                    </p>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
