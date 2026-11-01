import { useEffect, useRef, useState } from "react";
import { api, downloadAuthenticatedFile, openAuthenticatedFile } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Eye, FileDown, FileType2, Upload, X, AlertTriangle, Lock, Unlock } from "lucide-react";
import { toast } from "sonner";
import { uploadFile } from "./ClientDocs";
import { AiPrecheck } from "@/components/ai/AiPrecheck";
import { useAuth } from "@/context/AuthContext";
import { can } from "@/lib/plan";

 const STATUS_STYLE = { "de completat": ["#fff0f0", "#9b2c2c"], generat: ["#eef4ff", "#1d4ed8"], "necesită semnătură": ["#fff8e6", "#8a5a00"], "atașat": ["#ecfdf3", "#166534"] };

function Row({ p, id, statuses, reload, preview }) {
  const ref = useRef();
  const put = async (body) => { await api.put(`/dossier/${id}/item/${p.key}`, body); reload(); };
  const filePath = `/dossier/${id}/file/${encodeURIComponent(p.key)}`;
  const [bg, fg] = STATUS_STYLE[p.status] || STATUS_STYLE.generat;
  const canView = p.source === "generat" || !!p.upload || p.files.length > 0;
  return (
    <tr className="border-t align-top" style={{ borderColor: "var(--line)" }} data-testid={`opis-row-${p.nr}`}>
      <td className="px-2 py-2.5 font-bold">{p.nr}</td>
      <td className="px-2 py-2.5">
        <div className="font-semibold">{p.title}</div>
        <div className="text-[11px]" style={{ color: "var(--muted)" }}>{p.upload ? `Încărcat: ${p.upload.original_filename}` : p.source === "generat" ? "Generat din datele dosarului" : p.source === "client" ? "Din fișa clientului" : p.source === "manual" ? "Document oficial — atașează PDF-ul aplicabil" : "Din catalog echipamente"}</div>
        {p.key === "gdpr" && <a className="text-[11px] underline inline-block mt-1" style={{ color: "var(--blue)" }} href="https://www.distributie-energie.ro/wp-content/uploads/2026/04/Informare-generala-site-v-feb-2026.pdf" target="_blank" rel="noopener noreferrer">Deschide nota oficială DEER (PDF) ↗</a>}
        {p.missing.length > 0 && <div className="text-[11px] mt-1" style={{ color: "#9b2c2c" }}>Lipsă: {p.missing.join(", ")}</div>}
      </td>
      <td className="px-2 py-2.5">
        <select className="den-input text-xs py-1" style={{ background: bg, color: fg, fontWeight: 700, minWidth: 190 }} value={p.status} data-testid={`opis-status-${p.nr}`}
          onChange={(e) => put({ status: e.target.value === p.auto_status ? null : e.target.value })}>
          {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </td>
      <td className="px-2 py-2.5 whitespace-nowrap text-right">
        {canView && <button className="p-1.5 rounded hover:bg-[#eef4ff]" title="Previzualizare" onClick={() => openAuthenticatedFile(filePath)} data-testid={`opis-preview-${p.nr}`}><Eye size={15} style={{ color: "var(--blue)" }} /></button>}
        {canView && <button type="button" className="p-1.5 inline-block rounded hover:bg-[#eef4ff]" title="Descarcă PDF" onClick={() => downloadAuthenticatedFile(filePath, `document-${p.key}.pdf`)} data-testid={`opis-pdf-${p.nr}`}><FileDown size={15} style={{ color: "var(--blue)" }} /></button>}
        {p.source === "generat" && p.key !== "schema" && <button type="button" className="p-1.5 inline-block rounded hover:bg-[#eef4ff]" title="Descarcă Word" onClick={() => downloadAuthenticatedFile(`${filePath}?fmt=docx`, `document-${p.key}.docx`)} data-testid={`opis-docx-${p.nr}`}><FileType2 size={15} style={{ color: "var(--blue)" }} /></button>}
        <input ref={ref} type="file" accept="application/pdf,image/*" className="hidden" data-testid={`opis-upload-input-${p.nr}`}
          onChange={async (e) => { const f = e.target.files?.[0]; if (!f) return; await put({ upload: await uploadFile(f), status: null }); toast.success("Document atașat"); ref.current.value = ""; }} />
        <button className="p-1.5 rounded hover:bg-[#eef4ff]" title="Încarcă document existent / semnat" onClick={() => ref.current.click()} data-testid={`opis-upload-${p.nr}`}><Upload size={15} style={{ color: "var(--blue)" }} /></button>
        {p.upload && <button className="p-1.5 rounded hover:bg-[#fff0f0]" title="Elimină documentul încărcat" onClick={() => put({ clear_upload: true })} data-testid={`opis-clear-${p.nr}`}><X size={15} style={{ color: "#b33333" }} /></button>}
      </td>
    </tr>
  );
}

export function DossierOpis({ id }) {
  const [d, setD] = useState(null);
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
    <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="dossier-opis">
      <AiPrecheck id={id} open={pre} onClose={() => setPre(false)} onFinalize={doLock} />
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div>
          <h3 className="font-bold">Opis dosar prosumator ({d.positions.length} poziții)</h3>
          <button onClick={() => setShowReport(!showReport)} className="text-xs font-bold inline-flex items-center gap-1 mt-1" style={{ color: d.complete ? "#166534" : "#9b2c2c" }} data-testid="opis-report-toggle">
            <AlertTriangle size={13} /> {d.complete ? "Dosar complet" : `${d.missing_total} informații / documente lipsă — vezi raportul`}
          </button>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Btn variant="secondary" onClick={lock} data-testid="opis-finalize">{d.finalized ? <><Unlock size={14} /> Redeschide</> : <><Lock size={14} /> Finalizează dosarul</>}</Btn>
          <Btn variant="secondary" onClick={() => downloadAuthenticatedFile(`/dossier/${id}/file/opis`, "Opis_declaratie_autenticitate.pdf")} data-testid="opis-declaration"><FileDown size={14} /> Opis (declarație autenticitate)</Btn>
          <Btn onClick={() => downloadAuthenticatedFile(`/dossier/${id}/export`, "Dosar_prosumator.pdf")} data-testid="opis-export"><FileDown size={15} /> Export dosar complet PDF{d.complete ? "" : " (CIORNĂ)"}</Btn>
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
      <div className="overflow-x-auto">
        <table className="w-full text-sm bg-white rounded-lg">
          <thead><tr className="text-left text-[11px]" style={{ color: "var(--muted)" }}><th className="px-2 py-2">Nr.</th><th className="px-2 py-2">Document</th><th className="px-2 py-2">Stadiu</th><th></th></tr></thead>
          <tbody>{d.positions.map((p) => <Row key={p.key} p={p} id={id} statuses={d.statuses} reload={load} />)}</tbody>
        </table>
      </div>
    </div>
  );
}
