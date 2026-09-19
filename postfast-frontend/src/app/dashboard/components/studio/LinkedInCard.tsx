"use client";

import React, { useState } from "react";
import {
  Globe,
  MoreHorizontal,
  ThumbsUp,
  MessageSquare,
  Repeat2,
  Send,
  Edit2,
  Trash2,
  Calendar,
  Share2,
  Check,
  Copy,
  ExternalLink,
  Monitor,
  Smartphone,
  Bookmark,
} from "lucide-react";
import type { CompanyAccount, UserInfo } from "../layout/AppHeader";

interface LinkedInCardProps {
  content: string;
  hashtags: string[];
  cta?: string;
  selectedCompany: CompanyAccount | null;
  userInfo: UserInfo | null;
  onEdit?: () => void;
  onDelete?: () => void;
  onSaveDraft?: () => void;
  onSchedule?: () => void;
  onPublish?: () => void;
  isPublishing?: boolean;
  isEditMode?: boolean;
}

export default function LinkedInCard({
  content,
  hashtags,
  cta,
  selectedCompany,
  userInfo,
  onEdit,
  onDelete,
  onSaveDraft,
  onSchedule,
  onPublish,
  isPublishing,
  isEditMode,
}: LinkedInCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [avatarError, setAvatarError] = useState(false);
  const [previewDevice, setPreviewDevice] = useState<"desktop" | "mobile">("desktop");

  // Determine author display data
  const isPersonal = selectedCompany?.is_personal ?? true;
  const authorName = isPersonal
    ? userInfo?.name || selectedCompany?.name || "Usuario"
    : selectedCompany?.name || "Empresa";
  const authorSubtitle = isPersonal
    ? "Profesional en LinkedIn"
    : "Página de empresa oficial";
  const authorAvatar = isPersonal
    ? userInfo?.picture || selectedCompany?.logo_url
    : selectedCompany?.logo_url || userInfo?.picture;

  // Character calculations
  const fullText = [content, cta, hashtags.join(" ")].filter(Boolean).join("\n\n");
  const charCount = fullText.length;
  const isOptimalLength = charCount >= 500 && charCount <= 1300;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  // Dynamic truncation for LinkedIn "ver más" based on device preview
  const threshold = previewDevice === "desktop" ? 380 : 180;
  const needsTruncation = content.length > threshold;
  const displayedContent = needsTruncation && !isExpanded
    ? content.slice(0, threshold) + "..."
    : content;

  return (
    <div className="flex flex-col gap-3 w-full">
      {/* Device Preview Toggle Bar */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            Previsualización feed
          </span>
          {isEditMode && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300">
              Modo edición
            </span>
          )}
          <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">
            {previewDevice === "desktop" ? "Límite visual 3 líneas (~380 c.)" : "Límite móvil (~180 c.)"}
          </span>
        </div>

        <div className="flex items-center bg-slate-200/80 p-0.5 rounded-lg border border-slate-300">
          <button
            type="button"
            onClick={() => setPreviewDevice("desktop")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
              previewDevice === "desktop"
                ? "bg-[#2E2829] text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Monitor className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Escritorio</span>
          </button>
          <button
            type="button"
            onClick={() => setPreviewDevice("mobile")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
              previewDevice === "mobile"
                ? "bg-[#2E2829] text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Smartphone className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Móvil</span>
          </button>
        </div>
      </div>

      {/* Feed Canvas Viewport Wrapper */}
      <div className="bg-[#E4E7EB] p-3 sm:p-5 rounded-xl border border-slate-300/90 shadow-inner">
        {/* LinkedIn Post Card Container */}
        <article
          className={`bg-white rounded-xl border border-slate-300/80 shadow-[0_2px_12px_rgba(0,0,0,0.06)] overflow-hidden transition-all duration-200 ${
            previewDevice === "mobile" ? "max-w-[420px] mx-auto shadow-md" : "w-full"
          }`}
          aria-label="Previsualización de publicación en LinkedIn"
        >
        {/* Card Header: Author Profile */}
        <div className="p-4 pb-3 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            {authorAvatar && !avatarError ? (
              <img
                src={authorAvatar}
                alt={authorName}
                onError={() => setAvatarError(true)}
                className={`w-11 h-11 object-cover border border-slate-200 shrink-0 ${
                  isPersonal ? "rounded-full" : "rounded-lg"
                }`}
              />
            ) : (
              <div
                className={`w-11 h-11 bg-brand-charcoal text-white font-bold flex items-center justify-center text-sm uppercase shrink-0 ${
                  isPersonal ? "rounded-full" : "rounded-lg"
                }`}
              >
                {authorName.slice(0, 2)}
              </div>
            )}
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-bold text-slate-900 truncate hover:text-[#0A66C2] transition-colors cursor-pointer">
                  {authorName}
                </span>
                <span className="text-xs text-slate-400 font-normal">• 1.º</span>
              </div>
              <span className="text-[11px] text-slate-500 leading-tight truncate">
                {authorSubtitle}
              </span>
              <div className="flex items-center gap-1 text-[11px] text-slate-400 mt-0.5">
                <span>Ahora</span>
                <span>•</span>
                <Globe className="h-3 w-3 text-slate-400" />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={handleCopy}
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
              title="Copiar texto de la publicación"
            >
              {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
            </button>
            <button
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
              title="Opciones de publicación"
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Card Body: Text Content */}
        <div className="px-4 pb-3 text-[13.5px] leading-[1.55] text-slate-800 whitespace-pre-line font-normal break-words">
          {displayedContent}
          {needsTruncation && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-slate-500 hover:text-[#0A66C2] font-semibold text-xs ml-1 cursor-pointer focus-visible:outline-none"
            >
              {isExpanded ? " ver menos" : " ...ver más"}
            </button>
          )}

          {/* Call to action (if present) */}
          {cta && (
            <div className="mt-3 pt-2 font-medium text-slate-900 border-t border-slate-100">
              👉 {cta}
            </div>
          )}

          {/* Hashtags formatted */}
          {hashtags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5 pt-1">
              {hashtags.map((tag, idx) => (
                <span
                  key={idx}
                  className="text-xs font-semibold text-[#0A66C2] hover:underline cursor-pointer"
                >
                  {tag.startsWith("#") ? tag : `#${tag}`}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Social Metrics Bar */}
        <div className="px-4 py-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            <div className="flex -space-x-1 items-center">
              <span className="w-4 h-4 rounded-full bg-[#0A66C2] flex items-center justify-center text-white text-[9px]">
                👍
              </span>
              <span className="w-4 h-4 rounded-full bg-emerald-600 flex items-center justify-center text-white text-[9px]">
                👏
              </span>
              <span className="w-4 h-4 rounded-full bg-rose-500 flex items-center justify-center text-white text-[9px]">
                ❤️
              </span>
            </div>
            <span className="text-[11px] text-slate-500 font-medium">Reacciones simuladas</span>
          </div>
          <span className="text-[11px] text-slate-400">0 comentarios • 0 compartidos</span>
        </div>

        {/* Social Action Buttons */}
        <div className="px-2 py-1 border-t border-slate-100 bg-slate-50/50 flex items-center justify-around text-slate-600">
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-lg hover:bg-slate-100 text-xs font-semibold transition-colors">
            <ThumbsUp className="h-4 w-4 text-slate-500" />
            <span>Recomendar</span>
          </button>
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-lg hover:bg-slate-100 text-xs font-semibold transition-colors">
            <MessageSquare className="h-4 w-4 text-slate-500" />
            <span>Comentar</span>
          </button>
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-lg hover:bg-slate-100 text-xs font-semibold transition-colors">
            <Repeat2 className="h-4 w-4 text-slate-500" />
            <span>Compartir</span>
          </button>
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-lg hover:bg-slate-100 text-xs font-semibold transition-colors">
            <Send className="h-4 w-4 text-slate-500" />
            <span>Enviar</span>
          </button>
        </div>
      </article>
      </div>

      {/* Metrics & Action Bar */}
      <div className="flex items-center justify-between gap-4 px-1">
        {/* Character gauge */}
        <div className="flex items-center gap-2 text-xs">
          <span className="font-semibold text-slate-600">
            {charCount.toLocaleString()} / 3.000 caracteres
          </span>
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
              isOptimalLength
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-slate-100 text-slate-600 border-slate-200"
            }`}
          >
            {isOptimalLength ? "Longitud óptima LinkedIn" : charCount < 500 ? "Breve" : "Extenso"}
          </span>
        </div>

        {/* Quick Toolbar */}
        <div className="flex items-center gap-2">
          {onDelete && (
            <button
              onClick={onDelete}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer border border-rose-200"
              title="Borrar borrador y volver a un estado limpio para generar un nuevo post"
            >
              <Trash2 className="h-3.5 w-3.5 text-rose-500" />
              <span>Descartar</span>
            </button>
          )}

          {onEdit && (
            <button
              onClick={onEdit}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-brand-charcoal hover:bg-slate-100 rounded-lg transition-colors cursor-pointer border border-slate-200"
              title="Editar borrador manualmente"
            >
              <Edit2 className="h-3.5 w-3.5 text-slate-500" />
              <span>Editar</span>
            </button>
          )}

          {onSaveDraft && (
            <button
              onClick={onSaveDraft}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer border border-slate-200 shadow-xs"
              title={isEditMode ? "Guardar cambios y volver al historial" : "Guardar como borrador en el historial"}
            >
              <Bookmark className="h-3.5 w-3.5 text-slate-600" />
              <span>{isEditMode ? "Guardar cambios" : "Guardar borrador"}</span>
            </button>
          )}

          {onSchedule && (
            <button
              onClick={onSchedule}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-brand-charcoal hover:bg-slate-100 rounded-lg transition-colors cursor-pointer border border-slate-200 shadow-xs"
              title="Programar publicación en fecha y hora"
            >
              <Calendar className="h-3.5 w-3.5 text-slate-600" />
              <span>Programar</span>
            </button>
          )}

          {onPublish && (
            <button
              onClick={onPublish}
              disabled={isPublishing}
              className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold text-white bg-brand-teal hover:bg-brand-teal-dark rounded-lg transition-colors cursor-pointer shadow-xs disabled:opacity-50"
              title="Publicar inmediatamente en LinkedIn"
            >
              <Share2 className="h-3.5 w-3.5" />
              <span>{isPublishing ? "Publicando..." : "Publicar en LinkedIn"}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
