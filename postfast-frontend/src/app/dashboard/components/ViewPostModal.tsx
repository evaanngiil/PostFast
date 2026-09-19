"use client";

import React, { useState } from "react";
import { FileText, X, Copy, Check } from "lucide-react";
import { renderMarkdown } from "@/lib/markdown";

interface ViewPostModalProps {
  isOpen: boolean;
  onClose: () => void;
  post: any;
  companies: any[];
}

export default function ViewPostModal({
  isOpen,
  onClose,
  post,
  companies,
}: ViewPostModalProps) {
  const [copied, setCopied] = useState(false);

  if (!isOpen || !post) return null;

  const orgName =
    companies.find((c) => c.urn === post.account_id)?.name || post.account_id || "LinkedIn";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(post.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl overflow-hidden border border-slate-200">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-brand-teal" />
            <h3 className="font-bold text-slate-800 text-sm">Detalle de la publicación</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-6 flex flex-col gap-4 max-h-[75vh] overflow-y-auto">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex flex-col">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Cuenta
              </span>
              <span className="text-xs font-bold text-brand-charcoal mt-0.5">{orgName}</span>
            </div>
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Estado
              </span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded border font-bold uppercase tracking-wider mt-0.5 ${
                  post.status === "published"
                    ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                    : post.status === "scheduled"
                    ? "bg-blue-50 border-blue-200 text-blue-700"
                    : "bg-amber-50 border-amber-200 text-amber-700"
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
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Texto de la publicación
              </span>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-[11px] px-2.5 py-1 bg-slate-50 hover:bg-slate-100 text-slate-600 border border-slate-200 rounded font-semibold transition-colors cursor-pointer"
              >
                {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
                <span>{copied ? "Copiado" : "Copiar"}</span>
              </button>
            </div>
            <div className="bg-slate-50 rounded-lg p-4 border border-slate-200 text-xs leading-relaxed text-slate-800 whitespace-pre-line">
              {renderMarkdown(post.content)}
            </div>
          </div>

          {post.scheduled_time && (
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Fecha programada
              </span>
              <span className="text-xs text-slate-700 font-medium">
                {new Date(post.scheduled_time).toLocaleString()}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end px-5 py-3 border-t border-slate-100 bg-slate-50">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-lg transition-colors cursor-pointer"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
