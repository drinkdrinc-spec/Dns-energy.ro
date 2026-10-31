import { useEffect, useMemo, useState } from "react";
import { ExternalLink, ShieldCheck, Search, AlertTriangle, CheckCircle2 } from "lucide-react";
import { PageHeader, Btn } from "@/components/Layout";
import { api } from "@/lib/api";

const PORTALS = [
  { id: "deer", name: "DEER", detail: "Distribuție Energie Electrică România", url: "https://avize.distributie-energie.ro/", hints: ["5940"] },
  { id: "delgaz", name: "Delgaz Grid", detail: "Portal clienți și racordare", url: "https://delgaz.ro/login", hints: ["EMO3"] },
  { id: "oltenia", name: "Distribuție Oltenia", detail: "Portal DEO Connect", url: "https://portal.distributieoltenia.ro/", hints: [] },
  { id: "retele", name: "Rețele Electrice România", detail: "Muntenia, Banat și Dobrogea", url: "https://www.reteleelectrice.ro/", hints: ["RO001E", "RO002E", "RO005E"] },
];

// Regional links and county groups are taken from DEER's June 2025 user guide.
const DEER_REGIONS = [
  { url: "https://avize.edtn.ro/", counties: ["Cluj", "Bihor", "Maramureș", "Satu-Mare", "Bistrița-Năsăud", "Sălaj"] },
  { url: "https://avize.sdeets.ro/", counties: ["Alba", "Brașov", "Covasna", "Harghita", "Mureș", "Sibiu"] },
  { url: "https://avize.edmn.ro/", counties: ["Brăila", "Buzău", "Dâmbovița", "Galați", "Prahova", "Vrancea"] },
];
const normalizeCounty = (value) => String(value || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().replace(/^jud(?:etul)?\.?\s*/, "").replace(/\s+/g, " ").trim();
const deerRegionalPortal = (county) => {
  const key = normalizeCounty(county);
  return DEER_REGIONS.find((region) => region.counties.some((name) => normalizeCounty(name) === key))?.url || null;
};

function detectOperator(value) {
  const pod = String(value || "").trim().toUpperCase().replace(/\s+/g, "");
  if (!pod) return { pod, match: null, message: "Introdu POD-ul pentru a identifica operatorul." };
  if (/^RO001E/.test(pod) || /^RO002E/.test(pod) || /^RO005E/.test(pod)) {
    return { pod, match: "retele", message: "Prefix POD recunoscut pentru Rețele Electrice. Verifică și județul de pe factură." };
  }
  if (/^EMO3/.test(pod)) return { pod, match: "delgaz", message: "Prefix POD recunoscut pentru Delgaz Grid. Verifică operatorul de pe factură." };
  if (/^5940\d{14}$/.test(pod)) return { pod, match: "deer", message: "Format POD posibil asociat DEER. Confirmă sucursala și operatorul din factură." };
  return { pod, match: null, message: "Nu pot confirma operatorul doar din acest POD. Alege operatorul indicat pe factura de energie." };
}

function operatorId(value) {
  const operator = String(value || "").toLowerCase();
  if (/deer|distributie energie electrica/.test(operator)) return "deer";
  if (/delgaz/.test(operator)) return "delgaz";
  if (/oltenia|deo connect/.test(operator)) return "oltenia";
  if (/retele electrice|e-distribu/.test(operator)) return "retele";
  return "";
}

export default function DistributionPortals() {
  const [pros, setPros] = useState([]);
  const [prosId, setProsId] = useState("");
  const [pod, setPod] = useState("");
  const [manual, setManual] = useState("");
  const [loadFailed, setLoadFailed] = useState(false);
  useEffect(() => {
    api.get("/data/prosumator").then((r) => setPros(Array.isArray(r.data) ? r.data : [])).catch(() => setLoadFailed(true));
  }, []);
  const selectedPros = pros.find((item) => item.id === prosId) || null;
  const result = useMemo(() => detectOperator(pod), [pod]);
  const selectedId = result.match || manual || operatorId(selectedPros?.operator);
  const selected = PORTALS.find((p) => p.id === selectedId);
  const regionalUrl = selectedId === "deer" ? deerRegionalPortal(selectedPros?.county) : null;
  const portalUrl = regionalUrl || selected?.url;

  const selectPros = (id) => {
    setProsId(id);
    const item = pros.find((entry) => entry.id === id);
    if (!item) return;
    setPod(item.pod || "");
    setManual(operatorId(item.operator));
  };

  return (
    <div>
      <PageHeader eyebrow="RACORDARE" title="Portaluri distribuitori" sub="Selectează dosarul clientului sau introdu POD-ul pentru a deschide portalul distribuitorului potrivit." />
      <section className="den-panel mb-6">
        <div className="den-field mb-4">
          <label htmlFor="portal-client">Dosar de prosumator</label>
          <select id="portal-client" className="den-input w-full" value={prosId} onChange={(e) => selectPros(e.target.value)} data-testid="portal-pros-select">
            <option value="">Selectează un dosar (opțional)...</option>
            {pros.filter((item) => !/\bTEST\b/i.test([item.number, item.client_name].filter(Boolean).join(" "))).map((item) => (
              <option key={item.id} value={item.id}>{item.client_name || "Client"} — {item.address || item.pod || item.id.slice(0, 6)}</option>
            ))}
          </select>
          {loadFailed && <div className="mt-1 text-xs" style={{ color: "var(--muted)" }}>Lista dosarelor nu s-a încărcat; poți introduce POD-ul manual.</div>}
        </div>
        {selectedPros && <div className="mb-4 rounded-lg border bg-white px-3 py-2 text-xs" style={{ borderColor: "var(--line)" }} data-testid="portal-selected-dossier">
          <b>{selectedPros.client_name || "Client"}</b> · {selectedPros.operator || "operator neconfirmat"} · POD {selectedPros.pod || "necompletat"}
        </div>}
        <label className="block text-sm font-bold mb-2" htmlFor="portal-pod">POD-ul locului de consum</label>
        <div className="flex flex-col sm:flex-row gap-2">
          <input id="portal-pod" className="den-input flex-1" value={pod} onChange={(e) => setPod(e.target.value)} placeholder="Introdu POD-ul de pe factură" autoComplete="off" />
          <Btn variant="secondary" onClick={() => { setPod(""); setManual(""); setProsId(""); }}>Șterge</Btn>
        </div>
        <div className="flex gap-2 items-start mt-3 text-sm" style={{ color: result.match ? "var(--ink)" : "var(--muted)" }}>
          {result.match ? <CheckCircle2 size={18} className="shrink-0 mt-0.5" /> : <AlertTriangle size={18} className="shrink-0 mt-0.5" />}
          <span>{result.message}</span>
        </div>
        {!result.match && (
          <div className="mt-4">
            <label className="block text-sm font-bold mb-2" htmlFor="portal-manual">Selectează manual operatorul</label>
            <select id="portal-manual" className="den-input w-full" value={manual} onChange={(e) => setManual(e.target.value)}>
              <option value="">Alege operatorul de pe factură...</option>
              {PORTALS.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
        )}
        {selected && (
          <div className="mt-5 p-4 rounded-xl border" style={{ borderColor: "var(--line)", background: "var(--bg)" }}>
            <div className="font-bold">{selected.name}</div>
            <div className="text-sm mt-1" style={{ color: "var(--muted)" }}>{selected.detail}</div>
            {regionalUrl && <div className="text-xs mt-2" style={{ color: "var(--muted)" }}>Portal regional selectat după județul {selectedPros.county}.</div>}
            <a href={portalUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 mt-4 rounded-lg px-4 py-3 text-sm font-bold text-white" style={{ background: "var(--blue)" }} data-testid="portal-open-selected">
              <ExternalLink size={16} /> Deschide portalul operatorului
            </a>
            {regionalUrl && <a href={selected.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 mt-4 ml-2 rounded-lg border px-4 py-3 text-sm font-semibold" style={{ borderColor: "var(--line)" }}>Portal DEER general ↗</a>}
            <p className="text-xs mt-3" style={{ color: "var(--muted)" }}>Portalul se deschide într-o filă separată. Autentificarea rămâne în browserul folosit la conectare, atât timp cât portalul își menține sesiunea. DNS Energy nu stochează parola portalului.</p>
          </div>
        )}
      </section>
      <div className="flex items-start gap-3 text-sm p-4 rounded-xl" style={{ background: "#eef6ff", color: "#25456e" }}>
        <ShieldCheck size={20} className="shrink-0 mt-0.5" />
        <div><b>Protecția contului</b><p className="mt-1">Nu introduce parola distribuitorului în DNS Energy. Conectarea și depunerea au loc pe portalul oficial al operatorului.</p></div>
      </div>
      <h2 className="text-lg font-bold mt-7 mb-3">Portaluri oficiale</h2>
      <div className="grid md:grid-cols-2 gap-3">
        {PORTALS.map((p) => (
          <div key={p.id} className="den-panel">
            <div className="font-bold">{p.name}</div>
            <div className="text-sm mt-1 mb-4" style={{ color: "var(--muted)" }}>{p.detail}</div>
            <a href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm font-bold underline" style={{ color: "var(--blue)" }}>Deschide portalul <ExternalLink size={14} /></a>
          </div>
        ))}
      </div>
    </div>
  );
}
