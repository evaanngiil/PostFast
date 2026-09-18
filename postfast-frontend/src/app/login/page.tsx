"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@supabase/supabase-js";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [supabaseConfig, setSupabaseConfig] = useState<any>(null);

  useEffect(() => {
    fetch("http://localhost:8000/config")
      .then((r) => r.json())
      .then((data) => setSupabaseConfig(data))
      .catch((err) => console.error("Error fetching config:", err));

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
      fetch("http://localhost:8000/auth/me", {
        headers: { "Authorization": `Bearer ${token}` }
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.authenticated) {
            router.push("/dashboard");
          } else {
            // Delete invalid session cookie
            document.cookie = "aipost_session_id=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; samesite=lax";
            localStorage.removeItem("aipost_session_token");
          }
        })
        .catch((err) => {
          console.error("Error verifying active token on login page:", err);
        });
    }
  }, [router]);

  const translateError = (errorMsg: string): string => {
    if (!errorMsg) return "Ha ocurrido un error inesperado.";
    const lower = errorMsg.toLowerCase();
    if (lower.includes("email not confirmed")) {
      return "Por favor, confirma tu correo electrónico antes de iniciar sesión. Revisa tu bandeja de entrada.";
    }
    if (lower.includes("invalid login credentials")) {
      return "El correo electrónico o la contraseña son incorrectos.";
    }
    if (lower.includes("user not found")) {
      return "No existe ningún usuario registrado con este correo electrónico.";
    }
    if (lower.includes("email already in use") || lower.includes("already registered")) {
      return "Este correo electrónico ya está registrado por otro usuario.";
    }
    if (lower.includes("password is too short")) {
      return "La contraseña debe tener al menos 6 caracteres.";
    }
    if (lower.includes("invalid email")) {
      return "Formato de correo electrónico no válido.";
    }
    return errorMsg;
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!supabaseConfig) {
      setError("Configuración no cargada. Asegúrate de que el backend está corriendo.");
      return;
    }
    setIsLoading(true);
    
    try {
      const supabase = createClient(supabaseConfig.supabase_url, supabaseConfig.supabase_key);
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (authError) throw authError;

      const jwt = data.session?.access_token;
      if (!jwt) throw new Error("No token received");

      // Set cookie in browser manually or call backend to create session
      // In NextJS we can set it via document.cookie for middleware to pick up
      document.cookie = `aipost_session_id=${jwt}; path=/; max-age=604800; samesite=lax`;
      localStorage.setItem("aipost_session_token", jwt);

      // Also notify backend if needed
      const res = await fetch("http://localhost:8000/auth/session/create_from_supabase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ supabase_jwt: jwt })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "No se pudo sincronizar la sesión con el backend.");
      }

      window.location.href = "/dashboard";
    } catch (err: any) {
      setError(translateError(err.message || "Error al iniciar sesión"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!firstName || !lastName) return setError("Debes introducir tu nombre y apellidos.");
    if (!terms) return setError("Debes aceptar los términos y condiciones.");
    if (password !== confirmPassword) return setError("Las contraseñas no coinciden.");
    
    if (!supabaseConfig) return;
    setIsLoading(true);

    try {
      const supabase = createClient(supabaseConfig.supabase_url, supabaseConfig.supabase_key);
      const { data, error: authError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            first_name: firstName,
            last_name: lastName,
            name: `${firstName} ${lastName}`
          }
        }
      });

      if (authError) throw authError;

      router.push("/verify-email"); // Redirect to verification instructions page
    } catch (err: any) {
      setError(translateError(err.message || "Error al crear cuenta"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex text-slate-800" style={{
      backgroundImage: "url('/assets/login_bg_full2.jpg')",
      backgroundSize: "cover",
      backgroundPosition: "center",
      backgroundRepeat: "no-repeat"
    }}>
      {/* Mitad Izquierda Transparente (o display none en movil) */}
      <div className="hidden md:flex flex-1" />

      {/* Mitad Derecha Formulario */}
      <div className="flex-1 flex justify-center items-center backdrop-blur-[2px] bg-white/10 md:bg-transparent p-4">
        <div className="bg-white w-full max-w-[450px] p-10 rounded-2xl shadow-[0_8px_24px_rgba(0,0,0,0.1)] animate-fade-in-up">
          <div className="flex justify-center mb-4">
            <img src="/logo.png" alt="AIPost Logo" className="h-16 w-16 object-contain" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 text-center mb-2">Bienvenido a AIPost</h1>
          <p className="text-sm text-slate-500 text-center mb-6">Accede o crea una cuenta para empezar a generar contenido con IA.</p>

          <div className="flex gap-4 border-b border-slate-200 mb-6">
            <button 
              className={`pb-2 text-sm font-semibold transition-colors ${activeTab === "login" ? "text-brand-teal border-b-2 border-brand-teal" : "text-slate-500 hover:text-slate-700"}`}
              onClick={() => setActiveTab("login")}
            >
              Iniciar Sesión
            </button>
            <button 
              className={`pb-2 text-sm font-semibold transition-colors ${activeTab === "signup" ? "text-brand-teal border-b-2 border-brand-teal" : "text-slate-500 hover:text-slate-700"}`}
              onClick={() => setActiveTab("signup")}
            >
              Crear Cuenta
            </button>
          </div>

          {error && <div className="bg-rose-50 text-rose-600 p-3 rounded-lg text-sm mb-4 border border-rose-200">{error}</div>}

          {activeTab === "login" ? (
            <form onSubmit={handleLogin} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">Email</label>
                <input 
                  type="email" 
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="tu@email.com"
                  required
                  className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-brand-teal focus:ring-1 focus:ring-brand-teal transition-all"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">Contraseña</label>
                <input 
                  type="password" 
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-brand-teal focus:ring-1 focus:ring-brand-teal transition-all"
                />
              </div>
              <button 
                type="submit" 
                disabled={isLoading}
                className="mt-2 bg-brand-teal hover:bg-brand-teal-dark text-white font-bold py-2.5 rounded-lg transition-colors flex justify-center items-center shadow-lg shadow-brand-teal/20"
              >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Iniciar Sesión"}
              </button>
            </form>
          ) : (
            <form onSubmit={handleSignup} className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-600">Nombre</label>
                  <input type="text" value={firstName} onChange={e=>setFirstName(e.target.value)} placeholder="Ana" required className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-brand-teal" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-600">Apellidos</label>
                  <input type="text" value={lastName} onChange={e=>setLastName(e.target.value)} placeholder="García" required className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-brand-teal" />
                </div>
              </div>
              
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">Email</label>
                <input type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="tu@email.com" required className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-brand-teal" />
              </div>
              
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">Contraseña</label>
                <input type="password" value={password} onChange={e=>setPassword(e.target.value)} required className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-brand-teal" />
              </div>
              
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-600">Confirma tu contraseña</label>
                <input type="password" value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} required className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-brand-teal" />
              </div>

              <div className="flex items-center gap-2 mt-1">
                <input type="checkbox" id="terms" checked={terms} onChange={e=>setTerms(e.target.checked)} className="rounded border-slate-300 text-brand-teal focus:ring-brand-teal" />
                <label htmlFor="terms" className="text-xs text-slate-600">Acepto los Términos y la Política de Privacidad.</label>
              </div>

              <button 
                type="submit" 
                disabled={isLoading}
                className="mt-2 bg-brand-teal hover:bg-brand-teal-dark text-white font-bold py-2.5 rounded-lg transition-colors flex justify-center items-center shadow-lg shadow-brand-teal/20"
              >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Crear Cuenta"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
