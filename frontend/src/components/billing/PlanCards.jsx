import { Check } from "lucide-react";
import { lei } from "@/lib/plan";

export function PlanCards({ plans, features, current, selected, onSelect }) {
  return (
    <div className="grid md:grid-cols-3 gap-4" data-testid="plan-cards">
      {plans.map((p) => {
        const sel = selected === p.code;
        const feats = p.features.includes("*") ? ["Toate modulele platformei, inclusiv cele adăugate ulterior"] : p.features.map((f) => features[f] || f);
        return (
          <button type="button" key={p.code} onClick={() => onSelect?.(p.code)} data-testid={`plan-card-${p.code}`}
            className="text-left rounded-2xl border-2 p-5 bg-white transition-[transform,border-color] hover:-translate-y-0.5"
            style={{ borderColor: sel ? "var(--blue)" : "var(--line)" }}>
            <div className="flex items-center justify-between">
              <span className="text-lg font-extrabold">{p.name}</span>
              {current === p.code && <span className="text-[10px] font-bold rounded-full px-2 py-0.5" style={{ background: "#ecfdf3", color: "#166534" }}>actual</span>}
            </div>
            <div className="mt-3 text-2xl font-extrabold" data-testid={`plan-net-${p.code}`}>{lei(p.net)}<span className="text-xs font-semibold" style={{ color: "var(--muted)" }}> / lună fără TVA</span></div>
            <div className="text-xs mt-1" style={{ color: "var(--muted)" }} data-testid={`plan-vat-${p.code}`}>TVA {p.vat_rate}%: {lei(p.vat)}</div>
            <div className="text-sm font-bold mt-1" data-testid={`plan-total-${p.code}`}>Total de plată: {lei(p.total)}</div>
            <p className="text-xs mt-3" style={{ color: "var(--muted)" }}>{p.description}</p>
            <ul className="mt-3 space-y-1">{feats.map((f) => <li key={f} className="text-xs flex gap-1.5"><Check size={13} style={{ color: "var(--blue)" }} className="shrink-0 mt-0.5" />{f}</li>)}
              {p.max_inverters > 0 && <li className="text-xs flex gap-1.5"><Check size={13} className="shrink-0 mt-0.5" style={{ color: "#8a5a00" }} />Maximum {p.max_inverters} invertor / dosar</li>}</ul>
          </button>
        );
      })}
    </div>
  );
}
