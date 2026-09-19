"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@supabase/supabase-js";
import {
  Loader2,
  Mail,
  Lock,
  Eye,
  EyeOff,
  User,
  ShieldCheck,
  ArrowRight,
  AlertCircle,
} from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
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
      if (parts.length === 2) return parts.pop()?.split(";").shift();
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
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.authenticated) {
            router.push("/dashboard");
          } else {
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

      document.cookie = `aipost_session_id=${jwt}; path=/; max-age=604800; samesite=lax`;
      localStorage.setItem("aipost_session_token", jwt);

      const res = await fetch("http://localhost:8000/auth/session/create_from_supabase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ supabase_jwt: jwt }),
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
            name: `${firstName} ${lastName}`,
          },
        },
      });

      if (authError) throw authError;

      router.push("/verify-email");
    } catch (err: any) {
      setError(translateError(err.message || "Error al crear cuenta"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen w-full flex flex-col md:flex-row text-slate-800 bg-[#E2EEF2]"
      style={{
        backgroundImage: "url('/assets/login_bg_full2.jpg')",
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
      }}
    >
      <div className="hidden md:flex flex-1 lg:flex-[1.05]" />

      <div className="flex-1 flex justify-center items-center p-4 sm:p-6 md:p-10 backdrop-blur-[1px] md:backdrop-blur-none min-h-screen">
        <div className="w-full max-w-[430px] bg-white/95 backdrop-blur-md rounded-2xl border border-white/80 shadow-[0_12px_36px_rgba(0,0,0,0.08)] p-7 sm:p-9 my-auto">
          <div className="flex flex-col items-center text-center mb-5">
            <div className="w-14 h-14 rounded-2xl bg-white border border-slate-200/80 flex items-center justify-center p-2 mb-3 shadow-2xs">
              <img src="/logo.png" alt="AIPost Logo" className="w-full h-full object-contain" />
            </div>
            <h1 className="text-xl font-bold text-brand-charcoal tracking-tight">
              {activeTab === "login" ? "Iniciar sesión en AIPost" : "Crear cuenta corporativa"}
            </h1>
            <p className="text-xs text-slate-500 mt-1">
              {activeTab === "login"
                ? "Plataforma empresarial de redacción y publicación para LinkedIn"
                : "Configura tu cuenta para comenzar a publicar con agentes IA"}
            </p>
          </div>

          <div className="grid grid-cols-2 p-1 bg-slate-100 rounded-xl mb-5 border border-slate-200/80">
            <button
              type="button"
              onClick={() => {
                setActiveTab("login");
                setError("");
              }}
              className={`py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                activeTab === "login"
                  ? "bg-white text-brand-charcoal shadow-xs"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              Iniciar sesión
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab("signup");
                setError("");
              }}
              className={`py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                activeTab === "signup"
                  ? "bg-white text-brand-charcoal shadow-xs"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              Crear cuenta
            </button>
          </div>

          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 mb-4">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-600" />
              <span className="leading-snug">{error}</span>
            </div>
          )}

          {activeTab === "login" ? (
            <form onSubmit={handleLogin} className="flex flex-col gap-3.5">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-700">Email corporativo</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Mail className="h-4 w-4" />
                  </div>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="tu@empresa.com"
                    autoComplete="email"
                    inputMode="email"
                    required
                    className="w-full pl-9 pr-3 py-2.5 bg-slate-50/60 border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#2B8385]/20 focus:border-[#2B8385] transition-all"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-700">Contraseña</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Lock className="h-4 w-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    required
                    className="w-full pl-9 pr-10 py-2.5 bg-slate-50/60 border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#2B8385]/20 focus:border-[#2B8385] transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full mt-2 bg-[#2B8385] hover:bg-[#1E6062] text-white font-bold py-2.5 px-4 rounded-lg text-xs transition-colors flex justify-center items-center gap-2 shadow-xs cursor-pointer disabled:opacity-50"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <span>Iniciar sesión</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </form>
          ) : (
            <form onSubmit={handleSignup} className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-700">Nombre</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                      <User className="h-3.5 w-3.5" />
                    </div>
                    <input
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      placeholder="Ana"
                      autoComplete="given-name"
                      required
                      className="w-full pl-8 pr-2.5 py-2 bg-slate-50/60 border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#2B8385]/20 focus:border-[#2B8385] transition-all"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-slate-700">Apellidos</label>
                  <input
                    type="text"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="García"
                    autoComplete="family-name"
                    required
                    className="w-full px-3 py-2 bg-slate-50/60 border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#2B8385]/20 focus:border-[#2B8385] transition-all"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-700">Email corporativo</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Mail className="h-4 w-4" />
                  </div>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="tu@empresa.com"
                    autoComplete="email"
                    inputMode="email"
                    required
                    className="w-full pl-9 pr-3 py-2 bg-slate-50/60 border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#2B8385]/20 focus:border-[#2B8385] transition-all"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-700">Contraseña</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Lock className="h-4 w-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    required
                    className="w-full pl-9 pr-10 py-2 bg-slate-50/60 border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#2B8385]/20 focus:border-[#2B8385] transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-700">Confirma tu contraseña</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Lock className="h-4 w-4" />
                  </div>
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    required
                    className="w-full pl-9 pr-10 py-2 bg-slate-50/60 border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#2B8385]/20 focus:border-[#2B8385] transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                    tabIndex={-1}
                  >
                    {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-start gap-2 pt-0.5">
                <input
                  type="checkbox"
                  id="terms"
                  checked={terms}
                  onChange={(e) => setTerms(e.target.checked)}
                  className="mt-0.5 rounded border-slate-300 text-[#2B8385] focus:ring-[#2B8385] cursor-pointer"
                />
                <label htmlFor="terms" className="text-[11px] text-slate-600 cursor-pointer leading-tight">
                  Acepto los términos de servicio y la política de privacidad corporativa.
                </label>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full mt-1.5 bg-[#2B8385] hover:bg-[#1E6062] text-white font-bold py-2.5 px-4 rounded-lg text-xs transition-colors flex justify-center items-center gap-2 shadow-xs cursor-pointer disabled:opacity-50"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <span>Crear cuenta</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </form>
          )}

          <div className="mt-5 pt-3.5 border-t border-slate-100 flex items-center justify-center gap-1.5 text-[11px] text-slate-400 text-center">
            <ShieldCheck className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            <span>Protegido con cifrado TLS y autenticación Supabase</span>
          </div>
        </div>
      </div>
    </div>
  );
}
