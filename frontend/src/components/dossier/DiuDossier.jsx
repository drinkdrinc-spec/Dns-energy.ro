import { useEffect, useState } from "react";
import { FileDown, RefreshCw, Download } from "lucide-react";
import { toast } from "sonner";
import { api, API } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { DiuCircuits } from "./DiuCircuits";

const tok = () => localStorage.getItem("den_token");

export function DiuDossier({ id, form, setVal, setForm, savedAt }) {
  const [pros, setPros] = useState([]);
  const [pid, setPid] = useState(form.pros_id || "");
  const [docs, setDocs] = useState(null);
  const loadDocs = () => api.get(`/diu/${id}/docs`).then((r) => setDocs(r.data)).catch(() => {});
  useEffect(() => { api.get("/data/prosumator").then((r) => setPros(r.data)).catch(() => {}); loadDocs(); }, [id]); // eslint-disable-line
  useEffect(() => { if (savedAt) loadDocs(); }, [savedAt]); // eslint-disable-line

  const importPros = async () => {
    try { const { data } = await api.post(`/diu/${id}/import-pros`, { pros_id: pid }); setForm({ ...form, ...data }); toast.success("Date preluate din dosarul de prosumator"); loadDocs(); }
    catch (e) { toast.error(e.response?.data?.detail || "Eroare"); }
  };
  const pdf = (doc) => `${API}/diu/${id}/pdf?doc=${doc}&auth=${tok()}`;

  return (
    <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="diu-dossier">
      <h3 className="font-bold">Dosarul instalației de utilizare — documente automate</h3>
      <div className="flex flex-wrap items-end gap-2 mt-3">
        <div className="den-field min-w-[260px]"><label>Pornește din dosarul de prosumator</label>
          <select className="den-input" value={pid} onChange={(e) => setPid(e.target.value)} data-testid="diu-pros-select">
            <option value="">Alege dosarul...</option>
            {pros.map((p) => <option key={p.id} value={p.id}>{p.client_name || "fără nume"} — {p.address || p.pod || p.id.slice(0, 6)}</option>)}
          </select></div>
        <Btn variant="secondary" onClick={importPros} disabled={!pid} data-testid="diu-import-btn"><Download size={14} /> Preia datele</Btn>
      </div>
      <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Se preiau clientul, adresa, puterea, operatorul, ATR, protecțiile TG și circuitele invertoarelor. Circuitele existente nu se suprascriu.</p>
      <DiuCircuits form={form} setVal={setVal} />
      <div className="flex items-center justify-between flex-wrap gap-2 mt-5">
        <div className="text-xs font-bold" style={{ color: docs?.complete ? "#166534" : "#9b2c2c" }} data-testid="diu-docs-state">
          {docs ? (docs.complete ? "Toate documentele sunt complete" : "Unele documente au date lipsă (export CIORNĂ)") : ""} · stările se actualizează după „Salvează”</div>
        <div className="flex gap-2">
          <Btn variant="secondary" onClick={loadDocs} data-testid="diu-docs-refresh"><RefreshCw size={14} /> Actualizează</Btn>
          <a href={pdf("all")} target="_blank" rel="noopener noreferrer" data-testid="diu-export"><Btn><FileDown size={14} /> Dosar DI-U complet PDF</Btn></a>
        </div>
      </div>
      <div className="mt-2 space-y-1">{(docs?.positions || []).map((p) => (
        <div key={p.key} className="flex items-start justify-between gap-2 rounded-lg bg-white border px-3 py-2 text-xs" style={{ borderColor: "var(--line)" }} data-testid={`diu-doc-${p.key}`}>
          <div><b>{p.nr}. {p.title}</b>{p.missing.length > 0 && <div style={{ color: "#9b2c2c" }}>Lipsă: {p.missing.join(", ")}</div>}</div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="font-bold rounded-full px-2 py-0.5" style={p.missing.length ? { background: "#fff0f0", color: "#9b2c2c" } : { background: "#eef4ff", color: "#1d4ed8" }} data-testid={`diu-doc-status-${p.key}`}>{p.status}</span>
            <a href={pdf(p.key)} target="_blank" rel="noopener noreferrer" data-testid={`diu-doc-pdf-${p.key}`}><FileDown size={15} style={{ color: "var(--blue)" }} /></a>
          </div>
        </div>))}</div>
    </div>
  );
}
