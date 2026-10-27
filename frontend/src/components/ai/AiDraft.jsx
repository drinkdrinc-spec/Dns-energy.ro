import { useState } from "react";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { streamAI } from "@/lib/ai";

export function AiDraft({ module, field, label, form, onApply }) {
  const [open, setOpen] = useState(false);
  const [instr, setInstr] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true); setText("");
    try { await streamAI("/ai/draft", { module, field, label, current: form[field] || "", instructions: instr, form }, setText); }
    catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  };
  if (!open) return <button type="button" className="text-[11px] font-bold inline-flex items-center gap-1 mt-1" style={{ color: "var(--blue)" }} onClick={() => setOpen(true)} data-testid={`ai-draft-open-${field}`}><Sparkles size={12} /> Redactează cu AI</button>;
  return (
    <div className="mt-2 rounded-lg border p-2 text-xs space-y-2" style={{ borderColor: "var(--line)", background: "#f7fbff" }} data-testid={`ai-draft-${field}`}>
      <input className="den-input" placeholder="Instrucțiuni (opțional), ex. „recepție fără obiecțiuni, 2 invertoare”" value={instr} onChange={(e) => setInstr(e.target.value)} data-testid={`ai-draft-instr-${field}`} />
      <div className="flex gap-3">
        <button type="button" className="font-bold" style={{ color: "var(--blue)" }} onClick={run} disabled={busy} data-testid={`ai-draft-run-${field}`}>{busy ? "Se redactează..." : "Generează propunere"}</button>
        <button type="button" onClick={() => { setOpen(false); setText(""); }} data-testid={`ai-draft-close-${field}`}>Închide</button>
      </div>
      {text && <>
        <div className="whitespace-pre-wrap bg-white border rounded p-2" style={{ borderColor: "var(--line)" }} data-testid={`ai-draft-result-${field}`}>{text}</div>
        {!busy && <button type="button" className="font-bold" style={{ color: "#166534" }} onClick={() => { onApply(field, text); setOpen(false); setText(""); toast.success("Text preluat — verifică și salvează"); }} data-testid={`ai-draft-apply-${field}`}>Folosește textul (verifică înainte de salvare)</button>}
      </>}
    </div>
  );
}
