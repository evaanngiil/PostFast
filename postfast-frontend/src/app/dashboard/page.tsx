/* eslint-disable react/no-unescaped-entities */
"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  CheckCircle,
  BookOpen,
  Send,
  Loader2,
  Layers,
  RefreshCw,
  Eye,
  Edit3,
  ThumbsUp,
  Calendar,
  Building,
  Check,
  AlertCircle,
  Wand2,
  FileText,
  Upload,
  Trash2,
  LogOut,
  ChevronDown,
  XCircle,
  Copy
} from "lucide-react";
import { renderMarkdown, parseInlineMarkdown } from "@/lib/markdown";
import Toast from "./components/Toast";
import AgentPipeline from "./components/AgentPipeline";
import AgentTerminal from "./components/AgentTerminal";
import { FactCheckCard, SafetyGuardCard } from "./components/AuditReports";
import ScheduleModal from "./components/ScheduleModal";
import PublishStatusModal from "./components/PublishStatusModal";
import { useToast } from "./hooks/useToast";
import { useAgentLog } from "./hooks/useAgentLog";
import { useSkills } from "./hooks/useSkills";
import { useHistory } from "./hooks/useHistory";
import { useKnowledgeBase } from "./hooks/useKnowledgeBase";
import { useContentGeneration } from "./hooks/useContentGeneration";

export default function PostFastDashboard() {
  // Navigation
  const [activeTab, setActiveTab] = useState<"dashboard" | "generator" | "company" | "rag" | "history" | "skills">("generator");
  

  // Auth & Organizations
  const [isTenantDropdownOpen, setIsTenantDropdownOpen] = useState(false);
  const tenantDropdownRef = useRef<HTMLDivElement>(null);

  const [authToken, setAuthToken] = useState<string>("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<any[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<any>(null);
  const [authProvider, setAuthProvider] = useState<string>("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isLoadingCompanies, setIsLoadingCompanies] = useState<boolean>(false);
  const [isSyncingCompany, setIsSyncingCompany] = useState<boolean>(false);
  const [isLinkedinConnected, setIsLinkedinConnected] = useState<boolean>(false);

  // Estado de UI que permanece en la página (modales de detalle y opciones)
  const [viewPostData, setViewPostData] = useState<any>(null);
  const [isViewPostModalOpen, setIsViewPostModalOpen] = useState<boolean>(false);
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);

  // Config & WebSocket
  const [supabaseConfig, setSupabaseConfig] = useState<any>(null);

  // Notificaciones y registro de agentes (hooks de dominio transversal)
  const { toast: toastMessage, showToast, clearToast } = useToast();
  const { logs: terminalLogs, addLog, clearLogs } = useAgentLog(showToast);

  // Dominio de Habilidades (skills)
  const {
    skills, setSkills, selectedSkillId, setSelectedSkillId, selectedSkillIds, setSelectedSkillIds,
    isSkillDropdownOpen, setIsSkillDropdownOpen, newSkillName, setNewSkillName,
    newSkillDesc, setNewSkillDesc, newSkillMarkdown, setNewSkillMarkdown,
    activeWorkspaceSkill, setActiveWorkspaceSkill, workspaceSkillName, setWorkspaceSkillName,
    workspaceSkillDesc, setWorkspaceSkillDesc, workspaceSkillMarkdown, setWorkspaceSkillMarkdown,
    loadSkills, handleCreateSkill, handleDeleteSkill, handleUpdateSkill,
  } = useSkills({ authToken, orgUrn: selectedCompany?.urn, showToast });

  // Dominio del historial de publicaciones
  const { postsHistory, setPostsHistory, isLoadingHistory, loadHistory } = useHistory({
    authToken, orgUrn: selectedCompany?.urn,
  });

  // Dominio de la Base de Conocimiento (RAG)
  const {
    pdfDocuments, setPdfDocuments, isUploadingPdf,
    ragContent, setRagContent, isLoadingRag,
    brandBookText, setBrandBookText,
    localDos, setLocalDos, localDonts, setLocalDonts,
    newDoText, setNewDoText, newDontText, setNewDontText,
    editingDoIndex, setEditingDoIndex, editingDoText, setEditingDoText,
    editingDontIndex, setEditingDontIndex, editingDontText, setEditingDontText,
    isSavingBrandAssets,
    localAboutUs, setLocalAboutUs, localSpecialties, setLocalSpecialties,
    newSpecialtyText, setNewSpecialtyText, isEditingAboutUs, setIsEditingAboutUs,
    ragUrls, setRagUrls, urlToAdd, setUrlToAdd, isIngestingUrl,
    ragPosts, setRagPosts, isLoadingRagPosts,
    engagementMetrics, setEngagementMetrics, isLoadingMetrics,
    selectedDocName, selectedDoc, setSelectedDoc, isDocModalOpen, setIsDocModalOpen, docContentLoading,
    loadCompanyDocuments, handleUploadPdf, handleDeleteDocument,
    loadRagKnowledge, loadBrandAssets, loadRagUrls, handleAddUrl, handleDeleteUrl,
    loadRagPosts, loadEngagementMetrics, loadDocumentContent, handleSaveBrandAssets,
  } = useKnowledgeBase({ authToken, orgUrn: selectedCompany?.urn, addLog });

  // Núcleo de generación de contenido (form + pipeline + realtime + HITL + acciones)
  const {
    promptQuery, setPromptQuery, selectedTone, setSelectedTone,
    linkUrl, setLinkUrl,
    editingPost, setEditingPost, editInstruction, setEditInstruction,
    taskId, setTaskId, taskStatus, isGenerating, draftContent, setDraftContent,
    draftHashtags, draftCta, factCheck, setFactCheck, safetyReport, setSafetyReport,
    knowledgeGap,
    userFeedback, setUserFeedback, checkpointConfig, isSubmittingFeedback,
    activeAgent, agentSteps, submittedPrompt, showFullPrompt, setShowFullPrompt,
    currentPostId, setCurrentPostId, currentThreadId, setCurrentThreadId,
    pendingAction, setPendingAction, pendingActionRef,
    isScheduleModalOpen, setIsScheduleModalOpen, schedulePostData, setSchedulePostData,
    scheduleDate, setScheduleDate, isPublishStatusModalOpen, setIsPublishStatusModalOpen, publishStatus,
    handleGeneratePost, handleResumeWorkflow, handleStopGeneration, resetGeneratorState,
    handleEditPost, handleDeletePost, handlePublishNow, handleSaveDraft, submitSchedule, handleScheduleDialog,
  } = useContentGeneration({
    authToken, selectedCompany, supabaseConfig, selectedSkillIds,
    addLog, clearLogs, loadHistory, loadRagPosts, setActiveTab,
  });

  // 1. Cargar sesión de cookies y verificar Backend Config
  useEffect(() => {
    const getCookie = (name: string) => {
      const value = `; ${document.cookie}`;
      const parts = value.split(`; ${name}=`);
      if (parts.length === 2) return parts.pop()?.split(';').shift();
      return null;
    };
    
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get("auth_token");
    const isLinkedFromRedirect = urlParams.get("linkedin_connected");
    
    const cookieToken = getCookie("aipost_session_id");
    const localToken = localStorage.getItem("aipost_session_token");
    const token = urlToken || cookieToken || localToken;
    console.log("Dashboard mount - URL Token:", urlToken, "Cookie Token:", cookieToken, "Local Token:", localToken, "Selected Token:", token);
    
    if (urlToken) {
      document.cookie = `aipost_session_id=${urlToken}; path=/; max-age=604800; samesite=lax`;
      localStorage.setItem("aipost_session_token", urlToken);
    }
    
    if (urlToken || isLinkedFromRedirect) {
      // Clean query parameters from URL bar
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, document.title, cleanUrl);
    }
    
    if (token) {
      console.log("Token found, setting state.");
      if (!cookieToken) {
        document.cookie = `aipost_session_id=${token}; path=/; max-age=604800; samesite=lax`;
      }
      localStorage.setItem("aipost_session_token", token);
      setAuthToken(token);
    } else {
      console.warn("No token found in dashboard");
      setAuthError("No se ha detectado ninguna sesión activa. Por favor, inicia sesión.");
    }

    fetch("http://localhost:8000/config")
      .then(r => {
        if (!r.ok) throw new Error("API Offline");
        return r.json();
      })
      .then(data => {
        setSupabaseConfig(data);
        addLog("SISTEMA", "Conexión con el backend establecida. Realtime configurado.", "success");
      })
      .catch(err => {
        console.error(err);
        addLog("SISTEMA", "No se pudo conectar con el backend de FastAPI en localhost:8000. Por favor, inicia uvicorn.", "error");
      });
  }, []);

  // 1.5 Click outside to close tenant dropdown popover
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (tenantDropdownRef.current && !tenantDropdownRef.current.contains(event.target as Node)) {
        setIsTenantDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // 2. Verificar estado de onboarding y cargar datos
  useEffect(() => {
    if (!authToken) {
      console.log("useEffect [authToken] triggered but authToken is empty.");
      return;
    }

    console.log("Verifying token with /auth/me:", authToken.substring(0, 10) + "...");
    // Verificar perfil y onboarding
    fetch("http://localhost:8000/auth/me", {
      headers: { "Authorization": `Bearer ${authToken}` }
    })
      .then(r => {
        if (!r.ok) throw new Error("La API respondió con error " + r.status);
        return r.json();
      })
      .then(data => {
        console.log("/auth/me response in dashboard:", data);
        if (data.authenticated) {
          setAuthProvider(data.provider || "");
          setIsLinkedinConnected(!!data.linkedin_connected);
          if (!data.has_completed_onboarding) {
            console.log("Onboarding not completed. Redirecting to /onboarding");
            window.location.href = "/onboarding";
          } else {
            console.log("Auth & onboarding OK. Loading companies.");
            // Cargar datos del dashboard si la autenticación y onboarding son válidos
            loadCompanies();
          }
        } else {
          console.warn("Auth failed at /auth/me in dashboard. Reason:", data.reason);
          setAuthError(`Sesión no válida o expirada. Razón: ${data.reason || "No autorizado"}`);
        }
      })
      .catch(err => {
        console.error("Error verifying authentication in dashboard:", err);
        setAuthError(`No se pudo verificar la sesión: ${err.message || "Error de red"}`);
      });
  }, [authToken]);




  const handleLogout = async () => {
    try {
      await fetch("http://localhost:8000/auth/logout", {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
    } catch (e) {
      console.error(e);
    }
    document.cookie = "aipost_session_id=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    localStorage.removeItem("aipost_session_token");
    window.location.href = "/login";
  };

  const loadCompanies = async () => {
    setIsLoadingCompanies(true);
    try {
      const res = await fetch("http://localhost:8000/auth/organizations", {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      const data = await res.json();
      if (Array.isArray(data)) {
        const mapped = data.map((org: any) => {
          const urn = org.org_urn || `urn:li:person:${org.user_id}`;
          const name = org.is_personal 
            ? ((org.first_name || org.last_name) ? `${org.first_name || ""} ${org.last_name || ""}`.trim() : "Perfil Personal") 
            : (org.company_name || "Organización sin nombre");
          return {
            ...org,
            urn: urn,
            name: name
          };
        });
        setCompanies(mapped);
        if (mapped.length > 0) {
          const savedUrn = localStorage.getItem("postfast_active_org_urn");
          const found = mapped.find(c => c.urn === savedUrn);
          setSelectedCompany(found || mapped[0]);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingCompanies(false);
    }
  };

  const handleConnectLinkedin = () => {
    window.location.href = `http://localhost:8000/auth/login/linkedin?platform_token=${authToken}`;
  };

  const handleDisconnectLinkedin = async () => {
    try {
      const res = await fetch("http://localhost:8000/auth/linkedin/disconnect", {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) {
        setIsLinkedinConnected(false);
        addLog("SISTEMA", "Cuenta de LinkedIn desconectada correctamente.", "success");
        loadCompanies();
      } else {
        const err = await res.json();
        addLog("ERROR", `No se pudo desconectar LinkedIn: ${err.detail || 'Desconocido'}`, "error");
      }
    } catch (err: any) {
      addLog("ERROR", `Error de red al desconectar LinkedIn: ${err.message}`, "error");
    }
  };

  // NOTA: el 'Catálogo de Servicios' se eliminó del producto — la información
  // de servicios proviene exclusivamente de los PDFs y URLs indexados en el RAG.

  // Disparar sincronización inicial (Ingesta + Simulación de documentos RAG)
  const handleTriggerSync = async () => {
    if (!selectedCompany) return;
    setIsSyncingCompany(true);
    addLog("INGESTOR", `Solicitando extracción batch y simulación RAG para ${selectedCompany.name}...`, "info");
    
    try {
      const res = await fetch("http://localhost:8000/content/company/profiles/trigger_batch", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({
          org_urn: selectedCompany.urn,
          org_name: selectedCompany.name
        })
      });
      
      const data = await res.json();
      if (res.ok && data.task_id) {
        addLog("INGESTOR", `Tarea encolada con éxito. Celery Task ID: ${data.task_id}`, "success");
        setTaskId(data.task_id);
      } else {
        addLog("INGESTOR", `Error al sincronizar: ${data.detail || "Desconocido"}`, "error");
      }
    } catch (err) {
      addLog("INGESTOR", `Fallo de red: ${err}`, "error");
    } finally {
      setIsSyncingCompany(false);
    }
  };

  // eslint-disable-next-line
  useEffect(() => {
    if (selectedCompany && selectedCompany.urn && selectedCompany.urn !== "undefined" && selectedCompany.urn !== "null") {
      loadRagKnowledge(selectedCompany.urn);
      loadSkills(selectedCompany.urn);
      loadCompanyDocuments(selectedCompany.urn);
      loadHistory(selectedCompany.urn);
      loadBrandAssets(selectedCompany.urn);
      loadRagPosts(selectedCompany.urn);
      loadEngagementMetrics(selectedCompany.urn);
      loadRagUrls(selectedCompany.urn);
    } else {
      setRagContent(null);
      setSkills([]);
      setPdfDocuments([]);
      setPostsHistory([]);
      setBrandBookText("");
      setRagPosts([]);
      setEngagementMetrics(null);
      setRagUrls([]);
    }
  }, [selectedCompany]);

  if (authError) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center p-4">
        <div className="bg-white p-8 rounded-3xl shadow-[0_8px_30px_rgba(0,0,0,0.06)] border border-slate-200 text-center max-w-[500px]">
          <div className="w-16 h-16 bg-rose-50 text-rose-500 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-rose-100 animate-pulse">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Problema de Autenticación</h2>
          <p className="text-slate-600 text-sm mb-6 leading-relaxed">{authError}</p>
          <button 
            onClick={() => {
              document.cookie = "aipost_session_id=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; samesite=lax";
              localStorage.removeItem("aipost_session_token");
              window.location.href = "/login";
            }}
            className="w-full bg-gradient-to-r from-brand-teal to-brand-teal-dark text-white font-bold py-3 rounded-xl transition-all shadow-md shadow-brand-teal/20"
          >
            Volver a Iniciar Sesión
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800 font-sans">
      {/* Header Premium Gradients */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-200 px-4 md:px-6 py-4 flex flex-wrap md:flex-nowrap items-center justify-between shadow-sm gap-4">
        <div className="flex items-center gap-3">
          <button 
            className="md:hidden p-2 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          >
            <Layers className="h-5 w-5" />
          </button>
          <img src="/logo.png" alt="AIPost Logo" className="h-14 w-14 object-contain hidden sm:block" />
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-slate-900 via-brand-teal to-brand-teal-dark bg-clip-text text-transparent">
              AIPost
            </h1>
            <p className="text-xs text-slate-500 hidden md:block">Plataforma de Inteligencia Artificial para la Generación de Contenido Corporativo</p>
          </div>
        </div>

        {/* Multi-tenant Selector / LinkedIn Connector with Company Logo Badge */}
        <div className="flex items-center gap-3 ml-auto md:ml-0 relative" ref={tenantDropdownRef}>
          {selectedCompany && (
            <button 
              onClick={() => setIsTenantDropdownOpen(!isTenantDropdownOpen)}
              className="flex items-center gap-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl px-4 py-2 shadow-sm transition-all duration-200 cursor-pointer"
            >
              {selectedCompany.logo_url ? (
                <img 
                  src={selectedCompany.logo_url} 
                  alt={selectedCompany.name} 
                  className="w-7 h-7 rounded-lg object-cover shadow-sm shrink-0 border border-slate-250" 
                />
              ) : (
                <div className="w-7 h-7 bg-gradient-to-br from-brand-teal to-brand-teal-dark rounded-lg flex items-center justify-center text-[11px] font-extrabold text-white uppercase shadow-sm shrink-0">
                  {selectedCompany.name.slice(0, 2)}
                </div>
              )}
              <div className="flex flex-col text-left">
                <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider leading-none">Cuenta Activa</span>
                <span className="text-[12px] font-extrabold text-slate-700 leading-tight mt-0.5 max-w-[120px] sm:max-w-[180px] truncate">
                  {selectedCompany.name}
                </span>
              </div>
              <svg 
                xmlns="http://www.w3.org/2000/svg" 
                className={`h-4 w-4 text-slate-400 transition-transform duration-200 shrink-0 ${isTenantDropdownOpen ? 'rotate-180' : ''}`} 
                fill="none" 
                viewBox="0 0 24 24" 
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          )}

          {isTenantDropdownOpen && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-white/95 backdrop-blur-md rounded-2xl border border-slate-200 shadow-xl py-3 z-50 animate-in fade-in slide-in-from-top-2 duration-200 flex flex-col gap-2">
              <div className="px-4 py-2 border-b border-slate-100 flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Cambiar de Cuenta</span>
                <button 
                  onClick={loadCompanies} 
                  className="p-1 hover:bg-slate-100 rounded-md transition-colors cursor-pointer shrink-0"
                  title="Refrescar cuentas"
                >
                  <RefreshCw className="h-3 w-3 text-slate-500" />
                </button>
              </div>
              <div className="max-h-60 overflow-y-auto pr-1">
                {companies.length === 0 ? (
                  <span className="px-4 py-2 text-xs text-slate-400 italic">Cargando cuentas...</span>
                ) : (
                  companies.map(c => {
                    const isActive = selectedCompany && selectedCompany.urn === c.urn;
                    return (
                      <button 
                        key={c.urn} 
                        onClick={() => {
                          setSelectedCompany(c);
                          localStorage.setItem("postfast_active_org_urn", c.urn);
                          setIsTenantDropdownOpen(false);
                        }}
                        className={`w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 transition-colors text-left ${isActive ? 'bg-slate-50/50' : ''}`}
                      >
                        <div className="flex items-center gap-3">
                          {c.logo_url ? (
                            <img 
                              src={c.logo_url} 
                              alt={c.name} 
                              className="w-6 h-6 rounded-md object-cover border border-slate-200"
                            />
                          ) : (
                            <div className="w-6 h-6 bg-gradient-to-br from-brand-teal to-brand-teal-dark rounded-md flex items-center justify-center text-[9px] font-black text-white uppercase shrink-0">
                              {c.name.slice(0, 2)}
                            </div>
                          )}
                          <div className="flex flex-col">
                            <span className="text-xs font-bold text-slate-700 truncate max-w-[160px]">{c.name}</span>
                            <span className="text-[9px] text-slate-400 font-medium leading-none mt-0.5">
                              {c.is_personal ? "Perfil Personal" : "Página Empresa"}
                            </span>
                          </div>
                        </div>
                        {isActive && (
                          <Check className="h-4 w-4 text-brand-teal shrink-0" />
                        )}
                      </button>
                    );
                  })
                )}
              </div>


            </div>
          )}

          {/* LinkedIn Connector: solo visible cuando NO está conectado.
              (El cierre de sesión de LinkedIn vive discreto en el pie de la sidebar) */}
          {!isLinkedinConnected && (
            <button
              onClick={handleConnectLinkedin}
              className="flex items-center gap-1 md:gap-2 px-2 md:px-3.5 py-1.5 bg-[#0077b5] hover:bg-[#005c8d] text-white text-[10px] md:text-xs font-bold rounded-lg transition-colors cursor-pointer shadow-sm hover:shadow-md shrink-0"
              title="Conectar con tu cuenta de LinkedIn para importar organizaciones"
            >
              <svg className="h-3 md:h-3.5 w-3 md:w-3.5 fill-current" viewBox="0 0 24 24">
                <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.779-1.75-1.75s.784-1.75 1.75-1.75 1.75.779 1.75 1.75-.784 1.75-1.75 1.75zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
              </svg>
              <span className="hidden sm:inline">Conectar LinkedIn</span>
              <span className="sm:hidden">Conectar</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Container Layout */}
      <div className="flex-grow w-full max-w-7xl mx-auto px-4 md:px-6 py-4 md:py-8 flex flex-col md:flex-row gap-6">
        {/* Navigation Sidebar */}
        <aside className={`${isSidebarOpen ? "flex" : "hidden"} md:flex w-full md:w-64 shrink-0 flex-col gap-2`}>
          <div className="p-3 text-xs font-bold text-brand-teal tracking-wider uppercase">Menu Principal</div>
          
          <button 
            onClick={() => setActiveTab("generator")}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
              activeTab === "generator" 
                ? "bg-gradient-to-r from-brand-teal/20 to-brand-teal-dark/10 text-brand-teal border-l-4 border-brand-teal shadow-inner" 
                : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
            }`}
          >
            <Sparkles className="h-4.5 w-4.5" />
            Redactor Agéntico
          </button>
 
          <button 
            onClick={() => setActiveTab("skills")}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
              activeTab === "skills" 
                ? "bg-gradient-to-r from-brand-teal/20 to-brand-teal-dark/10 text-brand-teal border-l-4 border-brand-teal shadow-inner" 
                : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
            }`}
          >
            <Wand2 className="h-4.5 w-4.5" />
            Habilidades (Skills)
          </button>
 
          <button
            onClick={() => setActiveTab("company")}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
              activeTab === "company"
                ? "bg-gradient-to-r from-brand-teal/20 to-brand-teal-dark/10 text-brand-teal border-l-4 border-brand-teal shadow-inner"
                : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
            }`}
          >
            <Building className="h-4.5 w-4.5" />
            Perfil de Empresa
          </button>

          <button
            onClick={() => setActiveTab("rag")}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
              activeTab === "rag"
                ? "bg-gradient-to-r from-brand-teal/20 to-brand-teal-dark/10 text-brand-teal border-l-4 border-brand-teal shadow-inner"
                : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
            }`}
          >
            <BookOpen className="h-4.5 w-4.5" />
            Base de Conocimientos
          </button>
 
          <button 
            onClick={() => setActiveTab("history")}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
              activeTab === "history" 
                ? "bg-gradient-to-r from-brand-teal/20 to-brand-teal-dark/10 text-brand-teal border-l-4 border-brand-teal shadow-inner" 
                : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
            }`}
          >
            <Calendar className="h-4.5 w-4.5" />
            Histórico Editorial
          </button>
 

          {selectedCompany && selectedCompany.urn && selectedCompany.urn !== "undefined" && !selectedCompany.is_personal && (
            <div className="mt-8 p-4 rounded-xl bg-white border border-slate-200 shadow-sm flex flex-col gap-3">
              <div className="flex items-center gap-2">
                {selectedCompany.logo_url ? (
                  <img 
                    src={selectedCompany.logo_url} 
                    alt={selectedCompany.name} 
                    className="h-5 w-5 rounded-md object-cover border border-slate-200 shrink-0"
                  />
                ) : (
                  <div className="h-5 w-5 bg-gradient-to-br from-brand-teal to-brand-teal-dark rounded-md flex items-center justify-center text-[8px] font-black text-white uppercase shrink-0">
                    {selectedCompany.name.slice(0, 2)}
                  </div>
                )}
                <span className="text-xs font-bold text-slate-700">{selectedCompany.name}</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-normal">
                Genera la base de conocimientos vectorial (RAG) de esta empresa simulada (Do's & Don'ts, productos, competidores).
              </p>
              <button 
                onClick={handleTriggerSync}
                disabled={isSyncingCompany}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-brand-teal/10 hover:bg-brand-teal/20 text-brand-teal text-xs font-semibold rounded-lg border border-brand-teal/20 transition-all cursor-pointer"
              >
                {isSyncingCompany ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <RefreshCw className="h-3 w-3" />
                )}
                Sincronizar / Simular RAG
              </button>
            </div>
          )}
          <div className="flex flex-col gap-1 mt-auto">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 text-rose-500 hover:text-rose-700 hover:bg-rose-50 border border-transparent hover:border-rose-100 cursor-pointer"
            >
              <LogOut className="h-4.5 w-4.5" />
              Cerrar Sesión
            </button>
            {/* Cierre de sesión de LinkedIn: discreto a propósito. Cierra SOLO la
                sesión de LinkedIn (la sesión de plataforma sigue activa). */}
            {isLinkedinConnected && (
              <button
                onClick={handleDisconnectLinkedin}
                className="flex items-center gap-2 px-4 py-1.5 text-[11px] font-medium text-slate-400 hover:text-rose-500 transition-colors cursor-pointer"
                title="Cierra únicamente la sesión de LinkedIn; tu sesión de la plataforma sigue activa"
              >
                <svg className="h-3 w-3 fill-current opacity-70" viewBox="0 0 24 24">
                  <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.779-1.75-1.75s.784-1.75 1.75-1.75 1.75.779 1.75 1.75-.784 1.75-1.75 1.75zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                </svg>
                Cerrar sesión de LinkedIn
              </button>
            )}
          </div>
        </aside>
 
        {/* Tab Page Container */}
        <main className="flex-1 w-full max-w-[1920px] mx-auto p-4 md:p-8 flex flex-col gap-6">
          {selectedCompany?.is_personal ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 max-w-3xl mx-auto">
              <div className="bg-white rounded-3xl border border-slate-200 shadow-xl p-8 md:p-10 flex flex-col items-center text-center gap-6 w-full animate-fade-in-up">
                <div className="p-4 bg-brand-teal/10 rounded-full text-brand-teal shadow-inner">
                  <Building className="h-10 w-10" />
                </div>
                
                <div className="flex flex-col gap-2">
                  <h2 className="text-2xl font-bold text-slate-800">Perfil Personal Vinculado</h2>
                  <p className="text-sm text-slate-500 max-w-xl">
                    Este perfil funciona únicamente como tu conector de acceso e identidad en la plataforma.
                  </p>
                </div>

                <div className="flex flex-col gap-3 w-full mt-4">
                  <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">Selecciona una Empresa para comenzar</span>
                  
                  {companies.filter(c => !c.is_personal).length === 0 ? (
                    <div className="text-xs text-slate-400 italic py-4">
                      No tienes páginas de empresa (organizaciones) conectadas. Debes administrar al menos una página de LinkedIn para operar las funciones de IA.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full mt-2">
                      {companies.filter(c => !c.is_personal).map((comp) => (
                        <button
                          key={comp.urn}
                          onClick={() => {
                            setSelectedCompany(comp);
                            localStorage.setItem("postfast_active_org_urn", comp.urn);
                          }}
                          className="flex items-center gap-4 p-5 rounded-2xl border-2 border-slate-100 hover:border-brand-teal bg-gradient-to-tr from-white to-slate-50/50 hover:to-brand-teal/5 transition-all duration-300 text-left shadow-sm hover:shadow-md hover:shadow-brand-teal/5 group cursor-pointer relative overflow-hidden"
                        >
                          {comp.logo_url ? (
                            <img src={comp.logo_url} alt={comp.name} className="h-14 w-14 rounded-xl object-cover border border-slate-200 shadow-sm shrink-0 transition-transform duration-300 group-hover:scale-105" />
                          ) : (
                            <div className="h-14 w-14 bg-gradient-to-br from-brand-teal to-brand-teal-dark rounded-xl flex items-center justify-center text-xl font-black text-white uppercase shadow-sm shrink-0 transition-transform duration-300 group-hover:scale-105">
                              {comp.name.slice(0, 2)}
                            </div>
                          )}
                          <div className="flex flex-col overflow-hidden pr-6">
                            <span className="text-sm font-black text-slate-800 group-hover:text-brand-teal transition-colors truncate">{comp.name}</span>
                            <span className="text-[10px] text-slate-400 font-extrabold uppercase mt-1 tracking-wider">Empresa</span>
                            <span className="text-[10px] text-brand-teal font-bold mt-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                              Activar espacio →
                            </span>
                          </div>
                          
                          {/* Decorative subtle background circle */}
                          <div className="absolute right-0 bottom-0 w-24 h-24 bg-brand-teal/5 rounded-full translate-x-8 translate-y-8 group-hover:bg-brand-teal/10 transition-colors" />
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="w-full border-t border-slate-100 my-4" />

                <div className="p-4 bg-slate-50 border border-slate-150 rounded-2xl text-left flex items-start gap-3 w-full">
                  <AlertCircle className="h-5 w-5 text-brand-teal shrink-0 mt-0.5" />
                  <div className="flex flex-col gap-1">
                    <span className="text-xs font-bold text-slate-700">Restricciones de la API de LinkedIn</span>
                    <p className="text-[11px] text-slate-500 leading-relaxed">
                      Por políticas oficiales de LinkedIn, las cuentas personales tienen restringido el acceso programático a analíticas detalladas y extracción de perfiles. Por ello, las funciones de <strong className="text-slate-700 font-bold">Redactor Agéntico</strong>, <strong className="text-slate-700 font-bold">Habilidades Personalizadas (Skills)</strong> y <strong className="text-slate-700 font-bold">Base de Conocimientos (RAG)</strong> están reservadas exclusivamente para <strong className="text-slate-700 font-bold">Páginas de Empresa (Organizaciones)</strong>.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <>
              {/* TAB 1: GENERATOR TAB */}
              {activeTab === "generator" && (
            <div className="flex flex-col gap-6">
              {/* Form Input Card */}
              {(!draftContent && !isGenerating && taskStatus !== "PENDING_USER_INPUT") && (
                editingPost ? (
                /* DEDICATED EDIT MODE FORM */
                <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col gap-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                      <Sparkles className="h-5 w-5 text-brand-teal animate-pulse" />
                      Editar Publicación con Inteligencia Artificial
                    </h2>
                    <button
                      onClick={() => {
                        setEditingPost(null);
                        setEditInstruction("");
                        setCurrentPostId(null);
                        setCurrentThreadId(null);
                      }}
                      className="text-xs font-semibold text-slate-500 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                    >
                      Cancelar Edición
                    </button>
                  </div>
                  
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Left Column: Original Post Preview */}
                    <div className="flex flex-col gap-2 bg-slate-50 rounded-xl p-4 border border-slate-100">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Publicación Original (Solo Lectura)</span>
                        <span className="text-[10px] bg-slate-200/80 text-slate-600 px-2 py-0.5 rounded-full font-bold uppercase">Lectura</span>
                      </div>
                      <div className="text-sm text-slate-700 whitespace-pre-wrap font-medium flex-1 overflow-y-auto max-h-[300px] pr-2 bg-white rounded-lg p-3 border border-slate-200/60 mt-1">
                        {editingPost.content}
                      </div>
                    </div>

                    {/* Right Column: AI Improvement Input */}
                    <div className="flex flex-col gap-4">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">¿Qué cambios o mejoras quieres aplicar?</label>
                        <textarea 
                          value={editInstruction}
                          onChange={(e) => setEditInstruction(e.target.value)}
                          rows={6}
                          className="bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all resize-none font-medium"
                          placeholder="Ej: Haz el tono más profesional, reduce los párrafos a la mitad y añade 3 hashtags relevantes de tecnología..."
                        />
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="flex flex-col gap-1.5">
                          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Tono (Opcional)</label>
                          <input
                            type="text"
                            value={selectedTone}
                            onChange={(e) => setSelectedTone(e.target.value)}
                            className="bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all font-medium"
                            placeholder="Ej. Técnico, Cercano..."
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col gap-4 border-t border-slate-100 pt-4">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Habilidad (Skill) - Opcional</label>
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() => setIsSkillDropdownOpen(!isSkillDropdownOpen)}
                            className="w-full flex items-center justify-between bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all font-medium cursor-pointer shadow-sm text-left"
                          >
                            <span className="truncate text-slate-700">
                              {selectedSkillIds.length === 0
                                ? "Ninguna (Redacción libre - Solo base)"
                                : selectedSkillIds.length === 1
                                ? `${skills.find(s => s.id === selectedSkillIds[0])?.name || "1 Habilidad activa"}`
                                : `${selectedSkillIds.length} Habilidades activas`}
                            </span>
                            <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform duration-200 ${isSkillDropdownOpen ? "rotate-180" : ""}`} />
                          </button>

                          {isSkillDropdownOpen && (
                            <>
                              <div className="fixed inset-0 z-10" onClick={() => setIsSkillDropdownOpen(false)} />
                              <div className="absolute left-0 right-0 mt-2 bg-white border border-slate-200 rounded-xl shadow-xl z-20 max-h-60 overflow-y-auto p-2 flex flex-col gap-1">
                                <div className="flex justify-between items-center px-2 py-1 pb-2 border-b border-slate-100">
                                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Habilidades Tácticas</span>
                                  {selectedSkillIds.length > 0 && (
                                    <button 
                                      type="button"
                                      onClick={() => setSelectedSkillIds([])}
                                      className="text-[10px] font-bold text-rose-500 hover:text-rose-600 transition-colors cursor-pointer"
                                    >
                                      Limpiar todo
                                    </button>
                                  )}
                                </div>
                                <div className="pt-1 flex flex-col gap-0.5">
                                  {skills.filter(s => s.name !== "Guía de Estilo y Generación (Base)").length === 0 ? (
                                    <span className="text-xs text-slate-400 italic px-2 py-1.5">No hay habilidades personalizadas</span>
                                  ) : (
                                    skills.filter(s => s.name !== "Guía de Estilo y Generación (Base)").map(s => {
                                      const isSelected = selectedSkillIds.includes(s.id);
                                      return (
                                        <label 
                                          key={s.id} 
                                          className="flex items-start gap-2.5 px-2.5 py-2 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors"
                                        >
                                          <input 
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={() => {
                                              if (isSelected) {
                                                setSelectedSkillIds(selectedSkillIds.filter(id => id !== s.id));
                                              } else {
                                                setSelectedSkillIds([...selectedSkillIds, s.id]);
                                              }
                                            }}
                                            className="mt-0.5 rounded border-slate-300 text-brand-teal focus:ring-brand-teal h-4 w-4 cursor-pointer"
                                          />
                                          <div className="flex flex-col">
                                            <span className="text-xs font-bold text-slate-700">{s.name}</span>
                                            {s.description && <span className="text-[10px] text-slate-400 mt-0.5 font-medium line-clamp-1">{s.description}</span>}
                                          </div>
                                        </label>
                                      );
                                    })
                                  )}
                                </div>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">URL de Referencia (Opcional)</label>
                        <input 
                          type="text" 
                          value={linkUrl}
                          onChange={(e) => setLinkUrl(e.target.value)}
                          className="bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all font-medium font-mono"
                          placeholder="http://..."
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-between items-center mt-2 border-t border-slate-100 pt-4">
                    <p className="text-xs text-slate-400 font-medium max-w-lg">
                      Los agentes usarán el contexto del post y la conversación previa del hilo para aplicar tus mejoras.
                    </p>
                    <button 
                      onClick={handleGeneratePost}
                      disabled={isGenerating || !editInstruction.trim()}
                      className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-brand-teal to-brand-teal-dark hover:from-brand-teal hover:to-brand-teal-dark text-white font-semibold rounded-xl text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-brand-teal/20 cursor-pointer animate-fade-in"
                    >
                      {isGenerating ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Mejorando Post...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" />
                          Aplicar Mejoras con IA
                        </>
                      )}
                    </button>
                  </div>
                </section>
                ) : (
                /* STANDARD FREE GENERATION FORM */
                <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col gap-4">
                  <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-brand-teal" />
                    ¿De qué quieres hablar hoy en LinkedIn?
                  </h2>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5 md:col-span-2">
                      <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Idea o Temática del Post</label>
                      <textarea
                        value={promptQuery}
                        onChange={(e) => setPromptQuery(e.target.value)}
                        rows={3}
                        className="bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all resize-none font-medium"
                        placeholder="Escribe la idea general... (ej. 'Anuncia nuestro nuevo servicio de riego inteligente destacando el ahorro de agua')"
                      />
                    </div>

                    <div className="flex flex-col gap-1.5 md:col-span-2">
                      <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Habilidades Tácticas Seleccionadas (Opcional)</label>
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() => setIsSkillDropdownOpen(!isSkillDropdownOpen)}
                          className="w-full flex items-center justify-between bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all font-medium cursor-pointer shadow-sm text-left"
                        >
                          <span className="truncate text-slate-700">
                            {selectedSkillIds.length === 0
                              ? "Ninguna (Redacción libre - Solo base)"
                              : selectedSkillIds.length === 1
                              ? `${skills.find(s => s.id === selectedSkillIds[0])?.name || "1 Habilidad activa"}`
                              : `${selectedSkillIds.length} Habilidades activas`}
                          </span>
                          <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform duration-200 ${isSkillDropdownOpen ? "rotate-180" : ""}`} />
                        </button>

                        {isSkillDropdownOpen && (
                          <>
                            <div className="fixed inset-0 z-10" onClick={() => setIsSkillDropdownOpen(false)} />
                            <div className="absolute left-0 right-0 mt-2 bg-white border border-slate-200 rounded-xl shadow-xl z-20 max-h-60 overflow-y-auto p-2 flex flex-col gap-1">
                              <div className="flex justify-between items-center px-2 py-1 pb-2 border-b border-slate-100">
                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Habilidades Tácticas</span>
                                {selectedSkillIds.length > 0 && (
                                  <button 
                                    type="button"
                                    onClick={() => setSelectedSkillIds([])}
                                    className="text-[10px] font-bold text-rose-500 hover:text-rose-600 transition-colors cursor-pointer"
                                  >
                                    Limpiar todo
                                  </button>
                                )}
                              </div>
                              <div className="pt-1 flex flex-col gap-0.5">
                                {skills.filter(s => s.name !== "Guía de Estilo y Generación (Base)").length === 0 ? (
                                  <span className="text-xs text-slate-400 italic px-2 py-1.5">No hay habilidades personalizadas</span>
                                ) : (
                                  skills.filter(s => s.name !== "Guía de Estilo y Generación (Base)").map(s => {
                                    const isSelected = selectedSkillIds.includes(s.id);
                                    return (
                                      <label 
                                        key={s.id} 
                                        className="flex items-start gap-2.5 px-2.5 py-2 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors"
                                      >
                                        <input 
                                          type="checkbox"
                                          checked={isSelected}
                                          onChange={() => {
                                            if (isSelected) {
                                              setSelectedSkillIds(selectedSkillIds.filter(id => id !== s.id));
                                            } else {
                                              setSelectedSkillIds([...selectedSkillIds, s.id]);
                                            }
                                          }}
                                          className="mt-0.5 rounded border-slate-300 text-brand-teal focus:ring-brand-teal h-4 w-4 cursor-pointer"
                                        />
                                        <div className="flex flex-col">
                                          <span className="text-xs font-bold text-slate-700">{s.name}</span>
                                          {s.description && <span className="text-[10px] text-slate-400 mt-0.5 font-medium line-clamp-1">{s.description}</span>}
                                        </div>
                                      </label>
                                    );
                                  })
                                )}
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                      {selectedSkillIds.length > 0 && (
                         <div className="mt-2 bg-brand-teal/10 border border-brand-teal/20 p-3 rounded-lg text-xs text-brand-teal italic">
                           Aplicando reglas de escritura de las habilidades seleccionadas ({selectedSkillIds.length}).
                         </div>
                      )}
                    </div>
                    {/* Opciones avanzadas plegadas: la vista inicial queda limpia (petición + skills) */}
                    <div className="flex flex-col gap-2 md:col-span-2">
                      <button
                        type="button"
                        onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
                        className="flex items-center gap-1.5 text-xs font-bold text-slate-400 hover:text-slate-600 transition-colors cursor-pointer self-start"
                      >
                        <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${showAdvancedOptions ? "rotate-180" : ""}`} />
                        Opciones avanzadas {linkUrl && <span className="text-brand-teal">(configuradas)</span>}
                      </button>

                      {showAdvancedOptions && (
                        <div className="grid grid-cols-1 gap-4 bg-slate-50 border border-slate-100 rounded-xl p-4 animate-fade-in">
                          <div className="flex flex-col gap-1.5">
                            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">URL de Referencia</label>
                            <input
                              type="text"
                              value={linkUrl}
                              onChange={(e) => setLinkUrl(e.target.value)}
                              className="bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all font-medium font-mono"
                              placeholder="http://..."
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex justify-end mt-2">
                    <button 
                      onClick={handleGeneratePost}
                      disabled={isGenerating}
                      className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-brand-teal to-brand-teal-dark hover:from-brand-teal hover:to-brand-teal-dark text-white font-semibold rounded-xl text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-brand-teal/20 cursor-pointer"
                    >
                      {isGenerating ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Ejecutando Agentes...
                        </>
                      ) : (
                        <>
                          <Send className="h-4 w-4" />
                          Generar Post Asistido
                        </>
                      )}
                    </button>
                  </div>
                </section>
                )
              )}

              {/* Petición original anclada (vista de ejecución y vista final) */}
              {submittedPrompt && (isGenerating || ((taskStatus === "PENDING_USER_INPUT" || taskStatus === "COMPLETED") && draftContent)) && (
                <section className="bg-white rounded-2xl border border-slate-200 shadow-sm px-5 py-4 flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Send className="h-3.5 w-3.5 text-brand-teal" />
                      Tu petición
                      {isGenerating && (
                        <span className="flex items-center gap-1.5 text-[10px] font-bold text-brand-teal ml-2">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          EN PROCESO
                        </span>
                      )}
                    </span>
                    {/* Detener visible durante todo el proceso (el 'Volver al inicio'
                        vive en la cabecera del resultado, más visible) */}
                    {isGenerating && (
                      <button
                        onClick={handleStopGeneration}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-[11px] font-bold shadow-sm transition-colors cursor-pointer shrink-0"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Detener
                      </button>
                    )}
                  </div>
                  <p className="text-sm text-slate-700 font-medium whitespace-pre-wrap leading-relaxed">
                    {showFullPrompt || submittedPrompt.length <= 180
                      ? submittedPrompt
                      : `${submittedPrompt.slice(0, 180)}…`}
                  </p>
                  {submittedPrompt.length > 180 && (
                    <button
                      type="button"
                      onClick={() => setShowFullPrompt(!showFullPrompt)}
                      className="text-[11px] font-bold text-brand-teal hover:text-brand-teal-dark transition-colors cursor-pointer self-start"
                    >
                      {showFullPrompt ? "Mostrar menos ▲" : "Mostrar más ▼"}
                    </button>
                  )}
                </section>
              )}

              {/* Visualizador del pipeline agéntico (fases reales del grafo) */}
              {isGenerating && (
                <AgentPipeline
                  isEditing={!!editingPost}
                  agentSteps={agentSteps}
                  activeAgent={activeAgent}
                  onStop={handleStopGeneration}
                />
              )}

              {/* Terminal en tiempo real de los broadcasts (oculto en la vista final). */}
              {terminalLogs.length > 0 && (isGenerating || taskStatus === "FAILED") && (
                <AgentTerminal logs={terminalLogs} taskStatus={taskStatus} />
              )}

              {/* Interactive HITL Editor (When suspended in PENDING_USER_INPUT or COMPLETED) */}
              {/* Vista final: resultado expandido a ancho completo; auditorías debajo en horizontal */}
              {(taskStatus === "PENDING_USER_INPUT" || taskStatus === "COMPLETED") && draftContent && (
                <section className="flex flex-col gap-6">
                  {/* Aviso de vacío de conocimiento: la petición pedía información
                      específica que NO existe verificada en la base -> el post es general. */}
                  {knowledgeGap?.has_gap && (
                    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-start gap-3">
                      <AlertCircle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                      <div className="flex flex-col gap-1.5 flex-1">
                        <span className="text-sm font-bold text-amber-900">Información verificada insuficiente</span>
                        <p className="text-xs text-amber-800 leading-normal">
                          {knowledgeGap.user_message
                            || `No hay información verificada en tu base de conocimiento sobre ${knowledgeGap.missing_info || "esta petición"}. El post se ha redactado de forma general; añade documentos o enlaces para un contenido específico y contrastado.`}
                        </p>
                        <button
                          onClick={() => setActiveTab("rag")}
                          className="self-start mt-1 flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-[11px] font-bold shadow-sm transition-colors cursor-pointer"
                        >
                          <BookOpen className="h-3.5 w-3.5" />
                          Añadir información a la base de conocimiento
                        </button>
                      </div>
                    </div>
                  )}
                  {/* Post Editor (ancho completo) */}
                  <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col gap-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <h3 className="font-bold text-slate-800 flex items-center gap-2 text-sm">
                        <Edit3 className="h-4.5 w-4.5 text-brand-teal" />
                        {taskStatus === "COMPLETED" ? "PUBLICACIÓN GENERADA Y APROBADA" : "BORRADOR GENERADO (EDITAR O DAR FEEDBACK)"}
                        <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider ml-1 ${
                          taskStatus === "COMPLETED"
                            ? "bg-emerald-100 border-emerald-200 text-emerald-800"
                            : "bg-amber-100 border-amber-200 text-amber-800"
                        }`}>
                          {taskStatus === "COMPLETED" ? "Aprobado" : "Revisión"}
                        </span>
                      </h3>
                      {/* Volver al inicio: prominente y siempre visible en la vista de resultado */}
                      <button
                        onClick={resetGeneratorState}
                        className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-bold shadow-md transition-colors cursor-pointer shrink-0"
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        Volver al inicio
                      </button>
                    </div>

                    {/* Editor único y prominente: lo generado es el protagonista.
                        Editable directamente, sin pestañas ni vista markdown. */}
                    <div className="flex flex-col gap-2">
                      <textarea
                        value={draftContent}
                        onChange={(e) => setDraftContent(e.target.value)}
                        className="w-full bg-slate-50 focus:bg-white border border-slate-200 rounded-xl p-5 text-[15px] font-medium leading-relaxed text-slate-800 focus:outline-none focus:border-brand-teal focus:ring-[3px] focus:ring-brand-teal/10 transition-all min-h-[360px] resize-y"
                        placeholder="El contenido generado aparecerá aquí..."
                      />
                      <div className="flex items-center justify-between px-1">
                        <span className="text-[11px] text-slate-400 font-medium">
                          ✍️ Puedes editar el texto directamente antes de guardar, programar o publicar.
                        </span>
                        <div className="flex items-center gap-3">
                          <span className={`text-[11px] font-bold ${
                            draftContent.length > 3000 ? "text-rose-500" : "text-slate-400"
                          }`}>
                            {draftContent.length.toLocaleString()} / 3.000
                          </span>
                          <button
                            type="button"
                            onClick={() => {
                              navigator.clipboard.writeText(draftContent);
                              showToast("Post copiado al portapapeles.", "success");
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg text-[11px] font-bold transition-colors cursor-pointer"
                          >
                            <Copy className="h-3.5 w-3.5" />
                            Copiar
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Feedback Form / Completed Info Box */}
                    {taskStatus === "PENDING_USER_INPUT" ? (
                      <div className="flex flex-col gap-2 bg-slate-50 p-4 rounded-xl border border-slate-200">
                        <label className="text-[11px] font-bold text-slate-500 uppercase">Feedback o correcciones para los agentes</label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={userFeedback}
                            onChange={(e) => setUserFeedback(e.target.value)}
                            placeholder="Ej. Cambia el tercer punto para mencionar que el despliegue es en Kubernetes..."
                            className="flex-1 bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:border-brand-teal"
                          />
                          <button
                            onClick={() => handleResumeWorkflow(userFeedback)}
                            disabled={!userFeedback.trim() || isSubmittingFeedback}
                            className="flex items-center gap-1.5 px-4 py-2 bg-brand-teal hover:bg-brand-teal text-white text-xs font-bold rounded-lg transition-colors cursor-pointer disabled:opacity-40"
                          >
                            Corregir
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-xs text-emerald-800 flex flex-col gap-1.5 shadow-sm">
                        <span className="font-bold flex items-center gap-1.5">
                          <CheckCircle className="h-4 w-4" />
                          ¡Generación Completada Correctamente!
                        </span>
                        <span>El post ha sido aprobado y está listo. Puedes guardarlo como borrador, programarlo o publicarlo ahora. Si lo deseas, puedes editar el texto directamente en el panel superior antes de realizar cualquiera de estas acciones.</span>
                      </div>
                    )}

                    {/* Buttons */}
                    <div className="flex flex-wrap items-center gap-3 mt-2">
                      <button
                        onClick={() => {
                          if (taskStatus === "COMPLETED") {
                            handleSaveDraft({ account_id: selectedCompany?.urn, content: draftContent });
                          } else {
                            pendingActionRef.current = "save_draft";
                            handleResumeWorkflow("aprobar");
                          }
                        }}
                        disabled={isSubmittingFeedback}
                        className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 font-bold rounded-xl text-xs shadow-sm transition-colors cursor-pointer"
                      >
                        <FileText className="h-4 w-4" />
                        Guardar Borrador
                      </button>
                      <button
                        onClick={() => {
                          if (taskStatus === "COMPLETED") {
                            handleScheduleDialog({ account_id: selectedCompany?.urn, content: draftContent });
                          } else {
                            pendingActionRef.current = "schedule";
                            handleResumeWorkflow("aprobar");
                          }
                        }}
                        disabled={isSubmittingFeedback}
                        className="flex items-center gap-2 px-4 py-2.5 bg-white border border-brand-teal text-brand-teal hover:bg-brand-teal/5 font-bold rounded-xl text-xs shadow-sm transition-colors cursor-pointer"
                      >
                        <Calendar className="h-4 w-4" />
                        Programar
                      </button>
                      <button
                        onClick={() => {
                          if (taskStatus === "COMPLETED") {
                            handlePublishNow({ account_id: selectedCompany?.urn, content: draftContent });
                          } else {
                            pendingActionRef.current = "publish_now";
                            handleResumeWorkflow("aprobar");
                          }
                        }}
                        disabled={isSubmittingFeedback}
                        className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl text-xs shadow-lg shadow-emerald-600/10 cursor-pointer"
                      >
                        <ThumbsUp className="h-4 w-4" />
                        Publicar Ahora
                      </button>
                      {/* El reinicio vive en el botón persistente "Volver al inicio" de la tarjeta de petición */}
                    </div>
                  </div>

                  {/* Auditorías: CRAG y Compliance en disposición horizontal bajo el resultado */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                    {factCheck && <FactCheckCard report={factCheck} />}
                    {safetyReport && <SafetyGuardCard report={safetyReport} />}
                  </div>
                </section>
              )}
            </div>
          )}

          {/* TAB 2: KNOWLEDGE BASE RAG EXPLORER */}
          {/* TAB: PERFIL DE EMPRESA (Información, identidad y métricas) */}
          {activeTab === "company" && (
            <div className="flex flex-col gap-8">
              {isLoadingRag ? (
                <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-16 flex flex-col items-center justify-center gap-4 text-slate-500">
                  <Loader2 className="h-10 w-10 text-brand-teal animate-spin" />
                  <span className="text-sm font-semibold tracking-wide text-slate-600">Cargando el perfil de la empresa...</span>
                </div>
              ) : ragContent ? (
                <div className="flex flex-col gap-8">

                  {/* Premium Company Header & Actions */}
                  {(() => {
                    const profile = ragContent.company_profile || ragContent.company_profile_data || {};
                    return (
                      <div className="flex flex-col gap-6">
                        {/* Title Row */}
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                          <div className="flex items-center gap-4">
                            {selectedCompany?.logo_url ? (
                              <img
                                src={selectedCompany.logo_url}
                                alt={selectedCompany.name}
                                className="h-16 w-16 rounded-2xl object-cover border border-slate-200/80 shadow-md shrink-0 bg-white"
                              />
                            ) : (
                              <div className="h-16 w-16 bg-gradient-to-tr from-brand-teal to-brand-teal-dark rounded-2xl flex items-center justify-center text-xl font-black text-white uppercase shrink-0 shadow-md">
                                {selectedCompany ? selectedCompany.name.slice(0, 2) : "PF"}
                              </div>
                            )}
                            <div>
                              <div className="flex items-center gap-2">
                                <h1 className="text-2xl font-black text-slate-800 tracking-tight">
                                  {selectedCompany ? selectedCompany.name : "Perfil de Empresa"}
                                </h1>
                                <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 uppercase tracking-wide">
                                  {selectedCompany?.is_personal ? "Personal" : "Empresa"}
                                </span>
                              </div>
                              <p className="text-xs text-slate-500 mt-1 font-medium">
                                Información de la empresa & métricas de LinkedIn (Haz clic en la descripción para editar)
                              </p>
                            </div>
                          </div>

                          {/* Top-Right Quick Actions */}
                          <div className="flex items-center gap-3">
                            <button
                              onClick={handleSaveBrandAssets}
                              disabled={isSavingBrandAssets}
                              className="px-5 py-2.5 bg-brand-teal hover:bg-brand-teal-dark text-white rounded-xl font-bold text-xs transition-all shadow-md disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
                            >
                              {isSavingBrandAssets ? (
                                <>
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  Guardando...
                                </>
                              ) : (
                                "Guardar Todos los Cambios"
                              )}
                            </button>
                          </div>
                        </div>

                        {/* Misión y Especialidades Row (Editable!) */}
                        <div className="flex flex-col gap-4 border-l-3 border-brand-teal/30 pl-5 py-1 bg-slate-50/40 p-4 rounded-r-2xl border border-slate-200/40">
                          {isEditingAboutUs ? (
                            <div className="flex flex-col gap-2 max-w-4xl">
                              <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider">Editar Descripción (Misión / Acerca de)</span>
                              <textarea
                                value={localAboutUs}
                                onChange={(e) => setLocalAboutUs(e.target.value)}
                                rows={4}
                                className="bg-white border border-slate-200 rounded-xl p-3 text-sm text-slate-700 focus:outline-none focus:border-brand-teal w-full resize-y font-medium shadow-sm"
                                placeholder="Escribe la misión o descripción de la empresa..."
                              />
                              <button
                                onClick={() => setIsEditingAboutUs(false)}
                                className="self-end px-4 py-2 bg-brand-teal text-white text-xs font-bold rounded-lg hover:bg-brand-teal-dark transition-colors cursor-pointer shadow-sm"
                              >
                                Guardar texto en borrador
                              </button>
                            </div>
                          ) : (
                            <div className="group relative max-w-4xl cursor-pointer" onClick={() => setIsEditingAboutUs(true)} title="Haz clic para editar la descripción">
                              <p className="text-slate-600 text-sm leading-relaxed whitespace-pre-wrap font-medium pr-8 hover:text-slate-800 transition-colors">
                                {localAboutUs || "Sin descripción (About Us) disponible. Haz clic aquí para añadir una."}
                              </p>
                              <Edit3 className="h-4 w-4 text-slate-400 absolute right-0 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                          )}

                          {/* Specialties Editor */}
                          <div className="flex flex-wrap gap-1.5 items-center mt-1">
                            <span className="text-[10px] text-slate-400 font-extrabold uppercase tracking-wider mr-2">Especialidades:</span>
                            {localSpecialties.map((spec: string, i: number) => (
                              <span key={i} className="group flex items-center gap-1.5 px-3 py-1 bg-brand-teal/8 text-brand-teal rounded-lg text-xs border border-brand-teal/20 font-bold hover:bg-brand-teal/15 transition-all">
                                {spec}
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setLocalSpecialties(localSpecialties.filter((_, idx) => idx !== i));
                                  }}
                                  className="text-brand-teal/60 hover:text-brand-teal transition-colors font-bold shrink-0 text-sm leading-none"
                                  title="Eliminar especialidad"
                                >
                                  &times;
                                </button>
                              </span>
                            ))}

                            {/* Add Specialty input */}
                            <div className="flex items-center gap-1.5 ml-2">
                              <input
                                type="text"
                                value={newSpecialtyText}
                                onChange={(e) => setNewSpecialtyText(e.target.value)}
                                placeholder="Añadir especialidad..."
                                className="bg-white border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-700 focus:outline-none focus:border-brand-teal h-8 shadow-sm"
                                onKeyDown={(e) => {
                                  if (e.key === "Enter" && newSpecialtyText.trim()) {
                                    if (!localSpecialties.includes(newSpecialtyText.trim())) {
                                      setLocalSpecialties([...localSpecialties, newSpecialtyText.trim()]);
                                    }
                                    setNewSpecialtyText("");
                                  }
                                }}
                              />
                              <button
                                onClick={() => {
                                  if (newSpecialtyText.trim()) {
                                    if (!localSpecialties.includes(newSpecialtyText.trim())) {
                                      setLocalSpecialties([...localSpecialties, newSpecialtyText.trim()]);
                                    }
                                    setNewSpecialtyText("");
                                  }
                                }}
                                className="bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg px-2.5 py-1 text-xs font-bold border border-slate-200 h-8 transition-colors cursor-pointer"
                              >
                                +
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()}

                  {/* LinkedIn Analytics Stat bar */}
                  <div className="bg-gradient-to-r from-slate-50 to-slate-100/50 border border-slate-200 rounded-2xl p-5 shadow-sm">
                    <div className="flex flex-col gap-4">
                      <div className="flex items-center gap-2 text-slate-800 border-b border-slate-200/50 pb-2">
                        <Sparkles className="h-4.5 w-4.5 text-brand-teal" />
                        <span className="text-xs font-extrabold uppercase tracking-wider">Métricas de LinkedIn</span>
                      </div>

                      {isLoadingMetrics ? (
                        <div className="flex items-center justify-center py-6 text-xs text-slate-500 gap-2">
                          <Loader2 className="h-4 w-4 animate-spin text-brand-teal" />
                          <span>Cargando analíticas...</span>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-4">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="flex flex-col">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Seguidores</span>
                              <span className="text-2xl font-black text-slate-800 mt-1">
                                {ragContent.follower_count || ragContent.company_profile?.followers || ragContent.company_profile_data?.followers || "0"}
                              </span>
                            </div>
                            <div className="flex flex-col">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Impresiones</span>
                              <span className="text-2xl font-black text-slate-800 mt-1">
                                {engagementMetrics?.total_impressions || "0"}
                              </span>
                            </div>
                            <div className="flex flex-col">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Tasa de Eng. Promedio</span>
                              <span className="text-2xl font-black text-slate-800 mt-1">
                                {engagementMetrics?.avg_engagement_rate
                                  ? (engagementMetrics.avg_engagement_rate * 100).toFixed(2) + "%"
                                  : "0.00%"}
                              </span>
                            </div>
                            <div className="flex flex-col">
                              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Interacciones Totales</span>
                              <span className="text-2xl font-black text-slate-800 mt-1">
                                {((engagementMetrics?.total_likes || 0) +
                                  (engagementMetrics?.total_comments || 0) +
                                  (engagementMetrics?.total_shares || 0) +
                                  (engagementMetrics?.total_clicks || 0)) || "0"}
                              </span>
                            </div>
                          </div>

                          {/* Compact Breakdown */}
                          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 pt-3 border-t border-slate-200/50 text-xs font-semibold text-slate-600">
                            <div className="flex items-center gap-1.5">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                              <span className="text-slate-400">Reacciones (Likes):</span>
                              <span>{engagementMetrics?.total_likes || 0}</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                              <span className="text-slate-400">Comentarios:</span>
                              <span>{engagementMetrics?.total_comments || 0}</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                              <span className="text-slate-400">Compartidos (Shares):</span>
                              <span>{engagementMetrics?.total_shares || 0}</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <span className="w-1.5 h-1.5 rounded-full bg-purple-500"></span>
                              <span className="text-slate-400">Clics Totales:</span>
                              <span>{engagementMetrics?.total_clicks || 0}</span>
                            </div>
                            <span className="text-[10px] text-slate-400 font-normal italic ml-auto">
                              Analizados: {engagementMetrics?.post_count || 0} posts · Actualizado: {engagementMetrics?.extracted_at ? new Date(engagementMetrics.extracted_at).toLocaleDateString("es-ES") : "N/A"}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-16 flex flex-col items-center justify-center gap-4 text-slate-500 text-center">
                  <Building className="h-12 w-12 text-brand-teal/40" />
                  <div>
                    <h3 className="font-bold text-slate-800 text-lg">Sin perfil de empresa</h3>
                    <p className="text-sm text-slate-500 mt-2 max-w-sm leading-relaxed">
                      Sincroniza los activos de la empresa para cargar su información, identidad de marca y métricas de LinkedIn.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "rag" && (
            <div className="flex flex-col gap-8">
              {isLoadingRag ? (
                <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-16 flex flex-col items-center justify-center gap-4 text-slate-500">
                  <Loader2 className="h-10 w-10 text-brand-teal animate-spin" />
                  <span className="text-sm font-semibold tracking-wide text-slate-600">Indexando y recuperando base de conocimientos semántica...</span>
                </div>
              ) : ragContent ? (
                <div className="flex flex-col gap-8">
                  
                  {/* Workspace Grid — Fila 1: Guías (2/3) + Biblioteca PDFs (1/3), alturas
                      igualadas por el grid (align-items: stretch). Fila 2: Enlaces de Interés
                      a ancho completo = Guías + PDFs + gap. */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 w-full items-stretch">

                      {/* Guías de Estilo y Buenas Prácticas (antes Do's & Don'ts) */}
                      <div className="lg:col-span-2 bg-white border border-slate-200 rounded-3xl p-6 shadow-sm flex flex-col gap-6">
                        <div className="flex items-center justify-between pb-3 border-b border-slate-200">
                          <div className="flex items-center gap-2">
                            <BookOpen className="h-5 w-5 text-brand-teal" />
                            <h2 className="text-sm font-extrabold text-slate-800 uppercase tracking-wider">
                              Guías de Estilo y Buenas Prácticas
                            </h2>
                          </div>
                          <button
                            onClick={handleSaveBrandAssets}
                            disabled={isSavingBrandAssets}
                            className="px-4 py-2 bg-brand-teal hover:bg-brand-teal-dark text-white rounded-xl font-bold text-xs transition-all shadow-md disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
                          >
                            {isSavingBrandAssets ? (
                              <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Guardando...
                              </>
                            ) : (
                              "Guardar Guías"
                            )}
                          </button>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1">
                          {/* Column 1: DO'S */}
                          <div className="flex flex-col gap-3 flex-1">
                            <span className="text-xs font-bold text-emerald-700 flex items-center gap-1.5 border-b border-emerald-100 pb-2">
                              <CheckCircle className="h-4 w-4 text-emerald-600" />
                              Qué Hacer (Do's)
                            </span>
                            <div className="flex flex-col gap-2 flex-1 overflow-y-auto pr-1 min-h-[150px] max-h-[300px]">
                              {localDos.map((item, idx) => (
                                <div key={idx} className="group flex flex-col bg-slate-50/50 hover:bg-slate-100/70 border border-slate-100 hover:border-slate-200 rounded-xl p-3 transition-all duration-150 text-xs text-slate-700">
                                  {editingDoIndex === idx ? (
                                    <div className="flex flex-col gap-2 w-full">
                                      <textarea 
                                        value={editingDoText} 
                                        onChange={(e) => setEditingDoText(e.target.value)}
                                        rows={3}
                                        className="bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700 w-full focus:outline-none focus:border-brand-teal resize-y"
                                      />
                                      <div className="flex justify-end gap-2">
                                        <button 
                                          onClick={() => setEditingDoIndex(null)}
                                          className="text-[10px] font-bold text-slate-500 hover:text-slate-700 cursor-pointer px-2 py-1 bg-white border border-slate-200 rounded-lg shadow-sm"
                                        >
                                          Cancelar
                                        </button>
                                        <button 
                                          onClick={() => {
                                            const updated = [...localDos];
                                            updated[idx] = editingDoText;
                                            setLocalDos(updated);
                                            setEditingDoIndex(null);
                                          }}
                                          className="text-[10px] font-bold text-brand-teal hover:text-brand-teal-dark cursor-pointer px-2.5 py-1 bg-white border border-slate-200 rounded-lg shadow-sm"
                                        >
                                          Listo
                                        </button>
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="flex items-start justify-between w-full">
                                      <span 
                                        className="flex-1 font-semibold leading-relaxed whitespace-pre-wrap prose prose-slate max-w-none text-xs" 
                                        dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(item) }}
                                      />
                                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-3 shrink-0">
                                        <button 
                                          onClick={() => {
                                            setEditingDoIndex(idx);
                                            setEditingDoText(item);
                                          }}
                                          className="p-1 hover:bg-white border border-transparent hover:border-slate-200 text-slate-500 hover:text-brand-teal rounded-lg transition-colors cursor-pointer"
                                          title="Editar"
                                        >
                                          <Edit3 className="h-3.5 w-3.5" />
                                        </button>
                                        <button 
                                          onClick={() => {
                                            setLocalDos(localDos.filter((_, i) => i !== idx));
                                          }}
                                          className="p-1 hover:bg-white border border-transparent hover:border-slate-200 text-slate-500 hover:text-rose-600 rounded-lg transition-colors cursor-pointer"
                                          title="Eliminar"
                                        >
                                          <Trash2 className="h-3.5 w-3.5" />
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              ))}
                              {localDos.length === 0 && (
                                <span className="text-xs text-slate-400 italic py-4 text-center">
                                  No hay pautas positivas configuradas.
                                </span>
                              )}
                            </div>
                            
                            {/* Textarea addition form */}
                            <div className="flex flex-col gap-2 mt-2">
                              <textarea 
                                value={newDoText}
                                onChange={(e) => setNewDoText(e.target.value)}
                                placeholder="Añadir una pauta positiva (Do)..."
                                rows={2}
                                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-700 focus:outline-none focus:border-brand-teal resize-y"
                                onKeyDown={(e) => {
                                  if (e.key === "Enter" && !e.shiftKey && newDoText.trim()) {
                                    e.preventDefault();
                                    setLocalDos([...localDos, newDoText.trim()]);
                                    setNewDoText("");
                                  }
                                }}
                              />
                              <button 
                                onClick={() => {
                                  if (newDoText.trim()) {
                                    setLocalDos([...localDos, newDoText.trim()]);
                                    setNewDoText("");
                                  }
                                }}
                                className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all cursor-pointer shadow-sm self-end"
                              >
                                Añadir Do
                              </button>
                            </div>
                          </div>

                          {/* Column 2: DONT'S */}
                          <div className="flex flex-col gap-3 flex-1">
                            <span className="text-xs font-bold text-rose-700 flex items-center gap-1.5 border-b border-rose-100 pb-2">
                              <AlertCircle className="h-4 w-4 text-rose-600" />
                              Qué Evitar (Don'ts)
                            </span>
                            <div className="flex flex-col gap-2 flex-1 overflow-y-auto pr-1 min-h-[150px] max-h-[300px]">
                              {localDonts.map((item, idx) => (
                                <div key={idx} className="group flex flex-col bg-slate-50/50 hover:bg-slate-100/70 border border-slate-100 hover:border-slate-200 rounded-xl p-3 transition-all duration-150 text-xs text-slate-700">
                                  {editingDontIndex === idx ? (
                                    <div className="flex flex-col gap-2 w-full">
                                      <textarea 
                                        value={editingDontText} 
                                        onChange={(e) => setEditingDontText(e.target.value)}
                                        rows={3}
                                        className="bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700 w-full focus:outline-none focus:border-brand-teal resize-y"
                                      />
                                      <div className="flex justify-end gap-2">
                                        <button 
                                          onClick={() => setEditingDontIndex(null)}
                                          className="text-[10px] font-bold text-slate-500 hover:text-slate-700 cursor-pointer px-2 py-1 bg-white border border-slate-200 rounded-lg shadow-sm"
                                        >
                                          Cancelar
                                        </button>
                                        <button 
                                          onClick={() => {
                                            const updated = [...localDonts];
                                            updated[idx] = editingDontText;
                                            setLocalDonts(updated);
                                            setEditingDontIndex(null);
                                          }}
                                          className="text-[10px] font-bold text-brand-teal hover:text-brand-teal-dark cursor-pointer px-2.5 py-1 bg-white border border-slate-200 rounded-lg shadow-sm"
                                        >
                                          Listo
                                        </button>
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="flex items-start justify-between w-full">
                                      <span 
                                        className="flex-1 font-semibold leading-relaxed whitespace-pre-wrap prose prose-slate max-w-none text-xs" 
                                        dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(item) }}
                                      />
                                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-3 shrink-0">
                                        <button 
                                          onClick={() => {
                                            setEditingDontIndex(idx);
                                            setEditingDontText(item);
                                          }}
                                          className="p-1 hover:bg-white border border-transparent hover:border-slate-200 text-slate-500 hover:text-brand-teal rounded-lg transition-colors cursor-pointer"
                                          title="Editar"
                                        >
                                          <Edit3 className="h-3.5 w-3.5" />
                                        </button>
                                        <button 
                                          onClick={() => {
                                            setLocalDonts(localDonts.filter((_, i) => i !== idx));
                                          }}
                                          className="p-1 hover:bg-white border border-transparent hover:border-slate-200 text-slate-500 hover:text-rose-600 rounded-lg transition-colors cursor-pointer"
                                          title="Eliminar"
                                        >
                                          <Trash2 className="h-3.5 w-3.5" />
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              ))}
                              {localDonts.length === 0 && (
                                <span className="text-xs text-slate-400 italic py-4 text-center">
                                  No hay pautas a evitar configuradas.
                                </span>
                              )}
                            </div>
                            
                            {/* Textarea addition form */}
                            <div className="flex flex-col gap-2 mt-2">
                              <textarea 
                                value={newDontText}
                                onChange={(e) => setNewDontText(e.target.value)}
                                placeholder="Añadir una pauta a evitar (Don't)..."
                                rows={2}
                                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-700 focus:outline-none focus:border-brand-teal resize-y"
                                onKeyDown={(e) => {
                                  if (e.key === "Enter" && !e.shiftKey && newDontText.trim()) {
                                    e.preventDefault();
                                    setLocalDonts([...localDonts, newDontText.trim()]);
                                    setNewDontText("");
                                  }
                                }}
                              />
                              <button 
                                onClick={() => {
                                  if (newDontText.trim()) {
                                    setLocalDonts([...localDonts, newDontText.trim()]);
                                    setNewDontText("");
                                  }
                                }}
                                className="bg-rose-600 hover:bg-rose-700 text-white rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all cursor-pointer shadow-sm self-end"
                              >
                                Añadir Don't
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Document Library Section */}
                      <div className="lg:col-span-1 bg-white border border-slate-200 rounded-3xl p-6 shadow-sm flex flex-col gap-6 flex-1">
                        <div className="flex items-center gap-2 pb-3 border-b border-slate-200">
                          <FileText className="h-5 w-5 text-brand-teal" />
                          <h2 className="text-sm font-extrabold text-slate-800 uppercase tracking-wider">
                            Biblioteca RAG (PDFs)
                          </h2>
                        </div>

                        <div className="flex flex-col gap-6 flex-1">
                          {/* Drag and Drop Upload */}
                          <div className="flex flex-col gap-3">
                            <p className="text-xs text-slate-500 leading-relaxed font-medium">
                              Sube documentos corporativos oficiales para entrenar semánticamente la generación de posts con el contexto real de tu marca.
                            </p>
                            <label className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-slate-300 hover:border-brand-teal rounded-2xl cursor-pointer bg-white hover:bg-slate-100/50 transition-all shadow-sm">
                              <Upload className="h-6 w-6 text-slate-400 mb-2 shrink-0" />
                              <span className="text-xs text-slate-700 font-bold tracking-tight">
                                {isUploadingPdf ? "Subiendo..." : "Subir Documento PDF"}
                              </span>
                              <span className="text-[10px] text-slate-400 mt-1">Máximo 10MB</span>
                              <input 
                                type="file" 
                                accept=".pdf" 
                                className="hidden" 
                                onChange={handleUploadPdf} 
                                disabled={isUploadingPdf} 
                              />
                            </label>
                          </div>

                          {/* PDF Document List */}
                          <div className="flex flex-col gap-3 flex-1 min-h-0">
                            <span className="text-[10px] font-extrabold text-slate-500 uppercase tracking-wider">
                              Documentos Indexados ({pdfDocuments.length})
                            </span>
                            
                            {pdfDocuments.length === 0 ? (
                              <div className="flex flex-col items-center justify-center text-center p-6 bg-slate-50/50 border border-slate-200/50 rounded-xl min-h-[150px] justify-center flex-1">
                                <FileText className="h-8 w-8 text-slate-300 mb-2" />
                                <span className="text-xs text-slate-400 italic">No hay archivos PDFs indexados.</span>
                              </div>
                            ) : (
                              <div className="flex flex-col gap-2 flex-1 overflow-y-auto pr-1 min-h-[120px] max-h-[220px]">
                                {pdfDocuments.map((doc, i) => (
                                  <div key={i} className="group flex items-center justify-between p-3 bg-slate-50/50 border border-slate-150 rounded-xl hover:bg-white hover:border-brand-teal/40 hover:shadow-sm transition-all duration-150">
                                    <button 
                                      onClick={() => loadDocumentContent(doc.filename)}
                                      className="flex items-center gap-2 text-xs text-slate-700 font-bold hover:text-brand-teal truncate text-left mr-2 flex-1 cursor-pointer"
                                      title="Ver Archivo PDF tal cual"
                                    >
                                      <FileText className="h-4 w-4 text-slate-400 group-hover:text-brand-teal shrink-0" />
                                      <span className="truncate">{doc.filename}</span>
                                    </button>
                                    <button 
                                      onClick={() => handleDeleteDocument(doc.filename)} 
                                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer shrink-0"
                                      title="Eliminar archivo"
                                    >
                                      <Trash2 className="h-3.5 w-3.5" />
                                    </button>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Enlaces de Interés (URLs) — RAG Web */}
                      <div className="lg:col-span-3 bg-white border border-slate-200 rounded-3xl p-6 shadow-sm flex flex-col gap-6">
                        <div className="flex items-center gap-2 pb-3 border-b border-slate-200">
                          <Layers className="h-5 w-5 text-brand-teal" />
                          <h2 className="text-sm font-extrabold text-slate-800 uppercase tracking-wider">
                            Enlaces de Interés (URLs)
                          </h2>
                        </div>

                        <div className="flex flex-col gap-4">
                          <p className="text-xs text-slate-500 leading-relaxed font-medium">
                            Indexa páginas web (servicios, notas de prensa, artículos) para que los agentes las usen como fuente verídica. Las URLs de referencia del generador se indexan aquí automáticamente.
                          </p>

                          {/* Add URL form */}
                          <div className="flex gap-2">
                            <input
                              type="text"
                              value={urlToAdd}
                              onChange={(e) => setUrlToAdd(e.target.value)}
                              placeholder="https://..."
                              className="flex-1 bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-700 font-mono focus:outline-none focus:border-brand-teal shadow-sm"
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && urlToAdd.trim() && !isIngestingUrl) handleAddUrl();
                              }}
                            />
                            <button
                              onClick={handleAddUrl}
                              disabled={isIngestingUrl || !urlToAdd.trim()}
                              className="flex items-center gap-1.5 px-3.5 py-2 bg-brand-teal hover:bg-brand-teal-dark text-white text-xs font-bold rounded-xl transition-colors cursor-pointer disabled:opacity-50 shadow-sm shrink-0"
                            >
                              {isIngestingUrl ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Upload className="h-3.5 w-3.5" />
                              )}
                              {isIngestingUrl ? "Indexando..." : "Añadir"}
                            </button>
                          </div>

                          {/* URL list */}
                          <div className="flex flex-col gap-3">
                            <span className="text-[10px] font-extrabold text-slate-500 uppercase tracking-wider">
                              Enlaces Indexados ({ragUrls.length})
                            </span>
                            {ragUrls.length === 0 ? (
                              <div className="flex flex-col items-center justify-center text-center p-6 bg-slate-50/50 border border-slate-200/50 rounded-xl min-h-[100px]">
                                <Layers className="h-8 w-8 text-slate-300 mb-2" />
                                <span className="text-xs text-slate-400 italic">No hay enlaces indexados.</span>
                              </div>
                            ) : (
                              <div className="flex flex-col gap-2 max-h-80 overflow-y-auto pr-1">
                                {ragUrls.map((link, i) => (
                                  <div key={i} className="group flex items-center justify-between p-3 bg-slate-50/50 border border-slate-150 rounded-xl hover:bg-white hover:border-brand-teal/40 hover:shadow-sm transition-all duration-150">
                                    <a
                                      href={link.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="flex flex-col text-left mr-2 flex-1 min-w-0 cursor-pointer"
                                      title={link.url}
                                    >
                                      <span className="text-xs text-slate-700 font-bold hover:text-brand-teal truncate">{link.title}</span>
                                      <span className="text-[10px] text-slate-400 font-mono truncate">{link.url}</span>
                                    </a>
                                    <button
                                      onClick={() => handleDeleteUrl(link.url)}
                                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer shrink-0"
                                      title="Eliminar enlace del RAG"
                                    >
                                      <Trash2 className="h-3.5 w-3.5" />
                                    </button>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>

                  </div>
                </div>
              ) : (
                <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-16 flex flex-col items-center justify-center gap-4 text-slate-500 text-center">
                  <BookOpen className="h-12 w-12 text-brand-teal/40" />
                  <div>
                    <h3 className="font-bold text-slate-800 text-lg">Base de conocimientos vacía</h3>
                    <p className="text-sm text-slate-500 mt-2 max-w-sm leading-relaxed">
                      Sincroniza los activos de la empresa para cargar la base de conocimientos semántica (RAG) de este registro.
                    </p>
                    {selectedCompany && selectedCompany.urn && selectedCompany.urn !== "undefined" && !selectedCompany.is_personal && (
                      <button 
                        onClick={handleTriggerSync}
                        disabled={isSyncingCompany}
                        className="mt-6 flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-r from-brand-teal to-brand-teal-dark hover:from-brand-teal hover:to-brand-teal-dark text-white text-xs font-bold rounded-xl shadow-md transition-all cursor-pointer mx-auto disabled:opacity-50"
                      >
                        {isSyncingCompany ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RefreshCw className="h-4 w-4" />
                        )}
                        Sincronizar y Simular RAG
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: SCHEDULED & PUBLISHED HISTORY */}
          {activeTab === "history" && (
            <div className="flex flex-col gap-6">
              <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                <h3 className="font-bold text-slate-800 flex items-center gap-2 text-sm">
                  <Calendar className="h-5 w-5 text-brand-teal" />
                  HISTÓRICO EDITORIAL DE LINKEDIN
                </h3>
                <button 
                  onClick={() => loadHistory(selectedCompany?.urn)} 
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-lg border border-slate-200 shadow-sm transition-colors cursor-pointer"
                >
                  <RefreshCw className="h-3 w-3" />
                  Actualizar Lista
                </button>
              </div>

              {isLoadingHistory ? (
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-12 flex items-center justify-center gap-3 text-slate-500">
                  <Loader2 className="h-5 w-5 animate-spin text-brand-teal" />
                  <span>Recuperando historial de posts...</span>
                </div>
              ) : postsHistory.length === 0 ? (
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-12 flex flex-col items-center justify-center gap-4 text-slate-500 text-center">
                  <Calendar className="h-10 w-10 text-brand-teal/50" />
                  <div>
                    <h3 className="font-bold text-slate-855">No hay publicaciones persistidas</h3>
                    <p className="text-xs text-slate-500 mt-1">Cuando apruebes una publicación generada por el Community Manager, aparecerá listada en este histórico.</p>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  {postsHistory.map((post, i) => (
                    <div key={i} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col gap-3 hover:border-slate-300 transition-all duration-150">
                      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                        <div className="flex flex-col">
                          <span className="text-[11px] font-bold text-brand-teal tracking-wider uppercase">
                            {companies.find(c => c.urn === post.account_id)?.name || post.account_id || "LinkedIn Org"}
                          </span>
                          {post.thread_id && <span className="text-[9px] text-slate-400 font-mono mt-0.5" title="Thread ID para recuperar contexto">TID: {post.thread_id.split("-")[0]}...</span>}
                        </div>
                        <div className="flex items-center gap-1.5">
                          {post.score !== undefined && post.score !== null && (
                            <span 
                              title="Puntuación de calidad del post (evaluación de Hook, Estructura, Valor y CTA)"
                              className={`text-[9px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider flex items-center gap-1 ${
                                post.score >= 80 
                                  ? "bg-emerald-50 border-emerald-200 text-emerald-700 font-bold" 
                                  : post.score >= 50
                                  ? "bg-amber-50 border-amber-200 text-amber-700 font-bold"
                                  : "bg-rose-50 border-rose-200 text-rose-700 font-bold"
                              }`}
                            >
                              ⭐ {post.score}/100
                            </span>
                          )}
                          <span className={`text-[9px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider ${
                            post.status === "published" 
                              ? "bg-emerald-50 border-emerald-200 text-emerald-700" 
                              : post.status === "scheduled"
                              ? "bg-blue-50 border-blue-200 text-blue-700"
                              : "bg-amber-50 border-amber-200 text-amber-700"
                          }`}>
                            {post.status === "published" 
                              ? "Publicado" 
                              : post.status === "scheduled" 
                              ? "Programado" 
                              : post.status === "saved_for_later" || post.status === "draft"
                              ? "Borrador" 
                              : post.status}
                          </span>
                        </div>
                      </div>
                      <div className="text-xs leading-relaxed text-slate-700 line-clamp-4 overflow-hidden min-h-[4.5rem]">
                        {renderMarkdown(post.content)}
                      </div>
                      
                      <div className="flex items-center justify-between mt-auto border-t border-slate-100 pt-3">
                        <div className="flex gap-2">
                          <button 
                            onClick={() => {
                              setViewPostData(post);
                              setIsViewPostModalOpen(true);
                            }}
                            className="p-1.5 text-slate-500 hover:text-brand-teal hover:bg-brand-teal/10 rounded transition-colors"
                            title="Ver Publicación Completa"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                          
                          {post.status !== "published" && (
                            <>
                              <button 
                                onClick={() => handleEditPost(post)}
                                className="p-1.5 text-slate-500 hover:text-brand-teal hover:bg-brand-teal/10 rounded transition-colors"
                                title="Editar con IA"
                              >
                                <Edit3 className="h-4 w-4" />
                              </button>
                              <button 
                                onClick={() => handlePublishNow(post)}
                                className="p-1.5 text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 rounded transition-colors"
                                title="Publicar Ahora en LinkedIn"
                              >
                                <Send className="h-4 w-4" />
                              </button>
                              <button 
                                onClick={() => handleScheduleDialog(post)}
                                className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                                title="Programar Publicación"
                              >
                                <Calendar className="h-4 w-4" />
                              </button>
                            </>
                          )}
                          
                          <button 
                            onClick={() => handleDeletePost(post.id)}
                            className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors"
                            title="Eliminar del Historial"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="flex gap-2 text-[10px] text-slate-500">
                          <span>{new Date(post.created_at || post.published_time).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: SKILLS */}
          {activeTab === "skills" && (
            <div className="flex flex-col gap-6">
              {/* Header and overview */}
              <div className="flex flex-col gap-1.5">
                <h2 className="text-xl font-extrabold text-slate-800 flex items-center gap-2">
                  <Wand2 className="h-5 w-5 text-brand-teal" />
                  Espacio de Trabajo de Habilidades (Skills Workspace)
                </h2>
                <p className="text-xs text-slate-500">
                  Las Habilidades definen las pautas de estilo, tono de voz y directrices de redacción que sigue el agente de Inteligencia Artificial para generar contenido.
                </p>
              </div>

              {/* Two columns workspace layout */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                
                {/* Left Column: Editor Workspace */}
                <div className="lg:col-span-8 flex flex-col gap-6">
                  {/* Editor Container */}
                  <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col gap-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <h3 className="font-bold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-2">
                        <Edit3 className="h-4 w-4 text-brand-teal" />
                        {activeWorkspaceSkill ? "Editor de Habilidad" : "Crear Nueva Habilidad"}
                      </h3>
                      {activeWorkspaceSkill && activeWorkspaceSkill.name === "Guía de Estilo y Generación (Base)" && (
                        <span className="text-[10px] font-bold text-amber-500 bg-amber-50 border border-amber-100 px-2.5 py-1 rounded-lg">
                          Habilidad de Sistema (Título y descripción bloqueados)
                        </span>
                      )}
                    </div>

                    <div className="flex flex-col gap-4">
                      {/* Name input */}
                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Nombre de la Habilidad</label>
                        <input 
                          type="text" 
                          value={workspaceSkillName} 
                          onChange={(e) => setWorkspaceSkillName(e.target.value)} 
                          placeholder="Nombre (ej. Storytelling Tecnológico)" 
                          disabled={activeWorkspaceSkill && activeWorkspaceSkill.name === "Guía de Estilo y Generación (Base)"}
                          className="bg-white disabled:bg-slate-50 disabled:text-slate-400 border border-slate-200 rounded-xl px-3.5 py-2.5 text-xs font-semibold text-slate-800 focus:outline-none focus:border-brand-teal transition-all" 
                        />
                      </div>

                      {/* Description input */}
                      <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Descripción de la Habilidad</label>
                        <input 
                          type="text" 
                          value={workspaceSkillDesc} 
                          onChange={(e) => setWorkspaceSkillDesc(e.target.value)} 
                          placeholder="Para qué sirve esta habilidad..." 
                          disabled={activeWorkspaceSkill && activeWorkspaceSkill.name === "Guía de Estilo y Generación (Base)"}
                          className="bg-white disabled:bg-slate-50 disabled:text-slate-400 border border-slate-200 rounded-xl px-3.5 py-2.5 text-xs font-semibold text-slate-800 focus:outline-none focus:border-brand-teal transition-all" 
                        />
                      </div>

                      {/* Content textarea */}
                      <div className="flex flex-col gap-1">
                        <div className="flex justify-between items-center">
                          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Instrucciones y Pautas (Markdown)</label>
                          <span className="text-[9px] text-slate-400 font-medium font-mono">Compatible con Markdown</span>
                        </div>
                        <textarea 
                          value={workspaceSkillMarkdown} 
                          onChange={(e) => setWorkspaceSkillMarkdown(e.target.value)} 
                          rows={14} 
                          placeholder="Define el estilo, los ganchos recomendados, el formato del post y proporciona ejemplos few-shot..." 
                          className="bg-white border border-slate-200 rounded-xl px-4 py-3.5 text-xs text-slate-800 focus:outline-none focus:border-brand-teal font-mono leading-relaxed transition-all resize-y" 
                        />
                      </div>

                      {/* Action buttons */}
                      <div className="flex justify-between items-center mt-2 border-t border-slate-100 pt-4">
                        {activeWorkspaceSkill && activeWorkspaceSkill.name !== "Guía de Estilo y Generación (Base)" ? (
                          <button 
                            onClick={async () => {
                              if (confirm("¿Seguro que deseas eliminar esta habilidad táctica?")) {
                                await handleDeleteSkill(activeWorkspaceSkill.id);
                                // Set back to base skill
                                const base = skills.find((s: any) => s.name === "Guía de Estilo y Generación (Base)");
                                if (base) {
                                  setActiveWorkspaceSkill(base);
                                  setWorkspaceSkillName(base.name);
                                  setWorkspaceSkillDesc(base.description || "");
                                  setWorkspaceSkillMarkdown(base.markdown_content || "");
                                } else {
                                  setActiveWorkspaceSkill(null);
                                  setWorkspaceSkillName("");
                                  setWorkspaceSkillDesc("");
                                  setWorkspaceSkillMarkdown("");
                                }
                              }
                            }}
                            className="flex items-center gap-1.5 px-4 py-2 text-rose-500 hover:bg-rose-50 border border-transparent hover:border-rose-100 rounded-xl text-xs font-bold transition-all cursor-pointer"
                          >
                            <Trash2 className="h-4 w-4" />
                            Eliminar Habilidad
                          </button>
                        ) : <div />}

                        <div className="flex gap-3">
                          {activeWorkspaceSkill ? (
                            <button 
                              onClick={() => handleUpdateSkill(activeWorkspaceSkill.id, workspaceSkillName, workspaceSkillDesc, workspaceSkillMarkdown)} 
                              disabled={!workspaceSkillName || !workspaceSkillMarkdown}
                              className="px-5 py-2.5 bg-gradient-to-r from-brand-teal to-brand-teal-dark hover:from-brand-teal-dark hover:to-brand-teal text-white rounded-xl font-bold text-xs transition-all disabled:opacity-50 cursor-pointer shadow-md shadow-brand-teal/20"
                            >
                              Guardar Cambios
                            </button>
                          ) : (
                            <button 
                              onClick={handleCreateSkill} 
                              disabled={!workspaceSkillName || !workspaceSkillMarkdown}
                              className="px-5 py-2.5 bg-gradient-to-r from-brand-teal to-brand-teal-dark hover:from-brand-teal-dark hover:to-brand-teal text-white rounded-xl font-bold text-xs transition-all disabled:opacity-50 cursor-pointer shadow-md shadow-brand-teal/20"
                            >
                              Guardar Nueva Habilidad
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right Column: Skill Explorer / List */}
                <div className="lg:col-span-4 flex flex-col gap-4">
                  <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 flex flex-col gap-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <h3 className="font-bold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-2">
                        <Layers className="h-4 w-4 text-brand-teal" />
                        Explorador
                      </h3>
                      <button
                        onClick={() => {
                          setActiveWorkspaceSkill(null);
                          setWorkspaceSkillName("");
                          setWorkspaceSkillDesc("");
                          setWorkspaceSkillMarkdown("");
                        }}
                        className="px-2.5 py-1 bg-brand-teal/10 hover:bg-brand-teal/20 text-brand-teal text-[10px] font-bold rounded-lg transition-colors cursor-pointer"
                      >
                        + Nueva Habilidad
                      </button>
                    </div>

                    <div className="flex flex-col gap-4">
                      {/* Section: Habilidad Base */}
                      <div className="flex flex-col gap-2">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-1">Habilidad Base de Estilo</span>
                        {(() => {
                          const baseSkillObj = skills.find(s => s.name === "Guía de Estilo y Generación (Base)");
                          if (!baseSkillObj) return <span className="text-xs text-slate-400 italic px-1">Generando Habilidad Base...</span>;
                          const isSelected = activeWorkspaceSkill && activeWorkspaceSkill.id === baseSkillObj.id;
                          return (
                            <button
                              onClick={() => {
                                setActiveWorkspaceSkill(baseSkillObj);
                                setWorkspaceSkillName(baseSkillObj.name);
                                setWorkspaceSkillDesc(baseSkillObj.description || "");
                                setWorkspaceSkillMarkdown(baseSkillObj.markdown_content || "");
                              }}
                              className={`w-full text-left p-3.5 rounded-xl border transition-all duration-200 flex flex-col gap-1 relative overflow-hidden ${
                                isSelected 
                                  ? "bg-brand-teal/5 border-brand-teal/40 shadow-sm shadow-brand-teal/5" 
                                  : "bg-slate-50 hover:bg-slate-100 border-slate-200"
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-black text-brand-teal truncate pr-8">{baseSkillObj.name}</span>
                                <span className="text-[9px] px-1.5 py-0.5 bg-brand-teal/10 text-brand-teal rounded-full font-bold border border-brand-teal/20 shrink-0">
                                  Base
                                </span>
                              </div>
                              <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">{baseSkillObj.description}</p>
                            </button>
                          );
                        })()}
                      </div>

                      {/* Section: Habilidades Tacticas */}
                      <div className="flex flex-col gap-2">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-1">Habilidades Tácticas Personalizadas</span>
                        {(() => {
                          const tacticalSkills = skills.filter(s => s.name !== "Guía de Estilo y Generación (Base)");
                          if (tacticalSkills.length === 0) {
                            return (
                              <div className="text-xs text-slate-400 italic px-1 py-3 text-center border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
                                No tienes habilidades tácticas personalizadas.
                              </div>
                            );
                          }
                          return (
                            <div className="flex flex-col gap-2 max-h-80 overflow-y-auto pr-1">
                              {tacticalSkills.map(s => {
                                const isSelected = activeWorkspaceSkill && activeWorkspaceSkill.id === s.id;
                                return (
                                  <button
                                    key={s.id}
                                    onClick={() => {
                                      setActiveWorkspaceSkill(s);
                                      setWorkspaceSkillName(s.name);
                                      setWorkspaceSkillDesc(s.description || "");
                                      setWorkspaceSkillMarkdown(s.markdown_content || "");
                                    }}
                                    className={`w-full text-left p-3.5 rounded-xl border transition-all duration-200 flex flex-col gap-1 relative ${
                                      isSelected 
                                        ? "bg-brand-teal/5 border-brand-teal/40 shadow-sm shadow-brand-teal/5" 
                                        : "bg-slate-50 hover:bg-slate-100 border-slate-200"
                                    }`}
                                  >
                                    <span className="text-xs font-bold text-slate-700 truncate pr-6">{s.name}</span>
                                    <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">{s.description || "Sin descripción."}</p>
                                  </button>
                                );
                              })}
                            </div>
                          );
                        })()}
                      </div>
                    </div>
                  </div>
                </div>

              </div>

              {/* Row 2: RAG Posts Reference Library */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col gap-4">
                <div className="flex flex-col gap-1">
                  <h3 className="font-bold text-slate-800 text-sm flex items-center gap-2">
                    <FileText className="h-4.5 w-4.5 text-brand-teal" />
                    BIBLIOTECA DE POSTS DE REFERENCIA (APRENDIZAJE FEW-SHOT)
                  </h3>
                  <p className="text-xs text-slate-400">
                    Los posts con mayor puntuación de calidad (de 0 a 100) se inyectan dinámicamente como ejemplos de escritura para entrenar la redacción del agente.
                  </p>
                </div>
                {isLoadingRagPosts ? (
                  <span className="text-xs text-slate-400 italic">Cargando biblioteca de posts...</span>
                ) : ragPosts.length === 0 ? (
                  <span className="text-xs text-slate-400 italic">No hay posts de referencia indexados en el RAG para esta organización.</span>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[500px] overflow-y-auto pr-2">
                    {ragPosts.map((post) => {
                      const score = post.score || 0;
                      let badgeColor = "bg-rose-50 text-rose-600 border-rose-100";
                      if (score >= 80) {
                        badgeColor = "bg-emerald-50 text-emerald-600 border-emerald-100";
                      } else if (score >= 60) {
                        badgeColor = "bg-amber-50 text-amber-600 border-amber-100";
                      }
                      return (
                        <div key={post.id} className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex flex-col justify-between gap-3 shadow-sm hover:border-brand-teal/40 transition-all duration-200">
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center justify-between text-[10px] text-slate-400 font-semibold border-b border-slate-200 pb-1">
                              <span className="truncate">ID: {post.id.substring(0, 12)}...</span>
                              <span>{post.created_at ? new Date(post.created_at).toLocaleDateString("es-ES") : "Histórico"}</span>
                            </div>
                            <p className="text-[11px] leading-relaxed text-slate-600 whitespace-pre-wrap italic font-mono">
                              {post.content}
                            </p>
                          </div>
                          <div className="flex items-center justify-between border-t border-slate-150 pt-2">
                            <span className={`text-[9px] px-2 py-0.5 rounded-full font-bold border ${badgeColor}`}>
                              Calidad: {score}/100
                            </span>
                            <span className="text-[9px] px-2 py-0.5 bg-brand-teal/10 text-brand-teal rounded-full font-bold border border-brand-teal/20">
                              RAG Post
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

            </div>
          )}
            </>
          )}
        </main>
      </div>

      {/* Footer component */}
      <footer className="bg-slate-900 border-t border-slate-800 text-slate-400 py-12 mt-16 relative z-10">
        <div className="max-w-7xl mx-auto px-4 md:px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex flex-col gap-2 text-center md:text-left">
            <div className="flex items-center gap-2 justify-center md:justify-start">
              <img src="/logo.png" alt="AIPost Logo" className="h-7 w-7 object-contain" />
              <span className="text-sm font-black tracking-wider text-white">AIPost</span>
            </div>
            <p className="text-[11px] text-slate-500 max-w-sm">
              Plataforma avanzada de generación de contenido corporativo inteligente y optimización de engagement en redes profesionales.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-xs font-semibold text-slate-450">
            <a href="#" className="hover:text-brand-teal transition-colors">API Status</a>
            <a href="#" className="hover:text-brand-teal transition-colors">Documentación</a>
            <a href="#" className="hover:text-brand-teal transition-colors">Política de Privacidad</a>
            <a href="#" className="hover:text-brand-teal transition-colors">Términos del Servicio</a>
          </div>
          <div className="flex flex-col items-center md:items-end gap-1.5 text-center md:text-right">
            <span className="text-[10px] text-slate-500 font-extrabold uppercase tracking-widest">Tecnología</span>
            <span className="text-xs font-bold text-slate-400">Powered by AIPost Agents</span>
            <span className="text-[10px] text-slate-650 font-medium">© {new Date().getFullYear()} AIPost. Todos los derechos reservados.</span>
          </div>
        </div>
      </footer>

      {/* Schedule Modal */}
      {isScheduleModalOpen && (
        <ScheduleModal
          scheduleDate={scheduleDate}
          onChange={setScheduleDate}
          onConfirm={submitSchedule}
          onClose={() => {
            setIsScheduleModalOpen(false);
            setSchedulePostData(null);
            setScheduleDate("");
          }}
        />
      )}

      {/* View Post Modal */}
      {isViewPostModalOpen && viewPostData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden border border-slate-100">
            <div className="flex items-center justify-between p-4 border-b border-slate-100">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <FileText className="h-5 w-5 text-brand-teal" />
                Detalle de la Publicación
              </h3>
              <button 
                onClick={() => {
                  setIsViewPostModalOpen(false);
                  setViewPostData(null);
                }}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-50 transition-colors"
              >
                &times;
              </button>
            </div>
            <div className="p-6 flex flex-col gap-4 max-h-[70vh] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex flex-col">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Cuenta Destino</span>
                  <span className="text-sm font-semibold text-brand-teal mt-0.5">
                    {companies.find(c => c.urn === viewPostData.account_id)?.name || viewPostData.account_id || "LinkedIn Org"}
                  </span>
                </div>
                <div className="flex flex-col items-end">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Estado</span>
                  <span className={`text-[10px] px-2.5 py-0.5 rounded-full border font-bold uppercase tracking-wider mt-0.5 ${
                    viewPostData.status === "published" 
                      ? "bg-emerald-50 border-emerald-200 text-emerald-700" 
                      : viewPostData.status === "scheduled"
                      ? "bg-blue-50 border-blue-200 text-blue-700"
                      : "bg-amber-50 border-amber-200 text-amber-700"
                  }`}>
                    {viewPostData.status === "published" 
                      ? "Publicado" 
                      : viewPostData.status === "scheduled" 
                      ? "Programado" 
                      : viewPostData.status === "saved_for_later" || viewPostData.status === "draft"
                      ? "Borrador Guardado" 
                      : viewPostData.status}
                  </span>
                </div>
              </div>
              
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Contenido</span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(viewPostData.content);
                      addLog("SISTEMA", "Contenido copiado al portapapeles en formato Markdown.", "success");
                    }}
                    className="text-[10px] px-2.5 py-1 bg-white hover:bg-slate-50 text-slate-600 border border-slate-200 rounded-lg font-bold shadow-sm transition-all cursor-pointer"
                  >
                    Copiar Markdown
                  </button>
                </div>
                <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 text-sm leading-relaxed text-slate-800">
                  {renderMarkdown(viewPostData.content)}
                </div>
              </div>

              {viewPostData.scheduled_time && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Programado Para</span>
                  <span className="text-sm text-slate-700 font-medium">
                    {new Date(viewPostData.scheduled_time).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
            <div className="flex items-center justify-end p-4 border-t border-slate-100 bg-slate-50/50">
              <button 
                onClick={() => {
                  setIsViewPostModalOpen(false);
                  setViewPostData(null);
                }}
                className="px-6 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-sm font-bold rounded-xl transition-all cursor-pointer"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RAG Document Visualizer Modal */}
      {isDocModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl overflow-hidden border border-slate-100 flex flex-col h-[85vh]">
            <div className="flex items-center justify-between p-5 border-b border-slate-100 bg-slate-50/50">
              <h3 className="font-bold text-slate-800 flex items-center gap-2.5 text-sm md:text-base">
                <FileText className="h-5 w-5 text-brand-teal" />
                Visualizador de Documento RAG: <span className="font-mono text-xs md:text-sm text-brand-teal-dark bg-brand-teal/10 px-2 py-1 rounded border border-brand-teal/20">{selectedDoc?.filename || "Cargando..."}</span>
              </h3>
              <button 
                onClick={() => {
                  setIsDocModalOpen(false);
                  setSelectedDoc(null);
                }}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-150 transition-colors text-lg"
              >
                &times;
              </button>
            </div>
            
            <div className="p-6 flex-1 overflow-y-auto bg-slate-50/30">
              {docContentLoading ? (
                <div className="h-full flex flex-col items-center justify-center gap-3 text-slate-500">
                  <Loader2 className="h-8 w-8 animate-spin text-brand-teal" />
                  <span className="text-xs font-semibold">Reconstruyendo documento desde el vector store...</span>
                </div>
              ) : selectedDoc ? (
                selectedDoc.isPdf ? (
                  <iframe
                    src={`http://localhost:8000/content/company/documents/pdf?org_urn=${encodeURIComponent(selectedCompany?.urn || "")}&filename=${encodeURIComponent(selectedDoc.filename)}&token=${authToken}`}
                    className="w-full h-full border border-slate-200 rounded-xl bg-white shadow-inner"
                    style={{ minHeight: "550px" }}
                    title={selectedDoc.filename}
                  />
                ) : (
                  <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-sm min-h-full leading-relaxed text-slate-850 text-xs md:text-sm whitespace-pre-wrap font-mono prose max-w-none">
                    {selectedDoc.content}
                  </div>
                )
              ) : (
                <div className="h-full flex items-center justify-center text-slate-400 italic text-xs">
                  No se pudo cargar el contenido.
                </div>
              )}
            </div>
            
            <div className="flex items-center justify-end p-4 border-t border-slate-100 bg-slate-50/50 gap-3">
              {selectedDoc && !selectedDoc.isPdf && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(selectedDoc.content);
                    addLog("SISTEMA", "Contenido del documento copiado al portapapeles.", "success");
                  }}
                  className="px-4 py-2 text-xs bg-white hover:bg-slate-100 text-slate-700 font-bold border border-slate-200 rounded-lg shadow-sm transition-colors cursor-pointer"
                >
                  Copiar Contenido
                </button>
              )}
              <button 
                onClick={() => {
                  setIsDocModalOpen(false);
                  setSelectedDoc(null);
                }}
                className="px-6 py-2 bg-slate-200 hover:bg-slate-350 text-slate-700 text-xs font-bold rounded-lg transition-all cursor-pointer"
              >
                Cerrar Visualizador
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Publish Status Modal */}
      {isPublishStatusModalOpen && (
        <PublishStatusModal
          status={publishStatus}
          onClose={() => setIsPublishStatusModalOpen(false)}
        />
      )}

      {/* Toast Notification */}
      <Toast toast={toastMessage} onClose={clearToast} />
    </div>
  );
}
