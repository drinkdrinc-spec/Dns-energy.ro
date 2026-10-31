import { useState } from "react";
import { ExternalLink, ShieldCheck, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Btn } from "@/components/Layout";
import { useAuth } from "@/context/AuthContext";
import { can } from "@/lib/plan";
import { api } from "@/lib/api";

export function AiOdReview({ id, module }) {
  const { user } = useAuth();
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  if (!can(user, "ai_gpt")) return null;
  const run = async () => {
    setBusy(true); setResult(null);
    try { const { data } = await api.post(`/ai/${module}/${id}/od-check`, {}, { timeout: 180000 }); setResult(data); }
    catch (e) { toast.error(e.response?.data?.detail || e.message || "Verificarea OD a eșuat"); }
    finally { setBusy(false); }
  };
  return <section className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "#f7fbff" }} data-testid={`ai-od-review-${module}`}>
    <div className="flex items-center justify-between flex-wrap gap-3">
      <div><h3 className="font-bold flex items-center gap-2"><ShieldCheck size={16} style={{ color: "var(--blue)" }} /> Verificare dosar după OD</h3>
        <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Analizează datele tehnice, documentele și formularele înregistrate pentru operatorul ales. Indică lipsuri, dar nu certifică dosarul și nu înlocuiește formularul oficial curent.</p></div>
      <Btn variant="secondary" onClick={run} disabled={busy} data-testid={`ai-od-review-button-${module}`}><Sparkles size={14} />{busy ? "Verifică dosarul…" : "Verifică cerințele OD"}</Btn>
    </div>
    {result && <div className="mt-3 space-y-3">
      <div className="text-sm whitespace-pre-wrap rounded-lg bg-white border p-3" style={{ borderColor: "var(--line)" }} data-testid={`ai-od-review-result-${module}`}>{result.review || "AI nu a returnat o analiză."}</div>
      {result.sources?.length > 0 && <div className="rounded-lg bg-white border p-3" style={{ borderColor: "var(--line)" }}>
        <div className="text-xs font-bold mb-2">Formulare oficiale din registru — {result.operator}</div>
        <div className="space-y-1">{result.sources.map((s, i) => <a key={`${s.url}-${i}`} href={s.url} target="_blank" rel="noopener noreferrer" className="flex items-start gap-2 text-xs underline" style={{ color: "var(--blue)" }}>
          <ExternalLink size={12} className="mt-0.5 shrink-0" /> <span>{s.title}{s.version ? ` · ${s.version}` : ""} · {s.status || "versiune neverificată"}</span>
        </a>)}</div>
      </div>}
      <p className="text-[11px]" style={{ color: "#8a5a00" }} data-testid={`ai-od-review-notice-${module}`}>{result.notice}</p>
    </div>}
  </section>;
}
