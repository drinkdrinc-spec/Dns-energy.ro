import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { OfferEditor } from "@/components/offers/OfferEditor";

const money = (v, c) => `${(v || 0).toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${c === "EUR" ? "€" : "lei"}`;

function Numbering() {
  const [n, setN] = useState(null);
  useEffect(() => { api.get("/offers/numbering").then((r) => setN(r.data)); }, []);
  if (!n) return null;
  const save = async () => { try { const { data } = await api.put("/offers/numbering", n); setN(data); toast.success("Numerotare actualizată"); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  return (
    <div className="flex flex-wrap items-end gap-2 text-xs" data-testid="numbering-panel">
      <div className="den-field"><label>Următoarea ofertă nr.</label><input className="den-input" style={{ width: 110 }} value={n.offer_next} onChange={(e) => setN({ ...n, offer_next: e.target.value })} data-testid="numbering-offer" /></div>
      <div className="den-field"><label>Următorul contract nr.</label><input className="den-input" style={{ width: 110 }} value={n.contract_next} onChange={(e) => setN({ ...n, contract_next: e.target.value })} data-testid="numbering-contract" /></div>
      <Btn variant="secondary" onClick={save} data-testid="numbering-save">Salvează numerotarea</Btn>
    </div>
  );
}

export default function Offers() {
  const [list, setList] = useState([]);
  const [open, setOpen] = useState(null);
  const load = () => api.get("/offers").then((r) => setList(r.data));
  useEffect(() => { if (!open) load(); }, [open]);
  const create = async () => { const { data } = await api.post("/offers", { items: [] }); setOpen(data.id); };
  const [pros, setPros] = useState(null);
  const fromDossier = async (pid) => { try { const { data } = await api.post("/offers/from-dossier", { pros_id: pid }); toast.success(`Ofertă nr. ${data.number} creată din dosar — completează prețurile`); setOpen(data.id); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  if (open) return <OfferEditor id={open} onBack={() => setOpen(null)} onOpen={setOpen} />;
  return (
    <div data-testid="offers-page">
      <PageHeader eyebrow="Comercial" title="Oferte de preț" sub="Creează, duplică și exportă oferte; după acceptare generezi contractul cu anexele." action={<Btn onClick={create} data-testid="offer-new"><Plus size={14} /> Ofertă nouă</Btn>} />
      <div className="den-panel mb-3"><Numbering /></div>
      <div className="den-panel mb-3 flex flex-wrap items-end gap-2" data-testid="offer-from-dossier">
        <div className="den-field min-w-[280px]"><label>Ofertă din dosarul de prosumator (preia clientul și echipamentele)</label>
          <select className="den-input" defaultValue="" onFocus={() => !pros && api.get("/data/prosumator").then((r) => setPros(r.data)).catch(() => setPros([]))} onChange={(e) => e.target.value && fromDossier(e.target.value)} data-testid="offer-from-dossier-select">
            <option value="">Alege dosarul...</option>{(pros || []).map((p) => <option key={p.id} value={p.id}>{p.client_name || "fără nume"} — {p.address || p.id.slice(0, 6)}</option>)}</select></div>
      </div>
      <div className="den-panel overflow-x-auto">
        <table className="w-full text-sm" data-testid="offers-table">
          <thead><tr className="text-left text-xs" style={{ color: "var(--muted)" }}><th className="py-2">Nr.</th><th>Beneficiar</th><th>Data emiterii</th><th>Valoare (fără TVA)</th><th>Total cu TVA</th><th>Status</th><th>Contract</th></tr></thead>
          <tbody>{list.map((o) => (
            <tr key={o.id} className="border-t cursor-pointer hover:bg-slate-50" style={{ borderColor: "var(--line)" }} onClick={() => setOpen(o.id)} data-testid={`offer-row-${o.number}`}>
              <td className="py-2 font-bold">{o.number}</td><td>{o.beneficiary || "—"}</td><td>{o.date ? new Date(o.date).toLocaleDateString("ro-RO") : ""}</td>
              <td>{money(o.net, o.currency)}</td><td>{money(o.gross, o.currency)}</td><td><span className="text-xs rounded-full px-2 py-0.5 bg-slate-100">{o.status}</span></td>
              <td className="text-xs">{o.contract_id ? (o.contract_outdated ? "da (ofertă modificată)" : "da") : "—"}</td>
            </tr>))}
            {!list.length && <tr><td colSpan={7} className="py-6 text-center text-sm" style={{ color: "var(--muted)" }}>Nicio ofertă încă.</td></tr>}</tbody>
        </table>
      </div>
    </div>
  );
}
