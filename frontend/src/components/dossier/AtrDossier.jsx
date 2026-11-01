import { useEffect, useState } from "react";
import { api, API, downloadAuthenticatedFile, openAuthenticatedFile } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Slot } from "@/components/dossier/PowerDossier";
import { Plus, Trash2, CheckCircle2, AlertTriangle } from "lucide-react";
import { FormAlert } from "@/components/dossier/FormAlert";
import { AtrTracking } from "@/components/dossier/AtrTracking";

function installedPanelKwp(pros) {
  if (!pros) return "";
  const number = (value) => {
    const parsed = Number(String(value ?? "").replace(",", "."));
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const inverters = pros.cef?.inverters || [];
  const calculated = inverters.reduce((total, inverter) => {
    const panelW = number(inverter.panel_w);
    const panels = (inverter.strings || []).reduce((sum, string) => sum + number(string.panels), 0);
    const count = Math.max(1, number(inverter.count || inverter.quantity) || 1);
    return total + panels * panelW * count / 1000;
  }, 0);
  if (calculated > 0) return Number(calculated.toFixed(3));
  const legacyPanels = number(pros.panel_count);
  const legacyW = number(pros.panel_w);
  if (legacyPanels > 0 && legacyW > 0) return Number((legacyPanels * legacyW / 1000).toFixed(3));
  return pros.cef?.total_kwp || pros.panel_kwp || pros._kwp || "";
}

function normalizeClientName(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO").replace(/\s+/g, " ");
}

function normalizeLocation(value) {
  return normalizeClientName(value).replace(/[^a-z0-9]/g, "");
}

const DOCS = [["plan", "Plan de situație la scară (viza emitentului CU) / schiță de amplasament", "req"], ["cf", "Extras de carte funciară (CF / nr. cadastral)", "req"],
  ["prop", "Act de proprietate / drept de folosință", "req"], ["id", "Act de identitate / CUI / acte de funcționare", "req"], ["cu", "Certificat de urbanism", "new"],
  ["ac", "Autorizație de construire", ""], ["puz", "PUZ / PUD (dacă e cerut prin CU)", ""], ["acord", "Acord notarial proprietar (dacă nu e proprietar)", ""],
  ["imp", "Împuternicire reprezentant / proiectant", ""], ["gdpr", "Notă DEER privind prelucrarea datelor personale (persoane fizice, după caz)", ""],
  ["authenticity", "Declarație DEER privind autenticitatea datelor (obligatorie pentru toate cererile)", "deer"], ["memoriu", "Memoriu tehnic — date tehnice și energetice", ""],
  ["schema", "Schemă monofilară instalație de producere + racordare", "prod"], ["fise", "Fișe tehnice / certificate invertoare", "prod"], ["pram", "Buletin de încercare a prizei de pământ", "spor"], ["receptie", "Proces-verbal de recepție a instalației de producere", "spor"], ["constatator", "Certificat constatator ONRC (persoană juridică prosumator)", "pj"], ["atr_prev", "ATR / certificat de racordare anterior", "existing"]];
const OFFICIAL_SOURCES = [
  { id: "deer", match: /deer|distribuție energie electrică|distributie energie electrica/i, name: "DEER — formulare și documente de racordare", docs: "https://www.distributie-energie.ro/racordare-la-retea-2/", portal: "https://avize.distributie-energie.ro/" },
  { id: "delgaz", match: /delgaz/i, name: "Delgaz Grid — documente pentru prosumatori", docs: "https://delgaz.ro/energie-electrica/prosumatori", portal: "https://delgaz.ro/" },
  { id: "oltenia", match: /oltenia|deo connect|distribuție oltenia|distributie oltenia/i, name: "Distribuție Oltenia — formulare pentru prosumatori", docs: "https://www.distributieoltenia.ro/ro/informatii-utile/prosumatori/formularele-necesare-pentru-a-deveni-prosumator.html", portal: "https://portal.distributieoltenia.ro/" },
  { id: "rer", match: /rețele electrice|retele electrice|e-distribu/i, name: "Rețele Electrice România — cereri și documente", docs: "https://www.reteleelectrice.ro/cereri-documente/", portal: "https://www.reteleelectrice.ro/" },
];
const DEER_FORMS = [
  { value: "Loc nou de consum și producere — Anexa 1", title: "Cerere loc de consum și producere nou — Anexa 1", url: "https://www.distributie-energie.ro/wp-content/uploads/2023/12/1.-Loc-consum-si-producere-nou-_Anexa-nr-1.docx", key: "new" },
  { value: "Loc existent — notificare — Anexa 2", title: "Notificare loc de consum existent — Anexa 2", url: "https://www.distributie-energie.ro/wp-content/uploads/2023/12/2.-Loc-de-consum-existent_Anexa-nr-2.docx", key: "existing" },
  { value: "Loc existent prosumator — actualizare CRR — Anexa 3", title: "Notificare loc consum și producere existent, actualizare CRR — Anexa 3", url: "https://www.distributie-energie.ro/wp-content/uploads/2023/12/3.-Loc-de-consum-si-producere-existent-actualizare-CRR_Anexa-nr-3.docx", key: "existing" },
  { value: "Loc existent — spor de putere — Anexa 1", title: "Cerere loc existent cu spor de putere — Anexa 1", url: "https://www.distributie-energie.ro/wp-content/uploads/2023/12/4.-Loc-consum-si_sau-producere-existent-Spor-Putere_Anexa-nr-1.docx", key: "spor" },
  { value: "Prosumator prin program de finanțare — Anexa 4", title: "Cerere de racordare prosumator prin programe de finanțare — Anexa 4", url: "https://www.distributie-energie.ro/wp-content/uploads/2023/12/5.-Cerere-de-racordare-prosumator-%E2%80%93-prin-programe-de-finantare-Anexa-4.docx", key: "new" },
  { value: "Loc existent ≤10,8 kW — notificare simplificată — Anexa 5", title: "Notificare prosumator / proiect demonstrativ ≤10,8 kW — Anexa 5", url: "https://www.distributie-energie.ro/wp-content/uploads/2023/12/5.-Loc-consum-si_sau-producere-existent-prevazut_cu_instalatii_de_producere_Anexa-nr-5.docx", key: "existing" },
  { value: "Producere >400 kW — procedură dedicată", title: "Cerere pentru instalații de producere >400 kW — procedură dedicată", url: "https://www.distributie-energie.ro/wp-content/uploads/2024/04/Persoane-fizice-si-juridice-care-au-puterea-instalata-pe-producere-mai-mare-de-400kW.doc", key: "large" },
];
const AUTH_DECLARATION_URL = "https://www.distributie-energie.ro/racordare-la-retea-2/";
const AUTO = { schema: "schemă aprobată", fise: "fișe catalog" };
const pdf = (id, full) => `/atr/${id}/pdf?full=${full}`

export function AtrDossier({ id, form, setVal }) {
  const [pros, setPros] = useState([]);
  const [officialForms, setOfficialForms] = useState([]);
  const [catalogFiles, setCatalogFiles] = useState([]);
  useEffect(() => { api.get("/data/prosumator").then((r) => setPros(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    if (!form.client_name || !pros.length) return;
    const current = pros.find((p) => p.id === form.pros_id);
    const belongsToClient = (item) => item.client_id
      ? item.client_id === form.client_id
      : normalizeClientName(item.client_name) === normalizeClientName(form.client_name);
    if (current && belongsToClient(current)) return;
    const candidates = pros.filter(belongsToClient);
    const locationValue = form.pod || form.address;
    const locationKey = normalizeLocation(locationValue);
    const matches = locationKey ? candidates.filter((item) => normalizeLocation(form.pod ? item.pod : item.address) === locationKey) : candidates;
    if (matches.length === 1) selectPros(matches[0].id);
    else if (current && !belongsToClient(current)) setVal("pros_id", "");
  }, [form.client_id, form.client_name, form.pod, form.address, form.pros_id, pros.length]);
  useEffect(() => {
    if (!form.operator) { setOfficialForms([]); return; }
    api.get(`/forms/operator-links?operator=${encodeURIComponent(form.operator)}&scope=atr`)
      .then((r) => setOfficialForms(r.data || []))
      .catch(() => setOfficialForms([]));
  }, [form.operator]);
  const operatorSource = OFFICIAL_SOURCES.find((source) => source.match.test(String(form.operator || ""))); 
  const selectedDeerForm = DEER_FORMS.find((f) => f.value === form.deer_case) || null;
  const selectedRecord = pros.find((p) => p.id === form.pros_id) || null;
  const selectedPros = selectedRecord && (selectedRecord.client_id
    ? selectedRecord.client_id === form.client_id
    : normalizeClientName(selectedRecord.client_name) === normalizeClientName(form.client_name)) ? selectedRecord : null;
  const deerAnnexIssues = (() => {
    if (operatorSource?.id !== "deer" || !selectedDeerForm) return [];
    const issues = [];
    const kind = String(form.request_type || "").toLocaleLowerCase("ro-RO");
    if (selectedDeerForm.key === "new" && selectedDeerForm.value.includes("loc nou") && !kind.includes("utilizator nou")) issues.push("Anexa 1 pentru loc nou cere tipul de solicitare «utilizator nou definitiv».");
    if (selectedDeerForm.key === "spor" && !kind.includes("spor de putere")) issues.push("Anexa 1 selectată pentru spor trebuie să corespundă tipului solicitării «spor de putere».");
    if (selectedDeerForm.key === "existing" && selectedDeerForm.value.includes("actualizare CRR") && !kind.includes("administrativ")) issues.push("Anexa 3 pentru actualizare CRR cere tipul solicitării administrative.");
    if (selectedDeerForm.value.includes("≤10,8")) {
      const invs = selectedPros?.cef?.inverters || [];
      const stringsPower = invs.reduce((sum, inv) => sum + (inv.strings || []).reduce((n, st) => n + (Number(st.panels) || 0), 0) * (Number(inv.panel_w) || 0) / 1000 * (Number(inv.count) || 1), 0);
      const power = Number(form.pv_kw) || Number(selectedPros?.cef?.total_kwp) || Number(selectedPros?.panel_kwp) || stringsPower || Number(selectedPros?.inverter_kw);
      if (!power) issues.push("Completează puterea instalată de producere pentru verificarea Anexei 5.");
      else if (power > 10.8) issues.push("Anexa 5 este pentru putere instalată de maximum 10,8 kW.");
      const supply = String(form.supply || selectedPros?.supply || selectedPros?.cef?.grid?.supply || "").toLowerCase();
      if (!supply) issues.push("Selectează tipul branșamentului pentru verificarea Anexei 5.");
      else if (supply.includes("trifaz") || supply.includes("400")) issues.push("Anexa 5 selectată cere conexiune diferită de trifazic.");
    }
    if (selectedDeerForm.key === "large") {
      const power = Number(form.pv_kw) || Number(selectedPros?.cef?.total_kwp) || Number(selectedPros?.panel_kwp) || Number(selectedPros?.inverter_kw);
      if (!power) issues.push("Completează puterea instalată de producere pentru procedura dedicată.");
      else if (power <= 400) issues.push("Procedura dedicată DEER selectată este pentru putere instalată mai mare de 400 kW.");
    }
    return issues;
  })();
  const normClientName = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLocaleLowerCase("ro-RO");
  const clientPros = form.client_id
    ? pros.filter((p) => p.client_id === form.client_id)
    : (form.client_name ? pros.filter((p) => normClientName(p.client_name) === normClientName(form.client_name)) : []);
  useEffect(() => {
    if (!form.pros_id) { setCatalogFiles([]); return; }
    let active = true;
    api.get(`/prosumator/${encodeURIComponent(form.pros_id)}/catalog-files`)
      .then((r) => { if (active) setCatalogFiles(Array.isArray(r.data) ? r.data : []); })
      .catch(() => { if (active) setCatalogFiles([]); });
    return () => { active = false; };
  }, [form.pros_id]);
  const catalogRequirements = (() => {
    const cef = selectedPros?.cef || {};
    const requirements = [];
    const add = (kind, model, catalogId) => {
      const name = String(model || "").trim();
      const identity = catalogId || name.toLocaleLowerCase("ro-RO");
      if (identity) requirements.push({ kind, model: name, catalogId: catalogId || "", identity });
    };
    for (const inv of cef.inverters || []) {
      add("invertor", inv.brand_model, inv.catalog_id);
      add("panou", inv.panel_model, inv.panel_catalog_id);
      if (inv.battery_mode === "own") add("baterie", inv.battery?.model, inv.battery?.catalog_id);
    }
    for (const battery of cef.shared_batteries || []) add("baterie", battery.model, battery.catalog_id);
    const seen = new Set();
    return requirements.filter((item) => {
      const key = `${item.kind}:${item.identity}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  })();
  const catalogEvidenceMissing = catalogRequirements.flatMap((item) =>
    ["Fișă tehnică", "Declarație de conformitate"].filter((documentKind) =>
      !catalogFiles.some((file) => file.kind === documentKind && (
        item.catalogId ? file.catalog_id === item.catalogId
          : String(file.model || "").trim().toLocaleLowerCase("ro-RO") === item.model.toLocaleLowerCase("ro-RO")
      ))
    ).map((documentKind) => `${documentKind} — ${item.model || item.kind}`)
  );
  const catalogEquipmentComplete = catalogRequirements.length > 0 && catalogEvidenceMissing.length === 0;
  const equipmentSummary = (() => {
    const cef = selectedPros?.cef || {};
    const items = [];
    for (const [index, inv] of (cef.inverters || []).entries()) {
      const quantity = inv.count || inv.quantity || 1;
      const panelCount = (inv.strings || []).reduce((sum, string) => sum + (Number(string.panels) || 0), 0);
      items.push({ key: `inv-${index}`, label: `Invertor: ${inv.brand_model || "model necompletat"} · ${quantity} buc. · ${inv.p_nom_kw || "—"} kW` });
      if (inv.panel_model || panelCount) items.push({ key: `panel-${index}`, label: `Panouri: ${inv.panel_model || "model necompletat"} · ${panelCount || "—"} buc. · ${inv.panel_w || "—"} Wp` });
      if (inv.battery_mode === "own" && inv.battery?.model) items.push({ key: `battery-own-${index}`, label: `Baterie: ${inv.battery.model} · ${inv.battery.modules || 1} buc. · ${inv.battery.coupling || "cuplare nespecificată"}` });
    }
    for (const [index, battery] of (cef.shared_batteries || []).entries()) {
      items.push({ key: `battery-${index}`, label: `Baterie: ${battery.model || "model necompletat"} · ${battery.modules || 1} buc. · ${battery.coupling || "cuplare nespecificată"}` });
    }
    return items;
  })();
  const selectPros = (id) => {
    setVal("pros_id", id);
    const item = pros.find((p) => p.id === id);
    if (!item || (item.client_id
      ? item.client_id !== form.client_id
      : normalizeClientName(item.client_name) !== normalizeClientName(form.client_name))) {
      setVal("pros_id", "");
      return;
    }
    const values = { pod: item.pod, operator: item.operator, address: item.address, supply: item.supply,
      p_abs_kw: item.bransament_kw, pv_kw: installedPanelKwp(item), p_evac_kw: item.power || item.cef?.total_export_kw };
    Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== "") setVal(key, value); });
  };
  const att = form.attachments || {};
  const recs = form.receptors || [];
  const prod = String(form.kind || "").includes("producere");
  const caseKey = selectedDeerForm?.key || (String(form.request_type || "").toLowerCase().includes("spor") ? "spor" : String(form.request_type || "").startsWith("utilizator nou") ? "new" : "existing");
  const isNew = caseKey === "new";
  const need = operatorSource?.id === "deer"
    ? [...new Set(["authenticity", ...(form.applicant_type === "Persoană fizică" ? ["gdpr"] : []), ...(form.submission_mode === "Prin împuternicit" ? ["imp"] : []),
        ...(["new", "spor", "existing", "large"].includes(caseKey) ? ["id", "cf", "prop"] : []),
        ...(caseKey === "new" ? ["plan"] : []), ...(caseKey === "spor" ? ["plan", "atr_prev", ...(prod ? ["pram", "receptie", "schema", "fise"] : [])] : []),
        ...(caseKey === "existing" && prod ? ["schema", "fise"] : []), ...(caseKey === "large" ? ["memoriu", "schema", "fise"] : []),
        ...(form.applicant_type === "Persoană juridică" && prod ? ["constatator"] : [])])]
    : DOCS.filter(([, , r]) => r === "req" || (r === "prod" && prod) || (r === "new" && isNew) || (r === "spor" && caseKey === "spor")).map(([k]) => k);
  const autoAvailable = (k) => !!form.pros_id && prod && (k === "schema"
    ? Boolean(selectedPros?.cef?.inverters?.length)
    : k === "fise" ? catalogEquipmentComplete : false);
  const has = (k) => k === "fise"
    ? catalogEquipmentComplete
    : (att[k] || []).length > 0 || autoAvailable(k);
  const missing = need.filter((k) => !has(k));
  const setR = (i, k, v) => setVal("receptors", recs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="sm:col-span-2 den-panel mt-3" data-testid="atr-dossier">
      <FormAlert operator={form.operator} scope="atr" />
      {operatorSource?.id === "deer" && <section className="mb-4 rounded-xl border p-4 sm:p-5" style={{ borderColor: "var(--line)", background: "linear-gradient(135deg, #f2f7ff 0%, #fff 72%)" }} data-testid="atr-next-actions">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--blue)" }}>Pachet de depunere · DEER</div>
            <h3 className="mt-1 text-base font-bold">{selectedDeerForm ? selectedDeerForm.title : "Selectează procedura DEER aplicabilă"}</h3>
            <p className="mt-1 text-xs leading-5" style={{ color: "var(--muted)" }}>
              {selectedPros
                ? `Datele POD, puterea și echipamentele sunt legate de dosarul ${selectedPros.number || selectedPros.client_name || "prosumator"}.`
                : "Alege clientul și dosarul de prosumator pentru preluarea automată a datelor tehnice."}
              {" "}Formularul este precompletat din dosar; valorile lipsă rămân goale. Verifică datele și semnează înainte de depunere.
            </p>
          </div>
          {selectedDeerForm && <div className="flex flex-wrap gap-2"><Btn type="button" onClick={() => id && openAuthenticatedFile(`/atr/${encodeURIComponent(id)}/official-docx`)} disabled={!id} data-testid="atr-download-prefilled-deer">Descarcă anexa precompletată (DOCX)</Btn><a href={selectedDeerForm.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-10 items-center justify-center rounded-lg border px-4 text-sm font-semibold" style={{ borderColor: "var(--line)" }} data-testid="atr-download-official-annex">Model necompletat ↗</a></div>}
        </div>
        {deerAnnexIssues.length > 0 && <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900" role="alert" data-testid="atr-deer-annex-eligibility"><strong>Verifică încadrarea procedurii înainte de descărcare:</strong><ul className="mt-1 list-disc pl-4">{deerAnnexIssues.map((issue) => <li key={issue}>{issue}</li>)}</ul></div>}
        {selectedPros && <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full border bg-white px-3 py-1">POD: {selectedPros.pod || "de completat"}</span>
          <span className="rounded-full border bg-white px-3 py-1">Invertor: {selectedPros.inverter_kw || selectedPros.cef?.total_kw || "—"} kW</span>
          <span className="rounded-full border bg-white px-3 py-1">Evacuare: {selectedPros.power || selectedPros.cef?.total_export_kw || "—"} kW</span>
          <span className="rounded-full border bg-white px-3 py-1">Echipamente: {catalogRequirements.length}</span>
        </div>}
        {selectedPros && <div className="mt-3 rounded-lg border bg-white px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-equipment-summary">
          <div className="text-xs font-bold">Echipamente preluate în cerere și anexe</div>
          {equipmentSummary.length ? <ul className="mt-1 grid gap-1 text-xs sm:grid-cols-2">{equipmentSummary.map((item) => <li key={item.key}>{item.label}</li>)}</ul> : <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Nu există echipamente salvate în dosarul de prosumator selectat.</p>}
          {selectedPros.cef?.inverters?.some((inv) => inv.battery_mode === "own" && inv.battery && !inv.battery.model) && <p className="mt-1 text-xs text-amber-700">Completați modelul bateriei în dosarul de prosumator pentru a-l include în anexă.</p>}
        </div>}
        {!selectedDeerForm && <a href={operatorSource.docs} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex text-sm font-semibold underline">Alege formularul pe pagina oficială DEER ↗</a>}
      </section>}
      <details className="mb-3 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-official-details">
        <summary className="cursor-pointer text-sm font-semibold">Formulare oficiale, GDPR și anexă</summary>
        <div className="mt-3">
      {operatorSource?.id === "deer" && <div className="rounded-xl border px-4 py-3 mb-3 text-xs" style={{ borderColor: "var(--line)" }} data-testid="atr-deer-gdpr">
        <div className="font-bold mb-1">Document GDPR — DEER</div>
        <p className="mb-2" style={{ color: "var(--muted)" }}>Pentru persoane fizice, include în dosar nota de informare privind prelucrarea datelor personale, conform listei curente DEER. Este o notă de informare oficială, nu un formular de consimțământ creat de DNS Energy.</p>
        <a href="https://www.distributie-energie.ro/wp-content/uploads/2026/04/Informare-generala-site-v-feb-2026.pdf" target="_blank" rel="noopener noreferrer" className="underline font-semibold">Deschide nota oficială DEER (PDF) ↗</a>
      </div>}
      {form.operator && operatorSource && <div className="rounded-xl border px-4 py-3 mb-3 text-xs" style={{ borderColor: "var(--line)" }} data-testid="atr-official-source-links">
        <div className="font-bold mb-2">Surse oficiale pentru formulare și documente — {form.operator}</div>
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          <a href={operatorSource.docs} target="_blank" rel="noopener noreferrer" className="underline font-semibold">Deschide formularele și lista documentelor <span aria-hidden="true">↗</span></a>
          <a href={operatorSource.portal} target="_blank" rel="noopener noreferrer" className="underline font-semibold">Deschide portalul operatorului <span aria-hidden="true">↗</span></a>
        </div>
        <div className="mt-2" style={{ color: "var(--muted)" }}>Linkuri către surse oficiale. Formularul aplicabil se alege în funcție de locul nou/existent, spor de putere și situația prosumatorului.</div>
      </div>}
      {form.operator && <div className="rounded-xl border px-4 py-3 mb-3 text-xs" style={{ borderColor: "var(--line)" }} data-testid="atr-official-forms">
        <div className="font-bold mb-1">Formulare oficiale înregistrate pentru distribuitor</div>
        {officialForms.length ? officialForms.map((f) => <div key={f.id} className="mt-1">
          <a href={f.url} target="_blank" rel="noopener noreferrer" className="underline font-semibold">{f.title || "Formular oficial ATR"}</a>
          {f.version ? ` · versiunea ${f.version}` : ""}
          {f.status ? ` · ${f.status}` : ""}
        </div>) : <div style={{ color: "var(--muted)" }}>Nu există încă un link ATR înregistrat pentru acest operator. Verificați formularul pe site-ul oficial înainte de depunere.</div>}
        <div className="mt-2" style={{ color: "var(--muted)" }}>PDF-ul generat de DNS Energy este un model completat pentru lucru și verificare; nu este garantat ca reproducere identică a formularului oficial curent.</div>
      </div>}
      {operatorSource?.id === "deer" && selectedDeerForm && <div className="rounded-xl border p-4 mb-4" style={{ borderColor: "var(--line)" }} data-testid="atr-deer-form-selected">
        <div className="font-bold mb-1">Formular DEER selectat</div>
        <div className="text-sm">{selectedDeerForm.title}</div>
        <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>Verifică dacă acest caz corespunde situației locului de consum, puterii și lucrărilor cerute de operator. Documentul oficial se descarcă din DEER.</div>
        <a href={selectedDeerForm.url} target="_blank" rel="noopener noreferrer" className="inline-flex underline font-semibold text-sm mt-2">Deschide formularul oficial selectat ↗</a>
      </div>}
        </div>
      </details>
      <details className="mb-3 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-technical-questionnaire">
        <summary className="cursor-pointer text-sm font-semibold">Chestionar tehnic ATR și lista receptoarelor</summary>
        <div className="mt-3">
      <h3 className="text-[11px] font-bold uppercase tracking-wider mb-3" style={{ color: "var(--blue)" }}>Cerere și chestionar ATR — {prod ? "loc de consum și de producere (prosumator)" : "loc de consum"}</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        {prod && <>
          <div className="sm:col-span-2 rounded-lg border px-3 py-2 text-xs" style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid="atr-pros">
            {(clientPros.length > 1 || (clientPros.length === 1 && !form.pros_id))
              ? <label className="den-field"><span>Alege locul de consum pentru acest client</span><select className="den-input" value={form.pros_id || ""} onChange={(e) => selectPros(e.target.value)}><option value="">Alege dosarul prosumator...</option>{clientPros.map((p) => <option key={p.id} value={p.id}>{p.number} · POD {p.pod || "necompletat"} · {p.address || p.client_name}</option>)}</select></label>
              : selectedPros
                ? <>Dosar prosumator asociat automat după client: <strong style={{ color: "var(--ink)" }}>{selectedPros.number} · {selectedPros.client_name}</strong></>
                : <>Nu există dosar de prosumator asociat pentru acest client. Creează întâi dosarul prosumator pentru preluarea automată a schemei și echipamentelor.</>}
          </div>
          {selectedPros && <div className="sm:col-span-2 rounded-lg border px-3 py-2 text-xs" style={{ borderColor: "var(--line)", color: "var(--muted)" }} data-testid="atr-linked-equipment">
            <strong className="text-sm" style={{ color: "var(--ink)" }}>Date tehnice preluate din dosarul prosumator</strong>
            <div className="mt-1">POD {selectedPros.pod || "—"} · {selectedPros.operator || "operator necompletat"} · Putere invertor {selectedPros.inverter_kw || selectedPros.cef?.total_kw || "—"} kW · Evacuare {selectedPros.power || selectedPros.cef?.total_export_kw || "—"} kW</div>
            {(selectedPros.cef?.inverters || []).length > 0 && <ul className="mt-1 list-disc pl-4">{selectedPros.cef.inverters.map((inv, i) => <li key={inv.id || i}>{inv.brand_model || `Invertor ${i + 1}`} — {inv.p_nom_kw || "putere nespecificată"} kW; panou {inv.panel_model || "nespecificat"}{inv.strings?.length ? `; stringuri ${inv.strings.map((s) => s.panels).filter(Boolean).join(" + ")}` : ""}{(inv.battery?.model || inv.battery?.brand_model) ? `; baterie ${inv.battery.model || inv.battery.brand_model}` : ""}</li>)}</ul>}
          </div>}
          <div className="den-field"><label>Putere instalată centrală (kW)</label><input className="den-input" value={form.pv_kw || ""} onChange={(e) => setVal("pv_kw", e.target.value)} data-testid="atr-pv-kw" /></div>
          <div className="den-field"><label>Putere max. evacuată (kW)</label><input className="den-input" value={form.p_evac_kw || ""} onChange={(e) => setVal("p_evac_kw", e.target.value)} data-testid="atr-evac-kw" /></div>
          <div className="den-field"><label>Data PIF centrală</label><input type="date" className="den-input" value={form.pif_date || ""} onChange={(e) => setVal("pif_date", e.target.value)} /></div>
        </>}
        <div className="den-field"><label>Factor de putere mediu (cos φ)</label><input className="den-input" value={form.cos_phi || ""} onChange={(e) => setVal("cos_phi", e.target.value)} /></div>
        <div className="den-field"><label>Cel mai mare motor (kW)</label><input className="den-input" value={form.motor_kw || ""} onChange={(e) => setVal("motor_kw", e.target.value)} /></div>
      </div>
      <div className="mt-4 text-xs font-bold">Lista receptoarelor</div>
      {recs.map((r, i) => <div key={i} className="grid grid-cols-[1fr_90px_1fr_24px] gap-2 mt-1" data-testid={`atr-rec-${i}`}>
        <input className="den-input" placeholder="Denumire" value={r.name || ""} onChange={(e) => setR(i, "name", e.target.value)} />
        <input className="den-input" placeholder="kW" value={r.kw || ""} onChange={(e) => setR(i, "kw", e.target.value)} />
        <input className="den-input" placeholder="Observații / regim" value={r.notes || ""} onChange={(e) => setR(i, "notes", e.target.value)} />
        <button type="button" onClick={() => setVal("receptors", recs.filter((_, j) => j !== i))}><Trash2 size={13} style={{ color: "#b33333" }} /></button></div>)}
      <button type="button" className="text-xs font-bold mt-2 inline-flex items-center gap-1" style={{ color: "var(--blue)" }} onClick={() => setVal("receptors", [...recs, {}])} data-testid="atr-add-rec"><Plus size={12} />Adaugă receptor</button>
        </div>
      </details>
      <div className="mt-4 flex items-center gap-2 text-xs font-bold" data-testid="atr-checklist-status">
        {missing.length ? <><AlertTriangle size={14} style={{ color: "#8a5a00" }} />Lipsesc {missing.length} documente obligatorii</> : <><CheckCircle2 size={14} style={{ color: "#166534" }} />Toate documentele obligatorii sunt atașate</>}</div>
      <details className="mt-2 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-documents-details">
        <summary className="cursor-pointer text-sm font-semibold">Documente anexate · {missing.length} obligatorii lipsă</summary>
        {operatorSource?.id === "deer" && <p className="text-xs mb-2"><a href={AUTH_DECLARATION_URL} target="_blank" rel="noopener noreferrer" className="underline font-semibold">Descarcă declarația oficială de autenticitate DEER ↗</a></p>}
        {need.includes("fise") && <p className="mb-2 text-xs" style={{ color: "var(--muted)" }}>Fișele tehnice sunt marcate automat complete numai când fiecare echipament selectat are în catalog atât fișa tehnică, cât și declarația de conformitate. Fișierele adăugate manual rămân incluse în PDF, dar trebuie verificate pentru fiecare model.</p>}
        {need.includes("fise") && catalogEvidenceMissing.length > 0 && <ul className="mb-2 list-disc pl-5 text-xs text-amber-800" data-testid="atr-catalog-evidence-missing">{catalogEvidenceMissing.map((item) => <li key={item}>{item}</li>)}</ul>}
        <div className="mt-3">{DOCS.map(([k, l, r]) => <Slot key={k} k={k} testPrefix="atr" label={`${l}${need.includes(k) ? " *" : r ? " (nu e cazul)" : ""}`} files={att[k] || []} auto={autoAvailable(k)} autoLabel={AUTO[k]} onChange={(v) => setVal("attachments", { ...att, [k]: v })} />)}</div>
      </details>
      <div className="flex flex-wrap gap-2 mt-4">
        {id ? <>
          <Btn type="button" variant="secondary" onClick={() => openAuthenticatedFile(pdf(id, 0))} data-testid="atr-cerere-pdf">Precompletare ATR (PDF)</Btn>
          <Btn type="button" onClick={() => downloadAuthenticatedFile(`/atr/${encodeURIComponent(id)}/package.zip`, "Pachet_ATR_anexe.zip")} data-testid="atr-package-zip" title="Cererea ATR și anexele disponibile pentru procedura și operatorul selectat">Cerere + anexe (ZIP)</Btn>
          <Btn type="button" onClick={() => openAuthenticatedFile(pdf(id, 1))} data-testid="atr-full-pdf">Dosar ATR — PDF unic</Btn>
          <span className="text-[11px] self-center" style={{ color: "var(--muted)" }}>Salvați modificările înainte de generare.</span>
        </> : <span className="text-xs" style={{ color: "var(--muted)" }}>Salvați cererea pentru a genera documentele.</span>}
      </div>
      {id && <details className="mt-3 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-tracking-details"><summary className="cursor-pointer text-sm font-semibold">Stadiu și termene de urmărire</summary><div className="mt-3"><AtrTracking id={id} operator={form.operator} /></div></details>}
    </div>
  );
}
