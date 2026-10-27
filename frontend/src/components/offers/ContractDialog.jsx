import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const money = (v, c) => `${(v || 0).toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${c === "EUR" ? "€" : "lei"}`;

export function ContractDialog({ offer, open, onClose, onDone }) {
  const [pay, setPay] = useState({ mode: "integral", due_days: "", advance_type: "percent", advance_value: "", advance_days: "", balance_rule: "", tranches: [] });
  const [f, setF] = useState({ execution_term: "", works_warranty_months: "", place: "", date: new Date().toISOString().slice(0, 10) });
  const [calc, setCalc] = useState(null);
  const [err, setErr] = useState("");
  const P = (k, v) => setPay({ ...pay, [k]: v });
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => api.post(`/offers/${offer.id}/contract/preview`, { payment: pay }).then((r) => { setCalc(r.data); setErr(""); }).catch((e) => { setCalc(null); setErr(e.response?.data?.detail || ""); }), 300);
    return () => clearTimeout(t);
  }, [pay, open, offer.id]);
  const gen = async (regenerate = false) => {
    try { const { data } = await api.post(`/offers/${offer.id}/contract`, { payment: pay, ...f, regenerate }); toast.success(`Contract nr. ${data.number} generat`); onDone(data); onClose(); }
    catch (e) {
      if (e.response?.status === 409 && window.confirm(`${e.response.data.detail}\n\nRegenerezi contractul?`)) return gen(true);
      toast.error(e.response?.data?.detail || "Eroare");
    }
  };
  const field = (k, l, t = "text", obj = "f") => (
    <div className="den-field"><label>{l}</label><input className="den-input" type={t} value={(obj === "f" ? f : pay)[k] ?? ""} data-testid={`contract-${k}`}
      onChange={(e) => (obj === "f" ? setF({ ...f, [k]: e.target.value }) : P(k, e.target.value))} /></div>);
  const tr = pay.tranches || [];
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="contract-dialog">
        <DialogHeader><DialogTitle>Generează contract din oferta nr. {offer.number}</DialogTitle></DialogHeader>
        <p className="text-xs" style={{ color: "var(--muted)" }}>Verifică datele beneficiarului din ofertă înainte de generare. Total ofertă: <b>{money(offer.totals?.net, offer.currency)}</b> + TVA = <b>{money(offer.totals?.gross, offer.currency)}</b></p>
        <div className="flex gap-4 text-sm">{[["integral", "A. Plată integrală"], ["avans", "B. Plată cu avans"]].map(([k, l]) => (
          <label key={k} className="flex items-center gap-2"><input type="radio" checked={pay.mode === k} onChange={() => P("mode", k)} data-testid={`pay-mode-${k}`} /> {l}</label>))}</div>
        {pay.mode === "integral" ? (
          <div className="grid sm:grid-cols-3 gap-2">{field("due_days", "Termen de plată (zile)", "number", "p")}{field("due_date", "sau data scadenței", "date", "p")}{field("due_rule", "sau regula scadenței", "text", "p")}</div>
        ) : (
          <div className="space-y-2">
            <div className="grid sm:grid-cols-4 gap-2">
              <div className="den-field"><label>Avans ca</label><select className="den-input" value={pay.advance_type} onChange={(e) => P("advance_type", e.target.value)} data-testid="contract-advance_type"><option value="percent">procent (%)</option><option value="amount">sumă fixă (fără TVA)</option></select></div>
              {field("advance_value", pay.advance_type === "percent" ? "Avans (%)" : "Avans (sumă)", "number", "p")}{field("advance_days", "Termen avans (zile)", "number", "p")}{field("balance_rule", "Diferența se achită", "text", "p")}
            </div>
            <div className="text-xs font-bold">Tranșe suplimentare (opțional — înlocuiesc avansul simplu)</div>
            {tr.map((x, i) => (
              <div key={i} className="grid grid-cols-[1fr_110px_90px_1fr_24px] gap-1.5">
                {["label", "type", "value", "due"].map((k) => k === "type"
                  ? <select key={k} className="den-input !text-xs" value={x.type || "percent"} onChange={(e) => P("tranches", tr.map((y, j) => (j === i ? { ...y, type: e.target.value } : y)))} data-testid={`tranche-${i}-type`}><option value="percent">%</option><option value="amount">sumă</option></select>
                  : <input key={k} className="den-input !text-xs" placeholder={{ label: "Denumire", value: "Valoare", due: "Termen / etapă" }[k]} value={x[k] ?? ""} onChange={(e) => P("tranches", tr.map((y, j) => (j === i ? { ...y, [k]: e.target.value } : y)))} data-testid={`tranche-${i}-${k}`} />)}
                <button onClick={() => P("tranches", tr.filter((_, j) => j !== i))} data-testid={`tranche-${i}-del`}>×</button>
              </div>))}
            <button className="text-xs font-bold" style={{ color: "var(--blue)" }} onClick={() => P("tranches", [...tr, { label: `Tranșa ${tr.length + 1}`, type: "percent", value: "", due: "" }])} data-testid="tranche-add">+ Tranșă</button>
          </div>
        )}
        {calc && <div className="rounded-lg border p-3 text-xs" style={{ borderColor: "var(--line)", background: "#f7fbff" }} data-testid="contract-pay-preview">{calc.text}</div>}
        {err && <div className="text-xs" style={{ color: "#9b2c2c" }} data-testid="contract-pay-error">{err}</div>}
        <div className="grid sm:grid-cols-2 gap-2">{field("execution_term", "Termen de execuție (ex. maxim 30 zile calendaristice)")}{field("works_warranty_months", "Garanție manoperă (luni)", "number")}{field("place", "Locul încheierii (localitate)")}{field("date", "Data contractului", "date")}</div>
        <div className="flex justify-end gap-2"><Btn variant="secondary" onClick={onClose} data-testid="contract-cancel">Anulează</Btn><Btn onClick={() => gen(false)} disabled={!calc} data-testid="contract-generate">Generează contract</Btn></div>
      </DialogContent>
    </Dialog>
  );
}
