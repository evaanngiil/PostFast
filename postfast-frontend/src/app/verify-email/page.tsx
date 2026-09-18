"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Mail } from "lucide-react";

export default function VerifyEmailPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white p-12 rounded-2xl shadow-[0_4px_12px_rgba(0,0,0,0.05)] border border-slate-200 max-w-[480px] w-full text-center animate-fade-in-up">
        
        <div className="flex justify-center mb-6">
          <div className="p-4 bg-brand-teal/10 rounded-full border border-brand-teal/20">
            <Mail className="w-16 h-16 text-brand-teal animate-pulse" />
          </div>
        </div>

        <h1 className="text-[1.75rem] font-semibold text-slate-800 mb-3">
          ¡Verifica tu correo!
        </h1>
        
        <p className="text-slate-500 mb-8 leading-relaxed text-base">
          Te hemos enviado un enlace de confirmación a tu correo electrónico. Por favor, haz clic en el enlace de verificación para activar tu cuenta antes de iniciar sesión.
        </p>

        <button 
          onClick={() => router.push("/login")}
          className="w-full bg-brand-teal hover:bg-brand-teal-dark hover:-translate-y-[2px] text-white font-semibold py-3.5 rounded-xl transition-all duration-200 cursor-pointer shadow-lg shadow-brand-teal/20"
        >
          Volver al Inicio de Sesión
        </button>

      </div>
    </div>
  );
}
