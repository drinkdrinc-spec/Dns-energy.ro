import { useEffect, useRef, useState } from "react";
import { api, fileUrl } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { uploadFile } from "@/components/dossier/ClientDocs";
import { Plus, Trash2, Upload, FileText } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

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

const CO = [["company", "Denumire firmă"], ["brand", "Brand aplicație"], ["rep", "Reprezentant legal"], ["cui", "CUI"], ["regcom", "Nr. Registrul Comerțului"], ["phone", "Telefon"], ["email", "E-mail"], ["iban", "IBAN încasări"], ["bank", "Banca"], ["address", "Adresă sediu", true],
  ["anre_attest", "Atestat ANRE — număr"], ["anre_category", "Atestat ANRE — tip/categorie"], ["anre_issuer", "Emitent"], ["anre_issued", "Data emiterii", false, "date"],
  ["anre_valid", "Valabil până la", false, "date"], ["next_pram_number", "Următorul nr. buletin PRAM", false, "number"], ["warranty_months", "Garanție lucrări (luni)"], ["kit_bmp", "Text standard kit BMP (PV recepție)", true], ["kit_structure", "Text standard kit structură (PV recepție)", true],
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
        <FileSlot label="Logo firmă (imagine)" file={s.logo} onFile={setFile("logo")} testid="co-logo" />
        <FileSlot label="Antet firmă (imagine)" file={s.header_logo} onFile={setFile("header_logo")} testid="co-header" />
        <FileSlot label="Armătură / element grafic" file={s.armatura} onFile={setFile("armatura")} testid="co-armatura" />
        <FileSlot label="Ștampila firmei (imagine)" file={s.stamp} onFile={setFile("stamp")} testid="co-stamp" />
        <FileSlot label="Atestat ANRE (PDF)" file={s.anre_file} onFile={setFile("anre_file")} testid="co-anre-file" />
        <FileSlot label="Alt document / autorizație" file={null} onFile={(f) => save({ ...s, other_docs: [...(s.other_docs || []), f] })} testid="co-other" />
        {(s.other_docs || []).map((f, i) => <div key={f.storage_path} className="text-xs ml-4 flex gap-2"><a className="underline" style={{ color: "var(--blue)" }} href={fileUrl(f.storage_path)} target="_blank" rel="noopener noreferrer">{f.original_filename}</a>
          <button onClick={() => save({ ...s, other_docs: s.other_docs.filter((_, j) => j !== i) })}><Trash2 size={12} style={{ color: "#b33333" }} /></button></div>)}
      </div>
      <p className="text-[11px] mt-3" style={{ color: "var(--muted)" }}>Ștampila (imagine PNG/JPG) și semnătura grafică a persoanei selectate ca executant/semnatar se aplică automat la generarea documentelor, doar dacă persoana are autorizație valabilă și verificată și a autorizat folosirea semnăturii. Lipsurile și documentele expirate sunt semnalate ca avertisment în dosar.</p>
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
    <div className="mt-3 flex flex-wrap gap-5">
      <label className="text-xs flex items-center gap-2"><input type="checkbox" checked={f.measures_grounding !== false} onChange={(e) => s("measures_grounding")(e.target.checked)} />măsoară priză de pământ</label>
      <label className="text-xs flex items-center gap-2"><input type="checkbox" checked={!!f.measures_insulation} onChange={(e) => s("measures_insulation")(e.target.checked)} />măsoară rezistență izolație (DIU)</label>
      <label className="text-xs flex items-center gap-2"><input type="checkbox" checked={f.active !== false} onChange={(e) => s("active")(e.target.checked)} />activ</label>
    </div>
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
      <In label="CNP (împuternicit)" value={f.cnp} onChange={s("cnp")} testid="staff-cnp" />
      <In label="Adresă domiciliu" value={f.address} onChange={s("address")} testid="staff-address" />
    </div>
    <label className="mt-3 inline-flex items-center gap-2 text-xs"><input type="checkbox" checked={f.active !== false} onChange={(e) => s("active")(e.target.checked)} data-testid="staff-active" />Activ</label>
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

const USER_STATUS = { pending: ["În așteptare", "#fff8e6", "#8a5a00"], active: ["Activ", "#ecfdf3", "#166534"], suspended: ["Suspendat", "#fff0f0", "#9b2c2c"], disabled: ["Dezactivat", "#f3f4f6", "#6b7280"] };
function CompanyUsers() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [staff, setStaff] = useState([]);
  const load = () => api.get("/admin/users").then((r) => setData(r.data)).catch((e) => toast.error(e.response?.data?.detail || "Nu am putut încărca utilizatorii firmei"));
  useEffect(() => { if (user?.role === "admin") { load(); api.get("/data/staff").then((r) => setStaff(r.data)).catch(() => {}); } }, [user?.role]);
  if (user?.role !== "admin") return null;
  if (!data) return <div className="den-panel text-sm" style={{ color: "var(--muted)" }}>Se încarcă utilizatorii firmei…</div>;
  const update = async (id, body) => {
    try { await api.put(`/admin/users/${id}`, body); toast.success("Utilizator salvat"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Nu am putut salva utilizatorul"); }
  };
  return <div className="den-panel" data-testid="company-users-settings">
    <div className="mb-3"><h3 className="font-bold">Utilizatorii firmei</h3><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Asociază fiecare cont cu personalul firmei și stabilește rolul, dreptul de semnare și notificările.</p></div>
    <div className="space-y-2">
      {data.users.map((account) => {
        const status = USER_STATUS[account.status] || USER_STATUS.active;
        const main = account.role === "admin" && !account.tenant && account.id === data.users[0]?.id;
        return <article key={account.id} className="grid gap-3 rounded-xl border p-3 lg:grid-cols-[minmax(180px,1.2fr)_minmax(150px,1fr)_minmax(170px,1fr)_auto_auto_minmax(150px,1fr)] lg:items-center" style={{ borderColor: "var(--line)" }} data-testid={`company-user-${account.email}`}>
          <div className="min-w-0"><b className="block truncate text-sm">{account.name || "Utilizator"}</b><span className="block truncate text-xs" style={{ color: "var(--muted)" }}>{account.email}</span></div>
          <label className="den-field"><span>Rol în firmă</span><select className="den-input" value={account.role} disabled={main} onChange={(e) => update(account.id, { role: e.target.value })} data-testid={`company-user-role-${account.email}`}>{Object.entries(data.roles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="den-field"><span>Profil personal</span><select className="den-input" value={account.staff_id || ""} disabled={main} onChange={(e) => update(account.id, { staff_id: e.target.value })} data-testid={`company-user-staff-${account.email}`}><option value="">— neasociat —</option>{staff.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}</select></label>
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={!!account.is_engineer} disabled={main} onChange={(e) => update(account.id, { is_engineer: e.target.checked })} data-testid={`company-user-engineer-${account.email}`} />Inginer semnatar</label>
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={account.notify_signing !== false} disabled={main} onChange={(e) => update(account.id, { notify_signing: e.target.checked })} data-testid={`company-user-notify-${account.email}`} />Notificări</label>
          <div className="flex flex-wrap items-center gap-2 text-xs"><span className="rounded-full px-2 py-1 font-bold" style={{ background: status[1], color: status[2] }} data-testid={`company-user-status-${account.email}`}>{status[0]}</span>{main ? <span style={{ color: "var(--muted)" }}>administrator principal</span> : <>
            {account.status !== "active" && <button className="font-bold" style={{ color: "#166534" }} onClick={() => update(account.id, { status: "active" })}>Activează</button>}
            {account.status === "active" && <button className="font-bold" style={{ color: "#8a5a00" }} onClick={() => update(account.id, { status: "suspended" })}>Suspendă</button>}
            {account.status !== "disabled" && <button className="font-bold" style={{ color: "#9b2c2c" }} onClick={() => update(account.id, { status: "disabled" })}>Dezactivează</button>}
          </>}</div>
        </article>;
      })}
    </div>
  </div>;
}

const BUNDLE_MODES = [["four", "Patru fișiere: acte client · dosar · schemă · anexe tehnice"], ["one", "Un singur fișier cu tot"], ["three", "Trei fișiere: acte client · dosar (cu schema) · anexe tehnice"], ["two", "Două fișiere: dosar (cu schema) · anexe tehnice"]];
const OPS = ["Rețele Electrice", "DEER", "Delgaz Grid", "Distribuție Energie Oltenia"];
function OutputSettings() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/settings").then((r) => setS(r.data)); }, []);
  if (!s) return null;
  const save = async () => { await api.put("/settings", s); toast.success("Setări documente salvate"); };
  const set = (k, v) => setS((old) => ({ ...old, [k]: v }));
  const operatorModes = s.bundle_operator_modes || {};
  return <div className="den-panel" data-testid="bundle-settings">
    <h3 className="font-bold">Documente</h3><p className="my-2 text-xs" style={{ color: "var(--muted)" }}>Alege în câte PDF-uri se împarte exportul dosarului. Setările pe operator pot suprascrie alegerea generală.</p>
    <div className="space-y-2">{BUNDLE_MODES.map(([v, label]) => <label key={v} className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm" style={{ borderColor: (s.bundle_mode || "one") === v ? "var(--green)" : "var(--line)", background: (s.bundle_mode || "one") === v ? "#f2faf5" : "white" }}><input type="radio" name="bundle-mode" checked={(s.bundle_mode || "one") === v} onChange={() => set("bundle_mode", v)} /><span>{label}</span></label>)}</div>
    <div className="mt-4 border-t pt-3" style={{ borderColor: "var(--line)" }}><b className="text-sm">Pe operatorul de distribuție</b><p className="my-1 text-xs" style={{ color: "var(--muted)" }}>„Ca mai sus” folosește împărțirea generală.</p><div className="space-y-2">{OPS.map((op) => <label key={op} className="grid items-center gap-3 text-sm sm:grid-cols-[170px_minmax(0,1fr)]"><span>{op}</span><select className="den-input" value={operatorModes[op] || "default"} onChange={(e) => set("bundle_operator_modes", { ...operatorModes, [op]: e.target.value === "default" ? "" : e.target.value })}><option value="default">Ca mai sus</option>{BUNDLE_MODES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label>)}</div></div>
    <div className="mt-4 text-right"><Btn onClick={save} data-testid="bundle-settings-save">Salvează</Btn></div>
  </div>;
}

const DEFAULT_SIZING = {
  connection_mono: [[3.7, 16], [4.6, 20], [5.8, 25], [7.4, 32], [9.2, 40], [11.5, 50]],
  connection_tri: [[22.2, 32], [27.7, 40], [34.6, 50], [43.6, 63]],
  inverter_mono: [[3, 20], [5, 25], [6, 32], [8, 40]],
  inverter_tri: [[10, 25], [15, 32], [20, 40], [30, 63]],
  cable_cu: [[16, 2.5], [25, 4], [32, 6], [50, 10], [63, 16], [100, 25]],
  inverter_min_section: 6,
};
const SIZING_LABELS = { connection_mono: "Branșament monofazat", connection_tri: "Branșament trifazat", inverter_mono: "Invertor monofazat", inverter_tri: "Invertor trifazat", cable_cu: "Cablu Cu (Normativ I7)" };
function SizingSettings() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/settings").then((r) => setS(r.data)); }, []);
  if (!s) return null;
  const rules = { ...DEFAULT_SIZING, ...(s.sizing_rules || {}) };
  const save = async (next = rules) => { const body = { ...s, sizing_rules: next }; await api.put("/settings", body); setS(body); toast.success("Dimensionarea a fost salvată"); };
  const setRows = (key, rows) => { rules[key] = rows; setS({ ...s, sizing_rules: { ...rules } }); };
  const restore = () => save(DEFAULT_SIZING);
  return <div className="den-panel" data-testid="sizing-settings">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-bold">Dimensionare — siguranțe și cabluri</h3><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Treptelor de putere le corespund siguranțe și secțiuni minime folosite ca propuneri în dosare.</p></div><button className="text-xs font-bold" onClick={restore} data-testid="sizing-reset">↶ Standard</button></div>
    <div className="grid gap-3 xl:grid-cols-2">
      {Object.entries(SIZING_LABELS).map(([key, title]) => <div key={key} className="rounded-xl border p-3" style={{ borderColor: "var(--line)" }}><b className="text-xs uppercase tracking-wide">{title}</b><p className="my-1 text-[11px]" style={{ color: "var(--muted)" }}>{key === "cable_cu" ? "disjunctor (A) → secțiune minimă (mm²)" : "putere maximă (kW) → disjunctor (A)"}</p>{(rules[key] || []).map((row, i) => <div key={i} className="mb-1 flex items-center gap-2"><span className="text-xs">≤</span><input className="den-input !w-24 !py-1.5" type="number" step="any" value={row[0]} aria-label={`${title}, prag ${i + 1}`} onChange={(e) => setRows(key, rules[key].map((x, j) => j === i ? [e.target.value, x[1]] : x))} />{key === "cable_cu" ? <span>A →</span> : <span>kW →</span>}<input className="den-input !w-24 !py-1.5" type="number" step="any" value={row[1]} aria-label={`${title}, valoare ${i + 1}`} onChange={(e) => setRows(key, rules[key].map((x, j) => j === i ? [x[0], e.target.value] : x))} />{key === "cable_cu" && <span className="text-xs">mm²</span>}<button className="ml-auto px-2 text-sm" style={{ color: "#9b2c2c" }} onClick={() => setRows(key, rules[key].filter((_, j) => j !== i))} aria-label={`Șterge prag ${i + 1}`}>♲</button></div>)}<button className="mt-1 text-xs font-bold" style={{ color: "var(--blue)" }} onClick={() => setRows(key, [...(rules[key] || []), ["", ""]])}>＋ treaptă</button></div>)}
      <div className="rounded-xl border p-3" style={{ borderColor: "var(--line)" }}><b className="text-xs uppercase tracking-wide">Podea trasee invertor</b><p className="my-2 text-[11px]" style={{ color: "var(--muted)" }}>Secțiunea minimă pe cablul invertor→BMP/TEG (derating + cădere de tensiune).</p><div className="flex items-center gap-2"><span className="text-xs" style={{ color: "var(--muted)" }}>minim</span><input className="den-input !w-20 !py-1.5" type="number" min="1.5" step="0.5" value={rules.inverter_min_section ?? 6} onChange={(e) => { rules.inverter_min_section = e.target.value; setS({ ...s, sizing_rules: { ...rules } }); }} aria-label="Secțiune minimă cablu invertor în mm pătrați" data-testid="sizing-inverter-min-section" /><span className="text-xs">mm²</span></div><p className="mt-3 text-[11px]" style={{ color: "var(--muted)" }}>Format cablu: mono RVK 3× (L+N+PE). trifazat RVK 5× (3L+N+PE).<br />Derivarea valorilor standard: docs/tabel-sigurante-cabluri.md.</p></div>
    </div>
    <div className="mt-4 text-right"><Btn onClick={() => save()} data-testid="sizing-save">Salvează</Btn></div>
  </div>;
}

export default function BaseSettings() {
  return (
    <div className="space-y-5">
      <PageHeader eyebrow="Configurare" title="Setări firmă" sub="Profil, utilizatori, personal autorizat, aparate de măsură, documente și reguli de dimensionare folosite în dosare." />
      <section className="space-y-2" data-testid="settings-company-section"><div><h2 className="text-base font-bold">Profil firmă</h2><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Datele și fișierele firmei folosite în documente.</p></div><Company /></section>
      <section className="space-y-2" data-testid="settings-users-section"><CompanyUsers /></section>
      <section className="space-y-2" data-testid="settings-staff-section"><div><h2 className="text-base font-bold">Ingineri și personal</h2><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Autorizații, semnături și datele persoanelor preluate în dosare.</p></div><ListTab module="staff" empty={{ auths: [] }} render={staffRender} title="Persoană nouă" testid="staff" /></section>
      <section className="space-y-2" data-testid="settings-instruments-section"><div><h2 className="text-base font-bold">Aparate de măsură PRAM</h2><p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Serii, documente metrologice și tipurile de măsurători efectuate.</p></div><ListTab module="instruments" empty={{}} render={instRender} title="Aparat nou" testid="inst" /></section>
      <section className="space-y-2" data-testid="settings-documents-section"><OutputSettings /></section>
      <section className="space-y-2" data-testid="settings-sizing-section"><SizingSettings /></section>
      <section className="space-y-2" data-testid="settings-audit-section"><div><h2 className="text-base font-bold">Jurnal modificări</h2></div><Audit /></section>
    </div>
  );
}
