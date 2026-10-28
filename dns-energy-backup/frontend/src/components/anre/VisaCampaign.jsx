import { useState } from "react";
import { toast } from "sonner";
import { Sparkles, Send } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { Btn } from "@/components/Layout";

function Draft({ it, set }) {
  return (
    <div className="border rounded-md p-3 space-y-2" style={{ borderColor: "var(--line)", opacity: it.on ? 1 : 0.5 }} data-testid={`campaign-item-${it.cui}`}>
      <label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" checked={it.on} onChange={(e) => set({ on: e.target.checked })} data-testid={`campaign-include-${it.cui}`} />
        {it.company} <span className="font-normal text-xs" style={{ color: it.days_left < 0 ? "#9b2c2c" : "#8a5a00" }}>{it.days_left < 0 ? `depășită cu ${-it.days_left} zile` : `în ${it.days_left} zile`} · {it.to}</span></label>
      {it.error && <div className="text-xs" style={{ color: "#9b2c2c" }}>{it.error}</div>}
      <input className="den-input" value={it.subject} placeholder="Subiect" onChange={(e) => set({ subject: e.target.value })} data-testid={`campaign-subject-${it.cui}`} />
      <textarea className="den-input min-h-[150px]" value={it.body} placeholder="Textul e-mailului" onChange={(e) => set({ body: e.target.value })} data-testid={`campaign-body-${it.cui}`} />
      {it.result && <div className="text-xs font-bold" style={{ color: it.result.sent ? "#166534" : "#9b2c2c" }} data-testid={`campaign-result-${it.cui}`}>{it.result.sent ? `Trimis la ${it.result.to}` : it.result.error}</div>}
    </div>
  );
}

export function VisaCampaign({ onClose, onSent }) {
  const [instr, setInstr] = useState("");
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const gen = async () => {
    setBusy(true);
    try { const { data } = await api.post("/admin/operators/campaign/drafts", { instructions: instr }, { timeout: 300000 }); setD({ ...data, items: data.items.map((i) => ({ ...i, on: !i.error })) }); }
    catch (e) { toast.error(e.response?.data?.detail || "Ciornele nu au putut fi generate"); } finally { setBusy(false); }
  };
  const sel = d?.items.filter((i) => i.on && i.subject.trim() && i.body.trim() && !i.result?.sent) || [];
  const send = async () => {
    if (!window.confirm(`Trimiteți ${sel.length} e-mailuri?`)) return;
    setBusy(true);
    try {
      const { data } = await api.post("/admin/operators/campaign/send", { items: sel.map(({ tenant, subject, body }) => ({ tenant, subject, body })) });
      const by = Object.fromEntries(data.results.map((r) => [r.tenant, r]));
      setD({ ...d, items: d.items.map((i) => (by[i.tenant] ? { ...i, result: by[i.tenant] } : i)) });
      toast.success(`${data.sent} din ${data.results.length} e-mailuri trimise`); onSent();
    } catch (e) { toast.error(e.response?.data?.detail || "Eroare la trimitere"); } finally { setBusy(false); }
  };
  const upd = (t, p) => setD({ ...d, items: d.items.map((i) => (i.tenant === t ? { ...i, ...p } : i)) });
  return (
    <Dialog open onOpenChange={(v) => !v && !busy && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="campaign-dialog">
        <DialogHeader><DialogTitle>Campanie e-mail — vizări în 30 de zile și depășite</DialogTitle></DialogHeader>
        <p className="text-xs" style={{ color: "var(--muted)" }}>Asistentul AI redactează câte un e-mail pentru fiecare firmă. Firmele contactate în ultimele 7 zile sunt sărite. Nimic nu pleacă până nu apăsați „Trimite tot”.</p>
        <div className="flex gap-2"><input className="den-input flex-1" placeholder="Instrucțiuni opționale pentru toate e-mailurile" value={instr} onChange={(e) => setInstr(e.target.value)} data-testid="campaign-instructions" />
          <Btn variant="secondary" onClick={gen} disabled={busy} data-testid="campaign-generate"><Sparkles size={14} /> {busy && !d ? "Se redactează..." : d ? "Regenerează" : "Generează ciornele"}</Btn></div>
        {d && <>
          {!!d.skipped.length && <div className="text-xs" data-testid="campaign-skipped">Sărite: {d.skipped.map((s) => `${s.company} (${s.reason})`).join("; ")}</div>}
          {!d.items.length && <div className="text-sm py-4 text-center" style={{ color: "var(--muted)" }} data-testid="campaign-empty">Nicio firmă de contactat acum.</div>}
          <div className="space-y-3">{d.items.map((it) => <Draft key={it.tenant} it={it} set={(p) => upd(it.tenant, p)} />)}</div>
          {!!d.items.length && <div className="flex justify-end"><Btn onClick={send} disabled={busy || !sel.length} data-testid="campaign-send-all"><Send size={14} /> Trimite tot ({sel.length})</Btn></div>}
        </>}
      </DialogContent>
    </Dialog>
  );
}
