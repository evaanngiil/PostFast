import { useState } from "react";
import type { ToastMessage } from "@/lib/types";

interface UseSkillsDeps {
  authToken: string;
  orgUrn: string | undefined;
  showToast: (text: string, type?: ToastMessage["type"]) => void;
}

/**
 * Dominio de Habilidades (skills): catálogo, selección para el generador y CRUD
 * del workspace de edición.
 */
export function useSkills({ authToken, orgUrn, showToast }: UseSkillsDeps) {
  const [skills, setSkills] = useState<any[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState<string>("");
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([]);
  const [isSkillDropdownOpen, setIsSkillDropdownOpen] = useState(false);
  const [newSkillName, setNewSkillName] = useState("");
  const [newSkillDesc, setNewSkillDesc] = useState("");
  const [newSkillMarkdown, setNewSkillMarkdown] = useState("");

  const [activeWorkspaceSkill, setActiveWorkspaceSkill] = useState<any | null>(null);
  const [workspaceSkillName, setWorkspaceSkillName] = useState("");
  const [workspaceSkillDesc, setWorkspaceSkillDesc] = useState("");
  const [workspaceSkillMarkdown, setWorkspaceSkillMarkdown] = useState("");

  const loadSkills = async (urn: string) => {
    try {
      const res = await fetch(`http://localhost:8000/content/skills?org_urn=${encodeURIComponent(urn)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSkills(data);
        if (data.length > 0) {
          const base = data.find((s: any) => s.name === "Guía de Estilo y Generación (Base)");
          const target = base || data[0];
          setActiveWorkspaceSkill(target);
          setWorkspaceSkillName(target.name);
          setWorkspaceSkillDesc(target.description || "");
          setWorkspaceSkillMarkdown(target.markdown_content || "");
        } else {
          setActiveWorkspaceSkill(null);
          setWorkspaceSkillName("");
          setWorkspaceSkillDesc("");
          setWorkspaceSkillMarkdown("");
        }
      }
    } catch (err) { console.error(err); }
  };

  const handleCreateSkill = async () => {
    if (!orgUrn) return;
    const name = workspaceSkillName || newSkillName;
    const desc = workspaceSkillDesc || newSkillDesc;
    const markdown = workspaceSkillMarkdown || newSkillMarkdown;
    if (!name || !markdown) {
      showToast("El nombre y el contenido son obligatorios.", "error");
      return;
    }
    try {
      const res = await fetch("http://localhost:8000/content/skills", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({ org_urn: orgUrn, name, description: desc, markdown_content: markdown })
      });
      if (res.ok) {
        showToast("Habilidad creada correctamente.", "success");
        setNewSkillName(""); setNewSkillDesc(""); setNewSkillMarkdown("");
        setWorkspaceSkillName(""); setWorkspaceSkillDesc(""); setWorkspaceSkillMarkdown("");
        loadSkills(orgUrn);
      } else {
        showToast("Error al crear la habilidad.", "error");
      }
    } catch (e) {
      console.error(e);
      showToast("Error de red al crear la habilidad.", "error");
    }
  };

  const handleDeleteSkill = async (id: string) => {
    try {
      await fetch(`http://localhost:8000/content/skills/${id}`, { method: "DELETE", headers: { "Authorization": `Bearer ${authToken}` } });
      if (orgUrn) loadSkills(orgUrn);
    } catch (e) {}
  };

  const handleUpdateSkill = async (id: string, name: string, description: string, markdownContent: string) => {
    try {
      const res = await fetch(`http://localhost:8000/content/skills/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({ name, description, markdown_content: markdownContent })
      });
      if (res.ok) {
        showToast("Habilidad actualizada correctamente.", "success");
        if (orgUrn) loadSkills(orgUrn);
      } else {
        showToast("Error al actualizar la habilidad.", "error");
      }
    } catch (e) {
      console.error(e);
      showToast("Error de red al actualizar la habilidad.", "error");
    }
  };

  return {
    skills, setSkills,
    selectedSkillId, setSelectedSkillId,
    selectedSkillIds, setSelectedSkillIds,
    isSkillDropdownOpen, setIsSkillDropdownOpen,
    newSkillName, setNewSkillName,
    newSkillDesc, setNewSkillDesc,
    newSkillMarkdown, setNewSkillMarkdown,
    activeWorkspaceSkill, setActiveWorkspaceSkill,
    workspaceSkillName, setWorkspaceSkillName,
    workspaceSkillDesc, setWorkspaceSkillDesc,
    workspaceSkillMarkdown, setWorkspaceSkillMarkdown,
    loadSkills, handleCreateSkill, handleDeleteSkill, handleUpdateSkill,
  };
}
