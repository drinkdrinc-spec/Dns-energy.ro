import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { Btn } from "@/components/Layout";

const dt = (s) => new Date(s).toLocaleDateString("ro-RO");

export function VisaCallDialog({ op, onClose, onSaved }) {
  const [hist, setHist] = useState(null);
  const [f, setF] = useState({ outcome: "", note: "", callback_date: "" });
  useEffect(() => { api.get(`/admin/operators/${op.tenant}/calls`).then((r) => setHist(r.data)); }, [op.tenant]);
  const save = async () => {
    try { await api.post(`/admin/operators/${op.tenant}/calls`, f); toast.success("Apel notat"); onSaved(); onClose(); }
    catch (e) { toast.error(e.response?.data?.detail || "Eroare"); }
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg" data-testid="call-dialog">
        <DialogHeader><DialogTitle>Apel — {op.company}</DialogTitle></DialogHeader>
        <p className="text-xs" style={{ color: "var(--muted)" }}>{op.contact_name} · {op.contact_phone || "fără telefon"}</p>
        <select className="den-input" value={f.outcome} onChange={(e) => setF({ ...f, outcome: e.target.value })} data-testid="call-outcome">
          <option value="">Rezultatul apelului...</option>{(hist?.outcomes || []).map((o) => <option key={o} value={o}>{o}</option>)}</select>
        <textarea className="den-input min-h-[80px]" placeholder="Notiță (opțional)" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} data-testid="call-note" />
        <label className="text-xs">Data revenirii (opțional)<input type="date" className="den-input" value={f.callback_date} onChange={(e) => setF({ ...f, callback_date: e.target.value })} data-testid="call-callback" /></label>
        <div className="flex justify-end"><Btn onClick={save} disabled={!f.outcome} data-testid="call-save">Salvează apelul</Btn></div>
        {!!hist?.items.length && <div className="text-xs space-y-1 border-t pt-2" style={{ borderColor: "var(--line)" }} data-testid="call-history">
          <b>Istoric apeluri</b>{hist.items.map((c) => <div key={c.id}>{dt(c.at)} — <b>{c.outcome}</b>{c.callback_date && ` · revenire ${dt(c.callback_date)}`}{c.note && ` · ${c.note}`} <span style={{ color: "var(--muted)" }}>({c.by})</span></div>)}</div>}
      </DialogContent>
    </Dialog>
  );
}
