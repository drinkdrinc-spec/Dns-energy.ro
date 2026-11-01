import { useEffect, useState } from "react";
import { FileDown, RefreshCw, Download, FileType2 } from "lucide-react";
import { toast } from "sonner";
import { api, API, openAuthenticatedFile, downloadAuthenticatedFile } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { DiuCircuits } from "./DiuCircuits";

const tok = () => localStorage.getItem("den_token");

const OPERATOR_DOCS = {
  deer: [
    { label: "Dosar instalației și documentația tehnică", keys: ["opis", "memoriu"] },
    { label: "Proces-verbal de recepție și punere în funcțiune", keys: ["receptie", "pif"] },
    { label: "Buletine de verificare PRAM", keys: ["pram_priza", "pram_cont", "pram_izol", "pram_ddr"] },
    { label: "Fișe tehnice și certificate pentru echipamente", external: true },
    { label: "Schema monofilară cu TG și protecții", keys: ["schema_tg"] },
  ],
  delgaz: [
    { label: "Formularul oficial DIU DEGR E P46-A38, după caz", external: true },
    { label: "Declarația executantului privind ATR-ul și proiectul verificat", keys: ["conformitate"], external: true },
    { label: "Proces-verbal de recepție și PIF", keys: ["receptie", "pif"] },
    { label: "Buletine de verificare PRAM", keys: ["pram_priza", "pram_cont", "pram_izol", "pram_ddr"] },
    { label: "Schema monofilară cu TG, protecții și reglaje", keys: ["schema_tg"] },
    { label: "Angajamentul consumatorului privind accesul personalului autorizat ANRE", keys: ["angajament_delgaz"] },
    { label: "Proiect tehnic verificat ANRE, dacă este aplicabil", external: true },
  ],
  retele: [
    { label: "Declarația executantului privind respectarea ATR-ului și proiectului verificat", keys: ["conformitate"], external: true },
    { label: "Proces-verbal de recepție și PIF", keys: ["receptie", "pif"] },
    { label: "Documente de verificare și probe", keys: ["pram_priza", "pram_cont", "pram_izol", "pram_ddr"] },
    { label: "Schema monofilară până la interfață/TG", keys: ["schema_tg"] },
    { label: "Schema surselor proprii avizată, dacă există", external: true },
  ],
  oltenia: [
    { label: "Lista și formularele curente publicate de operator", external: true },
    { label: "ATR / certificatul de racordare și condițiile tehnice", external: true },
    { label: "Proces-verbal de recepție și buletinele aplicabile", keys: ["receptie", "pram_priza", "pram_cont", "pram_izol", "pram_ddr"] },
    { label: "Schema monofilară cu tabloul general și protecțiile", keys: ["schema_tg"] },
    { label: "Declarațiile și fișele tehnice ale echipamentelor", keys: ["conformitate"], external: true },
  ],
};
const operatorInfoFor = (operator) => {
  const value = String(operator || "").toLowerCase();
  if (!value) return { key: "", label: "Selectează operatorul pentru lista și formularul aplicabil." };
  if (/deer|distributie energie electrica/.test(value)) return { key: "deer", label: "DEER — ghid de racordare pentru prosumatori", url: "https://www.distributie-energie.ro/racordare-la-retea-prosumator/" };
  if (/delgaz/.test(value)) return { key: "delgaz", label: "Delgaz Grid — opis oficial DI-U (DEGR E P46-A38)", url: "https://delgaz.ro/getattachment/4b81ca72-870b-4f1b-a703-b21ef7059bc4/Opis_Dosar_Instalatie_de_utilizare.pdf" };
  if (/retele electrice|e-distribu/.test(value)) return { key: "retele", label: "Rețele Electrice — lista oficială a documentelor DIU", url: "https://www.reteleelectrice.ro/cereri-documente/" };
  if (/oltenia|deo connect/.test(value)) return { key: "oltenia", label: "Distribuție Oltenia — portalul oficial de documente", url: "https://www.distributieoltenia.ro/" };
  return { key: "", label: "Lista este orientativă. Confirmă formularul și cerințele actuale pe site-ul operatorului." };
};
const operatorDocsFor = (operator) => {
  const info = operatorInfoFor(operator);
  return OPERATOR_DOCS[info.key] || [
    { label: "Formularul oficial DI-U și anexele aplicabile", external: true },
    { label: "ATR / certificatul de racordare și condițiile tehnice", external: true },
    { label: "Schema monofilară și documentația tehnică", keys: ["schema_tg", "memoriu"] },
    { label: "Procese-verbale și buletine de verificare", keys: ["receptie", "pif", "pram_priza", "pram_cont", "pram_izol", "pram_ddr"] },
    { label: "Declarații și fișe tehnice ale echipamentelor", keys: ["conformitate"], external: true },
  ];
};
const requirementState = (item, docs) => {
  if (!docs && item.keys?.length) return { label: "Se verifică…", tone: "#475569", bg: "#f1f5f9" };
  const positions = (item.keys || []).map((key) => docs?.positions?.find((position) => position.key === key)).filter(Boolean);
  if (!positions.length) return item.external
    ? { label: "Verificare / atașare la operator", tone: "#92400e", bg: "#fffbeb" }
    : { label: "Nu este generat pentru acest dosar", tone: "#475569", bg: "#f1f5f9" };
  const missing = positions.some((position) => position.missing?.length);
  if (item.external) return missing
    ? { label: "De completat · verifică/atașează la operator", tone: "#991b1b", bg: "#fef2f2" }
    : { label: "Generat · verifică și atașează la operator", tone: "#92400e", bg: "#fffbeb" };
  return missing
    ? { label: "De completat", tone: "#991b1b", bg: "#fef2f2" }
    : { label: "Generat în dosar · verifică și semnează", tone: "#166534", bg: "#f0fdf4" };
};


export function DiuDossier({ id, form, setVal, setForm, savedAt }) {
  const [pros, setPros] = useState([]);
  const [pid, setPid] = useState(form.pros_id || "");
  const [docs, setDocs] = useState(null);
  const [importing, setImporting] = useState(false);
  const isTestRecord = (value) => /\bTEST\b/i.test(String(value || ""));
  const isTestDiu = isTestRecord(form.number) || isTestRecord(form.client_name);
  const normalizeClient = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
  const matchesClient = (item) => (form.client_id && item.client_id)
    ? form.client_id === item.client_id
    : Boolean(normalizeClient(form.client_name) && normalizeClient(form.client_name) === normalizeClient(item.client_name));
  const availablePros = pros.filter((item) => {
    const isTestPros = isTestRecord([item.number, item.client_name].filter(Boolean).join(" "));
    return isTestPros === isTestDiu && matchesClient(item);
  });
  useEffect(() => { setPid(form.pros_id || ""); }, [id, form.pros_id]);
  const loadDocs = () => api.get(`/diu/${id}/docs`).then((r) => setDocs(r.data)).catch(() => {});
  useEffect(() => { api.get("/data/prosumator").then((r) => setPros(r.data)).catch(() => {}); loadDocs(); }, [id]); // eslint-disable-line
  useEffect(() => { if (savedAt) loadDocs(); }, [savedAt]); // eslint-disable-line

  const importPros = async (selectedPid = pid) => {
    if (!selectedPid || importing) return;
    setImporting(true);
    try {
      const { data } = await api.post(`/diu/${id}/import-pros`, { pros_id: selectedPid });
      setPid(selectedPid);
      setForm((current) => ({ ...current, ...data }));
      toast.success("Datele dosarului au fost preluate automat");
      loadDocs();
    } catch (e) {
      setPid(form.pros_id || "");
      toast.error(e.response?.data?.detail || "Nu am putut prelua dosarul");
    } finally { setImporting(false); }
  };
  const pdf = (doc) => `/diu/${id}/pdf?doc=${doc}`

  return (
    <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f8fafd" }} data-testid="diu-dossier">
      <h3 className="font-bold">Dosarul instalației de utilizare — documente automate</h3>
      <div className="flex flex-wrap items-end gap-2 mt-3">
        <div className="den-field min-w-[260px]"><label>Pornește din dosarul de prosumator</label>
          <select className="den-input" value={pid} onChange={(e) => importPros(e.target.value)} disabled={importing} data-testid="diu-pros-select">
            <option value="">Alege dosarul...</option>
            {availablePros.map((p) => <option key={p.id} value={p.id}>{isTestRecord([p.number, p.client_name].filter(Boolean).join(" ")) ? "TEST · " : ""}{p.client_name || "fără nume"} — {p.address || p.pod || p.id.slice(0, 6)}</option>)}
          </select></div>
        <Btn variant="secondary" onClick={() => importPros()} disabled={!pid || importing} data-testid="diu-import-btn"><Download size={14} /> {importing ? "Se preiau..." : "Reîncarcă datele"}</Btn>
      </div>
      <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Datele, protecțiile și circuitele se preiau din dosarul prosumator selectat. Valorile PRAM sunt incluse numai dacă au fost măsurate și salvate; schimbarea instalației elimină măsurătorile vechi.</p>
      <div className="mt-4 rounded-lg border bg-white p-3" style={{ borderColor: "var(--line)" }} data-testid="diu-operator-requirements">
        <div className="font-bold text-sm">Dosar adaptat operatorului de distribuție</div>
        <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Operator selectat: <b>{form.operator || "neselectat"}</b>. Lista de mai jos ajută la pregătirea dosarului; cerințele finale și formularele condiționale se confirmă din sursa oficială.</p>
        {operatorInfoFor(form.operator).url && <a className="mt-2 inline-flex text-xs font-semibold underline" href={operatorInfoFor(form.operator).url} target="_blank" rel="noopener noreferrer" data-testid="diu-official-requirements">Deschide {operatorInfoFor(form.operator).label} ↗</a>}
        <ul className="mt-2 grid sm:grid-cols-2 gap-2 text-xs">{operatorDocsFor(form.operator).map((item) => { const state = requirementState(item, docs); return <li key={item.label} className="rounded border px-3 py-2 flex items-start justify-between gap-2" style={{ borderColor: "var(--line)" }}><span>{item.label}</span><span className="shrink-0 rounded-full px-2 py-0.5 font-semibold text-[10px]" style={{ color: state.tone, background: state.bg }}>{state.label}</span></li>; })}</ul>
      </div>
      <details className="mt-4 rounded-xl border bg-white px-4" style={{ borderColor: "var(--line)" }} data-testid="diu-technical-details">
        <summary className="cursor-pointer py-3 text-sm font-semibold">Detalii tehnice, circuite și rezultate PRAM</summary>
        <div className="pb-4"><DiuCircuits form={form} setVal={setVal} /></div>
      </details>
      <div className="flex items-center justify-between flex-wrap gap-2 mt-5">
        <div className="text-xs font-bold" style={{ color: docs?.complete ? "#166534" : "#9b2c2c" }} data-testid="diu-docs-state">
          {docs ? (docs.complete ? "Toate documentele sunt complete" : "Unele documente au date lipsă (export CIORNĂ)") : ""} · stările se actualizează după „Salvează”</div>
        <div className="flex gap-2">
          <Btn variant="secondary" onClick={loadDocs} data-testid="diu-docs-refresh"><RefreshCw size={14} /> Actualizează</Btn>
          <Btn onClick={() => downloadAuthenticatedFile(`/diu/${id}/package`, `DIU_${id}.zip`)} data-testid="diu-package"><FileDown size={14} /> Descarcă dosarul + acte + fișe (ZIP)</Btn>
          <Btn variant="secondary" onClick={() => openAuthenticatedFile(pdf("all"))} data-testid="diu-export"><FileDown size={14} /> PDF DI-U</Btn>
        </div>
      </div>
      <div className="mt-2 space-y-1">{(docs?.positions || []).map((p) => (
        <div key={p.key} className="flex items-start justify-between gap-2 rounded-lg bg-white border px-3 py-2 text-xs" style={{ borderColor: "var(--line)" }} data-testid={`diu-doc-${p.key}`}>
          <div><b>{p.nr}. {p.title}</b>{p.missing.length > 0 && <div style={{ color: "#9b2c2c" }}>Lipsă: {p.missing.join(", ")}</div>}</div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="font-bold rounded-full px-2 py-0.5" style={p.status === "semnat" ? { background: "#ecfdf3", color: "#166534" } : p.missing.length ? { background: "#fff0f0", color: "#9b2c2c" } : { background: "#eef4ff", color: "#1d4ed8" }} data-testid={`diu-doc-status-${p.key}`}>{p.status}{p.signed_at ? ` ${new Date(p.signed_at).toLocaleDateString("ro-RO")}` : ""}</span>
            <button type="button" onClick={() => openAuthenticatedFile(pdf(p.key))} title={p.signed_at ? "PDF semnat" : "PDF"} data-testid={`diu-doc-pdf-${p.key}`}><FileDown size={15} style={{ color: "var(--blue)" }} /></button>
            <button type="button" onClick={() => downloadAuthenticatedFile(pdf(p.key), `DIU_${p.key}_${id}.pdf`)} title="Descarcă PDF separat" aria-label={`Descarcă ${p.title} PDF`} data-testid={`diu-doc-download-${p.key}`}><Download size={15} style={{ color: "var(--blue)" }} /></button>
            {p.docx && <button type="button" onClick={() => openAuthenticatedFile(`/diu/${id}/pdf?doc=${p.key}&fmt=docx`)} title="Word (editabil)" data-testid={`diu-doc-docx-${p.key}`}><FileType2 size={15} style={{ color: "var(--blue)" }} /></button>}
          </div>
        </div>))}</div>
    </div>
  );
}
