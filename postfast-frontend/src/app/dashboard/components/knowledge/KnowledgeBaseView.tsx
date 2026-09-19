"use client";

import React, { useState } from "react";
import {
  Database,
  FileText,
  Upload,
  Link as LinkIcon,
  Trash2,
  Eye,
  RefreshCw,
  Plus,
  Check,
  X,
  Search,
  Building,
  Tag,
  ShieldCheck,
  ExternalLink,
  Save,
  Sparkles,
} from "lucide-react";
import type { CompanyAccount } from "../layout/AppHeader";

interface KnowledgeBaseViewProps {
  selectedCompany: CompanyAccount | null;
  ragContent: any;
  isLoadingRag: boolean;
  pdfDocuments: any[];
  isUploadingPdf: boolean;
  onUploadPdf: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onDeleteDocument: (filename: string) => void;
  ragUrls: any[];
  urlToAdd: string;
  setUrlToAdd: (url: string) => void;
  isIngestingUrl: boolean;
  onAddUrl: () => void;
  onDeleteUrl: (url: string) => void;
  localDos: string[];
  setLocalDos: (dos: string[]) => void;
  localDonts: string[];
  setLocalDonts: (donts: string[]) => void;
  isSavingBrandAssets: boolean;
  onSaveBrandAssets: () => void;
  localAboutUs: string;
  setLocalAboutUs: (val: string) => void;
  localSpecialties: string[];
  setLocalSpecialties: (val: string[]) => void;
  onViewDocContent: (docName: string) => void;
  onTriggerSync: () => void;
  isSyncingCompany: boolean;
}

/** Limpia texto de asteriscos, guiones y prefijos de etiqueta */
function cleanDirectiveText(raw: string): string {
  if (!raw) return "";
  let text = raw.trim();
  // Elimina viñetas iniciales como - * • y números tipo 1.
  text = text.replace(/^[-*•\d.)\s]+/, "");
  // Elimina prefijos repetitivos como **Do's:**, **Don'ts:**, Do's:, Don'ts:, etc.
  text = text.replace(/^(?:\*{1,2})?(?:do'?s|dont'?s|don'ts|qué hacer|qué evitar|qué no hacer):\s*(?:\*{1,2})?/i, "");
  // Elimina cualquier asterisco restante
  text = text.replace(/\*{1,2}/g, "");
  // Normaliza espacios
  return text.replace(/\s+/g, " ").trim();
}

export default function KnowledgeBaseView({
  selectedCompany,
  ragContent,
  isLoadingRag,
  pdfDocuments,
  isUploadingPdf,
  onUploadPdf,
  onDeleteDocument,
  ragUrls,
  urlToAdd,
  setUrlToAdd,
  isIngestingUrl,
  onAddUrl,
  onDeleteUrl,
  localDos,
  setLocalDos,
  localDonts,
  setLocalDonts,
  isSavingBrandAssets,
  onSaveBrandAssets,
  localAboutUs,
  setLocalAboutUs,
  localSpecialties,
  setLocalSpecialties,
  onViewDocContent,
  onTriggerSync,
  isSyncingCompany,
}: KnowledgeBaseViewProps) {
  const [newDo, setNewDo] = useState("");
  const [newDont, setNewDont] = useState("");
  const [newSpecialty, setNewSpecialty] = useState("");
  const [searchDocQuery, setSearchDocQuery] = useState("");

  const filteredDocs = pdfDocuments.filter((d) =>
    (d.filename || d.name || d.document_name || "").toLowerCase().includes(searchDocQuery.toLowerCase())
  );

  const totalRules = localDos.length + localDonts.length;

  const handleAddDo = () => {
    const cleaned = cleanDirectiveText(newDo);
    if (cleaned && !localDos.map(cleanDirectiveText).includes(cleaned)) {
      setLocalDos([...localDos, cleaned]);
      setNewDo("");
    }
  };

  const handleAddDont = () => {
    const cleaned = cleanDirectiveText(newDont);
    if (cleaned && !localDonts.map(cleanDirectiveText).includes(cleaned)) {
      setLocalDonts([...localDonts, cleaned]);
      setNewDont("");
    }
  };

  const handleAddSpecialty = () => {
    const trimmed = newSpecialty.trim();
    if (trimmed && !localSpecialties.includes(trimmed)) {
      setLocalSpecialties([...localSpecialties, trimmed]);
      setNewSpecialty("");
    }
  };

  return (
    <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6">
      <div className="bg-white rounded-xl border border-slate-300/80 shadow-xs overflow-hidden">
        <div className="px-6 py-3.5 border-b border-[#473E3F] bg-[#383132] text-white flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#2B8385]/20 border border-[#2B8385]/40 flex items-center justify-center text-[#3FA5A7] shadow-2xs">
              <Building className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-white">
                  {selectedCompany?.name || "Empresa seleccionada"}
                </span>
              </div>
              <span className="text-[11px] text-slate-300 font-mono">
                {selectedCompany?.urn || "Cuenta corporativa activa"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 self-start sm:self-auto flex-wrap">
            <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-300">
              <Sparkles className="h-3.5 w-3.5 text-[#3FA5A7]" />
              <span>Contexto principal de redacción autónoma</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onTriggerSync}
                disabled={isSyncingCompany}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/15 text-white border border-white/20 rounded-lg text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
                title="Sincronizar y recalcular embeddings vectoriales"
              >
                <RefreshCw className={`h-3.5 w-3.5 text-slate-300 ${isSyncingCompany ? "animate-spin" : ""}`} />
                <span>{isSyncingCompany ? "Sincronizando..." : "Sincronizar RAG"}</span>
              </button>
              <button
                onClick={onSaveBrandAssets}
                disabled={isSavingBrandAssets}
                className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#2B8385] hover:bg-[#1E6062] text-white rounded-lg text-xs font-bold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                title="Guardar información general, especialidades y directivas de la empresa"
              >
                <Save className="h-3.5 w-3.5" />
                <span>{isSavingBrandAssets ? "Guardando..." : "Guardar información"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Contenido del perfil de empresa: Descripción (About Us) y Especialidades con fondo cálido */}
        <div className="p-6 bg-[#FAF9F8] grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Descripción corporativa (8 columnas) */}
          <div className="lg:col-span-8 flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-[#383132] flex items-center gap-1.5">
                <span>Descripción corporativa e identidad de marca</span>
              </label>
              <span className="text-[11px] text-slate-500 font-mono">
                {localAboutUs.length} caracteres
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-normal">
              Información de posicionamiento, misión, actividad principal y propuesta de valor. Los redactores autónomos inyectan esta descripción para alinear cada publicación con la voz y el conocimiento institucional.
            </p>
            <textarea
              value={localAboutUs}
              onChange={(e) => setLocalAboutUs(e.target.value)}
              rows={6}
              placeholder="Describe aquí la actividad de la organización, sectores donde opera, propuesta de valor, misión y visión estratégica..."
              className="w-full text-xs p-3.5 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-[#2B8385] focus:border-[#2B8385] resize-y leading-relaxed shadow-2xs"
            />
            <div className="flex items-center justify-between text-[11px] text-slate-500">
              <span>Al pulsar "Guardar información", este texto se indexa como vector prioritario en la base de conocimiento</span>
            </div>
          </div>

          {/* Especialidades y pilares temáticos (4 columnas) */}
          <div className="lg:col-span-4 flex flex-col gap-2.5 border-t lg:border-t-0 lg:border-l border-slate-200 lg:pl-6 pt-4 lg:pt-0">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-[#383132] flex items-center gap-1.5">
                <Tag className="h-3.5 w-3.5 text-[#2B8385]" />
                <span>Especialidades y pilares temáticos</span>
              </label>
              <span className="text-[10px] text-slate-500 font-mono">
                {localSpecialties.length} etiqueta{localSpecialties.length === 1 ? "" : "s"}
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-normal">
              Áreas clave de conocimiento que guían la elección de temáticas y hashtags estratégicos en LinkedIn.
            </p>

            {/* Chips de especialidades */}
            <div className="flex flex-wrap gap-1.5 min-h-[85px] max-h-[145px] overflow-y-auto p-2.5 bg-[#EDE9E8] rounded-lg border border-[#DDD7D6] content-start">
              {localSpecialties.length === 0 ? (
                <span className="text-xs text-slate-500 italic py-2 px-1">
                  Sin especialidades registradas. Añade pilares como "Banca digital", "Sostenibilidad", "Ciberseguridad", etc.
                </span>
              ) : (
                localSpecialties.map((spec, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-md bg-white text-[#383132] border border-[#CDC6C5] shadow-2xs hover:border-[#2B8385] transition-colors"
                  >
                    <span>{spec}</span>
                    <button
                      type="button"
                      onClick={() => setLocalSpecialties(localSpecialties.filter((_, i) => i !== idx))}
                      className="text-slate-400 hover:text-rose-600 transition-colors ml-0.5 cursor-pointer"
                      title="Eliminar especialidad"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))
              )}
            </div>

            {/* Input para añadir especialidad */}
            <div className="flex items-center gap-1.5 mt-auto pt-1">
              <input
                type="text"
                value={newSpecialty}
                onChange={(e) => setNewSpecialty(e.target.value)}
                placeholder="Añadir pilar temático..."
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddSpecialty();
                  }
                }}
                className="flex-1 text-xs px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-[#2B8385] focus:border-[#2B8385]"
              />
              <button
                type="button"
                onClick={handleAddSpecialty}
                disabled={!newSpecialty.trim()}
                className="p-1.5 bg-[#2B8385] text-white rounded-lg hover:bg-[#1E6062] transition-colors cursor-pointer disabled:opacity-40"
                title="Añadir pilar"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Métricas y resumen de estado RAG con acentos de color corporativos */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-[#2B8385] p-4 shadow-xs flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Documentos PDF</span>
            <p className="text-xl font-extrabold text-[#1E6062] mt-0.5">{pdfDocuments.length}</p>
          </div>
          <div className="w-9 h-9 rounded-lg bg-[#EAF4F5] border border-[#BCDDE0] flex items-center justify-center text-[#2B8385]">
            <FileText className="h-4.5 w-4.5" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-[#473E3F] p-4 shadow-xs flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Enlaces web</span>
            <p className="text-xl font-extrabold text-[#383132] mt-0.5">{ragUrls.length}</p>
          </div>
          <div className="w-9 h-9 rounded-lg bg-[#F4EFEF] border border-[#E0D7D7] flex items-center justify-center text-[#473E3F]">
            <LinkIcon className="h-4.5 w-4.5" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-[#2B8385] p-4 shadow-xs flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Directivas de estilo</span>
            <p className="text-xl font-extrabold text-[#1E6062] mt-0.5">{totalRules}</p>
          </div>
          <div className="w-9 h-9 rounded-lg bg-[#EAF4F5] border border-[#BCDDE0] flex items-center justify-center text-[#2B8385]">
            <ShieldCheck className="h-4.5 w-4.5" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-[#473E3F] p-4 shadow-xs flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Pilares temáticos</span>
            <p className="text-xl font-extrabold text-[#383132] mt-0.5">{localSpecialties.length}</p>
          </div>
          <div className="w-9 h-9 rounded-lg bg-[#F4EFEF] border border-[#E0D7D7] flex items-center justify-center text-[#473E3F]">
            <Tag className="h-4.5 w-4.5" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Columna izquierda: Directivas de estilo y voz de marca (5 columnas) */}
        <div className="lg:col-span-5 flex flex-col gap-5">
          <div className="bg-white rounded-xl border border-slate-300/80 p-5 shadow-xs flex flex-col gap-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[#F4EFEF] text-[#473E3F] border border-[#E0D7D7] flex items-center justify-center">
                  <ShieldCheck className="h-4 w-4" />
                </div>
                <div className="flex flex-col">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-[#383132]">
                    Directivas de estilo y voz de marca
                  </h2>
                  <span className="text-[11px] text-slate-500 mt-0.5">
                    Reglas operativas de conducta y estilo para los redactores autónomos
                  </span>
                </div>
              </div>
            </div>

            {/* Bloque: Pautas recomendadas (Do's) */}
            <div className="flex flex-col gap-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#2B8385]" />
                  <span>Pautas recomendadas (Do's)</span>
                </span>
                <span className="text-[10px] text-slate-500 font-mono font-medium">
                  {localDos.length} pauta{localDos.length === 1 ? "" : "s"}
                </span>
              </div>

              <div className="flex flex-col gap-1.5 max-h-56 overflow-y-auto pr-1">
                {localDos.length === 0 ? (
                  <div className="p-3 bg-[#F4F6F8] rounded-lg border border-slate-200 text-xs text-slate-400 italic text-center">
                    No hay pautas registradas. Añade directivas de estilo positivas.
                  </div>
                ) : (
                  localDos.map((rawItem, idx) => {
                    const item = cleanDirectiveText(rawItem);
                    if (!item) return null;
                    return (
                      <div
                        key={idx}
                        className="group flex items-start justify-between p-2.5 rounded-lg bg-[#F1F8F8] border border-[#CDE6E7] hover:border-[#2B8385] hover:bg-white hover:shadow-2xs transition-all gap-2.5"
                      >
                        <div className="w-5 h-5 rounded-md bg-[#2B8385]/15 text-[#2B8385] border border-[#2B8385]/30 flex items-center justify-center shrink-0 mt-0.5">
                          <Check className="h-3 w-3" />
                        </div>
                        <span className="text-xs text-slate-800 font-medium leading-relaxed flex-1">
                          {item}
                        </span>
                        <button
                          onClick={() => setLocalDos(localDos.filter((_, i) => i !== idx))}
                          className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-600 transition-opacity p-0.5 cursor-pointer shrink-0"
                          title="Eliminar pauta"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Input para añadir Do */}
              <div className="flex items-center gap-1.5 mt-1">
                <input
                  type="text"
                  value={newDo}
                  onChange={(e) => setNewDo(e.target.value)}
                  placeholder="Ej: Mantener párrafos breves y centrarse en valor real..."
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddDo();
                    }
                  }}
                  className="flex-1 text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-[#2B8385] focus:border-[#2B8385]"
                />
                <button
                  type="button"
                  onClick={handleAddDo}
                  disabled={!newDo.trim()}
                  className="p-2 bg-[#2B8385] text-white rounded-lg hover:bg-[#1E6062] transition-colors cursor-pointer disabled:opacity-40"
                  title="Añadir pauta"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {/* Bloque: Restricciones y qué evitar (Don'ts) */}
            <div className="flex flex-col gap-2.5 pt-4 border-t border-slate-200">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#473E3F]" />
                  <span>Restricciones y qué evitar (Don'ts)</span>
                </span>
                <span className="text-[10px] text-slate-500 font-mono font-medium">
                  {localDonts.length} restricci{localDonts.length === 1 ? "ón" : "ones"}
                </span>
              </div>

              <div className="flex flex-col gap-1.5 max-h-56 overflow-y-auto pr-1">
                {localDonts.length === 0 ? (
                  <div className="p-3 bg-[#F4F6F8] rounded-lg border border-slate-200 text-xs text-slate-400 italic text-center">
                    No hay restricciones registradas. Añade límites o elementos prohibidos.
                  </div>
                ) : (
                  localDonts.map((rawItem, idx) => {
                    const item = cleanDirectiveText(rawItem);
                    if (!item) return null;
                    return (
                      <div
                        key={idx}
                        className="group flex items-start justify-between p-2.5 rounded-lg bg-[#F7F4F4] border border-[#E6DCDC] hover:border-[#473E3F] hover:bg-white hover:shadow-2xs transition-all gap-2.5"
                      >
                        <div className="w-5 h-5 rounded-md bg-[#473E3F]/15 text-[#473E3F] border border-[#473E3F]/30 flex items-center justify-center shrink-0 mt-0.5">
                          <X className="h-3 w-3" />
                        </div>
                        <span className="text-xs text-slate-800 font-medium leading-relaxed flex-1">
                          {item}
                        </span>
                        <button
                          onClick={() => setLocalDonts(localDonts.filter((_, i) => i !== idx))}
                          className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-600 transition-opacity p-0.5 cursor-pointer shrink-0"
                          title="Eliminar restricción"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Input para añadir Don't */}
              <div className="flex items-center gap-1.5 mt-1">
                <input
                  type="text"
                  value={newDont}
                  onChange={(e) => setNewDont(e.target.value)}
                  placeholder="Ej: No citar clientes sin autorización ni inventar métricas..."
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddDont();
                    }
                  }}
                  className="flex-1 text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-[#473E3F] focus:border-[#473E3F]"
                />
                <button
                  type="button"
                  onClick={handleAddDont}
                  disabled={!newDont.trim()}
                  className="p-2 bg-[#473E3F] text-white rounded-lg hover:bg-[#342D2E] transition-colors cursor-pointer disabled:opacity-40"
                  title="Añadir restricción"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Columna derecha: Repositorio documental y fuentes RAG (7 columnas) */}
        <div className="lg:col-span-7 flex flex-col gap-5">
          {/* Card 1: Repositorio documental (PDF) */}
          <div className="bg-white rounded-xl border border-slate-300/80 p-5 shadow-xs flex flex-col gap-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-[#2B8385]" />
                <div>
                  <h2 className="text-xs font-bold uppercase tracking-wider text-[#383132]">
                    Repositorio documental ({pdfDocuments.length})
                  </h2>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Documentos e informes oficiales para la contrastación factual
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <div className="relative w-full sm:w-56">
                  <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                  <input
                    type="text"
                    value={searchDocQuery}
                    onChange={(e) => setSearchDocQuery(e.target.value)}
                    placeholder="Buscar por nombre..."
                    className="w-full text-xs pl-8 pr-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-[#2B8385] focus:border-[#2B8385]"
                  />
                </div>

                <label className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2B8385] hover:bg-[#1E6062] text-white rounded-lg text-xs font-bold transition-colors cursor-pointer shadow-2xs shrink-0">
                  <Upload className="h-3.5 w-3.5" />
                  <span>{isUploadingPdf ? "Subiendo..." : "Subir PDF"}</span>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={onUploadPdf}
                    disabled={isUploadingPdf}
                    className="hidden"
                  />
                </label>
              </div>
            </div>

            {/* Zona drag and drop discreta con tono turquesa suave */}
            <label className="border border-dashed border-[#92C4C6] rounded-lg p-3.5 flex items-center justify-center gap-2 bg-[#F0F7F7] hover:bg-[#E2EFF0] transition-all cursor-pointer group">
              <Upload className="h-4 w-4 text-[#2B8385] transition-colors" />
              <span className="text-xs font-semibold text-[#1E6062] transition-colors">
                {isUploadingPdf ? "Procesando e indexando documento PDF..." : "Haz clic para subir un nuevo documento PDF al índice RAG"}
              </span>
              <input
                type="file"
                accept=".pdf"
                onChange={onUploadPdf}
                disabled={isUploadingPdf}
                className="hidden"
              />
            </label>

            {/* Tabla de documentos */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-[#ECEEF0] text-[10px] font-bold uppercase tracking-wider text-[#383132] border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-3">Documento</th>
                    <th className="py-2.5 px-3">Fecha de indexación</th>
                    <th className="py-2.5 px-3">Estado RAG</th>
                    <th className="py-2.5 px-3 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredDocs.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-slate-400 italic text-xs">
                        {searchDocQuery.trim()
                          ? "No se encontraron documentos que coincidan con la búsqueda."
                          : "No hay documentos subidos en este espacio. Sube un PDF para alimentar la verificación factual."}
                      </td>
                    </tr>
                  ) : (
                    filteredDocs.map((doc, idx) => {
                      const docFilename = doc.filename || doc.name || doc.document_name || `Documento ${idx + 1}`;
                      const formattedDate = doc.created_at
                        ? new Date(doc.created_at).toLocaleDateString("es-ES", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                          })
                        : "—";
                      return (
                        <tr key={docFilename + idx} className="hover:bg-slate-50/80 transition-colors">
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-2.5 min-w-0">
                              <FileText className="h-4 w-4 text-rose-600 shrink-0" />
                              <span className="font-semibold text-slate-900 truncate max-w-xs" title={docFilename}>
                                {docFilename}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-3 text-slate-500 font-mono text-[11px] whitespace-nowrap">
                            {formattedDate}
                          </td>
                          <td className="py-3 px-3">
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <Check className="h-2.5 w-2.5" />
                              <span>Indexado</span>
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => onViewDocContent(docFilename)}
                                className="p-1.5 text-slate-500 hover:text-[#2B8385] hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
                                title="Ver fragmentos del documento"
                              >
                                <Eye className="h-3.5 w-3.5" />
                              </button>
                              <button
                                onClick={() => onDeleteDocument(docFilename)}
                                className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
                                title="Eliminar documento de la base vectorial"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Card 2: Enlaces web y fuentes externas (URLs) */}
          <div className="bg-white rounded-xl border border-slate-300/80 p-5 shadow-xs flex flex-col gap-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <LinkIcon className="h-4 w-4 text-[#2B8385]" />
                <div>
                  <h2 className="text-xs font-bold uppercase tracking-wider text-[#383132]">
                    Enlaces web y fuentes externas ({ragUrls.length})
                  </h2>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Páginas web y comunicados para contraste de fuentes
                  </p>
                </div>
              </div>
            </div>

            {/* Formulario de ingesta de URL */}
            <div className="flex items-center gap-2">
              <input
                type="url"
                value={urlToAdd}
                onChange={(e) => setUrlToAdd(e.target.value)}
                placeholder="https://empresa.com/noticias/comunicado-oficial..."
                onKeyDown={(e) => {
                  if (e.key === "Enter" && urlToAdd.trim() && !isIngestingUrl) {
                    e.preventDefault();
                    onAddUrl();
                  }
                }}
                className="flex-1 text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-[#2B8385] focus:border-[#2B8385]"
              />
              <button
                onClick={onAddUrl}
                disabled={isIngestingUrl || !urlToAdd.trim()}
                className="px-3.5 py-2 bg-[#2B8385] hover:bg-[#1E6062] text-white rounded-lg text-xs font-bold transition-colors cursor-pointer shadow-2xs disabled:opacity-40"
              >
                {isIngestingUrl ? "Indexando..." : "Indexar enlace"}
              </button>
            </div>

            {/* Lista de URLs */}
            <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto">
              {ragUrls.length === 0 ? (
                <span className="text-xs text-slate-400 italic py-3 text-center">
                  No hay enlaces web registrados en esta organización.
                </span>
              ) : (
                ragUrls.map((item: any, i: number) => {
                  const urlStr = typeof item === "string" ? item : item?.url || "";
                  return (
                    <div
                      key={i}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-[#F4F6F8] border border-slate-200/90 hover:border-slate-300 text-xs transition-colors"
                    >
                      <div className="flex items-center gap-2 min-w-0 pr-2">
                        <LinkIcon className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                        <span className="text-slate-700 truncate font-mono text-[11px]">{urlStr}</span>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <a
                          href={urlStr}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 text-slate-400 hover:text-[#2B8385] transition-colors"
                          title="Abrir enlace externo"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                        <button
                          onClick={() => onDeleteUrl(urlStr)}
                          className="text-slate-400 hover:text-rose-600 transition-colors p-1 cursor-pointer"
                          title="Eliminar enlace"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
