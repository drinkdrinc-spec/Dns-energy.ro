import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileDown } from "lucide-react";
import { api, API } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { ContractSign, SignedLink } from "@/components/offers/ContractSign";

const ST = ["Generat", "Trimis la semnare", "Semnat", "În execuție", "Finalizat", "Reziliat"];
const money = (v, c) => `${(v || 0).toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${c === "EUR" ? "€" : "lei"}`;

function Template() {
  const [t, setT] = useState(null);
  const [arts, setArts] = useState(null);
  const load = () => api.get("/contract-template").then((r) => { setT(r.data); setArts((r.data.pending || r.data.active).articles); });
  useEffect(() => { let alive = true; api.get("/contract-template").then((r) => { if (alive) { setT(r.data); setArts((r.data.pending || r.data.active).articles); } }); return () => { alive = false; }; }, []);
  if (!t) return null;
  const act = async (fn, msg) => { try { await fn(); toast.success(msg); load(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  return (
    <div className="den-panel mt-4" data-testid="contract-template">
      <h3 className="font-bold">Clauzele contractului</h3>
      <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Activ: versiunea {t.active.version}{t.active.source ? ` (${t.active.source})` : ""}. Modificările intră în vigoare doar după aprobare.
        Variabile disponibile: {t.placeholders.map((p) => `{${p}}`).join(", ")}</p>
      {t.pending && <div className="text-xs font-bold mt-2" style={{ color: "#8a5a00" }} data-testid="template-pending">Versiunea {t.pending.version} așteaptă aprobarea.</div>}
      <div className="space-y-2 mt-3 max-h-[60vh] overflow-y-auto">{arts.map((a, i) => (
        <div key={i}><input className="den-input !text-xs font-bold" value={a.title} onChange={(e) => setArts(arts.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} data-testid={`tpl-title-${i}`} />
          <textarea className="den-input !text-xs mt-1" rows={5} value={a.text} onChange={(e) => setArts(arts.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} data-testid={`tpl-text-${i}`} /></div>))}</div>
      <div className="flex flex-wrap gap-2 mt-3">
        <Btn variant="secondary" onClick={() => act(() => api.put("/contract-template", { articles: arts }), "Propunere salvată — necesită aprobare")} data-testid="tpl-save">Salvează propunerea</Btn>
        {t.pending && <Btn onClick={() => window.confirm("Aprobi noile clauze pentru contractele generate de acum înainte?") && act(() => api.post("/contract-template/approve", { approve: true }), "Clauze aprobate")} data-testid="tpl-approve">Aprobă</Btn>}
        {t.pending && <Btn variant="secondary" onClick={() => act(() => api.post("/contract-template/approve", { approve: false }), "Propunere respinsă")} data-testid="tpl-reject">Respinge</Btn>}
      </div>
    </div>
  );
}

export default function Contracts() {
  const [list, setList] = useState([]);
  const [tpl, setTpl] = useState(false);
  const [sign, setSign] = useState(null);
  const load = () => api.get("/contracts").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);
  const status = async (id, st) => { try { await api.post(`/contracts/${id}/status`, { status: st }); toast.success("Status actualizat"); load(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  return (
    <div data-testid="contracts-page">
      <PageHeader eyebrow="Comercial" title="Contracte" sub="Contracte generate din oferte acceptate, cu Anexa 1 (oferta comercială) și Anexa 2 (garanții)."
        action={<Btn variant="secondary" onClick={() => setTpl(!tpl)} data-testid="tpl-toggle">Clauze contract</Btn>} />
      <div className="den-panel overflow-x-auto">
        <table className="w-full text-sm" data-testid="contracts-table">
          <thead><tr className="text-left text-xs" style={{ color: "var(--muted)" }}><th className="py-2">Nr.</th><th>Beneficiar</th><th>Data</th><th>Ofertă</th><th>Valoare (fără TVA)</th><th>Plată</th><th>Status</th><th /></tr></thead>
          <tbody>{list.map((c) => (
            <tr key={c.id} className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`contract-row-${c.number}`}>
              <td className="py-2 font-bold">{c.number}</td><td>{c.beneficiary}</td><td>{new Date(c.date).toLocaleDateString("ro-RO")}</td>
              <td className="text-xs">nr. {c.offer_number} v{c.offer_version}{c.offer_changed && <div style={{ color: "#8a5a00" }}>oferta modificată ulterior</div>}</td>
              <td>{money(c.net, c.currency)}</td><td className="text-xs">{c.payment_mode === "avans" ? "cu avans" : "integrală"}</td>
              <td><select className="den-input !py-1 !text-xs" value={c.status} onChange={(e) => status(c.id, e.target.value)} data-testid={`contract-status-${c.number}`}>{ST.map((s) => <option key={s}>{s}</option>)}</select></td>
              <td className="flex items-center gap-2 py-2"><a href={`${API}/contracts/${c.id}/pdf?auth=${localStorage.getItem("den_token")}`} target="_blank" rel="noopener noreferrer" data-testid={`contract-pdf-${c.number}`}><FileDown size={16} style={{ color: "var(--blue)" }} /></a>
                <SignedLink c={c} />
                {c.status !== "Semnat" && !c.signed && <button className="text-xs font-bold" style={{ color: "var(--blue)" }} onClick={() => setSign(c)} data-testid={`contract-sign-${c.number}`}>Semnare online</button>}</td>
            </tr>))}
            {!list.length && <tr><td colSpan={8} className="py-6 text-center text-sm" style={{ color: "var(--muted)" }}>Niciun contract încă — acceptă o ofertă și apasă „Generează contract”.</td></tr>}</tbody>
        </table>
      </div>
      {tpl && <Template />}
      {sign && <ContractSign c={sign} open={!!sign} onClose={() => setSign(null)} onDone={load} />}
    </div>
  );
}
