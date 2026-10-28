import { AlertTriangle, XCircle, CheckCircle2 } from "lucide-react";

export function Issues({ errors = [], warnings = [], testid }) {
  if (!errors?.length && !warnings?.length) return null;
  return (
    <div className="mt-3 space-y-1.5" data-testid={testid}>
      {errors.map((e, i) => <div key={`e${i}`} className="flex gap-2 text-xs rounded-lg px-3 py-2" style={{ background: "#fff0f0", color: "#9b2c2c" }}><XCircle size={14} className="shrink-0 mt-0.5" />{e}</div>)}
      {warnings.map((w, i) => <div key={`w${i}`} className="flex gap-2 text-xs rounded-lg px-3 py-2" style={{ background: "#fff8e6", color: "#8a5a00" }}><AlertTriangle size={14} className="shrink-0 mt-0.5" />{w}</div>)}
    </div>
  );
}

export function Totals({ res }) {
  if (!res) return null;
  const t = res.totals;
  const items = [["Panouri", `${t.kwp} kWp`, "tot-kwp"], ["Invertoare", `${t.inverters_kw} kW`, "tot-kw"], ["Evacuat", `${t.export_kw} kW`, "tot-export"],
    ["Stocare", `${t.storage_kwh} kWh`, "tot-kwh"], ["Nr. panouri", t.panels, "tot-panels"], ["Invertoare", `${t.inverters} buc.`, "tot-inv"]];
  const ok = !res.errors.length && !res.warnings.length;
  return (
    <div className="rounded-xl p-4 text-white" style={{ background: "var(--navy)" }} data-testid="cef-totals">
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
        {items.map(([l, v, id]) => (
          <div key={id}><div className="text-[10px] uppercase tracking-wider" style={{ color: "#8fa3c2" }}>{l}</div><div className="font-extrabold text-lg" data-testid={id}>{v}</div></div>
        ))}
      </div>
      <div className="mt-3 text-xs flex items-center gap-2" data-testid="cef-status">
        {ok ? <><CheckCircle2 size={14} color="#4ade80" /> Configurație fără incompatibilități detectate</> :
          <><AlertTriangle size={14} color="#fbbf24" /> {res.errors.length} erori · {res.warnings.length} avertizări</>}
        {res.grid.anti && <span className="ml-2 rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: "#7f1d1d" }}>Tablou antiinsularizare inclus</span>}
      </div>
    </div>
  );
}
