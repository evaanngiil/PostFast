import { Calendar } from "lucide-react";

interface ScheduleModalProps {
  scheduleDate: string;
  onChange: (value: string) => void;
  onConfirm: () => void;
  onClose: () => void;
}

/** Modal para elegir fecha/hora de publicación programada en LinkedIn. */
export default function ScheduleModal({ scheduleDate, onChange, onConfirm, onClose }: ScheduleModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-slate-100">
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h3 className="font-bold text-slate-800 flex items-center gap-2">
            <Calendar className="h-5 w-5 text-brand-teal" />
            Programar Publicación
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-50 transition-colors"
          >
            &times;
          </button>
        </div>
        <div className="p-6 flex flex-col gap-4">
          <p className="text-sm text-slate-600">
            Elige la fecha y hora en la que quieres publicar el contenido en LinkedIn.
          </p>
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Fecha y Hora</label>
            <input
              type="datetime-local"
              value={scheduleDate}
              onChange={(e) => onChange(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all font-medium"
            />
          </div>
        </div>
        <div className="flex items-center justify-end gap-3 p-4 border-t border-slate-100 bg-slate-50/50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-bold text-slate-600 hover:text-slate-800 transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            disabled={!scheduleDate}
            className="px-6 py-2 bg-brand-teal hover:bg-brand-teal text-white text-sm font-bold rounded-xl transition-all shadow-md shadow-brand-teal/20 disabled:opacity-50 cursor-pointer"
          >
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}
