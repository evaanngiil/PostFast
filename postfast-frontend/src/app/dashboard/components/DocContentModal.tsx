"use client";

import React from "react";
import { FileText, X, Loader2, Copy, Check } from "lucide-react";

interface DocContentModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedDoc: any;
  docContentLoading: boolean;
  selectedCompanyUrn?: string;
  authToken: string;
}

export default function DocContentModal({
  isOpen,
  onClose,
  selectedDoc,
  docContentLoading,
  selectedCompanyUrn,
  authToken,
}: DocContentModalProps) {
  const [copied, setCopied] = React.useState(false);

  if (!isOpen) return null;

  const handleCopy = async () => {
    if (selectedDoc?.content) {
      try {
        await navigator.clipboard.writeText(selectedDoc.content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        // Fallback
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-3 sm:p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl overflow-hidden border border-slate-200 flex flex-col max-h-[88dvh] h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-5 py-3.5 sm:py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <FileText className="h-4 w-4 text-brand-teal" />
            <h3 className="font-bold text-slate-800 text-sm">
              Visor de documento:{" "}
              <span className="font-mono text-xs font-semibold text-brand-charcoal bg-white px-2 py-0.5 rounded border border-slate-200">
                {selectedDoc?.filename || "Cargando..."}
              </span>
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content Viewer */}
        <div className="p-4 sm:p-5 flex-1 overflow-y-auto bg-slate-50/30 custom-scroll">
          {docContentLoading ? (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin text-brand-teal" />
              <span className="text-xs font-medium">Recuperando fragmentos desde la base vectorial...</span>
            </div>
          ) : selectedDoc ? (
            selectedDoc.isPdf ? (
              <iframe
                src={`http://localhost:8000/content/company/documents/pdf?org_urn=${encodeURIComponent(
                  selectedCompanyUrn || ""
                )}&filename=${encodeURIComponent(selectedDoc.filename)}&token=${authToken}`}
                className="w-full h-full border border-slate-200 rounded-lg bg-white shadow-inner"
                style={{ minHeight: "500px" }}
                title={selectedDoc.filename}
              />
            ) : (
              <div className="bg-white rounded-lg p-5 border border-slate-200 shadow-xs min-h-full leading-relaxed text-slate-800 text-xs whitespace-pre-wrap font-mono">
                {selectedDoc.content}
              </div>
            )
          ) : (
            <div className="h-full flex items-center justify-center text-slate-400 italic text-xs">
              No se pudo cargar el documento.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end px-5 py-3 border-t border-slate-100 bg-slate-50 gap-2">
          {selectedDoc && !selectedDoc.isPdf && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white hover:bg-slate-100 text-slate-700 font-semibold border border-slate-200 rounded-md transition-colors cursor-pointer"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
              <span>{copied ? "Copiado" : "Copiar texto"}</span>
            </button>
          )}
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
