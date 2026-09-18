import { useEffect, useRef, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import type { FactCheckReport, SafetyReport, KnowledgeGap, ToastMessage } from "@/lib/types";

type PendingAction = "save_draft" | "publish_now" | "schedule" | null;

interface UseContentGenerationDeps {
  authToken: string;
  selectedCompany: any;
  supabaseConfig: any;
  selectedSkillIds: string[];
  addLog: (sender: string, msg: string, type?: ToastMessage["type"] | "warn") => void;
  clearLogs: () => void;
  loadHistory: (overrideUrn?: string) => void;
  loadRagPosts: (urn: string) => void;
  setActiveTab: (tab: "dashboard" | "generator" | "company" | "rag" | "history" | "skills") => void;
}

/**
 * Núcleo de generación de contenido: formulario del generador, ejecución del
 * pipeline (task + suscripción Realtime), bucle HITL y las acciones de destino
 * del borrador (publicar, guardar, programar). Es el cluster más acoplado del
 * dashboard, por eso vive en un único hook con dependencias inyectadas.
 */
export function useContentGeneration({
  authToken, selectedCompany, supabaseConfig, selectedSkillIds,
  addLog, clearLogs, loadHistory, loadRagPosts, setActiveTab,
}: UseContentGenerationDeps) {
  // Formulario del generador
  const [promptQuery, setPromptQuery] = useState<string>("");
  const [selectedTone, setSelectedTone] = useState<string>("");
  const [linkUrl, setLinkUrl] = useState<string>("");
  const [editingPost, setEditingPost] = useState<any | null>(null);
  const [editInstruction, setEditInstruction] = useState<string>("");

  // Task / Realtime / HITL
  const [taskId, setTaskId] = useState<string | null>(null);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [draftContent, setDraftContent] = useState<string>("");
  const [draftHashtags, setDraftHashtags] = useState<string[]>([]);
  const [draftCta, setDraftCta] = useState<string>("");
  const [factCheck, setFactCheck] = useState<FactCheckReport | null>(null);
  const [safetyReport, setSafetyReport] = useState<SafetyReport | null>(null);
  const [knowledgeGap, setKnowledgeGap] = useState<KnowledgeGap | null>(null);
  const [userFeedback, setUserFeedback] = useState<string>("");
  const [checkpointConfig, setCheckpointConfig] = useState<any>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState<boolean>(false);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [agentSteps, setAgentSteps] = useState<string[]>([]);
  const [submittedPrompt, setSubmittedPrompt] = useState<string>("");
  const [showFullPrompt, setShowFullPrompt] = useState(false);
  const [currentPostId, setCurrentPostId] = useState<string | null>(null);

  // Acciones de destino / scheduling
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const pendingActionRef = useRef<PendingAction>(null);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [schedulePostData, setSchedulePostData] = useState<any>(null);
  const [scheduleDate, setScheduleDate] = useState<string>("");
  const [isPublishStatusModalOpen, setIsPublishStatusModalOpen] = useState(false);
  const [publishStatus, setPublishStatus] = useState<"loading" | "success" | "error" | null>(null);

  const handlePublishNow = async (post: any) => {
    setPublishStatus("loading");
    setIsPublishStatusModalOpen(true);
    try {
      const res = await fetch(`http://localhost:8000/content/schedule_post`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({
          platform: "linkedin",
          account_id: post.account_id,
          content: post.content,
          scheduled_time_str: null,
          post_id: currentPostId || post.id || null,
          thread_id: currentThreadId || post.thread_id || null
        })
      });
      if (res.ok) {
        setPublishStatus("success");
        addLog("SISTEMA", "Post publicado exitosamente en LinkedIn.", "success");
      } else {
        setPublishStatus("error");
        const errData = await res.json().catch(() => ({}));
        addLog("SISTEMA", `Error al publicar post: ${errData.detail || "Error desconocido"}`, "error");
      }
      loadHistory(selectedCompany?.urn);
      loadRagPosts(selectedCompany?.urn);
    } catch (e) {
      console.error(e);
      setPublishStatus("error");
      addLog("SISTEMA", "Error al enviar la petición de publicación.", "error");
    }
  };

  const handleSaveDraft = async (post: any) => {
    try {
      const res = await fetch(`http://localhost:8000/content/save_draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({
          platform: "linkedin",
          account_id: post.account_id,
          content: post.content,
          scheduled_time_str: null,
          post_id: currentPostId || post.id || null,
          thread_id: currentThreadId || post.thread_id || null
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        addLog("SISTEMA", `Error al guardar borrador: ${errData.detail || "Error desconocido"}`, "error");
        return;
      }

      const data = await res.json();
      if (data && data.post_id) {
        setCurrentPostId(data.post_id);
      }
      loadHistory(selectedCompany?.urn);
      addLog("SISTEMA", "Borrador guardado exitosamente.", "success");
    } catch (e) {
      console.error(e);
      addLog("SISTEMA", "Fallo de red al intentar guardar el borrador.", "error");
    }
  };

  // Suscripción a Supabase Broadcast en tiempo real (progreso del pipeline).
  useEffect(() => {
    if (!supabaseConfig || !taskId) return;

    const supabase = createClient(supabaseConfig.supabase_url, supabaseConfig.supabase_key);

    addLog("WEBSOCKET", `Suscribiéndose al canal de broadcast 'task:${taskId}'...`, "info");

    const channel = supabase.channel(`task:${taskId}`)
      .on("broadcast", { event: "status_changed" }, (payload: any) => {
        const data = payload.payload;
        console.log("Realtime broadcast recibido:", data);

        if (data.status) {
          setTaskStatus(data.status);
        }

        if (data.message) {
          addLog("CELERY WORKER", data.message, "info");
        }

        // Manejar progresos específicos de nodos en el grafo
        if (data.node) {
          let type: "info" | "success" | "warn" | "error" = "info";
          let prefix = `[Agente: ${data.node}]`;
          if (data.status === "FAILED") type = "error";

          addLog(prefix, data.message || "Procesando tarea...", type);
          setActiveAgent(data.node);
          // Registrar el paso en el pipeline dinámico (orden real de ejecución)
          setAgentSteps(prev => prev.includes(data.node) ? prev : [...prev, data.node]);
        }

        // Si entramos en estado interactivo
        if (data.status === "PENDING_USER_INPUT") {
          addLog("SUPERVISOR", "Generación finalizada. Entrando en fase de revisión interactiva (HITL).", "success");
          setCheckpointConfig(data.checkpoint);
          setDraftContent(data.draft_content || "");
          setFactCheck(data.fact_check_report);
          setSafetyReport(data.safety_report);
          if (data.knowledge_gap !== undefined) setKnowledgeGap(data.knowledge_gap);
          setIsGenerating(false);
          setActiveAgent(null);
        }

        // Si la tarea se completó exitosamente
        if (data.status === "COMPLETED") {
          addLog("SUPERVISOR", "¡Publicación aprobada con éxito!", "success");
          setDraftContent(data.final_post || "");
          if (data.fact_check_report) {
            setFactCheck(data.fact_check_report);
          }
          if (data.safety_report) {
            setSafetyReport(data.safety_report);
          }
          if (data.knowledge_gap !== undefined) setKnowledgeGap(data.knowledge_gap);
          setIsGenerating(false);
          setActiveAgent(null);

          // Ejecutar la acción pendiente
          const action = pendingActionRef.current;
          if (action === "publish_now") {
            handlePublishNow({ account_id: selectedCompany?.urn, content: data.final_post });
          } else if (action === "save_draft") {
            handleSaveDraft({ account_id: selectedCompany?.urn, content: data.final_post });
          } else if (action === "schedule") {
            setSchedulePostData({ account_id: selectedCompany?.urn, content: data.final_post });
            setIsScheduleModalOpen(true);
          }

          pendingActionRef.current = null;
          setPendingAction(null);
          loadHistory(selectedCompany?.urn);
        }

        // Si falló
        if (data.status === "FAILED") {
          addLog("ERROR", `Fallo crítico en la ejecución del pipeline: ${data.error || "Desconocido"}`, "error");
          setIsGenerating(false);
          setActiveAgent(null);
        }
      })
      .subscribe((status) => {
        if (status === "SUBSCRIBED") {
          addLog("WEBSOCKET", "Conectado exitosamente por WebSocket al canal Realtime de Supabase.", "success");
        }
      });

    return () => {
      supabase.removeChannel(channel);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, supabaseConfig]);

  const handleGeneratePost = async () => {
    if (!selectedCompany) {
      addLog("GENERATOR", "Error: Selecciona una organización conectada primero.", "error");
      return;
    }

    setIsGenerating(true);

    // Generar un ID único que se usará alineado como post_id y thread_id de LangGraph
    const generateUUID = () => {
      if (typeof crypto !== "undefined" && crypto.randomUUID) {
        return crypto.randomUUID();
      }
      return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        const v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      });
    };
    const generatedId = currentPostId || generateUUID();
    const activeThreadId = currentThreadId || generatedId;

    setCurrentPostId(generatedId);
    setCurrentThreadId(activeThreadId);

    setTaskId(null);
    setTaskStatus("STARTING");
    setCheckpointConfig(null);
    setFactCheck(null);
    setSafetyReport(null);
    setKnowledgeGap(null);
    clearLogs();
    setAgentSteps([]);
    setShowFullPrompt(false);
    // Fijar la petición original que se mostrará anclada durante todo el flujo
    setSubmittedPrompt(editingPost ? `✏️ Edición de post — Instrucciones: ${editInstruction}` : promptQuery);

    addLog("GENERATOR", `Despachando tarea asíncrona a Celery para la empresa '${selectedCompany.name}'...`, "info");

    try {
      const finalQuery = editingPost
        ? `Quiero editar y mejorar este post:\n\n${editingPost.content}\n\nMis instrucciones de mejora: ${editInstruction}`
        : promptQuery;

      const payload = {
        query: finalQuery,
        tone: "Profesional",
        account_name: selectedCompany.name,
        link_url: linkUrl || null,
        selected_account: {
          urn: selectedCompany.urn,
          name: selectedCompany.name,
          vanityName: selectedCompany.vanity_name || selectedCompany.name.toLowerCase().replace(/\s/g, "")
        },
        skill_id: selectedSkillIds.length > 0 ? selectedSkillIds[0] : null,
        selected_skills: selectedSkillIds,
        thread_id: activeThreadId,
        edit_mode: !!editingPost,
        // Protocolo estructurado de edición (el string embebido en query queda como legacy)
        original_post: editingPost ? editingPost.content : null,
        edit_instructions: editingPost ? editInstruction : null
      };

      const res = await fetch("http://localhost:8000/content/generate_post", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (res.ok && data.task_id) {
        addLog("ORQUESTRADOR", `Tarea encolada en Celery. Task ID: ${data.task_id}. Esperando activación de agentes...`, "success");
        if (linkUrl) {
          addLog("RAG", "La URL de referencia se está indexando también en tu base de conocimiento (persistencia a largo plazo).", "info");
        }
        setTaskId(data.task_id);
      } else {
        addLog("ORQUESTRADOR", `Error al iniciar generación: ${data.detail || "Desconocido"}`, "error");
        setIsGenerating(false);
      }
    } catch (err) {
      addLog("ORQUESTRADOR", `Error de comunicación: ${err}`, "error");
      setIsGenerating(false);
    }
  };

  // Enviar feedback al agente en pausa (HITL Loop) o aprobar
  const handleResumeWorkflow = async (feedbackText: string) => {
    if (!taskId) return;

    setIsSubmittingFeedback(true);
    addLog("SISTEMA", feedbackText === "aprobar" ? "Enviando señal de APROBACIÓN final a LinkedIn..." : `Enviando feedback correctivo al Content Writer: "${feedbackText}"`, "info");

    try {
      const res = await fetch("http://localhost:8000/content/generate_post/resume", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({
          task_id: taskId,
          feedback: feedbackText
        })
      });

      const data = await res.json();
      if (res.ok && data.task_id) {
        addLog("ORQUESTRADOR", `Bucle reanudado. Nuevo Task ID asignado: ${data.task_id}. Escuchando agentes...`, "success");
        // Cambiar al nuevo ID de tarea para seguir los nuevos broadcasts
        setCheckpointConfig(null);
        // Reiniciar el pipeline visual: sin esto, los pasos de la generación previa
        // (Profiler, Writer, validadores...) siguen marcados como completados y la
        // nueva pasada con feedback aparece "ya terminada" desde el primer instante.
        setAgentSteps([]);
        setActiveAgent(null);
        setFactCheck(null);
        setSafetyReport(null);
        setTaskId(data.task_id);
        setIsGenerating(true);
        // Estado transitorio: oculta la vista de resultado inmediatamente
        // (evita el solape ejecución+resultado hasta el primer broadcast)
        setTaskStatus("RESUMING");
      } else {
        addLog("ORQUESTRADOR", `Error al reanudar: ${data.detail || "Desconocido"}`, "error");
        setTaskStatus("PENDING_USER_INPUT");
      }
    } catch (err) {
      addLog("ORQUESTRADOR", `Fallo de red al reanudar: ${err}`, "error");
      setTaskStatus("PENDING_USER_INPUT");
    } finally {
      setIsSubmittingFeedback(false);
      setUserFeedback("");
    }
  };

  const handleStopGeneration = async () => {
    if (!taskId) return;

    addLog("SISTEMA", "Enviando solicitud de cancelación para detener la generación...", "warn");
    try {
      const res = await fetch(`http://localhost:8000/content/generate_post/stop/${taskId}`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${authToken}`
        }
      });
      const data = await res.json();
      if (res.ok) {
        addLog("SISTEMA", "Generación de contenido abortada por el usuario.", "success");
      } else {
        addLog("SISTEMA", `Error al parar generación: ${data.detail || "Desconocido"}`, "error");
      }
    } catch (err) {
      addLog("SISTEMA", `Fallo de red al parar generación: ${err}`, "error");
    } finally {
      // Reiniciar estados para permitir una nueva generación
      setIsGenerating(false);
      setTaskId(null);
      setTaskStatus(null);
      setActiveAgent(null);
    }
  };

  // Reset completo del generador: vuelve a la vista inicial (formulario limpio)
  const resetGeneratorState = () => {
    setDraftContent("");
    setTaskId(null);
    setTaskStatus(null);
    setCheckpointConfig(null);
    setFactCheck(null);
    setSafetyReport(null);
    setKnowledgeGap(null);
    clearLogs();
    setAgentSteps([]);
    setSubmittedPrompt("");
    setCurrentThreadId(null);
    setCurrentPostId(null);
    setEditingPost(null);
    setEditInstruction("");
  };

  const handleEditPost = (post: any) => {
    // El thread_id es exactamente el id del post
    const finalThreadId = post.id;

    // Limpiar estados de generación anterior para poder ver el formulario de prompt
    setDraftContent("");
    setTaskId(null);
    setTaskStatus(null);
    setCheckpointConfig(null);
    setFactCheck(null);
    setSafetyReport(null);
    setKnowledgeGap(null);
    clearLogs();
    setAgentSteps([]);
    setSubmittedPrompt("");

    // Configurar el contexto del post a editar
    setEditingPost(post);
    setEditInstruction("");
    setCurrentThreadId(finalThreadId);
    setCurrentPostId(post.id || null);
    setActiveTab("generator");
  };

  const handleDeletePost = async (postId: string) => {
    try {
      await fetch(`http://localhost:8000/content/posts/${postId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      loadHistory(selectedCompany?.urn);
    } catch (e) {
      console.error(e);
    }
  };

  const submitSchedule = async () => {
    if (!scheduleDate || !schedulePostData) return;
    setPublishStatus("loading");
    setIsPublishStatusModalOpen(true);
    try {
      const res = await fetch(`http://localhost:8000/content/schedule_post`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({
            platform: "linkedin",
            account_id: schedulePostData.account_id,
            content: schedulePostData.content,
            scheduled_time_str: new Date(scheduleDate).toISOString(),
            post_id: currentPostId || schedulePostData.id || null,
            thread_id: currentThreadId || schedulePostData.thread_id || null
        })
      });
      if (res.ok) {
        setPublishStatus("success");
        addLog("SISTEMA", `Post programado para ${scheduleDate}`, "success");
        setIsScheduleModalOpen(false);
        setSchedulePostData(null);
        setScheduleDate("");
      } else {
        setPublishStatus("error");
        const errData = await res.json().catch(() => ({}));
        addLog("SISTEMA", `Error al programar post: ${errData.detail || "Error desconocido"}`, "error");
      }
      loadHistory(selectedCompany?.urn);
      loadRagPosts(selectedCompany?.urn);
    } catch (e) {
      console.error(e);
      setPublishStatus("error");
      addLog("SISTEMA", "Error al enviar la petición de programación.", "error");
    }
  };

  const handleScheduleDialog = (post: any) => {
    const defaultDate = new Date(Date.now() + 86400000).toISOString().slice(0, 16);
    setScheduleDate(defaultDate);
    setSchedulePostData(post);
    setIsScheduleModalOpen(true);
  };

  return {
    // Formulario
    promptQuery, setPromptQuery, selectedTone, setSelectedTone,
    linkUrl, setLinkUrl,
    editingPost, setEditingPost, editInstruction, setEditInstruction,
    // Task / Realtime / HITL
    taskId, setTaskId, taskStatus, isGenerating, draftContent, setDraftContent,
    draftHashtags, draftCta, factCheck, setFactCheck, safetyReport, setSafetyReport,
    knowledgeGap,
    userFeedback, setUserFeedback, checkpointConfig, isSubmittingFeedback,
    activeAgent, agentSteps, submittedPrompt, showFullPrompt, setShowFullPrompt,
    currentPostId, setCurrentPostId, currentThreadId, setCurrentThreadId,
    // Acciones / scheduling
    pendingAction, setPendingAction, pendingActionRef,
    isScheduleModalOpen, setIsScheduleModalOpen, schedulePostData, setSchedulePostData,
    scheduleDate, setScheduleDate, isPublishStatusModalOpen, setIsPublishStatusModalOpen, publishStatus,
    // Handlers
    handleGeneratePost, handleResumeWorkflow, handleStopGeneration, resetGeneratorState,
    handleEditPost, handleDeletePost, handlePublishNow, handleSaveDraft, submitSchedule, handleScheduleDialog,
  };
}
