import { useEffect, useState } from "react";
import { api, API } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Slot } from "@/components/dossier/PowerDossier";
import { Plus, Trash2, CheckCircle2, AlertTriangle } from "lucide-react";
import { FormAlert } from "@/components/dossier/FormAlert";
import { AtrTracking } from "@/components/dossier/AtrTracking";

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
const pdf = (id, full) => `${API}/atr/${id}/pdf?full=${full}&auth=${localStorage.getItem("den_token")}`;

export function AtrDossier({ id, form, setVal }) {
  const [pros, setPros] = useState([]);
  const [officialForms, setOfficialForms] = useState([]);
  useEffect(() => { api.get("/data/prosumator").then((r) => setPros(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    if (!form.operator) { setOfficialForms([]); return; }
    api.get(`/forms/operator-links?operator=${encodeURIComponent(form.operator)}&scope=atr`)
      .then((r) => setOfficialForms(r.data || []))
      .catch(() => setOfficialForms([]));
  }, [form.operator]);
  const operatorSource = OFFICIAL_SOURCES.find((source) => source.match.test(String(form.operator || ""))); 
  const selectedDeerForm = DEER_FORMS.find((f) => f.value === form.deer_case) || null;
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
  const has = (k) => (att[k] || []).length > 0 || (!!form.pros_id && prod && AUTO[k]);
  const missing = need.filter((k) => !has(k));
  const setR = (i, k, v) => setVal("receptors", recs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="sm:col-span-2 den-panel mt-3" data-testid="atr-dossier">
      <FormAlert operator={form.operator} scope="atr" />
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
      </details>
      <details className="mb-3 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-technical-questionnaire">
        <summary className="cursor-pointer text-sm font-semibold">Chestionar tehnic ATR și lista receptoarelor</summary>
        <div className="mt-3">
      <h3 className="text-[11px] font-bold uppercase tracking-wider mb-3" style={{ color: "var(--blue)" }}>Cerere și chestionar ATR — {prod ? "loc de consum și de producere (peste 27 kW)" : "loc de consum"}</h3>
      <div className="grid sm:grid-cols-2 gap-3">
        {prod && <>
          <div className="den-field"><label>Dosar de prosumator / CEF asociat (date PV, schemă, fișe)</label><select className="den-input" value={form.pros_id || ""} onChange={(e) => setVal("pros_id", e.target.value)} data-testid="atr-pros">
            <option value="">— fără —</option>{pros.map((p) => <option key={p.id} value={p.id}>{p.number} · {p.client_name}</option>)}</select></div>
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
        {operatorSource?.id === "deer" && <p className="text-xs mb-2"><a href="https://www.distributie-energie.ro/wp-content/uploads/2024/02/Declaratie-autenticitate-date-racordare.doc" target="_blank" rel="noopener noreferrer" className="underline font-semibold">Descarcă declarația oficială de autenticitate DEER ↗</a></p>}
        <div className="mt-3">{DOCS.map(([k, l, r]) => <Slot key={k} k={k} testPrefix="atr" label={`${l}${need.includes(k) ? " *" : r ? " (nu e cazul)" : ""}`} files={att[k] || []} auto={!!form.pros_id && prod && AUTO[k]} autoLabel={AUTO[k]} onChange={(v) => setVal("attachments", { ...att, [k]: v })} />)}</div>
      </details>
      <div className="flex flex-wrap gap-2 mt-4">
        {id ? <>
          <a href={pdf(id, 0)} target="_blank" rel="noopener noreferrer" data-testid="atr-cerere-pdf"><Btn type="button" variant="secondary">Cererea ATR completată (PDF)</Btn></a>
          <a href={pdf(id, 1)} target="_blank" rel="noopener noreferrer" data-testid="atr-full-pdf"><Btn type="button">Dosar ATR — PDF unic</Btn></a>
          <span className="text-[11px] self-center" style={{ color: "var(--muted)" }}>Salvați modificările înainte de generare.</span>
        </> : <span className="text-xs" style={{ color: "var(--muted)" }}>Salvați cererea pentru a genera documentele.</span>}
      </div>
      {id && <details className="mt-3 rounded-lg border px-3 py-2" style={{ borderColor: "var(--line)" }} data-testid="atr-tracking-details"><summary className="cursor-pointer text-sm font-semibold">Stadiu și termene de urmărire</summary><div className="mt-3"><AtrTracking id={id} operator={form.operator} /></div></details>}
    </div>
  );
}
