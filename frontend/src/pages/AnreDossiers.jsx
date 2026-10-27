import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import { AnreEditor } from "@/components/anre/AnreEditor";

const TYPES = { nou: "Atestat nou", b_c1a: "Extindere B → C1A", b_c2a: "Extindere B → C2A", modificare: "Modificarea datelor atestatului", vizare: "Vizare periodică", altele: "Altă solicitare" };

export default function AnreDossiers() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [open, setOpen] = useState(null);
  const [kind, setKind] = useState("nou");
  const load = () => api.get("/anre/dossiers").then((r) => setList(r.data));
  useEffect(() => { if (!open) load(); }, [open]);
  const create = async () => { try { const { data } = await api.post("/anre/dossiers", { kind }); toast.success("Comandă creată"); setOpen(data.id); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  if (open) return <AnreEditor id={open} platform={!!user?.platform} onBack={() => setOpen(null)} />;
  return (
    <div data-testid="anre-page">
      <PageHeader eyebrow="Serviciu premium" title="Dosare ANRE" sub="Pregătirea dosarelor de atestare / actualizare a atestatelor ANRE (Ord. ANRE 134/2021): opis, cereri și anexe precompletate, documente, verificare finală și asistent AI. Serviciu D-ENERGY: 3.200 lei + TVA; tarifele ANRE se plătesc separat. Nu garantăm aprobarea ANRE." />
      <div className="den-panel mb-4 flex flex-wrap items-end gap-2">
        <div className="den-field"><label>Tipul solicitării</label><select className="den-input" value={kind} onChange={(e) => setKind(e.target.value)} data-testid="anre-kind">{Object.entries(TYPES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
        <Btn onClick={create} data-testid="anre-new">Comandă dosar (3.200 lei + TVA)</Btn>
        <p className="text-[11px] w-full" style={{ color: "var(--muted)" }}>Eligibilitatea pentru fiecare tip de atestat se verifică pe baza documentelor (personal autorizat, dotări). Plata se face prin OP și se confirmă de administrator.</p>
      </div>
      <div className="den-panel overflow-x-auto"><table className="w-full text-sm" data-testid="anre-table">
        <thead><tr className="text-left text-xs" style={{ color: "var(--muted)" }}><th className="py-2">Firmă</th><th>Solicitare</th><th>Plată</th><th>Atestat operator</th><th>Progres</th><th>Lipsuri</th><th>Verificare finală</th><th>Status</th></tr></thead>
        <tbody>{list.map((d) => (
          <tr key={d.id} className="border-t cursor-pointer hover:bg-slate-50" style={{ borderColor: "var(--line)" }} onClick={() => setOpen(d.id)} data-testid={`anre-row-${d.id}`}>
            <td className="py-2"><b>{d.company || "—"}</b><div className="text-xs">{d.cui}</div></td><td>{TYPES[d.kind]}</td><td>{d.payment_status}</td><td className="text-xs">{d.attest_status}</td>
            <td>{d.progress}%</td><td>{d.missing}</td><td className="text-xs">{d.final_check ? (d.final_check.ok ? "fără blocaje" : "cu lipsuri") : "—"}</td><td>{d.status}</td></tr>))}
          {!list.length && <tr><td colSpan={8} className="py-6 text-center" style={{ color: "var(--muted)" }}>Niciun dosar ANRE.</td></tr>}</tbody></table></div>
    </div>
  );
}
