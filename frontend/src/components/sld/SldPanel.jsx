import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { FileDown, Wand2, RefreshCw, ShieldCheck, Upload, X, Eye, Send } from "lucide-react";
import { api, API, fileUrl } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { uploadFile } from "@/components/dossier/ClientDocs";
import { SldChecks } from "./SldChecks";
import { SldCompare } from "./SldCompare";
import { SldEditor } from "./SldEditor";

const tok = () => localStorage.getItem("den_token");
const ST = { approved: ["Aprobată", "#e7f7ee", "#1e7a46"], stale: ["Aprobare anulată — configurație modificată", "#fff4e0", "#8a5a00"], draft: ["Ciornă — neaprobată", "#fff0f0", "#9b2c2c"] };

export function SldPanel({ id, form, setVal }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState(false);
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
  const requestApproval = () => run(async () => { await persist(); const r = await api.post(`/sld/${id}/request-approval`, { origin: window.location.origin }); await load(); toast.success(r.data.recipients.some((x) => x.sent) ? "Cerere de aprobare trimisă" : "Cerere înregistrată — e-mail netrimis (dosar TEST fără e-mail de test)"); });
  const sendSign = (role) => run(async () => { const r = await api.post(`/sld/${id}/send-sign`, { role, origin: window.location.origin, pos_keys: ["schema"] }); toast.success(r.data.every((x) => x.email_sent) ? "Link de semnare trimis pe e-mail" : "Cerere creată — e-mail netrimis (dosar TEST fără e-mail de test)"); });
  const source = (body) => run(async () => { await api.put(`/sld/${id}/source`, body); await load(); });

  if (!d) return null;
  const st = ST[d.approval.status];
  return (
    <div className="mt-6 rounded-xl border p-4 bg-white" style={{ borderColor: "var(--line)" }} data-testid="sld-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-bold">Schemă monofilară și dimensionare tehnică <span className="text-[10px] font-bold ml-1 rounded-full px-2 py-0.5" style={{ background: "#eef4ff", color: "var(--blue)" }}>generator nou — în verificare</span>{d.is_test && <span className="text-[10px] font-bold ml-1 rounded-full px-2 py-0.5" style={{ background: "#fff0f0", color: "#9b2c2c" }} data-testid="sld-test-badge">DOSAR DE TEST</span>}</h3>
          <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Simboluri SR EN 60617 · calcule HD 60364 / IEC 62548. Dimensionarea este o propunere verificabilă; devine document final doar după aprobarea proiectantului / verificatorului.</p>
        </div>
        <span className="text-xs font-bold rounded-full px-3 py-1" style={{ background: st[1], color: st[2] }} data-testid="sld-status">{st[0]}{d.approval.status === "approved" ? ` · ${Object.values(d.approval.approvals || {}).filter((a) => a.valid).map((a) => a.name).join(" + ")}` : ""}</span>
      </div>
      {d.from_legacy && <div className="mt-3 rounded-lg px-3 py-2 text-xs flex flex-wrap items-center gap-3" style={{ background: "#fff8e6", color: "#8a5a00" }} data-testid="sld-legacy-banner">
        <span className="flex-1 min-w-[240px]">Schema este desenată din datele fișei (invertor, panouri, baterie). Stringurile/MPPT nu sunt definite — preluați datele în Configuratorul CEF și completați stringurile pentru o schemă completă.</span>
        <Btn variant="secondary" onClick={() => run(async () => { await api.post(`/sld/${id}/import-legacy`); toast.success("Date preluate în configurator — reîncărcați dosarul pentru a edita stringurile"); await load(); })} disabled={busy} data-testid="sld-import-legacy">Preia în configuratorul CEF</Btn>
      </div>}
      <button type="button" className="mt-3 text-xs font-bold" style={{ color: "var(--blue)" }} onClick={() => setEdit(!edit)} data-testid="sld-edit-toggle">{edit ? "Închide editarea manuală" : "Editare manuală a schemei (tabel + previzualizare)"}</button>
      {edit && <SldEditor id={id} onSaved={(cef) => { if (cef) setVal?.("cef", cef); load(); }} />}
      <div className="flex flex-wrap gap-2 mt-4">
        <Btn variant="secondary" onClick={refresh} disabled={busy} data-testid="sld-refresh"><RefreshCw size={14} /> Salvează și verifică</Btn>
        <Btn variant="secondary" onClick={apply} disabled={busy} data-testid="sld-apply"><Wand2 size={14} /> Completează automat valorile calculate</Btn>
        <Btn onClick={() => open(`/sld/${id}/pdf`)} disabled={busy} data-testid="sld-preview"><Eye size={14} /> Previzualizare schemă generată ({d.format})</Btn>
        <Btn variant="secondary" onClick={() => open(`/sld/${id}/pdf?fmt=${d.format === "A3" ? "A4" : "A3"}`)} disabled={busy} data-testid="sld-preview-alt"><FileDown size={14} /> PDF {d.format === "A3" ? "A4" : "A3"}</Btn>
        <Btn variant="secondary" onClick={() => open(`/sld/${id}/report`)} disabled={busy} data-testid="sld-report"><FileDown size={14} /> Raport de calcul</Btn>
        <Btn variant="secondary" onClick={() => window.open(`${API}/sld/demo/pdf?auth=${tok()}`, "_blank")} data-testid="sld-demo"><Eye size={14} /> Schemă demonstrativă</Btn>
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
          {Object.entries(d.approval.approvals || {}).map(([r, a]) => (
            <p key={r} className="text-xs mb-1" style={{ color: a.valid ? "#1e7a46" : "#8a5a00" }} data-testid={`sld-approval-info-${r}`}>{a.role_label}: <b>{a.name}</b> {a.auth} · {String(a.at).slice(0, 16).replace("T", " ")} UTC · rev. {d.revision}{a.valid ? "" : " — anulată (configurație modificată)"}</p>
          ))}
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
          {d.approval.status !== "approved" && (
            <div className="mt-2 pt-2 border-t" style={{ borderColor: "var(--line)" }}>
              <Btn variant="secondary" disabled={busy || (d.source === "generated" && !d.ready)} onClick={requestApproval} data-testid="sld-request-approval"><Send size={13} /> Cere aprobare pe e-mail</Btn>
              <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Se trimite și automat, o singură dată pe versiune, la salvare, când datele sunt complete și fără erori.</p>
              {(d.approval_requests || []).slice().reverse().slice(0, 3).map((q, i) => (
                <p key={i} className="text-[11px]" data-testid={`sld-approval-request-${i}`}>{String(q.at).slice(0, 16).replace("T", " ")} UTC · {q.auto ? "automat" : "manual"} · {q.recipients.map((x) => `${x.name}: ${x.sent ? "trimis la " + x.to : "netrimis (TEST fără e-mail de test)"}`).join("; ") || "fără destinatari cu e-mail"}</p>
              ))}
            </div>
          )}
          {d.approval.status !== "draft" && <button className="text-xs mt-1 underline" style={{ color: "#b33333" }} onClick={unapprove} data-testid="sld-unapprove">Retrage aprobarea</button>}
          {d.approval.status === "approved" && (
            <div className="mt-3 pt-2 border-t" style={{ borderColor: "var(--line)" }}>
              <div className="text-[11px] font-bold mb-1">Semnare la distanță (link + cod pe e-mailul din Personal)</div>
              {["designer", "verifier"].map((r) => d.people[r] && (
                <Btn key={r} variant="secondary" className="mr-2 mb-1" disabled={busy || !d.people[r].eligible || !d.people[r].email} title={d.people[r].email ? "" : "Completați e-mailul în Setări de bază → Personal"} onClick={() => sendSign(r)} data-testid={`sld-send-sign-${r}`}>
                  <Send size={13} /> Trimite la {r === "designer" ? "proiectant" : "verificator"}{d.people[r].email ? "" : " (fără e-mail)"}
                </Btn>
              ))}
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>Starea semnării apare în secțiunea „Semnături” de mai jos; PDF-ul semnat intră automat în opis.</p>
            </div>
          )}
        </div>
      </div>
      {d.history?.length > 0 && (
        <div className="mt-4" data-testid="sld-history">
          <div className="text-[11px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--blue)" }}>Istoric versiuni aprobate</div>
          {d.history.map((h, i) => (
            <div key={i} className="text-xs flex flex-wrap gap-2 py-1 border-t" style={{ borderColor: "var(--line)" }} data-testid={`sld-history-${i}`}>
              <b>rev. {h.revision}</b><span>{String(h.at).slice(0, 16).replace("T", " ")} UTC</span><span>{h.role_label}: {h.name}</span>
              <span>{h.source === "uploaded" ? "schemă încărcată" : "schemă generată"}</span>
              <span className="font-bold" style={{ color: h.current ? "#1e7a46" : "var(--muted)" }}>{h.current ? "versiunea în vigoare" : "versiune anterioară"}</span>
              {h.file && <a className="underline" style={{ color: "var(--blue)" }} href={fileUrl(h.file.storage_path)} target="_blank" rel="noopener noreferrer" data-testid={`sld-history-file-${i}`}>PDF</a>}
            </div>
          ))}
          <SldCompare id={id} history={d.history} />
        </div>
      )}
    </div>
  );
}
