import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Upload, FileDown, Send } from "lucide-react";
import { api, API } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { streamAI, clean } from "@/lib/ai";

const tok = () => localStorage.getItem("den_token");
const CO = [["name", "Denumire"], ["cui", "CUI"], ["regcom", "Nr. Reg. Comerțului"], ["address", "Sediu social"], ["rep_name", "Reprezentant legal"], ["rep_role", "Funcție"],
  ["email", "E-mail"], ["phone", "Telefon"], ["attest_no", "Nr. atestat existent"], ["attest_types", "Tipuri atestat existent"], ["attest_valid", "Valabil până la"]];
const STAFF = [["name", "Nume"], ["role", "Funcție"], ["grade", "Grad/tip autorizare"], ["license", "Nr. legitimație"], ["license_valid", "Valabilă până la"], ["contract", "Contract"]];
const EQ = [["name", "Dotare"], ["serial", "Serie/buc."], ["ownership", "Proprietate/folosință"], ["calibration", "Verificare metrologică"]];

function Rows({ cols, rows, onChange, tid }) {
  return (
    <div className="overflow-x-auto"><table className="text-xs" data-testid={tid}><tbody>
      {rows.map((r, i) => <tr key={i}>{cols.map(([k, l]) => <td key={k} className="pr-1 pb-1"><input className="den-input !py-1 !text-xs" placeholder={l} value={r[k] ?? ""} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)))} data-testid={`${tid}-${i}-${k}`} /></td>)}
        <td><button onClick={() => onChange(rows.filter((_, j) => j !== i))}>×</button></td></tr>)}</tbody></table>
      <button className="text-xs font-bold" style={{ color: "var(--blue)" }} onClick={() => onChange([...rows, {}])} data-testid={`${tid}-add`}>+ rând</button></div>
  );
}

function Assistant({ id }) {
  const [msgs, setMsgs] = useState([]);
  const [t, setT] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get(`/anre/dossiers/${id}/ai`).then((r) => setMsgs(r.data)); }, [id]);
  const send = async () => {
    const q = t.trim(); if (!q) return; setT(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "..." }]);
    try { await streamAI(`/anre/dossiers/${id}/ai`, { text: q }, (full) => setMsgs((m) => [...m.slice(0, -1), { role: "assistant", content: full }])); }
    catch (e) { toast.error(e.message); setMsgs((m) => m.slice(0, -1)); } finally { setBusy(false); }
  };
  return (
    <div className="den-panel" data-testid="anre-ai">
      <h3 className="font-bold mb-2">Asistent AI pentru dosar</h3>
      <div className="space-y-2 max-h-72 overflow-y-auto text-sm">{msgs.map((m, i) => <div key={i} className={`rounded-lg px-3 py-2 whitespace-pre-wrap ${m.role === "user" ? "bg-[#eef4ff]" : "bg-white border"}`} data-testid={`anre-ai-msg-${m.role}`}>{clean(m.content)}</div>)}
        {!msgs.length && <p className="text-xs" style={{ color: "var(--muted)" }}>Întreabă: „Ce documente mai lipsesc și de unde le obțin?”</p>}</div>
      <div className="flex gap-2 mt-2"><input className="den-input flex-1" value={t} onChange={(e) => setT(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} placeholder="Întrebare despre dosar..." data-testid="anre-ai-input" />
        <Btn onClick={send} disabled={busy} data-testid="anre-ai-send"><Send size={14} /></Btn></div>
    </div>
  );
}

export function AnreEditor({ id, platform, onBack }) {
  const [d, setD] = useState(null);
  const [rep, setRep] = useState(null);
  const [filing, setFiling] = useState({});
  const load = () => api.get(`/anre/dossiers/${id}`).then((r) => setD(r.data));
  useEffect(() => { load(); }, [id]); // eslint-disable-line
  if (!d) return null;
  const paid = d.payment_status === "plătit" || d.creation_mode === "intern" || platform;
  const save = async (extra = {}) => { try { const { data } = await api.put(`/anre/dossiers/${id}`, { company: d.company, staff: d.staff, equipment: d.equipment, target_types: d.target_types, ...extra }); setD(data); toast.success("Salvat"); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  const up = async (key, file) => { const fd = new FormData(); fd.append("file", file); fd.append("issued", key === "cert_constatator" ? (window.prompt("Data emiterii certificatului (AAAA-LL-ZZ):") || "") : "");
    try { const { data } = await api.post(`/anre/dossiers/${id}/docs/${key}`, fd, { headers: { "Content-Type": "multipart/form-data" } }); setD(data); toast.success("Document încărcat"); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  const review = async (key, body) => { try { const { data } = await api.post(`/anre/dossiers/${id}/docs/${key}/review`, body); setD(data); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  const runCheck = async () => { try { const { data } = await api.post(`/anre/dossiers/${id}/check`); setRep(data); load(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  const url = (k) => `${API}/anre/dossiers/${id}/file/${k}?auth=${tok()}`;
  return (
    <div className="space-y-4" data-testid="anre-editor">
      <div className="flex flex-wrap items-center gap-2">
        <button className="text-sm font-bold" onClick={onBack} data-testid="anre-back">← Dosare ANRE</button>
        <h2 className="text-xl font-extrabold">{d.types[d.kind]}</h2><span className="text-xs rounded-full px-2 py-0.5 bg-slate-100" data-testid="anre-progress">{d.progress}% verificat</span>
        <select className="den-input !py-1 !text-sm ml-auto" style={{ width: 210 }} value={d.status} disabled={!paid} onChange={(e) => save({ status: e.target.value, ...filing })} data-testid="anre-status">{d.statuses.map((s) => <option key={s}>{s}</option>)}</select>
      </div>
      {d.creation_mode === "intern" && <div className="den-panel text-sm" style={{ background: "#eef4ff" }} data-testid="anre-internal-draft">Dosar intern — poți completa și verifica documentele fără să emiți o comandă sau o proformă.</div>}
      {!paid && <div className="den-panel text-sm" style={{ background: "#fff8e6" }} data-testid="anre-unpaid">Serviciul costă <b>{d.price.net} lei + TVA ({d.price.total} lei)</b>. Plătiți prin OP cu mențiunea „{d.invoice_number || `Dosar ANRE ${d.id.slice(0, 8)}`}”; dosarul se deblochează după confirmarea plății de către administrator. {d.price.note}.
        {d.transfer && <div className="mt-2 text-xs grid sm:grid-cols-3 gap-1" data-testid="anre-transfer"><span>Beneficiar: <b>{d.transfer.beneficiary}</b></span><span>CUI: {d.transfer.cui || "—"}</span><span>IBAN: <b>{d.transfer.iban || "—"}</b></span><span>Banca: {d.transfer.bank || "—"}</span><span>Suma: <b>{d.transfer.amount} lei</b></span><span>Mențiune OP: <b>{d.transfer.reference}</b></span></div>}</div>}
      {d.invoice_id && <a href={`${API}/billing/invoices/${d.invoice_id}/pdf?auth=${tok()}`} target="_blank" rel="noopener noreferrer" className="text-sm font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} data-testid="anre-proforma-pdf"><FileDown size={14} /> Proforma {d.invoice_number} (PDF)</a>}
      {platform && d.payment_status !== "plătit" && <Btn onClick={async () => { const ref = window.prompt("Referința OP / extras:"); if (ref) { await api.post(`/admin/anre/${id}/payment`, { reference: ref }); load(); } }} data-testid="anre-confirm-payment">Confirmă plata (admin)</Btn>}
      {paid && <>
        <div className="den-panel"><h3 className="font-bold mb-2">Date firmă (preluate din profil)</h3>
          <div className="grid sm:grid-cols-4 gap-2">{CO.map(([k, l]) => <div key={k} className="den-field"><label>{l}</label><input className="den-input" value={d.company?.[k] ?? ""} onChange={(e) => setD({ ...d, company: { ...d.company, [k]: e.target.value } })} data-testid={`anre-co-${k}`} /></div>)}
            <div className="den-field sm:col-span-4"><label>Tip(uri) atestat solicitat</label><div className="flex flex-wrap gap-2">
              {["A1", "A2", "A3", "B", "Bi", "Bp", "C1A", "C1B", "C2A", "C2B", "D1", "D2", "E1", "E2"].map((t) => { const tt = d.target_types || []; return (
                <label key={t} className="text-xs flex items-center gap-1 rounded border px-2 py-1" style={{ borderColor: "var(--line)" }}>
                  <input type="checkbox" checked={tt.includes(t)} onChange={(e) => setD({ ...d, target_types: e.target.checked ? [...tt, t] : tt.filter((x) => x !== t) })} data-testid={`anre-target-${t}`} />{t}</label>); })}</div></div></div>
          <h3 className="font-bold mt-3 mb-1 text-sm">Personal (Anexa 7)</h3><Rows cols={STAFF} rows={d.staff || []} onChange={(v) => setD({ ...d, staff: v })} tid="anre-staff" />
          <h3 className="font-bold mt-3 mb-1 text-sm">Dotări (Anexa 5)</h3><Rows cols={EQ} rows={d.equipment || []} onChange={(v) => setD({ ...d, equipment: v })} tid="anre-eq" />
          <Btn className="mt-3" onClick={() => save()} data-testid="anre-save">Salvează datele</Btn></div>
        <div className="den-panel overflow-x-auto"><div className="flex items-center justify-between mb-2"><h3 className="font-bold">Opis</h3><a href={url("opis")} target="_blank" rel="noopener noreferrer" className="text-xs font-bold" style={{ color: "var(--blue)" }} data-testid="anre-opis-pdf">Opis PDF</a></div>
          <table className="w-full text-xs" data-testid="anre-opis"><thead><tr className="text-left" style={{ color: "var(--muted)" }}><th>Nr.</th><th>Document</th><th>Temei</th><th>Sursă</th><th>Status</th><th>Acțiuni</th></tr></thead>
            <tbody>{d.items.map((i) => (
              <tr key={i.key} className="border-t align-top" style={{ borderColor: "var(--line)" }} data-testid={`anre-item-${i.key}`}>
                <td className="py-1.5">{i.nr}</td><td>{i.title}{i.notes && <div style={{ color: "#8a5a00" }}>{i.notes}</div>}</td><td>{i.basis}</td><td>{i.source_label}</td>
                <td className="font-bold" data-testid={`anre-item-status-${i.key}`}>{i.status}</td>
                <td className="space-x-2 whitespace-nowrap">
                  {i.source === "client" ? <label className="cursor-pointer font-bold" style={{ color: "var(--blue)" }}><Upload size={12} className="inline" /> Încarcă<input type="file" className="hidden" accept="application/pdf,image/jpeg,image/png" onChange={(e) => e.target.files[0] && up(i.key, e.target.files[0])} data-testid={`anre-upload-${i.key}`} /></label>
                    : <button className="font-bold" style={{ color: "#166534" }} onClick={() => review(i.key, { approved: i.status !== "verificat" })} data-testid={`anre-approve-${i.key}`}>{i.status === "verificat" ? "Anulează aprobarea" : "Am verificat"}</button>}
                  {(i.source !== "client" || i.file) && <a href={url(i.key)} target="_blank" rel="noopener noreferrer" data-testid={`anre-view-${i.key}`}><FileDown size={12} className="inline" /></a>}
                  {i.source === "client" && i.file && <select className="den-input !py-0 !text-[11px] !w-36 inline" value={i.status} onChange={(e) => review(i.key, { status: e.target.value })} data-testid={`anre-review-${i.key}`}>{d.doc_statuses.map((s) => <option key={s}>{s}</option>)}</select>}
                </td></tr>))}</tbody></table></div>
        <div className="den-panel"><div className="flex flex-wrap gap-2 items-end">
          <Btn onClick={runCheck} data-testid="anre-check">Verificare finală</Btn>
          <a href={url("raport")} target="_blank" rel="noopener noreferrer" data-testid="anre-report-pdf"><Btn variant="secondary">Raport PDF</Btn></a>
          <Btn variant="secondary" onClick={async () => { try { const r = await fetch(`${API}/anre/dossiers/${id}/package?auth=${tok()}`); if (!r.ok) throw new Error((await r.json()).detail); const b = await r.blob(); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `Dosar_ANRE_${d.company?.cui || id.slice(0, 6)}.zip`; a.click(); } catch (e) { toast.error(e.message); } }} data-testid="anre-package">Pachet final (ZIP)</Btn>
          <input className="den-input !w-40" placeholder="Nr. înregistrare ANRE" onChange={(e) => setFiling({ ...filing, filing_no: e.target.value })} data-testid="anre-filing-no" />
          <input className="den-input !w-40" type="date" onChange={(e) => setFiling({ ...filing, filing_date: e.target.value })} data-testid="anre-filing-date" />
          <input className="den-input !w-52" placeholder="Rezultat ANRE (pentru „Soluționat”)" onChange={(e) => setFiling({ ...filing, result: e.target.value })} data-testid="anre-result" />
          <label className="text-xs font-bold cursor-pointer" style={{ color: "var(--blue)" }}><Upload size={12} className="inline" /> {d.docs?.decizie ? `Decizie: ${d.docs.decizie.name}` : "Încarcă decizia / atestatul ANRE"}
            <input type="file" className="hidden" accept="application/pdf,image/jpeg,image/png" onChange={(e) => e.target.files[0] && up("decizie", e.target.files[0])} data-testid="anre-upload-decizie" /></label></div>
          {rep && <div className="mt-3 text-xs space-y-1" data-testid="anre-report">{[["Lipsă", "missing"], ["De verificat / expirate", "review"], ["Formulare incomplete", "incomplete"], ["Neconcordanțe", "issues"]].map(([l, k]) => rep[k].length > 0 && <div key={k}><b>{l}:</b> {rep[k].join("; ")}</div>)}
            {rep.ok && <b style={{ color: "#166534" }}>Fără blocaje — pachetul final poate fi generat.</b>}</div>}</div>
        <Assistant id={id} />
      </>}
    </div>
  );
}
