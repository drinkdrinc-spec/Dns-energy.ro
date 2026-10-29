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
  ["imp", "Împuternicire reprezentant / proiectant", ""], ["memoriu", "Memoriu tehnic — date tehnice și energetice", ""],
  ["schema", "Schemă monofilară instalație de producere + racordare", "prod"], ["fise", "Fișe tehnice / certificate invertoare", "prod"], ["atr_prev", "ATR / certificat de racordare anterior", "spor"]];
const OFFICIAL_SOURCES = [
  { id: "deer", match: /deer|distribuție energie electrică|distributie energie electrica/i, name: "DEER — formulare și documente de racordare", docs: "https://www.distributie-energie.ro/racordare-la-retea-2/", portal: "https://avize.distributie-energie.ro/" },
  { id: "delgaz", match: /delgaz/i, name: "Delgaz Grid — documente pentru prosumatori", docs: "https://delgaz.ro/energie-electrica/prosumatori", portal: "https://delgaz.ro/" },
  { id: "oltenia", match: /oltenia|deo connect|distribuție oltenia|distributie oltenia/i, name: "Distribuție Oltenia — formulare pentru prosumatori", docs: "https://www.distributieoltenia.ro/ro/informatii-utile/prosumatori/formularele-necesare-pentru-a-deveni-prosumator.html", portal: "https://portal.distributieoltenia.ro/" },
  { id: "rer", match: /rețele electrice|retele electrice|e-distribu/i, name: "Rețele Electrice România — cereri și documente", docs: "https://www.reteleelectrice.ro/cereri-documente/", portal: "https://www.reteleelectrice.ro/" },
];
const DEER_ANNEXES = {
  anexa1: { title: "Cerere — loc de consum existent cu spor de putere (Anexa 1)", url: "https://www.distributie-energie.ro/wp-content/uploads/2023/12/4.-Loc-consum-si_sau-producere-existent-Spor-Putere_Anexa-nr-1.docx", note: "Se selectează când OD solicită procedura de spor de putere; verifică formularul curent și indicațiile OD." },
  anexa2: { title: "Notificare — loc de consum existent (Anexa 2)", url: "https://www.distributie-energie.ro/wp-content/uploads/2023/12/2.-Loc-de-consum-existent_Anexa-nr-2.docx", note: "Se folosește numai dacă situația și cerințele OD permit notificarea pentru loc existent, fără procedură de spor de putere." },
};
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
  const annexChoice = form.annex_choice || (String(form.request_type || "").toLowerCase().includes("spor") ? "anexa1" : "anexa2");
  const annexInfo = DEER_ANNEXES[annexChoice];
  const att = form.attachments || {};
  const recs = form.receptors || [];
  const prod = String(form.kind || "").includes("producere");
  const isNew = !form.request_type || String(form.request_type).startsWith("utilizator nou");
  const need = DOCS.filter(([, , r]) => r === "req" || (r === "prod" && prod) || (r === "new" && isNew) || (r === "spor" && !isNew)).map(([k]) => k);
  const has = (k) => (att[k] || []).length > 0 || (!!form.pros_id && prod && AUTO[k]);
  const missing = need.filter((k) => !has(k));
  const setR = (i, k, v) => setVal("receptors", recs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="sm:col-span-2 den-panel mt-3" data-testid="atr-dossier">
      <FormAlert operator={form.operator} scope="atr" />
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
      {operatorSource?.id === "deer" && <div className="rounded-xl border p-4 mb-4" style={{ borderColor: "var(--line)" }} data-testid="atr-annex-selector">
        <div className="font-bold mb-1">Anexă pentru dosarul existent — DEER</div>
        <div className="text-xs mb-3" style={{ color: "var(--muted)" }}>Schimbi numai anexa. Datele clientului, echipamentele, documentele încărcate și restul dosarului se păstrează.</div>
        <label className="block text-xs font-semibold mb-1" htmlFor="atr-annex-choice">Anexa cerută de operator</label>
        <select id="atr-annex-choice" className="den-input w-full" value={annexChoice} onChange={(e) => setVal("annex_choice", e.target.value)}>
          <option value="anexa2">Anexa 2 — Notificare loc de consum existent</option>
          <option value="anexa1">Anexa 1 — Cerere pentru loc existent cu spor de putere</option>
        </select>
        <div className="text-xs mt-2" style={{ color: "var(--muted)" }}>{annexInfo.note}</div>
        <a href={annexInfo.url} target="_blank" rel="noopener noreferrer" className="inline-flex underline font-semibold text-sm mt-2">Deschide formularul oficial selectat ↗</a>
        <div className="text-xs mt-2" style={{ color: "var(--muted)" }}>Alegerea se salvează în datele cererii când salvezi dosarul. Formularul oficial trebuie completat cu datele existente înainte de export; confirmă cu OD ce anexă se aplică.</div>
      </div>}
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
      <div className="mt-4 flex items-center gap-2 text-xs font-bold" data-testid="atr-checklist-status">
        {missing.length ? <><AlertTriangle size={14} style={{ color: "#8a5a00" }} />Lipsesc {missing.length} documente obligatorii</> : <><CheckCircle2 size={14} style={{ color: "#166534" }} />Toate documentele obligatorii sunt atașate</>}</div>
      {DOCS.map(([k, l, r]) => <Slot key={k} k={k} testPrefix="atr" label={`${l}${need.includes(k) ? " *" : r ? " (nu e cazul)" : ""}`} files={att[k] || []} auto={!!form.pros_id && prod && AUTO[k]} autoLabel={AUTO[k]} onChange={(v) => setVal("attachments", { ...att, [k]: v })} />)}
      <div className="flex flex-wrap gap-2 mt-4">
        {id ? <>
          <a href={pdf(id, 0)} target="_blank" rel="noopener noreferrer" data-testid="atr-cerere-pdf"><Btn type="button" variant="secondary">Cererea ATR completată (PDF)</Btn></a>
          <a href={pdf(id, 1)} target="_blank" rel="noopener noreferrer" data-testid="atr-full-pdf"><Btn type="button">Dosar ATR — PDF unic</Btn></a>
          <span className="text-[11px] self-center" style={{ color: "var(--muted)" }}>Salvați modificările înainte de generare.</span>
        </> : <span className="text-xs" style={{ color: "var(--muted)" }}>Salvați cererea pentru a genera documentele.</span>}
      </div>
      {id && <AtrTracking id={id} operator={form.operator} />}
    </div>
  );
}
