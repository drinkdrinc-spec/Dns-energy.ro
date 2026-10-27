import { useEffect, useState } from "react";
import { Sparkles, Lock } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Btn } from "@/components/Layout";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const SEV = { critic: ["#fff0f0", "#9b2c2c"], important: ["#fff8e6", "#8a5a00"], minor: ["#eef4ff", "#1d4ed8"] };

export function AiPrecheck({ id, open, onClose, onFinalize, base = "dossier", title = "Verificare AI înainte de finalizare", action = "Finalizează dosarul" }) {
  const [pc, setPc] = useState(null);
  const [err, setErr] = useState("");
  const [checked, setChecked] = useState([]);
  useEffect(() => {
    if (!open) return;
    setPc(null); setErr(""); setChecked([]);
    api.post(`/ai/${base}/${id}/precheck`, {}, { timeout: 180000 }).then((r) => setPc(r.data)).catch((e) => setErr(e.response?.data?.detail || "Verificarea AI a eșuat"));
  }, [open, id, base]);
  const items = pc?.items || [];
  const left = items.length - checked.length;
  const finalize = async () => {
    if (pc && left > 0 && !window.confirm(`Mai sunt ${left} puncte nebifate din verificarea AI. Continui oricum?`)) return;
    try { await onFinalize(); } catch (e) { return; }
    try { if (pc) await api.post(`/ai/${base}/${id}/precheck/ack`, { checked }); } catch (e) { /* ack optional */ }
    onClose();
  };
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="ai-precheck-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><Sparkles size={18} style={{ color: "var(--blue)" }} /> {title}</DialogTitle></DialogHeader>
        {!pc && !err && <p className="text-sm" style={{ color: "var(--muted)" }} data-testid="ai-precheck-loading">ChatGPT verifică dosarul... (până la un minut)</p>}
        {err && <p className="text-sm" style={{ color: "#9b2c2c" }} data-testid="ai-precheck-error">{err}</p>}
        {pc && !items.length && <p className="text-sm font-bold" style={{ color: "#166534" }} data-testid="ai-precheck-ok">Nu au fost găsite lipsuri sau neconcordanțe.</p>}
        <div className="space-y-2 max-h-[55vh] overflow-y-auto">{items.map((it, i) => {
          const [bg, fg] = SEV[it.severity] || SEV.important;
          return (
            <label key={i} className="flex items-start gap-3 rounded-lg border px-3 py-2 text-sm cursor-pointer" style={{ borderColor: "var(--line)" }} data-testid={`ai-precheck-item-${i}`}>
              <input type="checkbox" className="mt-1" checked={checked.includes(i)} onChange={(e) => setChecked(e.target.checked ? [...checked, i] : checked.filter((x) => x !== i))} data-testid={`ai-precheck-check-${i}`} />
              <span className="flex-1">{it.text}</span>
              <span className="text-[10px] font-bold uppercase rounded-full px-2 py-0.5" style={{ background: bg, color: fg }}>{it.severity}</span>
            </label>);
        })}</div>
        {items.length > 0 && <p className="text-xs" style={{ color: left ? "#8a5a00" : "#166534" }} data-testid="ai-precheck-left">{left ? `${left} puncte nebifate — poți continua oricum, după confirmare.` : "Toate punctele au fost bifate."}</p>}
        <div className="flex justify-end gap-2">
          <Btn variant="secondary" onClick={onClose} data-testid="ai-precheck-cancel">Anulează</Btn>
          <Btn onClick={finalize} disabled={!pc && !err} data-testid="ai-precheck-finalize"><Lock size={14} /> {action}</Btn>
        </div>
      </DialogContent>
    </Dialog>
  );
}
