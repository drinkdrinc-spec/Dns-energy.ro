import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileDown } from "lucide-react";
import { api, API } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";

const ST = ["în așteptare", "aprobat", "respins", "expirat"];

function Row({ o, onDone }) {
  const [st, setSt] = useState(o.status || "în așteptare");
  const [notes, setNotes] = useState(o.admin_notes || "");
  const [vd, setVd] = useState(o.visa_date || "");
  const visa = async (confirmed) => { try { await api.post(`/admin/operators/${o.tenant}/visa`, { visa_date: vd, confirmed }); toast.success(confirmed ? "Data vizării confirmată" : "Confirmare retrasă"); onDone(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  const decide = async () => { try { await api.post(`/admin/operators/${o.tenant}/decision`, { status: st, notes }); toast.success("Decizie salvată"); onDone(); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); } };
  return (
    <tr className="border-t align-top" style={{ borderColor: "var(--line)" }} data-testid={`operator-row-${o.cui}`}>
      <td className="py-2"><b>{o.company}</b><div className="text-xs">CUI {o.cui} · {o.email}</div></td>
      <td className="text-xs">nr. {o.attest_no}<br />{(o.attest_types || []).join(", ")} {o.attest_other || ""}<br />valabil: {o.attest_valid || "—"}<br />titular: {o.holder_name}</td>
      <td className="text-xs">{o.has_document ? <a href={`${API}/admin/operators/${o.tenant}/document?auth=${localStorage.getItem("den_token")}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-bold" style={{ color: "var(--blue)" }} data-testid={`operator-doc-${o.cui}`}><FileDown size={13} /> {o.doc_name}</a> : "lipsă"}</td>
      <td className="text-xs" data-testid={`operator-visa-${o.cui}`}><input type="date" className="den-input !py-1 !text-xs" value={vd} onChange={(e) => setVd(e.target.value)} data-testid={`operator-visa-date-${o.cui}`} />
        <div className="mt-1">{o.visa_confirmed ? <b style={{ color: "#166534" }}>confirmată</b> : o.visa_date ? <b style={{ color: "#8a5a00" }}>de confirmat</b> : "—"}{o.visa_reminded_at && <> · memento trimis {new Date(o.visa_reminded_at).toLocaleDateString("ro-RO")}</>}</div>
        <button className="font-bold mt-1" style={{ color: "var(--blue)" }} onClick={() => visa(!o.visa_confirmed || vd !== o.visa_date)} data-testid={`operator-visa-confirm-${o.cui}`}>{o.visa_confirmed && vd === o.visa_date ? "Retrage confirmarea" : "Confirmă data"}</button></td>
      <td className="text-xs">{o.verified_at ? new Date(o.verified_at).toLocaleDateString("ro-RO") : "—"}<div>{o.verified_by}</div></td>
      <td><select className="den-input !py-1 !text-xs" value={st} onChange={(e) => setSt(e.target.value)} data-testid={`operator-status-${o.cui}`}>{ST.map((s) => <option key={s}>{s}</option>)}</select>
        <textarea className="den-input !text-xs mt-1" rows={2} placeholder="Observații (obligatoriu la respingere)" value={notes} onChange={(e) => setNotes(e.target.value)} data-testid={`operator-notes-${o.cui}`} />
        <Btn className="mt-1" onClick={decide} data-testid={`operator-decide-${o.cui}`}>Salvează decizia</Btn></td>
    </tr>
  );
}

export default function AdminOperators() {
  const [list, setList] = useState([]);
  const [cfg, setCfg] = useState(null);
  const load = () => { api.get("/admin/operators").then((r) => setList(r.data)); api.get("/admin/attest-config").then((r) => setCfg(r.data)); };
  useEffect(() => { load(); }, []);
  const [busyT, setBusyT] = useState(false);
  const toggle = async (v) => { setBusyT(true); try { const { data } = await api.put("/admin/attest-config", { attest_block_existing: v }); setCfg(data); toast.success("Regulă actualizată"); } catch (e) { toast.error(e.response?.data?.detail || "Eroare"); api.get("/admin/attest-config").then((r) => setCfg(r.data)); } finally { setBusyT(false); } };
  return (
    <div data-testid="admin-operators-page">
      <PageHeader eyebrow="Administrare platformă" title="Operatori economici și atestate ANRE" sub="Verificare manuală: documentul încărcat nu este dovadă suficientă până la verificarea în registrul ANRE." />
      {cfg && <label className="den-panel mb-4 flex items-center gap-2 text-sm" data-testid="attest-block-existing"><input type="checkbox" checked={cfg.attest_block_existing} disabled={busyT} onChange={(e) => toggle(e.target.checked)} data-testid="attest-block-toggle" />
        Blochează imediat și conturile existente (create înainte de {cfg.attest_cutoff ? new Date(cfg.attest_cutoff).toLocaleDateString("ro-RO") : "—"}) fără atestat aprobat. Dezactivat = își păstrează accesul până la verificare.</label>}
      <div className="den-panel overflow-x-auto">
        <table className="w-full text-sm"><thead><tr className="text-left text-xs" style={{ color: "var(--muted)" }}><th className="py-2">Firmă</th><th>Atestat</th><th>Document</th><th>Vizare periodică</th><th>Verificat</th><th>Status și observații</th></tr></thead>
          <tbody>{list.map((o) => <Row key={o.tenant} o={o} onDone={load} />)}
            {!list.length && <tr><td colSpan={6} className="py-6 text-center" style={{ color: "var(--muted)" }}>Nicio solicitare.</td></tr>}</tbody></table>
      </div>
    </div>
  );
}
