import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { FileDown, Wand2, RefreshCw, ShieldCheck, Upload, X, Eye } from "lucide-react";
import { api, API, fileUrl } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { uploadFile } from "@/components/dossier/ClientDocs";
import { SldChecks } from "./SldChecks";

const tok = () => localStorage.getItem("den_token");
const ST = { approved: ["Aprobată", "#e7f7ee", "#1e7a46"], stale: ["Aprobare anulată — configurație modificată", "#fff4e0", "#8a5a00"], draft: ["Ciornă — neaprobată", "#fff0f0", "#9b2c2c"] };

export function SldPanel({ id, form, setVal }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const ref = useRef();
  const persist = () => api.put(`/data/prosumator/${id}`, form);
  const load = () => api.get(`/sld/${id}`).then((r) => setD(r.data)).catch(() => {});
  useEffect(() => { load(); }, [id]); // eslint-disable-line
  const run = async (fn) => { setBusy(true); try { await fn(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } setBusy(false); };
  const refresh = () => run(async () => { await persist(); await load(); toast.success("Date salvate și verificate"); });
  const apply = () => run(async () => {
    const r = await api.post(`/sld/${id}/apply`, { cef: form.cef });
    setVal("cef", r.data.cef); await load();
    toast.success(r.data.filled.length ? `${r.data.filled.length} câmpuri completate cu valori calculate — de confirmat` : "Nu există câmpuri goale de completat");
  });
  const open = (path) => run(async () => { await persist(); window.open(`${API}${path}${path.includes("?") ? "&" : "?"}auth=${tok()}`, "_blank"); await load(); });
  const approve = (role) => run(async () => { await persist(); await api.post(`/sld/${id}/approve`, { role }); await load(); toast.success("Schema a fost aprobată"); });
  const unapprove = () => run(async () => { await api.post(`/sld/${id}/unapprove`); await load(); });
  const source = (body) => run(async () => { await api.put(`/sld/${id}/source`, body); await load(); });

  if (!d) return null;
  const st = ST[d.approval.status];
  return (
    <div className="mt-6 rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="sld-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-bold">Schemă monofilară și dimensionare tehnică <span className="text-[10px] font-bold ml-1 rounded-full px-2 py-0.5" style={{ background: "#eef4ff", color: "var(--blue)" }}>generator nou — în verificare</span></h3>
          <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Simboluri SR EN 60617 · calcule HD 60364 / IEC 62548. Dimensionarea este o propunere verificabilă; devine document final doar după aprobarea proiectantului / verificatorului.</p>
        </div>
        <span className="text-xs font-bold rounded-full px-3 py-1" style={{ background: st[1], color: st[2] }} data-testid="sld-status">{st[0]}{d.approval.status === "approved" ? ` · ${d.approval.name}` : ""}</span>
      </div>
      <div className="flex flex-wrap gap-2 mt-4">
        <Btn variant="secondary" onClick={refresh} disabled={busy} data-testid="sld-refresh"><RefreshCw size={14} /> Salvează și verifică</Btn>
        <Btn variant="secondary" onClick={apply} disabled={busy} data-testid="sld-apply"><Wand2 size={14} /> Completează automat valorile calculate</Btn>
        <Btn onClick={() => open(`/sld/${id}/pdf`)} disabled={busy} data-testid="sld-preview"><Eye size={14} /> Previzualizare schemă ({d.format})</Btn>
        <Btn variant="secondary" onClick={() => open(`/sld/${id}/pdf?fmt=${d.format === "A3" ? "A4" : "A3"}`)} disabled={busy} data-testid="sld-preview-alt"><FileDown size={14} /> PDF {d.format === "A3" ? "A4" : "A3"}</Btn>
        <Btn variant="secondary" onClick={() => open(`/sld/${id}/report`)} disabled={busy} data-testid="sld-report"><FileDown size={14} /> Raport de calcul</Btn>
        <a href={`${API}/sld/demo/pdf?auth=${tok()}`} target="_blank" rel="noopener noreferrer" data-testid="sld-demo"><Btn variant="secondary"><Eye size={14} /> Schemă demonstrativă</Btn></a>
      </div>
      <SldChecks d={d} />
      <div className="grid sm:grid-cols-2 gap-4 mt-4">
        <div className="rounded-lg border p-3" style={{ borderColor: "var(--line)" }} data-testid="sld-source-box">
          <div className="text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--blue)" }}>Schema folosită în dosar</div>
          {[["generated", "Schema generată de aplicație"], ["uploaded", "Schema încărcată (realizată de specialist)"]].map(([k, l]) => (
            <label key={k} className="flex items-center gap-2 text-sm mb-1"><input type="radio" name="sld-src" checked={d.source === k} onChange={() => source({ source: k })} data-testid={`sld-source-${k}`} /> {l}</label>
          ))}
          <div className="flex flex-wrap items-center gap-2 mt-2 text-xs">
            <input ref={ref} type="file" accept="application/pdf" className="hidden" data-testid="sld-upload-input" onChange={async (e) => { const f = e.target.files?.[0]; if (!f) return; const up = await uploadFile(f); await source({ upload: up }); ref.current.value = ""; toast.success("Schemă încărcată"); }} />
            {d.upload ? <a href={fileUrl(d.upload.storage_path)} target="_blank" rel="noopener noreferrer" className="underline" style={{ color: "var(--blue)" }} data-testid="sld-upload-link">{d.upload.original_filename}</a> : <span style={{ color: "var(--muted)" }}>Nicio schemă încărcată</span>}
            <button onClick={() => ref.current.click()} className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} data-testid="sld-upload-btn"><Upload size={12} /> {d.upload ? "Înlocuiește" : "Încarcă PDF"}</button>
            {d.upload && <button onClick={() => source({ clear_upload: true })} data-testid="sld-upload-clear"><X size={13} style={{ color: "#b33333" }} /></button>}
          </div>
        </div>
        <div className="rounded-lg border p-3" style={{ borderColor: "var(--line)" }} data-testid="sld-approval-box">
          <div className="text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--blue)" }}>Verificare și aprobare tehnică</div>
          {d.approval.status !== "draft" && <p className="text-xs mb-2" data-testid="sld-approval-info">{d.approval.role_label}: <b>{d.approval.name}</b> {d.approval.auth} · {String(d.approval.at).slice(0, 16).replace("T", " ")} UTC · rev. {d.revision}</p>}
          {["designer", "verifier"].map((r) => {
            const p = d.people[r];
            return (
              <div key={r} className="flex items-center justify-between gap-2 text-xs mb-1.5">
                <span>{r === "designer" ? "Proiectant" : "Verificator"}: {p ? <b>{p.name}</b> : <i style={{ color: "#9b2c2c" }}>neselectat în Semnatari</i>}{p && !p.eligible && <span style={{ color: "#9b2c2c" }}> (autorizație nevalidată)</span>}</span>
                <Btn variant="secondary" disabled={busy || !p?.eligible || (d.source === "generated" && !d.ready)} onClick={() => approve(r)} data-testid={`sld-approve-${r}`}><ShieldCheck size={13} /> Aprobă</Btn>
              </div>
            );
          })}
          {d.source === "generated" && !d.ready && <p className="text-[11px] mt-1" style={{ color: "#9b2c2c" }}>Aprobarea este blocată până la completarea datelor lipsă și rezolvarea erorilor.</p>}
          {d.approval.status !== "draft" && <button className="text-xs mt-1 underline" style={{ color: "#b33333" }} onClick={unapprove} data-testid="sld-unapprove">Retrage aprobarea</button>}
        </div>
      </div>
    </div>
  );
}
