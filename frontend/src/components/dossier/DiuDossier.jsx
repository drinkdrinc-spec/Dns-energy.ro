import { useEffect, useState } from "react";
import { FileDown, RefreshCw, Download, FileType2 } from "lucide-react";
import { toast } from "sonner";
import { api, API, openAuthenticatedFile } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { DiuCircuits } from "./DiuCircuits";

const tok = () => localStorage.getItem("den_token");

const OPERATOR_DOCS = {
  deer: ["Dosar instalației de utilizare și documentația tehnică a instalației de producere", "Proces-verbal de recepție și punere în funcțiune, după caz", "Buletin de încercare a prizei de pământ", "Fișe tehnice și certificate pentru invertor, module și stocare", "Schema monofilară cu tabloul general și protecțiile prevăzute"],
  delgaz: ["Formular DIU DEGR E P46-A38, după caz", "Declarația executantului privind ATR-ul și proiectul verificat", "Proces-verbal de recepție cu rezultate corespunzătoare", "Buletin de verificare a instalației și buletine PRAM", "Schema monofilară cu TG, protecții și reglaje", "Angajamentul consumatorului privind accesul personalului autorizat ANRE", "Proiect tehnic verificat ANRE pentru instalații complexe"],
  retele: ["Declarația executantului privind respectarea ATR-ului și proiectului verificat", "Proces-verbal de recepție cu rezultate corespunzătoare", "Documente de verificare, probe și teste conform normelor", "Schema monofilară, cel puțin până la interfață/TG, cu protecții și reglaje", "Schema surselor proprii avizată de operator, dacă există"],
  oltenia: ["Lista DI-U și formularele curente publicate de operator", "ATR / certificatul de racordare și condițiile tehnice", "Proces-verbal de recepție și buletinele de verificare aplicabile", "Schema monofilară cu tabloul general, protecțiile și reglajele", "Declarațiile executantului și documentele tehnice ale echipamentelor"],
};
const operatorInfoFor = (operator) => {
  const value = String(operator || "").toLowerCase();
  if (!value) return { key: "", label: "Selectează operatorul pentru lista și formularul aplicabil." };
  if (/deer|distributie energie electrica/.test(value)) return { key: "deer", label: "DEER — ghid de racordare pentru prosumatori", url: "https://www.distributie-energie.ro/racordare-la-retea-prosumator/" };
  if (/delgaz/.test(value)) return { key: "delgaz", label: "Delgaz Grid — opis oficial DI-U (DEGR E P46-A38)", url: "https://delgaz.ro/getattachment/52b58b1b-a66a-4a79-888a-4b9ad5990fa0/Opis_Dosar_Instalatie_de_utilizare.pdf" };
  if (/retele electrice|e-distribu/.test(value)) return { key: "retele", label: "Rețele Electrice — lista oficială a documentelor DIU", url: "https://www.reteleelectrice.ro/cereri-documente/" };
  if (/oltenia|deo connect/.test(value)) return { key: "oltenia", label: "Distribuție Oltenia — portalul oficial de documente", url: "https://www.distributieoltenia.ro/" };
  return { key: "", label: "Lista este orientativă. Confirmă formularul și cerințele actuale pe site-ul operatorului." };
};
const operatorDocsFor = (operator) => {
  const info = operatorInfoFor(operator);
  return OPERATOR_DOCS[info.key] || ["Formularul oficial DI-U și anexele aplicabile", "ATR / certificatul de racordare și condițiile tehnice", "Schema monofilară și documentația tehnică", "Procese-verbale și buletine de verificare", "Declarații și fișe tehnice ale echipamentelor"];
};


export function DiuDossier({ id, form, setVal, setForm, savedAt }) {
  const [pros, setPros] = useState([]);
  const [pid, setPid] = useState(form.pros_id || "");
  const [docs, setDocs] = useState(null);
  const availablePros = pros.filter((item) => !/\bTEST\b/i.test([item.number, item.client_name].filter(Boolean).join(" ")));
  const loadDocs = () => api.get(`/diu/${id}/docs`).then((r) => setDocs(r.data)).catch(() => {});
  useEffect(() => { api.get("/data/prosumator").then((r) => setPros(r.data)).catch(() => {}); loadDocs(); }, [id]); // eslint-disable-line
  useEffect(() => { if (savedAt) loadDocs(); }, [savedAt]); // eslint-disable-line

  const importPros = async () => {
    try { const { data } = await api.post(`/diu/${id}/import-pros`, { pros_id: pid }); setForm({ ...form, ...data }); toast.success("Date preluate din dosarul de prosumator"); loadDocs(); }
    catch (e) { toast.error(e.response?.data?.detail || "Eroare"); }
  };
  const pdf = (doc) => `/diu/${id}/pdf?doc=${doc}`

  return (
    <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="diu-dossier">
      <h3 className="font-bold">Dosarul instalației de utilizare — documente automate</h3>
      <div className="flex flex-wrap items-end gap-2 mt-3">
        <div className="den-field min-w-[260px]"><label>Pornește din dosarul de prosumator</label>
          <select className="den-input" value={pid} onChange={(e) => setPid(e.target.value)} data-testid="diu-pros-select">
            <option value="">Alege dosarul...</option>
            {availablePros.map((p) => <option key={p.id} value={p.id}>{p.client_name || "fără nume"} — {p.address || p.pod || p.id.slice(0, 6)}</option>)}
          </select></div>
        <Btn variant="secondary" onClick={importPros} disabled={!pid} data-testid="diu-import-btn"><Download size={14} /> Preia datele</Btn>
      </div>
      <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Se preiau clientul, adresa, puterea, operatorul, ATR, protecțiile TG și circuitele invertoarelor. Circuitele existente nu se suprascriu.</p>
      <div className="mt-4 rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }} data-testid="diu-operator-requirements">
        <div className="font-bold text-sm">Dosar adaptat operatorului de distribuție</div>
        <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Operator selectat: <b>{form.operator || "neselectat"}</b>. Lista de mai jos ajută la pregătirea dosarului; cerințele finale și formularele condiționale se confirmă din sursa oficială.</p>
        {operatorInfoFor(form.operator).url && <a className="mt-2 inline-flex text-xs font-semibold underline" href={operatorInfoFor(form.operator).url} target="_blank" rel="noopener noreferrer" data-testid="diu-official-requirements">Deschide {operatorInfoFor(form.operator).label} ↗</a>}
        <ul className="mt-2 grid sm:grid-cols-2 gap-2 text-xs">{operatorDocsFor(form.operator).map((item) => <li key={item} className="rounded border px-3 py-2" style={{ borderColor: "var(--line)" }}>□ {item}</li>)}</ul>
      </div>
      <DiuCircuits form={form} setVal={setVal} />
      <div className="flex items-center justify-between flex-wrap gap-2 mt-5">
        <div className="text-xs font-bold" style={{ color: docs?.complete ? "#166534" : "#9b2c2c" }} data-testid="diu-docs-state">
          {docs ? (docs.complete ? "Toate documentele sunt complete" : "Unele documente au date lipsă (export CIORNĂ)") : ""} · stările se actualizează după „Salvează”</div>
        <div className="flex gap-2">
          <Btn variant="secondary" onClick={loadDocs} data-testid="diu-docs-refresh"><RefreshCw size={14} /> Actualizează</Btn>
          <Btn onClick={() => openAuthenticatedFile(pdf("all"))} data-testid="diu-export"><FileDown size={14} /> Dosar DI-U complet PDF</Btn>
        </div>
      </div>
      <div className="mt-2 space-y-1">{(docs?.positions || []).map((p) => (
        <div key={p.key} className="flex items-start justify-between gap-2 rounded-lg bg-white border px-3 py-2 text-xs" style={{ borderColor: "var(--line)" }} data-testid={`diu-doc-${p.key}`}>
          <div><b>{p.nr}. {p.title}</b>{p.missing.length > 0 && <div style={{ color: "#9b2c2c" }}>Lipsă: {p.missing.join(", ")}</div>}</div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="font-bold rounded-full px-2 py-0.5" style={p.status === "semnat" ? { background: "#ecfdf3", color: "#166534" } : p.missing.length ? { background: "#fff0f0", color: "#9b2c2c" } : { background: "#eef4ff", color: "#1d4ed8" }} data-testid={`diu-doc-status-${p.key}`}>{p.status}{p.signed_at ? ` ${new Date(p.signed_at).toLocaleDateString("ro-RO")}` : ""}</span>
            <button type="button" onClick={() => openAuthenticatedFile(pdf(p.key))} title={p.signed_at ? "PDF semnat" : "PDF"} data-testid={`diu-doc-pdf-${p.key}`}><FileDown size={15} style={{ color: "var(--blue)" }} /></button>
            {p.docx && <button type="button" onClick={() => openAuthenticatedFile(`/diu/${id}/pdf?doc=${p.key}&fmt=docx`)} title="Word (editabil)" data-testid={`diu-doc-docx-${p.key}`}><FileType2 size={15} style={{ color: "var(--blue)" }} /></button>}
          </div>
        </div>))}</div>
    </div>
  );
}
