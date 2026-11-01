import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import { AnreEditor } from "@/components/anre/AnreEditor";
import { AnreTemplates } from "@/components/anre/AnreTemplates";

const TYPES = { nou: "Atestat nou", b_c1a: "Extindere B → C1A", b_c2a: "Extindere B → C2A", modificare: "Modificarea datelor atestatului", vizare: "Vizare periodică", altele: "Altă solicitare" };

export default function AnreDossiers() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [open, setOpen] = useState(null);
  const fromMail = new URLSearchParams(window.location.search).get("tip") === "vizare";
  const [kind, setKind] = useState(fromMail ? "vizare" : "nou");
  const load = () => api.get("/anre/dossiers").then((r) => setList(r.data));
  useEffect(() => { if (!open) load(); }, [open]);
  const create = async (mode) => { try { const { data } = await api.post("/anre/dossiers", { kind, mode }); toast.success(mode === "intern" ? "Dosar ANRE intern creat — fără comandă sau proformă." : `Comandă creată — proforma ${data.invoice_number} a fost emisă.`); setOpen(data.id); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  if (open) return <AnreEditor id={open} platform={!!user?.platform} onBack={() => setOpen(null)} />;
  return (
    <div data-testid="anre-page">
      <PageHeader eyebrow="Documentație ANRE" title="Dosare ANRE" sub="Pregătește intern dosarul, verifică opisul și documentele. Dacă dorești serviciul de pregătire D-ENERGY, îl poți comanda separat; tarifele ANRE se plătesc separat." />
      {user?.platform && <AnreTemplates />}
      {fromMail && kind === "vizare" && <div className="den-panel mb-2 text-sm" style={{ background: "#eef4ff" }} data-testid="anre-visa-banner">Tipul „Vizare periodică” a fost preselectat din memento. Alege pregătirea internă sau comandă serviciul extern.</div>}
      <div className="den-panel mb-4 flex flex-wrap items-end gap-2">
        <div className="den-field"><label>Tipul solicitării</label><select className="den-input" value={kind} onChange={(e) => setKind(e.target.value)} data-testid="anre-kind">{Object.entries(TYPES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
        <Btn onClick={() => create("intern")} data-testid="anre-new">Pregătește dosarul intern</Btn>
        <Btn variant="secondary" onClick={() => create("serviciu")} data-testid="anre-order-service">Comandă serviciul D-ENERGY · 3.200 lei + TVA</Btn>
        <p className="text-[11px] w-full" style={{ color: "var(--muted)" }}>Dosarul intern nu emite proformă. Comanda serviciului este separată și emite proformă; plata se confirmă de administrator. Eligibilitatea se verifică pe baza documentelor reale privind personalul autorizat și dotările.</p>
      </div>
      <div className="den-panel overflow-x-auto"><table className="w-full text-sm" data-testid="anre-table">
        <thead><tr className="text-left text-xs" style={{ color: "var(--muted)" }}><th className="py-2">Firmă</th><th>Solicitare</th><th>Plată</th><th>Atestat operator</th><th>Progres</th><th>Lipsuri</th><th>Verificare finală</th><th>Status</th></tr></thead>
        <tbody>{list.map((d) => (
          <tr key={d.id} className="border-t cursor-pointer hover:bg-slate-50" style={{ borderColor: "var(--line)" }} onClick={() => setOpen(d.id)} data-testid={`anre-row-${d.id}`}>
            <td className="py-2"><b>{d.company || "—"}</b><div className="text-xs">{d.cui} {d.owner_email && `· ${d.owner_email}`} · ref. {d.id.slice(0, 8)}</div></td><td>{TYPES[d.kind]}</td><td>{d.payment_status}</td><td className="text-xs">{d.attest_status}</td>
            <td>{d.progress}%</td><td>{d.missing}</td><td className="text-xs">{d.final_check ? (d.final_check.ok ? "fără blocaje" : "cu lipsuri") : "—"}</td><td>{d.status}</td></tr>))}
          {!list.length && <tr><td colSpan={8} className="py-6 text-center" style={{ color: "var(--muted)" }}>Niciun dosar ANRE.</td></tr>}</tbody></table></div>
    </div>
  );
}
