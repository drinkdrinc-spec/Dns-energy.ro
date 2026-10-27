import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Btn } from "@/components/Layout";
import { BillingForm } from "@/components/billing/BillingForm";
import { PlanCards } from "@/components/billing/PlanCards";
import { InvoiceList } from "@/components/billing/InvoiceList";
import { lei } from "@/lib/plan";
import { CreditCard, ShieldCheck } from "lucide-react";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Eroare");

function PaymentWatcher({ sid, onDone }) {
  const [st, setSt] = useState("verificare");
  useEffect(() => {
    let n = 0, stop = false;
    const tick = async () => {
      try {
        const { data } = await api.get(`/billing/payment-status/${sid}`);
        if (data.payment_status === "paid") { setSt("paid"); onDone(true); return; }
        if (["expired", "failed", "cancelled"].includes(data.payment_status)) { setSt(data.status); onDone(false); return; }
      } catch { /* retry */ }
      if (!stop && ++n < 20) setTimeout(tick, 2500); else setSt("timeout");
    };
    tick();
    return () => { stop = true; };
  }, [sid]); // eslint-disable-line
  const msg = { verificare: "Verificăm plata la furnizor… (abonamentul se activează doar după confirmarea furnizorului)", paid: "Plata a fost confirmată de furnizor — abonamentul este activ.",
    timeout: "Confirmarea întârzie. Reîncărcați pagina peste câteva minute; abonamentul se activează automat la confirmarea furnizorului." }[st] || `Plata nu a fost finalizată (${st}).`;
  return <div className="den-panel mb-5 text-sm font-semibold" style={{ background: st === "paid" ? "#ecfdf3" : "#fff8e6" }} data-testid="payment-status">{msg}</div>;
}

export default function Subscription() {
  const { refresh } = useAuth();
  const [sp, setSp] = useSearchParams();
  const [me, setMe] = useState(null);
  const [cat, setCat] = useState(null);
  const [prof, setProf] = useState({});
  const [sel, setSel] = useState("");
  const [months, setMonths] = useState(1);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/billing/me").then((r) => { setMe(r.data); setProf(r.data.profile || {}); setSel((s) => s || r.data.plan.code || "pro"); }).catch(err);
  useEffect(() => { load(); api.get("/billing/plans").then((r) => setCat(r.data)); if (sp.get("anulat")) toast.info("Plata a fost anulată — puteți genera oricând un link nou."); }, []); // eslint-disable-line
  const [q, setQ] = useState(null);
  useEffect(() => { if (sel) api.get(`/billing/quote?plan=${sel}&months=${months}`).then((r) => setQ(r.data)).catch((e) => setQ({ error: formatApiErrorDetail(e.response?.data?.detail) })); }, [sel, months, me?.plan?.code, me?.plan?.valid_until]);
  if (!me || !cat) return null;
  const p = me.plan;
  const plan = cat.plans.find((x) => x.code === sel);
  const saveProf = async () => { try { const { data } = await api.put("/billing/profile", prof); setProf(data); toast.success("Datele de facturare au fost salvate"); load(); } catch (e) { err(e); } };
  const pay = async () => {
    if (!me.profile?.client_type) { toast.error("Completați și salvați întâi datele de facturare"); return; }
    setBusy(true);
    try { const { data } = await api.post("/billing/checkout", { plan: sel, months, origin_url: window.location.origin }); window.location.href = data.checkout_url; }
    catch (e) { err(e); setBusy(false); }
  };
  return (
    <div>
      <PageHeader eyebrow="Cont" title="Abonament și facturare" sub="Alegeți abonamentul, verificați baza de impozitare, TVA-ul și totalul, apoi plătiți securizat. Cardul nu este debitat automat la reînnoire." />
      {sp.get("session_id") && <PaymentWatcher sid={sp.get("session_id")} onDone={(ok) => { if (ok) { refresh(); load(); } setTimeout(() => setSp({}), 8000); }} />}
      <div className="den-panel mb-5 flex flex-wrap items-center gap-6" data-testid="current-plan">
        <div><div className="text-[11px] font-bold uppercase" style={{ color: "var(--muted)" }}>Abonament curent</div><div className="text-2xl font-extrabold" data-testid="current-plan-name">{p.name}</div></div>
        <div><div className="text-[11px] font-bold uppercase" style={{ color: "var(--muted)" }}>Stare</div><span data-testid="current-plan-status"><span className="text-xs font-bold rounded-full px-2 py-0.5" style={p.active ? { background: "#ecfdf3", color: "#166534" } : { background: "#fff8e6", color: "#8a5a00" }}>{p.status}</span></span></div>
        <div><div className="text-[11px] font-bold uppercase" style={{ color: "var(--muted)" }}>Valabil până la</div><div className="font-bold" data-testid="current-plan-until">{p.valid_until || "—"}</div></div>
      </div>
      <h2 className="text-base md:text-lg font-extrabold mb-3">1. Date de facturare</h2>
      <div className="den-panel mb-6"><BillingForm value={prof} onChange={setProf} /><Btn className="mt-4" onClick={saveProf} data-testid="billing-save">Salvează datele de facturare</Btn></div>
      <h2 className="text-base md:text-lg font-extrabold mb-3">2. Alegeți abonamentul</h2>
      <PlanCards plans={cat.plans} features={cat.features} current={p.active ? p.code : null} selected={sel} onSelect={setSel} />
      <div className="den-panel mt-5 mb-6 flex flex-wrap items-end gap-6" data-testid="checkout-box">
        <div className="den-field"><label>Perioadă</label><select className="den-input" value={months} onChange={(e) => setMonths(+e.target.value)} data-testid="checkout-months">
          {[1, 3, 6, 12].map((m) => <option key={m} value={m}>{m} {m === 1 ? "lună" : "luni"}</option>)}</select></div>
        <div className="text-sm space-y-0.5" data-testid="checkout-summary">
          {q?.error ? <div className="font-semibold" style={{ color: "#9b2c2c" }} data-testid="checkout-error">{q.error}</div> : q && <>
            {q.credit > 0 ? <><div>Preț abonament: {lei(q.gross)}</div><div style={{ color: "#166534" }} data-testid="checkout-credit">Credit din abonamentul actual: −{lei(q.credit)} <span className="text-[11px]">({q.credit_note})</span></div></>
              : q.credit_note && <div className="text-[11px]" style={{ color: "var(--muted)" }} data-testid="checkout-credit-note">{q.credit_note}</div>}
            <div>Bază de impozitare: <b data-testid="checkout-net">{lei(q.net)}</b></div><div>TVA {q.vat_rate}%: <b data-testid="checkout-vat">{lei(q.vat)}</b></div>
            <div className="text-lg font-extrabold" data-testid="checkout-total">Total de plată: {lei(q.total)}</div></>}</div>
        <Btn onClick={pay} disabled={busy || !plan || q?.error} data-testid="pay-btn"><CreditCard size={15} />{busy ? "Se generează linkul…" : "Plătește abonamentul"}</Btn>
        <p className="text-[11px] flex items-center gap-1 w-full" style={{ color: "var(--muted)" }}><ShieldCheck size={13} />Plata se face pe pagina securizată Stripe (mod test: card 4242 4242 4242 4242). D-ENERGY nu stochează datele cardului; abonamentul se activează doar după confirmarea verificată a plății.</p>
      </div>
      <h2 className="text-base md:text-lg font-extrabold mb-3">Proforme și plăți</h2>
      <div className="den-panel mb-6"><InvoiceList items={me.invoices} actions={(i) => i.status === "în așteptarea plății" && i.pay_url ? <a href={i.pay_url} className="font-bold" style={{ color: "#166534" }} data-testid={`invoice-pay-${i.number}`}>Plătește</a> : null} /></div>
      <h2 className="text-base md:text-lg font-extrabold mb-3">Istoric</h2>
      <div className="den-panel text-xs space-y-1" data-testid="billing-history">{me.history.map((h) => <div key={h.id}><b>{new Date(h.at).toLocaleString("ro-RO")}</b> · {h.kind} — {h.detail}</div>)}</div>
    </div>
  );
}
