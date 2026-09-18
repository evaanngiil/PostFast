import { CheckCircle, ShieldAlert } from "lucide-react";
import type { ToastMessage } from "@/lib/types";

interface ToastProps {
  toast: ToastMessage | null;
  onClose: () => void;
}

/** Notificación flotante efímera (esquina inferior derecha). */
export default function Toast({ toast, onClose }: ToastProps) {
  if (!toast) return null;
  return (
    <div className={`fixed bottom-6 right-6 z-[100] flex items-center gap-3 px-5 py-4 rounded-2xl shadow-2xl border animate-[slideInUp_0.3s_ease-out] transition-all max-w-sm ${
      toast.type === "success"
        ? "bg-emerald-50 border-emerald-200 text-emerald-800"
        : toast.type === "error"
        ? "bg-rose-50 border-rose-200 text-rose-800"
        : "bg-blue-50 border-blue-200 text-blue-800"
    }`}>
      {toast.type === "success" && <CheckCircle className="h-5 w-5 text-emerald-600 shrink-0" />}
      {toast.type === "error" && <ShieldAlert className="h-5 w-5 text-rose-600 shrink-0" />}
      {toast.type === "info" && <CheckCircle className="h-5 w-5 text-blue-600 shrink-0" />}
      <span className="text-xs font-bold leading-normal">{toast.text}</span>
      <button
        onClick={onClose}
        className="text-slate-400 hover:text-slate-600 font-bold text-lg ml-2 cursor-pointer leading-none"
      >
        &times;
      </button>
    </div>
  );
}
