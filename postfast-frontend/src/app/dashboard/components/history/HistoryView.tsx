"use client";

import React, { useState } from "react";
import {
  RefreshCw,
  Eye,
  Edit3,
  Send,
  Calendar,
  Trash2,
  CheckCircle2,
  FileText,
  Search,
} from "lucide-react";
import { renderMarkdown } from "@/lib/markdown";

interface PostItem {
  id: string;
  account_id?: string;
  thread_id?: string;
  content: string;
  status: string;
  score?: number;
  created_at?: string;
  published_time?: string;
}

interface HistoryViewProps {
  postsHistory: PostItem[];
  isLoadingHistory: boolean;
  loadHistory: (urn?: string) => void;
  selectedOrgUrn?: string;
  companies: any[];
  onViewPost: (post: PostItem) => void;
  onEditPost: (post: PostItem) => void;
  onPublishNow: (post: PostItem) => void;
  onScheduleDialog: (post: PostItem) => void;
  onDeletePost: (postId: string) => void;
}

export default function HistoryView({
  postsHistory,
  isLoadingHistory,
  loadHistory,
  selectedOrgUrn,
  companies,
  onViewPost,
  onEditPost,
  onPublishNow,
  onScheduleDialog,
  onDeletePost,
}: HistoryViewProps) {
  const [filterStatus, setFilterStatus] = useState<"all" | "published" | "scheduled" | "draft">("all");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredPosts = postsHistory.filter((p) => {
    if (searchQuery.trim() && !p.content.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (filterStatus === "all") return true;
    if (filterStatus === "published") return p.status === "published";
    if (filterStatus === "scheduled") return p.status === "scheduled";
    if (filterStatus === "draft") return p.status === "draft" || p.status === "saved_for_later";
    return true;
  });

  const countPublished = postsHistory.filter((p) => p.status === "published").length;
  const countScheduled = postsHistory.filter((p) => p.status === "scheduled").length;
  const countDrafts = postsHistory.filter((p) => p.status === "draft" || p.status === "saved_for_later").length;

  return (
    <div className="w-full max-w-[116rem] 2xl:max-w-[124rem] 3xl:max-w-[136rem] mx-auto px-3 sm:px-5 lg:px-6 xl:px-8 2xl:px-12 py-4 sm:py-6 2xl:py-8 flex flex-col gap-5 sm:gap-6 2xl:gap-8">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-[#473E3F] p-4 shadow-xs">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Total publicaciones</span>
          <p className="text-xl font-extrabold text-[#383132] mt-1">{postsHistory.length}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-emerald-600 p-4 shadow-xs">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Publicados</span>
          <p className="text-xl font-extrabold text-emerald-700 mt-1">{countPublished}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-[#2B8385] p-4 shadow-xs">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Programados</span>
          <p className="text-xl font-extrabold text-[#1E6062] mt-1">{countScheduled}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 border-l-4 border-l-amber-600 p-4 shadow-xs">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Borradores</span>
          <p className="text-xl font-extrabold text-amber-700 mt-1">{countDrafts}</p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {(
            [
              { id: "all", label: `Todos (${postsHistory.length})` },
              { id: "published", label: `Publicados (${countPublished})` },
              { id: "scheduled", label: `Programados (${countScheduled})` },
              { id: "draft", label: `Borradores (${countDrafts})` },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterStatus(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                filterStatus === tab.id
                  ? "bg-[#473E3F] text-white font-bold shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/70"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar por contenido..."
              className="w-full text-xs pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-teal focus:border-brand-teal"
            />
          </div>
          <button
            onClick={() => loadHistory(selectedOrgUrn)}
            disabled={isLoadingHistory}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#473E3F] hover:bg-[#383132] text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer shrink-0 disabled:opacity-50"
            title="Actualizar historial"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-slate-200 ${isLoadingHistory ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Actualizar</span>
          </button>
        </div>
      </div>

      {/* Posts Cards Grid */}
      {isLoadingHistory ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-xs text-slate-400">
          Cargando publicaciones del espacio...
        </div>
      ) : filteredPosts.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center flex flex-col items-center justify-center gap-2 text-slate-400">
          <FileText className="h-8 w-8 text-slate-300" />
          <span className="text-xs font-medium">No se encontraron publicaciones con el filtro seleccionado.</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4 sm:gap-5">
          {filteredPosts.map((post) => {
            const orgName =
              companies.find((c) => c.urn === post.account_id)?.name || post.account_id || "LinkedIn";
            const dateFormatted = post.created_at || post.published_time
              ? new Date(post.created_at || post.published_time!).toLocaleDateString("es-ES", {
                  day: "2-digit",
                  month: "short",
                  year: "numeric",
                })
              : "Fecha no registrada";

            return (
              <div
                key={post.id}
                className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col gap-3 hover:border-slate-300 transition-all"
              >
                {/* Card Top */}
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-brand-charcoal truncate max-w-[200px]">
                    {orgName}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {post.score !== undefined && post.score !== null && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200">
                        {post.score}/100
                      </span>
                    )}
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-md border uppercase tracking-wider ${
                        post.status === "published"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : post.status === "scheduled"
                          ? "bg-blue-50 text-blue-700 border-blue-200"
                          : "bg-amber-50 text-amber-700 border-amber-200"
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

                {/* Content excerpt */}
                <div className="text-xs text-slate-600 line-clamp-3 leading-relaxed">
                  {renderMarkdown(post.content)}
                </div>

                {/* Footer Toolbar */}
                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400 mt-auto">
                  <span>{dateFormatted}</span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => onViewPost(post)}
                      className="p-1.5 text-slate-500 hover:text-brand-teal hover:bg-slate-100 rounded-md transition-colors"
                      title="Ver publicación completa"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </button>
                    {post.status !== "published" && (
                      <>
                        <button
                          onClick={() => onEditPost(post)}
                          className="p-1.5 text-slate-500 hover:text-brand-teal hover:bg-slate-100 rounded-md transition-colors"
                          title="Editar publicación"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => onScheduleDialog(post)}
                          className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                          title="Programar fecha de publicación"
                        >
                          <Calendar className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => onPublishNow(post)}
                          className="p-1.5 text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 rounded-md transition-colors"
                          title="Publicar en LinkedIn inmediatamente"
                        >
                          <Send className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => onDeletePost(post.id)}
                      className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                      title="Eliminar publicación"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
