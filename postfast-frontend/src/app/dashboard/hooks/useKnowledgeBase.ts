import { useState } from "react";
import type { ChangeEvent } from "react";
import type { ToastMessage } from "@/lib/types";

interface UseKnowledgeBaseDeps {
  authToken: string;
  orgUrn: string | undefined;
  addLog: (sender: string, msg: string, type?: ToastMessage["type"]) => void;
}

/** Normaliza el campo `specialties` (string/array/objetos anidados) a lista plana de strings. */
function getSpecialties(profileObj: any): string[] {
  if (!profileObj) return [];
  const specs = profileObj.specialties;
  if (!specs) return [];
  if (typeof specs === "string") {
    try {
      const parsed = JSON.parse(specs);
      return getSpecialties({ specialties: parsed });
    } catch (e) {
      return specs.split(",").map((s: string) => s.trim()).filter(Boolean);
    }
  }
  if (Array.isArray(specs)) {
    const result: string[] = [];
    const processItem = (item: any) => {
      if (!item) return;
      if (typeof item === "string") {
        result.push(item);
      } else if (Array.isArray(item)) {
        item.forEach(processItem);
      } else if (typeof item === "object") {
        if (Array.isArray(item.tags)) {
          item.tags.forEach(processItem);
        } else if (item.tag && typeof item.tag === "string") {
          result.push(item.tag);
        } else if (item.localizedValue && typeof item.localizedValue === "string") {
          result.push(item.localizedValue);
        } else if (item.name && typeof item.name === "string") {
          result.push(item.name);
        } else if (item.value && typeof item.value === "string") {
          result.push(item.value);
        } else {
          Object.values(item).forEach((val) => {
            if (typeof val === "string") {
              result.push(val);
            }
          });
        }
      }
    };
    specs.forEach(processItem);
    return result;
  }
  return [];
}

/** Extrae las listas de Do's y Don'ts del brand book en markdown. */
function parseDosAndDonts(markdown: string): { dos: string[]; donts: string[] } {
  const dos: string[] = [];
  const donts: string[] = [];
  if (!markdown) return { dos, donts };
  const lines = markdown.split("\n");
  let currentSection: "none" | "dos" | "donts" = "none";
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const lower = trimmed.toLowerCase();
    if (lower.includes("do's") || lower.includes("dos") || lower.includes("qué hacer") || lower.includes("qué hacer (do's)")) {
      if (!trimmed.startsWith("-") && !trimmed.startsWith("*")) {
        currentSection = "dos";
        continue;
      }
    } else if (lower.includes("don'ts") || lower.includes("donts") || lower.includes("qué no hacer") || lower.includes("qué no hacer (don'ts)")) {
      if (!trimmed.startsWith("-") && !trimmed.startsWith("*")) {
        currentSection = "donts";
        continue;
      }
    }
    if (trimmed.startsWith("-") || trimmed.startsWith("*")) {
      const content = trimmed
        .replace(/^[-*]\s*/, "")
        .replace(/^\*\*Do's:\*\*\s*/i, "")
        .replace(/^\*\*Don'ts:\*\*\s*/i, "")
        .replace(/^Do's:\s*/i, "")
        .replace(/^Don'ts:\s*/i, "")
        .trim();
      if (content) {
        if (currentSection === "dos" || lower.includes("do's:") || lower.includes("dos:")) {
          dos.push(content);
        } else if (currentSection === "donts" || lower.includes("don'ts:") || lower.includes("donts:")) {
          donts.push(content);
        }
      }
    }
  }
  if (dos.length === 0 && donts.length === 0) {
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("-") || trimmed.startsWith("*")) {
        const content = trimmed.replace(/^[-*]\s*/, "").trim();
        if (content.toLowerCase().startsWith("do's:") || content.toLowerCase().startsWith("**do's:**")) {
          dos.push(content.replace(/^(?:\*\*Do's:\*\*|Do's:)\s*/i, ""));
        } else if (content.toLowerCase().startsWith("don'ts:") || content.toLowerCase().startsWith("**don'ts:**")) {
          donts.push(content.replace(/^(?:\*\*Don'ts:\*\*|Don'ts:)\s*/i, ""));
        }
      }
    }
  }
  if (dos.length === 0 && donts.length === 0) {
    for (const line of lines) {
      const trimmed = line.trim();
      if ((trimmed.startsWith("-") || trimmed.startsWith("*")) && !trimmed.includes("**")) {
        dos.push(trimmed.replace(/^[-*]\s*/, ""));
      }
    }
  }
  return { dos, donts };
}

/**
 * Dominio de la Base de Conocimiento (RAG): documentos PDF, enlaces de interés,
 * brand book (do's/don'ts), "acerca de"/especialidades, posts de referencia,
 * métricas de engagement y el visor de documentos.
 */
export function useKnowledgeBase({ authToken, orgUrn, addLog }: UseKnowledgeBaseDeps) {
  // PDFs
  const [pdfDocuments, setPdfDocuments] = useState<any[]>([]);
  const [isUploadingPdf, setIsUploadingPdf] = useState(false);

  // Perfil RAG / marca
  const [ragContent, setRagContent] = useState<any>(null);
  const [isLoadingRag, setIsLoadingRag] = useState<boolean>(false);
  const [brandBookText, setBrandBookText] = useState<string>("");
  const [localDos, setLocalDos] = useState<string[]>([]);
  const [localDonts, setLocalDonts] = useState<string[]>([]);
  const [newDoText, setNewDoText] = useState("");
  const [newDontText, setNewDontText] = useState("");
  const [editingDoIndex, setEditingDoIndex] = useState<number | null>(null);
  const [editingDoText, setEditingDoText] = useState("");
  const [editingDontIndex, setEditingDontIndex] = useState<number | null>(null);
  const [editingDontText, setEditingDontText] = useState("");
  const [isSavingBrandAssets, setIsSavingBrandAssets] = useState<boolean>(false);
  const [localAboutUs, setLocalAboutUs] = useState<string>("");
  const [localSpecialties, setLocalSpecialties] = useState<string[]>([]);
  const [newSpecialtyText, setNewSpecialtyText] = useState("");
  const [isEditingAboutUs, setIsEditingAboutUs] = useState<boolean>(false);

  // Enlaces de interés (URLs)
  const [ragUrls, setRagUrls] = useState<{ url: string; title: string; created_at: string }[]>([]);
  const [urlToAdd, setUrlToAdd] = useState("");
  const [isIngestingUrl, setIsIngestingUrl] = useState(false);

  // Posts de referencia RAG
  const [ragPosts, setRagPosts] = useState<any[]>([]);
  const [isLoadingRagPosts, setIsLoadingRagPosts] = useState<boolean>(false);

  // Métricas de engagement
  const [engagementMetrics, setEngagementMetrics] = useState<any>(null);
  const [isLoadingMetrics, setIsLoadingMetrics] = useState<boolean>(false);

  // Visor de documentos
  const [selectedDocName, setSelectedDocName] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<any | null>(null);
  const [isDocModalOpen, setIsDocModalOpen] = useState<boolean>(false);
  const [docContentLoading, setDocContentLoading] = useState<boolean>(false);

  const loadCompanyDocuments = async (urn: string) => {
    try {
      const res = await fetch(`http://localhost:8000/content/company/documents?org_urn=${encodeURIComponent(urn)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) setPdfDocuments(await res.json());
    } catch (err) { console.error(err); }
  };

  const handleUploadPdf = async (e: ChangeEvent<HTMLInputElement>) => {
    if (!orgUrn || !e.target.files || e.target.files.length === 0) return;
    setIsUploadingPdf(true);
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`http://localhost:8000/content/company/upload_pdf?org_urn=${encodeURIComponent(orgUrn)}`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${authToken}` },
        body: formData
      });
      if (res.ok) {
        loadCompanyDocuments(orgUrn);
      }
    } catch (err) { console.error(err); }
    finally { setIsUploadingPdf(false); e.target.value = ''; }
  };

  const handleDeleteDocument = async (filename: string) => {
    if (!orgUrn) return;
    try {
      await fetch(`http://localhost:8000/content/company/documents?org_urn=${encodeURIComponent(orgUrn)}&filename=${encodeURIComponent(filename)}`, {
        method: "DELETE", headers: { "Authorization": `Bearer ${authToken}` }
      });
      loadCompanyDocuments(orgUrn);
    } catch (e) {}
  };

  const loadRagKnowledge = async (urn: string) => {
    setIsLoadingRag(true);
    try {
      const res = await fetch(`http://localhost:8000/content/company/profiles/${encodeURIComponent(urn)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRagContent(data);
        const profile = data.company_profile || data.company_profile_data || {};
        setLocalAboutUs(profile.about_us_content || "");
        setLocalSpecialties(getSpecialties(profile));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingRag(false);
    }
  };

  const loadBrandAssets = async (urn: string) => {
    try {
      const res = await fetch(`http://localhost:8000/content/company/brand_assets?org_urn=${encodeURIComponent(urn)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setBrandBookText(data.brand_book || "");
        const { dos, donts } = parseDosAndDonts(data.brand_book || "");
        setLocalDos(dos);
        setLocalDonts(donts);
      }
    } catch (err) {
      console.error("Error loading brand assets:", err);
    }
  };

  const loadRagUrls = async (urn: string) => {
    try {
      const res = await fetch(`http://localhost:8000/content/company/urls?org_urn=${encodeURIComponent(urn)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) setRagUrls(await res.json());
    } catch (err) {
      console.error("Error loading RAG URLs:", err);
    }
  };

  const handleAddUrl = async () => {
    if (!orgUrn || !urlToAdd.trim()) return;
    setIsIngestingUrl(true);
    try {
      const res = await fetch(`http://localhost:8000/content/company/ingest_url`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({ org_urn: orgUrn, url: urlToAdd.trim() })
      });
      const data = await res.json();
      if (res.ok) {
        addLog("RAG", `URL indexada en la base de conocimiento: ${data.title || urlToAdd} (${data.chunks_indexed} fragmentos).`, "success");
        setUrlToAdd("");
        loadRagUrls(orgUrn);
      } else {
        addLog("RAG", `No se pudo indexar la URL: ${data.detail || "Error desconocido"}`, "error");
      }
    } catch (err: any) {
      addLog("RAG", `Error de red al indexar la URL: ${err.message}`, "error");
    } finally {
      setIsIngestingUrl(false);
    }
  };

  const handleDeleteUrl = async (url: string) => {
    if (!orgUrn) return;
    try {
      await fetch(`http://localhost:8000/content/company/urls?org_urn=${encodeURIComponent(orgUrn)}&url=${encodeURIComponent(url)}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      loadRagUrls(orgUrn);
    } catch (err) {
      console.error("Error deleting RAG URL:", err);
    }
  };

  const loadRagPosts = async (urn: string) => {
    setIsLoadingRagPosts(true);
    try {
      const res = await fetch(`http://localhost:8000/content/company/rag_posts?org_urn=${encodeURIComponent(urn)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRagPosts(data);
      }
    } catch (err) {
      console.error("Error loading RAG posts:", err);
    } finally {
      setIsLoadingRagPosts(false);
    }
  };

  const loadEngagementMetrics = async (urn: string) => {
    setIsLoadingMetrics(true);
    try {
      const res = await fetch(`http://localhost:8000/content/engagement/${encodeURIComponent(urn)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setEngagementMetrics(data);
      }
    } catch (err) {
      console.error("Error loading metrics:", err);
    } finally {
      setIsLoadingMetrics(false);
    }
  };

  const loadDocumentContent = async (filename: string) => {
    if (!orgUrn) return;
    setSelectedDocName(filename);
    setIsDocModalOpen(true);
    if (filename.toLowerCase().endsWith(".pdf")) {
      setSelectedDoc({ filename, isPdf: true });
      setDocContentLoading(false);
      return;
    }
    setDocContentLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/content/company/documents/content?org_urn=${encodeURIComponent(orgUrn)}&filename=${encodeURIComponent(filename)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedDoc(data);
      } else {
        setSelectedDoc({ filename, content: "Error al recuperar el contenido del documento." });
      }
    } catch (err) {
      console.error("Error fetching document content:", err);
      setSelectedDoc({ filename, content: "Error de red al recuperar el contenido." });
    } finally {
      setDocContentLoading(false);
    }
  };

  const handleSaveBrandAssets = async () => {
    if (!orgUrn) return;
    setIsSavingBrandAssets(true);

    const brandBookMarkdown = `# Do's y Don'ts para LinkedIn

## Do's
${localDos.map(item => `- ${item}`).join('\n')}

## Don'ts
${localDonts.map(item => `- ${item}`).join('\n')}
`;

    try {
      const res = await fetch(`http://localhost:8000/content/company/brand_assets`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({
          org_urn: orgUrn,
          brand_book: brandBookMarkdown,
          about_us_content: localAboutUs,
          specialties: localSpecialties
        })
      });
      if (res.ok) {
        setBrandBookText(brandBookMarkdown);
        addLog("RAG", "Acerca de, especialidades y guías de estilo actualizados e indexados en el RAG.", "success");
        loadRagKnowledge(orgUrn);
      } else {
        addLog("RAG", "Error al guardar las directrices de la empresa.", "error");
      }
    } catch (err) {
      console.error("Error saving brand assets:", err);
      addLog("RAG", "Error de red al guardar las directrices de la empresa.", "error");
    } finally {
      setIsSavingBrandAssets(false);
    }
  };

  return {
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
  };
}
