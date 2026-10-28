import { useState } from "react";
import { toast } from "sonner";
import { Sparkles, Send } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { streamAI } from "@/lib/ai";
import { Btn } from "@/components/Layout";

export function VisaEmailDialog({ op, onClose, onSent }) {
  const [instr, setInstr] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const draft = async () => {
    setBusy(true);
    try {
      const split = (t) => { const m = t.match(/^\s*Subiect:\s*(.*)\n?([\s\S]*)$/i); if (m) { setSubject(m[1].trim()); setBody(m[2].replace(/^\n+/, "")); } else setBody(t); };
      split(await streamAI(`/admin/operators/${op.tenant}/ai-email`, { instructions: instr }, split));
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const send = async () => {
    setBusy(true);
    try { const { data } = await api.post(`/admin/operators/${op.tenant}/email`, { subject, body }); toast.success(`E-mail trimis la ${data.to}`); onSent(); onClose(); }
    catch (e) { toast.error(e.response?.data?.detail || "E-mailul nu a putut fi trimis"); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="visa-email-dialog">
        <DialogHeader><DialogTitle>E-mail către {op.company}</DialogTitle></DialogHeader>
        <p className="text-xs" style={{ color: "var(--muted)" }}>Destinatar: {op.contact_email || "—"} · Redactat de asistentul AI, îl puteți modifica înainte de trimitere.</p>
        <div className="flex gap-2"><input className="den-input flex-1" placeholder="Instrucțiuni opționale (ex.: amintește de discuția telefonică)" value={instr} onChange={(e) => setInstr(e.target.value)} data-testid="visa-email-instructions" />
          <Btn variant="secondary" onClick={draft} disabled={busy} data-testid="visa-email-draft"><Sparkles size={14} /> {body ? "Rescrie" : "Redactează cu AI"}</Btn></div>
        <input className="den-input" placeholder="Subiect" value={subject} onChange={(e) => setSubject(e.target.value)} data-testid="visa-email-subject" />
        <textarea className="den-input min-h-[260px]" placeholder="Textul e-mailului" value={body} onChange={(e) => setBody(e.target.value)} data-testid="visa-email-body" />
        <div className="flex justify-end"><Btn onClick={send} disabled={busy || !subject.trim() || !body.trim()} data-testid="visa-email-send"><Send size={14} /> Trimite</Btn></div>
      </DialogContent>
    </Dialog>
  );
}
