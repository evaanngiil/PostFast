import { Loader2, CheckCircle, ShieldAlert } from "lucide-react";

interface PublishStatusModalProps {
  status: "loading" | "success" | "error" | null;
  onClose: () => void;
}

/** Modal de estado de la publicación en LinkedIn (cargando / éxito / error). */
export default function PublishStatusModal({ status, onClose }: PublishStatusModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
      <style>{`
        @keyframes checkmarkScale {
          0% { transform: scale(0); opacity: 0; }
          50% { transform: scale(1.15); }
          100% { transform: scale(1); opacity: 1; }
        }
        @keyframes slideInUp {
          from { transform: translateY(15px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm overflow-hidden border border-slate-100 p-6 flex flex-col items-center gap-4 text-center">
        {status === "loading" && (
          <div className="flex flex-col items-center gap-4 py-6">
            <div className="w-16 h-16 bg-slate-50 border border-slate-200 rounded-full flex items-center justify-center text-brand-teal shadow-sm">
              <Loader2 className="w-8 h-8 animate-spin" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-base">Publicando en LinkedIn...</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-[250px]">Estamos conectando y enviando tu post de manera segura.</p>
            </div>
          </div>
        )}

        {status === "success" && (
          <div className="flex flex-col items-center gap-4 py-4 animate-[slideInUp_0.3s_ease-out]">
            <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center text-emerald-600 shadow-lg shadow-emerald-100/30 animate-[checkmarkScale_0.4s_cubic-bezier(0.175,0.885,0.32,1.275)]">
              <CheckCircle className="w-10 h-10 stroke-[2.5]" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-base">¡Publicación Exitosa!</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-[260px]">Tu contenido se ha publicado correctamente en LinkedIn. Ya puedes verlo en tu feed.</p>
            </div>
            <button
              onClick={onClose}
              className="mt-2 px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-md transition-colors cursor-pointer"
            >
              Entendido
            </button>
          </div>
        )}

        {status === "error" && (
          <div className="flex flex-col items-center gap-4 py-4 animate-[slideInUp_0.3s_ease-out]">
            <div className="w-16 h-16 bg-rose-100 rounded-full flex items-center justify-center text-rose-600 shadow-lg shadow-rose-100/30 animate-[checkmarkScale_0.4s_cubic-bezier(0.175,0.885,0.32,1.275)]">
              <ShieldAlert className="w-10 h-10 stroke-[2.5]" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-base">Error al publicar</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-[260px]">LinkedIn ha rechazado la publicación. Por favor, comprueba tus credenciales de sesión.</p>
            </div>
            <button
              onClick={onClose}
              className="mt-2 px-6 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold rounded-xl transition-colors cursor-pointer"
            >
              Cerrar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
