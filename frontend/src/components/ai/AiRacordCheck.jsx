import { useState } from "react";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Btn } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import { can } from "@/lib/plan";
import { streamAI } from "@/lib/ai";
import { api } from "@/lib/api";

export function AiRacordCheck({ id, module }) {
  const { user } = useAuth();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  if (!can(user, "ai_gpt")) return null;
  const run = async () => {
    setBusy(true); setText("");
    try {
      const r = await api.post(`/ai/${module}/${id}/prepare`);
      const prefix = `Date copiate din fișa clientului: ${r.data.filled?.join(", ") || "niciuna"} (câmpurile deja completate au fost păstrate).\n\nVerificare AI:\n`;
      setText(prefix);
      await streamAI(`/ai/${module}/${id}/check`, {}, (chunk) => setText(prefix + chunk));
    } catch (e) { toast.error(e.response?.data?.detail || e.message || "Verificarea a eșuat"); }
    finally { setBusy(false); }
  };
  return <section className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f7fbff" }} data-testid={`ai-${module}-check`}>
    <div className="flex items-center justify-between flex-wrap gap-2">
      <div><h3 className="font-bold flex items-center gap-2"><Sparkles size={16} style={{ color: "var(--blue)" }} /> AI verificator și completare</h3>
        <p className="text-[11px]" style={{ color: "var(--muted)" }}>Preia doar date existente în fișa clientului, verifică documentele și calculele și arată ce lipsește. Nu inventează valori sau măsurători.</p></div>
      <Btn variant="secondary" onClick={run} disabled={busy}><Sparkles size={14} /> {busy ? "Verifică…" : "Verifică și completează"}</Btn>
    </div>
    {text && <div className="mt-3 text-sm whitespace-pre-wrap rounded-lg bg-white border p-3" style={{ borderColor: "var(--line)" }}>{text}</div>}
  </section>;
}
