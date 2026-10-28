import { useMemo, useState } from "react";
import { ExternalLink, ShieldCheck, Search, AlertTriangle, CheckCircle2 } from "lucide-react";
import { PageHeader, Btn } from "@/components/Layout";

const PORTALS = [
  { id: "deer", name: "DEER", detail: "Distribuție Energie Electrică România", url: "https://avize.distributie-energie.ro/", hints: ["5940"] },
  { id: "delgaz", name: "Delgaz Grid", detail: "Portal clienți și racordare", url: "https://delgaz.ro/login", hints: ["EMO3"] },
  { id: "oltenia", name: "Distribuție Oltenia", detail: "Portal DEO Connect", url: "https://portal.distributieoltenia.ro/", hints: [] },
  { id: "retele", name: "Rețele Electrice România", detail: "Muntenia, Banat și Dobrogea", url: "https://www.reteleelectrice.ro/", hints: ["RO001E", "RO002E", "RO005E"] },
];

function detectOperator(value) {
  const pod = String(value || "").trim().toUpperCase().replace(/\s+/g, "");
  if (!pod) return { pod, match: null, message: "Introdu POD-ul pentru a identifica operatorul." };
  if (/^RO001E/.test(pod) || /^RO002E/.test(pod) || /^RO005E/.test(pod)) {
    return { pod, match: "retele", message: "Prefix POD recunoscut pentru Rețele Electrice. Verifică și județul de pe factură." };
  }
  if (/^EMO3/.test(pod)) return { pod, match: "delgaz", message: "Prefix POD recunoscut pentru Delgaz Grid. Verifică operatorul de pe factură." };
  if (/^5940\d{14}$/.test(pod)) return { pod, match: "deer", message: "Format POD posibil asociat DEER. Sucursala și operatorul trebuie confirmați din factură." };
  return { pod, match: null, message: "Nu pot confirma operatorul doar din acest POD. Alege operatorul indicat pe factura de energie." };
}

export default function DistributionPortals() {
  const [pod, setPod] = useState("");
  const [manual, setManual] = useState("");
  const result = useMemo(() => detectOperator(pod), [pod]);
  const selected = PORTALS.find((p) => p.id === (result.match || manual));

  return (
    <div>
      <PageHeader eyebrow="RACORDARE" title="Portaluri distribuitori" sub="DNS Energy identifică portalul după POD atunci când prefixul este recunoscut. Verifică întotdeauna operatorul de pe factură înainte de depunere." />
      <section className="den-panel mb-6">
        <label className="block text-sm font-bold mb-2" htmlFor="portal-pod">POD-ul locului de consum</label>
        <div className="flex flex-col sm:flex-row gap-2">
          <input id="portal-pod" className="den-input flex-1" value={pod} onChange={(e) => setPod(e.target.value)} placeholder="Introdu POD-ul de pe factură" autoComplete="off" />
          <Btn variant="secondary" onClick={() => { setPod(""); setManual(""); }}>Șterge</Btn>
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
            <a href={selected.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 mt-4 rounded-lg px-4 py-3 text-sm font-bold text-white" style={{ background: "var(--blue)" }}>
              <ExternalLink size={16} /> Deschide portalul operatorului
            </a>
            <p className="text-xs mt-3" style={{ color: "var(--muted)" }}>Autentificarea și depunerea se finalizează în portalul oficial. DNS Energy nu stochează parola portalului și nu confirmă depunerea automat.</p>
          </div>
        )}
      </section>
      <div className="flex items-start gap-3 text-sm p-4 rounded-xl" style={{ background: "#eef6ff", color: "#25456e" }}>
        <ShieldCheck size={20} className="shrink-0 mt-0.5" />
        <div><b>Protecția contului</b><p className="mt-1">Nu introduce parola distribuitorului în DNS Energy. Până când operatorii oferă o integrare autorizată (de exemplu OAuth/API), conectarea directă și reutilizarea sesiunii nu pot fi garantate în siguranță.</p></div>
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
