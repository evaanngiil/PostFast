"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { createClient } from "@supabase/supabase-js";

export default function OnboardingPage() {
  const router = useRouter();
  const [role, setRole] = useState("");
  const [goals, setGoals] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [userName, setUserName] = useState("usuario");
  const [supabaseConfig, setSupabaseConfig] = useState<any>(null);

  const goalOptions = [
    "Generar leads",
    "Aumentar engagement",
    "Educar a la audiencia",
    "Construir marca personal",
    "Ahorrar tiempo en contenido",
  ];

  const [authToken, setAuthToken] = useState("");

  useEffect(() => {
    const getCookie = (name: string) => {
      const value = `; ${document.cookie}`;
      const parts = value.split(`; ${name}=`);
      if (parts.length === 2) return parts.pop()?.split(';').shift();
      return null;
    };
    const cookieToken = getCookie("aipost_session_id");
    const localToken = localStorage.getItem("aipost_session_token");
    const token = cookieToken || localToken;
    if (token) {
      if (!cookieToken) {
        document.cookie = `aipost_session_id=${token}; path=/; max-age=604800; samesite=lax`;
      }
      setAuthToken(token);
      // Fetch user info from backend
      fetch("http://localhost:8000/auth/me", {
        headers: { "Authorization": `Bearer ${token}` }
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.authenticated && data.user_info) {
            const ui = data.user_info;
            setUserName(ui.first_name || ui.firstName || ui.name || "usuario");
          } else if (data.authenticated === false) {
             document.cookie = "aipost_session_id=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
             localStorage.removeItem("aipost_session_token");
             router.push("/login");
          }
        })
        .catch((err) => {
          console.error("Error fetching /auth/me in onboarding:", err);
          document.cookie = "aipost_session_id=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
          localStorage.removeItem("aipost_session_token");
          router.push("/login");
        });
    } else {
      document.cookie = "aipost_session_id=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
      localStorage.removeItem("aipost_session_token");
      router.push("/login");
    }

    fetch("http://localhost:8000/config")
      .then((r) => r.json())
      .then((data) => setSupabaseConfig(data))
      .catch((err) => console.error("Error fetching config:", err));
  }, []);

  useEffect(() => {
    // Attempt to fetch current user's name if config is available
    if (supabaseConfig) {
      const fetchUser = async () => {
        try {
          const supabase = createClient(supabaseConfig.supabase_url, supabaseConfig.supabase_key);
          const { data: { user } } = await supabase.auth.getUser();
          if (user) {
            setUserName(user.user_metadata?.first_name || user.user_metadata?.name || "usuario");
          }
        } catch (e) {
          console.error("Error fetching user name from Supabase:", e);
        }
      };
      fetchUser();
    }
  }, [supabaseConfig]);

  const toggleGoal = (goal: string) => {
    setGoals((prev) => {
      if (prev.includes(goal)) return prev.filter((g) => g !== goal);
      if (prev.length >= 3) return prev;
      return [...prev, goal];
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!role) return setError("Indica tu rol para continuar.");
    if (goals.length === 0) return setError("Selecciona al menos un objetivo.");
    if (!authToken) return setError("Sesión no válida o expirada.");
    
    setIsLoading(true);
    try {
      const res = await fetch("http://localhost:8000/auth/onboarding", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({ role, goals })
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Error al completar el onboarding.");
      }

      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Error al guardar. Inténtalo de nuevo.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center py-10 px-4">
      <div className="w-full max-w-[700px]">
        {/* Logo (if applicable) */}
        <div className="flex justify-center mb-6">
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="AIPost Logo" className="h-10 w-10 object-contain" />
              <span className="text-brand-teal font-bold text-2xl tracking-wider">AIPost</span>
            </div>
        </div>

        {/* Hero Section */}
        <div className="bg-gradient-to-br from-brand-teal to-brand-teal-dark rounded-t-3xl rounded-b-lg p-10 text-center mb-8 shadow-md">
          <h1 className="text-white text-3xl font-bold mb-2">¡Bienvenido, {userName}!</h1>
          <p className="text-white/90 text-lg">Configura tu perfil para personalizar tu experiencia con IA</p>
        </div>

        {/* Form Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-[0_4px_16px_rgba(0,0,0,0.06)]">
          <h3 className="text-xl font-bold text-slate-900 mb-1">Sobre ti</h3>
          <p className="text-sm text-slate-500 mb-8">Solo necesitamos unos datos para calibrar tu asistente de contenido.</p>

          {error && <div className="bg-rose-50 text-rose-600 p-4 rounded-xl text-sm mb-6 border border-rose-200 font-medium">{error}</div>}

          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-bold text-slate-700">Tu rol en la organización</label>
              <input 
                type="text" 
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Ej: Fundador, Marketing Manager, Community Manager"
                className="px-4 py-3 border-[1.5px] border-slate-200 rounded-xl text-sm focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-sm font-bold text-slate-700 flex justify-between">
                Objetivos principales con la plataforma
                <span className="text-xs text-slate-400 font-normal">Máx. 3 seleccionados</span>
              </label>
              <div className="flex flex-wrap gap-2 mt-1">
                {goalOptions.map((goal) => {
                  const isSelected = goals.includes(goal);
                  return (
                    <button
                      key={goal}
                      type="button"
                      onClick={() => toggleGoal(goal)}
                      className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all border ${
                        isSelected 
                          ? "bg-brand-teal/10 border-brand-teal text-brand-teal shadow-sm" 
                          : "bg-white border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                      }`}
                    >
                      {goal}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mt-4">
              <button 
                type="submit" 
                disabled={isLoading}
                className="w-full bg-gradient-to-br from-brand-teal to-brand-teal-dark hover:shadow-[0_6px_20px_rgba(0,169,157,0.3)] hover:-translate-y-[1px] text-white font-bold py-3.5 rounded-xl transition-all duration-250 flex justify-center items-center text-[15px]"
              >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Empezar a usar AIPost"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
