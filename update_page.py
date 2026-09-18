import os
import re

file_path = "/Users/evan/Documents/UNIVERSIDAD/GRADO/TFG/PostFast/postfast-frontend/src/app/page.tsx"
with open(file_path, "r") as f:
    content = f.read()

# 1. Update lucide-react imports
content = content.replace("Check,\n  AlertCircle\n} from \"lucide-react\";", "Check,\n  AlertCircle,\n  Wand2,\n  FileText,\n  Upload,\n  Trash2\n} from \"lucide-react\";")

# 2. Update activeTab type
content = content.replace("const [activeTab, setActiveTab] = useState<\"dashboard\" | \"generator\" | \"rag\" | \"history\">(\"generator\");", "const [activeTab, setActiveTab] = useState<\"dashboard\" | \"generator\" | \"rag\" | \"history\" | \"skills\">(\"generator\");")

# 3. Add new states
new_states = """
  // Skills
  const [skills, setSkills] = useState<any[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState<string>("");
  const [newSkillName, setNewSkillName] = useState("");
  const [newSkillDesc, setNewSkillDesc] = useState("");
  const [newSkillMarkdown, setNewSkillMarkdown] = useState("");

  // PDFs
  const [pdfDocuments, setPdfDocuments] = useState<any[]>([]);
  const [isUploadingPdf, setIsUploadingPdf] = useState(false);
"""
content = content.replace("  // Auth & Organizations", new_states + "\n  // Auth & Organizations")

# 4. Add load functions inside component
load_functions = """
  const loadSkills = async (urn: string) => {
    try {
      const res = await fetch(`http://localhost:8000/content/skills?org_urn=${encodeURIComponent(urn)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) setSkills(await res.json());
    } catch (err) { console.error(err); }
  };

  const loadCompanyDocuments = async (urn: string) => {
    try {
      const res = await fetch(`http://localhost:8000/content/company/documents?org_urn=${encodeURIComponent(urn)}`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.ok) setPdfDocuments(await res.json());
    } catch (err) { console.error(err); }
  };

  const handleCreateSkill = async () => {
    if (!selectedCompany) return;
    try {
      const res = await fetch("http://localhost:8000/content/skills", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({ org_urn: selectedCompany.urn, name: newSkillName, description: newSkillDesc, markdown_content: newSkillMarkdown })
      });
      if (res.ok) {
        setNewSkillName(""); setNewSkillDesc(""); setNewSkillMarkdown("");
        loadSkills(selectedCompany.urn);
      }
    } catch (e) {}
  };

  const handleDeleteSkill = async (id: string) => {
    try {
      await fetch(`http://localhost:8000/content/skills/${id}`, { method: "DELETE", headers: { "Authorization": `Bearer ${authToken}` } });
      if (selectedCompany) loadSkills(selectedCompany.urn);
    } catch (e) {}
  };

  const handleUploadPdf = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedCompany || !e.target.files || e.target.files.length === 0) return;
    setIsUploadingPdf(true);
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const res = await fetch(`http://localhost:8000/content/company/upload_pdf?org_urn=${encodeURIComponent(selectedCompany.urn)}`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${authToken}` },
        body: formData
      });
      if (res.ok) {
        if (selectedCompany) loadCompanyDocuments(selectedCompany.urn);
      }
    } catch (err) { console.error(err); }
    finally { setIsUploadingPdf(false); e.target.value = ''; }
  };

  const handleDeleteDocument = async (filename: string) => {
    if (!selectedCompany) return;
    try {
      await fetch(`http://localhost:8000/content/company/documents?org_urn=${encodeURIComponent(selectedCompany.urn)}&filename=${encodeURIComponent(filename)}`, { 
        method: "DELETE", headers: { "Authorization": `Bearer ${authToken}` } 
      });
      loadCompanyDocuments(selectedCompany.urn);
    } catch (e) {}
  };
"""
content = content.replace("  const loadCompanies = async () => {", load_functions + "\n  const loadCompanies = async () => {")

# 5. Call loadSkills and loadCompanyDocuments in selectedCompany useEffect
content = content.replace("""  // Cargar RAG al cambiar de organización seleccionada
  useEffect(() => {
    if (selectedCompany) {
      loadRagKnowledge(selectedCompany.urn);
    }
  }, [selectedCompany]);""", """  // Cargar RAG al cambiar de organización seleccionada
  useEffect(() => {
    if (selectedCompany) {
      loadRagKnowledge(selectedCompany.urn);
      loadSkills(selectedCompany.urn);
      loadCompanyDocuments(selectedCompany.urn);
    }
  }, [selectedCompany]);""")

# 6. Add "skill_id" to payload in handleGeneratePost
content = content.replace("""        selected_account: {
          urn: selectedCompany.urn,
          name: selectedCompany.name,
          vanityName: selectedCompany.vanity_name || selectedCompany.name.toLowerCase().replace(/\s/g, "")
        }
      };""", """        selected_account: {
          urn: selectedCompany.urn,
          name: selectedCompany.name,
          vanityName: selectedCompany.vanity_name || selectedCompany.name.toLowerCase().replace(/\\s/g, "")
        },
        skill_id: selectedSkillId || null
      };""")

content = content.replace("http://localhost:8000/generate_post", "http://localhost:8000/content/generate_post")

# 7. Add Sidebar Tab for Skills
sidebar_rag = """          <button 
            onClick={() => setActiveTab("rag")}"""
sidebar_skills = """          <button 
            onClick={() => setActiveTab("skills")}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
              activeTab === "skills" 
                ? "bg-gradient-to-r from-indigo-600/20 to-violet-600/10 text-indigo-300 border-l-4 border-indigo-500 shadow-inner" 
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
            }`}
          >
            <Wand2 className="h-4.5 w-4.5" />
            Habilidades (Skills)
          </button>
"""
content = content.replace(sidebar_rag, sidebar_skills + "\n" + sidebar_rag)

# 8. Add skill selector to generator form
skill_selector = """
                  <div className="flex flex-col gap-1.5 md:col-span-2">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Habilidad (Skill) - Opcional</label>
                    <select 
                      value={selectedSkillId}
                      onChange={(e) => setSelectedSkillId(e.target.value)}
                      className="bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-medium cursor-pointer"
                    >
                      <option value="">Ninguna (Redacción libre)</option>
                      {skills.map(s => (
                        <option key={s.id} value={s.id}>{s.name} - {s.description}</option>
                      ))}
                    </select>
                    {selectedSkillId && (
                       <div className="mt-2 bg-indigo-900/20 border border-indigo-500/30 p-3 rounded-lg text-xs text-indigo-200 italic">
                         Aplicando reglas de escritura de la habilidad seleccionada.
                       </div>
                    )}
                  </div>
"""
content = content.replace("""                  <div className="flex flex-col gap-1.5 md:col-span-2">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">URL de Referencia (Opcional)</label>""", skill_selector + """                  <div className="flex flex-col gap-1.5 md:col-span-2">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">URL de Referencia (Opcional)</label>""")

# 9. Modify RAG tab to include PDF column
rag_tab_content = """                  <div className="bg-slate-950/30 backdrop-blur-md rounded-2xl border border-slate-800 p-6 flex flex-col gap-4">
                    <h3 className="font-bold text-slate-200 border-b border-slate-800 pb-3 text-sm flex items-center gap-2">
                      <FileText className="h-4.5 w-4.5 text-indigo-400" />
                      DOCUMENTACIÓN CORPORATIVA (PDFs)
                    </h3>
                    <div className="flex flex-col gap-4">
                      <div className="flex items-center gap-2">
                        <label className="flex-1 flex flex-col items-center justify-center p-4 border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-xl cursor-pointer bg-slate-900/50 transition-colors">
                          <Upload className="h-6 w-6 text-slate-400 mb-2" />
                          <span className="text-xs text-slate-300 font-semibold">{isUploadingPdf ? "Subiendo..." : "Subir archivo PDF"}</span>
                          <input type="file" accept=".pdf" className="hidden" onChange={handleUploadPdf} disabled={isUploadingPdf} />
                        </label>
                      </div>
                      
                      <div className="flex flex-col gap-2">
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">PDFs Indexados</span>
                        {pdfDocuments.length === 0 ? (
                          <span className="text-xs text-slate-500 italic">No hay documentos subidos.</span>
                        ) : (
                          pdfDocuments.map((doc, i) => (
                            <div key={i} className="flex items-center justify-between p-3 bg-slate-900/50 border border-slate-800 rounded-lg">
                              <span className="text-xs text-slate-300 font-mono truncate mr-2">{doc.filename}</span>
                              <button onClick={() => handleDeleteDocument(doc.filename)} className="p-1.5 text-rose-400 hover:bg-rose-500/20 rounded transition-colors">
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </section>"""
content = content.replace("                </section>\n              ) : (", rag_tab_content + "\n              ) : (")

# 10. Add Skills Tab implementation at the end before </main>
skills_tab = """
          {/* TAB 4: SKILLS */}
          {activeTab === "skills" && (
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              <div className="md:col-span-5 flex flex-col gap-4">
                <div className="bg-slate-950/40 backdrop-blur-md rounded-2xl border border-slate-800 p-6 flex flex-col gap-4">
                  <h3 className="font-bold text-slate-200 border-b border-slate-800 pb-3 text-sm flex items-center gap-2">
                    <Wand2 className="h-4.5 w-4.5 text-indigo-400" />
                    MIS HABILIDADES (SKILLS)
                  </h3>
                  <div className="flex flex-col gap-3">
                    {skills.length === 0 ? (
                      <span className="text-xs text-slate-500 italic">No tienes habilidades creadas.</span>
                    ) : (
                      skills.map(s => (
                        <div key={s.id} className="p-4 bg-slate-900/60 border border-slate-700 rounded-xl relative group">
                          <h4 className="text-sm font-bold text-indigo-300 mb-1">{s.name}</h4>
                          <p className="text-xs text-slate-400 mb-2">{s.description}</p>
                          <button onClick={() => handleDeleteSkill(s.id)} className="absolute top-3 right-3 p-1.5 text-rose-400 hover:bg-rose-500/20 rounded opacity-0 group-hover:opacity-100 transition-all">
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
              <div className="md:col-span-7 flex flex-col gap-4">
                <div className="bg-slate-950/40 backdrop-blur-md rounded-2xl border border-slate-800 p-6 flex flex-col gap-4">
                  <h3 className="font-bold text-slate-200 border-b border-slate-800 pb-3 text-sm flex items-center gap-2">
                    <Edit3 className="h-4.5 w-4.5 text-indigo-400" />
                    CREAR NUEVA HABILIDAD
                  </h3>
                  <div className="flex flex-col gap-3">
                    <input type="text" value={newSkillName} onChange={(e)=>setNewSkillName(e.target.value)} placeholder="Nombre (ej. Tono Técnico)" className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500" />
                    <input type="text" value={newSkillDesc} onChange={(e)=>setNewSkillDesc(e.target.value)} placeholder="Descripción breve" className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500" />
                    <label className="text-xs font-bold text-slate-400 uppercase mt-2">Instrucciones (Markdown)</label>
                    <textarea value={newSkillMarkdown} onChange={(e)=>setNewSkillMarkdown(e.target.value)} rows={10} placeholder="Escribe el prompt o los ejemplos..." className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono" />
                    <button onClick={handleCreateSkill} disabled={!newSkillName || !newSkillMarkdown} className="mt-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-bold text-xs transition-colors disabled:opacity-50 self-end">Guardar Habilidad</button>
                  </div>
                </div>
              </div>
            </div>
          )}
"""
content = content.replace("        </main>\n      </div>", skills_tab + "        </main>\n      </div>")

with open(file_path, "w") as f:
    f.write(content)
print("Page.tsx updated successfully.")
