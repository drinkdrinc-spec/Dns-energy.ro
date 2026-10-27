import { useState } from "react";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Btn } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import { can } from "@/lib/plan";
import { streamAI } from "@/lib/ai";

export function AiDossierCheck({ id }) {
  const { user } = useAuth();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  if (!can(user, "ai_gpt")) return null;
  const run = async () => {
    setBusy(true); setText("");
    try { await streamAI(`/ai/dossier/${id}/check`, {}, setText); }
    catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  };
  return (
    <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f7fbff" }} data-testid="ai-check-section">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div><h3 className="font-bold flex items-center gap-2"><Sparkles size={16} style={{ color: "var(--blue)" }} /> Verificare AI înainte de trimitere</h3>
          <p className="text-[11px]" style={{ color: "var(--muted)" }}>ChatGPT analizează datele salvate, opisul și configurația CEF. Rezultatul este orientativ — verificarea finală o face electricianul autorizat.</p></div>
        <Btn variant="secondary" onClick={run} disabled={busy} data-testid="ai-check-btn"><Sparkles size={14} /> {busy ? "Se verifică..." : "Verifică dosarul cu AI"}</Btn>
      </div>
      {text && <div className="mt-3 text-sm whitespace-pre-wrap rounded-lg bg-white border p-3" style={{ borderColor: "var(--line)" }} data-testid="ai-check-result">{text}</div>}
    </div>
  );
}
