import { useEffect, useRef, useState } from "react";
import { api, fileUrl } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { uploadFile } from "@/components/dossier/ClientDocs";
import { Plus, Trash2, Upload, FileText } from "lucide-react";
import { toast } from "sonner";

const today = () => new Date().toISOString().slice(0, 10);
const soon = () => new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10);
export const docStatus = (exp, file) => (!file ? "lipsă" : !exp ? "valabil" : exp < today() ? "expirat" : exp <= soon() ? "aproape de expirare" : "valabil");
const BADGE = { valabil: ["#ecfdf3", "#166534"], "aproape de expirare": ["#fff8e6", "#8a5a00"], expirat: ["#fff0f0", "#9b2c2c"], "lipsă": ["#f1f5f9", "#475569"] };
const Badge = ({ s, testid }) => <span className="text-[11px] font-bold rounded-full px-2 py-0.5" style={{ background: BADGE[s][0], color: BADGE[s][1] }} data-testid={testid}>{s}</span>;

function In({ label, value, onChange, type = "text", testid, full }) {
  return <div className={`den-field ${full ? "sm:col-span-2" : ""}`}><label>{label}</label><input className="den-input" type={type} value={value || ""} onChange={(e) => onChange(e.target.value)} data-testid={testid} /></div>;
}

function FileSlot({ label, file, onFile, testid }) {
  const ref = useRef();
  return (
    <div className="flex items-center gap-2 text-xs flex-wrap" data-testid={testid}>
      <input ref={ref} type="file" accept="application/pdf,image/*" className="hidden" onChange={async (e) => { const f = e.target.files?.[0]; if (f) { onFile(await uploadFile(f)); ref.current.value = ""; } }} data-testid={`${testid}-input`} />
      <span className="font-semibold">{label}:</span>
      {file ? <a href={fileUrl(file.storage_path)} target="_blank" rel="noopener noreferrer" className="underline inline-flex items-center gap-1" style={{ color: "var(--blue)" }}><FileText size={12} />{file.original_filename}</a> : <span style={{ color: "var(--muted)" }}>neîncărcat</span>}
      <button onClick={() => ref.current.click()} className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} data-testid={`${testid}-btn`}><Upload size={12} />{file ? "Înlocuiește" : "Încarcă"}</button>
    </div>
  );
}

const CO = [["company", "Denumire firmă"], ["cui", "CUI"], ["regcom", "Nr. Registrul Comerțului"], ["phone", "Telefon"], ["email", "E-mail"], ["address", "Adresă sediu", true],
  ["anre_attest", "Atestat ANRE — număr"], ["anre_category", "Atestat ANRE — tip/categorie"], ["anre_issuer", "Emitent"], ["anre_issued", "Data emiterii", false, "date"],
  ["anre_valid", "Valabil până la", false, "date"], ["warranty_months", "Garanție lucrări (luni)"], ["kit_bmp", "Text standard kit BMP (PV recepție)", true], ["kit_structure", "Text standard kit structură (PV recepție)", true],
  ["test_email", "E-mail pentru teste (primește toate e-mailurile dosarelor TEST; gol = nu se trimit)"]];

function Company() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/settings").then((r) => setS(r.data)); }, []);
  if (!s) return null;
  const set = (k, v) => setS({ ...s, [k]: v });
  const save = async (next = s) => { await api.put("/settings", next); setS(next); toast.success("Profil firmă salvat"); };
  const setFile = (k) => (f) => save({ ...s, [k]: f });
  return (
    <div className="den-panel" data-testid="company-tab">
      <div className="grid sm:grid-cols-2 gap-3">{CO.map(([k, l, full, t]) => <In key={k} label={l} type={t} full={full} value={s[k]} onChange={(v) => set(k, v)} testid={`co-${k}`} />)}</div>
      <div className="mt-2 text-xs">Stare atestat ANRE: <Badge s={docStatus(s.anre_valid, s.anre_file)} testid="co-anre-status" /></div>
      <div className="mt-4 space-y-2">
        <FileSlot label="Antet firmă (imagine)" file={s.header_logo} onFile={setFile("header_logo")} testid="co-header" />
        <FileSlot label="Armătură / element grafic" file={s.armatura} onFile={setFile("armatura")} testid="co-armatura" />
        <FileSlot label="Ștampila firmei (imagine)" file={s.stamp} onFile={setFile("stamp")} testid="co-stamp" />
        <FileSlot label="Atestat ANRE (PDF)" file={s.anre_file} onFile={setFile("anre_file")} testid="co-anre-file" />
        <FileSlot label="Alt document / autorizație" file={null} onFile={(f) => save({ ...s, other_docs: [...(s.other_docs || []), f] })} testid="co-other" />
        {(s.other_docs || []).map((f, i) => <div key={f.storage_path} className="text-xs ml-4 flex gap-2"><a className="underline" style={{ color: "var(--blue)" }} href={fileUrl(f.storage_path)} target="_blank" rel="noopener noreferrer">{f.original_filename}</a>
          <button onClick={() => save({ ...s, other_docs: s.other_docs.filter((_, j) => j !== i) })}><Trash2 size={12} style={{ color: "#b33333" }} /></button></div>)}
      </div>
      <p className="text-[11px] mt-3" style={{ color: "var(--muted)" }}>Ștampila și semnăturile NU se aplică automat în documente; documentele generate au spații pentru semnătura olografă sau pentru semnare la distanță.</p>
      <div className="mt-4"><Btn onClick={() => save()} data-testid="co-save">Salvează profilul firmei</Btn></div>
    </div>
  );
}

function ListTab({ module, empty, render, title, testid }) {
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const load = () => api.get(`/data/${module}`).then((r) => setItems(r.data));
  useEffect(() => { load(); }, []); // eslint-disable-line
  const save = async (it) => { const { id, _k, ...rest } = it; if (id) await api.put(`/data/${module}/${id}`, rest); else { await api.post(`/data/${module}`, rest); setDrafts((d) => d.filter((x) => x._k !== _k)); } toast.success("Salvat"); load(); };
  const del = async (id) => { if (window.confirm("Ștergi înregistrarea?")) { await api.delete(`/data/${module}/${id}`); load(); } };
  return (
    <div className="space-y-4" data-testid={testid}>
      <Btn onClick={() => setDrafts([{ ...empty, _k: Date.now() }, ...drafts])} data-testid={`${testid}-add`}><Plus size={15} /> {title}</Btn>
      {[...drafts, ...items].map((it, i) => <Card key={it.id || it._k} it={it} render={render} save={save} del={del} idx={i} testid={testid} />)}
    </div>
  );
}

function Card({ it, render, save, del, idx, testid }) {
  const [f, setF] = useState(it);
  return (
    <div className="den-panel" data-testid={`${testid}-card-${idx}`}>
      {render(f, setF)}
      <div className="flex gap-2 mt-4"><Btn onClick={() => save(f)} data-testid={`${testid}-save-${idx}`}>Salvează</Btn>
        {f.id && <Btn variant="secondary" onClick={() => del(f.id)} data-testid={`${testid}-delete-${idx}`}>Șterge</Btn>}
        {f.created_by && <span className="text-[11px] self-center" style={{ color: "var(--muted)" }}>Adăugat de {f.created_by} · actualizat {new Date(f.updated_at).toLocaleString("ro-RO")}</span>}</div>
    </div>
  );
}

const instRender = (f, setF) => {
  const s = (k) => (v) => setF({ ...f, [k]: v });
  return <>
    <div className="flex justify-between mb-2"><b className="text-sm">{f.maker_model || "Aparat nou"}</b><Badge s={docStatus(f.expires, f.file)} testid="inst-status" /></div>
    <div className="grid sm:grid-cols-3 gap-3">
      <In label="Producător și model" value={f.maker_model} onChange={s("maker_model")} testid="inst-model" />
      <In label="Serie aparat" value={f.serial} onChange={s("serial")} testid="inst-serial" />
      <In label="Denumirea exactă a documentului (ex. Certificat de etalonare / Buletin de verificare metrologică)" value={f.cert_name} onChange={s("cert_name")} testid="inst-cert-name" />
      <In label="Număr document" value={f.cert_no} onChange={s("cert_no")} testid="inst-cert-no" />
      <In label="Data emiterii" type="date" value={f.issued} onChange={s("issued")} testid="inst-issued" />
      <In label="Expirare / următoarea verificare" type="date" value={f.expires} onChange={s("expires")} testid="inst-expires" />
    </div>
    <div className="mt-3"><FileSlot label="Document scanat (PDF)" file={f.file} onFile={s("file")} testid="inst-file" /></div>
  </>;
};

const staffRender = (f, setF) => {
  const s = (k) => (v) => setF({ ...f, [k]: v });
  const auths = f.auths || [];
  const sa = (i, k, v) => setF({ ...f, auths: auths.map((a, j) => (j === i ? { ...a, [k]: v } : a)) });
  return <>
    <div className="grid sm:grid-cols-2 gap-3">
      <In label="Nume și prenume" value={f.name} onChange={s("name")} testid="staff-name" />
      <In label="Funcție / calificare" value={f.qualification} onChange={s("qualification")} testid="staff-qual" />
      <In label="E-mail (pentru semnare la distanță)" value={f.email} onChange={s("email")} testid="staff-email" />
      <In label="Telefon" value={f.phone} onChange={s("phone")} testid="staff-phone" />
    </div>
    <div className="mt-3 space-y-3">
      {auths.map((a, i) => (
        <div key={i} className="rounded-lg border p-3" style={{ borderColor: "var(--line)" }} data-testid={`staff-auth-${i}`}>
          <div className="flex justify-between mb-2"><b className="text-xs">Autorizație / atestat {i + 1}</b><Badge s={docStatus(a.expires, a.file)} testid={`staff-auth-status-${i}`} /></div>
          <div className="grid sm:grid-cols-4 gap-2">
            <In label="Tip (conform actului)" value={a.type} onChange={(v) => sa(i, "type", v)} testid={`auth-${i}-type`} />
            <In label="Număr" value={a.number} onChange={(v) => sa(i, "number", v)} testid={`auth-${i}-number`} />
            <In label="Emitent" value={a.issuer} onChange={(v) => sa(i, "issuer", v)} testid={`auth-${i}-issuer`} />
            <In label="Categorie / grad" value={a.category} onChange={(v) => sa(i, "category", v)} testid={`auth-${i}-category`} />
            <In label="Domeniu de competență (din act)" value={a.domain} onChange={(v) => sa(i, "domain", v)} testid={`auth-${i}-domain`} full />
            <In label="Data emiterii" type="date" value={a.issued} onChange={(v) => sa(i, "issued", v)} testid={`auth-${i}-issued`} />
            <In label="Valabil până la" type="date" value={a.expires} onChange={(v) => sa(i, "expires", v)} testid={`auth-${i}-expires`} />
          </div>
          <div className="mt-2 flex flex-wrap gap-4 items-center">
            <FileSlot label="Act scanat" file={a.file} onFile={(v) => sa(i, "file", v)} testid={`auth-${i}-file`} />
            <label className="text-xs flex items-center gap-1"><input type="checkbox" checked={!!a.verified} onChange={(e) => sa(i, "verified", e.target.checked)} data-testid={`auth-${i}-verified`} /> Am verificat actul original</label>
            <button className="text-xs" style={{ color: "#b33333" }} onClick={() => setF({ ...f, auths: auths.filter((_, j) => j !== i) })}>Elimină</button>
          </div>
        </div>
      ))}
      <button className="text-xs font-bold inline-flex items-center gap-1" style={{ color: "var(--blue)" }} onClick={() => setF({ ...f, auths: [...auths, {}] })} data-testid="staff-add-auth"><Plus size={13} /> Adaugă autorizație / certificat / diplomă</button>
      <div className="flex flex-wrap gap-4 items-center"><FileSlot label="Semnătura persoanei (imagine)" file={f.signature} onFile={s("signature")} testid="staff-signature" />
        <label className="text-xs flex items-center gap-1"><input type="checkbox" checked={!!f.signature_authorized} onChange={(e) => s("signature_authorized")(e.target.checked)} data-testid="staff-sig-auth" /> Persoana a autorizat folosirea semnăturii</label></div>
    </div>
  </>;
};

function Audit() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get("/audit").then((r) => setRows(r.data)); }, []);
  return <div className="den-panel overflow-x-auto" data-testid="audit-tab"><table className="w-full text-xs"><thead><tr className="text-left" style={{ color: "var(--muted)" }}><th className="p-2">Data</th><th>Utilizator</th><th>Acțiune</th><th>Modul</th><th>Câmpuri</th></tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i} className="border-t" style={{ borderColor: "var(--line)" }}><td className="p-2 whitespace-nowrap">{new Date(r.at).toLocaleString("ro-RO")}</td><td>{r.user}</td><td>{r.action}</td><td>{r.module}</td><td>{(r.fields || []).join(", ")}</td></tr>)}</tbody></table></div>;
}

const TABS = [["firma", "Firmă și atestat"], ["aparate", "Aparate de măsură"], ["personal", "Personal"], ["jurnal", "Jurnal modificări"]];

export default function BaseSettings() {
  const [tab, setTab] = useState("firma");
  return (
    <div>
      <PageHeader eyebrow="Configurare" title="Setări de bază — Firmă, Personal și Autorizații" sub="Datele de aici se preiau automat în dosarele de prosumator după selectarea persoanelor și a aparatului." />
      <div className="flex gap-2 flex-wrap mb-4">{TABS.map(([k, l]) => <button key={k} onClick={() => setTab(k)} data-testid={`base-tab-${k}`} className="rounded-full px-4 py-2 text-[12px] font-bold border"
        style={k === tab ? { background: "var(--navy)", color: "#fff", borderColor: "var(--navy)" } : { background: "#fff", borderColor: "var(--line)" }}>{l}</button>)}</div>
      {tab === "firma" && <Company />}
      {tab === "aparate" && <ListTab module="instruments" empty={{}} render={instRender} title="Aparat nou" testid="inst" />}
      {tab === "personal" && <ListTab module="staff" empty={{ auths: [] }} render={staffRender} title="Persoană nouă" testid="staff" />}
      {tab === "jurnal" && <Audit />}
    </div>
  );
}
