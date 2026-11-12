import { useEffect, useRef, useState } from "react";
import { api, API } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Eye, FileDown, FileType2, Upload, X, AlertTriangle, Lock, Unlock } from "lucide-react";
import { toast } from "sonner";
import { uploadFile } from "./ClientDocs";
import { AiPrecheck } from "@/components/ai/AiPrecheck";
import { useAuth } from "@/context/AuthContext";
import { can } from "@/lib/plan";

const tok = () => localStorage.getItem("den_token");
const STATUS_STYLE = { "de completat": ["#fff5e8", "#9a5c12", "#e79334"], generat: ["#eef4ff", "#1d4ed8", "#4386e5"], "necesită semnătură": ["#fff8e6", "#8a5a00", "#d7a33d"], "atașat": ["#ecfdf3", "#166534", "#218e50"] };

function Row({ p, id, statuses, reload, preview }) {
  const ref = useRef();
  const put = async (body) => { await api.put(`/dossier/${id}/item/${p.key}`, body); reload(); };
  const url = `${API}/dossier/${id}/file/${encodeURIComponent(p.key)}?auth=${tok()}`;
  const [bg, fg, dot] = STATUS_STYLE[p.status] || STATUS_STYLE.generat;
  const canView = p.source === "generat" || !!p.upload || p.files.length > 0;
  return (
    <div className="grid grid-cols-1 gap-2 border-t py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center" style={{ borderColor: "var(--line)" }} data-testid={`opis-row-${p.nr}`}>
      <div className="min-w-0">
        <div className="flex items-start gap-2.5"><span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: dot }} aria-hidden="true" /><span className="min-w-0"><b className="block text-sm">{p.title}</b><span className="mt-0.5 block text-[11px]" style={{ color: "var(--muted)" }}>{p.upload ? `Încărcat: ${p.upload.original_filename}` : p.source === "generat" ? "Generat din datele dosarului" : p.source === "client" ? "Din fișa clientului" : "Din catalog echipamente"}</span></span></div>
        {p.missing.length > 0 && <div className="ml-5 mt-1 text-[11px]" style={{ color: "#9b2c2c" }}>Lipsă: {p.missing.join(", ")}</div>}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 sm:justify-end">
        <select aria-label={`Stadiu: ${p.title}`} className="den-input max-w-[165px] !py-1 text-[11px]" style={{ background: bg, color: fg, fontWeight: 700 }} value={p.status} data-testid={`opis-status-${p.nr}`}
          onChange={(e) => put({ status: e.target.value === p.auto_status ? null : e.target.value })}>
          {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="flex items-center">
        {canView && <button className="p-1.5 rounded hover:bg-[#eef4ff]" title="Previzualizare" onClick={() => preview(url, p.title)} data-testid={`opis-preview-${p.nr}`}><Eye size={15} style={{ color: "var(--blue)" }} /></button>}
        {canView && <a className="p-1.5 inline-block rounded hover:bg-[#eef4ff]" title="PDF" href={url} target="_blank" rel="noopener noreferrer" data-testid={`opis-pdf-${p.nr}`}><FileDown size={15} style={{ color: "var(--blue)" }} /></a>}
        {p.source === "generat" && p.key !== "schema" && <a className="p-1.5 inline-block rounded hover:bg-[#eef4ff]" title="Word" href={`${url}&fmt=docx`} data-testid={`opis-docx-${p.nr}`}><FileType2 size={15} style={{ color: "var(--blue)" }} /></a>}
        <input ref={ref} type="file" accept="application/pdf,image/*" className="hidden" data-testid={`opis-upload-input-${p.nr}`}
          onChange={async (e) => { const f = e.target.files?.[0]; if (!f) return; await put({ upload: await uploadFile(f), status: null }); toast.success("Document atașat"); ref.current.value = ""; }} />
        <button className="p-1.5 rounded hover:bg-[#eef4ff]" title="Încarcă document existent / semnat" onClick={() => ref.current.click()} data-testid={`opis-upload-${p.nr}`}><Upload size={15} style={{ color: "var(--blue)" }} /></button>
        {p.upload && <button className="p-1.5 rounded hover:bg-[#fff0f0]" title="Elimină documentul încărcat" onClick={() => put({ clear_upload: true })} data-testid={`opis-clear-${p.nr}`}><X size={15} style={{ color: "#b33333" }} /></button>}
        </div>
      </div>
    </div>
  );
}

export function DossierOpis({ id }) {
  const [d, setD] = useState(null);
  const [pv, setPv] = useState(null);
  const [showReport, setShowReport] = useState(false);
  const [pre, setPre] = useState(false);
  const { user } = useAuth();
  const load = () => api.get(`/dossier/${id}`).then((r) => setD(r.data)).catch(() => {});
  useEffect(() => { load(); }, [id]); // eslint-disable-line
  if (!d) return null;
  const doLock = async () => {
    try { await api.post(`/dossier/${id}/${d.finalized ? "reopen" : "finalize"}`); toast.success(d.finalized ? "Dosar redeschis" : "Dosar finalizat — datele din setări sunt înghețate"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Operațiunea a eșuat"); throw e; }
  };
  const lock = () => (!d.finalized && can(user, "ai_gpt") ? setPre(true) : doLock().catch(() => {}));
  return (
    <div className="mt-6 rounded-xl border bg-white p-4 sm:p-5" style={{ borderColor: "var(--line)" }} data-testid="dossier-opis">
      <AiPrecheck id={id} open={pre} onClose={() => setPre(false)} onFinalize={doLock} />
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div>
          <h3 className="font-bold">Acte & poze</h3>
          <button onClick={() => setShowReport(!showReport)} className="text-xs font-bold inline-flex items-center gap-1 mt-1" style={{ color: d.complete ? "#166534" : "#9b2c2c" }} data-testid="opis-report-toggle">
            <AlertTriangle size={13} /> {d.complete ? "Dosar complet" : `${d.missing_total} informații / documente lipsă — vezi raportul`}
          </button>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Btn variant="secondary" onClick={lock} data-testid="opis-finalize">{d.finalized ? <><Unlock size={14} /> Redeschide</> : <><Lock size={14} /> Finalizează dosarul</>}</Btn>
          <a href={`${API}/dossier/${id}/file/opis?auth=${tok()}`} target="_blank" rel="noopener noreferrer" data-testid="opis-declaration"><Btn variant="secondary"><FileDown size={14} /> Opis (declarație autenticitate)</Btn></a>
          <a href={`${API}/dossier/${id}/export?auth=${tok()}`} target="_blank" rel="noopener noreferrer" data-testid="opis-export"><Btn><FileDown size={15} /> Export dosar complet PDF{d.complete ? "" : " (CIORNĂ)"}</Btn></a>
        </div>
      </div>
      {d.finalized && <p className="text-xs mb-2" style={{ color: "#166534" }} data-testid="opis-finalized">Finalizat la {new Date(d.finalized).toLocaleString("ro-RO")} — modificările din setări nu mai afectează acest dosar.</p>}
      {d.signer_warnings?.map((w) => <p key={w} className="text-xs mb-1" style={{ color: "#9b2c2c" }} data-testid="signer-warning">⚠ {w}</p>)}
      <p className="text-[11px] mb-2" style={{ color: "var(--muted)" }}>Modificările din formular (semnatari, teste, reglaje, date) se reflectă în opis și documente după „Salvează”.</p>
      {showReport && (
        <div className="rounded-lg bg-white border p-3 mb-3 text-xs" style={{ borderColor: "var(--line)" }} data-testid="opis-report">
          {d.common_missing?.length > 0 && <div className="mb-2"><b>Date comune (client / executant), folosite în toate documentele generate:</b> {d.common_missing.join(", ")}</div>}
          {d.positions.filter((p) => p.missing.length).map((p) => <div key={p.key} className="mb-1"><b>{p.nr}. {p.title}:</b> {p.missing.join(", ")}</div>)}
          {d.complete && "Nu lipsește nimic."}
        </div>
      )}
      <div className="mt-3" aria-label="Documente dosar">
        <div className="mb-2 text-right text-[11px]" style={{ color: "var(--muted)" }}>{d.positions.length} fișiere</div>
        {d.positions.map((p) => <Row key={p.key} p={p} id={id} statuses={d.statuses} reload={load} preview={(u, t) => setPv({ u, t })} />)}
      </div>
      {pv && (
        <div className="fixed inset-0 z-50 bg-black/60 flex flex-col p-3 sm:p-8" data-testid="opis-preview-modal">
          <div className="flex items-center justify-between bg-white rounded-t-lg px-4 py-2"><b className="text-sm">{pv.t}</b><button onClick={() => setPv(null)} data-testid="opis-preview-close"><X size={18} /></button></div>
          <iframe title="preview" src={pv.u} className="flex-1 w-full bg-white rounded-b-lg" />
        </div>
      )}
    </div>
  );
}

