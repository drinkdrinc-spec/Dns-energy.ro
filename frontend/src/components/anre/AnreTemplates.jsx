import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Upload, FileDown, Trash2 } from "lucide-react";
import { api, API } from "@/lib/api";

const tok = () => localStorage.getItem("den_token");

export function AnreTemplates() {
  const [d, setD] = useState(null);
  const [help, setHelp] = useState(false);
  useEffect(() => { api.get("/admin/anre/templates").then((r) => setD(r.data)); }, []);
  if (!d) return null;
  const up = async (key, file) => { const fd = new FormData(); fd.append("file", file);
    try { const { data } = await api.post(`/admin/anre/templates/${key}`, fd, { headers: { "Content-Type": "multipart/form-data" } }); setD(data); toast.success("Formular încărcat"); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  const del = async (key) => { if (!window.confirm("Eliminați modelul oficial? Se va folosi din nou modelul standard D-ENERGY.")) return; const { data } = await api.delete(`/admin/anre/templates/${key}`); setD(data); };
  return (
    <div className="den-panel mb-4" data-testid="anre-templates">
      <div className="flex items-center justify-between"><h3 className="font-bold">Formulare oficiale ANRE (modele)</h3>
        <button className="text-xs font-bold" style={{ color: "var(--blue)" }} onClick={() => setHelp(!help)} data-testid="anre-tpl-help-toggle">{help ? "Ascunde" : "Cum se pregătesc"}</button></div>
      <p className="text-xs" style={{ color: "var(--muted)" }}>Încărcați cererea și anexele în varianta actuală ANRE. Word (.docx) cu marcaje {"{{firma}}"} se completează exact pe model; PDF-ul se completează doar dacă are câmpuri de formular cu aceleași nume. Fără model se folosește varianta standard D-ENERGY.</p>
      {help && <div className="text-xs mt-2 grid sm:grid-cols-2 gap-x-4" data-testid="anre-tpl-placeholders">{Object.entries(d.placeholders).map(([k, l]) => <div key={k}><code>{`{{${k}}}`}</code> — {l}</div>)}</div>}
      <table className="w-full text-xs mt-2"><tbody>{d.items.map((i) => { const t = i.template; return (
        <tr key={i.key} className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`anre-tpl-${i.key}`}>
          <td className="py-1.5 font-bold">{i.label}</td>
          <td data-testid={`anre-tpl-status-${i.key}`}>{t ? <>{t.name} · {t.matched?.length || 0} câmpuri recunoscute{!t.matched?.length && <span style={{ color: "#9b2c2c" }}> — nu se poate precompleta, se folosește modelul standard</span>}</> : <span style={{ color: "var(--muted)" }}>model standard D-ENERGY</span>}</td>
          <td className="space-x-2 whitespace-nowrap text-right">
            <label className="cursor-pointer font-bold" style={{ color: "var(--blue)" }}><Upload size={12} className="inline" /> {t ? "Înlocuiește" : "Încarcă"}<input type="file" className="hidden" accept=".docx,application/pdf" onChange={(e) => e.target.files[0] && up(i.key, e.target.files[0])} data-testid={`anre-tpl-upload-${i.key}`} /></label>
            {t && <a href={`${API}/admin/anre/templates/${i.key}/file?auth=${tok()}`} target="_blank" rel="noopener noreferrer" data-testid={`anre-tpl-view-${i.key}`}><FileDown size={12} className="inline" /></a>}
            {t && <button onClick={() => del(i.key)} data-testid={`anre-tpl-delete-${i.key}`}><Trash2 size={12} className="inline" /></button>}
          </td></tr>); })}</tbody></table>
    </div>
  );
}
