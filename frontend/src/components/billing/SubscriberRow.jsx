import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatApiErrorDetail } from "@/lib/api";
import { InvoiceList } from "@/components/billing/InvoiceList";
import { Btn } from "@/components/Layout";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Eroare");
const ST = { pending: "În așteptare", active: "Activ", suspended: "Suspendat", disabled: "Dezactivat" };

function Billing({ p }) {
  if (!p?.client_type) return <span style={{ color: "#9b2c2c" }}>date de facturare lipsă</span>;
  return p.client_type === "pj" ? <>{p.company_name} · CUI {p.cui} · {p.regcom}<br />{p.hq_address}, {p.locality}, {p.county}, {p.country} · rep. {p.rep_name}<br />{p.billing_email} · {p.phone}</>
    : <>PF {p.full_name}<br />{p.address}, {p.locality}, {p.county}, {p.country}<br />{p.billing_email} · {p.phone}</>;
}

export function SubscriberDetail({ u, plans, reload }) {
  const [plan, setPlan] = useState({ plan: u.subscription?.plan || "start", valid_until: u.subscription?.valid_until || "", status: u.subscription?.status || "activ", justification: "" });
  const [inv, setInv] = useState(null);
  const [hist, setHist] = useState(null);
  const [pay, setPay] = useState({});
  useEffect(() => { setPlan((p) => ({ ...p, plan: u.subscription?.plan || p.plan, valid_until: u.subscription?.valid_until || "", status: u.subscription?.status || "activ" })); }, [u.subscription?.valid_until, u.subscription?.plan, u.subscription?.status]);
  const call = async (fn, ok) => { try { await fn(); toast.success(ok); reload(); loadInv(); return true; } catch (e) { err(e); return false; } };
  const loadInv = () => api.get(`/admin/invoices?uid=${u.id}`).then((r) => setInv(r.data));
  const t = (k) => `${k}-${u.email}`;
  return (
    <div className="mt-3 rounded-xl border p-4 space-y-4 text-xs" style={{ borderColor: "var(--line)", background: "#fbfcfe" }} data-testid={t("sub-detail")}>
      <div><b>Date de facturare:</b><div className="mt-1" data-testid={t("sub-billing")}><Billing p={u.profile} /></div></div>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="den-field"><label>Abonament</label><select className="den-input" value={plan.plan} onChange={(e) => setPlan({ ...plan, plan: e.target.value })} data-testid={t("sub-plan-select")}>{plans.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select></div>
        <div className="den-field"><label>Valabil până la</label><input type="date" className="den-input" value={plan.valid_until} onChange={(e) => setPlan({ ...plan, valid_until: e.target.value })} data-testid={t("sub-plan-until")} /></div>
        <div className="den-field"><label>Stare</label><select className="den-input" value={plan.status} onChange={(e) => setPlan({ ...plan, status: e.target.value })} data-testid={t("sub-plan-status")}>{["activ", "suspendat", "anulat"].map((s) => <option key={s}>{s}</option>)}</select></div>
        <div className="den-field flex-1 min-w-[180px]"><label>Justificare (obligatorie)</label><input className="den-input" value={plan.justification} onChange={(e) => setPlan({ ...plan, justification: e.target.value })} data-testid={t("sub-plan-just")} /></div>
        <Btn onClick={() => call(() => api.post(`/admin/subscribers/${u.id}/plan`, plan), "Abonament actualizat")} data-testid={t("sub-plan-save")}>Atribuie manual</Btn>
      </div>
      <div className="flex flex-wrap gap-2">
        <Btn variant="secondary" onClick={() => call(() => api.post("/admin/invoices", { uid: u.id, plan: plan.plan, months: 1 }), "Proformă emisă")} data-testid={t("sub-new-invoice")}>Emite proformă (1 lună, {plan.plan.toUpperCase()})</Btn>
        <Btn variant="secondary" onClick={loadInv} data-testid={t("sub-load-invoices")}>Proforme și plăți</Btn>
        <Btn variant="secondary" onClick={() => api.get(`/admin/billing/history/${u.id}`).then((r) => setHist(r.data))} data-testid={t("sub-load-history")}>Istoric modificări</Btn>
      </div>
      {inv && <InvoiceList items={inv} actions={(i) => i.status !== "plătită" && i.status !== "anulată" && i.status !== "rambursată" ? <>
        <button className="font-bold" style={{ color: "#166534" }} onClick={() => setPay({ id: i.id, amount: i.total, method: "transfer bancar", reference: "", justification: "" })} data-testid={`invoice-record-${i.number}`}>Înregistrează plată</button>
        <button className="font-bold" style={{ color: "#9b2c2c" }} onClick={() => { const j = window.prompt("Motivul anulării:"); if (j) call(() => api.post(`/admin/invoices/${i.id}/cancel`, { justification: j }), "Proformă anulată"); }} data-testid={`invoice-cancel-${i.number}`}>Anulează</button></>
        : i.status === "plătită" ? <button className="font-bold" style={{ color: "var(--blue)" }} onClick={() => { const r = window.prompt("Seria și numărul facturii fiscale emise:", i.fiscal_ref || ""); if (r !== null) call(() => api.put(`/admin/invoices/${i.id}/fiscal`, { fiscal_ref: r }), "Factură asociată"); }} data-testid={`invoice-fiscal-${i.number}`}>{i.fiscal_ref ? `Factură ${i.fiscal_ref}` : "Asociază factura fiscală"}</button> : null} />}
      {pay.id && <div className="flex flex-wrap gap-2 items-end rounded-lg border p-3" style={{ borderColor: "var(--line)" }} data-testid="payment-form">
        {[["amount", "Sumă (RON)"], ["method", "Metodă"], ["reference", "Referință OP / chitanță"], ["justification", "Justificare"]].map(([k, l]) => (
          <div key={k} className="den-field"><label>{l}</label><input className="den-input" value={pay[k]} onChange={(e) => setPay({ ...pay, [k]: e.target.value })} data-testid={`payment-${k}`} /></div>))}
        <Btn onClick={() => call(() => api.post(`/admin/invoices/${pay.id}/payment`, pay), "Plată înregistrată").then((ok) => ok && setPay({}))} data-testid="payment-save">Salvează plata</Btn>
      </div>}
      {hist && <div className="space-y-1" data-testid={t("sub-history")}>{hist.map((h) => <div key={h.id}><b>{new Date(h.at).toLocaleString("ro-RO")}</b> · {h.kind} · {h.by} — {h.detail}</div>)}</div>}
    </div>
  );
}

export function SubscriberRow({ u, plans, reload }) {
  const [open, setOpen] = useState(false);
  const upd = async (body) => { try { await api.put(`/admin/subscribers/${u.id}`, body); toast.success("Salvat"); reload(); } catch (e) { err(e); } };
  return (
    <div className="border-t py-3" style={{ borderColor: "var(--line)" }} data-testid={`sub-row-${u.email}`}>
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <div className="min-w-[200px]"><b>{u.profile?.company_name || u.profile?.full_name || u.name}</b><div className="text-xs" style={{ color: "var(--muted)" }}>{u.email}</div></div>
        <span className="text-xs font-bold" data-testid={`sub-account-${u.email}`}>{ST[u.status]}</span>
        <span className="text-xs" data-testid={`sub-plan-${u.email}`}><b>{u.plan?.name}</b> · {u.plan?.status}{u.plan?.valid_until ? ` · până la ${u.plan.valid_until}` : ""}</span>
        <span className="text-xs" style={{ color: "var(--muted)" }}>{u.dossiers} dosare prosumator · {u.diu} DI-U</span>
        <div className="ml-auto flex gap-3 text-xs font-bold">
          {u.status !== "active" && <button style={{ color: "#166534" }} onClick={() => upd({ status: "active" })} data-testid={`sub-approve-${u.email}`}>Aprobă</button>}
          {u.status === "active" && <button style={{ color: "#8a5a00" }} onClick={() => upd({ status: "suspended" })} data-testid={`sub-suspend-${u.email}`}>Suspendă</button>}
          {u.status !== "disabled" && <button style={{ color: "#9b2c2c" }} onClick={() => upd({ status: "disabled" })} data-testid={`sub-disable-${u.email}`}>Dezactivează</button>}
          <button style={{ color: "var(--blue)" }} onClick={() => setOpen(!open)} data-testid={`sub-open-${u.email}`}>{open ? "Închide" : "Gestionează"}</button>
        </div>
      </div>
      {open && <SubscriberDetail u={u} plans={plans} reload={reload} />}
    </div>
  );
}
