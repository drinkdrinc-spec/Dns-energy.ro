import { useEffect, useRef, useState } from "react";
import { api, downloadAuthenticatedFile, openAuthenticatedFile } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Eye, FileDown, FileType2, Upload, X, AlertTriangle, Lock, Unlock } from "lucide-react";
import { toast } from "sonner";
import { uploadFile } from "./ClientDocs";
import { AiPrecheck } from "@/components/ai/AiPrecheck";
import { useAuth } from "@/context/AuthContext";
import { can } from "@/lib/plan";

const STATUS_STYLE = { "de completat": ["#fff8e8", "#76500a"], generat: ["#eef4ff", "#1d4ed8"], "necesită semnătură": ["#fff8e6", "#8a5a00"], "atașat": ["#ecfdf3", "#166534"] };

function Row({ p, id, statuses, reload }) {
  const ref = useRef();
  const put = async (body) => { await api.put(`/dossier/${id}/item/${p.key}`, body); reload(); };
  const filePath = `/dossier/${id}/file/${encodeURIComponent(p.key)}`;
  const officialFormLabel = p.official_form_label || "formularul oficial DEER";
  const officialFormUrl = `/docs/${p.official_doc_endpoint || "anexa1"}/${encodeURIComponent(id)}`;
  const officialFormFilename = p.official_doc_endpoint === "anexa2" ? `DEER_Anexa2_${String(id).slice(0, 8)}.docx` : `Anexa_1_DEER_${String(id).slice(0, 8)}.docx`;
  const [bg, fg] = STATUS_STYLE[p.status] || STATUS_STYLE.generat;
  const dotColor = p.status === "atașat" ? "#1f8f4e" : p.status === "de completat" ? "#f08a24" : "#cfcfcf";
  const multiUpload = ["fotografii_instalatie", "fotografii_lucrare", "alt_document"].includes(p.key);
  const uploadedFiles = [...(p.uploads || []), ...(p.upload ? [p.upload] : [])];
  const canView = !p.docx_only && (p.source === "generat" || !!p.official_operator_form || uploadedFiles.length > 0 || p.files.length > 0);
  return (
    <tr className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-2 border rounded-lg p-2 mb-2 bg-white md:mb-0 md:table-row md:border-0 md:rounded-none md:p-0" style={{ borderColor: "var(--line)" }} data-testid={`opis-row-${p.nr}`}>
      <td className="hidden md:table-cell px-2 py-2.5 font-bold">{p.nr}</td>
      <td className="col-span-2 md:col-span-1 md:table-cell px-2 py-2.5">
        <div className="flex items-start gap-2 font-semibold"><span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: dotColor }} /><span><span className="md:hidden">{p.nr}. </span>{p.title}</span></div>
        <div className="text-[11px]" style={{ color: "var(--muted)" }}>{uploadedFiles.length ? `Încărcate: ${uploadedFiles.map((file) => file.original_filename).filter(Boolean).join(", ")}` : p.docx_only ? "Descarcă formularul Word, verifică datele și semnează-l. Încarcă apoi PDF-ul semnat aici ca să intre în dosarul complet." : p.source === "generat" ? "Generat din datele dosarului" : p.source === "client" ? "Din fișa clientului" : p.source === "manual" ? "Document oficial — atașează PDF-ul aplicabil" : "Din catalog echipamente"}</div>
        {p.key === "gdpr" && <a className="text-[11px] underline inline-block mt-1" style={{ color: "var(--blue)" }} href="https://www.distributie-energie.ro/wp-content/uploads/2026/10/Informare-generala-site-v2-2026.pdf" target="_blank" rel="noopener noreferrer">Deschide nota oficială DEER (PDF, versiunea octombrie 2026) ↗</a>}
        {p.missing.length > 0 && <div className="text-[11px] mt-1" style={{ color: "#76500a" }}>Lipsă: {p.missing.join(", ")}</div>}
      </td>
      <td className="min-w-0 md:table-cell px-2 py-2.5">
        <select className="den-input text-xs py-1 w-full md:w-auto min-w-[150px] md:min-w-[190px]" style={{ background: bg, color: fg, fontWeight: 700 }} value={p.status} data-testid={`opis-status-${p.nr}`}
          onChange={(e) => put({ status: e.target.value === p.auto_status ? null : e.target.value })}>
          {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </td>
      <td className="flex items-center justify-end whitespace-nowrap text-right md:table-cell px-2 py-2.5">
        {canView && <button className="p-1.5 rounded hover:bg-[#eef4ff]" title="Previzualizare" onClick={() => openAuthenticatedFile(filePath)} data-testid={`opis-preview-${p.nr}`}><Eye size={15} style={{ color: "var(--blue)" }} /></button>}
        {canView && <button type="button" className="p-1.5 inline-flex items-center gap-1 rounded hover:bg-[#eef4ff]" title={p.key === "schema" ? "Descarcă schema monofilară PDF" : p.key === "priza" ? "Descarcă buletinul PRAM PDF" : "Descarcă PDF"} aria-label={p.key === "schema" ? "Descarcă schema monofilară PDF" : p.key === "priza" ? "Descarcă buletinul PRAM PDF" : `Descarcă PDF ${p.title}`} onClick={() => downloadAuthenticatedFile(`${filePath}?download=1`, `document-${p.key}.pdf`)} data-testid={`opis-pdf-${p.nr}`}><FileDown size={15} style={{ color: "var(--blue)" }} />{p.key === "schema" ? <span className="text-[11px]">Schema PDF</span> : p.key === "priza" ? <span className="text-[11px]">PRAM PDF</span> : null}</button>}
        {p.source === "generat" && p.key !== "schema" && !p.docx_only && <button type="button" className="p-1.5 inline-block rounded hover:bg-[#eef4ff]" title="Descarcă Word" onClick={() => downloadAuthenticatedFile(`${filePath}?fmt=docx`, `document-${p.key}.docx`)} data-testid={`opis-docx-${p.nr}`}><FileType2 size={15} style={{ color: "var(--blue)" }} /></button>}
        {p.docx_only && <button type="button" className="p-1.5 inline-flex items-center gap-1 rounded hover:bg-[#eef4ff]" title={`Descarcă ${officialFormLabel} precompletat`} onClick={() => downloadAuthenticatedFile(officialFormUrl, officialFormFilename)} data-testid={`opis-deer-official-form-${p.nr}`}><FileType2 size={15} style={{ color: "var(--blue)" }} /><span className="text-[11px]">{officialFormLabel} Word</span></button>}
        <input ref={ref} type="file" accept="application/pdf,image/*" multiple={multiUpload} className="hidden" data-testid={`opis-upload-input-${p.nr}`}
          onChange={async (e) => { const files = Array.from(e.target.files || []); if (!files.length) return; try { if (multiUpload) await put({ add_uploads: await Promise.all(files.map(uploadFile)), status: null }); else await put({ upload: await uploadFile(files[0]), status: null }); toast.success(files.length > 1 ? `${files.length} fișiere atașate` : "Document atașat"); } catch (error) { toast.error(error?.response?.data?.detail || "Nu am putut atașa documentul"); } finally { ref.current.value = ""; } }} />
        <button className="p-1.5 rounded hover:bg-[#eef4ff]" title={multiUpload ? "Încarcă unul sau mai multe fișiere" : p.docx_only ? `Încarcă ${officialFormLabel} completat și semnat (PDF)` : "Încarcă document existent / semnat"} aria-label={multiUpload ? `Încarcă fișiere pentru ${p.title}` : p.docx_only ? `Încarcă ${officialFormLabel} completat și semnat (PDF)` : `Încarcă document ${p.title}`} onClick={() => ref.current.click()} data-testid={`opis-upload-${p.nr}`}><Upload size={15} style={{ color: "var(--blue)" }} />{p.docx_only && <span className="text-[11px]">PDF semnat</span>}</button>
        {p.uploads?.map((file, index) => <button key={file.storage_path || index} className="p-1.5 rounded hover:bg-[#fff0f0]" title={`Elimină ${file.original_filename || "fișierul"}`} onClick={() => put({ remove_upload_index: index })} data-testid={`opis-clear-${p.nr}-${index}`}><X size={15} style={{ color: "#b33333" }} /></button>)}
        {p.upload && <button className="p-1.5 rounded hover:bg-[#fff0f0]" title="Elimină documentul încărcat" onClick={() => put({ clear_upload: true })} data-testid={`opis-clear-${p.nr}`}><X size={15} style={{ color: "#b33333" }} /></button>}
      </td>
    </tr>
  );
}

export function DossierOpis({ id, mode = "all", onChecklist }) {
  const [d, setD] = useState(null);
  const [showReport, setShowReport] = useState(false);
  const [pre, setPre] = useState(false);
  const [exporting, setExporting] = useState(false);
  const exportLock = useRef(false);
  const { user } = useAuth();
  const load = () => api.get(`/dossier/${id}`).then((r) => {
    const data = r.data;
    setD(data);
    if (onChecklist && Array.isArray(data.positions)) {
      const byKey = new Map(data.positions.map((position) => [position.key, position]));
      const ready = (key) => {
        const position = byKey.get(key);
        return Boolean(position) && !(position.missing || []).length;
      };
      const requiredActKeys = ["factura", "certificat", "anre_firma", "metrologie_pram", "priza"];
      const commissioning = data.positions.filter((position) => ["pif", "pif_pv"].includes(position.key));
      onChecklist({
        installation: ready("schema"),
        acts: requiredActKeys.every((key) => !byKey.has(key) || ready(key)),
        documents: data.complete === true,
        commissioning: commissioning.some((position) => position.key === "pif") && commissioning.every((position) => !(position.missing || []).length),
      });
    }
  }).catch(() => {});
  useEffect(() => { load(); }, [id]); // eslint-disable-line
  if (!d) return null;
  const positions = mode === "attachments" ? d.positions.filter((p) => p.source !== "generat")
    : mode === "generated" ? d.positions.filter((p) => p.source === "generat") : d.positions;
  const fileCount = positions.reduce((count, p) => count + (p.upload ? 1 : 0) + (p.uploads || []).length + (p.files || []).length, 0);
  const doLock = async () => {
    try { await api.post(`/dossier/${id}/${d.finalized ? "reopen" : "finalize"}`); toast.success(d.finalized ? "Dosar redeschis" : "Dosar finalizat — datele din setări sunt înghețate"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Operațiunea a eșuat"); throw e; }
  };
  const lock = () => (!d.finalized && can(user, "ai_gpt") ? setPre(true) : doLock().catch(() => {}));
  return (
    <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid={mode === "attachments" ? "dossier-acts-photos" : "dossier-opis"}>
      {mode !== "attachments" && <AiPrecheck id={id} open={pre} onClose={() => setPre(false)} onFinalize={doLock} />}
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div>
          <h3 className="font-bold">{mode === "attachments" ? "Acte și poze" : mode === "generated" ? `Documente generate (${positions.length})` : `Opis dosar prosumator (${d.positions.length} poziții)`}</h3>
          {mode === "attachments" ? <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{fileCount} fișiere atașate · încarcă aici actele clientului și fotografiile instalației</p>
            : <button onClick={() => setShowReport(!showReport)} className="text-xs font-bold inline-flex items-center gap-1 mt-1" style={{ color: d.complete ? "#166534" : "#8a5a00" }} data-testid="opis-report-toggle">
              <AlertTriangle size={13} /> {d.complete ? "Dosar complet" : `${d.missing_total} informații / documente lipsă — vezi raportul`}
            </button>}
        </div>
        {mode !== "attachments" && <div className="flex gap-2 flex-wrap">
          <Btn variant="secondary" onClick={lock} data-testid="opis-finalize">{d.finalized ? <><Unlock size={14} /> Redeschide</> : <><Lock size={14} /> Finalizează dosarul</>}</Btn>
          <Btn variant="secondary" onClick={() => downloadAuthenticatedFile(`/dossier/${id}/file/opis?download=1`, "Opis_declaratie_autenticitate.pdf")} data-testid="opis-declaration"><FileDown size={14} /> Opis (declarație autenticitate)</Btn>
          <Btn disabled={exporting} aria-busy={exporting} onClick={async () => {
            if (exportLock.current) return;
            exportLock.current = true;
            setExporting(true);
            try { await downloadAuthenticatedFile(`/dossier/${id}/export`, "Dosar_prosumator.pdf"); }
            finally { exportLock.current = false; setExporting(false); }
          }} data-testid="opis-export"><FileDown size={15} /> {exporting ? "Se pregătește PDF-ul… păstrează pagina deschisă" : `Export dosar complet PDF${d.complete ? "" : " (CIORNĂ)"}`}</Btn>
        </div>}
      </div>
      {mode !== "attachments" && d.finalized && <p className="text-xs mb-2" style={{ color: "#166534" }} data-testid="opis-finalized">Finalizat la {new Date(d.finalized).toLocaleString("ro-RO")} — modificările din setări nu mai afectează acest dosar.</p>}
      {mode !== "attachments" && d.signer_warnings?.map((w) => <p key={w} className="text-xs mb-1" style={{ color: "#9b2c2c" }} data-testid="signer-warning">⚠ {w}</p>)}
      {mode !== "attachments" && <p className="text-[11px] mb-2" style={{ color: "var(--muted)" }}>Modificările din formular (semnatari, teste, reglaje, date) se reflectă în opis și documente după „Salvează”.</p>}
      {mode !== "attachments" && showReport && (
        <div className="rounded-lg bg-white border p-3 mb-3 text-xs" style={{ borderColor: "var(--line)" }} data-testid="opis-report">
          {d.common_missing?.length > 0 && <div className="mb-2"><b>Date comune (client / executant), folosite în toate documentele generate:</b> {d.common_missing.join(", ")}</div>}
          {d.positions.filter((p) => p.missing.length).map((p) => <div key={p.key} className="mb-1"><b>{p.nr}. {p.title}:</b> {p.missing.join(", ")}</div>)}
          {d.complete && "Nu lipsește nimic."}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm bg-white rounded-lg">
          <thead className="hidden md:table-header-group"><tr className="text-left text-[11px]" style={{ color: "var(--muted)" }}><th className="px-2 py-2">Nr.</th><th className="px-2 py-2">Document</th><th className="px-2 py-2">Stadiu</th><th></th></tr></thead>
          <tbody className="block md:table-row-group">{positions.map((p) => <Row key={p.key} p={p} id={id} statuses={d.statuses} reload={load} />)}</tbody>
        </table>
      </div>
    </div>
  );
}
