import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, downloadAuthenticatedFile } from "@/lib/api";
import { PageHeader, Btn } from "@/components/Layout";
import { SubscriberRow } from "@/components/billing/SubscriberRow";
import { PlanEditor } from "@/components/billing/PlanEditor";
import { StatusPill } from "@/components/billing/InvoiceList";
import { lei } from "@/lib/plan";
import { Download } from "lucide-react";

function Transactions() {
  const [rows, setRows] = useState([]);
  const load = () => api.get("/admin/transactions").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const sync = async (sid) => { await api.post(`/admin/transactions/${sid}/sync`); toast.success("Stare verificată la Stripe"); load(); };
  return (
    <div className="den-panel overflow-x-auto" data-testid="tx-table"><table className="w-full text-xs">
      <thead><tr className="text-left" style={{ color: "var(--muted)" }}><th className="py-2">Data</th><th>Utilizator</th><th>Proformă</th><th>Abonament</th><th>Sumă</th><th>Mod</th><th>Stare</th><th>ID tranzacție</th><th></th></tr></thead>
      <tbody>{rows.map((t) => <tr key={t.session_id} className="border-t" style={{ borderColor: "var(--line)" }}>
        <td className="py-2 whitespace-nowrap">{new Date(t.created_at).toLocaleString("ro-RO")}</td><td>{t.user_email}</td><td>{t.invoice_number}</td><td>{t.plan} × {t.months}</td>
        <td>{lei(t.amount)}</td><td>{t.mode}</td><td><StatusPill s={t.status} /></td><td className="font-mono text-[10px]">{t.session_id.slice(0, 22)}…</td>
        <td><button className="font-bold" style={{ color: "var(--blue)" }} onClick={() => sync(t.session_id)} data-testid={`tx-sync-${t.invoice_number}`}>Verifică</button></td></tr>)}</tbody></table></div>
  );
}

const TABS = [["users", "Utilizatori"], ["plans", "Prețuri și funcții"], ["tx", "Tranzacții online"]];

export default function AdminBilling() {
  const [tab, setTab] = useState("users");
  const [subs, setSubs] = useState(null);
  const [plans, setPlans] = useState(null);
  const load = () => { api.get("/admin/subscribers").then((r) => setSubs(r.data)).catch((e) => toast.error(e.response?.data?.detail || "Eroare")); api.get("/admin/plans").then((r) => setPlans(r.data)); };
  useEffect(() => { load(); }, []);
  if (!subs || !plans) return null;
  return (
    <div>
      <PageHeader eyebrow="Administrare platformă" title="Utilizatori și abonamente" sub="Conturi abonați, date de facturare, abonamente, plăți (online și manuale), istoric și export pentru contabilitate."
        action={<Btn type="button" variant="secondary" onClick={() => downloadAuthenticatedFile("/admin/billing/export", "export-contabilitate.csv")} data-testid="billing-export"><Download size={15} />Export contabilitate (CSV)</Btn>} />
      <div className="flex gap-2 flex-wrap mb-4">{TABS.map(([k, l]) => <button key={k} onClick={() => setTab(k)} data-testid={`ab-tab-${k}`} className="rounded-full px-4 py-2 text-[12px] font-bold border"
        style={k === tab ? { background: "var(--navy)", color: "#fff", borderColor: "var(--navy)" } : { background: "#fff", borderColor: "var(--line)" }}>{l}</button>)}</div>
      {tab === "users" && <div className="den-panel" data-testid="subscribers-list">{subs.length ? subs.map((u) => <SubscriberRow key={u.id} u={u} plans={plans.plans} reload={load} />)
        : <div className="text-sm" style={{ color: "var(--muted)" }}>Nu există încă abonați înregistrați.</div>}</div>}
      {tab === "plans" && <PlanEditor data={plans} reload={load} />}
      {tab === "tx" && <Transactions />}
    </div>
  );
}
