"use client";

import React, { useRef, useState, useEffect } from "react";
import {
  PenLine,
  Database,
  SlidersHorizontal,
  Clock,
  ChevronDown,
  Check,
  RefreshCw,
  LogOut,
  Menu,
  X,
  Building2,
  User,
  ShieldCheck,
} from "lucide-react";

export interface CompanyAccount {
  urn: string;
  name: string;
  logo_url?: string;
  is_personal?: boolean;
  company_name?: string;
  first_name?: string;
  last_name?: string;
}

export interface UserInfo {
  name?: string;
  picture?: string;
  email?: string;
}

interface AppHeaderProps {
  activeTab: "generator" | "knowledge" | "skills" | "history";
  setActiveTab: (tab: "generator" | "knowledge" | "skills" | "history") => void;
  selectedCompany: CompanyAccount | null;
  setSelectedCompany: (company: CompanyAccount) => void;
  companies: CompanyAccount[];
  loadCompanies: () => void;
  isLinkedinConnected: boolean;
  handleConnectLinkedin: () => void;
  handleDisconnectLinkedin: () => void;
  handleLogout: () => void;
  userInfo: UserInfo | null;
}

export default function AppHeader({
  activeTab,
  setActiveTab,
  selectedCompany,
  setSelectedCompany,
  companies,
  loadCompanies,
  isLinkedinConnected,
  handleConnectLinkedin,
  handleDisconnectLinkedin,
  handleLogout,
  userInfo,
}: AppHeaderProps) {
  const [isTenantOpen, setIsTenantOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});

  const tenantRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on click outside
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (tenantRef.current && !tenantRef.current.contains(e.target as Node)) {
        setIsTenantOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setIsUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const markImageFailed = (src: string) => {
    setFailedImages((prev) => ({ ...prev, [src]: true }));
  };

  const navItems = [
    { id: "generator", label: "Estudio", icon: PenLine },
    { id: "knowledge", label: "Base de conocimiento", icon: Database },
    { id: "skills", label: "Habilidades", icon: SlidersHorizontal },
    { id: "history", label: "Histórico", icon: Clock },
  ] as const;

  return (
    <header className="sticky top-0 z-40 bg-[#2E2829] border-b border-[#3E3637] shadow-sm text-white">
      <div className="w-full max-w-[116rem] 2xl:max-w-[124rem] 3xl:max-w-[136rem] mx-auto px-3 sm:px-5 lg:px-8 2xl:px-12 h-14 sm:h-16 lg:h-[68px] 2xl:h-[76px] flex items-center justify-between gap-2 sm:gap-4">
        {/* Left: Brand Logo & Navigation */}
        <div className="flex items-center gap-3 sm:gap-6 lg:gap-8 min-w-0">
          {/* Logo & Brand Identity */}
          <div className="flex items-center gap-2.5 sm:gap-3.5 shrink-0">
            <img
              src="/logo.png"
              alt="AIPost Logo"
              className="h-9 w-9 sm:h-10 sm:w-10 lg:h-11 lg:w-11 object-contain select-none transition-transform hover:scale-105 duration-200"
            />
            <span className="text-base sm:text-lg lg:text-xl font-black tracking-[0.14em] sm:tracking-[0.18em] text-white select-none leading-none">
              AIPOST
            </span>
          </div>

          {/* Desktop Navigation Tabs */}
          <nav className="hidden md:flex items-center gap-1 lg:gap-1.5" aria-label="Navegación principal">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center gap-1.5 lg:gap-2 px-2.5 lg:px-3.5 py-1.5 lg:py-2 rounded-lg text-xs lg:text-sm 2xl:text-base font-semibold transition-all duration-150 cursor-pointer ${
                    isActive
                      ? "bg-[#2B8385] text-white shadow-xs font-bold"
                      : "text-slate-300 hover:text-white hover:bg-white/10"
                  }`}
                  aria-current={isActive ? "page" : undefined}
                >
                  <Icon
                    className={`h-4 w-4 2xl:h-4.5 2xl:w-4.5 transition-colors ${
                      isActive ? "text-white" : "text-slate-400"
                    }`}
                  />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Right: Tenant Switcher, LinkedIn Status & User Pill */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {/* Tenant / Organization Switcher */}
          {selectedCompany && (
            <div className="relative" ref={tenantRef}>
              <button
                onClick={() => setIsTenantOpen(!isTenantOpen)}
                className="flex items-center gap-2 sm:gap-2.5 2xl:gap-3 bg-[#3D3536] hover:bg-[#483F40] border border-[#524849] rounded-lg 2xl:rounded-xl px-2 sm:px-2.5 2xl:px-3.5 py-1 sm:py-1.5 2xl:py-2 text-left transition-colors cursor-pointer text-white"
                title="Cambiar organización o cuenta activa"
                aria-expanded={isTenantOpen}
                aria-haspopup="true"
              >
                {selectedCompany.logo_url && !failedImages[selectedCompany.logo_url] ? (
                  <img
                    src={selectedCompany.logo_url}
                    alt={selectedCompany.name}
                    onError={() => markImageFailed(selectedCompany.logo_url!)}
                    className="w-5 h-5 sm:w-6 sm:h-6 2xl:w-7 2xl:h-7 rounded object-cover border border-[#524849] shrink-0"
                  />
                ) : (
                  <div className="w-5 h-5 sm:w-6 sm:h-6 2xl:w-7 2xl:h-7 bg-[#2B8385] text-white rounded flex items-center justify-center text-xs 2xl:text-sm font-bold uppercase shrink-0">
                    {selectedCompany.name.slice(0, 2)}
                  </div>
                )}
                <div className="flex flex-col">
                  <span className="text-xs sm:text-sm 2xl:text-base font-bold text-white leading-tight max-w-[85px] sm:max-w-[130px] md:max-w-[180px] lg:max-w-[220px] 2xl:max-w-[340px] truncate">
                    {selectedCompany.name}
                  </span>
                  <span className="text-[0.6875rem] 2xl:text-xs text-slate-300 font-medium leading-none hidden sm:inline">
                    {selectedCompany.is_personal ? "Perfil personal" : "Página de empresa"}
                  </span>
                </div>
                <ChevronDown
                  className={`h-3 w-3 sm:h-3.5 sm:w-3.5 2xl:h-4 2xl:w-4 text-slate-300 transition-transform duration-150 ${
                    isTenantOpen ? "rotate-180" : ""
                  }`}
                />
              </button>

              {/* Tenant Dropdown */}
              {isTenantOpen && (
                <div className="absolute right-0 top-full mt-1.5 2xl:mt-2.5 w-72 sm:w-80 md:w-88 2xl:w-96 max-w-[calc(100vw-1.5rem)] bg-[#2E2829] rounded-xl 2xl:rounded-2xl border border-[#443C3D] shadow-2xl py-2 z-50 animate-in fade-in slide-in-from-top-1 duration-150 text-white">
                  <div className="px-3 2xl:px-4 py-2 2xl:py-2.5 border-b border-[#3E3637] flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Building2 className="h-3.5 w-3.5 2xl:h-4 2xl:w-4 text-[#3FA5A7]" />
                      <span className="text-xs 2xl:text-sm font-bold uppercase tracking-wider text-slate-300">
                        Cuentas vinculadas
                      </span>
                    </div>
                    <button
                      onClick={loadCompanies}
                      className="p-1 2xl:p-1.5 text-slate-400 hover:text-white rounded-md hover:bg-white/10 transition-colors cursor-pointer"
                      title="Actualizar cuentas"
                    >
                      <RefreshCw className="h-3 w-3 2xl:h-3.5 2xl:w-3.5" />
                    </button>
                  </div>
                  <div className="max-h-56 sm:max-h-64 2xl:max-h-80 overflow-y-auto py-1 custom-scroll">
                    {companies.length === 0 ? (
                      <div className="px-4 py-6 text-center text-xs 2xl:text-sm text-slate-400">
                        No hay cuentas vinculadas disponibles.
                      </div>
                    ) : (
                      companies.map((c) => {
                        const isCurrent = c.urn === selectedCompany.urn;
                        return (
                          <button
                            key={c.urn}
                            onClick={() => {
                              setSelectedCompany(c);
                              localStorage.setItem("postfast_active_org_urn", c.urn);
                              setIsTenantOpen(false);
                            }}
                            className={`w-full flex items-center justify-between px-3 2xl:px-4 py-2 2xl:py-2.5 hover:bg-[#3D3536] text-left transition-colors cursor-pointer ${
                              isCurrent ? "bg-[#3D3536]/80 text-[#3FA5A7]" : "text-slate-200"
                            }`}
                          >
                            <div className="flex items-center gap-2.5 2xl:gap-3 min-w-0">
                              {c.logo_url && !failedImages[c.logo_url] ? (
                                <img
                                  src={c.logo_url}
                                  alt={c.name}
                                  onError={() => markImageFailed(c.logo_url!)}
                                  className="w-6 h-6 2xl:w-7 2xl:h-7 rounded object-cover border border-[#524849] shrink-0"
                                />
                              ) : (
                                <div className="w-6 h-6 2xl:w-7 2xl:h-7 bg-[#2B8385] text-white rounded flex items-center justify-center text-xs 2xl:text-sm font-bold uppercase shrink-0">
                                  {c.name.slice(0, 2)}
                                </div>
                              )}
                              <div className="flex flex-col truncate">
                                <span className="text-xs sm:text-sm 2xl:text-base font-semibold text-white truncate">
                                  {c.name}
                                </span>
                                <span className="text-[0.6875rem] 2xl:text-xs text-slate-400">
                                  {c.is_personal ? "Perfil personal" : "Página de empresa"}
                                </span>
                              </div>
                            </div>
                            {isCurrent && <Check className="h-4 w-4 2xl:h-5 2xl:w-5 text-[#3FA5A7] shrink-0 ml-2" />}
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* LinkedIn Connector (only shown when disconnected) */}
          {!isLinkedinConnected && (
            <button
              onClick={handleConnectLinkedin}
              className="flex items-center gap-1.5 px-2.5 py-1.5 bg-[#0077B5] hover:bg-[#005E93] text-white rounded-md text-xs font-semibold shadow-xs transition-colors cursor-pointer"
              title="Conectar con tu cuenta de LinkedIn"
            >
              <svg className="h-3 w-3 fill-current" viewBox="0 0 24 24">
                <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.779-1.75-1.75s.784-1.75 1.75-1.75 1.75.779 1.75 1.75-.784 1.75-1.75 1.75zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" />
              </svg>
              <span className="hidden sm:inline">Conectar LinkedIn</span>
            </button>
          )}

          {/* User Profile Pill & Dropdown */}
          <div className="relative" ref={userMenuRef}>
            <button
              onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
              className="flex items-center gap-2 p-1 hover:bg-white/10 rounded-lg transition-colors cursor-pointer text-white"
              aria-expanded={isUserMenuOpen}
              aria-haspopup="true"
            >
              {userInfo?.picture && !failedImages[userInfo.picture] ? (
                <img
                  src={userInfo.picture}
                  alt={userInfo.name || "Usuario"}
                  onError={() => markImageFailed(userInfo.picture!)}
                  className="w-7 h-7 2xl:w-8 2xl:h-8 rounded-full object-cover border border-[#524849] shrink-0"
                />
              ) : (
                <div className="w-7 h-7 2xl:w-8 2xl:h-8 rounded-full bg-[#3D3536] text-white flex items-center justify-center text-xs font-bold shrink-0 uppercase border border-[#524849]">
                  {(userInfo?.name || userInfo?.email || "U").slice(0, 2)}
                </div>
              )}
              <ChevronDown className="h-3 w-3 2xl:h-3.5 2xl:w-3.5 text-slate-300 hidden sm:block" />
            </button>

            {isUserMenuOpen && (
              <div className="absolute right-0 top-full mt-1.5 2xl:mt-2.5 w-60 sm:w-64 2xl:w-72 bg-[#2E2829] rounded-xl 2xl:rounded-2xl border border-[#443C3D] shadow-2xl py-2 z-50 animate-in fade-in slide-in-from-top-1 duration-150 text-white">
                <div className="px-3.5 2xl:px-4 py-2.5 2xl:py-3 border-b border-[#3E3637]">
                  <p className="text-xs 2xl:text-sm font-bold text-white truncate">
                    {userInfo?.name || "Usuario"}
                  </p>
                  <p className="text-[0.6875rem] 2xl:text-xs text-slate-400 truncate mt-0.5">
                    {userInfo?.email || "Sesión activa"}
                  </p>
                </div>

                {isLinkedinConnected && (
                  <button
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      handleDisconnectLinkedin();
                    }}
                    className="w-full flex items-center gap-2 2xl:gap-2.5 px-3.5 2xl:px-4 py-2 2xl:py-2.5 text-xs 2xl:text-sm text-slate-300 hover:bg-[#3D3536] transition-colors text-left cursor-pointer"
                  >
                    <User className="h-3.5 w-3.5 2xl:h-4 2xl:w-4 text-slate-400" />
                    <span>Desconectar LinkedIn</span>
                  </button>
                )}

                <button
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    handleLogout();
                  }}
                  className="w-full flex items-center gap-2 2xl:gap-2.5 px-3.5 2xl:px-4 py-2 2xl:py-2.5 text-xs 2xl:text-sm text-rose-400 hover:bg-rose-950/30 transition-colors text-left cursor-pointer font-medium"
                >
                  <LogOut className="h-3.5 w-3.5 2xl:h-4 2xl:w-4 text-rose-400" />
                  <span>Cerrar sesión</span>
                </button>
              </div>
            )}
          </div>

          {/* Mobile Nav Toggle */}
          <button
            onClick={() => setIsMobileNavOpen(!isMobileNavOpen)}
            className="md:hidden p-1.5 text-slate-300 hover:bg-white/10 rounded-lg text-white"
            aria-label="Abrir menú de navegación móvil"
          >
            {isMobileNavOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Navigation Drawer */}
      {isMobileNavOpen && (
        <div className="md:hidden border-t border-[#3E3637] bg-[#2E2829] px-4 py-3 flex flex-col gap-1 text-white">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setIsMobileNavOpen(false);
                }}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold text-left ${
                  isActive
                    ? "bg-[#2B8385] text-white font-bold"
                    : "text-slate-300 hover:bg-white/10"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? "text-white" : "text-slate-400"}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </header>
  );
}
