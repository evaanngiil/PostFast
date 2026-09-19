/* eslint-disable react/no-unescaped-entities */
"use client";

import React, { useState, useEffect } from "react";
import AppHeader from "./components/layout/AppHeader";
import Studio from "./components/studio/Studio";
import KnowledgeBaseView from "./components/knowledge/KnowledgeBaseView";
import SkillsView from "./components/skills/SkillsView";
import HistoryView from "./components/history/HistoryView";
import ViewPostModal from "./components/ViewPostModal";
import EditPostModal from "./components/EditPostModal";
import DocContentModal from "./components/DocContentModal";
import ScheduleModal from "./components/ScheduleModal";
import PublishStatusModal from "./components/PublishStatusModal";
import Toast from "./components/Toast";
import { useToast } from "./hooks/useToast";
import { useAgentLog } from "./hooks/useAgentLog";
import { useSkills } from "./hooks/useSkills";
import { useHistory } from "./hooks/useHistory";
import { useKnowledgeBase } from "./hooks/useKnowledgeBase";
import { useContentGeneration } from "./hooks/useContentGeneration";

export default function PostFastDashboard() {
  // Navigation Tabs: Linear & Knowledge Base Focus
  const [activeTab, setActiveTab] = useState<"generator" | "knowledge" | "skills" | "history">("generator");

  // Auth & Organizations
  const [authToken, setAuthToken] = useState<string>("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<any[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<any>(null);
  const [, setAuthProvider] = useState<string>("");
  const [, setIsLoadingCompanies] = useState<boolean>(false);
  const [isSyncingCompany, setIsSyncingCompany] = useState<boolean>(false);
  const [isLinkedinConnected, setIsLinkedinConnected] = useState<boolean>(false);
  const [userInfo, setUserInfo] = useState<{ name?: string; picture?: string; email?: string } | null>(null);

  const [viewPostData, setViewPostData] = useState<any>(null);
  const [isViewPostModalOpen, setIsViewPostModalOpen] = useState<boolean>(false);
  const [editModalPost, setEditModalPost] = useState<any>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);
  const [supabaseConfig, setSupabaseConfig] = useState<any>(null);

  // Cross-cutting hooks
  const { toast: toastMessage, showToast, clearToast } = useToast();
  const { logs: terminalLogs, addLog, clearLogs } = useAgentLog(showToast);

  // Skills Domain
  const {
    skills,
    selectedSkillIds,
    setSelectedSkillIds,
    activeWorkspaceSkill,
    setActiveWorkspaceSkill,
    workspaceSkillName,
    setWorkspaceSkillName,
    workspaceSkillDesc,
    setWorkspaceSkillDesc,
    workspaceSkillMarkdown,
    setWorkspaceSkillMarkdown,
    loadSkills,
    handleCreateSkill,
    handleDeleteSkill,
    handleUpdateSkill,
  } = useSkills({ authToken, orgUrn: selectedCompany?.urn, showToast });

  // History Domain
  const { postsHistory, isLoadingHistory, loadHistory } = useHistory({
    authToken,
    orgUrn: selectedCompany?.urn,
  });

  // Knowledge Base Domain (RAG)
  const {
    pdfDocuments,
    isUploadingPdf,
    ragContent,
    isLoadingRag,
    localDos,
    setLocalDos,
    localDonts,
    setLocalDonts,
    isSavingBrandAssets,
    localAboutUs,
    setLocalAboutUs,
    localSpecialties,
    setLocalSpecialties,
    ragUrls,
    urlToAdd,
    setUrlToAdd,
    isIngestingUrl,
    selectedDoc,
    setSelectedDoc,
    isDocModalOpen,
    setIsDocModalOpen,
    docContentLoading,
    loadCompanyDocuments,
    handleUploadPdf,
    handleDeleteDocument,
    loadRagKnowledge,
    loadBrandAssets,
    loadRagUrls,
    handleAddUrl,
    handleDeleteUrl,
    loadRagPosts,
    loadEngagementMetrics,
    loadDocumentContent,
    handleSaveBrandAssets,
  } = useKnowledgeBase({ authToken, orgUrn: selectedCompany?.urn, addLog });

  // Content Generation Domain (Workflow + HITL)
  const {
    promptQuery,
    setPromptQuery,
    linkUrl,
    setLinkUrl,
    setTaskId,
    taskStatus,
    isGenerating,
    draftContent,
    setDraftContent,
    currentPostId,
    draftHashtags,
    draftCta,
    factCheck,
    safetyReport,
    knowledgeGap,
    userFeedback,
    setUserFeedback,
    checkpointConfig,
    isSubmittingFeedback,
    activeAgent,
    agentSteps,
    isScheduleModalOpen,
    setIsScheduleModalOpen,
    schedulePostData,
    scheduleDate,
    setScheduleDate,
    isPublishStatusModalOpen,
    setIsPublishStatusModalOpen,
    publishStatus,
    editingPost,
    setEditingPost,
    editInstruction,
    setEditInstruction,
    resetGeneratorState,
    handleGeneratePost,
    handleResumeWorkflow,
    handleStopGeneration,
    handleEditPost,
    handleDeletePost,
    handlePublishNow,
    handleSaveDraft,
    submitSchedule,
    handleScheduleDialog,
  } = useContentGeneration({
    authToken,
    selectedCompany,
    supabaseConfig,
    selectedSkillIds,
    addLog,
    clearLogs,
    loadHistory,
    loadRagPosts,
    setActiveTab: (t: string) => setActiveTab(t as any),
    showToast,
  });

  // 1. Session Initialization
  useEffect(() => {
    const getCookie = (name: string) => {
      const value = `; ${document.cookie}`;
      const parts = value.split(`; ${name}=`);
      if (parts.length === 2) return parts.pop()?.split(";").shift();
      return null;
    };

    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get("auth_token");
    const isLinkedFromRedirect = urlParams.get("linkedin_connected");

    const cookieToken = getCookie("aipost_session_id");
    const localToken = localStorage.getItem("aipost_session_token");
    const token = urlToken || cookieToken || localToken;

    if (urlToken) {
      document.cookie = `aipost_session_id=${urlToken}; path=/; max-age=604800; samesite=lax`;
      localStorage.setItem("aipost_session_token", urlToken);
    }

    if (urlToken || isLinkedFromRedirect) {
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, document.title, cleanUrl);
    }

    if (token) {
      if (!cookieToken) {
        document.cookie = `aipost_session_id=${token}; path=/; max-age=604800; samesite=lax`;
      }
      localStorage.setItem("aipost_session_token", token);
      setAuthToken(token);
    } else {
      setAuthError("No se ha detectado ninguna sesión activa. Por favor, inicia sesión.");
    }

    fetch("http://localhost:8000/config")
      .then((r) => {
        if (!r.ok) throw new Error("API Offline");
        return r.json();
      })
      .then((data) => {
        setSupabaseConfig(data);
      })
      .catch((err) => {
        console.error("Error conectando con backend config:", err);
      });
  }, []);

  // 2. Verify Session & Profile
  useEffect(() => {
    if (!authToken) return;

    fetch("http://localhost:8000/auth/me", {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error("La API respondió con error " + r.status);
        return r.json();
      })
      .then((data) => {
        if (data.authenticated) {
          setAuthProvider(data.provider || "");
          setIsLinkedinConnected(!!data.linkedin_connected);
          if (data.user_info) {
            setUserInfo(data.user_info);
          }
          if (!data.has_completed_onboarding) {
            window.location.href = "/onboarding";
          } else {
            loadCompanies();
          }
        } else {
          setAuthError(`Sesión no válida o expirada. Razón: ${data.reason || "No autorizado"}`);
        }
      })
      .catch((err) => {
        setAuthError(`No se pudo verificar la sesión: ${err.message || "Error de red"}`);
      });
  }, [authToken]);

  const handleLogout = async () => {
    try {
      await fetch("http://localhost:8000/auth/logout", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
    } catch {
      // Ignore network errors on logout
    }
    document.cookie = "aipost_session_id=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; samesite=lax";
    localStorage.removeItem("aipost_session_token");
    window.location.href = "/login";
  };

  const loadCompanies = async () => {
    setIsLoadingCompanies(true);
    try {
      const res = await fetch("http://localhost:8000/auth/organizations", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      if (Array.isArray(data)) {
        const mapped = data.map((org: any) => {
          const urn = org.org_urn || `urn:li:person:${org.user_id}`;
          const name = org.is_personal
            ? (org.first_name || org.last_name
                ? `${org.first_name || ""} ${org.last_name || ""}`.trim()
                : "Perfil Personal")
            : (org.company_name || "Organización sin nombre");
          return {
            ...org,
            urn,
            name,
          };
        });
        setCompanies(mapped);
        if (mapped.length > 0) {
          const savedUrn = localStorage.getItem("postfast_active_org_urn");
          const found = mapped.find((c) => c.urn === savedUrn);
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
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        setIsLinkedinConnected(false);
        addLog("SISTEMA", "Cuenta de LinkedIn desconectada correctamente.", "success");
        loadCompanies();
      } else {
        const err = await res.json();
        addLog("ERROR", `No se pudo desconectar LinkedIn: ${err.detail || "Desconocido"}`, "error");
      }
    } catch (err: any) {
      addLog("ERROR", `Error de red al desconectar LinkedIn: ${err.message}`, "error");
    }
  };

  const handleTriggerSync = async () => {
    if (!selectedCompany) return;
    setIsSyncingCompany(true);
    addLog("INGESTOR", `Solicitando extracción batch y simulación RAG para ${selectedCompany.name}...`, "info");

    try {
      const res = await fetch("http://localhost:8000/content/company/profiles/trigger_batch", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          org_urn: selectedCompany.urn,
          org_name: selectedCompany.name,
        }),
      });

      const data = await res.json();
      if (res.ok && data.task_id) {
        addLog("INGESTOR", `Tarea encolada con éxito. ID: ${data.task_id}`, "success");
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

  // Sync workspace domains when active company changes
  useEffect(() => {
    if (selectedCompany?.urn && selectedCompany.urn !== "undefined" && selectedCompany.urn !== "null") {
      loadRagKnowledge(selectedCompany.urn);
      loadSkills(selectedCompany.urn);
      loadCompanyDocuments(selectedCompany.urn);
      loadHistory(selectedCompany.urn);
      loadBrandAssets(selectedCompany.urn);
      loadRagPosts(selectedCompany.urn);
      loadEngagementMetrics(selectedCompany.urn);
      loadRagUrls(selectedCompany.urn);
    }
  }, [selectedCompany]);

  if (authError) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center p-4">
        <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 text-center max-w-md">
          <div className="w-12 h-12 bg-rose-50 text-rose-600 rounded-xl flex items-center justify-center mx-auto mb-4 border border-rose-200">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">Sesión requerida</h2>
          <p className="text-slate-600 text-xs mb-6 leading-relaxed">{authError}</p>
          <button
            onClick={() => {
              document.cookie = "aipost_session_id=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; samesite=lax";
              localStorage.removeItem("aipost_session_token");
              window.location.href = "/login";
            }}
            className="w-full bg-brand-teal hover:bg-brand-teal-dark text-white font-bold py-2.5 rounded-lg text-xs transition-all shadow-xs cursor-pointer"
          >
            Iniciar sesión
          </button>
        </div>
      </div>
    );
  }

  const handleOpenEditModal = (post: any) => {
    setEditModalPost(post);
    setIsEditModalOpen(true);
  };

  const handleSaveEditedDraft = async (updatedContent: string) => {
    if (!editModalPost) return;
    await handleSaveDraft({
      id: editModalPost.id,
      account_id: editModalPost.account_id || selectedCompany?.urn,
      content: updatedContent,
    });
    if (currentPostId === editModalPost.id || (!currentPostId && editModalPost.content === draftContent)) {
      setDraftContent(updatedContent);
    }
    resetGeneratorState();
    loadHistory(selectedCompany?.urn);
    showToast("Publicación actualizada correctamente", "success");
  };

  const handleImproveEditedPostWithAI = async (updatedContent: string, instructions: string) => {
    if (!editModalPost) return;
    setActiveTab("generator");
    showToast("Iniciando optimización con IA...", "info");
    await handleGeneratePost(
      {
        ...editModalPost,
        content: updatedContent,
      },
      instructions
    );
  };

  const handleCancelEdit = () => {
    resetGeneratorState();
    setActiveTab("generator");
    showToast("Modo de edición cancelado. Listo para redactar un nuevo post.", "info");
  };

  const handleResetStudio = () => {
    resetGeneratorState();
    showToast("Lienzo restablecido. Todo limpio para un nuevo post.", "info");
  };

  const handleStudioSave = async () => {
    if (editingPost) {
      await handleSaveDraft({
        id: editingPost.id || currentPostId,
        account_id: selectedCompany?.urn,
        content: draftContent,
      });
      resetGeneratorState();
      loadHistory(selectedCompany?.urn);
      setActiveTab("history");
      showToast("Publicación actualizada y guardada con éxito en el Histórico", "success");
    } else {
      await handleSaveDraft({
        content: draftContent,
        account_id: selectedCompany?.urn,
      });
      showToast("Borrador guardado exitosamente", "success");
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F0F2F5] text-slate-800 font-sans">
      <AppHeader
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        selectedCompany={selectedCompany}
        setSelectedCompany={setSelectedCompany}
        companies={companies}
        loadCompanies={loadCompanies}
        isLinkedinConnected={isLinkedinConnected}
        handleConnectLinkedin={handleConnectLinkedin}
        handleDisconnectLinkedin={handleDisconnectLinkedin}
        handleLogout={handleLogout}
        userInfo={userInfo}
      />

      <main className="flex-1 w-full pb-16">
        {activeTab === "generator" && (
          <Studio
            promptQuery={promptQuery}
            setPromptQuery={setPromptQuery}
            linkUrl={linkUrl}
            setLinkUrl={setLinkUrl}
            skills={skills}
            selectedSkillIds={selectedSkillIds}
            setSelectedSkillIds={setSelectedSkillIds}
            isGenerating={isGenerating}
            onGenerate={() => handleGeneratePost()}
            onStop={handleStopGeneration}
            activeAgent={activeAgent}
            agentSteps={agentSteps}
            draftContent={draftContent}
            draftHashtags={draftHashtags}
            draftCta={draftCta}
            selectedCompany={selectedCompany}
            userInfo={userInfo}
            factCheck={factCheck}
            safetyReport={safetyReport}
            knowledgeGap={knowledgeGap}
            checkpointConfig={checkpointConfig}
            userFeedback={userFeedback}
            setUserFeedback={setUserFeedback}
            onSubmitFeedback={(isApproved: boolean) => handleResumeWorkflow(isApproved ? "aprobar" : userFeedback)}
            isSubmittingFeedback={isSubmittingFeedback}
            onSaveDraft={handleStudioSave}
            onSchedule={() => {
              handleScheduleDialog({ content: draftContent, hashtags: draftHashtags, cta: draftCta });
            }}
            onPublish={() => {
              handlePublishNow({ content: draftContent, hashtags: draftHashtags, cta: draftCta });
            }}
            onEdit={() => {
              handleOpenEditModal({
                id: currentPostId || editingPost?.id,
                account_id: selectedCompany?.urn,
                content: draftContent,
                status: "draft"
              });
            }}
            isPublishing={publishStatus === "loading"}
            terminalLogs={terminalLogs}
            taskStatus={taskStatus}
            clearLogs={clearLogs}
            editingPost={editingPost}
            editInstruction={editInstruction}
            setEditInstruction={setEditInstruction}
            onCancelEdit={handleCancelEdit}
            onResetStudio={handleResetStudio}
          />
        )}

        {/* Tab 2: Knowledge Base & RAG (Slide 2 Enterprise Layout) */}
        {activeTab === "knowledge" && (
          <KnowledgeBaseView
            selectedCompany={selectedCompany}
            ragContent={ragContent}
            isLoadingRag={isLoadingRag}
            pdfDocuments={pdfDocuments}
            isUploadingPdf={isUploadingPdf}
            onUploadPdf={handleUploadPdf}
            onDeleteDocument={handleDeleteDocument}
            ragUrls={ragUrls}
            urlToAdd={urlToAdd}
            setUrlToAdd={setUrlToAdd}
            isIngestingUrl={isIngestingUrl}
            onAddUrl={handleAddUrl}
            onDeleteUrl={handleDeleteUrl}
            localDos={localDos}
            setLocalDos={setLocalDos}
            localDonts={localDonts}
            setLocalDonts={setLocalDonts}
            isSavingBrandAssets={isSavingBrandAssets}
            onSaveBrandAssets={handleSaveBrandAssets}
            localAboutUs={localAboutUs}
            setLocalAboutUs={setLocalAboutUs}
            localSpecialties={localSpecialties}
            setLocalSpecialties={setLocalSpecialties}
            onViewDocContent={loadDocumentContent}
            onTriggerSync={handleTriggerSync}
            isSyncingCompany={isSyncingCompany}
          />
        )}

        {/* Tab 3: Skills & Directives Workspace */}
        {activeTab === "skills" && (
          <SkillsView
            skills={skills}
            activeWorkspaceSkill={activeWorkspaceSkill}
            setActiveWorkspaceSkill={setActiveWorkspaceSkill}
            workspaceSkillName={workspaceSkillName}
            setWorkspaceSkillName={setWorkspaceSkillName}
            workspaceSkillDesc={workspaceSkillDesc}
            setWorkspaceSkillDesc={setWorkspaceSkillDesc}
            workspaceSkillMarkdown={workspaceSkillMarkdown}
            setWorkspaceSkillMarkdown={setWorkspaceSkillMarkdown}
            handleCreateSkill={handleCreateSkill}
            handleUpdateSkill={(id, name, desc, md) => handleUpdateSkill(id, name, desc, md)}
            handleDeleteSkill={handleDeleteSkill}
          />
        )}

        {activeTab === "history" && (
          <HistoryView
            postsHistory={postsHistory}
            isLoadingHistory={isLoadingHistory}
            loadHistory={loadHistory}
            selectedOrgUrn={selectedCompany?.urn}
            companies={companies}
            onViewPost={(post) => {
              setViewPostData(post);
              setIsViewPostModalOpen(true);
            }}
            onEditPost={(post) => {
              handleOpenEditModal(post);
            }}
            onPublishNow={(post) => {
              handlePublishNow(post);
            }}
            onScheduleDialog={(post) => {
              handleScheduleDialog(post);
            }}
            onDeletePost={(postId) => {
              handleDeletePost(postId);
            }}
          />
        )}
      </main>

      <ViewPostModal
        isOpen={isViewPostModalOpen}
        onClose={() => {
          setIsViewPostModalOpen(false);
          setViewPostData(null);
        }}
        post={viewPostData}
        companies={companies}
      />

      <EditPostModal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setEditModalPost(null);
        }}
        post={editModalPost}
        companies={companies}
        onSaveManual={handleSaveEditedDraft}
        onUpdateWithAI={handleImproveEditedPostWithAI}
      />

      <DocContentModal
        isOpen={isDocModalOpen}
        onClose={() => {
          setIsDocModalOpen(false);
          setSelectedDoc(null);
        }}
        selectedDoc={selectedDoc}
        docContentLoading={docContentLoading}
        selectedCompanyUrn={selectedCompany?.urn}
        authToken={authToken}
      />

      {isScheduleModalOpen && (
        <ScheduleModal
          scheduleDate={scheduleDate}
          onChange={setScheduleDate}
          onConfirm={submitSchedule}
          onClose={() => setIsScheduleModalOpen(false)}
        />
      )}

      {isPublishStatusModalOpen && (
        <PublishStatusModal
          status={publishStatus}
          onClose={() => setIsPublishStatusModalOpen(false)}
        />
      )}

      {/* Global Toast */}
      <Toast toast={toastMessage} onClose={clearToast} />
    </div>
  );
}
